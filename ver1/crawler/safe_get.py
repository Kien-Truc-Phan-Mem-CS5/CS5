import requests
import time
import logging


logger = logging.getLogger('main')

def safe_get(url, headers=None, max_retries=5):
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 429:
                reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 60))
                wait_time = max(reset_time - int(time.time()), 1)
                logger.warning(f"Rate limit reached. Waiting for {wait_time} seconds.")
                time.sleep(wait_time)
                continue

            remaining = int(response.headers.get('X-RateLimit-Remaining', 1))
            if remaining == 0:
                reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 60))
                wait_time = max(reset_time - int(time.time()), 1)
                logger.info(f"Remaining requests: 0. Waiting for {wait_time} seconds.")
                time.sleep(wait_time)

            response.raise_for_status()  # Sẽ raise nếu status code là 4xx hoặc 5xx
            return response

        except requests.exceptions.RequestException as e:
            logger.error(f"Request attempt {attempt+1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                raise  # Để backoff xử lý nếu retry đủ số lần

