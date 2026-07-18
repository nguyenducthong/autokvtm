import logging
import time

from config import GAME_ACTIVITY_NAME, GAME_PACKAGE_NAME, INDEX_THOAT_SAN_XUAT_MAC_DINH
from core.adb import ADBController
from core.adb_helper import get_adb_helper
from core.image import ImageProcessor

logger = logging.getLogger(__name__)
img = ImageProcessor()

TAI_KHOAN_TEMPLATE = "assets/items/tai_khoan.png"
TAI_KHOAN_ON_TEMPLATE = "assets/items/tai_khoan_on.png"
ICON_GAME_TEMPLATE = "assets/items/icon_game.png"
CHECK_LOG_GAME_TEMPLATE = "assets/items/check_log_game.png"

def doi_thiet_bi_adb(serial: str, timeout: int = 75, interval: float = 2.0) -> bool:
    """Doi LDPlayer xuat hien trong adb devices."""
    helper = get_adb_helper()
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            if serial in helper.get_devices():
                return True
        except Exception as e:
            logger.debug("Chua doc duoc adb devices: %s", e)
        time.sleep(interval)
    return False


def vao_game(
    serial: str,
    package_name: str = None,
    activity: str = None,
    wait_timeout: int = 75,
) -> bool:
    """Mo game tren LDPlayer sau khi thiet bi da san sang qua ADB."""
    package_name = package_name or GAME_PACKAGE_NAME
    activity = activity if activity is not None else GAME_ACTIVITY_NAME
    if not package_name:
        raise ValueError("Chua cau hinh GAME_PACKAGE_NAME trong config.py")

    logger.info("[VAO_GAME] Doi ADB san sang: %s", serial)
    if not doi_thiet_bi_adb(serial, timeout=wait_timeout):
        logger.error("[VAO_GAME] Qua thoi gian doi ADB: %s", serial)
        return False

    logger.info("[VAO_GAME] Mo game %s tren %s", package_name, serial)
    adb = ADBController(serial=serial)
    adb.open_app(package_name, activity)
    time.sleep(10)
    return xu_ly_man_hinh_vao_game(adb)


def vao_game_sau_khi_start_ld(serial: str, wait_timeout: int = 75) -> bool:
    return vao_game(serial=serial, wait_timeout=wait_timeout)


def _tim_anh(adb: ADBController, template_path: str, threshold: float = 0.82):
    screen = adb.screenshot_full()
    if screen is None:
        return None, None
    pos = img.find_template_color(template_path=template_path, threshold=threshold, screen_img=screen)
    return pos, screen


def _doi_anh(adb: ADBController, template_path: str, timeout: int, interval: float = 1.5,
             threshold: float = 0.82):
    end_time = time.time() + timeout
    while time.time() < end_time:
        pos, screen = _tim_anh(adb, template_path, threshold=threshold)
        if pos:
            return pos, screen
        time.sleep(interval)
    return None, None


def _tap_tai_khoan_den_khi_on(adb: ADBController, timeout: int = 45) -> bool:
    end_time = time.time() + timeout
    while time.time() < end_time:
        pos_on, _ = _tim_anh(adb, TAI_KHOAN_ON_TEMPLATE, threshold=0.82)
        if pos_on:
            logger.info("[VAO_GAME] Tai khoan da duoc chon")
            return True

        pos, _ = _tim_anh(adb, TAI_KHOAN_TEMPLATE, threshold=0.82)
        if pos:
            logger.info("[VAO_GAME] Tap tai khoan tai %s", pos)
            adb.tap(*pos)
            time.sleep(2)
            continue

        logger.info("[VAO_GAME] Chua thay nut tai khoan, doi tiep...")
        time.sleep(1.5)
    return False


def _dong_popup_quang_cao(adb: ADBController, count: int = 5, interval: float = 2.0):
    x, y = INDEX_THOAT_SAN_XUAT_MAC_DINH
    for i in range(count):
        logger.info("[VAO_GAME] Dong popup/quang cao %s/%s tai (%s,%s)", i + 1, count, x, y)
        adb.tap(x, y)
        time.sleep(interval)


def xu_ly_man_hinh_vao_game(adb: ADBController) -> bool:
    """Chon tai khoan, doi vao game va dong popup sau khi app da mo."""
    logger.info("[VAO_GAME] Doi man hinh tai khoan")
    if not _tap_tai_khoan_den_khi_on(adb, timeout=60):
        logger.warning("[VAO_GAME] Khong chon duoc tai khoan trong thoi gian cho")
        return False

    logger.info("[VAO_GAME] Doi icon game xuat hien")
    pos_icon, _ = _doi_anh(adb, ICON_GAME_TEMPLATE, timeout=60, interval=2, threshold=0.82)
    if pos_icon:
        logger.info("[VAO_GAME] Da thay icon game tai %s", pos_icon)
        adb.tap(*pos_icon)
    else:
        logger.warning("[VAO_GAME] Chua thay icon_game.png, van tiep tuc doi load")

    logger.info("[VAO_GAME] Doi game load 40s")
    time.sleep(40)
    pos_log_game, _ = _tim_anh(adb, CHECK_LOG_GAME_TEMPLATE, threshold=0.82)
    if pos_log_game:
        logger.info("[VAO_GAME] Da thay log game tai %s", pos_log_game)
        _dong_popup_quang_cao(adb, count=5, interval=2)
        return True
    else:
        logger.warning("[VAO_GAME] Chua thay log_game.png")
        return False
