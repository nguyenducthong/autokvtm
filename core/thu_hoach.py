import sys
import os
import time
import logging
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from .adb import ADBController
from .image import ImageProcessor
from utils.utils import (
    lay_toa_do_tu_indexs, tim_may, find_image_v2, _get_adb,
    set_state, PlayerState, save_debug_image, is_debug_mode
)
from config import CLICK_DELAY_THU_HOACH as CLICK_DELAY

logger = logging.getLogger(__name__)

img = ImageProcessor()
MAX_ATTEMPTS = 3
THRESHOLD = 0.75                  # Độ chính xác tìm kiếm linh hoạt hơn

DEBUG_MODE = False
DEBUG_DIR = "debug/trong_cay"

def set_debug_mode(enabled: bool):
    """Bật/tắt debug mode lưu ảnh cho phần thu hoạch."""
    global DEBUG_MODE
    DEBUG_MODE = enabled
    if enabled:
        os.makedirs(DEBUG_DIR, exist_ok=True)
        logger.info(f"[DEBUG] Thu hoach debug mode ON — lưu ảnh tại {DEBUG_DIR}/")

def _save_debug_screenshot(screen, template_path, pos, step_name):
    """Lưu ảnh debug nếu debug mode bật."""
    if not (DEBUG_MODE or is_debug_mode()) or screen is None:
        return
    save_debug_image(screen, template_path, pos, step_name=step_name, debug_dir=DEBUG_DIR)


def thuhoach(points: list, tap, duration_ms: int = 800, threshold: float = None):
    """
    Thu hoạch bằng cách kéo giỏ mượt liên tục qua các vị trí chậu cây.
    Đã sửa lỗi `points.insert(0, pos)` làm biến dạng danh sách điểm gốc.
    """
    adb = _get_adb()
    if not adb:
        logger.error("ADB chưa được khởi tạo cho thread này!")
        return

    set_state(PlayerState.THU_HOACH)
    x, y = tap
    th = threshold or THRESHOLD

    pos = tim_gio_thu_hoach(threshold=th)
    if not pos:
        logger.info("Chưa thấy giỏ thu hoạch ngay, tap lại chậu để mở popup...")
        adb.tap(x, y)
        time.sleep(CLICK_DELAY)
        pos = tim_gio_thu_hoach(threshold=th)

    if pos:
        # Tạo danh sách điểm kéo mới, không làm hỏng list 'points' của caller
        path_points = [pos] + list(points)
        logger.info(f"Tìm thấy giỏ tại {pos}, kéo mượt liên tục qua {len(path_points)} điểm")
        adb.drag_smooth(path_points, total_duration_ms=duration_ms)
        time.sleep(0.3)
    else:
        logger.warning("Không tìm thấy giỏ thu hoạch sau các lần thử")
        adb.tap(x, y)


def tim_gio_thu_hoach(threshold: float = None):
    th = threshold or THRESHOLD
    adb = _get_adb()
    screen = adb.screenshot_full() if adb else None
    if screen is not None:
        pos = img.find_template_color("assets/items/core_thu_hoach.png", threshold=th, screen_img=screen)
        _save_debug_screenshot(screen, "assets/items/core_thu_hoach.png", pos, "tim_gio_chinh")
        if pos:
            logger.info(f"Tìm được giỏ tại {pos}")
            return pos

        # Thử mẫu giỏ phụ nếu có
        alt_path = "assets/items/core_thu_hoach_1.png"
        if os.path.exists(alt_path):
            pos_alt = img.find_template_color(alt_path, threshold=th, screen_img=screen)
            _save_debug_screenshot(screen, alt_path, pos_alt, "tim_gio_phu")
            if pos_alt:
                logger.info(f"Tìm được giỏ (mẫu 2) tại {pos_alt}")
                return pos_alt
    else:
        # Fallback find_image_v2 nếu không lấy trực tiếp screen từ adb
        pos = find_image_v2(template_path="assets/items/core_thu_hoach.png", screen=True,
                            threshold=th, max_retry=0, step_name="tim_gio_chinh")
        if pos:
            logger.info(f"Tìm được giỏ tại {pos}")
            return pos

        alt_path = "assets/items/core_thu_hoach_1.png"
        if os.path.exists(alt_path):
            pos_alt = find_image_v2(template_path=alt_path, screen=False, threshold=th, max_retry=0, step_name="tim_gio_phu")
            if pos_alt:
                logger.info(f"Tìm được giỏ (mẫu 2) tại {pos_alt}")
                return pos_alt

    logger.debug("Không tìm được giỏ")
    return None