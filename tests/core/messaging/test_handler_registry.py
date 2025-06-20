import pytest

from core.messaging.handlers import HUB_ID, QiHandlerRegistry
from core.models import (
    QiMessage,  # Assuming QiMessage is needed for handler signatures
)

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio

# --- Mocks and Fixtures ---


async def mock_handler_one(message: QiMessage):
    return "handler_one_response"


async def mock_handler_two(message: QiMessage):
    return "handler_two_response"


def sync_mock_handler(message: QiMessage):
    return "sync_handler_response"


@pytest.fixture
async def registry() -> QiHandlerRegistry:
    reg = QiHandlerRegistry()
    # Clear to ensure pristine state for each test if needed, though fixture should do this.
    await reg.clear()
    return reg


# --- Test Basic Registration ---


async def test_register_handler(registry: QiHandlerRegistry):
    handler_id = await registry.register(
        mock_handler_one, topic="test.topic", session_id="session1"
    )
    assert isinstance(handler_id, str)

    # Verify internal state (example, not exhaustive for all internal maps)
    assert handler_id in registry._by_id
    assert registry._by_id[handler_id] == mock_handler_one
    assert handler_id in registry._by_topic["test.topic"]
    assert registry._by_topic["test.topic"][handler_id] == mock_handler_one
    assert handler_id in registry._by_session["session1"]
    assert registry._handler_id_to_topic[handler_id] == "test.topic"


async def test_register_multiple_handlers_same_topic_same_session(
    registry: QiHandlerRegistry,
):
    handler_id1 = await registry.register(
        mock_handler_one, topic="multi.topic", session_id="s1"
    )
    handler_id2 = await registry.register(
        mock_handler_two, topic="multi.topic", session_id="s1"
    )  # Different function
    handler_id3 = await registry.register(
        mock_handler_one, topic="multi.topic", session_id="s1"
    )  # Same function again

    assert handler_id1 != handler_id2
    assert handler_id1 != handler_id3
    assert handler_id2 != handler_id3

    handlers = await registry.get_handlers(topic="multi.topic", session_id="s1")
    assert len(handlers) == 3
    # Order might not be guaranteed, check presence
    assert mock_handler_one in handlers
    assert mock_handler_two in handlers
    # mock_handler_one appears twice
    assert sum(1 for h in handlers if h == mock_handler_one) == 2


async def test_register_same_handler_different_topics_or_sessions(
    registry: QiHandlerRegistry,
):
    await registry.register(mock_handler_one, topic="topic.A", session_id="s1")
    await registry.register(
        mock_handler_one, topic="topic.B", session_id="s1"
    )  # Same session, diff topic
    await registry.register(
        mock_handler_one, topic="topic.A", session_id="s2"
    )  # Diff session, same topic

    handlers_s1_A = await registry.get_handlers(topic="topic.A", session_id="s1")
    handlers_s1_B = await registry.get_handlers(topic="topic.B", session_id="s1")
    handlers_s2_A = await registry.get_handlers(topic="topic.A", session_id="s2")

    assert len(handlers_s1_A) == 1 and handlers_s1_A[0] == mock_handler_one
    assert len(handlers_s1_B) == 1 and handlers_s1_B[0] == mock_handler_one
    assert len(handlers_s2_A) == 1 and handlers_s2_A[0] == mock_handler_one


# --- Test Get Handlers (Two-Tier Logic) ---


async def test_get_handlers_no_handlers_found(registry: QiHandlerRegistry):
    handlers = await registry.get_handlers(topic="nonexistent.topic", session_id="s1")
    assert handlers == []


async def test_get_handlers_session_specific_only(registry: QiHandlerRegistry):
    await registry.register(mock_handler_one, topic="get.test", session_id="s_specific")
    handlers = await registry.get_handlers(topic="get.test", session_id="s_specific")
    assert handlers == [mock_handler_one]


