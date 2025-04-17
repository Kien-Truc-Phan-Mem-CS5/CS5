import psycopg2
import requests
import json
import time

# token của bạn
GITHUB_TOKEN = ""  

HEADERS = {
    "Accept": "application/vnd.github+json",
    ## fix add user-agent
    #"User-Agent": "MyGitHubCrawler/1.0",
    "Authorization": f"token {GITHUB_TOKEN}" if GITHUB_TOKEN else ""
}

# Kết nối tới PostgreSQL
conn = psycopg2.connect(
    dbname="crawler",
    user="admin",
    password="secret",
    host="localhost",
    port="5432"
)
cur = conn.cursor()

# Lấy danh sách release có tag name
cur.execute("""
    SELECT r.id, r.release_tag_name, repo."user", repo.name
    FROM release r
    JOIN repo ON r.repoID = repo.id
    WHERE r.release_tag_name IS NOT NULL;
""")
releases = cur.fetchall()

all_commit_data = []

print(f"Found {len(releases)} releases with tag names.")

for idx, (release_id, tag_name, user, repo_name) in enumerate(releases):
    print(f"[{idx+1}/{len(releases)}] Getting commits for {user}/{repo_name} - Tag: {tag_name}")

    url = f"https://api.github.com/repos/{user}/{repo_name}/commits?sha={tag_name}"
    res = requests.get(url, headers=HEADERS)

    if res.status_code != 200:
        print(f"Lỗi {res.status_code} khi lấy commit cho {user}/{repo_name} tag {tag_name}")
        continue

    commits = res.json()

    for commit in commits:
        commit_hash = commit.get("sha")
        commit_msg = commit.get("commit", {}).get("message")

        if not commit_hash or not commit_msg:
            continue
        # print(commit_hash)
        # print(commit_msg)
        # Ghi vào bảng commit
        cur.execute("""
            INSERT INTO commit (hash, message, releaseID)
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING;
        """, (commit_hash, commit_msg, release_id))

        # Thêm vào JSON
        all_commit_data.append({
            "repo": f"{user}/{repo_name}",
            "release_tag_name": tag_name,
            "commit_hash": commit_hash,
            "commit_message": commit_msg
        })

    conn.commit()
    time.sleep(1.2)  # Giới hạn tốc độ tránh bị block API

# Ghi tất cả commit ra file JSON
with open("commits_output.json", "w", encoding="utf-8") as f:
    json.dump(all_commit_data, f, indent=4, ensure_ascii=False)

cur.close()
conn.close()
print(f"Đã lưu {len(all_commit_data)} commit vào database và file 'commits_output.json'")
