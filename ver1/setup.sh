g#!/bin/bash

# # Bước 1: Chạy file gitstar_crawler.py
echo "Chạy file gitstar_crawler.py..."
python gitstar_crawler.py

# # Bước 2: Pull PostgreSQL image từ Docker
echo "Đang pull PostgreSQL từ Docker..."
docker pull postgres

# # Bước 3: Kiểm tra & dừng container cũ nếu có
if [ "$(docker ps -aq -f name=my-postgres)" ]; then
  echo "Container my-postgres đã tồn tại. Đang xóa..."
  docker stop my-postgres
  docker rm my-postgres
fi

# # Chạy container mới
echo "Đang tạo container PostgreSQL..."
docker run -d --name my-postgres -e POSTGRES_USER=admin \
           -e POSTGRES_PASSWORD=secret \
           -e POSTGRES_DB=crawler \
           -p 5432:5432 postgres:latest

# # Chờ database sẵn sàng
echo "Chờ PostgreSQL khởi động..."
sleep 5
until docker exec my-postgres pg_isready -U admin; do
  echo "Chờ thêm..."
  sleep 2
done

# # Bước 4: Chạy file database.py để tạo bảng
echo "Chạy file database.py..."
python database.py

# # Bước 5: Chạy file add_repo_db.py để thêm dữ liệu
echo "Chạy file add_repo_db.py..."
python add_repo_db.py

# # Bước 6: Test thử database
echo "Query....."
python query.py
echo "Tất cả các bước đã hoàn tất!"


#Bước 7: Lấy release của các repo
echo "Chạy file crawl_releases_to_db.py....."
python crawl_releases_to_db.py

#Bước 8: Chạy crawl lấy commits của release
echo "Chạy file fetch_commits.py...."
python fetch_commits.py