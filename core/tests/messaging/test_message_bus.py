import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from core.bases.models import QiMessage, QiMessageType, QiSession
from core.config import qi_config  # For default timeouts
from core.constants import HUB_ID
from core.messaging.connection_manager import (
    QiConnectionManager,  # For type hinting if needed
)
from core.messaging.handler_registry import (
    QiHandlerRegistry,  # For type hinting if needed
)
from core.messaging.message_bus import QiMessageBus

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio

# --- Mocks & Fixtures ---


class MockWebSocket:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.sent_text = []
        self.closed = False

    async def send_text(self, text: str):
        self.sent_text.append(text)
        await asyncio.sleep(0)

    async def close(self, code: int = 1000):
        self.closed = True
        await asyncio.sleep(0)

    def __eq__(self, other):
        if isinstance(other, MockWebSocket):
            return self.session_id == other.session_id
        return False

    def __hash__(self):
        return hash(self.session_id)


def create_mock_session(
    logical_id: str, session_id: str | None = None, parent_logical_id: str | None = None
) -> QiSession:
    true_session_id = session_id or f"session_for_{logical_id}"
    return QiSession(
        id=true_session_id,
        logical_id=logical_id,
        parent_logical_id=parent_logical_id,
        tags=[],
    )


@pytest.fixture
def mock_connection_manager():
    return AsyncMock(spec=QiConnectionManager)


@pytest.fixture
def mock_handler_registry():
    return AsyncMock(spec=QiHandlerRegistry)


@pytest.fixture
async def message_bus(mock_connection_manager, mock_handler_registry) -> QiMessageBus:
    # Temporarily patch qi_config if its attributes are accessed directly in __init__
    with (
        patch.object(qi_config, "reply_timeout", 5.0),
        patch.object(qi_config, "max_pending_requests_per_session", 100),
    ):
        bus = QiMessageBus()
    bus._connection_manager = mock_connection_manager
    bus._handler_registry = mock_handler_registry
    return bus


# --- Test Session Lifecycle ---


async def test_register_session(message_bus: QiMessageBus, mock_connection_manager):
    socket = MockWebSocket("s1_sock_id")
    session = create_mock_session("client1", "s1_sock_id")
    await message_bus.register(socket=socket, session=session)
    mock_connection_manager.register.assert_called_once_with(
        socket=socket, session=session
    )


async def test_unregister_session(
    message_bus: QiMessageBus, mock_connection_manager, mock_handler_registry
):
    session_id_to_unregister = "s1_to_unregister"
    # Simulate some pending requests for this session
    future_mock = asyncio.Future()
    message_bus._pending_request_futures["req1"] = future_mock
    message_bus._session_to_pending[session_id_to_unregister] = {"req1"}

    await message_bus.unregister(session_id=session_id_to_unregister)

    # Assertions
    mock_handler_registry.drop_session.assert_called_once_with(
        session_id=session_id_to_unregister
    )
    mock_connection_manager.unregister.assert_called_once_with(
        session_id=session_id_to_unregister
    )
    assert "req1" not in message_bus._pending_request_futures
    assert session_id_to_unregister not in message_bus._session_to_pending
    assert future_mock.cancelled() or isinstance(
        future_mock.exception(), ConnectionAbortedError
    )


# --- Test Handler Subscription (on decorator) ---


async def test_on_decorator_registers_handler(
    message_bus: QiMessageBus, mock_handler_registry
):
    test_topic = "decorator.topic"
    test_session_id = "decorator_session"

    @message_bus.on(test_topic, session_id=test_session_id)
    async def my_handler(msg: QiMessage):
        pass

    await asyncio.sleep(0)  # Allow create_task to run
    mock_handler_registry.register.assert_called_once_with(
        handler_fn=my_handler, topic=test_topic, session_id=test_session_id
    )


# --- Test Publish Logic ---


async def test_publish_reply_resolves_future(message_bus: QiMessageBus):
    request_id = "req_for_reply"
    reply_payload = {"data": "resolved"}
    originating_session_id = "origin_s1"

    future = asyncio.get_running_loop().create_future()
    message_bus._pending_request_futures[request_id] = future
    message_bus._session_to_pending[originating_session_id] = {request_id}

    reply_message = QiMessage(
        message_id="reply_msg_id",
        topic="some.topic",
        type=QiMessageType.REPLY,
        sender=create_mock_session(HUB_ID),
        reply_to=request_id,
        payload=reply_payload,
    )
    await message_bus.publish(message=reply_message)

    assert await future == reply_payload
    assert request_id not in message_bus._pending_request_futures
    assert not message_bus._session_to_pending[originating_session_id]


