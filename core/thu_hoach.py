import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from .adb import ADBController
from .image import ImageProcessor
from config import DEVICE_SERIAL
import time
import logging

logger = logging.getLogger(__name__)

# Không khởi tạo ADB ngay, sẽ khởi tạo khi cần
adb = None
img = ImageProcessor()
MAX_ATTEMPTS = 3
THRESHOLD = 0.75                  # Độ chính xác tìm kiếm
CLICK_DELAY = 1.5

def init_adb(serial=None):
    """Khởi tạo ADB controller"""
    global adb
    if serial is None:
        serial = DEVICE_SERIAL
    adb = ADBController(serial=serial)
    return adb


def thuhoach(points: list, tap, duration_ms: int = 1500):
    """
    Thu hoạch bằng cách kéo giỏ qua các vị trí

    Args:
        points: Danh sách các vị trí cần thu hoạch
        tap: Vị trí đầu tiên để tap
        duration_ms: Tổng thời gian kéo (ms), mặc định 1500ms
    """
    x, y = tap
    # adb.tap(x, y, 1)
    pos = tim_gio_thu_hoach()
    if pos:
        points.insert(0, pos)
        logger.info(f"Tìm thấy giỏ tại {pos}, kéo qua {len(points)} điểm")

        # Sử dụng drag_smooth thay vì send_touch_sendevent
        adb.drag_smooth(points, total_duration_ms=duration_ms)
    else:
        logger.warning("Không tìm thấy giỏ, tap lại vị trí đầu")
        adb.tap(x, y)


def tim_gio_thu_hoach():
    pos = find_image("assets/items/thu_hoach.png", True)
    if (pos):
        print("Tim được giỏ")
        return pos
    else:
        print("Không Tìm được giỏ")
        return None

def find_image(template_path, screen):
    screen_path = "cache/screen.png"
    if (screen):
        adb.screenshot_full(screen_path)
    return img.find_template(screen_path=screen_path, template_path=template_path, threshold=THRESHOLD)
    
