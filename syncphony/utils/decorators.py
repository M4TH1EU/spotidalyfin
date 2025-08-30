import random
import threading
import time
from typing import Callable

from requests import ReadTimeout
from spotipy import SpotifyException
from tidalapi.exceptions import TooManyRequests

from syncphony.utils.logger import syncphony_logger


def rate_limit(func: Callable = None, *, returns=None, raise_on_failure=False, timeout: int = 30):
    """
    Decorator that retries a function if TooManyRequests, ReadTimeout, or SpotifyException occur.
    Also enforces a hard timeout (default: 30s) to prevent silent hangs.
    Works both with and without parentheses:
        @rate_limit
        @rate_limit(returns=[])
    """

    def run_with_timeout(inner_func, *args, **kwargs):
        """Run inner_func with a timeout using threading."""
        result = {}
        exc = {}

        def target():
            try:
                result["value"] = inner_func(*args, **kwargs)
            except Exception as e:
                exc["error"] = e

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join(timeout)

        if thread.is_alive():
            raise TimeoutError(f"Function '{inner_func.__name__}' timed out after {timeout}s")

        if "error" in exc:
            raise exc["error"]
        return result.get("value")

    def decorator(inner_func):
        def wrapper(*args, **kwargs):
            logger = syncphony_logger
            if args and hasattr(args[0], "__class__") and hasattr(args[0], "logger"):
                logger = getattr(args[0], "logger")

            retry_count = 0
            while True:
                try:
                    return run_with_timeout(inner_func, *args, **kwargs)
                except (TooManyRequests, ReadTimeout, SpotifyException) as e:
                    logger.warning("Rate limit or transient error, retrying...")
                    if retry_count < 7:
                        retry_count += 1
                        time.sleep(2 ** retry_count + random.uniform(0.2, 0.6))
                    else:
                        logger.warning("Max retries reached for rate-limited call")
                        if raise_on_failure:
                            raise e
                        return returns
                except TimeoutError as e:
                    logger.error(str(e))
                    if raise_on_failure:
                        raise e
                    return returns
                except Exception as e:
                    raise e

        return wrapper

    if func is not None and callable(func):
        return decorator(func)

    return decorator


def debug_time(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"{func.__name__} took {end - start} seconds")
        return result

    return wrapper
