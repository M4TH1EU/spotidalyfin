import random
import time
from pathlib import Path

from tidalapi.exceptions import TooManyRequests

cache_dir = Path("~/.cache/spotidalyfin").expanduser()


def rate_limit(func):
    def wrapper(*args, **kwargs):
        retry_count = 0
        while True:
            try:
                return func(*args, **kwargs)
            except TooManyRequests as e:
                if retry_count < 7:
                    retry_count += 1
                    time.sleep(1.2 ** retry_count + random.uniform(0.1, 0.4))
                else:
                    raise RuntimeError("Rate limit exceeded") from e
            except Exception as e:
                raise e

    return wrapper


def debug_time(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"{func.__name__} took {end - start} seconds")
        return result

    return wrapper
