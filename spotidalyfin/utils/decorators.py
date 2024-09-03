import random
import time


def rate_limit(func):
    def wrapper(*args, **kwargs):
        retry_count = 0
        while True:
            try:
                return func(*args, **kwargs)
            except RuntimeError as e:
                if "429" in str(e):
                    if retry_count < 7:
                        retry_count += 1
                        time.sleep(1.5 ** retry_count + random.uniform(0.1, 0.4))
                    else:
                        raise RuntimeError("Rate limit exceeded") from e
                else:
                    raise e

    return wrapper
