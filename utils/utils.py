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

def init_adb(serial=None, adb: ADBController=None):
    """Khởi tạo ADB controller"""
    if adb is not None:
        return adb
    if serial is None:
        serial = DEVICE_SERIAL
    adb = ADBController(serial=serial)
    return adb

def tim_may(template_path, config_row, count=1):
    # tìm giá trị hiện tại của current_row 
    # So sánh với config_row để di chuyển lên/xuống máy
    # Tìm hàng hiện tại bằng cách tìm các số từ 1 đến 10
    current_row = None
    for i in range(1, 11):
        may_i = f"assets/items/num/{i}.png"
        pos = find_image_v2(may_i, False)
        if pos:
            current_row = i
            logger.info(f"Đã xác định hàng hiện tại là {current_row}")
            break
    if current_row == None:
        current_row = 0

    if current_row == config_row:
        logger.info(f"Đang ở hàng {current_row}, đúng với cấu hình")
        return True

    if current_row < config_row:
        diff = 0
        # Cần lên máy
        if (current_row == 0 and config_row == 1) or current_row > 1:
            diff = config_row - current_row 
        else:
            diff = config_row - current_row - 1
        logger.info(f"Cần lên máy {diff} lần")
        len_may(diff)
    else:
        diff = 0
        # Cần xuống máy
        if (current_row == 1 and config_row == 0) or (current_row == 2 and config_row == 1) and config_row > 2:
            diff = current_row - config_row
        else:
            diff = current_row - config_row - 1
        if (diff > 2 and config_row == 1):
            xuong_nha()
            len_may(1)
        else:
            logger.info(f"Cần xuống máy {diff} lần")    
            xuong_may(diff)

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
    pos = find_image_v2("assets/items/check_xuong_1.png", True)
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
    logger.info(f"Tìm hình ảnh: {template_path}, chụp mới: {screen}")
    if not hasattr(local_cache, '_last_screen'):
        local_cache._last_screen = None

    if screen:
        # Chụp mới vào memory, không lưu file
        if adb is None:
            init_adb()
        local_cache._last_screen = adb.screenshot_full()
    else:
        # Nếu dùng cache nhưng cache trống, chụp một ảnh mới tự động
        if local_cache._last_screen is None:
            if adb is None:
                init_adb()
            local_cache._last_screen = adb.screenshot_full()

    # Dùng screen_img nếu có, không thì dùng cache
    use_screen = screen_img if screen_img is not None else local_cache._last_screen
    if use_screen is None:
        logger.warning("Không có ảnh màn hình để tìm template: %s", template_path)
        return None
    return img.find_template(template_path=template_path, threshold=THRESHOLD, screen_img=use_screen)

def find_image_v2(template_path, screen, screen_img=None, threshold=THRESHOLD):
    """ test dùng cho ảnh màu ko scale
    Tìm template trong screen
    :param template_path: Đường dẫn ảnh mẫu
    :param screen: True = chụp mới, False = dùng screen đã cache
    :param screen_img: Numpy array của screen (tùy chọn, dùng lại ảnh đã chụp)
    """
    logger.info(f"Tìm hình ảnh: {template_path}, chụp mới: {screen}")
    if not hasattr(local_cache, '_last_screen'):
        local_cache._last_screen = None

    if screen:
        # Chụp mới vào memory, không lưu file
        if adb is None:
            init_adb()
        local_cache._last_screen = adb.screenshot_full()
    else:
        # Nếu dùng cache nhưng cache trống, chụp một ảnh mới tự động
        if local_cache._last_screen is None:
            if adb is None:
                init_adb()
            local_cache._last_screen = adb.screenshot_full()

    # Dùng screen_img nếu có, không thì dùng cache
    use_screen = screen_img if screen_img is not None else local_cache._last_screen
    if use_screen is None:
        logger.warning("Không có ảnh màn hình để tìm template: %s", template_path)
        return None
    return img.find_exact(template_path=template_path, threshold=threshold, screen_img=use_screen)

def clear_screen_cache():
    """Xóa cache screenshot để giải phóng memory (gọi sau khi hoàn thành task)"""
    if hasattr(local_cache, '_last_screen'):
        local_cache._last_screen = None
