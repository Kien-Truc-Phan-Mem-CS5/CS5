import requests
from bs4 import BeautifulSoup
import json
import time
from database import query as q
import os
import logging
from crawler import safe_get as s
from database.db_pool import get_connection, release_connection
from psycopg2 import extras, DatabaseError


# Lấy logger đã được cấu hình từ module chính
logger = logging.getLogger('main')



# URL Gitstar Ranking
BASE_URL = "https://gitstar-ranking.com/repositories?page={}"


# def get_top_repos(max_repos=5000):
#     repos = []
#     page = 1

#     while len(repos) < max_repos:
#         url = BASE_URL.format(page)
#         print(f"Crawling page {page}...")

#         try:
#             response = s.safe_get(url, headers=HEADERS)
#             response.raise_for_status()
#         except requests.exceptions.RequestException as e:
#             print(f"Lỗi khi truy cập {url}: {e}")
#             logger.error("Lỗi trong get_top_repos khi truy cập url: %s", e, exc_info=True)
#             break

#         try:
#             soup = BeautifulSoup(response.text, "html.parser")
#             repo_items = soup.select(".list-group-item.paginated_item")
#         except Exception as e:
#             print(f"Lỗi khi phân tích HTML trang {page}: {e}")
#             logger.error("Lỗi trong get_top_repos khi phân tích HTML: %s", e, exc_info=True)
#             break

#         if not repo_items:
#             print("Không tìm thấy repo nào, có thể đã đến trang cuối!")
#             break

#         for repo_item in repo_items:
#             try:
#                 repo_link = repo_item.get("href")
#                 if not repo_link or not repo_link.startswith("/"):
#                     continue

#                 repo_user, repo_name = repo_link.strip("/").split("/", 1)

#                 repo_stars_elem = repo_item.select_one(".stargazers_count")
#                 repo_stars = repo_stars_elem.text.strip().replace(",", "") if repo_stars_elem else "0"

#                 repos.append({
#                     "user": repo_user,
#                     "name": repo_name,
#                     "stars": int(repo_stars)
#                 })

#                 print(f"Added {repo_name} by {repo_user} with {repo_stars} stars")

#                 if len(repos) >= max_repos:
#                     break
#             except Exception as e:
#                 print(f"Bỏ qua một repo do lỗi: {e}")
#                 logger.error("Lỗi trong get_top_repos bỏ qua repo lỗi: %s", e, exc_info=True)
#                 continue

#         page += 1
#         time.sleep(1)  # Đợi để tránh bị chặn

#     return repos


# def save_repo_to_db(repos):
#      # Kết nối PostgreSQL
#     conn = get_connection()
#     try:
#         cur = conn.cursor()
#         # Chèn dữ liệu vào bảng repo
#         for repo in repos:
#             user_name = repo["user"]
#             name = repo["name"]
#             q.insert_repo(conn, cur, user_name, name)
#         # Lưu thay đổi
#         q.save_change(conn)
#         print(f"Đã thêm {len(repos)} repositories vào database!")
#     finally:
#         cur.close()
#         release_connection(conn)


import psycopg2.extras
from psycopg2 import DatabaseError

def save_repo_to_db(repos, batch_size=100):
    print(len(repos))
    conn = get_connection()
    try:
        cur = conn.cursor()
        total_inserted = 0

        # Chia nhỏ repos thành các batch và insert từng batch
        for i in range(0, len(repos), batch_size):
            batch = repos[i:i + batch_size]
            records = [(repo["user"], repo["name"]) for repo in batch]
            print(len(records))
            try:
                extras.execute_batch(
                    cur,
                    """INSERT INTO repo ("user", name) VALUES (%s, %s)""",
                    records
                )
                total_inserted += len(records)
                records.clear()
                print("đã lưu thành công batch repo vào db")
            except DatabaseError as e:
                print(f"Database error occurred: {e}")
                logger.error("Database error in save_repo_to_db: %s", e, exc_info=True)
                cur.connection.rollback()

        # Commit các thay đổi vào DB
        q.save_change(conn)
        print(f"Đã thêm {total_inserted} repositories vào database!")
    finally:
        cur.close()
        release_connection(conn)



def save_repo_to_json(repos):
    os.makedirs("output", exist_ok=True)
    try:
        with open("output/gitstar_repos.json", "w", encoding="utf-8") as f:
            json.dump(repos, f, indent=4, ensure_ascii=False)

        print(f"Đã lưu {len(repos)} repositories vào gitstar_repos.json!")
    except Exception as e:
        print(f"Lỗi trong quá trình crawl tổng thể: {e}")
        logger.error("Lỗi trong save_repo_to_json: %s", e, exc_info=True)


# def get_repo():
#     repos = get_top_repos(5000)
#     # Lưu vào file json
#     save_repo_to_json(repos)
#     # Lưu vào database
#     save_repo_to_db(repos)




from concurrent.futures import ThreadPoolExecutor, as_completed

def crawl_page(page):
    url = BASE_URL.format(page)
    print(f"[Thread] Crawling page {page}...")

    try:
        response = s.safe_get(url)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Lỗi khi truy cập {url}: {e}")
        logger.error("Lỗi trong get_top_repos khi truy cập url: %s", e, exc_info=True)
        return

    try:
        soup = BeautifulSoup(response.text, "html.parser")
        repo_items = soup.select(".list-group-item.paginated_item")
    except Exception as e:
        print(f"Lỗi khi phân tích HTML trang {page}: {e}")
        logger.error("Lỗi trong get_top_repos khi phân tích HTML: %s", e, exc_info=True)
        return

    if not repo_items:
        print("Không tìm thấy repo nào, có thể đã đến trang cuối!")
        return

    page_repos = []
    for repo_item in repo_items:
        try:
            repo_link = repo_item.get("href")
            if not repo_link or not repo_link.startswith("/"):
                continue

            repo_user, repo_name = repo_link.strip("/").split("/", 1)

            repo_stars_elem = repo_item.select_one(".stargazers_count")
            repo_stars = repo_stars_elem.text.strip().replace(",", "") if repo_stars_elem else "0"

            page_repos.append({
                "user": repo_user,
                "name": repo_name,
                "stars": int(repo_stars)
            })

            print(f"Added {repo_name} by {repo_user} with {repo_stars} stars")

        except Exception as e:
            print(f"Bỏ qua một repo do lỗi: {e}")
            logger.error("Lỗi trong get_top_repos bỏ qua repo lỗi: %s", e, exc_info=True)
            continue
    return page_repos

def get_top_repos(max_repos=5000, max_workers=10):
    repos = []
    max_pages = (max_repos // 100) # mỗi trang có khoảng 10 repo

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(crawl_page, page) for page in range(1, max_pages + 1)]

        for future in as_completed(futures):
            result = future.result()
            repos.extend(result)
            print(f"[+] Đã crawl được {len(repos)} repo...")

            if len(repos) >= max_repos:
                break

    # Cắt đúng số lượng yêu cầu
    return repos[:max_repos]

def get_repo():
    repos = get_top_repos(5000, max_workers=50)
    save_repo_to_json(repos)
    save_repo_to_db(repos)
