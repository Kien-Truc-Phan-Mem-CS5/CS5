# GitHub Repository Crawler
## Nhóm 16 - 2425II_INT3105_2
Mẫn Thị Bích Phương - 22021119 - K67I-IT2   
Đàm Quang Đạt - 22028026 - K67I-CS2   
Nguyễn Văn Lợi - 22021114 - K67I-IT2   

## Giới thiệu
Dưới đây là báo cáo ngắn gọn về dự án, với báo cáo chi tiết và đầy đủ, xin hãy đọc ở đây:  
### ***[Báo cáo btl KTPM](https://docs.google.com/document/d/1yQMmqp3aIh690GjjTO0WuX2wOcycXvUJ/edit?usp=sharing&ouid=117858628179603340640&rtpof=true&sd=true)***

## TTriển khai crawler cơ bản 
Crawler này thực hiện các công việc sau:
- Thu thập danh sách top 5000 repository từ Gitstar
- Lấy thông tin các bản phát hành (releases) của từng repository
- Thu thập thông tin commit 

Dữ liệu được lưu trữ trong cơ sở dữ liệu PostgreSQL.

## Các Vấn Đề Gặp Phải
Khi thực hiện thu thập tự động các thông tin liên quan đến repositories, phiên bản triển khai đơn giản đã gặp một số vấn đề sau:

### 1. Giới Hạn Tốc Độ Truy Cập
- Giới hạn tốc độ truy cập (rate limit): lỗi kết nối `requests.exceptions.ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))`
- Giới hạn API mặc định: 60 yêu cầu/giờ với yêu cầu không xác thực bằng token
- Giới hạn khi xác thực bằng token: 5.000 yêu cầu/giờ

### 2. Dữ Liệu Repository Không Đầy Đủ
- Một số repository không có thông tin release hoặc tag hoặc cả 2
- Không thể thu thập thông tin liên quan cho các trường hợp này

### 3. Vấn Đề Ký Tự Đặc Biệt
- API gặp lỗi với các ký tự đặc biệt trong SHA của tag_name
- GitHub không tìm thấy commit/branch tương ứng với tag chứa ký tự đặc biệt

### 4. Vấn Đề Hiệu Suất
- Tốc độ chậm do số lượng yêu cầu lớn (5000 repos, ~82000 releases/tags), trong khi có giới hạn về api
- Ghi dữ liệu vào database chưa tối ưu gây độ trễ, ảnh hưởng hiệu suất tổng thể

## Các Cải Tiến Đã Triển Khai

### A. Quản Lý Giới Hạn Truy Cập
- Xác thực bằng token tăng giới hạn lên 5.000 yêu cầu/giờ
- Triển khai `Exponential Backoff` để tự động thử lại khi gặp lỗi
- Theo dõi hạn mức sử dụng API qua endpoint `/rate_limit`
- Luân chuyển token hoặc chờ đến thời điểm reset khi cần

### B. Tối Ưu Hóa Cơ Sở Dữ Liệu
- Ghi dữ liệu theo lô (batch) để giảm số lượng truy vấn, tăng tốc độ ghi.
- Sử dụng connection pooling và tối ưu truy vấn
- Hạn chế các phép JOIN phức tạp
- Đọc dữ liệu theo từng phần (chunk) để tránh tràn bộ nhớ khi xử lí dữ liệu lớn

### C. Tăng Độ Ổn Định Hệ Thống
- Cơ chế Retry kết hợp backoff + jitter cho lỗi mạng hoặc lỗi tạm thời từ GitHub
- Tái sử dụng kết nối HTTP với `requests.Session()`

### D. Xử Lý Repository Thiếu Dữ Liệu
- Với repo không có release: sử dụng thông tin tag và commit thay thế
- Với repo không có cả release lẫn tag: chỉ lưu thông tin commit (các trường liên quan để trống)

### E. Xử Lý Song Song
- Triển khai `ThreadPoolExecutor` để thu thập dữ liệu đồng thời với nhiều yêu cầu
- Lợi ích:
  - Tăng tốc độ xử lý tổng thể, do nhiều request được xử lý đồng thời
  - Tận dụng tối đa hạn mức API của nhiều token
  - Tránh tình trạng token bị reset trước khi sử dụng hết
- Kết hợp với chiến lược luân phiên token để phân tải đều, hạn chế rủi ro bị chặn

## Kết Quả
| Cải tiến | Xử lí song song | Số token | Thời gian |
|--------|------|---------|------|
| Triển khai đơn giản | Không | 1 | 16h 17p |
| Triển khai đơn giản | Không | 4 : lần lượt | 13h 7p |
| Áp dụng tối ưu csdl <br> Xử lí song song <br> Xử lí các lỗi dữ liệu <br> Retry + backoff  | Có : 4 threads | 4 : lần lượt | 7h 38p |
| Tăng số threads  <br> Dùng user-agent ngẫu nhiên <br> Luân phiên token  | Có : 12 threads | 5 : luân phiên | 3h 13p |
| Tăng số threads <br> Tuỳ chỉnh số threads cho từng hoạt động  | Có : 16 commit, 32 release | 6 : luân phiên | 2h 45p |
| Tăng số threads | Có : 32 commit, 64 release | 8 : luân phiên | 2h 6p |
| Tăng số threads | Có : 48 commit, 64 release | 10 : luân phiên | 1h 19p |


