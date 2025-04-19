#!/bin/bash

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

# crawl
echo "crawl thông tin ...."
python main.py