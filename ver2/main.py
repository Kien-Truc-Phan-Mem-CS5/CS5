from crawler import gitstar_crawler, releases_crawler, commit_crawler
from database import database
import time
import cProfile
import pstats
import logging
from crawler.safe_get import session


logging.basicConfig(
    filename = 'crawler.log',
    level = logging.DEBUG, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # Định dạng log
)
# Tạo logger cho module chính
logger = logging.getLogger('main')
logger.info('Ứng dụng bắt đầu chạy')


def main():
    database.intital()
    gitstar_crawler.get_repo()
    releases_crawler.crawl_releases()
    commit_crawler.get_all_commits()
    pass

if __name__ == "__main__":
    profiler = cProfile.Profile()
    start_time = time.time()
    profiler.enable()
    main()
    profiler.disable()
    end_time = time.time()

    print(f"Thời gian thực thi: {end_time - start_time:.4f} giây")

    stats = pstats.Stats(profiler)
    stats.strip_dirs().sort_stats('cumulative').print_stats(10)
    # Cuối chương trình:
    session.close()

