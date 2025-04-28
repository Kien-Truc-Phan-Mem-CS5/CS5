import requests
import time
import logging
import backoff
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Cấu hình logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('main')

# Danh sách User-Agent
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:45.0) Gecko/20100101 Firefox/45.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.80 Safari/537.36"
]

# Token GitHub
GITHUB_TOKENS = [

]

# Tạo session
session = requests.Session()
adapter = HTTPAdapter(
    pool_connections=70,  # Total number of connection pools
    pool_maxsize=70,      # Connections per host
    max_retries=Retry(
        total=5,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504]
    )
)
session.mount('https://', adapter)
session.mount('http://', adapter)
request_count = 0

# Danh sách token và thời điểm reset tương ứng
GITHUB_TOKEN_INFO = [{
    "token": token,
    "reset": 0,
    "count": 0
} for token in GITHUB_TOKENS]

current_token_index = 0

def get_random_user_agent():
    return random.choice(user_agents)

def check_rate_limit(token):
    url = "https://api.github.com/rate_limit"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        core_limit = data['resources']['core']
        remaining = core_limit['remaining']
        reset_time = core_limit['reset']

        # Chuyển thời gian reset từ timestamp thành giờ:phút
        reset_time_formatted = time.strftime('%H:%M:%S', time.gmtime(reset_time))

        return remaining, reset_time_formatted
    else:
        logger.error(f"Lỗi khi kiểm tra rate limit: {response.status_code}")
        return None, None

def get_next_token():
    global current_token_index

    # First try: find a token that hasn't reached 500 requests
    start_index = current_token_index
    for _ in range(len(GITHUB_TOKEN_INFO)):
        info = GITHUB_TOKEN_INFO[current_token_index]
        current_token_index = (current_token_index + 1) % len(GITHUB_TOKEN_INFO)

        # Check if this token has used fewer than 500 requests
        if info["count"] < 500:
            remaining, reset_time = check_rate_limit(info["token"])
            if remaining and remaining > 10:  # Still ensure it has quota
                logger.info(f"Token {info['token'][-4:]} has used {info['count']}/500 requests and has {remaining} quota remaining. Using this token.")
                return info["token"]

    # Second try: reset counts if all tokens have reached 500 requests
    if all(info["count"] >= 500 for info in GITHUB_TOKEN_INFO):
        logger.info("All tokens have reached 500 requests limit. Resetting counts.")
        for info in GITHUB_TOKEN_INFO:
            info["count"] = 0

    # Third try: get any token with remaining quota
    for info in GITHUB_TOKEN_INFO:
        remaining, reset_time = check_rate_limit(info["token"])
        if remaining and remaining > 20:
            current_token_index = GITHUB_TOKEN_INFO.index(info)
            logger.info(f"Using token {info['token'][-4:]} with {remaining} quota remaining.")
            return info["token"]

    # If no token has any quota left, wait for reset
    wait_for_next_reset()
    return get_next_token()  # Try again after waiting

def wait_for_next_reset():
    now = int(time.time())
    resets = [info["reset"] for info in GITHUB_TOKEN_INFO if info["reset"] > now]

    if resets:
        wait_time = min(resets) - now
        logger.error(f"Tất cả token đều hết quota. Phải chờ {wait_time} giây tới khi GitHub reset rate limit.")

        while wait_time > 0:
            mins, secs = divmod(wait_time, 60)
            print(f"Đang chờ reset quota... còn lại: {mins:02d}:{secs:02d}", end="\r")
            time.sleep(1)
            wait_time -= 1
        print("\nĐã hết thời gian chờ. Tiếp tục request.")
    else:
        logger.error("Không thể xác định thời điểm reset quota. Tạm chờ mặc định 60s.")
        for i in range(60, 0, -1):
            print(f" Đang chờ mặc định... còn lại: {i:02d}s", end="\r")
            time.sleep(1)
        print("\nĐã hết thời gian chờ. Tiếp tục request.")

@backoff.on_exception(
    backoff.expo,
    requests.exceptions.RequestException,
    max_tries=5,
    jitter=backoff.full_jitter
)
def safe_get(url, timeout=10):
    global request_count

    token = get_next_token()
    if token is None:
        logger.error("Không có token nào có quota còn lại. Đợi reset.")
        return None

    session.headers.update({
        "User-Agent": get_random_user_agent(),
        "Accept": "application/vnd.github+json",
        "Authorization": f"token {token}"
    })

    try:
        response = session.get(url, timeout=timeout)
        request_count += 1

        # Update request count for token
        for info in GITHUB_TOKEN_INFO:
            if info["token"] == token:
                info["count"] += 1

        # Kiểm tra status code
        if response.status_code != 200:
            logger.error(f"Lỗi HTTP {response.status_code} khi GET {url}")
            return None

        return response

    except requests.exceptions.RequestException as e:
        logger.error(f"[LỖI KẾT NỐI] {e}")
        return None

def print_token_usage():
    logger.info(f"Đã gửi tổng cộng {request_count} requests.")
    print("\n Thống kê số request đã gửi qua từng token:")
    for info in GITHUB_TOKEN_INFO:
        print(f" Token ...{info['token'][-4:]}: {info['count']} requests")
