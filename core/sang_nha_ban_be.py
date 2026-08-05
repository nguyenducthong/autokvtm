import logging
import os
import time
from core.image import ImageProcessor, get_resource_path
from utils.daily_stats import record_daily_stat

logger = logging.getLogger(__name__)
img = ImageProcessor()

CORE_BAN_BE = "assets/items/core_ban_be.png"
CORE_QUAY_VE = "assets/items/core_quay_ve.png"
INDEX_MAC_DINH_BAN_BE = (219, 656)
SANG_BAN_BE_INTERVAL_SECONDS = 3600  # 1 hour

_last_run_at = {}

def can_sang_ban_be(serial: str, interval_seconds: int = SANG_BAN_BE_INTERVAL_SECONDS) -> bool:
    last = _last_run_at.get(serial, 0)
    return time.time() - last >= interval_seconds

def reset_sang_ban_be_timer(serial: str = None):
    if serial is None:
        _last_run_at.clear()
    else:
        _last_run_at.pop(serial, None)

def _sleep(seconds, stop_event=None):
    if stop_event is not None:
        stop_event.wait(seconds)
    else:
        time.sleep(seconds)

def _should_stop(stop_event=None):
    return stop_event is not None and stop_event.is_set()

def _tim_anh(adb, template_path: str, threshold: float = 0.82):
    resolved_path = get_resource_path(template_path)
    if not os.path.exists(resolved_path):
        logger.warning("[SANG BẠN BÈ] Thiếu ảnh mẫu: %s", template_path)
        return None
    screen = adb.screenshot_full()
    if screen is None:
        return None
    return img.find_template_color(template_path=template_path, threshold=threshold, screen_img=screen)

def _doi_anh(adb, template_path: str, timeout: int = 30, interval: float = 1.0,
             threshold: float = 0.82, stop_event=None):
    end_time = time.time() + timeout
    while time.time() < end_time:
        if _should_stop(stop_event):
            return None
        pos = _tim_anh(adb, template_path, threshold=threshold)
        if pos:
            return pos
        _sleep(interval, stop_event)
    return None

def sang_ban_be(adb, serial: str = None, force: bool = False, stop_event=None) -> bool:
    """Xử lý sang nhà bạn bè."""
    serial = serial or getattr(adb, "serial", "unknown")
    if _should_stop(stop_event):
        return False
    if not force and not can_sang_ban_be(serial):
        return False

    _last_run_at[serial] = time.time()
    logger.info("[SANG BẠN BÈ] Bắt đầu tìm nút Bạn Bè: %s", serial)

    # 1. Tìm hình ảnh -> core_ban_be -> tab vào
    pos_ban_be = _doi_anh(adb, CORE_BAN_BE, timeout=15, stop_event=stop_event)
    if not pos_ban_be:
        logger.warning("[SANG BẠN BÈ] Không tìm thấy ảnh core_ban_be.png")
        return False

    logger.info("[SANG BẠN BÈ] Tìm thấy nút bạn bè tại %s, tap vào", pos_ban_be)
    adb.tap(*pos_ban_be)

    # 2. chờ 1s -> tab index_mac_dinh_ban_be X=219 Y=656
    _sleep(1.0, stop_event)
    if _should_stop(stop_event):
        return False

    logger.info("[SANG BẠN BÈ] Tap index mặc định bạn bè (%d, %d)", INDEX_MAC_DINH_BAN_BE[0], INDEX_MAC_DINH_BAN_BE[1])
    adb.tap(*INDEX_MAC_DINH_BAN_BE)

    # 3. Đợi xuất hiện hình ảnh -> core_quay_ve thì tab để quay về nhà
    logger.info("[SANG BẠN BÈ] Đợi xuất hiện core_quay_ve.png")
    pos_quay_ve = _doi_anh(adb, CORE_QUAY_VE, timeout=30, stop_event=stop_event)
    if not pos_quay_ve:
        logger.warning("[SANG BẠN BÈ] Không tìm thấy ảnh core_quay_ve.png")
        return False

    logger.info("[SANG BẠN BÈ] Tìm thấy nút quay về tại %s, tap để quay về", pos_quay_ve)
    adb.tap(*pos_quay_ve)

    # 4. Đợi xuất hiện hình ảnh -> core_ban_be -> hoàn thành
    logger.info("[SANG BẠN BÈ] Đợi xuất hiện lại core_ban_be.png để hoàn thành")
    pos_ban_be_lai = _doi_anh(adb, CORE_BAN_BE, timeout=30, stop_event=stop_event)
    if pos_ban_be_lai:
        logger.info("[SANG BẠN BÈ] Đã quay về nhà thành công (thấy core_ban_be.png)")
        record_daily_stat(serial, "sang_ban_be")
        return True
    else:
        logger.warning("[SANG BẠN BÈ] Không thấy core_ban_be.png sau khi quay về")
        return False
