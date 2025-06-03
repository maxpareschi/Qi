import asyncio
from unittest.mock import MagicMock

import pytest

from core.bases.models import QiSession
from core.messaging.connection_manager import QiConnectionManager

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio


class MockWebSocket:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.close_called = False
        self.close_code = None
        self.application_state = MagicMock()  # For FastAPI internals if needed
        self.client_state = MagicMock()  # For FastAPI internals if needed

    async def close(self, code: int = 1000):
        self.close_called = True
        self.close_code = code
        # Simulate that closing a socket might take a moment
        # or that create_task schedules it
        await asyncio.sleep(0)

    def __eq__(self, other):
        if isinstance(other, MockWebSocket):
            return self.session_id == other.session_id
        return False

    def __hash__(self):
        return hash(self.session_id)


def create_session(
    logical_id: str, session_id: str | None = None, parent_logical_id: str | None = None
) -> QiSession:
    return QiSession(
        id=session_id
        or f"session_{logical_id}",  # Ensure unique session.id if not provided
        logical_id=logical_id,
        parent_logical_id=parent_logical_id,
        tags=[],
    )


@pytest.fixture
async def manager() -> QiConnectionManager:
    return QiConnectionManager()


# --- Basic Registration and Unregistration ---


async def test_register_new_session(manager: QiConnectionManager):
    session1 = create_session("client1", "session_id_1")
    socket1 = MockWebSocket("session_id_1")

    await manager.register(socket=socket1, session=session1)

    # Check internal state (ideally through public methods if possible, but direct for verification)
    assert session1.id in manager._sockets
    assert manager._sockets[session1.id] == socket1
    assert session1.id in manager._sessions
    assert manager._sessions[session1.id] == session1
    assert manager._logical_to_session[session1.logical_id] == session1.id

    # Test get_socket and get_live_session_id
    retrieved_socket = await manager.get_socket(session1.id)
    assert retrieved_socket == socket1
    live_session_id = await manager.get_live_session_id(session1.logical_id)
    assert live_session_id == session1.id


async def test_unregister_session(manager: QiConnectionManager):
    session1 = create_session("client1", "session_id_1")
    socket1 = MockWebSocket("session_id_1")

    await manager.register(socket=socket1, session=session1)
    await manager.unregister(session_id=session1.id)

    assert session1.id not in manager._sockets
    assert session1.id not in manager._sessions
    assert session1.logical_id not in manager._logical_to_session  # This should be gone
    assert socket1.close_called is True

    retrieved_socket = await manager.get_socket(session1.id)
    assert retrieved_socket is None
    live_session_id = await manager.get_live_session_id(session1.logical_id)
    assert live_session_id is None


# --- Test Overwriting/Hot-Reload ---


async def test_register_existing_logical_id_replaces_old(manager: QiConnectionManager):
    # Session 1
    session1 = create_session("client_A", "session_id_A1")
    socket1 = MockWebSocket("session_id_A1")
    await manager.register(socket=socket1, session=session1)

    assert await manager.get_live_session_id("client_A") == "session_id_A1"
    assert await manager.get_socket("session_id_A1") == socket1

    # Session 2 with same logical_id
    session2 = create_session(
        "client_A", "session_id_A2"
    )  # New session.id, same logical_id
    socket2 = MockWebSocket("session_id_A2")
    await manager.register(socket=socket2, session=session2)

    # Old session should be gone and its socket closed
    assert socket1.close_called is True
    assert await manager.get_socket("session_id_A1") is None

    # New session should be active
    assert await manager.get_live_session_id("client_A") == "session_id_A2"
    assert await manager.get_socket("session_id_A2") == socket2
    assert "session_id_A1" not in manager._sessions
    assert "session_id_A2" in manager._sessions


# --- Test Parent-Child Relationships and Unregistration ---