async def test_publish_event_dispatches_and_fans_out(
    message_bus: QiMessageBus, mock_handler_registry, mock_connection_manager
):
    event_message = QiMessage(
        message_id="event1",
        topic="event.topic",
        type=QiMessageType.EVENT,
        sender=create_mock_session("s_sender", "sender_id"),
    )
    mock_handler_registry.get_handlers.return_value = []  # No specific handlers
    mock_connection_manager.snapshot_sockets.return_value = {
        "s_receiver_id": MockWebSocket("s_receiver_id")
    }

    await message_bus.publish(message=event_message)

    mock_handler_registry.get_handlers.assert_called_once_with(
        topic="event.topic", session_id="s_sender"
    )
    mock_connection_manager.snapshot_sockets.assert_called_once()  # Called for broadcast
    # Further assertions could check if _safe_send was called on the socket if we mock it deeper


async def test_publish_request_dispatches_and_auto_replies(
    message_bus: QiMessageBus, mock_handler_registry, mock_connection_manager
):
    request_sender_session = create_mock_session("req_sender_log", "req_sender_id")
    request_message = QiMessage(
        message_id="req_msg1",
        topic="service.request",
        type=QiMessageType.REQUEST,
        sender=request_sender_session,
        payload={"ask": "something"},
    )
    handler_response_payload = {"answer": "this"}

    async def mock_req_handler(msg):
        return handler_response_payload

    mock_handler_registry.get_handlers.return_value = [mock_req_handler]

    # Mock fan-out for the reply
    target_socket = MockWebSocket(request_sender_session.id)
    mock_connection_manager.snapshot_sessions_by_logical.return_value = {
        request_sender_session.id: target_socket
    }

    await message_bus.publish(message=request_message)

    mock_handler_registry.get_handlers.assert_called_once_with(
        topic="service.request", session_id="req_sender_log"
    )
    # Check that _fan_out was called for the reply
    mock_connection_manager.snapshot_sessions_by_logical.assert_called_once_with(
        [request_sender_session.logical_id]
    )
    assert len(target_socket.sent_text) == 1
    # We'd need to json.loads(target_socket.sent_text[0]) and check contents for full verification


# --- Test Request Logic ---


async def test_request_successful(
    message_bus: QiMessageBus, mock_handler_registry, mock_connection_manager
):
    topic = "test.req.topic"
    req_payload = {"data": "question"}
    reply_payload = {"data": "answer"}
    requester_session_id = "req_s1"

    # Mock handler producing a reply that will be picked up by _dispatch_and_maybe_reply
    # when the request message is published by message_bus.request()
    async def internal_handler(msg: QiMessage):
        # Simulate that this handler is for the request and generates a reply payload
        # The bus should then take this payload and send it as a REPLY
        if msg.type == QiMessageType.REQUEST and msg.topic == topic:
            # The actual reply that resolves the future comes from a separate QiMessage.REPLY
            # For this test, we need to simulate that reply coming in.
            # The simplest is to have the handler invoked by publish() inside request(),
            # and then manually simulate the reply message coming back into the bus.
            pass  # Handler does its work

    mock_handler_registry.get_handlers.return_value = [internal_handler]

    # To make request() resolve, we need to simulate the QiMessage.REPLY being published.
    # We'll patch `publish` to intercept the outgoing request, then simulate the incoming reply.
    original_publish = message_bus.publish
    outgoing_request_message_id = None

    async def publish_interceptor(message: QiMessage):
        nonlocal outgoing_request_message_id
        if message.type == QiMessageType.REQUEST and message.topic == topic:
            outgoing_request_message_id = message.message_id
            # Call original publish to process handlers (like internal_handler)
            await original_publish(message=message)

            # Now, simulate the actual reply message coming back for this request
            simulated_reply = QiMessage(
                message_id="sim_reply_id",
                topic=topic,
                type=QiMessageType.REPLY,
                sender=create_mock_session(HUB_ID),
                reply_to=outgoing_request_message_id,
                payload=reply_payload,
            )
            await original_publish(
                message=simulated_reply
            )  # This will resolve the future
        else:
            await original_publish(message=message)

    with patch.object(
        message_bus, "publish", side_effect=publish_interceptor, wraps=original_publish
    ) as _:
        response = await message_bus.request(
            topic=topic,
            payload=req_payload,
            session_id=requester_session_id,
            timeout=0.1,
        )
        assert response == reply_payload
        assert outgoing_request_message_id not in message_bus._pending_request_futures


