import psycopg2
import json

# Kết nối PostgreSQL
conn = psycopg2.connect(
    dbname="crawler",
    user="admin",
    password="secret",
    host="localhost",
    port="5432"
)
cur = conn.cursor()

# Đọc file JSON
with open("gitstar_repos.json", "r", encoding="utf-8") as f:
    repos = json.load(f)

# Chèn dữ liệu vào bảng repo
for repo in repos:
    user_name = repo["user"]
    name = repo["name"]

    cur.execute("""
        INSERT INTO repo ("user", name) 
        VALUES (%s, %s)
        ON CONFLICT ("user", name) DO NOTHING;
    """, (user_name, name))

# Lưu thay đổi
conn.commit()
print(f"Đã thêm {len(repos)} repositories vào database!")

# Đóng kết nối
cur.close()
conn.close()
