import asyncio
import functools
from typing import Callable, Type, Tuple
from utils.logger import get_logger

log = get_logger("retry")


def with_retry(max_retries: int = 3, delay: float = 2.0, exceptions: Tuple[Type[Exception], ...] = (Exception,)):
    """
    Async retry decorator with exponential backoff.
    Usage:
        @with_retry(max_retries=3, delay=2.0)
        async def my_function(...):
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries - 1:
                        log.error(f"{func.__name__} failed after {max_retries} attempts: {e}")
                        raise
                    wait = delay * (2 ** attempt)
                    log.warning(f"{func.__name__} attempt {attempt + 1}/{max_retries} failed: {e}. Retrying in {wait}s...")
                    await asyncio.sleep(wait)
        return wrapper
    return decorator
