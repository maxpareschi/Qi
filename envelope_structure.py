{
    "message_id": "f69e55f3-6e50-4ed6-876d-93fcd5e7b5b1",  # type: uuid4
    "topic": "TEST_TOPIC",  # type: str
    "payload": {},  # type: dict[str, Any]
    "context": {
        "project": "TEST_PROJECT",  # type: str
        "entity": "TEST_ENTITY",  # type: str
        "task": "Compositing",  # type: str
    },  # type: Optional[QiContext] - Business context only
    "source": {
        "session": "session-uuid-string",  # type: str - Process instance
        "window_uuid": "window-uuid-string",  # type: Optional[str] - UI window instance
        "addon": "addon-skeleton",  # type: Optional[str] - Which addon sent this
    },  # type: Optional[QiSource] - Routing/technical context
    "user": {
        "username": "testuser",  # type: str - Required username
        "auth_data": {},  # type: dict[str, Any] - Flexible auth fields
    },  # type: Optional[QiUser] - Identity/auth context
    "reply_to": "c69e55f3-6b50-4ed6-876d-93fcd6e7b5b4",  # type: Optional[uuid4]
    "timestamp": 1699123456.789,  # type: float (unix timestamp with milliseconds)
}
