from psycopg2 import extras, DatabaseError
import requests
import json
import os
import logging
from database import query as q
from crawler import safe_get as s
from database.db_pool import get_connection, release_connection
from urllib.parse import quote


logger = logging.getLogger('main')


def get_commits(user, repo_name, tag_name):
    encoded_tag_name = quote(tag_name, safe='')
    url = f"https://api.github.com/repos/{user}/{repo_name}/commits?sha={encoded_tag_name}"
    response = s.safe_get(url)
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


from concurrent.futures import ThreadPoolExecutor, as_completed

def crawl_commits_for_release(release):
    release_id, tag_name, user, repo_name = release
    results = []
    json_entries = []
    try:
        commits = get_commits(user, repo_name, tag_name)
        for commit in commits:
            commit_hash = commit.get("sha")
            commit_msg = commit.get("commit", {}).get("message")

            if not commit_hash or not commit_msg:
                continue

            results.append((commit_hash, commit_msg, release_id))
            json_entries.append({
                "repo": f"{user}/{repo_name}",
                "release_tag_name": tag_name,
                "commit_hash": commit_hash,
                "commit_message": commit_msg
            })
    except requests.exceptions.RequestException as e:
        print(f'Lỗi khi lấy commit cho {user}/{repo_name} tag {tag_name}: {e}')
        logger.error("Lỗi trong crawl_commits_for_release: %s", e, exc_info=True)
    return results, json_entries


def get_all_commits():
    conn = get_connection()
    try:
        cur = conn.cursor()
        releases = q.get_all_tag_names(conn, cur)
        print(f"Found {len(releases)} releases with tag names.")
        CHUNK_SIZE = 1000
        BATCH_SIZE = 1000
        MAX_THREADS = 10

        os.makedirs("output", exist_ok=True)
        json_path = "output/commits_output.json"

        with open(json_path, "w", encoding="utf-8") as f_json:
            f_json.write("[\n")
            is_first_json = True

            for releases_chunk in chunked_iterable(releases, CHUNK_SIZE):
                commit_records = []
                json_chunk = []

                with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
                    futures = [executor.submit(crawl_commits_for_release, release) for release in releases_chunk]
                    for future in as_completed(futures):
                        commit_data, json_data = future.result()
                        commit_records.extend(commit_data)
                        json_chunk.extend(json_data)

                        # Ghi theo batch để không dồn quá nhiều
                        if len(commit_records) >= BATCH_SIZE:
                            save_commits_chunk_to_db(cur, commit_records)
                            append_json_chunk(f_json, json_chunk, is_first_json)
                            if is_first_json:
                                is_first_json = False

                            commit_records.clear()
                            json_chunk.clear()

                # Ghi nốt phần còn lại
                if commit_records:
                    save_commits_chunk_to_db(cur, commit_records)
                if json_chunk:
                    append_json_chunk(f_json, json_chunk, is_first_json)
                    is_first_json = False

            f_json.write("\n]")

        q.save_change(conn)
        print(f"Đã lưu commit vào database và file '{json_path}'")

    finally:
        cur.close()
        release_connection(conn)


# def get_all_commits():
#     # Kết nối tới PostgreSQL
#     conn = get_connection()
#     try:
#         cur = conn.cursor()
#         releases = q.get_all_tag_names(conn, cur)
#         print(f"Found {len(releases)} releases with tag names.")
#         CHUNK_SIZE = 1000
#         BATCH_SIZE = 1000
#         os.makedirs("output", exist_ok=True)
#         json_path = "output/commits_output.json"

#         with open(json_path, "w", encoding="utf-8") as f_json:
#             f_json.write("[\n")
#             is_first_json = True
#             for releases_chunk in chunked_iterable(releases, CHUNK_SIZE):
#                 commit_records = []
#                 json_chunk = []

#                 for idx, (release_id, tag_name, user, repo_name) in enumerate(releases_chunk):
#                    # print(f"[{idx+1}/{len(releases)}] Getting commits for {user}/{repo_name} - Tag: {tag_name}")
#                     if (user == 'andreafabrizi' and repo_name == 'Dropbox-Uploader') or (user == 'freeCodeCamp' and repo_name == 'freeCodeCamp'):
#                         try: 
#                             commits = get_commits(user, repo_name, tag_name)
#                         except requests.exceptions.RequestException as e:
#                             print(f'Lỗi khi lấy commit cho {user}/{repo_name} tag {tag_name}: {e}')
#                             logger.error("Lỗi trong get_commits khi lấy thông tin commit của release: %s", e, exc_info=True)

#                         for commit in commits:
#                             commit_hash = commit.get("sha")
#                             commit_msg = commit.get("commit", {}).get("message")

#                             if not commit_hash or not commit_msg:
#                                 continue

#                             commit_records.append((commit_hash, commit_msg, release_id))
#                             json_data = {
#                                 "repo": f"{user}/{repo_name}",
#                                 "release_tag_name": tag_name,
#                                 "commit_hash": commit_hash,
#                                 "commit_message": commit_msg
#                             }
#                             json_chunk.append(json_data)
#                             if len(commit_records) >= BATCH_SIZE:
#                                 save_commits_chunk_to_db(cur, commit_records)
#                                 append_json_chunk(f_json, json_chunk, is_first_json)
#                                 is_first_json = False
#                                 json_chunk.clear()
#                 # Ghi nốt nếu còn dữ liệu
#                 if commit_records:
#                     save_commits_chunk_to_db(cur, commit_records)
#                 if json_chunk:
#                     append_json_chunk(f_json, json_chunk, is_first_json)

#             f_json.write("\n]")

#         q.save_change(conn)
#         print(f"Đã lưu commit vào database và file 'commits_output.json'")

#     finally:
#         cur.close()
#         release_connection(conn)
