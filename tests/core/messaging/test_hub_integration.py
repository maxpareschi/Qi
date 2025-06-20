"""
Integration tests for QiHub focusing on actual component interaction.

These tests use real Hub instances and minimal mocking to verify proper integration
between components, ensuring the hub correctly delegates to underlying systems
and handles events appropriately.
"""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.constants import HUB_ID
from core.messaging.hub import QiHub
from core.models import QiMessage, QiMessageType, QiSession

# Mark all tests as asyncio
pytestmark = pytest.mark.asyncio


# --- Fixtures for more realistic hub testing ---


@pytest.fixture
async def real_hub():
    """Create a real QiHub instance without heavy mocking."""
    # We allow the Hub to create its own real MessageBus
    return QiHub()


@pytest.fixture
def mock_socket():
    """Create a mock WebSocket that handles basic operations."""
    socket = MagicMock()
    socket.send_json = AsyncMock()
    return socket


@pytest.fixture
def test_session():
    """Create a standard test session."""
    return QiSession(
        id="test_session_id",
        logical_id="test_client",
        parent_logical_id=None,
        tags=["test"],
    )


# --- Improved tests that focus on behavior ---


async def test_register_session_with_real_hub_fixed_v2(
    real_hub, mock_socket, test_session
):
    """Test session registration with a real hub instance."""
    # Set up a hook to detect when session is registered
    registration_complete = asyncio.Event()

    # Patch the connection manager to avoid real registration
    with patch(
        "core.messaging.connections.QiConnectionManager.register"
    ) as mock_register:
        mock_register.return_value = None

        @real_hub.on_event("register", session_id=HUB_ID)
        async def on_register(session):
            nonlocal registration_complete
            assert session.id == test_session.id
            registration_complete.set()

        # Register the session
        await real_hub.register(socket=mock_socket, session=test_session)

        # Wait for registration to complete
        await asyncio.wait_for(registration_complete.wait(), timeout=1.0)

        # Verify the connection manager was called with our socket and session
        mock_register.assert_called_once()
        call_args = mock_register.call_args
        assert call_args[1]["socket"] == mock_socket
        assert call_args[1]["session"].id == test_session.id

    # Since we can't directly access bus methods, verify through an unregister event
    unregister_called = asyncio.Event()

    # Patch the connection manager again for unregister
    with patch(
        "core.messaging.connections.QiConnectionManager.unregister"
    ) as mock_unregister:
        mock_unregister.return_value = None

        @real_hub.on_event("unregister", session_id=HUB_ID)
        async def on_unregister(session_id):
            nonlocal unregister_called
            unregister_called.set()

        # Unregister and verify the event was triggered
        await real_hub.unregister(session_id=test_session.id)
        await asyncio.wait_for(unregister_called.wait(), timeout=1.0)

        # Verify unregister was called with our session id
        mock_unregister.assert_called_once_with(session_id=test_session.id)


async def test_request_response_pattern_with_real_hub_fixed_v2(
    real_hub, test_session, mock_socket
):
    """Test the request-response pattern with a real hub instance."""
    # First patch connection manager to avoid real registration
    with patch(
        "core.messaging.connections.QiConnectionManager.register"
    ) as mock_register:
        mock_register.return_value = None

        # Register the session
        await real_hub.register(socket=mock_socket, session=test_session)

        # Mock register was called with our session
        mock_register.assert_called_once()

        # Test response we expect
        test_response = {"status": "success", "value": 42}

        # Now patch message_bus.request to return our test response directly
        with patch("core.messaging.bus.QiMessageBus.request") as mock_request:
            mock_request.return_value = test_response

            # Make a request
            response = await real_hub.request(
                topic="test.request.topic",
                payload={"action": "test"},
                session_id=test_session.id,
                timeout=1.0,
            )

            # Verify request was called with expected args
            mock_request.assert_called_once()
            request_args = mock_request.call_args[1]
            assert request_args["topic"] == "test.request.topic"
            assert request_args["payload"] == {"action": "test"}
            assert request_args["session_id"] == test_session.id
            assert request_args["timeout"] == 1.0

            # Response should match what our mock returned
            assert response == test_response

    # Clean up with patched unregister
    with patch(
        "core.messaging.connections.QiConnectionManager.unregister"
    ) as mock_unregister:
        mock_unregister.return_value = None
        await real_hub.unregister(session_id=test_session.id)
        mock_unregister.assert_called_once_with(session_id=test_session.id)


