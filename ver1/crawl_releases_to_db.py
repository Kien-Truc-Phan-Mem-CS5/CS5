import requests
import psycopg2
import time
import json

# Token GitHub của bạn
GITHUB_TOKEN = ""  

HEADERS = {
    "Accept": "application/vnd.github+json",
    ##fix interrupt: add user-agent
    #"User-Agent": "MyGitHubCrawler/1.0",
    "Authorization": f"token {GITHUB_TOKEN}" if GITHUB_TOKEN else ""
}

# Kết nối DB
conn = psycopg2.connect(
    dbname="crawler",
    user="admin",
    password="secret",
    host="localhost",
    port="5432"
)
cur = conn.cursor()

# Lấy danh sách repo
def get_all_repos():
    cur.execute("SELECT id, \"user\", name FROM repo;")
    return cur.fetchall()

# Gọi API để lấy release
def get_releases(owner, repo_name):
    url = f"https://api.github.com/repos/{owner}/{repo_name}/releases"
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200:
        print(f"Lỗi {res.status_code} với {owner}/{repo_name}")
        return []
    return res.json()

# BẮT ĐẦU CRAWL
repos = get_all_repos()
all_release_data = []  # chứa toàn bộ dữ liệu để ghi JSON

for idx, (repo_id, user, name) in enumerate(repos):
    print(f"[{idx+1}/{len(repos)}] {user}/{name}")
    releases = get_releases(user, name)

    for rel in releases:
        content = rel.get("body") or ""
        release_name = rel.get("name") or rel.get("tag_name")
        release_tag_name = rel.get("tag_name")
        print(release_tag_name)
        # Ghi vào DB
        cur.execute("""
            INSERT INTO release (release_name, release_tag_name, content, repoID)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING;
        """, (release_name, release_tag_name, content.strip(), repo_id))


        # Ghi vào JSON
        all_release_data.append({
            "repo": f"{user}/{name}",
            "release_name": release_name,
            "release_tag_name": release_tag_name, 
            "body": content.strip(),
            "published_at": rel.get("published_at")
        })



    conn.commit()
    time.sleep(1.2)

# Ghi toàn bộ dữ liệu ra file JSON
with open("releases_output.json", "w", encoding="utf-8") as f:
    json.dump(all_release_data, f, indent=4, ensure_ascii=False)

# Đóng kết nối
cur.close()
conn.close()
print(f"Đã lưu {len(all_release_data)} bản release vào cả database và file 'releases_output.json'")
