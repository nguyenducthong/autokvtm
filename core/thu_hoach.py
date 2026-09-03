import sys
import os
import time
import logging
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from .adb import ADBController
from .image import ImageProcessor
from utils.utils import lay_toa_do_tu_indexs, tim_may, find_image_v2, _get_adb, set_state, PlayerState
from config import CLICK_DELAY_THU_HOACH as CLICK_DELAY

logger = logging.getLogger(__name__)

img = ImageProcessor()
MAX_ATTEMPTS = 3
THRESHOLD = 0.75                  # Độ chính xác tìm kiếm linh hoạt hơn



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
    # Thử mẫu giỏ chính
    pos = find_image_v2(template_path="assets/items/core_thu_hoach.png", screen=True,
                        threshold=th, max_retry=0)
    if pos:
        logger.info(f"Tìm được giỏ tại {pos}")
        return pos

    # Thử mẫu giỏ phụ nếu có
    alt_path = "assets/items/core_thu_hoach_1.png"
    if os.path.exists(alt_path):
        pos_alt = find_image_v2(template_path=alt_path, screen=False, threshold=th, max_retry=0)
        if pos_alt:
            logger.info(f"Tìm được giỏ (mẫu 2) tại {pos_alt}")
            return pos_alt

    logger.debug("Không tìm được giỏ")
    return None