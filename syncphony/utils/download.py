import random
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial

import requests

from syncphony.utils.logger import syncphony_logger


def download_chunk(url, timeout=30, retries=5, backoff=1.5, logger=syncphony_logger):
    for attempt in range(retries):
        try:
            r = requests.get(url, stream=True, timeout=timeout)
            r.raise_for_status()
            return r.content
        except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
            if attempt == retries - 1:
                raise  # re-raise after last attempt
            sleep = backoff ** attempt + random.random()
            syncphony_logger.debug(f"Retry {attempt + 1}/{retries} for {url} in {sleep:.1f}s due to {e}")
            time.sleep(sleep)

    return None


def download_all_ordered(download_urls, max_workers=8, logger=syncphony_logger):
    download_fn = partial(download_chunk, logger=logger)
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        parts = list(ex.map(download_fn, download_urls))
    return bytearray(b"".join(parts))
