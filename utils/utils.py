import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from core.adb import ADBController
from core.image import ImageProcessor
from config import DEVICE_SERIAL, INDEX_HANG, CONFIG_TEMP_TC, INDEX_XUONG_NHA_MAC_DINH
import time
import logging
import threading
THRESHOLD = 0.8
logger = logging.getLogger(__name__)

# Không khởi tạo ADB ngay, sẽ khởi tạo khi cần
adb = None
img = ImageProcessor()
local_cache = threading.local()  # Cache per thread để tránh lẫn khi chạy nhiều thread

def init_adb(serial=None):
    """Khởi tạo ADB controller"""
    global adb
    if serial is None:
        serial = DEVICE_SERIAL
    adb = ADBController(serial=serial)
    return adb

def tim_may(template_path, count=1):
    
    pos = find_image(template_path, True)
    if (pos):
        logger.info(f"tim duoc {template_path} {pos}")
        return True
    else:
        count= count + 1
        logger.info(f"khong tim duoc {template_path}" )
        may_10 = "assets/items/num/10.png"
        pos = find_image(may_10, False)
        logger.info(f"Lỗi tìm mây số lượng: {count}" )
        if (pos):
            xuong_nha()
        if (count > 5):
            xuong_nha()
        if (count > 10):
            return False # Bỏ qua cấu hình này
        len_may(1, 50)
        return tim_may(template_path, count)  


def lay_toa_do_tu_indexs(indexs_list):
    return [INDEX_HANG[idx] for idx in indexs_list if idx in INDEX_HANG]


def len_may(count: int=1, duration: int=50,sleep: float=0.7):
    for _ in range(count):
        adb.scroll_up(450, 500, 70, duration)
        time.sleep(sleep)

def xuong_may(count: int=1, duration: int=50,sleep: float=0.7):
    for _ in range(count):
        adb.scroll_down(500, 450, 70, duration)
        time.sleep(sleep)

def xuong_nha(duration: int=50,sleep: float=0.7):
    adb.scroll_up(450, 500, 70, duration)
    adb.scroll_down(500, 450, 70, duration)
    time.sleep(sleep)
    pos = find_image("assets/items/check_xuong_1.png", True)
    if (pos):
        logger.info("Tìm được xuống nhà")
        (x,y) = pos
        adb.tap(x,y)
        time.sleep(sleep)
    else:
        logger.info("Không tìm được tab mặc định")
        (x,y) = INDEX_XUONG_NHA_MAC_DINH
        adb.tap(x,y)
        time.sleep(sleep)

def find_image(template_path, screen, screen_img=None):
    """
    Tìm template trong screen
    :param template_path: Đường dẫn ảnh mẫu
    :param screen: True = chụp mới, False = dùng screen đã cache
    :param screen_img: Numpy array của screen (tùy chọn, dùng lại ảnh đã chụp)
    """
    if not hasattr(local_cache, '_last_screen'):
        local_cache._last_screen = None

    if screen:
        # Chụp mới vào memory, không lưu file
        local_cache._last_screen = adb.screenshot_full()

    # Dùng screen_img nếu có, không thì dùng cache
    use_screen = screen_img if screen_img is not None else local_cache._last_screen
    return img.find_template(template_path=template_path, threshold=THRESHOLD, screen_img=use_screen)

def clear_screen_cache():
    """Xóa cache screenshot để giải phóng memory (gọi sau khi hoàn thành task)"""
    if hasattr(local_cache, '_last_screen'):
        local_cache._last_screen = None