async def test_request_timeout(message_bus: QiMessageBus):
    with pytest.raises(asyncio.TimeoutError):
        await message_bus.request(
            topic="timeout.topic", payload={}, session_id="s_timeout", timeout=0.01
        )
    # Check cleanup
    assert (
        not message_bus._pending_request_futures
    )  # Should be empty after timeout and cleanup


async def test_request_limit_exceeded(message_bus: QiMessageBus):
    session_id = "s_limit"
    message_bus._max_pending = 1  # Set low for test
    message_bus._session_to_pending[session_id] = {"dummy_req"}  # Simulate one pending

    with pytest.raises(RuntimeError, match="Too many concurrent requests"):
        await message_bus.request(
            topic="limit.topic", payload={}, session_id=session_id
        )

    # Reset for other tests if bus instance is reused by pytest across tests in a class
    # (though with function-scoped fixture, this shouldn't be an issue)
    message_bus._session_to_pending.pop(session_id, None)
    message_bus._max_pending = qi_config.max_pending_requests_per_session  # reset


# --- Test _fan_out Logic (indirectly through publish, or can be tested directly) ---


async def test_fan_out_to_targets(message_bus: QiMessageBus, mock_connection_manager):
    msg = QiMessage(
        topic="fan.target",
        type=QiMessageType.EVENT,
        sender=create_mock_session("s_send"),
        target=["log_recv1", "log_recv2"],
    )
    sockets_map = {
        "recv1_id": MockWebSocket("recv1_id"),
        "recv2_id": MockWebSocket("recv2_id"),
    }
    mock_connection_manager.snapshot_sessions_by_logical.return_value = sockets_map

    await message_bus._fan_out(message=msg)

    mock_connection_manager.snapshot_sessions_by_logical.assert_called_once_with(
        ["log_recv1", "log_recv2"]
    )
    assert len(sockets_map["recv1_id"].sent_text) == 1
    assert len(sockets_map["recv2_id"].sent_text) == 1


async def test_fan_out_broadcast(message_bus: QiMessageBus, mock_connection_manager):
    msg = QiMessage(
        topic="fan.broadcast",
        type=QiMessageType.EVENT,
        sender=create_mock_session("s_broadcast_sender"),
    )
    sockets_map = {
        "b_recv1_id": MockWebSocket("b_recv1_id"),
        "b_recv2_id": MockWebSocket("b_recv2_id"),
    }
    mock_connection_manager.snapshot_sockets.return_value = sockets_map

    await message_bus._fan_out(message=msg)

    mock_connection_manager.snapshot_sockets.assert_called_once()
    assert len(sockets_map["b_recv1_id"].sent_text) == 1
    assert len(sockets_map["b_recv2_id"].sent_text) == 1


async def test_fan_out_bubble(message_bus: QiMessageBus, mock_connection_manager):
    sender_session = create_mock_session(
        "child_sender", parent_logical_id="parent_listener"
    )
    msg = QiMessage(
        topic="fan.bubble", type=QiMessageType.EVENT, sender=sender_session, bubble=True
    )
    parent_socket = MockWebSocket("parent_socket_id")
    mock_connection_manager.snapshot_sessions_by_logical.return_value = {
        "parent_socket_id": parent_socket
    }

    await message_bus._fan_out(message=msg)
    mock_connection_manager.snapshot_sessions_by_logical.assert_called_once_with(
        ["parent_listener"]
    )
    assert len(parent_socket.sent_text) == 1


# --- Test _safe_send (can be part of fan_out tests or separate) ---
async def test_safe_send_logs_exception(message_bus: QiMessageBus, caplog):
    faulty_socket = MockWebSocket("faulty_sock")

    async def mock_send_text_error(text: str):
        raise ConnectionResetError("Socket broke")

    faulty_socket.send_text = mock_send_text_error  # Monkey patch

    with caplog.at_level("ERROR"):
        await message_bus._safe_send(socket=faulty_socket, raw_message="test")

    assert "Error sending message over WebSocket" in caplog.text
    assert "ConnectionResetError: Socket broke" in caplog.text
