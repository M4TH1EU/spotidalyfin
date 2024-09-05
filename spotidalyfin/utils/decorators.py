import datetime
import random
import time
from pathlib import Path

from cachier import cachier
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
                    time.sleep(1.5 ** retry_count + random.uniform(0.1, 0.4))
                else:
                    raise RuntimeError("Rate limit exceeded") from e
            except Exception as e:
                raise e

    return wrapper


def cache_2days(func):
    return cachier(stale_after=datetime.timedelta(days=2), cache_dir=cache_dir)(func)


def cache_2weeks(func):
    return cachier(stale_after=datetime.timedelta(weeks=2), cache_dir=cache_dir)(func)


def cache_2months(func):
    return cachier(stale_after=datetime.timedelta(weeks=8), cache_dir=cache_dir)(func)
