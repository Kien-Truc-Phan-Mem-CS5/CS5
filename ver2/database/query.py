import psycopg2
import logging

# Lấy logger đã được cấu hình từ module chính
logger = logging.getLogger('main')


def connect_database():
    try:
        conn = psycopg2.connect(
            dbname="crawler",
            user="admin",
            password="secret",
            host="localhost",
            port="5432"
        )
        cur = conn.cursor()
        print(f'kết nối thành công tới csdl')
        return conn, cur
    except psycopg2.DatabaseError as e:
        print(f"Lỗi khi kết nối đến cơ sở dữ liệu: {e}")
        logger.error("Lỗi trong connect_database: %s", e, exc_info=True)
        exit(1)

def close_connect(conn, cur):
    try:
        cur.close()
        conn.close()
        print(f'đóng kết nối thành công')
    except psycopg2.DatabaseError as e:
        print(f'Không đóng csdl thành công: {e}')
        logger.error("Lỗi trong close_connect: %s", e, exc_info=True)


def save_change(conn):
    try:
        conn.commit()
    except psycopg2.DatabaseError as e:
        print(f"Lỗi khi commit dữ liệu: {e}")
        logger.error("Lỗi trong save_change khi commit data: %s", e, exc_info=True)
        conn.rollback()
    

def insert_repo(conn, cur, user_name, name):
    try:
        cur.execute("""
            INSERT INTO repo ("user", name) 
            VALUES (%s, %s)
            ON CONFLICT ("user", name) DO NOTHING;
        """, (user_name, name))
    except psycopg2.errors.UniqueViolation:
        print(f"Repository {user_name}/{name} đã tồn tại.")
    except Exception as e:
        print(f"Đã xảy ra lỗi: {e}")
        logger.error("Lỗi trong insert_repo: %s", e, exc_info=True)

        conn.rollback()

def get_all_repos(conn, cur):
    try:
        cur.execute("SELECT id, \"user\", name FROM repo;")
        return cur.fetchall()
    except psycopg2.DatabaseError as e:
        print(f"Lỗi khi lấy danh sách repo: {e}")
        logger.error("Lỗi trong get_all_repos: %s", e, exc_info=True)
        conn.rollback()
        return []
    
def insert_release(conn, cur, release_name, release_tag_name, content, repo_id):
    try:
        cur.execute("""
            INSERT INTO release (release_name, release_tag_name, content, repoID)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING;
        """, (release_name, release_tag_name, content.strip(), repo_id))
    except psycopg2.DatabaseError as e:
        print(f"Lỗi khi ghi vào cơ sở dữ liệu: {e}")
        logger.error("Lỗi trong insert_release: %s", e, exc_info=True)
        conn.rollback()

def get_all_tag_names(conn, cur):
    try:
        cur.execute("""
            SELECT r.id, r.release_tag_name, repo."user", repo.name
            FROM release r
            JOIN repo ON r.repoID = repo.id
            WHERE r.release_tag_name IS NOT NULL;
        """)
        return cur.fetchall()
    except psycopg2.DatabaseError as e:
        print(f'Lỗi khi lấy danh sách releases của repo: {e}')
        logger.error("Lỗi trong get_all_tag_names: %s", e, exc_info=True)
        conn.rollback()
        return []
    
def insert_commit(conn, cur,commit_hash, commit_msg, release_id):
    try:
        cur.execute("""
            INSERT INTO commit (hash, message, releaseID)
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING;
        """, (commit_hash, commit_msg, release_id))
    except psycopg2.DatabaseError as e:
        print(f"Lỗi khi ghi vào cơ sở dữ liệu: {e}")
        logger.error("Lỗi trong insert_commit: %s", e, exc_info=True)
        conn.rollback()
# # Truy vấn dữ liệu
# cur.execute("DELETE FROM commit;")
# conn.commit()
# cur.execute("SELECT * FROM commit;")
# rows = cur.fetchall()

# # Hiển thị dữ liệu
# print("Danh sách repo:")
# for row in rows:
#     print(row)


# # cur.execute("ALTER TABLE release ADD COLUMN release_name TEXT;")
# # cur.execute("ALTER TABLE release ADD COLUMN release_tag_name TEXT;")
# # conn.commit()
# # cur.execute("""
# #     SELECT column_name, data_type 
# #     FROM information_schema.columns 
# #     WHERE table_name = 'release';
# # """)
# # columns = cur.fetchall()
# # print("Các cột trong bảng 'release':")
# # for name, dtype in columns:
# #     print(f"  - {name} ({dtype})")
# cur.close()
# conn.close()
