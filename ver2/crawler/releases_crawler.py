import requests
from psycopg2 import extras, DatabaseError
import json
import logging
from database import query as q
import os
from crawler import safe_get as s
from database.db_pool import get_connection, release_connection

logger = logging.getLogger('main')


conn = get_connection()


def get_releases(owner, repo_name):
    url = f"https://api.github.com/repos/{owner}/{repo_name}/releases"
    res = s.safe_get(url)
    return res.json()

def get_tags(owner, repo_name):
    url = f"https://api.github.com/repos/{owner}/{repo_name}/tags"
    res = s.safe_get(url)
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

# def crawl_releases():
#     try:
#         cur = conn.cursor()
#         repos = q.get_all_repos(conn, cur)
#         CHUNK_SIZE = 1000
#         BATCH_SIZE = 1000
#         os.makedirs("output", exist_ok=True)
#         json_path = "output/releases_output.json"

#         with open(json_path, "w", encoding="utf-8") as f_json:
#             f_json.write("[\n")
#             is_first_json = True

#             for repo_chunk in chunked_iterable(repos, CHUNK_SIZE):
#                 release_records = []
#                 json_chunk = []
#                 for idx, (repo_id, user, name) in enumerate(repo_chunk):
#                     #print(f"[{idx+1}/{len(repo_chunk)}] {user}/{name}")
#                     if (user == 'andreafabrizi' and name == 'Dropbox-Uploader') or (user == 'freeCodeCamp' and name == 'freeCodeCamp'):
#                         try:
#                             releases = get_releases(user, name)
#                         except requests.exceptions.RequestException as e:
#                             print(f"Lỗi khi lấy release cho {user}/{name}: {e}")
#                             logger.error("Lỗi khi lấy thông tin release: %s", e, exc_info=True)
#                         print(releases)
                        
#                         if releases != []:
#                             for rel in releases:
#                                 content = rel.get("body") or ""
#                                 release_name = rel.get("name") or rel.get("tag_name")
#                                 release_tag_name = rel.get("tag_name")
#                                 published_at = rel.get("published_at")

#                                 print(release_tag_name)
#                                 release_records.append((release_name, release_tag_name, content.strip(), repo_id))

#                                 # Ghi từng bản ghi vào JSON file
#                                 json_data = {
#                                     "repo": f"{user}/{name}",
#                                     "release_name": release_name,
#                                     "release_tag_name": release_tag_name,
#                                     "body": content.strip(),
#                                     "published_at": published_at
#                                 }
#                                 json_chunk.append(json_data)
#                                 if is_first_json:
#                                     is_first_json = False

#                                 if len(release_records) >= BATCH_SIZE:
#                                     save_releases_chunk_to_db(cur, release_records)
#                                     append_json_chunk(f_json, json_chunk, is_first_json)
#                                     is_first_json = False
#                                     json_chunk.clear()
                            
#                         else:
#                             tags = get_tags(user, name)
#                             if not tags:
#                                 logger.info(f"{user}/{name} không có release và tag")
#                                 release_records.append(("", "", "", repo_id))
#                                 json_data = {
#                                     "repo": f"{user}/{name}",
#                                     "release_name": "",
#                                     "release_tag_name": "",
#                                     "body": "",
#                                     "published_at": None
#                                 }
#                                 json_chunk.append(json_data)
#                                 continue

#                             for tag in tags:
#                                 tag_name = tag.get("name")
#                                 print(tag_name)

#                                 if not tag_name:
#                                     continue

#                                 release_records.append(("", tag_name, "", repo_id))
#                                 json_data = {
#                                     "repo": f"{user}/{name}",
#                                     "release_name": "",
#                                     "release_tag_name": tag_name,
#                                     "body": "",
#                                     "published_at": None
#                                 }
#                                 json_chunk.append(json_data)
#                                 if len(release_records) >= BATCH_SIZE:
#                                     save_releases_chunk_to_db(cur, release_records)
#                                     append_json_chunk(f_json, json_chunk, is_first_json)
#                                     is_first_json = False
#                                     json_chunk.clear()


#                 # Ghi nốt nếu còn dữ liệu
#                 if release_records:
#                     save_releases_chunk_to_db(cur, release_records)
#                 if json_chunk:
#                     append_json_chunk(f_json, json_chunk, is_first_json)

#             f_json.write("\n]")

#         q.save_change(conn)
#         print("Đã lưu vào database và releases_output.json theo từng phần thành công.")

#     finally:
#         cur.close()
#         release_connection(conn)




from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

lock = threading.Lock()

def process_repo(repo_tuple, conn):
    repo_id, user, name = repo_tuple
    release_records = []
    json_chunk = []

    try:
        releases = get_releases(user, name)
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
        tags = get_tags(user, name)
        if not tags:
            logger.info(f"{user}/{name} không có release và tag")
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
    
    return release_records, json_chunk


