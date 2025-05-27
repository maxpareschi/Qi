{
    "message_id": "f69e55f3-6e50-4ed6-876d-93fcd5e7b5b1",  # type: uuid4
    "topic": "TEST_TOPIC",  # type: str
    "payload": {},  # type: dict[str, Any]
    "context": {
        "project": "TEST_PROJECT",  # type: str
        "entity": "TEST_ENTITY",  # type: str
        "task": "Compositing",  # type: str
        "session": "session-uuid-string",  # type: str (session ID - replaces sender and source)
    },  # type: Optional[QiContext]
    "reply_to": "c69e55f3-6b50-4ed6-876d-93fcd6e7b5b4",  # type: Optional[uuid4]
    "timestamp": 1699123456.789,  # type: float (unix timestamp with milliseconds)
}
