import psycopg2
import json
import query as q




def save_repo_to_db(repo):
    # Kết nối PostgreSQL
    conn, cur = q.connect_database()

    # Đọc file JSON
    try:
        with open("gitstar_repos.json", "r", encoding="utf-8") as f:
            repos = json.load(f)
    except FileNotFoundError:
        print("File không tồn tại.")
    except json.JSONDecodeError:
        print("Lỗi phân tích cú pháp JSON.")

    # Chèn dữ liệu vào bảng repo
    for repo in repos:
        user_name = repo["user"]
        name = repo["name"]
        q.insert_repo(user_name=user_name, name=name)

    # Lưu thay đổi
    q.save_change(conn)
    print(f"Đã thêm {len(repos)} repositories vào database!")

    # Đóng kết nối
    q.close_connect(conn, cur)