def crawl_releases_multithreaded():
    try:
        cur = conn.cursor()
        repos = q.get_all_repos(conn, cur)

        CHUNK_SIZE = 1000
        BATCH_SIZE = 1000
        MAX_THREADS = 10

        os.makedirs("output", exist_ok=True)
        json_path = "output/releases_output.json"

        with open(json_path, "w", encoding="utf-8") as f_json:
            f_json.write("[\n")
            is_first_json = True

            for repo_chunk in chunked_iterable(repos, CHUNK_SIZE):
                release_records = []
                json_chunk = []

                with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
                    futures = [executor.submit(process_repo, repo, conn) for repo in repo_chunk]
                    
                    for future in as_completed(futures):
                        release_data, json_data = future.result()
                        release_records.extend(release_data)
                        json_chunk.extend(json_data)

                        # Lưu từng batch nếu đã đủ BATCH_SIZE
                        if len(release_records) >= BATCH_SIZE:
                            save_releases_chunk_to_db(cur, release_records)
                            append_json_chunk(f_json, json_chunk, is_first_json)
                            if is_first_json:
                                is_first_json = False
                            release_records.clear()
                            json_chunk.clear()

                # Lưu phần còn lại sau khi duyệt xong chunk
                if release_records:
                    save_releases_chunk_to_db(cur, release_records)
                if json_chunk:
                    append_json_chunk(f_json, json_chunk, is_first_json)
                    if is_first_json:
                        is_first_json = False

            f_json.write("\n]")

        q.save_change(conn)
        print("Đã lưu vào database và releases_output.json thành công.")

    finally:
        cur.close()
        release_connection(conn)




# from concurrent.futures import ThreadPoolExecutor, as_completed

# def process_repo(repo_id, user, name):
#     release_records = []
#     json_chunk = []

#     try:
#         releases = get_releases(user, name)
#     except requests.exceptions.RequestException as e:
#         logger.error(f"Lỗi khi lấy release cho {user}/{name}: {e}")
#         return release_records, json_chunk  # Trả về rỗng nếu lỗi

#     if releases:
#         for rel in releases:
#             content = rel.get("body") or ""
#             release_name = rel.get("name") or rel.get("tag_name")
#             release_tag_name = rel.get("tag_name")
#             published_at = rel.get("published_at")
#             print(release_tag_name)
#             release_records.append((release_name, release_tag_name, content.strip(), repo_id))
#             json_chunk.append({
#                 "repo": f"{user}/{name}",
#                 "release_name": release_name,
#                 "release_tag_name": release_tag_name,
#                 "body": content.strip(),
#                 "published_at": published_at
#             })
#     else:
#         tags = get_tags(user, name)
#         if not tags:
#             release_records.append(("", "", "", repo_id))
#             json_chunk.append({
#                 "repo": f"{user}/{name}",
#                 "release_name": "",
#                 "release_tag_name": "",
#                 "body": "",
#                 "published_at": None
#             })
#         else:
#             for tag in tags:
#                 tag_name = tag.get("name")
#                 if not tag_name:
#                     continue
#                 print(tag_name)
#                 release_records.append(("", tag_name, "", repo_id))
#                 json_chunk.append({
#                     "repo": f"{user}/{name}",
#                     "release_name": "",
#                     "release_tag_name": tag_name,
#                     "body": "",
#                     "published_at": None
#                 })

#     return release_records, json_chunk

# def crawl_releases():
#     try:
#         cur = conn.cursor()
#         repos = q.get_all_repos(conn, cur)
#         BATCH_SIZE = 1000
#         CHUNK_SIZE = 1000
#         os.makedirs("output", exist_ok=True)
#         json_path = "output/releases_output.json"
#         print(len(repos))
#         with open(json_path, "w", encoding="utf-8") as f_json:
#             f_json.write("[\n")
#             is_first_json = True
#             for repo_chunk 
#             with ThreadPoolExecutor(max_workers=8) as executor:
#                 futures = {
#                     executor.submit(process_repo, repo_id, user, name): (repo_id, user, name)
#                     for (repo_id, user, name) in repos
#                     #if (user, name) in [("andreafabrizi", "Dropbox-Uploader"), ("freeCodeCamp", "freeCodeCamp")]
#                 }

#                 release_records = []
#                 json_chunk = []

#                 for future in as_completed(futures):
#                     try:
#                         repo_releases, repo_json = future.result()
#                         release_records.extend(repo_releases)
#                         json_chunk.extend(repo_json)

#                         if len(release_records) >= BATCH_SIZE:
#                             save_releases_chunk_to_db(cur, release_records)
#                             append_json_chunk(f_json, json_chunk, is_first_json)
#                             is_first_json = False
#                             release_records.clear()
#                             json_chunk.clear()

#                     except Exception as e:
#                         repo_id, user, name = futures[future]
#                         logger.error(f"Lỗi khi xử lý repo {user}/{name}: {e}", exc_info=True)

#                 # Ghi phần còn lại
#                 if release_records:
#                     save_releases_chunk_to_db(cur, release_records)
#                 if json_chunk:
#                     append_json_chunk(f_json, json_chunk, is_first_json)

#             f_json.write("\n]")

#         q.save_change(conn)
#         print("Đã lưu vào database và releases_output.json song song thành công.")

#     finally:
#         cur.close()
#         release_connection(conn)
