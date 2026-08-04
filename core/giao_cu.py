import logging
import os
import time

from config import INDEX_MAC_DINH_GIAO_CU, INDEX_THOAT_SAN_XUAT_MAC_DINH, INDEX_XOA_DON_GIAO_CU
from core.image import ImageProcessor
from utils.daily_stats import record_daily_stat

logger = logging.getLogger(__name__)
img = ImageProcessor()

GIAO_CU_CO_DON = "assets/items/core_giao_cu_co_don.png"
GIAO_CU_GIAO_DON = "assets/items/core_giao_cu_giao_don.png"
GIAO_CU_DON_HANG_OFF = "assets/items/core_giao_cu_don_hang_off.png"
GIAO_CU_BACK = "assets/items/core_back.png"
GIAO_CU_DONG_Y = "assets/items/giao_cu_dong_y.png"
GIAO_CU_INTERVAL_SECONDS = 31 * 60

_last_run_at = {}


def can_giao_cu(serial: str, interval_seconds: int = GIAO_CU_INTERVAL_SECONDS) -> bool:
    last = _last_run_at.get(serial, 0)
    return time.time() - last >= interval_seconds


def reset_giao_cu_timer(serial: str = None):
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
    if not os.path.exists(template_path):
        logger.warning("[GIAO CÚ] Thiếu ảnh mẫu: %s", template_path)
        return None
    screen = adb.screenshot_full()
    if screen is None:
        return None
    return img.find_template_color(template_path=template_path, threshold=threshold, screen_img=screen)


def _doi_anh(adb, template_path: str, timeout: int = 20, interval: float = 1.0,
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


def _tap_neu_thay(adb, template_path: str, timeout: int = 8, stop_event=None) -> bool:
    pos = _doi_anh(adb, template_path, timeout=timeout, interval=1, stop_event=stop_event)
    if not pos:
        return False
    adb.tap(*pos)
    _sleep(1.0, stop_event)
    return True


def _thoat_popup(adb, stop_event=None):
    adb.tap(*INDEX_THOAT_SAN_XUAT_MAC_DINH)
    _sleep(1.0, stop_event)
    _tap_neu_thay(adb, GIAO_CU_BACK, timeout=4, stop_event=stop_event)


def _co_vat_pham_bo_qua(adb, dsvp_bo_qua, threshold: float = 0.82) -> bool:
    for item in dsvp_bo_qua or []:
        path = item.get("path") if isinstance(item, dict) else item
        if not path:
            continue
        if not os.path.isabs(path) and not path.startswith("assets/"):
            path = os.path.join("assets/items", path)
        if _tim_anh(adb, path, threshold=threshold):
            logger.info("[GIAO CÚ] Đơn có vật phẩm bỏ qua: %s", path)
            return True
    return False


def giao_cu(adb, serial: str = None, dsvp_bo_qua=None, force: bool = False, stop_event=None) -> bool:
    """Xử lý giao cú theo chu kỳ 30 phút."""
    serial = serial or getattr(adb, "serial", "unknown")
    if _should_stop(stop_event):
        return False
    if not force and not can_giao_cu(serial):
        return False

    _last_run_at[serial] = time.time()
    logger.info("[GIAO CÚ] Mở popup giao cú: %s", serial)
    adb.tap(*INDEX_MAC_DINH_GIAO_CU)
    _sleep(1.5, stop_event)

    handled = False
    for _ in range(20):
        if _should_stop(stop_event):
            return handled

        pos_don = _tim_anh(adb, GIAO_CU_CO_DON, threshold=0.82)
        if pos_don:
            handled = True
            adb.tap(*pos_don)
            _sleep(1.0, stop_event)

            if _co_vat_pham_bo_qua(adb, dsvp_bo_qua, threshold=0.82):
                logger.info("[GIAO CÚ] Xóa đơn vì có vật phẩm bỏ qua")
                adb.tap(*INDEX_XOA_DON_GIAO_CU)
                _sleep(0.5, stop_event)
            else:
                logger.info("[GIAO CÚ] Đợi nút giao đơn")
                if _tap_neu_thay(adb, GIAO_CU_GIAO_DON, timeout=20, stop_event=stop_event):
                    record_daily_stat(serial, "giao_cu")
                _tap_neu_thay(adb, GIAO_CU_DONG_Y, timeout=1, stop_event=stop_event)
            _sleep(1.0, stop_event)
            continue

        pos_off = _tim_anh(adb, GIAO_CU_DON_HANG_OFF, threshold=0.82)
        if pos_off:
            handled = True
            adb.tap(*pos_off)
            _sleep(1.0, stop_event)
            logger.info("[GIAO CÚ] Xóa đơn tắt")
            adb.tap(*INDEX_XOA_DON_GIAO_CU)
            _sleep(0.5, stop_event)
            continue

        break

    _thoat_popup(adb, stop_event=stop_event)
    return handled
