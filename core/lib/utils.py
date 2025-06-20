# core/lib/utils.py

"""
This module contains utility functions for the core library.
"""

import asyncio
from concurrent.futures import ProcessPoolExecutor
from functools import partial

_cpu_executor = ProcessPoolExecutor()


def cpu_bound(func):
    """Decorator for offloading CPU-bound handlers to processes"""

    async def wrapper(*args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_cpu_executor, partial(func, *args, **kwargs))

    return wrapper
