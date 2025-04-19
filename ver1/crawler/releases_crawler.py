import requests
from psycopg2 import extras, DatabaseError
import json
import backoff
import logging
from database import query as q
import os
from crawler import safe_get as s
from database.db_pool import get_connection, release_connection

logger = logging.getLogger('main')

GITHUB_TOKEN = ""
HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "MyGitHubCrawler/1.0",
    "Authorization": f"token {GITHUB_TOKEN}" if GITHUB_TOKEN else ""
}

conn = get_connection()

@backoff.on_exception(
    backoff.expo,
    requests.exceptions.RequestException, 
    max_tries=5,
    jitter=backoff.full_jitter
)
def get_releases(owner, repo_name):
    url = f"https://api.github.com/repos/{owner}/{repo_name}/releases"
    res = s.safe_get(url, headers=HEADERS)
    return res.json()


def chunked_iterable(iterable, size):
    for i in range(0, len(iterable), size):
        yield iterable[i:i + size]

def save_releases_chunk_to_db(cur, release_records):
    try:
        extras.execute_batch(
            cur,
            "INSERT INTO release (release_name, release_tag_name, content, repoID) VALUES (%s, %s, %s, %s)",
            release_records
        )
        release_records.clear()
        print("đã lưu thành công batch releases vào db")
    except DatabaseError as e:
        print(f"Database error occurred: {e}")
        logger.error("Database error in save_releases_chunk_to_db: %s", e, exc_info=True)
        cur.connection.rollback()

def append_json_chunk(f, data_chunk, is_first):
    try:
        if not is_first:
            f.write(',\n')
        json.dump(data_chunk, f, indent=4, ensure_ascii=False)
        print("đã lưu chunk releases vào json")
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error writing to JSON file: {e}")
        logger.error("Error in append_json_chunk: %s", e, exc_info=True)

def crawl_releases():
    try:
        cur = conn.cursor()
        repos = q.get_all_repos(conn, cur)

        CHUNK_SIZE = 1000
        BATCH_SIZE = 1000
        os.makedirs("output", exist_ok=True)
        json_path = "output/releases_output.json"

        with open(json_path, "w", encoding="utf-8") as f_json:
            f_json.write("[\n")
            is_first_json = True

            for repo_chunk in chunked_iterable(repos, CHUNK_SIZE):
                release_records = []
                json_chunk = []
                for idx, (repo_id, user, name) in enumerate(repo_chunk):
                    print(f"[{idx+1}/{len(repo_chunk)}] {user}/{name}")
                    try:
                        releases = get_releases(user, name)
                    except requests.exceptions.RequestException as e:
                        print(f"Lỗi khi lấy release cho {user}/{name}: {e}")
                        logger.error("Lỗi khi lấy thông tin release: %s", e, exc_info=True)
                        continue

                    for rel in releases:
                        content = rel.get("body") or ""
                        release_name = rel.get("name") or rel.get("tag_name")
                        release_tag_name = rel.get("tag_name")
                        published_at = rel.get("published_at")

                        print(release_tag_name)
                        release_records.append((release_name, release_tag_name, content.strip(), repo_id))

                        # Ghi từng bản ghi vào JSON file
                        json_data = {
                            "repo": f"{user}/{name}",
                            "release_name": release_name,
                            "release_tag_name": release_tag_name,
                            "body": content.strip(),
                            "published_at": published_at
                        }
                        json_chunk.append(json_data)
                        if is_first_json:
                            is_first_json = False

                        if len(release_records) >= BATCH_SIZE:
                            save_releases_chunk_to_db(cur, release_records)
                            append_json_chunk(f_json, json_chunk, is_first_json)
                            is_first_json = False
                            json_chunk.clear()

                # Ghi nốt nếu còn dữ liệu
                if release_records:
                    save_releases_chunk_to_db(cur, release_records)
                if json_chunk:
                    append_json_chunk(f_json, json_chunk, is_first_json)

            f_json.write("\n]")

        q.save_change(conn)
        print("Đã lưu vào database và releases_output.json theo từng phần thành công.")

    finally:
        cur.close()
        release_connection(conn)
