"""
Async-focused tests for the WebSocket endpoint in the server module.

These tests use more reliable async iteration patterns and proper error handling,
focusing on behavior rather than implementation details with special attention to
async edge cases like disconnections and error conditions.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocketDisconnect

from core.server.server import ws_endpoint


class AsyncJsonIterator:
    """A properly implemented async iterator for testing WebSocket JSON messages."""

    def __init__(self, messages, exception_after=None):
        """
        Initialize the iterator with a list of messages and optional disconnect point.

        Args:
            messages: List of JSON-serializable dictionaries to yield
            exception_after: Optional index after which to raise WebSocketDisconnect
        """
        self.messages = messages
        self.index = 0
        self.exception_after = exception_after
        self.messages_yielded = []  # Track which messages were actually yielded

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.messages):
            raise StopAsyncIteration

        # Get the current message
        message = self.messages[self.index]
        self.index += 1
        self.messages_yielded.append(message)

        # Check if we should raise an exception after this message
        # We increment the index first, THEN check for the exception condition
        if self.exception_after is not None and self.index - 1 == self.exception_after:
            raise WebSocketDisconnect()

        return message


class MockWebSocket:
    """Enhanced mock WebSocket with proper async iteration support."""

    def __init__(self):
        self.accept = AsyncMock()
        self.close = AsyncMock()
        self.receive_json = AsyncMock()
        self.send_json = AsyncMock()

        # For tracking close calls
        self.close_code = None
        self.closed = False

        # Default iter_json with no messages
        self.iter_json = MagicMock(return_value=AsyncJsonIterator([]))

    async def close(self, code=1000):
        """Mock close with code tracking."""
        self.close_code = code
        self.closed = True


@pytest.mark.asyncio
async def test_websocket_successful_session_init_fixed():
    """Test successful WebSocket session initialization."""
    ws = MockWebSocket()

    # Valid session data
    session_data = {"logical_id": "test_client", "id": "session_123", "tags": []}
    ws.receive_json.return_value = session_data

    with patch("core.server.server.qi_hub") as mock_hub:
        mock_hub.register = AsyncMock()
        mock_hub.unregister = AsyncMock()

        # Run the endpoint
        await ws_endpoint(ws)

        # Verify behavior
        ws.accept.assert_called_once()
        mock_hub.register.assert_called_once()
        # Changed to match actual implementation - server.py calls unregister with a positional arg
        mock_hub.unregister.assert_called_once_with("session_123")


@pytest.mark.asyncio
async def test_websocket_invalid_session_data_fixed():
    """Test handling of invalid session initialization data."""
    ws = MockWebSocket()

    # Invalid session data (missing required field 'logical_id')
    invalid_session = {"id": "session_123", "tags": []}
    ws.receive_json.return_value = invalid_session

    # Run the endpoint
    await ws_endpoint(ws)

    # Verify behavior
    ws.accept.assert_called_once()
    ws.close.assert_called_once()
    assert ws.close.call_args[1]["code"] == 4401  # Invalid Session code


@pytest.mark.asyncio
async def test_websocket_disconnect_during_init_fixed():
    """Test handling of disconnection during session initialization."""
    ws = MockWebSocket()

    # Simulate disconnection during receive_json
    ws.receive_json.side_effect = WebSocketDisconnect()

    with patch("core.server.server.qi_hub") as mock_hub:
        mock_hub.register = AsyncMock()
        mock_hub.unregister = AsyncMock()

        # Run the endpoint
        await ws_endpoint(ws)

        # Verify behavior
        ws.accept.assert_called_once()
        mock_hub.register.assert_not_called()
        mock_hub.unregister.assert_not_called()
        ws.close.assert_called_once()
        assert ws.close.call_args[1]["code"] == 4000  # Generic abnormal closure


@pytest.mark.asyncio
async def test_websocket_process_valid_messages_fixed():
    """Test processing of valid messages after successful initialization."""
    ws = MockWebSocket()

    # Valid session data
    session_data = {"logical_id": "test_client", "id": "session_123", "tags": []}
    ws.receive_json.return_value = session_data

    # Valid messages after initialization
    messages = [
        {
            "topic": "test.topic.1",
            "type": "event",
            "sender": session_data,
            "payload": {"data": "message1"},
        },
        {
            "topic": "test.topic.2",
            "type": "event",
            "sender": session_data,
            "payload": {"data": "message2"},
        },
    ]
    ws.iter_json = MagicMock(return_value=AsyncJsonIterator(messages))

    with patch("core.server.server.qi_hub") as mock_hub:
        mock_hub.register = AsyncMock()
        mock_hub.publish = AsyncMock()
        mock_hub.unregister = AsyncMock()

        # Run the endpoint
        await ws_endpoint(ws)

        # Verify behavior
        ws.accept.assert_called_once()
        mock_hub.register.assert_called_once()

        # Should publish both messages
        assert mock_hub.publish.call_count == 2

        # And unregister at the end - updated to match implementation
        mock_hub.unregister.assert_called_once_with("session_123")


@pytest.mark.asyncio
async def test_websocket_disconnect_during_message_processing_fixed():
    """Test handling of disconnection during message processing."""
    ws = MockWebSocket()

    # Valid session data
    session_data = {"logical_id": "test_client", "id": "session_123", "tags": []}
    ws.receive_json.return_value = session_data

    # Just create one test message - we'll never get to the second one
    message = {
        "topic": "test.topic.1",
        "type": "event",
        "sender": session_data,
        "payload": {"data": "message1"},
    }

    # Instead of using AsyncJsonIterator with exception_after,
    # we'll take direct control of the iteration process
    async def custom_iter_json():
        # First yield the message
        yield message
        # Then immediately raise WebSocketDisconnect
        raise WebSocketDisconnect()

    # Set up the mock to use our custom async generator function
    ws.iter_json = MagicMock(return_value=custom_iter_json())

    # Create a simple QiMessage mock class that just stores the values
    class MockMessage:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    # Test with custom message mock
    with patch("core.server.server.QiMessage", MockMessage):
        # And patch the hub
        with patch("core.server.server.qi_hub") as mock_hub:
            # Set up register
            mock_hub.register = AsyncMock()

            # Set up publish to track calls
            mock_hub.publish = AsyncMock()

            # Set up unregister
            mock_hub.unregister = AsyncMock()

            # Run the endpoint
            await ws_endpoint(ws)

            # Verify correct sequence of operations
            mock_hub.register.assert_called_once()
            mock_hub.publish.assert_called_once()  # Should be called exactly once
            mock_hub.unregister.assert_called_once_with("session_123")

            # Verify the message was passed to publish
            published_message = mock_hub.publish.call_args[0][0]
            assert published_message.topic == "test.topic.1"
            assert published_message.payload == {"data": "message1"}


@pytest.mark.asyncio
async def test_websocket_hub_registration_error_fixed():
    """Test handling of errors during hub registration."""
    ws = MockWebSocket()

    # Valid session data
    session_data = {"logical_id": "test_client", "id": "session_123", "tags": []}
    ws.receive_json.return_value = session_data

    with patch("core.server.server.qi_hub") as mock_hub:
        # Simulate error during registration
        mock_hub.register = AsyncMock(side_effect=RuntimeError("Registration failed"))
        mock_hub.unregister = AsyncMock()

        # Run the endpoint
        await ws_endpoint(ws)

        # Verify behavior
        ws.accept.assert_called_once()
        mock_hub.register.assert_called_once()
        ws.close.assert_called_once()
        assert ws.close.call_args[1]["code"] == 4500  # Internal server error code

        # Since registration failed, unregister should still be called for cleanup
        # This matches the actual behavior in the code - updated to match implementation
        mock_hub.unregister.assert_called_once_with("session_123")


@pytest.mark.asyncio
async def test_websocket_publish_error_fixed():
    """Test handling of errors during message publishing."""
    ws = MockWebSocket()

    # Valid session data
    session_data = {"logical_id": "test_client", "id": "session_123", "tags": []}
    ws.receive_json.return_value = session_data

    # Valid message
    message = {
        "topic": "test.topic",
        "type": "event",
        "sender": session_data,
        "payload": {"data": "test"},
    }
    ws.iter_json = MagicMock(return_value=AsyncJsonIterator([message]))

    with patch("core.server.server.qi_hub") as mock_hub:
        mock_hub.register = AsyncMock()
        # Simulate error during publish
        mock_hub.publish = AsyncMock(side_effect=RuntimeError("Publish failed"))
        mock_hub.unregister = AsyncMock()

        # Run the endpoint
        await ws_endpoint(ws)

        # Verify behavior
        mock_hub.register.assert_called_once()
        mock_hub.publish.assert_called_once()
        # Should still unregister at the end - updated to match implementation
        mock_hub.unregister.assert_called_once_with("session_123")