async def test_get_handlers_hub_specific_only(registry: QiHandlerRegistry):
    await registry.register(mock_handler_one, topic="get.test", session_id=HUB_ID)
    handlers = await registry.get_handlers(
        topic="get.test", session_id="s_any_other"
    )  # Requesting session is not HUB_ID
    assert handlers == [mock_handler_one]


async def test_get_handlers_session_and_hub_tiering(registry: QiHandlerRegistry):
    await registry.register(mock_handler_one, topic="tiered.get", session_id="s_user1")
    await registry.register(mock_handler_two, topic="tiered.get", session_id=HUB_ID)
    await registry.register(
        sync_mock_handler, topic="tiered.get", session_id="s_user1"
    )  # another for s_user1

    handlers_user1 = await registry.get_handlers(
        topic="tiered.get", session_id="s_user1"
    )
    # Expect session-specific first (order among them might not be guaranteed by get_handlers)
    assert len(handlers_user1) == 3
    assert mock_handler_one in handlers_user1[:2]  # s_user1's handlers
    assert sync_mock_handler in handlers_user1[:2]  # s_user1's handlers
    assert mock_handler_two == handlers_user1[2]  # HUB_ID handler last

    # Check for a different session that should only get HUB handler
    handlers_user2 = await registry.get_handlers(
        topic="tiered.get", session_id="s_user2"
    )
    assert handlers_user2 == [mock_handler_two]


async def test_get_handlers_hub_requesting_as_hub(registry: QiHandlerRegistry):
    # If HUB_ID itself requests, it should only get its own handlers, not duplicated.
    await registry.register(mock_handler_one, topic="hub.topic", session_id=HUB_ID)
    await registry.register(mock_handler_two, topic="hub.topic", session_id=HUB_ID)

    handlers = await registry.get_handlers(topic="hub.topic", session_id=HUB_ID)
    assert len(handlers) == 2
    assert mock_handler_one in handlers
    assert mock_handler_two in handlers


# --- Test Dropping Handlers ---


async def test_drop_handler_by_id(registry: QiHandlerRegistry):
    handler_id1 = await registry.register(
        mock_handler_one, topic="drop.test", session_id="s1"
    )
    handler_id2 = await registry.register(
        mock_handler_two, topic="drop.test", session_id="s1"
    )

    await registry.drop_handler(handler_id=handler_id1)

    assert handler_id1 not in registry._by_id
    assert handler_id1 not in registry._by_topic["drop.test"]
    assert handler_id1 not in registry._by_session["s1"]
    assert handler_id1 not in registry._handler_id_to_topic

    # Ensure second handler is still there
    assert handler_id2 in registry._by_id
    handlers = await registry.get_handlers(topic="drop.test", session_id="s1")
    assert handlers == [mock_handler_two]

    # Test dropping a non-existent handler_id
    await registry.drop_handler(handler_id="non_existent_id")  # Should not raise


async def test_drop_handler_last_one_for_topic_cleans_topic_entry(
    registry: QiHandlerRegistry,
):
    handler_id = await registry.register(
        mock_handler_one, topic="empty.topic.test", session_id="s1"
    )
    await registry.drop_handler(handler_id=handler_id)
    assert "empty.topic.test" not in registry._by_topic


async def test_drop_handler_last_one_for_session_cleans_session_entry(
    registry: QiHandlerRegistry,
):
    handler_id = await registry.register(
        mock_handler_one, topic="topic.test", session_id="empty_session_test"
    )
    await registry.drop_handler(handler_id=handler_id)
    assert "empty_session_test" not in registry._by_session


