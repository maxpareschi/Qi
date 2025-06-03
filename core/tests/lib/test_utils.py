import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from core.lib.utils import (  # Import _cpu_executor for potential cleanup
    _cpu_executor,
    cpu_bound,
)

pytestmark = pytest.mark.asyncio

# --- Test Functions to be Decorated ---


def sync_task_add(a, b):
    """Simple synchronous task that adds two numbers."""
    return a + b


async def async_task_multiply(a, b):
    """Simple asynchronous task that multiplies two numbers."""
    await asyncio.sleep(0.01)  # Simulate some async work
    return a * b


def sync_task_with_kwargs(a, b=0, *, c=0):
    """Synchronous task with keyword arguments."""
    return a + b + c


def sync_long_task(duration):
    """Synchronous task that blocks for a given duration."""
    time.sleep(duration)
    return f"Slept for {duration} seconds"


# --- Fixture for executor cleanup (optional but good practice) ---
@pytest.fixture(scope="module", autouse=True)
def cleanup_executor():
    """Ensure the global ProcessPoolExecutor is shut down after tests in this module."""
    yield
    # This is a global executor, ensure it's shut down.
    # Depending on how ProcessPoolExecutor is managed in the app, direct shutdown here might be aggressive
    # or might conflict if the app has its own lifecycle. For testing utils.py in isolation, it is okay.
    _cpu_executor.shutdown(wait=True)


# --- Tests for @cpu_bound decorator --- #


async def test_cpu_bound_on_sync_function():
    """Test that @cpu_bound correctly decorates and executes a synchronous function."""
    decorated_add = cpu_bound(sync_task_add)
    result = await decorated_add(5, 3)
    assert result == 8


async def test_cpu_bound_on_async_function_is_still_awaitable():
    """Test that @cpu_bound on an async function returns an awaitable and works.
    Note: While cpu_bound is for CPU-bound sync tasks, testing with async ensures it doesn't break.
    The ProcessPoolExecutor itself won't run the async function's event loop, it will run the coroutine object.
    This will likely run the async function synchronously within the executor process.
    This is generally NOT the intended use for cpu_bound (async functions should typically
    be run with asyncio.gather, etc., or if truly CPU bound and async, require careful handling).
    However, the test ensures the decorator doesn't outright fail.
    """
    decorated_multiply = cpu_bound(async_task_multiply)
    # This will effectively run `loop.run_in_executor(_cpu_executor, partial(async_task_multiply, 10, 2))`
    # `partial(async_task_multiply, 10, 2)` returns a coroutine object.
    # `run_in_executor` with a coroutine might not behave as expected for true async execution within the process pool.
    # It will likely run the coroutine to completion as if it were a sync function in the pool process.
    result = await decorated_multiply(10, 2)
    assert result == 20


async def test_cpu_bound_passes_args_and_kwargs_correctly():
    """Test that arguments and keyword arguments are passed correctly by @cpu_bound."""
    decorated_task = cpu_bound(sync_task_with_kwargs)

    # Positional args only
    result1 = await decorated_task(10)
    assert result1 == 10  # a=10, b=0 (default), c=0 (default)

    # Positional and keyword args
    result2 = await decorated_task(5, b=5)
    assert result2 == 10  # a=5, b=5, c=0 (default)

    # All as keyword args
    result3 = await decorated_task(a=3, b=3, c=3)
    assert result3 == 9

    # Only required and keyword-only
    result4 = await decorated_task(7, c=3)
    assert result4 == 10  # a=7, b=0 (default), c=3


async def test_cpu_bound_runs_in_different_thread_or_process(event_loop):
    """Test that the decorated function runs in a different thread/process (characteristic of run_in_executor)."""
    # This is an indirect test. We check if a blocking call doesn't block the main event loop.
    decorated_long_task = cpu_bound(sync_long_task)

    start_time = time.perf_counter()

    # Run two tasks that should be offloaded
    # If they run sequentially in the main thread, total time > 0.2s significantly
    # If they run in parallel in executor, total time approx 0.1s (plus overhead)
    task1 = decorated_long_task(0.1)
    task2 = decorated_long_task(0.1)

    results = await asyncio.gather(task1, task2)

    end_time = time.perf_counter()
    duration = end_time - start_time

    assert "Slept for 0.1 seconds" in results[0]
    assert "Slept for 0.1 seconds" in results[1]

    # Check that it didn't block excessively (indicating offloading)
    # Should be slightly more than 0.1 due to overhead, but much less than 0.2
    # ProcessPoolExecutor startup can add overhead, so tolerance is key.
    # print(f"Duration for two 0.1s tasks: {duration}")
    assert duration < 0.18, (
        "Tasks took too long, suggesting they might not have run concurrently in executor."
    )


@patch("core.lib.utils.asyncio.get_running_loop")
async def test_cpu_bound_uses_run_in_executor(mock_get_loop):
    """Verify that run_in_executor is called with the correct executor."""
    mock_loop = MagicMock()
    mock_get_loop.return_value = mock_loop
    mock_loop.run_in_executor = MagicMock(return_value=asyncio.Future())
    mock_loop.run_in_executor.return_value.set_result("mock_result")

    decorated_add = cpu_bound(sync_task_add)
    result = await decorated_add(1, 2)

    assert result == "mock_result"
    # Check that run_in_executor was called, with _cpu_executor as the first argument
    # The second argument is a functools.partial object, which is harder to assert directly by value
    # So, we check the executor instance and that it was called.
    assert mock_loop.run_in_executor.call_count == 1
    args, _ = mock_loop.run_in_executor.call_args
    assert args[0] is _cpu_executor  # Check it's the same executor instance
    # Example of checking the partial if needed, though often not done due to complexity
    # from functools import partial
    # assert isinstance(args[1], partial)
    # assert args[1].func == sync_task_add
    # assert args[1].args == (1,2)
