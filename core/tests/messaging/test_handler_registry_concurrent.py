"""
Concurrent operation tests for QiHandlerRegistry.

These tests focus on how the handler registry behaves under concurrent conditions,
including simultaneous handler registration, retrieval, and deregistration from
multiple sessions and topics.
"""

import asyncio
import random

import pytest

from core.constants import HUB_ID
from core.messaging.handler_registry import QiHandlerRegistry
from core.models import QiMessage

# Mark all tests as asyncio
pytestmark = pytest.mark.asyncio


# --- Fixtures ---


@pytest.fixture
async def registry():
    """Create a fresh handler registry for testing."""
    return QiHandlerRegistry()


# --- Test Functions ---


async def sample_handler(message: QiMessage):
    """Sample handler function for testing."""
    return f"Handled {message.topic}"


async def sample_handler_with_delay(message: QiMessage):
    """Sample handler with random delay to test concurrency."""
    await asyncio.sleep(random.uniform(0.01, 0.05))
    return f"Delayed handling of {message.topic}"


# --- Concurrency Tests ---


async def test_concurrent_handler_registration(registry):
    """Test registering many handlers concurrently from different sessions."""
    # Parameters for the test
    session_count = 5
    topic_count = 10

    # Create sessions
    sessions = [f"session_{i}" for i in range(session_count)]

    # Create topics
    topics = [f"test.topic.{i}" for i in range(topic_count)]

    # Create registration tasks
    tasks = []
    for session_id in sessions:
        for topic in topics:
            tasks.append(
                asyncio.create_task(
                    registry.register(
                        handler_function=sample_handler,
                        topic=topic,
                        session_id=session_id,
                    )
                )
            )

    # Wait for all registrations to complete
    await asyncio.gather(*tasks)

    # Verify all handlers were registered correctly
    for session_id in sessions:
        for topic in topics:
            handlers = await registry.get_handlers(
                topic=topic,
                session_id=session_id,
            )
            assert len(handlers) == 1

    # Register a handler under HUB_ID for one topic
    hub_topic = topics[0]
    await registry.register(
        handler_function=sample_handler,
        topic=hub_topic,
        session_id=HUB_ID,
    )

    # Now all sessions should see both their own handler and the HUB handler for this topic
    for session_id in sessions:
        handlers = await registry.get_handlers(
            topic=hub_topic,
            session_id=session_id,
        )
        # Each session should see its own handler + the HUB handler
        assert len(handlers) == 2


async def test_concurrent_handler_retrieval(registry):
    """Test retrieving handlers concurrently while registrations are happening."""
    # Register some initial handlers
    for i in range(5):
        await registry.register(
            handler_function=sample_handler,
            topic=f"test.topic.{i}",
            session_id="session_1",
        )

    # Create tasks that register more handlers
    register_tasks = []
    for i in range(5, 15):
        register_tasks.append(
            asyncio.create_task(
                registry.register(
                    handler_function=sample_handler_with_delay,
                    topic=f"test.topic.{i}",
                    session_id="session_2",
                )
            )
        )

    # Create tasks that retrieve handlers
    get_tasks = []
    for i in range(15):
        get_tasks.append(
            asyncio.create_task(
                registry.get_handlers(
                    topic=f"test.topic.{i}",
                    session_id="session_1",  # Use session_1 to test getting its own handlers
                )
            )
        )

    # Wait for all tasks to complete
    registration_results = await asyncio.gather(*register_tasks)
    get_results = await asyncio.gather(*get_tasks)

    # For topics 0-4, we should have found the initial handlers
    for i in range(5):
        assert len(get_results[i]) == 1

    # For topics 5-14, results may vary based on timing:
    # - If the get_handlers ran after registration, we'll have 1 handler
    # - If it ran before registration was complete, we'll have 0 handlers
    # This is expected non-deterministic behavior

    # Final check: all topics should now have handlers
    for i in range(15):
        handlers = await registry.get_handlers(
            topic=f"test.topic.{i}",
            session_id="session_1"
            if i < 5
            else "session_2",  # Use the right session ID
        )
        assert len(handlers) == 1


async def test_concurrent_registrations_same_topic_session(registry):
    """Test registering multiple handlers for the same topic/session concurrently."""
    session_id = "test_session"
    topic = "test.topic"
    handler_count = 20

    # Create registration tasks
    tasks = []
    for i in range(handler_count):
        tasks.append(
            asyncio.create_task(
                registry.register(
                    handler_function=sample_handler,
                    topic=topic,
                    session_id=session_id,
                )
            )
        )

    # Wait for all registrations to complete
    await asyncio.gather(*tasks)

    # Verify all handlers were registered
    handlers = await registry.get_handlers(
        topic=topic,
        session_id=session_id,
    )

    # We should have exactly handler_count handlers
    assert len(handlers) == handler_count


