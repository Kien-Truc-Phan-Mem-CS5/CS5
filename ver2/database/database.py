from database import query as q
import logging
from database.db_pool import get_connection, release_connection


# Lấy logger đã được cấu hình từ module chính
logger = logging.getLogger('main')

conn = get_connection()

# Tạo bảng
def intital():
    try: 
        cur = conn.cursor()
        # Xóa toàn bộ bảng (có ràng buộc khóa ngoại nên phải xóa release & commit trước)
        cur.execute("DROP TABLE IF EXISTS commit CASCADE;")
        cur.execute("DROP TABLE IF EXISTS release CASCADE;")
        cur.execute("DROP TABLE IF EXISTS repo CASCADE;")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS repo (
            id SERIAL PRIMARY KEY,
            "user" TEXT NOT NULL,
            name TEXT NOT NULL,
            CONSTRAINT unique_repo UNIQUE ("user", name)  -- Thêm UNIQUE constraint
        );

        CREATE TABLE IF NOT EXISTS release (
            id SERIAL PRIMARY KEY,
            release_name TEXT NOT NULL,
            release_tag_name TEXT NOT NULL,
            content TEXT NOT NULL,
            repoID INT NOT NULL REFERENCES repo(id)
        );

        CREATE TABLE IF NOT EXISTS commit (
            hash TEXT NOT NULL,
            message TEXT NOT NULL,
            releaseID INT NOT NULL REFERENCES release(id),
            CONSTRAINT unique_commit UNIQUE (hash, releaseID)
        );
        """)
        q.save_change(conn)
        show_tables(cur)
        print("Đã tạo bảng thành công!")
    finally:
        cur.close()
        release_connection(conn)

def show_tables(cur):
    # Lấy danh sách các bảng trong schema 'public'
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public';
    """)
    tables = cur.fetchall()

    print("Các bảng trong database:")
    for table in tables:
        table_name = table[0]
        print(f"\n Bảng: {table_name}")

        # Lấy thông tin các cột của bảng hiện tại
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s;
        """, (table_name,))
        columns = cur.fetchall()

        print("Cột:")
        for column in columns:
            column_name, data_type = column
            print(f"  - {column_name}: {data_type}")
