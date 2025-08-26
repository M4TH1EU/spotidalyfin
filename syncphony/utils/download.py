import random
import time
from concurrent.futures import ThreadPoolExecutor

import requests

from syncphony.utils.logger import log


def download_chunk(url, timeout=30, retries=5, backoff=1.5):
    for attempt in range(retries):
        try:
            r = requests.get(url, stream=True, timeout=timeout)
            r.raise_for_status()
            return r.content
        except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
            if attempt == retries - 1:
                raise  # re-raise after last attempt
            sleep = backoff ** attempt + random.random()
            log.debug(f"Retry {attempt + 1}/{retries} for {url} in {sleep:.1f}s due to {e}")
            time.sleep(sleep)

    return None


def download_all_ordered(download_urls, max_workers=8):
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        parts = list(ex.map(download_chunk, download_urls))
    return bytearray(b"".join(parts))