async def test_drop_session(registry: QiHandlerRegistry):
    # Initialize session state
    registry._by_session = {"s1": set(), "s2": set(), HUB_ID: set()}

    # Session s1 handlers
    s1_h1_id = await registry.register(
        mock_handler_one, topic="ds.topic1", session_id="s1"
    )
    s1_h2_id = await registry.register(
        mock_handler_two, topic="ds.topic2", session_id="s1"
    )
    registry._by_session["s1"].update({s1_h1_id, s1_h2_id})

    # Session s2 handlers
    s2_handler_id = await registry.register(
        sync_mock_handler, topic="ds.topic1", session_id="s2"
    )
    registry._by_session["s2"].add(s2_handler_id)

    # HUB handler
    hub_handler_id = await registry.register(
        mock_handler_one, topic="ds.topic1", session_id=HUB_ID
    )
    registry._by_session[HUB_ID].add(hub_handler_id)

    await registry.drop_session(session_id="s1")

    # s1 should be gone from _by_session
    assert "s1" not in registry._by_session

    # s1's handlers should be gone from _by_id and _handler_id_to_topic and _by_topic
    s1_handlers_topic1 = await registry.get_handlers(topic="ds.topic1", session_id="s1")
    s1_handlers_topic2 = await registry.get_handlers(topic="ds.topic2", session_id="s1")
    assert len(s1_handlers_topic1) == 1  # Only HUB handler left for this session view
    assert s1_handlers_topic1[0] == mock_handler_one  # HUB's mock_handler_one
    assert s1_handlers_topic2 == []  # No HUB handler for this topic

    # Check a specific handler from s1 is gone from _by_id
    assert s1_h1_id not in registry._by_id
    assert s1_h1_id not in registry._handler_id_to_topic

    # s2 and HUB handlers should remain
    assert "s2" in registry._by_session
    assert s2_handler_id in registry._by_id
    assert hub_handler_id in registry._by_id


# --- Test Clear Method ---


async def test_clear_registry(registry: QiHandlerRegistry):
    await registry.register(mock_handler_one, topic="clear.topic", session_id="s1")
    await registry.register(mock_handler_two, topic="clear.topic", session_id=HUB_ID)

    await registry.clear()

    assert not registry._by_id
    assert not registry._by_topic
    assert not registry._by_session
    assert not registry._handler_id_to_topic

    handlers = await registry.get_handlers(topic="clear.topic", session_id="s1")
    assert handlers == []


# --- Test Consistency (Indirectly) ---
# _assert_consistency is called internally if __debug__ is true.
# These tests ensure operations leave the registry in a valid state.
# We can't easily force __debug__ to be true/false here without deeper pytest config,
# so we rely on the fact that pytest often runs with assertions enabled.


async def test_complex_sequence_for_consistency(registry: QiHandlerRegistry):
    h1_s1_t1_id = await registry.register(mock_handler_one, topic="t1", session_id="s1")
    _ = await registry.register(mock_handler_two, topic="t1", session_id="s1")
    h3_s2_t1_id = await registry.register(
        sync_mock_handler, topic="t1", session_id="s2"
    )
    h4_hub_t1_id = await registry.register(
        mock_handler_one, topic="t1", session_id=HUB_ID
    )
    h5_s1_t2_id = await registry.register(mock_handler_two, topic="t2", session_id="s1")

    # Drop a specific handler
    await registry.drop_handler(handler_id=h1_s1_t1_id)
    # Drop a session
    await registry.drop_session(session_id="s2")  # This will remove h3_s2_t1_id

    # Check some remaining handlers
    s1_t1_handlers = await registry.get_handlers(topic="t1", session_id="s1")
    assert (
        len(s1_t1_handlers) == 2
    )  # mock_handler_two (from s1) and mock_handler_one (from HUB)
    assert mock_handler_two in s1_t1_handlers
    assert mock_handler_one in s1_t1_handlers

    s1_t2_handlers = await registry.get_handlers(topic="t2", session_id="s1")
    assert s1_t2_handlers == [mock_handler_two]

    # Ensure removed ones are gone
    assert h1_s1_t1_id not in registry._by_id
    assert h3_s2_t1_id not in registry._by_id
    assert "s2" not in registry._by_session

    # Check that remaining HUB and s1 handlers for t1 are correct
    assert h4_hub_t1_id in registry._by_id
    assert h5_s1_t2_id in registry._by_id

    # Clear all
    await registry.clear()
    assert not registry._by_id