async def test_unregister_parent_unregisters_children(manager: QiConnectionManager):
    parent_session = create_session("parent1", "parent_session_id")
    parent_socket = MockWebSocket("parent_session_id")
    await manager.register(socket=parent_socket, session=parent_session)

    child1_session = create_session(
        "child1", "child1_session_id", parent_logical_id="parent1"
    )
    child1_socket = MockWebSocket("child1_session_id")
    await manager.register(socket=child1_socket, session=child1_session)

    child2_session = create_session(
        "child2", "child2_session_id", parent_logical_id="parent1"
    )
    child2_socket = MockWebSocket("child2_session_id")
    await manager.register(socket=child2_socket, session=child2_session)

    grandchild_session = create_session(
        "grandchild1", "gc1_session_id", parent_logical_id="child1"
    )
    grandchild_socket = MockWebSocket("gc1_session_id")
    await manager.register(socket=grandchild_socket, session=grandchild_session)

    # Verify setup
    assert "parent1" in manager._children
    assert manager._children["parent1"] == {"child1", "child2"}
    assert "child1" in manager._children
    assert manager._children["child1"] == {"grandchild1"}

    # Unregister parent
    await manager.unregister(session_id=parent_session.id)
    await asyncio.sleep(
        0.01
    )  # Allow time for create_task in _unsafe_unregister to run closes

    # All sockets should be closed
    assert parent_socket.close_called is True
    assert child1_socket.close_called is True
    assert child2_socket.close_called is True
    assert grandchild_socket.close_called is True

    # All sessions should be gone
    assert not manager._sockets
    assert not manager._sessions
    assert not manager._logical_to_session
    assert not manager._children


async def test_unregister_child_does_not_unregister_parent(
    manager: QiConnectionManager,
):
    parent_session = create_session("parent2", "parent_session_id_2")
    parent_socket = MockWebSocket("parent_session_id_2")
    await manager.register(socket=parent_socket, session=parent_session)

    child_session = create_session(
        "child_of_parent2", "child_session_id_2", parent_logical_id="parent2"
    )
    child_socket = MockWebSocket("child_session_id_2")
    await manager.register(socket=child_socket, session=child_session)

    # Unregister child
    await manager.unregister(session_id=child_session.id)
    await asyncio.sleep(0.01)  # Allow time for close tasks

    # Child socket closed, parent not
    assert child_socket.close_called is True
    assert parent_socket.close_called is False

    # Child session gone, parent remains
    assert await manager.get_socket(child_session.id) is None
    assert await manager.get_live_session_id("child_of_parent2") is None
    assert await manager.get_socket(parent_session.id) == parent_socket
    assert await manager.get_live_session_id("parent2") == parent_session.id
    assert manager._children["parent2"] == set()  # Child removed from parent's list


# --- Test Snapshot and Utility Methods ---


async def test_snapshot_sockets(manager: QiConnectionManager):
    session1 = create_session("client_snap1", "snap_s1")
    socket1 = MockWebSocket("snap_s1")
    session2 = create_session("client_snap2", "snap_s2")
    socket2 = MockWebSocket("snap_s2")

    await manager.register(socket=socket1, session=session1)
    await manager.register(socket=socket2, session=session2)

    snapshot = await manager.snapshot_sockets()
    assert len(snapshot) == 2
    assert snapshot["snap_s1"] == socket1
    assert snapshot["snap_s2"] == socket2
    # Ensure it's a copy
    snapshot.clear()
    assert len(manager._sockets) == 2


async def test_snapshot_sessions_by_logical(manager: QiConnectionManager):
    s1 = create_session("log_A", "s_A")
    sock_A = MockWebSocket("s_A")
    s2 = create_session("log_B", "s_B")
    sock_B = MockWebSocket("s_B")
    s3 = create_session("log_C", "s_C")  # This one won't be queried
    sock_C = MockWebSocket("s_C")

    await manager.register(socket=sock_A, session=s1)
    await manager.register(socket=sock_B, session=s2)
    await manager.register(socket=sock_C, session=s3)

    snapshot = await manager.snapshot_sessions_by_logical(
        ["log_A", "log_B", "log_D_nonexistent"]
    )
    assert len(snapshot) == 2
    assert snapshot["s_A"] == sock_A
    assert snapshot["s_B"] == sock_B
    assert "s_C" not in snapshot