async def test_mixed_sync_async_event_handlers_fixed_v2(real_hub):
    """Test that both sync and async event handlers work correctly."""
    # We'll track which handlers have been called
    handlers_completed = set()
    completion_event = asyncio.Event()

    # Define a synchronous event handler
    @real_hub.on_event("test_event", session_id=HUB_ID)
    def sync_handler(arg):
        handlers_completed.add(f"sync:{arg}")
        # If both handlers have run, set the event
        if len(handlers_completed) == 2:
            # Note: This runs in a worker thread, so we use call_soon_threadsafe
            asyncio.get_running_loop().call_soon_threadsafe(completion_event.set)

    # Define an asynchronous event handler
    @real_hub.on_event("test_event", session_id=HUB_ID)
    async def async_handler(arg):
        handlers_completed.add(f"async:{arg}")
        # If both handlers have run, set the event
        if len(handlers_completed) == 2:
            completion_event.set()

    # Fire the event
    await real_hub._fire("test_event", "test_arg")

    # Wait for both handlers to complete with timeout
    try:
        await asyncio.wait_for(completion_event.wait(), timeout=1.0)
    except asyncio.TimeoutError:
        pytest.fail(
            f"Not all handlers completed within timeout, completed: {list(handlers_completed)}"
        )

    # Verify both handlers were called
    assert "sync:test_arg" in handlers_completed
    assert "async:test_arg" in handlers_completed


async def test_publish_message_with_real_hub_fixed_v2(
    real_hub, test_session, mock_socket
):
    """Test publishing a message to the hub."""
    # First patch connection manager to avoid real registration
    with patch(
        "core.messaging.connections.QiConnectionManager.register"
    ) as mock_register:
        mock_register.return_value = None

        # Register the session
        await real_hub.register(socket=mock_socket, session=test_session)

        # Create a message
        message = QiMessage(
            topic="test.publish.topic",
            type=QiMessageType.EVENT,
            sender=test_session,
            payload={"data": "test_value"},
        )

        # Now patch message_bus.publish instead of trying to hook into handlers
        with patch("core.messaging.bus.QiMessageBus.publish") as mock_publish:
            mock_publish.return_value = None

            # Publish the message
            await real_hub.publish(message=message)

            # Verify publish was called with our message
            mock_publish.assert_called_once_with(message=message)

    # Clean up with patched unregister
    with patch(
        "core.messaging.connections.QiConnectionManager.unregister"
    ) as mock_unregister:
        mock_unregister.return_value = None
        await real_hub.unregister(session_id=test_session.id)
        mock_unregister.assert_called_once_with(session_id=test_session.id)


async def test_event_hook_error_handling(real_hub, caplog):
    """Test that errors in event hooks are caught and logged."""

    # Set up a hook that will raise an exception
    @real_hub.on_event("error_test", session_id=HUB_ID)
    async def failing_hook():
        raise RuntimeError("Intentional test error")

    # Capture logs
    with caplog.at_level(logging.ERROR):
        # Fire the event
        await real_hub._fire("error_test")

        # Give a moment for the error to be logged
        await asyncio.sleep(0.1)

    # Verify the error was logged
    assert "Event hook 'error_test' raised an exception" in caplog.text
    assert "Intentional test error" in caplog.text


async def test_event_hooks_run_in_sequence(real_hub):
    """Test that event hooks run in sequential order, not parallel."""
    # Track hook execution
    execution_order = []
    all_complete = asyncio.Event()

    @real_hub.on_event("sequential_test", session_id=HUB_ID)
    async def slow_hook():
        execution_order.append("slow_start")
        # Sleep to simulate slow processing
        await asyncio.sleep(0.2)
        execution_order.append("slow_end")
        # If both hooks have completed
        if len(execution_order) == 4:
            all_complete.set()

    @real_hub.on_event("sequential_test", session_id=HUB_ID)
    async def fast_hook():
        execution_order.append("fast_start")
        execution_order.append("fast_end")
        # If both hooks have completed
        if len(execution_order) == 4:
            all_complete.set()

    # Fire the event
    await real_hub._fire("sequential_test")

    # Wait for both hooks to complete
    await asyncio.wait_for(all_complete.wait(), timeout=1.0)

    # Verify execution order - they should run sequentially (in the order registered)
    # Expected order: slow_start, slow_end, fast_start, fast_end
    assert execution_order.index("slow_start") < execution_order.index("slow_end")
    assert execution_order.index("slow_end") < execution_order.index("fast_start")
    assert execution_order.index("fast_start") < execution_order.index("fast_end")


async def test_unregister_fires_event_hook(real_hub, test_session, mock_socket):
    """Test that unregister fires the unregister event hook."""
    # Patch connection manager for register
    with patch(
        "core.messaging.connections.QiConnectionManager.register"
    ) as mock_register:
        mock_register.return_value = None

        # Register the session
        await real_hub.register(socket=mock_socket, session=test_session)

    # Set up a hook to detect unregistration
    unregister_called = asyncio.Event()
    unregistered_session_id = None

    @real_hub.on_event("unregister", session_id=HUB_ID)
    async def on_unregister(session_id):
        nonlocal unregistered_session_id, unregister_called
        unregistered_session_id = session_id
        unregister_called.set()

    # Patch connection manager for unregister
    with patch(
        "core.messaging.connections.QiConnectionManager.unregister"
    ) as mock_unregister:
        mock_unregister.return_value = None

        # Unregister the session
        await real_hub.unregister(session_id=test_session.id)

        # Wait for the hook to be called
        await asyncio.wait_for(unregister_called.wait(), timeout=1.0)

        # Verify unregister was called with the right session id
        mock_unregister.assert_called_once_with(session_id=test_session.id)

    # Verify the hook was called with the correct session ID
    assert unregistered_session_id == test_session.id
