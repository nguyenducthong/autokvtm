import logging
import time

from config import (
    INDEX_THOAT_SAN_XUAT_MAC_DINH,
    INDEX_THUYEN_MAC_DINH,
    INDEX_MO_RUONG_MAC_DINH,
    INDEX_BACK_MAC_DINH,
)
from core.image import ImageProcessor
from utils.daily_stats import record_daily_stat
from utils.utils import tim_may_v2, xuong_nha, setup_thread

logger = logging.getLogger(__name__)
img = ImageProcessor()

CHEST_TEMPLATE = "assets/items/core_chest.png"
RUONG_GO_TEMPLATE = "assets/items/core_ruong_go.png"
CHAM_DE_MO_RUONG = "assets/items/core_cham_de_mo_ruong.png"
OPEN_CHEST_TEMPLATE = "assets/items/core_open_chest.png"
FULL_KHO_TEMPLATE = "assets/items/core_full_kho.png"
CHAM_VAO_DE_MO_TEMPLATE = "assets/items/core_ruong_cham_de_nhan_qua.png"
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
    return time.time() - last >= interval_seconds


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
    """Về tầng 0 bằng logic dùng chung trong utils.tim_may_v2."""
    if _should_stop(stop_event):
        return False
    ok = tim_may_v2("assets/items/num/0.png", 0)
    if not ok:
        logger.warning("[MỞ RƯƠNG] tim_may_v2 về tầng 0 thất bại, chuyển sang xuong_nha")
        xuong_nha()
    return True


def _thoat_mac_dinh(adb, stop_event=None):
    x, y = INDEX_THOAT_SAN_XUAT_MAC_DINH
    adb.tap(x, y)
    _sleep(1.0, stop_event)


def _xu_ly_day_kho(adb, serial: str, stop_event=None):
    logger.warning("[MỞ RƯƠNG] Kho quá tải, đặt cờ đầy kho cho %s", serial)
    _day_kho_flags[serial] = True
    _thoat_mac_dinh(adb, stop_event=stop_event)
    adb.tap(*INDEX_BACK_MAC_DINH)
    _sleep(0.5, stop_event)
    _thoat_mac_dinh(adb, stop_event=stop_event)    


def mo_ruong(adb, serial: str = None, force: bool = False, stop_event=None) -> bool:
    """Mở rương mỗi 20 phút. Trả về True nếu đã xử lý mở rương thành công."""
    serial = serial or getattr(adb, "serial", "unknown")
    setup_thread(adb, stop_event=stop_event, device_name=serial)
    if _should_stop(stop_event):
        return False
    if da_day_kho(serial):
        logger.info("[MỞ RƯƠNG] Bỏ qua vì đã đặt cờ đầy kho: %s", serial)
        return False
    if not force and not can_mo_ruong(serial):
        return False

    _last_run_at[serial] = time.time()
    logger.info("[MỞ RƯƠNG] Kiểm tra rương ở tầng 0: %s", serial)
    _ve_tang_0(adb, stop_event=stop_event)
    if _should_stop(stop_event):
        return False

    pos_chest = _tim_anh(adb, CHEST_TEMPLATE, threshold=0.82)
    if not pos_chest:
        logger.info("[MỞ RƯƠNG] Chưa thấy chest.png")
        return False

    logger.info("[MỞ RƯƠNG] Thấy chest.png, vào thuyền")
    adb.tap(*INDEX_THUYEN_MAC_DINH)
    _sleep(2.0, stop_event)
    # Step 1: Tìm ảnh rưởng gỗ -> ẩn mở
    pos_ruong = _doi_anh(adb, RUONG_GO_TEMPLATE, timeout=2, interval=1, threshold=0.82, stop_event=stop_event)
    if not pos_ruong:
        logger.info("[MỞ RƯƠNG] Không thấy ruong_go.png, thoát")
        _thoat_mac_dinh(adb, stop_event=stop_event)
        return False
    
    pos_cham_de_mo_ruong = _doi_anh(adb, CHAM_DE_MO_RUONG, timeout=2, interval=1, threshold=0.82, stop_event=stop_event)
    logger.info("[MỞ RƯƠNG] Tìm ảnh cham_de_mo_ruong.png, tap để mở rương")
    if pos_cham_de_mo_ruong:
        logger.info("[MỞ RƯƠNG] Thấy cham_de_mo_ruong.png")
        mo_ruong = xu_ly_cham_mo_ruong(adb, serial, stop_event)
        if not mo_ruong:
            return False
    else:
        logger.info("[MỞ RƯƠNG] Không thấy cham_de_mo_ruong.png, tap để mở rương")
        _sleep(1.5, stop_event)
        # Tap mở rương
        adb.tap(*INDEX_MO_RUONG_MAC_DINH)
        _sleep(1.0, stop_event) 
        pos_cham_de_mo_ruong = _doi_anh(adb, CHAM_DE_MO_RUONG, timeout=1, interval=1, threshold=0.82, stop_event=stop_event)
        if pos_cham_de_mo_ruong:
            mo_ruong = xu_ly_cham_mo_ruong(adb, serial, stop_event)
            if not mo_ruong:
                return False

    logger.info("[MỞ RƯƠNG] Check lại lần cuối ảnh cham_de_mo_ruong.png, tap để nhân quà")
    pos_cham_de_mo_ruong = _doi_anh(adb, CHAM_DE_MO_RUONG, timeout=1, interval=1, threshold=0.82, stop_event=stop_event)
    if pos_cham_de_mo_ruong:
        mo_ruong = xu_ly_cham_mo_ruong(adb, serial, stop_event)
        if not mo_ruong:
            return False
    _thoat_mac_dinh(adb, stop_event=stop_event)
    logger.info("[MỞ RƯƠNG] Đã mở rương thành công")
    record_daily_stat(serial, "mo_ruong")
    return True

def xu_ly_cham_mo_ruong(adb, serial, stop_event):
    _sleep(1.5, stop_event)
    # Tap mở rương
    adb.tap(*INDEX_MO_RUONG_MAC_DINH)
    _sleep(1.5, stop_event)
    # Tap nhân quà
    adb.tap(*INDEX_MO_RUONG_MAC_DINH)
    _sleep(1.5, stop_event)
    
    full_kho = _doi_anh(adb, FULL_KHO_TEMPLATE, timeout=1, interval=1, threshold=0.82, stop_event=stop_event)
    if full_kho:
        logger.info("[MỞ RƯƠNG] Kho đầy sau khi mở rương")
        _xu_ly_day_kho(adb, serial, stop_event=stop_event)
        return False
    return True

if __name__ == "__main__":
    import sys
    from core.adb_helper import get_adb_helper
    from core.adb import ADBController

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    helper = get_adb_helper()
    devices = helper.get_devices()
    if not devices:
        print("❌ Không tìm thấy thiết bị LDPlayer nào đang kết nối!")
        sys.exit(1)

    target_serial = devices[0]
    dev_name = helper.get_device_name(target_serial)
    print(f"🚀 Bắt đầu test Mở Rương trên thiết bị: {dev_name} ({target_serial})")

    adb = ADBController(serial=target_serial)
    ok = mo_ruong(adb, serial=target_serial, force=True)
    if ok:
        print("✅ Test Mở Rương THÀNH CÔNG!")
    else:
        print("❌ Test Mở Rương THẤT BẠI hoặc KHÔNG THỰC HIỆN!")
