import time
import logging
from functools import wraps

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.FileHandler("logs/auto.log", encoding="utf-8"),
        logging.StreamHandler()  # In ra console
    ]
)

def log_time(func):
    """Decorator: Ghi log thời gian thực hiện hàm"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        logging.info(f"BẮT ĐẦU → {func.__name__}()")
        try:
            result = func(*args, **kwargs)
            end = time.perf_counter()
            duration = end - start
            logging.info(f"HOÀN TẤT → {func.__name__}() | ⏱ {duration:.3f}s")
            return result
        except Exception as e:
            end = time.perf_counter()
            duration = end - start
            logging.error(f"LỖI → {func.__name__}() | ⏱ {duration:.3f}s | {e}")
            raise
    return wrapper