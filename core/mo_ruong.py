import logging
import time

from config import (
    INDEX_THOAT_SAN_XUAT_MAC_DINH,
    INDEX_THUYEN_MAC_DINH,
    INDEX_XUONG_NHA_MAC_DINH,
)
from core.image import ImageProcessor

logger = logging.getLogger(__name__)
img = ImageProcessor()

CHEST_TEMPLATE = "assets/items/chest.png"
RUONG_GO_TEMPLATE = "assets/items/ruong_go.png"
OPEN_CHEST_TEMPLATE = "assets/items/open_chest.png"
BACK_TEMPLATE = "assets/items/back.png"

RUONG_INTERVAL_SECONDS = 20 * 60

_day_kho_flags = {}
_last_run_at = {}


def da_day_kho(serial: str) -> bool:
    return bool(_day_kho_flags.get(serial))


def reset_day_kho(serial: str = None):
    if serial is None:
        _day_kho_flags.clear()
    else:
        _day_kho_flags.pop(serial, None)


def can_mo_ruong(serial: str, interval_seconds: int = RUONG_INTERVAL_SECONDS) -> bool:
    if da_day_kho(serial):
        return False
    last = _last_run_at.get(serial, 0)
    # return time.time() - last >= interval_seconds
    return True  # bỏ check thời gian để có thể chạy lại ngay khi reset_day_kho


def _sleep(seconds, stop_event=None):
    if stop_event is not None:
        stop_event.wait(seconds)
    else:
        time.sleep(seconds)


def _should_stop(stop_event=None):
    return stop_event is not None and stop_event.is_set()


def _tim_anh(adb, template_path: str, threshold: float = 0.82):
    screen = adb.screenshot_full()
    if screen is None:
        return None
    return img.find_template_color(template_path=template_path, threshold=threshold, screen_img=screen)


def _doi_anh(adb, template_path: str, timeout: int = 12, interval: float = 1.0,
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


def _ve_tang_0(adb, stop_event=None):
    x, y = INDEX_XUONG_NHA_MAC_DINH
    for _ in range(2):
        if _should_stop(stop_event):
            return
        adb.tap(x, y)
        _sleep(1.0, stop_event)


def _thoat_mac_dinh(adb, stop_event=None):
    x, y = INDEX_THOAT_SAN_XUAT_MAC_DINH
    adb.tap(x, y)
    _sleep(1.0, stop_event)


def _xu_ly_day_kho(adb, serial: str, stop_event=None):
    logger.warning("[MO_RUONG] Kho qua tai, dat co day kho cho %s", serial)
    _day_kho_flags[serial] = True
    _thoat_mac_dinh(adb, stop_event=stop_event)
    pos_back = _doi_anh(adb, BACK_TEMPLATE, timeout=8, interval=1, threshold=0.82, stop_event=stop_event)
    if pos_back:
        adb.tap(*pos_back)
        _sleep(1.0, stop_event)


def mo_ruong(adb, serial: str = None, force: bool = False, stop_event=None) -> bool:
    """Mo ruong moi 20 phut. Tra ve True neu da xu ly mo ruong thanh cong."""
    serial = serial or getattr(adb, "serial", "unknown")
    if _should_stop(stop_event):
        return False
    if da_day_kho(serial):
        logger.info("[MO_RUONG] Bo qua vi da dat co day kho: %s", serial)
        return False
    if not force and not can_mo_ruong(serial):
        return False

    _last_run_at[serial] = time.time()
    logger.info("[MO_RUONG] Kiem tra ruong o tang 0: %s", serial)
    _ve_tang_0(adb, stop_event=stop_event)
    if _should_stop(stop_event):
        return False

    pos_chest = _tim_anh(adb, CHEST_TEMPLATE, threshold=0.82)
    if not pos_chest:
        logger.info("[MO_RUONG] Chua thay chest.png")
        return False

    logger.info("[MO_RUONG] Thay chest.png, vao thuyen")
    adb.tap(*INDEX_THUYEN_MAC_DINH)
    _sleep(2.0, stop_event)

    pos_ruong = _doi_anh(adb, RUONG_GO_TEMPLATE, timeout=12, interval=1, threshold=0.82, stop_event=stop_event)
    if not pos_ruong:
        logger.info("[MO_RUONG] Khong thay ruong_go.png, thoat")
        _thoat_mac_dinh(adb, stop_event=stop_event)
        return False
    adb.tap(*pos_ruong)
    _sleep(1.5, stop_event)

    pos_open = _doi_anh(adb, OPEN_CHEST_TEMPLATE, timeout=12, interval=1, threshold=0.82, stop_event=stop_event)
    if not pos_open:
        logger.info("[MO_RUONG] Khong thay open_chest.png, coi nhu kho qua tai")
        _xu_ly_day_kho(adb, serial, stop_event=stop_event)
        return False

    logger.info("[MO_RUONG] Mo ruong tai %s", pos_open)
    adb.tap(*pos_open)
    _sleep(1.5, stop_event)

    pos_open_again = _doi_anh(adb, OPEN_CHEST_TEMPLATE, timeout=6, interval=1, threshold=0.82, stop_event=stop_event)
    if not pos_open_again:
        logger.info("[MO_RUONG] Mat nut open_chest som, coi nhu kho qua tai")
        _xu_ly_day_kho(adb, serial, stop_event=stop_event)
        return False
    pos_open = pos_open_again

    adb.tap(*pos_open)
    _sleep(1.5, stop_event)

    pos_open_again = _doi_anh(adb, OPEN_CHEST_TEMPLATE, timeout=6, interval=1, threshold=0.82, stop_event=stop_event)
    if pos_open_again:
        pos_open = pos_open_again
    adb.tap(*pos_open)
    _sleep(1.5, stop_event)

    _thoat_mac_dinh(adb, stop_event=stop_event)
    logger.info("[MO_RUONG] Da mo ruong thanh cong")
    return True
