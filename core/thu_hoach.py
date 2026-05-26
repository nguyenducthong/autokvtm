import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from .adb import ADBController
from .image import ImageProcessor

import logging
from utils.utils import lay_toa_do_tu_indexs, tim_may, find_image_v2, _get_adb, set_state, PlayerState
logger = logging.getLogger(__name__)

img = ImageProcessor()
MAX_ATTEMPTS = 3
THRESHOLD = 0.8                  # Độ chính xác tìm kiếm
CLICK_DELAY = 1.5


def thuhoach(points: list, tap, duration_ms: int = 800, threshold: float = None):
    """
    Thu hoạch bằng cách kéo giỏ qua các vị trí.
    duration_ms giảm từ 1500 → 800ms cho nhanh hơn.
    threshold: nếu None thì dùng THRESHOLD mặc định của module.
    """
    adb = _get_adb()
    if not adb:
        logger.error("ADB chưa được khởi tạo cho thread này!")
        return

    set_state(PlayerState.THU_HOACH)
    x, y = tap
    pos = tim_gio_thu_hoach(threshold=threshold)
    if pos:
        points.insert(0, pos)
        logger.info(f"Tìm thấy giỏ tại {pos}, kéo qua {len(points)} điểm")
        adb.drag_smooth(points, total_duration_ms=duration_ms)
    else:
        logger.warning("Không tìm thấy giỏ, tap lại vị trí đầu")
        adb.tap(x, y)


def tim_gio_thu_hoach(threshold: float = None):
    th = threshold or THRESHOLD
    pos = find_image_v2(template_path="assets/items/thu_hoach.png", screen=True,
                        threshold=th, max_retry=0)
    if pos:
        logger.info(f"Tìm được giỏ tại {pos}")
        return pos
    else:
        logger.warning("Không tìm được giỏ")
        return None