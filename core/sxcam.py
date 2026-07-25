import logging
import time
from config import INDEX_THOAT_SAN_XUAT_MAC_DINH, INDEX_SXCAM
from core.image import ImageProcessor
from utils.utils import tim_may_v2, xuong_nha

logger = logging.getLogger(__name__)
img = ImageProcessor()

SXCAM_INTERVAL_SECONDS = 30 * 60  # 30 minutes
_last_run_at = {}

def can_sxcam(serial: str) -> bool:
    """Kiểm tra xem đã đủ 30 phút kể từ lần chạy trước chưa."""
    last = _last_run_at.get(serial, 0)
    return time.time() - last >= SXCAM_INTERVAL_SECONDS

def _sleep(seconds, stop_event=None):
    if stop_event is not None:
        stop_event.wait(seconds)
    else:
        time.sleep(seconds)

def _should_stop(stop_event=None):
    return stop_event is not None and stop_event.is_set()

def _tim_anh(adb, template_path: str, threshold: float = 0.85):
    screen = adb.screenshot_full()
    if screen is None:
        return None
    return img.find_template_color(template_path=template_path, threshold=threshold, screen_img=screen)

def _ve_tang_0(adb, stop_event=None):
    """Về tầng 0 bằng logic dùng chung trong utils.tim_may_v2."""
    if _should_stop(stop_event):
        return False
    ok = tim_may_v2("assets/items/num/0.png", 0)
    if not ok:
        logger.warning("[SXCAM] tim_may_v2 về tầng 0 thất bại, chuyển sang xuong_nha")
        xuong_nha()
    return True

def _thoat_mac_dinh(adb, stop_event=None):
    x, y = INDEX_THOAT_SAN_XUAT_MAC_DINH
    adb.tap(x, y)
    _sleep(1.0, stop_event)

def run_sxcam(adb, serial: str = None, force: bool = False, stop_event=None) -> bool:
    """Sản xuất cám mỗi 30 phút. Trả về True nếu chạy thành công."""
    serial = serial or getattr(adb, "serial", "unknown")
    if _should_stop(stop_event):
        return False
    if not force and not can_sxcam(serial):
        return False

    _last_run_at[serial] = time.time()
    logger.info("[SXCAM] Bắt đầu tiến trình sản xuất cám cho %s", serial)
    
    # 1. Về tầng 0
    _ve_tang_0(adb, stop_event=stop_event)
    if _should_stop(stop_event):
        return False

    # 2. Ở tầng 0 tìm ảnh sxcam_soi.png -> tìm được tab vào. -> đợi 2-3s
    pos_soi = _tim_anh(adb, "assets/items/sxcam_soi.png", threshold=0.85)
    if not pos_soi:
        logger.warning("[SXCAM] Không tìm thấy sxcam_soi.png ở tầng 0")
        return False

    logger.info("[SXCAM] Thấy sxcam_soi.png, click vào")
    adb.tap(*pos_soi)
    _sleep(2.5, stop_event)

    if _should_stop(stop_event):
        return False

    # 3. kiểm tra có sxcam_log.png thì nhấn tap_thoat_mac_dinh. -> kéo sang trái tìm hình ảnh sxcam_sx.png ->tab vào.
    pos_log = _tim_anh(adb, "assets/items/sxcam_log.png", threshold=0.85)
    if pos_log:
        logger.info("[SXCAM] Phát hiện sxcam_log.png, nhấn thoát mặc định")
        _thoat_mac_dinh(adb, stop_event)
        if _should_stop(stop_event):
            return False

    found_sx = False
    for attempt in range(5):
        if _should_stop(stop_event):
            return False
        pos_sx = _tim_anh(adb, "assets/items/sxcam_sx.png", threshold=0.8)
        if pos_sx:
            logger.info("[SXCAM] Tìm thấy sxcam_sx.png tại %s, tap vào", pos_sx)
            adb.tap(*pos_sx)
            _sleep(2.0, stop_event)
            found_sx = True
            break
        else:
            logger.info("[SXCAM] Chưa tìm thấy sxcam_sx.png ở lần thử %d, vuốt sang trái", attempt + 1)
            # Vuốt từ phải sang trái để cuộn menu
            adb.swipe(600, 500, 200, 500, 500)
            _sleep(1.0, stop_event)

    if not found_sx:
        logger.warning("[SXCAM] Không tìm thấy sxcam_sx.png sau 5 lần thử, thoát")
        _thoat_mac_dinh(adb, stop_event)
        return False

    if _should_stop(stop_event):
        return False

    # 4. tìm ảnh sxcam_luami.png thì kéo vị trí đó đến index_sxcam.
    pos_luami = _tim_anh(adb, "assets/items/sxcam_luami.png", threshold=0.8)
    if pos_luami:
        logger.info("[SXCAM] Tìm thấy sxcam_luami.png tại %s, kéo đến INDEX_SXCAM %s", pos_luami, INDEX_SXCAM)
        x_lm, y_lm = pos_luami
        x_sx, y_sx = INDEX_SXCAM
        
        adb.swipe(x_lm, y_lm, x_sx, y_sx, 200)
        _sleep(0.5, stop_event)
    else:
        logger.warning("[SXCAM] Không tìm thấy sxcam_luami.png để sản xuất")

    if _should_stop(stop_event):
        return False

    # 5. Bấm thoát mặc đinh. Tìm ảnh sxcam_venha.png để về ->đợi 5s chờ load lại màn hình
    logger.info("[SXCAM] Bấm thoát mặc định")
    _thoat_mac_dinh(adb, stop_event)
    if _should_stop(stop_event):
        return False
    _sleep(1.5, stop_event)

    pos_venha = _tim_anh(adb, "assets/items/sxcam_venha.png", threshold=0.8)
    if pos_venha:
        logger.info("[SXCAM] Tìm thấy sxcam_venha.png, click để về nhà")
        adb.tap(*pos_venha)
        _sleep(5.0, stop_event)
    else:
        logger.warning("[SXCAM] Không tìm thấy sxcam_venha.png để về nhà")

    logger.info("[SXCAM] Hoàn thành tiến trình sản xuất cám")
    return True
