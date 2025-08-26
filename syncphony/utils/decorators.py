import random
import time
from typing import Callable

from requests import ReadTimeout
from spotipy import SpotifyException
from tidalapi.exceptions import TooManyRequests

from syncphony.utils.logger import log


def rate_limit(func: Callable = None, *, returns=None, raise_on_failure=False):
    """
    Decorator that retries a function if TooManyRequests, ReadTimeout, or SpotifyException occur.
    Works both with and without parentheses:
        @rate_limit
        @rate_limit(returns=[])
    """

    def decorator(inner_func):
        def wrapper(*args, **kwargs):
            retry_count = 0
            while True:
                try:
                    return inner_func(*args, **kwargs)
                except (TooManyRequests, ReadTimeout, SpotifyException) as e:
                    log.warning("Rate limit exceeded, retrying in a few seconds")
                    if retry_count < 7:
                        retry_count += 1
                        time.sleep(2 ** retry_count + random.uniform(0.2, 0.6))
                    else:
                        log.warning("Rate limit exceeded, max retries reached")
                        if raise_on_failure:
                            raise e
                        return returns
                except Exception as e:
                    raise e

        return wrapper

    # If called as @rate_limit without parentheses → func is the function
    if func is not None and callable(func):
        return decorator(func)

    # If called as @rate_limit(...) → return the real decorator
    return decorator


def debug_time(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"{func.__name__} took {end - start} seconds")
        return result

    return wrapper
