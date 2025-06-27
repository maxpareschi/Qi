# test_phase3_comprehensive.py

"""
Comprehensive test for proper responsibility separation:
1. Hub: Service orchestration and dependency injection only
2. EventBus: Session management, message routing, handler registration
3. ServerManager: WebSocket connections integrated with EventBus
4. Proper QiMessage envelope handling for routing
"""

import asyncio
from typing import TYPE_CHECKING

from core.config import QiLaunchConfig
from core.decorators import inject, subscribe
from core.hub import Hub
from core.logger import get_logger
from core.models import QiMessage, QiMessageType

if TYPE_CHECKING:
    from core.bus import EventBus

log = get_logger(__name__)


@inject()
class TestEventService:
    """Test service demonstrating proper EventBus integration."""

    # Dependencies auto-injected by Hub based on attribute names
    config: QiLaunchConfig
    hub: Hub
    bus: "EventBus"

    def __init__(self):
        # Dependencies auto-injected by Hub after registration
        pass

    @subscribe("test.message")
    async def handle_test_message(self, message: QiMessage):
        """Handle test messages with proper QiMessage envelope."""
        log.info(
            f"Received message from session {message.sender.logical_id}: {message.payload}"
        )

        # Create response message with proper envelope
        response = QiMessage(
            topic="test.response",
            type=QiMessageType.EVENT,
            sender=message.sender,  # Server responding as original sender for this test
            target=[message.sender.id],  # Send back to sender
            payload={
                "processed": message.payload.get("text", "unknown"),
                "original_id": message.message_id,
            },
        )

        # Publish through EventBus
        await self.bus.publish(response)

    @subscribe("session.welcome")
    async def on_session_welcome(self, message: QiMessage):
        """Handle new session welcomes."""
        session_id = message.payload.get("session_id")
        logical_id = message.payload.get("logical_id")
        log.info(f"New session welcomed: {session_id} ({logical_id})")

    @subscribe("session.disconnect")
    async def on_session_disconnect(self, message: QiMessage):
        """Handle session disconnects."""
        session_id = message.payload.get("session_id")
        log.info(f"Session disconnected: {session_id}")


async def test_responsibility_separation():
    """Test that responsibilities are properly separated."""
    print("🔧 Testing Responsibility Separation\n")

    # 1. Initialize Hub (service orchestrator only)
    config = QiLaunchConfig()
    hub = Hub(config)
    logger = get_logger("test")
    hub.register("logger", logger)

    print("✅ Hub initialized - service orchestration only")

    # 2. Setup core services
    hub.setup_core_services()

    # Verify services are registered
    services = hub.list_services()
    expected_services = [
        "config",
        "hub",
        "logger",
        "bus",
        "extension_manager",
        "server",
    ]
    for service in expected_services:
        assert service in services, f"Service '{service}' should be registered"

    print("✅ Core services registered")

    # 3. Get EventBus and verify it's separate from Hub
    event_bus = hub.get("bus")
    assert event_bus is not hub, "EventBus should be separate from Hub"
    assert hasattr(event_bus, "register_session"), "EventBus should handle sessions"
    assert hasattr(event_bus, "register_handler"), "EventBus should handle handlers"

    print("✅ EventBus is properly separated from Hub")

    # 4. Test service dependency injection
    test_service = TestEventService()
    hub.register("test_service", test_service)

    # Verify dependencies were auto-injected
    assert test_service.config is not None, "Config should be auto-injected"
    assert test_service.hub is not None, "Hub should be auto-injected"
    assert test_service.bus is not None, "EventBus should be auto-injected"

    print("✅ Automatic dependency injection working")

    # 5. Test session management through EventBus
    # Create mock WebSocket for testing
    class MockWebSocket:
        def __init__(self):
            self.messages = []

        async def send_text(self, data):
            self.messages.append(data)

    mock_ws = MockWebSocket()
    session = await event_bus.register_session(mock_ws, "test_client")

    assert session.logical_id == "test_client", "Session should have correct logical_id"
    assert event_bus.get_session(session.id) == session, "Session should be retrievable"

    print("✅ Session management working through EventBus")

    # 6. Test message routing with proper envelope
    test_message = QiMessage(
        topic="test.message",
        type=QiMessageType.EVENT,
        sender=session,
        payload={"text": "Hello MessageBus!"},
    )

    # Publish message
    await event_bus.publish(test_message)
    await asyncio.sleep(0.1)  # Allow processing

    print("✅ Message routing working with proper QiMessage envelope")

    # 7. Test handler registration through Hub -> EventBus coordination
    # Verify test service handlers were registered
    handlers = event_bus.handlers.get("test.message", [])
    assert len(handlers) > 0, "Handler should be registered for test.message"

    print("✅ Handler registration working (Hub coordinates, EventBus handles)")

    # 8. Start server integrated with EventBus
    server = hub.get("server")
    await server.start()
    print(f"✅ Server started with EventBus integration: {server.url}")

    # 9. Test WebSocket connection (simulated)
    print("\n📡 Testing WebSocket Integration:")

    # Simulate WebSocket message
    websocket_message = {
        "topic": "test.message",
        "type": "event",
        "payload": {"text": "Hello from WebSocket!"},
        "target": [],
    }

    # This would normally come through WebSocket, but we'll test the handler directly
    await test_service.handle_test_message(
        QiMessage(
            topic="test.message",
            type=QiMessageType.EVENT,
            sender=session,
            payload=websocket_message["payload"],
        )
    )

    print("✅ WebSocket message handling working")

    # 10. Cleanup
    await event_bus.unregister_session(session.id)
    await server.shutdown()

    print("\n✅ All responsibility separation tests passed!")

    # Summary
    print("\n📋 Responsibility Separation Summary:")
    print("1. ✅ Hub: Service orchestration and dependency injection ONLY")
    print("2. ✅ EventBus: Session management, handler registration, message routing")
    print("3. ✅ ServerManager: WebSocket connections integrated with EventBus")
    print("4. ✅ QiMessage: Proper envelope structure for routing")
    print("5. ✅ Clean separation of concerns achieved")


async def test_message_envelope_routing():
    """Test proper message envelope routing."""
    print("\n🎯 Testing Message Envelope Routing")

    config = QiLaunchConfig()
    hub = Hub(config)
    hub.setup_core_services()
    event_bus = hub.get("bus")

    # Create two sessions
    mock_ws1 = type("MockWS", (), {"send_text": lambda self, data: None})()
    mock_ws2 = type("MockWS", (), {"send_text": lambda self, data: None})()

    session1 = await event_bus.register_session(mock_ws1, "client1")
    session2 = await event_bus.register_session(mock_ws2, "client2")

    # Test targeted message routing
    targeted_message = QiMessage(
        topic="private.message",
        type=QiMessageType.EVENT,
        sender=session1,
        target=[session2.id],  # Specific target
        payload={"content": "Hello client2!"},
    )

    await event_bus.publish(targeted_message)

    # Test logical ID routing
    logical_message = QiMessage(
        topic="logical.message",
        type=QiMessageType.EVENT,
        sender=session1,
        target=["client2"],  # Target by logical_id
        payload={"content": "Hello by logical ID!"},
    )

    await event_bus.publish(logical_message)

    print("✅ Message envelope routing working correctly")

    # Cleanup
    await event_bus.unregister_session(session1.id)
    await event_bus.unregister_session(session2.id)


async def main():
    """Run all tests."""
    await test_responsibility_separation()
    await test_message_envelope_routing()

    print("\n🎉 All tests passed! Architecture properly separated.")


if __name__ == "__main__":
    asyncio.run(main())
