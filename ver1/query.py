import psycopg2

conn = psycopg2.connect(
    dbname="crawler",
    user="admin",
    password="secret",
    host="localhost",
    port="5432"
)
cur = conn.cursor()

# Truy vấn dữ liệu
cur.execute("DELETE FROM commit;")
conn.commit()
cur.execute("SELECT * FROM commit;")
rows = cur.fetchall()

# Hiển thị dữ liệu
print("Danh sách repo:")
for row in rows:
    print(row)


# cur.execute("ALTER TABLE release ADD COLUMN release_name TEXT;")
# cur.execute("ALTER TABLE release ADD COLUMN release_tag_name TEXT;")
# conn.commit()
# cur.execute("""
#     SELECT column_name, data_type 
#     FROM information_schema.columns 
#     WHERE table_name = 'release';
# """)
# columns = cur.fetchall()
# print("Các cột trong bảng 'release':")
# for name, dtype in columns:
#     print(f"  - {name} ({dtype})")
cur.close()
conn.close()
