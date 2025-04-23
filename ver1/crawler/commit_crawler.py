from psycopg2 import extras, DatabaseError
import requests
import json
import os
import backoff
import logging
from database import query as q
from crawler import safe_get as s
from database.db_pool import get_connection, release_connection

logger = logging.getLogger('main')

# token của bạn
GITHUB_TOKEN = ""  

HEADERS = {
    "Accept": "application/vnd.github+json",
    ## fix add user-agent
    "User-Agent": "MyGitHubCrawler/1.0",
    "Authorization": f"token {GITHUB_TOKEN}" if GITHUB_TOKEN else ""
}


@backoff.on_exception(
    backoff.expo,
    (requests.exceptions.RequestException,),
    max_tries=5,
    jitter=backoff.full_jitter
)
def get_commits(user, repo_name, tag_name):
    url = f"https://api.github.com/repos/{user}/{repo_name}/commits?sha={tag_name}"
    response = s.safe_get(url, headers=HEADERS)
    return response.json()

def chunked_iterable(iterable, size):
    for i in range(0, len(iterable), size):
        yield iterable[i:i + size]

def save_commits_chunk_to_db(cur, commit_records):
    try:
        extras.execute_batch(
            cur,
            "INSERT INTO commit (hash, message, releaseID) VALUES (%s, %s, %s)",
            commit_records
        )
        commit_records.clear()
        print("đã lưu thành công batch commit vào db")
    except DatabaseError as e:
        print(f"Database error occurred: {e}")
        logger.error("Database error in save_commits_chunk_to_db: %s", e, exc_info=True)
        cur.connection.rollback()

def append_json_chunk(f, data_chunk, is_first):
    try:
        if not is_first:
            f.write(',\n')
        json.dump(data_chunk, f, indent=4, ensure_ascii=False)
        print("đã lưu chunk commit vào json")
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error writing to JSON file: {e}")
        logger.error("Error in append_json_chunk: %s", e, exc_info=True)


def get_all_commits():
    # Kết nối tới PostgreSQL
    conn = get_connection()
    try:
        cur = conn.cursor()
        releases = q.get_all_tag_names(conn, cur)
        print(f"Found {len(releases)} releases with tag names.")
        CHUNK_SIZE = 1000
        BATCH_SIZE = 1000
        os.makedirs("output", exist_ok=True)
        json_path = "output/commits_output.json"

        with open(json_path, "w", encoding="utf-8") as f_json:
            f_json.write("[\n")
            is_first_json = True
            for releases_chunk in chunked_iterable(releases, CHUNK_SIZE):
                commit_records = []
                json_chunk = []

                for idx, (release_id, tag_name, user, repo_name) in enumerate(releases_chunk):
                    print(f"[{idx+1}/{len(releases)}] Getting commits for {user}/{repo_name} - Tag: {tag_name}")

                    try: 
                        commits = get_commits(user, repo_name, tag_name)
                    except requests.exceptions.RequestException as e:
                        print(f'Lỗi khi lấy commit cho {user}/{repo_name} tag {tag_name}: {e}')
                        logger.error("Lỗi trong get_commits khi lấy thông tin commit của release: %s", e, exc_info=True)

                    for commit in commits:
                        commit_hash = commit.get("sha")
                        commit_msg = commit.get("commit", {}).get("message")

                        if not commit_hash or not commit_msg:
                            continue

                        commit_records.append((commit_hash, commit_msg, release_id))
                        json_data = {
                            "repo": f"{user}/{repo_name}",
                            "release_tag_name": tag_name,
                            "commit_hash": commit_hash,
                            "commit_message": commit_msg
                        }
                        json_chunk.append(json_data)
                        if len(commit_records) >= BATCH_SIZE:
                            save_commits_chunk_to_db(cur, commit_records)
                            append_json_chunk(f_json, json_chunk, is_first_json)
                            is_first_json = False
                            json_chunk.clear()
                # Ghi nốt nếu còn dữ liệu
                if commit_records:
                    save_commits_chunk_to_db(cur, commit_records)
                if json_chunk:
                    append_json_chunk(f_json, json_chunk, is_first_json)

            f_json.write("\n]")

        q.save_change(conn)
        print(f"Đã lưu commit vào database và file 'commits_output.json'")

    finally:
        cur.close()
        release_connection(conn)