async def test_get_all_logical_ids(manager: QiConnectionManager):
    s1 = create_session("log_X", "s_X")
    s2 = create_session("log_Y", "s_Y")
    await manager.register(socket=MockWebSocket("s_X"), session=s1)
    await manager.register(socket=MockWebSocket("s_Y"), session=s2)

    logical_ids = await manager.get_all_logical_ids()
    assert sorted(logical_ids) == sorted(["log_X", "log_Y"])


# --- Test Lock-Free Getters ---


async def test_try_get_socket_and_session(manager: QiConnectionManager):
    session = create_session("client_try", "try_s1")
    socket = MockWebSocket("try_s1")
    await manager.register(socket=socket, session=session)

    assert manager.try_get_socket(session_id="try_s1") == socket
    assert manager.try_get_session(session_id="try_s1") == session

    assert manager.try_get_socket(session_id="nonexistent") is None
    assert manager.try_get_session(session_id="nonexistent") is None


async def test_get_children_logicals(manager: QiConnectionManager):
    parent = create_session("parent_gc", "parent_gc_id")
    child1 = create_session("child_gc1", "child_gc1_id", parent_logical_id="parent_gc")
    child2 = create_session("child_gc2", "child_gc2_id", parent_logical_id="parent_gc")

    await manager.register(socket=MockWebSocket(parent.id), session=parent)
    await manager.register(socket=MockWebSocket(child1.id), session=child1)
    await manager.register(socket=MockWebSocket(child2.id), session=child2)

    children = manager.get_children_logicals(logical_id="parent_gc")
    assert children == {"child_gc1", "child_gc2"}

    # Test copy
    children.add("fake_child")
    assert manager.get_children_logicals(logical_id="parent_gc") == {
        "child_gc1",
        "child_gc2",
    }

    assert manager.get_children_logicals(logical_id="nonexistent_parent") == set()


# --- Test close_all ---
async def test_close_all_sessions(manager: QiConnectionManager):
    session1 = create_session("client_close1", "close_s1")
    socket1 = MockWebSocket("close_s1")
    session2 = create_session(
        "client_close2", "close_s2", parent_logical_id="client_close1"
    )
    socket2 = MockWebSocket("close_s2")

    await manager.register(socket=socket1, session=session1)
    await manager.register(socket=socket2, session=session2)

    await manager.close_all()
    await asyncio.sleep(0.01)  # Allow time for close tasks

    assert not manager._sockets
    assert not manager._sessions
    assert not manager._logical_to_session
    assert not manager._children
    assert socket1.close_called is True
    assert socket2.close_called is True


# --- Test unregistering non-existent session ---
async def test_unregister_non_existent_session(manager: QiConnectionManager):
    # Should not raise any error
    try:
        await manager.unregister(session_id="does_not_exist")
    except Exception as e:
        pytest.fail(f"Unregistering non-existent session raised an exception: {e}")


# --- Test _safe_close robustness ---
async def test_safe_close_already_closed_socket(manager: QiConnectionManager):
    mock_socket_obj = MockWebSocket("test_safe_close")

    # Simulate a socket that errors on close (e.g., already closed)
    async def mock_close_with_error(code=1000):
        mock_socket_obj.close_called = True  # mark it as called
        raise RuntimeError("Socket already closed or network error")

    original_close = mock_socket_obj.close
    mock_socket_obj.close = mock_close_with_error

    try:
        session = create_session("faulty_socket_client", "faulty_socket_id")
        # Manually insert the faulty socket to test _unsafe_unregister behavior
        # This is a bit of a white-box test for _safe_close robustness via its caller
        async with manager._lock:  # Need lock to modify internal state for test setup
            manager._sockets[session.id] = mock_socket_obj
            manager._sessions[session.id] = session
            manager._logical_to_session[session.logical_id] = session.id

        await manager.unregister(session_id=session.id)
        await asyncio.sleep(0.01)  # Allow time for close tasks

        # If it reaches here without an unhandled exception from the log,
        # _safe_close handled the error as expected (logged it).
        assert mock_socket_obj.close_called is True

    except Exception as e:
        pytest.fail(
            f"_safe_close (via unregister) did not handle socket close error: {e}"
        )
    finally:
        mock_socket_obj.close = original_close  # Restore original close method
