"""
Concurrent operation tests for QiConnectionManager.

These tests focus on behavior verification under concurrent conditions,
testing how the connection manager behaves when multiple operations happen
simultaneously and validating proper async waiting patterns to ensure reliability.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from core.messaging.connections import QiConnectionManager
from core.models import QiSession

# Mark all tests in this module as anyio
pytestmark = pytest.mark.anyio


class MockWebSocket:
    """Enhanced mock WebSocket with better async support."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.close_called = False
        self.close_code = None
        self.close_called_event = asyncio.Event()
        self.application_state = MagicMock()
        self.client_state = MagicMock()

    async def close(self, code: int = 1000):
        self.close_called = True
        self.close_code = code
        self.close_called_event.set()
        # Simulate that closing a socket might take a moment
        await asyncio.sleep(0.01)

    def __eq__(self, other):
        if isinstance(other, MockWebSocket):
            return self.session_id == other.session_id
        return False

    def __hash__(self):
        return hash(self.session_id)


def create_session(
    logical_id: str, session_id: str | None = None, parent_logical_id: str | None = None
) -> QiSession:
    """Helper to create a test session with given properties."""
    return QiSession(
        id=session_id or f"session_{logical_id}",
        logical_id=logical_id,
        parent_logical_id=parent_logical_id,
        tags=[],
    )


@pytest.fixture
async def manager() -> QiConnectionManager:
    """Create a fresh connection manager for each test."""
    return QiConnectionManager()


# --- Behavior-focused tests ---


async def test_register_session_behavior(manager: QiConnectionManager):
    """Test registration focusing on observable behavior, not implementation."""
    session = create_session("client1", "session_id_1")
    socket = MockWebSocket("session_id_1")

    await manager.register(socket=socket, session=session)

    # Verify behavior through public interfaces
    assert manager.try_get_socket(session_id=session.id) == socket
    assert manager.try_get_session(session_id=session.id) == session


async def test_unregister_session_behavior(manager: QiConnectionManager):
    """Test unregistration with proper async waiting for socket closure."""
    session = create_session("client1", "session_id_1")
    socket = MockWebSocket("session_id_1")

    await manager.register(socket=socket, session=session)
    await manager.unregister(session_id=session.id)

    # Wait for socket close with timeout
    try:
        await asyncio.wait_for(socket.close_called_event.wait(), timeout=1.0)
    except asyncio.TimeoutError:
        pytest.fail("Socket close was not called within timeout")

    # Verify session is no longer available
    assert manager.try_get_socket(session_id=session.id) is None
    assert manager.try_get_session(session_id=session.id) is None


async def test_replace_session_with_same_logical_id(manager: QiConnectionManager):
    """Test that registering a new session with same logical_id replaces old one."""
    # First session
    session1 = create_session("same_logical", "session_id_1")
    socket1 = MockWebSocket("session_id_1")
    await manager.register(socket=socket1, session=session1)

    # Second session with same logical_id
    session2 = create_session("same_logical", "session_id_2")
    socket2 = MockWebSocket("session_id_2")
    await manager.register(socket=socket2, session=session2)

    # Wait for first socket to be closed
    try:
        await asyncio.wait_for(socket1.close_called_event.wait(), timeout=1.0)
    except asyncio.TimeoutError:
        pytest.fail("First socket was not closed when replaced")

    # Verify only second session is now available
    assert manager.try_get_socket(session_id=session1.id) is None
    assert manager.try_get_session(session_id=session1.id) is None
    assert manager.try_get_socket(session_id=session2.id) == socket2
    assert manager.try_get_session(session_id=session2.id) == session2


# --- Concurrent operation tests ---


async def test_concurrent_registrations(manager: QiConnectionManager):
    """Test multiple registrations happening concurrently."""
    # Create multiple sessions and sockets
    sessions = [create_session(f"client{i}", f"session_{i}") for i in range(10)]
    sockets = [MockWebSocket(s.id) for s in sessions]

    # Create concurrent registration tasks
    tasks = [
        asyncio.create_task(manager.register(socket=socket, session=session))
        for socket, session in zip(sockets, sessions)
    ]

    # Wait for all registrations to complete
    await asyncio.gather(*tasks)

    # Verify all sessions were registered
    for session, socket in zip(sessions, sockets):
        assert manager.try_get_socket(session_id=session.id) == socket
        assert manager.try_get_session(session_id=session.id) == session


async def test_concurrent_register_and_unregister(manager: QiConnectionManager):
    """Test registration and unregistration happening concurrently."""
    # Create sessions
    sessions = [create_session(f"client{i}", f"session_{i}") for i in range(10)]
    sockets = [MockWebSocket(s.id) for s in sessions]

    # Register first half
    for i in range(5):
        await manager.register(socket=sockets[i], session=sessions[i])

    # Concurrently register second half and unregister first half
    register_tasks = [
        asyncio.create_task(manager.register(socket=sockets[i], session=sessions[i]))
        for i in range(5, 10)
    ]

    unregister_tasks = [
        asyncio.create_task(manager.unregister(session_id=sessions[i].id))
        for i in range(5)
    ]

    # Wait for all operations to complete
    await asyncio.gather(*register_tasks, *unregister_tasks)

    # Verify first half is unregistered
    for i in range(5):
        assert manager.try_get_socket(session_id=sessions[i].id) is None

    # Verify second half is registered
    for i in range(5, 10):
        assert manager.try_get_socket(session_id=sessions[i].id) == sockets[i]


