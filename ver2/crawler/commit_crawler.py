from psycopg2 import extras, DatabaseError
import requests
import json
import os
import logging
from database import query as q
from crawler import safe_get as s
from database.db_pool import get_connection, release_connection
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed


logger = logging.getLogger('main')


def get_compare_commits(user, repo_name, base_tag, head_tag):
    """
    Get commits that changed between two tags using GitHub's compare API
    """
    encoded_base_tag = quote(base_tag, safe='')
    encoded_head_tag = quote(head_tag, safe='')
    url = f"https://api.github.com/repos/{user}/{repo_name}/compare/{encoded_base_tag}...{encoded_head_tag}"
    
    response = s.safe_get(url)
    if not response:
        logger.error(f"Failed to get comparison between {base_tag} and {head_tag} for {user}/{repo_name}")
        return []
    
    data = response.json()
    return data.get('commits', [])


def get_repo_releases(conn, cur, user, repo_name):
    """
    Get all releases for a repository sorted by release date
    """
    try:
        cur.execute("""
            SELECT r.id, r.release_tag_name
            FROM release r
            JOIN repo ON r.repoID = repo.id
            WHERE repo."user" = %s AND repo.name = %s AND r.release_tag_name IS NOT NULL
            ORDER BY r.id ASC
        """, (user, repo_name))
        return cur.fetchall()
    except DatabaseError as e:
        logger.error(f"Database error getting releases for {user}/{repo_name}: {e}")
        return []


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
        cur.connection.commit()
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


def crawl_commits_for_release_pair(user, repo_name, releases):
    results = []
    json_entries = []
    
    if not releases:
        return results, json_entries
    
    # For each pair of consecutive releases
    for i in range(1, len(releases)):
        prev_release_id, prev_tag = releases[i-1]
        curr_release_id, curr_tag = releases[i]
        
        try:
            commits = get_compare_commits(user, repo_name, prev_tag, curr_tag)
            for commit in commits:
                commit_hash = commit.get("sha")
                commit_msg = commit.get("commit", {}).get("message")

                if not commit_hash or not commit_msg:
                    continue

                results.append((commit_hash, commit_msg, curr_release_id))
                json_entries.append({
                    "repo": f"{user}/{repo_name}",
                    "release_tag_name": curr_tag,
                    "previous_tag": prev_tag,
                    "commit_hash": commit_hash,
                    "commit_message": commit_msg
                })
        except requests.exceptions.RequestException as e:
            print(f'Lỗi khi lấy commit cho {user}/{repo_name} từ {prev_tag} đến {curr_tag}: {e}')
            logger.error("Lỗi trong crawl_commits_for_release_pair: %s", e, exc_info=True)
    
    # For the first release, get all commits up to that point
    if releases:
        first_release_id, first_tag = releases[0]
        try:
            # For the first tag, we get all commits up to that tag
            url = f"https://api.github.com/repos/{user}/{repo_name}/commits?sha={quote(first_tag, safe='')}"
            response = s.safe_get(url)
            if response:
                first_commits = response.json()
                for commit in first_commits:
                    commit_hash = commit.get("sha")
                    commit_msg = commit.get("commit", {}).get("message")

                    if not commit_hash or not commit_msg:
                        continue

                    results.append((commit_hash, commit_msg, first_release_id))
                    json_entries.append({
                        "repo": f"{user}/{repo_name}",
                        "release_tag_name": first_tag,
                        "previous_tag": "initial",
                        "commit_hash": commit_hash,
                        "commit_message": commit_msg
                    })
        except requests.exceptions.RequestException as e:
            print(f'Lỗi khi lấy commit cho {user}/{repo_name} phiên bản đầu tiên {first_tag}: {e}')
            logger.error("Lỗi khi lấy commit cho phiên bản đầu tiên: %s", e, exc_info=True)
            
    return results, json_entries


def process_repo(repo):
    repo_id, user, repo_name = repo
    conn = get_connection()
    try:
        cur = conn.cursor()
        # Get all releases for this repo
        releases = get_repo_releases(conn, cur, user, repo_name)
        print(f"Found {len(releases)} releases for {user}/{repo_name}")
        
        if not releases:
            return [], []
            
        return crawl_commits_for_release_pair(user, repo_name, releases)
    finally:
        if conn:
            release_connection(conn)


def get_all_commits():
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        repos = q.get_all_repos(conn, cur)
        print(f"Found {len(repos)} repositories.")
        CHUNK_SIZE = 1000
        BATCH_SIZE = 1000
        MAX_THREADS = 48

        os.makedirs("output", exist_ok=True)
        json_path = "output/commits_output.json"

        with open(json_path, "w", encoding="utf-8") as f_json:
            f_json.write("[\n")
            is_first_json = True

            for repos_chunk in chunked_iterable(repos, CHUNK_SIZE):
                commit_records = []
                json_chunk = []

                # Crawl commits đa luồng (an toàn vì không dùng cur/conn trong thread)
                with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
                    futures = [executor.submit(process_repo, repo) for repo in repos_chunk]
                    for future in as_completed(futures):
                        try:
                            commit_data, json_data = future.result()
                            commit_records.extend(commit_data)
                            json_chunk.extend(json_data)
                        except Exception as e:
                            logger.error("Error in thread result: %s", e, exc_info=True)

                        if len(commit_records) >= BATCH_SIZE:
                            save_commits_chunk_to_db(cur, commit_records)
                            append_json_chunk(f_json, json_chunk, is_first_json)
                            if is_first_json:
                                is_first_json = False
                            commit_records.clear()
                            json_chunk.clear()
                            s.print_token_usage()

                # Ghi nốt phần còn lại
                if commit_records:
                    save_commits_chunk_to_db(cur, commit_records)
                if json_chunk:
                    append_json_chunk(f_json, json_chunk, is_first_json)
                    is_first_json = False
                s.print_token_usage()
            f_json.write("\n]")

        conn.commit()
        print(f"Đã lưu commit vào database và file '{json_path}'")

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error("Lỗi trong get_all_commits: %s", e, exc_info=True)

    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)