async def test_concurrent_drop_and_register(registry):
    """Test dropping handlers while simultaneously registering new ones."""
    # Register initial handlers
    session_id = "test_session"
    topics = [f"test.topic.{i}" for i in range(10)]

    # Keep track of handler IDs as they're returned from register
    handler_ids = []
    for topic in topics:
        handler_id = await registry.register(
            handler_function=sample_handler,
            topic=topic,
            session_id=session_id,
        )
        handler_ids.append(handler_id)

    # Create tasks to drop the first half of handlers
    drop_tasks = []
    for i in range(5):
        drop_tasks.append(
            asyncio.create_task(registry.drop_handler(handler_id=handler_ids[i]))
        )

    # Create tasks to register new handlers for the first half of topics
    register_tasks = []
    new_handler_ids = []
    for i in range(5):
        task = asyncio.create_task(
            registry.register(
                handler_function=sample_handler_with_delay,
                topic=topics[i],
                session_id=session_id,
            )
        )
        register_tasks.append(task)

    # Wait for all tasks to complete
    await asyncio.gather(*(drop_tasks + register_tasks))

    # Get the new handler IDs that were registered
    new_ids = await asyncio.gather(*register_tasks)

    # Verify the state
    for i in range(10):
        handlers = await registry.get_handlers(
            topic=topics[i],
            session_id=session_id,
        )

        if i < 5:
            # First 5 topics should have exactly 1 handler (old one dropped, new one added)
            assert len(handlers) == 1
        else:
            # Last 5 topics should still have the original handler
            assert len(handlers) == 1


async def test_concurrent_drop_session(registry):
    """Test dropping a session while simultaneously registering and retrieving handlers."""
    # Register handlers for multiple sessions
    session_count = 5
    topic_count = 5

    sessions = [f"session_{i}" for i in range(session_count)]
    topics = [f"test.topic.{i}" for i in range(topic_count)]

    # Register initial handlers
    for session_id in sessions:
        for topic in topics:
            await registry.register(
                handler_function=sample_handler,
                topic=topic,
                session_id=session_id,
            )

    # Start tasks to drop the first session
    drop_task = asyncio.create_task(registry.drop_session(session_id=sessions[0]))

    # Start tasks to register new handlers for that session
    register_tasks = []
    for topic in topics:
        register_tasks.append(
            asyncio.create_task(
                registry.register(
                    handler_function=sample_handler_with_delay,
                    topic=topic,
                    session_id=sessions[0],
                )
            )
        )

    # Start tasks to retrieve handlers for all sessions
    get_tasks = []
    for session_id in sessions:
        for topic in topics:
            get_tasks.append(
                asyncio.create_task(
                    registry.get_handlers(
                        topic=topic,
                        session_id=session_id,
                    )
                )
            )

    # Wait for the drop to complete first
    await drop_task

    # Then wait for the other operations
    register_results = await asyncio.gather(*register_tasks, return_exceptions=True)
    get_results = await asyncio.gather(*get_tasks, return_exceptions=True)

    # New registrations for the dropped session should still succeed
    # (drop_session and register don't conflict in the API contract)

    # Final check: session 0 should have new handlers
    for topic in topics:
        handlers = await registry.get_handlers(
            topic=topic,
            session_id=sessions[0],
        )
        # We should have the newly registered handlers
        assert len(handlers) == 1


async def test_concurrent_clear_registry(registry):
    """Test clearing the registry while operations are in progress."""
    # Register handlers for multiple sessions
    session_count = 5
    topic_count = 5

    sessions = [f"session_{i}" for i in range(session_count)]
    topics = [f"test.topic.{i}" for i in range(topic_count)]

    # Register initial handlers
    for session_id in sessions:
        for topic in topics:
            await registry.register(
                handler_function=sample_handler,
                topic=topic,
                session_id=session_id,
            )

    # Start a task to clear the registry
    clear_task = asyncio.create_task(registry.clear())

    # Start tasks to register new handlers and retrieve existing ones
    register_tasks = []
    get_tasks = []

    for session_id in sessions:
        for topic in topics:
            register_tasks.append(
                asyncio.create_task(
                    registry.register(
                        handler_function=sample_handler_with_delay,
                        topic=f"new.{topic}",
                        session_id=session_id,
                    )
                )
            )
            get_tasks.append(
                asyncio.create_task(
                    registry.get_handlers(
                        topic=topic,
                        session_id=session_id,
                    )
                )
            )

    # Wait for all tasks to complete
    await clear_task
    register_results = await asyncio.gather(*register_tasks, return_exceptions=True)
    get_results = await asyncio.gather(*get_tasks, return_exceptions=True)

    # After clear, the original handlers should be gone
    for session_id in sessions:
        for topic in topics:
            handlers = await registry.get_handlers(
                topic=topic,
                session_id=session_id,
            )
            assert len(handlers) == 0

    # But new handlers registered after clear should still be there
    for session_id in sessions:
        for topic in topics:
            handlers = await registry.get_handlers(
                topic=f"new.{topic}",
                session_id=session_id,
            )
            assert len(handlers) == 1
