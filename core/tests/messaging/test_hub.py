import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from core.constants import HUB_ID
from core.messaging.hub import QiHub
from core.messaging.message_bus import QiMessageBus  # For type hinting and patching
from core.models import (  # Assuming QiMessage is needed
    QiMessage,
    QiMessageType,
    QiSession,
)

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio

# --- Mocks and Fixtures ---


@pytest.fixture
def mock_bus():
    # Create an AsyncMock that also has the attributes of QiMessageBus if needed for __getattr__
    # For most Hub tests, we just need to ensure methods are called.
    mock = AsyncMock(spec=QiMessageBus)
    # If QiMessageBus.__init__ takes args that Hub doesn't pass, this is fine.
    # Hub creates its own bus, so we'll patch the bus instance within Hub.
    return mock


@pytest.fixture
async def hub(mock_bus) -> QiHub:
    # Patch the QiMessageBus instance created within QiHub
    with patch("core.messaging.hub.QiMessageBus", return_value=mock_bus):
        h = QiHub()
    return h


class MockWebSocket:
    pass  # Simple placeholder if needed for type hints, Hub usually passes it to bus


# --- Test Hub Facade Methods ---


async def test_hub_register_delegates_to_bus(hub: QiHub, mock_bus: AsyncMock):
    mock_socket = MockWebSocket()
    mock_session = QiSession(id="s1", logical_id="client1")
    await hub.register(socket=mock_socket, session=mock_session)
    mock_bus.register.assert_called_once_with(socket=mock_socket, session=mock_session)


async def test_hub_unregister_delegates_to_bus(hub: QiHub, mock_bus: AsyncMock):
    session_id = "s1_to_drop"
    await hub.unregister(session_id=session_id)
    mock_bus.unregister.assert_called_once_with(session_id=session_id)


async def test_hub_publish_delegates_to_bus(hub: QiHub, mock_bus: AsyncMock):
    msg = QiMessage(
        message_id="m1",
        topic="t1",
        type=QiMessageType.EVENT,
        sender=QiSession(id=HUB_ID, logical_id=HUB_ID),
        payload={},
    )
    await hub.publish(message=msg)
    mock_bus.publish.assert_called_once_with(message=msg)


async def test_hub_request_delegates_to_bus(hub: QiHub, mock_bus: AsyncMock):
    topic = "req.topic"
    payload = {"data": "q"}
    context_dict = {"project": "proj_x"}
    session_id = "user_session_1"
    expected_response = {"response": "ok"}

    mock_bus.request.return_value = expected_response  # Simulate bus returning a value

    response = await hub.request(
        topic=topic,
        payload=payload,
        context=context_dict,
        session_id=session_id,
        timeout=1.0,
        target=["target_log_id"],
        parent_logical_id="parent_log_id",
    )

    assert response == expected_response
    mock_bus.request.assert_called_once_with(
        topic=topic,
        payload=payload,
        context=context_dict,  # Hub now passes dict directly
        session_id=session_id,
        timeout=1.0,
        target=["target_log_id"],
        parent_logical_id="parent_log_id",
    )


async def test_hub_on_decorator_delegates_to_bus(hub: QiHub, mock_bus: AsyncMock):
    topic = "decorated.topic"
    session_id = "decorated_session"

    # Mock the bus's .on() method to return a dummy decorator initially
    # The actual registration check happens on the mock_bus instance itself.
    dummy_decorator = lambda func: func  # Simple passthrough decorator for the test
    mock_bus.on.return_value = dummy_decorator

    @hub.on(topic, session_id=session_id)
    async def my_handler(msg: QiMessage):
        pass

    mock_bus.on.assert_called_once_with(topic=topic, session_id=session_id)
    # The decorator itself is returned by hub.on(), which comes from mock_bus.on()
    # The actual handler registration is done by the QiMessageBus.on() decorator internally calling _handler_registry.register
    # Testing that part is more for QiMessageBus tests.


# --- Test Event Hooks ---


