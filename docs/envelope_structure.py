"""
Final Qi Message Envelope Structure
==================================

This file documents the canonical message envelope structure used throughout the Qi system.
All Python and JavaScript implementations should conform to this structure.
"""


# ============================================================================
# CONTEXT: Business logic context for pipeline/project decisions
# ============================================================================

QiContext = {
    "project": "TEST_PROJECT",  # type: Optional[str] - Project identifier
    "entity": "TEST_ENTITY",  # type: Optional[str] - Entity/asset identifier
    "task": "Compositing",  # type: Optional[str] - Task/step identifier
    # Additional business context fields can be added as needed
}  # QiContext contains business logic context for routing decisions


# ============================================================================
# USER: Authentication and user-specific information
# ============================================================================

QiUser = {
    "id": "user-id-string",  # type: Optional[str] - Unique user identifier
    "name": "user-display-name",  # type: Optional[str] - User display name
    "email": "user@example.com",  # type: Optional[str] - User email
    # Future fields: auth tokens, permissions, roles, etc.
}  # QiUser contains authentication and user-specific data


# ============================================================================
# SOURCE: Routing information for message delivery
# ============================================================================

QiSource = {
    "addon": "addon-name",  # type: str - Source addon identifier
    "session_id": "session-id-string",  # type: str - WebSocket session identifier
    "window_id": "window-id-string",  # type: Optional[str] - Specific window identifier
    "user": QiUser,  # type: Optional[QiUser] - User who originated message
}  # QiSource contains routing information for message delivery and replies


# ============================================================================
# ENVELOPE: Complete message structure
# ============================================================================

QiMessage = {
    "message_id": "f69e55f3-6e50-4ed6-876d-93fcd5e7b5b1",  # type: str - Unique message identifier (UUID format)
    "topic": "test.ping",  # type: str - Message topic/type
    "payload": {"data": "example"},  # type: Dict[str, Any] - Message content
    "context": QiContext,  # type: Optional[QiContext] - Business context
    "source": QiSource,  # type: Optional[QiSource] - Routing information
    "user": QiUser,  # type: Optional[QiUser] - User information
    "reply_to": "c69e55f3-6b50-4ed6-876d-93fcd6e7b5b4",  # type: Optional[str] - ID of message being replied to (UUID format)
    "timestamp": 1699123456.789,  # type: float - Unix timestamp with milliseconds
}  # QiMessage is the complete envelope structure used throughout the system


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

# Python emit examples:
"""
# Basic message
await qi_bus.emit("task.status", payload={"status": "completed"})

# Message with custom context
await qi_bus.emit(
    "asset.updated", 
    payload={"asset_id": "123"},
    context={"project": "ProjectX", "entity": "Character", "task": "Modeling"}
)

# Reply to a message (auto-routes to original sender)
await qi_bus.emit(
    "task.result",
    payload={"result": "success"}, 
    reply_to=envelope.message_id
)
"""

# JavaScript emit examples:
"""
// Basic message
qiConnection.emit("task.status", {payload: {status: "completed"}})

// Message with custom context  
qiConnection.emit("asset.updated", {
    payload: {asset_id: "123"},
    context: {project: "ProjectX", entity: "Character", task: "Modeling"}
})

// Reply to a message (auto-routes to original sender)
qiConnection.emit("task.result", {
    payload: {result: "success"},
    reply_to: envelope.message_id
})
"""


# ============================================================================
# NOTES
# ============================================================================

"""
Consistent ID Naming:
- message_id: Unique identifier for each message (UUID format string)  
- session_id: WebSocket session identifier (UUID format string)
- window_id: Specific window identifier (UUID format string)
- reply_to: References another message_id for reply routing

UUID Fields as Strings:
- All ID fields are simple strings in UUID format
- No UUID validation or conversion is performed  
- JavaScript and Python both use strings natively
- Only requirement is uniqueness for routing purposes
- Generated using uuid.uuid4() converted to string
"""
