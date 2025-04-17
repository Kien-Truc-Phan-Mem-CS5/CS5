import requests
from bs4 import BeautifulSoup
import json
import time

# URL Gitstar Ranking
BASE_URL = "https://gitstar-ranking.com/repositories?page={}"

# Header để tránh bị chặn
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
}

def get_top_repos(max_repos=5000):
    repos = []
    page = 1

    while len(repos) < max_repos:
        url = BASE_URL.format(page)
        print(f"Crawling page {page}...")

        response = requests.get(url, headers=HEADERS)
        #response = requests.get(url)
        if response.status_code != 200:
            print(f" Không thể truy cập {url}, dừng crawl!")
            break

        soup = BeautifulSoup(response.text, "html.parser")

        # Lấy danh sách repository
        repo_items = soup.select(".list-group-item.paginated_item")
        if not repo_items:
            print(" Không tìm thấy repo nào, có thể đã đến trang cuối!")
            break

        for repo_item in repo_items:
            # Lấy đường dẫn href để đảm bảo lấy đúng user/repo
            repo_link = repo_item.get("href")
            if not repo_link or not repo_link.startswith("/"):
                continue  # Bỏ qua nếu không có đường dẫn hợp lệ

            repo_user, repo_name = repo_link.strip("/").split("/", 1)

            # Lấy số sao
            repo_stars_elem = repo_item.select_one(".stargazers_count")
            repo_stars = repo_stars_elem.text.strip().replace(",", "") if repo_stars_elem else "0"

            repos.append({
                "user": repo_user,
                "name": repo_name,
                "stars": int(repo_stars)
            })

            print(f" Added {repo_name} by {repo_user} and {repo_stars} stars")

            # Dừng nếu đủ repo
            if len(repos) >= max_repos:
                break

        # Chuyển trang
        page += 1
        time.sleep(2)  # Tránh bị chặn

    return repos

if __name__ == "__main__":
    # Crawl 5000 repositories
    repos = get_top_repos(5000)

    # Lưu vào file JSON
    with open("gitstar_repos.json", "w", encoding="utf-8") as f:
        json.dump(repos, f, indent=4, ensure_ascii=False)

    print(f" Đã lưu {len(repos)} repositories vào gitstar_repos.json!")
