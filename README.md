# GitHub Repository Crawler

## Giới thiệu
Dự án này xây dựng một crawler tự động thu thập thông tin về các bản releases, và commits liên quan từ 5000 repo nhiều sao nhất trên GitHub. Crawler sử dụng GitHub API để lấy dữ liệu từ 5000 repository có nhiều sao nhất và lưu trữ vào cơ sở dữ liệu PostgreSQL cùng với file JSON cho việc phân tích.   

Dưới đây là hướng dẫn cài đặt và tóm tắt về dự án, với báo cáo chi tiết và đầy đủ, xin hãy đọc ở đây:    
[Báo cáo btl KTPM](https://docs.google.com/document/d/1yQMmqp3aIh690GjjTO0WuX2wOcycXvUJ/edit?usp=sharing&ouid=117858628179603340640&rtpof=true&sd=true)

## Yêu cầu hệ thống
- Python 3.8+
- PostgreSQL
- Các thư viện Python: `requests`, `psycopg2`, `backoff`, `threading`,...

## Cài đặt
1. **Clone repository:**
   ```bash
   git clone <repository_url>
   cd <repository_directory>
   ```

2. **Cài đặt các thư viện cần thiết:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Cấu hình cơ sở dữ liệu:**
   - Tạo database PostgreSQL
   - Cập nhật trong database các thông tin kết nối trong `database/db_pool.py`:
     ```python
     connection_pool = pool.SimpleConnectionPool(
         minconn=1,
         maxconn=20,
         dbname="crawler",
         user="admin",
         password="secret",
         host="localhost",
         port="5432"
     )
     ```

4. **Cấu hình GitHub API tokens:**
   - Thêm GitHub tokens vào `crawler/safe_get.py` để tăng giới hạn API
     ```python
     GITHUB_TOKENS = [
         "token 1",
         "token 2",
         # Thêm các token khác nếu có
     ]
     ```
     
## Cấu trúc phiên bản cuối
```
ver2/
├── crawler/
│   ├── gitstar_crawler.py   # Thu thập danh sách repositories
│   ├── releases_crawler.py  # Thu thập thông tin releases và tags
│   ├── commit_crawler.py    # Thu thập thông tin commits
│   └── safe_get.py          # Xử lý requests an toàn với GitHub API
├── database/
│   ├── database.py          # Khởi tạo database
│   ├── db_pool.py           # Quản lý connection pool
│   └── query.py             # Các hàm truy vấn database
├── output/                  # Thư mục chứa dữ liệu output dạng JSON
└── main.py                  # Script chính điều khiển quá trình crawl
```

## Cách chạy
```bash
python main.py
```

Quá trình thực thi:
1. Khởi tạo cơ sở dữ liệu
2. Thu thập danh sách repositories từ GitStar
3. Thu thập thông tin releases/tags từ các repositories
4. Thu thập thông tin commits liên quan đến releases

## Giải pháp đã áp dụng
1. **Quản lý GitHub API Rate Limits:**
   - Sử dụng nhiều tokens để luân phiên gửi requests
   - Theo dõi lượng token đã sử dụng, thời gian refresh, dừng request nếu đã hết token

2. **Tối ưu hiệu năng:**
   - Sử dụng ThreadPoolExecutor để xử lý đa luồng
   - Lưu dữ liệu theo batch và dùng chunk để giảm số lượng truy vấn
   - Connection pooling để quản lý kết nối database hiệu quả

3. **Xử lý lỗi:**
   - Logging chi tiết khi chạy và vào các file json trong output
   - Xử lý ngoại lệ với cơ chế rollback transaction
   - Xử lý repositories không có releases bằng cách kiểm tra tags

4. **Lưu trữ dữ liệu:**
   - PostgreSQL với các bảng `repo`, `release`, và `commit`
   - File JSON cho phân tích

## Theo dõi hiệu suất
Dự án sử dụng cProfile để ghi lại hiệu suất thực thi. Kết quả được hiển thị sau khi chạy xong, cho biết các hàm tốn nhiều thời gian nhất.

## Hướng phát triển
- Sử dụng proxy để tối thiểu khả năng bị chặn (Dù trong quá trình chạy chưa từng ghi nhận trường hợp bị chặn/ban)
- Thêm cơ chế lưu trạng thái để tiếp tục từ điểm dừng

## Tài liệu tham khảo
- [GitHub REST API Documentation](https://docs.github.com/en/rest)
- [Gitstar Ranking](https://gitstar-ranking.com)