async def test_on_event_registration_and_fire_async_hook(
    hub: QiHub, mock_bus: AsyncMock
):
    event_name = "test_event_async"
    hook_called_with = None
    hook_event = asyncio.Event()

    @hub.on_event(event_name)
    async def async_hook(arg1, arg2):
        nonlocal hook_called_with
        hook_called_with = (arg1, arg2)
        hook_event.set()

    # Simulate the internal event that would trigger this hook
    await hub._fire(event_name, "val1", "val2")

    await asyncio.wait_for(hook_event.wait(), timeout=0.1)
    assert hook_called_with == ("val1", "val2")


async def test_on_event_registration_and_fire_sync_hook(
    hub: QiHub, mock_bus: AsyncMock
):
    event_name = "test_event_sync"
    hook_called_with = None

    @hub.on_event(event_name)
    def sync_hook(arg1, arg2):
        nonlocal hook_called_with
        hook_called_with = (arg1, arg2)

    await hub._fire(event_name, 123, 456)
    await asyncio.sleep(0.05)  # Allow time for to_thread to execute

    assert hook_called_with == (123, 456)


async def test_fire_event_with_no_hooks(hub: QiHub):
    try:
        await hub._fire("event_with_no_hooks", "arg")
    except Exception as e:
        pytest.fail(f"_fire raised an exception with no hooks: {e}")


async def test_fire_event_hook_exception_logged(
    hub: QiHub, caplog, mock_bus: AsyncMock
):
    event_name = "event_exception"

    @hub.on_event(event_name)
    async def faulty_hook(arg):
        raise ValueError("Hook failed intentionally")

    with caplog.at_level("ERROR"):
        await hub._fire(event_name, "test_arg")

    assert f"Event hook '{event_name}' raised an exception" in caplog.text
    assert "ValueError: Hook failed intentionally" in caplog.text


# --- Test __getattr__ Fallback ---


async def test_getattr_delegates_to_bus_for_public_methods(
    hub: QiHub, mock_bus: AsyncMock
):
    # Define a method on the mock_bus that isn't directly on Hub
    mock_bus.some_other_bus_method = AsyncMock(return_value="delegated_response")

    response = await hub.some_other_bus_method("param1", kwarg1="val1")

    assert response == "delegated_response"
    mock_bus.some_other_bus_method.assert_called_once_with("param1", kwarg1="val1")


async def test_getattr_does_not_delegate_private_attributes(hub: QiHub):
    with pytest.raises(AttributeError):
        _ = hub._some_private_bus_attribute

    with pytest.raises(AttributeError):
        _ = hub.__some_dunder_method_on_bus__


# --- Test Hub with its own bus instance (integration style) ---
# This test doesn't use the global mock_bus fixture for QiHub's internal bus.
async def test_hub_instantiates_and_uses_real_bus_for_publish():
    real_hub = QiHub()  # Creates its own QiMessageBus instance

    # We need to patch the QiMessageBus.publish method on the *instance*
    # that real_hub has created.
    # One way is to mock QiMessageBus at the module level before QiHub initializes it.

    # More direct: spy on the actual bus instance's method
    # This is a bit more of an integration test for the Hub itself.

    # Let's create a mock for the bus that QiHub will instantiate
    mock_internal_bus_instance = AsyncMock(spec=QiMessageBus)

    with patch(
        "core.messaging.hub.QiMessageBus",
        return_value=mock_internal_bus_instance,
    ) as MockBusClass:
        hub_with_mocked_internal_bus = QiHub()

        msg_to_publish = QiMessage(
            message_id="m_int",
            topic="t_int",
            type=QiMessageType.EVENT,
            sender=QiSession(id=HUB_ID, logical_id=HUB_ID),
            payload={},
        )
        await hub_with_mocked_internal_bus.publish(message=msg_to_publish)

        MockBusClass.assert_called_once()  # Check QiMessageBus was instantiated
        mock_internal_bus_instance.publish.assert_called_once_with(
            message=msg_to_publish
        )
