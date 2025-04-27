import requests
from psycopg2 import extras, DatabaseError
import json
import logging
from database import query as q
import os
from crawler import safe_get as s
from database.db_pool import get_connection, release_connection
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


logger = logging.getLogger('main')


def get_releases(owner, repo_name):
    url = f"https://api.github.com/repos/{owner}/{repo_name}/releases"
    res = s.safe_get(url)
    try:
        data = res.json()
        if not isinstance(data, list):
            print(data)
            raise ValueError(f"Expected list, got {type(data)}: {data}")
        return data
    except Exception as e:
        logger.error("Error parsing JSON from releases: %s", e, exc_info=True)
        return []


def get_tags(owner, repo_name):
    url = f"https://api.github.com/repos/{owner}/{repo_name}/tags"
    res = s.safe_get(url)
    try:
        data = res.json()
        if not isinstance(data, list):
            print(data)
            raise ValueError(f"Expected list, got {type(data)}: {data}")
        return data
    except Exception as e:
        logger.error("Error parsing JSON from releases: %s", e, exc_info=True)
        return []


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
        for item in data_chunk:
            if not is_first:
                f.write(',\n')
            json.dump(item, f, indent=4, ensure_ascii=False)
            is_first = False
        print("đã lưu chunk releases vào json")
        return is_first  # Cập nhật lại trạng thái
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error writing to JSON file: {e}")
        logger.error("Error in append_json_chunk: %s", e, exc_info=True)
        return is_first
    
lock = threading.Lock()

def process_repo(repo_tuple):
    repo_id, user, name = repo_tuple
    release_records = []
    json_chunk = []
    conn = get_connection()
    try:
        try:
            releases = get_releases(user, name)
            # Kiểm tra dữ liệu API trả về có đúng dạng list[dict] không
            if not isinstance(releases, list):
                print(f"[ERROR] Unexpected format for releases in {user}/{name}: {releases}")
                logger.error("Unexpected format for releases: %s", releases)
                return [], []

        except requests.exceptions.RequestException as e:
            print(f"Lỗi khi lấy release cho {user}/{name}: {e}")
            logger.error("Lỗi khi lấy thông tin release: %s", e, exc_info=True)
            return [], []

        if releases:
            for rel in releases:
                content = rel.get("body") or ""
                release_name = rel.get("name") or rel.get("tag_name")
                release_tag_name = rel.get("tag_name")
                published_at = rel.get("published_at")

                release_records.append((release_name, release_tag_name, content.strip(), repo_id))
                json_data = {
                    "repo": f"{user}/{name}",
                    "release_name": release_name,
                    "release_tag_name": release_tag_name,
                    "body": content.strip(),
                    "published_at": published_at
                }
                json_chunk.append(json_data)
        else:
            try:
                tags = get_tags(user, name)
            except requests.exceptions.RequestException as e:
                print(f"Lỗi khi lấy tag cho {user}/{name}: {e}")
                logger.error("Lỗi khi lấy thông tin tag: %s", e, exc_info=True)
                return [], []
            if not tags:
                logger.info(f"{user}/{name} không có release và tag")
                logger.error(f"{user}/{name} không có release và tag")
                release_records.append(("", "", "", repo_id))
                json_chunk.append({
                    "repo": f"{user}/{name}",
                    "release_name": "",
                    "release_tag_name": "",
                    "body": "",
                    "published_at": None
                })
            else:
                for tag in tags:
                    tag_name = tag.get("name")
                    if not tag_name:
                        continue
                    release_records.append(("", tag_name, "", repo_id))
                    json_chunk.append({
                        "repo": f"{user}/{name}",
                        "release_name": "",
                        "release_tag_name": tag_name,
                        "body": "",
                        "published_at": None
                    })
    finally:
        release_connection(conn)
    
    return release_records, json_chunk


def crawl_releases():
    conn = get_connection()
    cur = None
    try:
        cur = conn.cursor()
        repos = q.get_all_repos(conn, cur)

        CHUNK_SIZE = 1000
        BATCH_SIZE = 1000
        MAX_THREADS = 8

        os.makedirs("output", exist_ok=True)
        json_path = "output/releases_output.json"

        with open(json_path, "w", encoding="utf-8") as f_json:
            f_json.write("[\n")
            is_first_json = True

            for repo_chunk in chunked_iterable(repos, CHUNK_SIZE):
                print("processing chunk repo....")
                release_records = []
                json_chunk = []

                with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
                    futures = [executor.submit(process_repo, repo) for repo in repo_chunk]
                    
                    for future in as_completed(futures):
                        release_data, json_data = future.result()
                        release_records.extend(release_data)
                        json_chunk.extend(json_data)

                        # Lưu từng batch nếu đã đủ BATCH_SIZE
                        if len(release_records) >= BATCH_SIZE:
                            save_releases_chunk_to_db(cur, release_records)
                            is_first_json = append_json_chunk(f_json, json_chunk, is_first_json)
                            release_records.clear()
                            json_chunk.clear()
                            s.print_token_usage()
                # Lưu phần còn lại sau khi duyệt xong chunk
                if release_records:
                    save_releases_chunk_to_db(cur, release_records)
                if json_chunk:
                    is_first_json = append_json_chunk(f_json, json_chunk, is_first_json)

            f_json.write("\n]")

        q.save_change(conn)
        print("Đã lưu vào database và releases_output.json thành công.")
    finally:
        if cur:
            cur.close()
        release_connection(conn)
