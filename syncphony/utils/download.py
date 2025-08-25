from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import requests, time, random

from syncphony.utils.logger import log


#
# def download_chunk(url):
#     response = requests.get(url, stream=True, timeout=30)
#     response.raise_for_status()
#     return response.content
#
#
# def download_all(download_urls, max_workers=8):
#     audio_bytes = bytearray()
#     with ThreadPoolExecutor(max_workers=max_workers) as executor:
#         # submit all download tasks
#         future_to_url = {executor.submit(download_chunk, url): url for url in download_urls}
#         for future in as_completed(future_to_url):
#             audio_bytes.extend(future.result())
#     return audio_bytes


def download_chunk(url, timeout=30, retries=5, backoff=1.5):
    for attempt in range(retries):
        try:
            r = requests.get(url, stream=True, timeout=timeout)
            r.raise_for_status()
            return r.content
        except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
            if attempt == retries - 1:
                raise   # re-raise after last attempt
            sleep = backoff ** attempt + random.random()
            log.debug(f"Retry {attempt+1}/{retries} for {url} in {sleep:.1f}s due to {e}")
            time.sleep(sleep)

def download_all_ordered(download_urls, max_workers=8):
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        parts = list(ex.map(download_chunk, download_urls))
    return bytearray(b"".join(parts))