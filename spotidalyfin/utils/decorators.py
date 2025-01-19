import random
import time

from requests import ReadTimeout
from spotipy import SpotifyException
from tidalapi.exceptions import TooManyRequests

from spotidalyfin.utils.logger import log


def rate_limit(func):
    def wrapper(*args, **kwargs):
        retry_count = 0
        while True:
            try:
                return func(*args, **kwargs)
            except TooManyRequests or ReadTimeout or SpotifyException as e:
                log.warning(f"Rate limit exceeded, retrying in a few seconds")
                if retry_count < 7:
                    retry_count += 1
                    time.sleep(2 ** retry_count + random.uniform(0.2, 0.6))
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
