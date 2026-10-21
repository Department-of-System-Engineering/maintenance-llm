import logging
from functools import wraps
import time
from typing import Callable, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


def log_exceptions(func: Callable[..., T]) -> Callable[..., T]:
    @wraps(func)
    def wrapper(*args, **kwargs) -> T:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Exception in {func.__name__}: {e}")
            raise

    return wrapper


def log_step(step_name: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            logger.info(f"Executing {step_name}")
            start = time.perf_counter()
            result: T = func(*args, **kwargs)
            end = time.perf_counter()
            duration = end - start
            logger.info(f"{step_name} successfully executed in {duration:.3f} seconds")
            return result

        return wrapper

    return decorator
