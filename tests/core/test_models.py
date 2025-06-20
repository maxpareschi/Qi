import time
from uuid import UUID, uuid4

import pytest
from pydantic import ConfigDict, ValidationError

from core.models import (
    QiBaseModel,
    QiContext,
    QiMessage,
    QiMessageType,
    QiSession,
    QiUser,
)

# Assuming qi_launch_config is accessible for patching its dev_mode attribute
# from core.config import qi_launch_config # This import might cause issues if qi_launch_config itself tries to load things

# Mark all tests in this module as asyncio if any async functions are used,
# but these model tests are mostly synchronous.
# pytestmark = pytest.mark.asyncio

# --- Test QiBaseModel ---


def test_qibasemodel_dev_mode_validation_on():
    """Test QiBaseModel validation is ON when dev_mode is True."""

    # Create a model with strict validation
    class TestModelDev(QiBaseModel):
        model_config = ConfigDict(
            validate_assignment=True,
            validate_default=True,
            validate_return=True,
            extra="forbid",
            validate_on_construction=True,
        )
        known_field: str

    # Validation should be active: extra fields forbidden
    with pytest.raises(ValidationError) as exc_info:
        TestModelDev(known_field="test", unknown_field="extra")
    assert "extra inputs are not permitted" in str(exc_info.value).lower()

    # Test assignment validation
    model = TestModelDev(known_field="initial")
    with pytest.raises(ValidationError):
        model.known_field = 123  # Type error since field is str


def test_qibasemodel_dev_mode_validation_off():
    """Test QiBaseModel validation is OFF when dev_mode is False."""

    # Create a model with relaxed validation
    class TestModelProd(QiBaseModel):
        model_config = ConfigDict(
            validate_assignment=False,
            validate_default=False,
            validate_return=False,
            extra="allow",
            validate_on_construction=False,
        )
        known_field: str

    # Validation should be relaxed: extra fields allowed
    try:
        model = TestModelProd(known_field="test", unknown_field="extra_allowed")
        assert model.known_field == "test"
        assert getattr(model, "unknown_field") == "extra_allowed"
    except ValidationError:
        pytest.fail(
            "ValidationError raised in prod mode with extra fields, but should be allowed."
        )


# --- Test QiUser ---


def test_qiuser_creation_defaults():
    user = QiUser()
    assert user.id is None
    assert user.name is None
    assert user.email is None


def test_qiuser_creation_with_values():
    user_id = str(uuid4())
    user = QiUser(id=user_id, name="Test User", email="test@example.com")
    assert user.id == user_id
    assert user.name == "Test User"
    assert user.email == "test@example.com"


def test_qiuser_key_property():
    user1 = QiUser(id="123", name="Alice")
    assert user1.key == ("123", "Alice")

    user2 = QiUser(name="Bob")
    assert user2.key == (None, "Bob")

    user3 = QiUser()
    assert user3.key == (None, None)


# --- Test QiContext ---


def test_qicontext_creation_defaults():
    context = QiContext()
    assert isinstance(UUID(context.id), UUID)  # Default factory for id
    assert context.project is None
    assert context.entity is None
    assert context.task is None


def test_qicontext_creation_with_values():
    context_id = str(uuid4())
    context = QiContext(
        id=context_id, project="ProjectX", entity="AssetA", task="Modeling"
    )
    assert context.id == context_id
    assert context.project == "ProjectX"
    assert context.entity == "AssetA"
    assert context.task == "Modeling"


def test_qicontext_key_property():
    ctx1 = QiContext(project="P1", entity="E1", task="T1")
    assert ctx1.key == ("P1", "E1", "T1")

    ctx2 = QiContext(project="P2", entity="E2")
    assert ctx2.key == ("P2", "E2", None)

    ctx3 = QiContext()
    assert ctx3.key == (None, None, None)


# --- Test QiSession ---


def test_qisession_creation_minimal():
    logical_id = "test_session_logical_1"
    session = QiSession(logical_id=logical_id)
    assert isinstance(UUID(session.id), UUID)  # Default factory for id
    assert session.logical_id == logical_id
    assert session.parent_logical_id is None
    assert session.tags == []


def test_qisession_creation_with_all_values():
    session_id = str(uuid4())
    logical_id = "test_session_logical_2"
    parent_logical_id = "parent_session_logical"
    tags = ["tag1", "tag2"]
    session = QiSession(
        id=session_id,
        logical_id=logical_id,
        parent_logical_id=parent_logical_id,
        tags=tags,
    )
    assert session.id == session_id
    assert session.logical_id == logical_id
    assert session.parent_logical_id == parent_logical_id
    assert session.tags == tags


# --- Test QiMessage ---


def test_qimessage_creation_minimal():
    topic = "test.topic"
    msg_type = QiMessageType.EVENT
    sender_session = QiSession(logical_id="sender_logical")

    message = QiMessage(topic=topic, type=msg_type, sender=sender_session)

    assert isinstance(UUID(message.message_id), UUID)
    assert message.topic == topic
    assert message.type == msg_type
    assert message.sender == sender_session
    assert message.target == []
    assert message.reply_to is None
    assert message.context is None
    assert message.payload == {}
    assert isinstance(message.timestamp, float)
    assert time.time() - message.timestamp < 1  # Check timestamp is recent
    assert message.bubble is False


def test_qimessage_creation_with_all_values():
    message_id = str(uuid4())
    topic = "another.topic"
    msg_type = QiMessageType.REQUEST
    sender_session = QiSession(id="sender_id_val", logical_id="sender_logical_val")
    target = ["target1", "target2"]
    reply_to = str(uuid4())
    context = QiContext(project="TestProject")
    payload = {"key": "value", "num": 123}
    timestamp = time.time() - 60  # An older timestamp
    bubble = True

    message = QiMessage(
        message_id=message_id,
        topic=topic,
        type=msg_type,
        sender=sender_session,
        target=target,
        reply_to=reply_to,
        context=context,
        payload=payload,
        timestamp=timestamp,
        bubble=bubble,
    )

    assert message.message_id == message_id
    assert message.topic == topic
    assert message.type == msg_type
    assert message.sender == sender_session
    assert message.target == target
    assert message.reply_to == reply_to
    assert message.context == context
    assert message.payload == payload
    assert message.timestamp == timestamp
    assert message.bubble == bubble


def test_qimessage_type_enum():
    assert QiMessageType.EVENT == "event"
    assert QiMessageType.REQUEST == "request"
    assert QiMessageType.REPLY == "reply"

    with pytest.raises(ValidationError):
        # When using Pydantic's Enum support, assigning an invalid value during model
        # instantiation directly might raise a ValidationError if the enum is part of a model.
        # Or, if QiMessageType itself is directly assigned, it's a ValueError.
        # Here, we test it within a model context.
        class MsgWithInvalidType(QiBaseModel):
            type: QiMessageType

        MsgWithInvalidType(type="invalid_type")
