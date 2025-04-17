import psycopg2

conn = psycopg2.connect(
    dbname="crawler",
    user="admin",
    password="secret",
    host="localhost",
    port="5432"
)
cur = conn.cursor()
# Xóa toàn bộ bảng (có ràng buộc khóa ngoại nên phải xóa release & commit trước)
# cur.execute("DROP TABLE IF EXISTS commit CASCADE;")
# cur.execute("DROP TABLE IF EXISTS release CASCADE;")
# cur.execute("DROP TABLE IF EXISTS repo CASCADE;")

# Tạo bảng
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
    releaseID INT NOT NULL REFERENCES release(id)
);
""")

conn.commit()

cur.execute("""
    SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';
""")

tables = cur.fetchall()
print("Các bảng trong database:")
for table in tables:
    print(table[0])

cur.close()
conn.close()
print("Đã tạo bảng thành công!")
