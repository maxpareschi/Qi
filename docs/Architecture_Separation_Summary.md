# Architecture Separation Summary

## Overview

This document summarizes the proper separation of responsibilities achieved in the Qi refactoring, addressing the confusion between Hub responsibilities and event bus functionality.

## ✅ **Fixed Architecture**

### **Hub** - Service Orchestrator Only
**Responsibilities:**
- Service registration and discovery
- Dependency injection via decorators  
- Extension lifecycle management
- Coordinating service startup/shutdown

**What it does NOT do:**
- ❌ Event routing or handling
- ❌ Session management
- ❌ WebSocket connections
- ❌ Message envelope processing

```python
# Hub is purely for service coordination
hub = Hub(config)
hub.register("logger", logger)
hub.register("bus", event_bus)
hub.setup_core_services()
```

### **EventBus** - Event Routing System  
**Responsibilities:**
- Session management (QiSession tracking)
- WebSocket connection tracking
- Handler registration and routing
- Message envelope processing (QiMessage)
- Request/reply patterns
- Target-based message routing

```python
# EventBus handles all messaging
@service("bus")
class EventBus:
    async def register_session(self, websocket, logical_id) -> QiSession
    def register_handler(self, topic, handler)
    async def publish(self, message: QiMessage)
    async def request(self, topic, payload, sender) -> Any
```

### **ServerManager** - WebSocket Integration
**Responsibilities:**
- FastAPI server management
- WebSocket connection acceptance
- Integration with EventBus for sessions
- HTTP endpoint hosting

```python
# Server integrates with EventBus
@inject("config", "hub", "bus")
class ServerManager:
    async def _handle_websocket(self, websocket, logical_id):
        session = await self.bus.register_session(websocket, logical_id)
```

## 🎯 **Message Envelope Structure**

Using proper `QiMessage` envelopes for routing:

```python
message = QiMessage(
    topic="user.login",
    type=QiMessageType.EVENT,
    sender=session,           # QiSession with routing info
    target=["admin_users"],   # Route by logical_id or session_id
    payload={"user_id": 123}, # Actual data
    reply_to="request_123"    # For request/reply patterns
)

await event_bus.publish(message)
```

## 🔄 **Handler Registration Flow**

1. **Extension/Service Registration:**
   ```python
   @inject("config", "bus")
   class MyService:
       @subscribe("user.login")
       async def handle_login(self, message: QiMessage):
           # Receive full message envelope
           user_id = message.payload["user_id"]
           sender_session = message.sender
   ```

2. **Hub Coordinates Registration:**
   ```python
   hub.register("my_service", my_service)
   # Hub automatically finds @subscribe decorators
   # and registers them with EventBus
   ```

3. **EventBus Handles Routing:**
   ```python
   # When message published:
   await event_bus.publish(message)
   # EventBus routes to registered handlers
   # and target sessions via WebSocket
   ```

## 📋 **Terminology Clarification**

| **Term** | **New Meaning** | **Old Meaning** |
|----------|----------------|-----------------|
| **Hub** | Service orchestrator/DI container | Event bus facade |
| **EventBus** | Event routing and session management | Core message routing |
| **Session** | QiSession with WebSocket connection | Various connection types |
| **Handler** | Function receiving QiMessage | Function receiving raw data |

## 🏗️ **Benefits Achieved**

### **1. Clear Separation of Concerns**
- Hub: "Who provides what services?"
- EventBus: "How do messages flow?"
- Server: "How do clients connect?"

### **2. Proper Message Routing**
- Session-aware routing via QiMessage envelope
- Target-specific delivery (session_id or logical_id)
- Request/reply patterns with timeout handling

### **3. Scalable Architecture**
- Services are decoupled through EventBus
- Extensions register handlers declaratively
- WebSocket connections integrate seamlessly

### **4. No More Singletons**
- All coordination through Hub service registry
- EventBus is a service like any other
- Clean dependency injection throughout

## 🧪 **Validation**

The comprehensive test validates:

✅ Hub only does service orchestration  
✅ EventBus handles all event routing  
✅ Proper QiMessage envelope structure  
✅ Session management through EventBus  
✅ WebSocket integration working  
✅ Handler auto-registration working  
✅ Target-based message routing  

## 🚀 **Usage Example**

```python
# 1. Initialize system
config = QiLaunchConfig()
hub = Hub(config)
hub.setup_core_services()

# 2. Register application services
@inject("config", "bus")
class UserService:
    @subscribe("user.login")
    async def handle_login(self, message: QiMessage):
        # Process login with full message context
        pass

user_service = UserService()
hub.register("user_service", user_service)

# 3. Start system
await hub.start()  # Starts server, EventBus ready for connections

# 4. WebSocket client connects
# - Server accepts WebSocket
# - Registers session with EventBus  
# - Client can send QiMessage via WebSocket
# - EventBus routes to appropriate handlers
```

This architecture properly separates concerns and provides a scalable foundation for the Qi application! 