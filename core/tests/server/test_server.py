from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocket
from fastapi.testclient import TestClient

from core.bases.models import QiMessage, QiSession
from core.server.server import qi_server, ws_endpoint


class AsyncIterator:
    """Helper class to create async iterators for testing."""

    def __init__(self, items):
        self.items = items
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self.index]
        self.index += 1
        return item


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket connection."""
    ws = MagicMock(spec=WebSocket)
    ws.accept = AsyncMock()
    ws.receive_json = AsyncMock()
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()
    # Don't use AsyncMock for iter_json
    ws.iter_json = MagicMock()
    return ws


@pytest.fixture
def test_client():
    """Create a FastAPI test client."""
    return TestClient(qi_server)


def test_root_endpoint(test_client):
    """Test the root HTTP endpoint."""
    response = test_client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Qi - Fastapi local server is running!"}


class TestWebSocketEndpoint:
    """Test suite for WebSocket endpoint."""

    @pytest.mark.asyncio
    async def test_ws_endpoint_successful_connection(self, mock_websocket):
        """Test successful WebSocket connection and message handling."""
        # Mock session data
        session_data = {"logical_id": "test_session", "id": "123", "tags": []}
        mock_websocket.receive_json.return_value = session_data

        # Mock message data
        message_data = {
            "topic": "test.topic",
            "type": "event",
            "sender": session_data,
            "payload": {"test": "data"},
        }

        # Set iter_json to return our async iterator
        mock_websocket.iter_json.return_value = AsyncIterator([message_data])

        # Mock hub methods
        with patch("core.server.server.qi_hub") as mock_hub:
            mock_hub.register = AsyncMock()
            mock_hub.publish = AsyncMock()
            mock_hub.unregister = AsyncMock()

            # Run the endpoint
            await ws_endpoint(mock_websocket)

            # Verify session registration
            mock_websocket.accept.assert_called_once()
            mock_hub.register.assert_called_once()
            assert isinstance(mock_hub.register.call_args[0][1], QiSession)

            # Verify message handling
            mock_hub.publish.assert_called_once()
            assert isinstance(mock_hub.publish.call_args[0][0], QiMessage)

            # Verify cleanup
            mock_hub.unregister.assert_called_once_with("123")

    @pytest.mark.asyncio
    async def test_ws_endpoint_invalid_session(self, mock_websocket):
        """Test WebSocket connection with invalid session data."""
        mock_websocket.receive_json.return_value = {"invalid": "data"}

        await ws_endpoint(mock_websocket)

        mock_websocket.accept.assert_called_once()
        mock_websocket.close.assert_called_once_with(code=4401)
        mock_websocket.iter_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_ws_endpoint_disconnect_during_init(self, mock_websocket):
        """Test WebSocket disconnection during initialization."""
        mock_websocket.receive_json.side_effect = Exception("Connection closed")

        await ws_endpoint(mock_websocket)

        mock_websocket.accept.assert_called_once()
        mock_websocket.close.assert_called_once_with(code=4500)
        mock_websocket.iter_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_ws_endpoint_invalid_message(self, mock_websocket):
        """Test handling of invalid messages during the session."""
        # Mock valid session data
        session_data = {"logical_id": "test_session", "id": "123", "tags": []}
        mock_websocket.receive_json.return_value = session_data

        # Set iter_json to return an async iterator with invalid message
        mock_websocket.iter_json.return_value = AsyncIterator([{"invalid": "message"}])

        with patch("core.server.server.qi_hub") as mock_hub:
            mock_hub.register = AsyncMock()
            mock_hub.publish = AsyncMock()
            mock_hub.unregister = AsyncMock()

            await ws_endpoint(mock_websocket)

            # Verify session was registered
            mock_hub.register.assert_called_once()

            # Verify invalid message was not published
            mock_hub.publish.assert_not_called()

            # Verify cleanup
            mock_hub.unregister.assert_called_once_with("123")

    @pytest.mark.asyncio
    async def test_ws_endpoint_disconnect_during_session(self, mock_websocket):
        """Test WebSocket disconnection during an active session."""
        # Mock valid session data
        session_data = {"logical_id": "test_session", "id": "123", "tags": []}
        mock_websocket.receive_json.return_value = session_data

        # Create an async iterator that raises an exception
        class ErrorIterator:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise Exception("Connection closed")

        # Set iter_json to return an error-raising iterator
        mock_websocket.iter_json.return_value = ErrorIterator()

        with patch("core.server.server.qi_hub") as mock_hub:
            mock_hub.register = AsyncMock()
            mock_hub.unregister = AsyncMock()

            await ws_endpoint(mock_websocket)

            # Verify session was registered and unregistered
            mock_hub.register.assert_called_once()
            mock_hub.unregister.assert_called_once_with("123")
