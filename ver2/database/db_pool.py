from psycopg2 import pool, OperationalError, DatabaseError
import logging

logger = logging.getLogger('main')

try:
    # Khởi tạo connection pool
    connection_pool = pool.SimpleConnectionPool(
        minconn=1,
        maxconn=10,
        dbname="crawler",
        user="admin",
        password="secret",
        host="localhost",
        port="5432"
    )
    if connection_pool:
        logger.info("Connection pool created successfully.")
except (Exception, OperationalError) as error:
    logger.error("Error creating connection pool: %s", error)
    connection_pool = None

def get_connection():
    if connection_pool:
        try:
            return connection_pool.getconn()
        except (Exception, DatabaseError) as error:
            logger.error("Error getting connection from pool: %s", error)
            return None
    else:
        logger.error("Connection pool is not initialized.")
        return None

def release_connection(conn):
    if connection_pool and conn:
        try:
            connection_pool.putconn(conn)
            print("đã đóng kết nối")
        except (Exception, DatabaseError) as error:
            logger.error("Error releasing connection back to pool: %s", error)

def close_all_connections():
    if connection_pool:
        try:
            connection_pool.closeall()
            logger.info("All connections in the pool have been closed.")
        except (Exception, DatabaseError) as error:
            logger.error("Error closing all connections in the pool: %s", error)
