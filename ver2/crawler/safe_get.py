import requests
import time
import logging
import backoff
from fake_useragent import UserAgent

logger = logging.getLogger('main')
session = requests.Session()
ua = UserAgent()

# GitHub Token
GITHUB_TOKEN = ""

# Header mặc định
session.headers.update({
    "Accept": "application/vnd.github+json",
    "Authorization": f"token {GITHUB_TOKEN}" if GITHUB_TOKEN else ""
})


@backoff.on_exception(
    backoff.expo,
    requests.exceptions.RequestException,
    max_tries=5,
    jitter=backoff.full_jitter
)
def safe_get(url, timeout=10):
    try:
        # Random user-agent mỗi request
        session.headers.update({
            "User-Agent": ua.random
        })

        response = session.get(url, timeout=timeout)

        # Xử lý rate limit
        if response.status_code in [403, 429] or response.headers.get("X-RateLimit-Remaining") == "0":
            reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 60))
            wait_time = max(reset_time - int(time.time()), 1)
            logger.warning(f"[Rate Limit] Đợi {wait_time} giây để reset...")
            time.sleep(wait_time)
            raise requests.exceptions.RequestException("Retrying due to rate limit.")

        response.raise_for_status()
        return response

    except requests.exceptions.RequestException as e:
        logger.error(f"[Request Failed] {url} -> {e}")
        raise