# --- Error handling tests ---


async def test_safe_close_handles_exceptions(manager: QiConnectionManager):
    """Test that _safe_close properly handles exceptions during socket close."""
    session = create_session("error_client", "error_session")
    socket = MockWebSocket("error_session")

    # Make socket.close raise an exception
    original_close = socket.close

    async def failing_close(code=1000):
        socket.close_called = True
        socket.close_called_event.set()
        raise RuntimeError("Simulated socket close error")

    socket.close = failing_close

    try:
        # Register and then unregister to trigger _safe_close
        await manager.register(socket=socket, session=session)
        await manager.unregister(session_id=session.id)

        # Wait for close to be called
        await asyncio.wait_for(socket.close_called_event.wait(), timeout=1.0)

        # Verify socket was marked as closed
        assert socket.close_called

        # Verify session was unregistered despite exception
        assert manager.try_get_socket(session_id=session.id) is None
        assert manager.try_get_session(session_id=session.id) is None

    finally:
        # Restore original close method
        socket.close = original_close


async def test_parent_child_relationship_behavior(manager: QiConnectionManager):
    """Test parent-child relationship behavior with wait events."""
    # Create parent session
    parent_session = create_session("parent", "parent_id")
    parent_socket = MockWebSocket("parent_id")

    # Create child sessions
    child1_session = create_session("child1", "child1_id", parent_logical_id="parent")
    child1_socket = MockWebSocket("child1_id")

    child2_session = create_session("child2", "child2_id", parent_logical_id="parent")
    child2_socket = MockWebSocket("child2_id")

    # Register all sessions
    await manager.register(socket=parent_socket, session=parent_session)
    await manager.register(socket=child1_socket, session=child1_session)
    await manager.register(socket=child2_socket, session=child2_session)

    # Verify children are linked to parent
    children = manager.get_children_logicals(logical_id="parent")
    assert "child1" in children
    assert "child2" in children

    # Unregister parent
    await manager.unregister(session_id=parent_session.id)

    # Wait for all sockets to be closed
    try:
        await asyncio.wait_for(
            asyncio.gather(
                parent_socket.close_called_event.wait(),
                child1_socket.close_called_event.wait(),
                child2_socket.close_called_event.wait(),
            ),
            timeout=1.0,
        )
    except asyncio.TimeoutError:
        pytest.fail("Not all sockets were closed within timeout")

    # Verify all sessions are unregistered
    assert manager.try_get_socket(session_id=parent_session.id) is None
    assert manager.try_get_socket(session_id=child1_session.id) is None
    assert manager.try_get_socket(session_id=child2_session.id) is None


# --- Snapshot behavior tests ---


async def test_snapshot_accuracy(manager: QiConnectionManager):
    """Test that snapshots accurately reflect manager state at point of capture."""
    # Create and register some sessions
    sessions = [
        create_session(f"snap_client{i}", f"snap_session_{i}") for i in range(5)
    ]
    sockets = [MockWebSocket(s.id) for s in sessions]

    for socket, session in zip(sockets, sessions):
        await manager.register(socket=socket, session=session)

    # Take a snapshot
    snapshot = await manager.snapshot_sockets()

    # Verify snapshot accuracy
    assert len(snapshot) == 5
    for session, socket in zip(sessions, sockets):
        assert snapshot[session.id] == socket

    # Modify manager state after snapshot
    await manager.unregister(session_id=sessions[0].id)

    # Verify snapshot is unaffected (copy not reference)
    assert len(snapshot) == 5
    assert sessions[0].id in snapshot

    # Take new snapshot
    new_snapshot = await manager.snapshot_sockets()

    # Verify new snapshot reflects changes
    assert len(new_snapshot) == 4
    assert sessions[0].id not in new_snapshot


async def test_snapshot_sessions_by_logical_accuracy_fixed(
    manager: QiConnectionManager,
):
    """
    Test that filtered session snapshots are accurate.
    Note: Each logical_id can only have one session mapped to it at a time,
    so we test with multiple different logical IDs.
    """
    # Create sessions with different logical IDs
    session_a = create_session("group_a_logical", "session_a")
    socket_a = MockWebSocket("session_a")

    session_b = create_session("group_b_logical", "session_b")
    socket_b = MockWebSocket("session_b")

    session_c = create_session("group_c_logical", "session_c")
    socket_c = MockWebSocket("session_c")

    # Register all sessions
    await manager.register(socket=socket_a, session=session_a)
    await manager.register(socket=socket_b, session=session_b)
    await manager.register(socket=socket_c, session=session_c)

    # Query for sessions with logical_ids 'group_a_logical' and 'group_b_logical'
    logical_ids_to_query = ["group_a_logical", "group_b_logical"]
    snapshot = await manager.snapshot_sessions_by_logical(logical_ids_to_query)

    # Should return exactly 2 sessions - one for each logical_id in the query
    assert len(snapshot) == 2

    # Both of our sessions should be in the result
    assert "session_a" in snapshot
    assert "session_b" in snapshot

    # The third session should not be included
    assert "session_c" not in snapshot

    # Verify the socket objects are correct
    assert snapshot["session_a"] == socket_a
    assert snapshot["session_b"] == socket_b
