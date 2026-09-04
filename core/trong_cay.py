import sys
import os

from adbutils import adb
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from .adb import ADBController
from .image import ImageProcessor
from utils.utils import (
    lay_toa_do_tu_indexs, tim_may, find_image_v2,
    setup_thread, _should_stop, _sleep, _get_adb, get_device_name,
    set_state, get_state, PlayerState,
    save_debug_image, is_debug_mode, set_thread_status
)
from config import (
    DEVICE_SERIAL, INDEX_HANG, CONFIG_TEMP_TC, INDEX_MAY,
    INDEX_SAN_XUAT_MAC_DINH, INDEX_NEXT_SAN_XUAT_MAC_DINH, INDEX_SUA_MAY_MAC_DINH,
    INDEX_THOAT_SAN_XUAT_MAC_DINH,
    TIME_SLEEP_TRONG_CAY as TIME_SLEEP,
    TIME_SLEEP_SHORT_TRONG_CAY as TIME_SLEEP_SHORT
)
import time
import logging
from .thu_hoach import thuhoach
from .san_xuat import xu_ly_may, sua_may, tim_vp

THRESHOLD = 0.85
logger = logging.getLogger(__name__)
img = ImageProcessor()

DEBUG_MODE = False
DEBUG_DIR = "debug/trong_cay"

def set_debug_mode(enabled: bool):
    """Bật/tắt debug mode lưu ảnh cho phần trồng cây."""
    global DEBUG_MODE
    DEBUG_MODE = enabled
    if enabled:
        os.makedirs(DEBUG_DIR, exist_ok=True)
        logger.info(f"[DEBUG] Trong cay debug mode ON — lưu ảnh tại {DEBUG_DIR}/")

def _save_debug_screenshot(screen, template_path, pos, step_name, region=None):
    """Lưu ảnh debug nếu debug mode bật."""
    if not (DEBUG_MODE or is_debug_mode()) or screen is None:
        return
    save_debug_image(screen, template_path, pos, step_name=step_name, debug_dir=DEBUG_DIR, region=region)


def main_tc(config: list, adb_instance=None, stop_event=None, stop_callback=None,
            global_threshold=None, is_sua_may: bool = False):
    """
    Chạy auto farm theo config.
    Mỗi thread gọi hàm này với adb_instance + stop_event riêng.
    global_threshold: threshold mặc định từ settings, dùng khi task không có threshold riêng.
    """
    # Giữ device_name đã set trước đó (từ GUI thread)
    _dev_name = get_device_name()
    if adb_instance and stop_event:
        setup_thread(adb_instance, stop_event, device_name=_dev_name)
    elif adb_instance:
        setup_thread(adb_instance, device_name=_dev_name)
    # thu_hoach giờ dùng _get_adb() từ thread-local, không cần gán global nữa

    adb = _get_adb()
    if not adb:
        raise RuntimeError("ADB chưa được khởi tạo! Truyền adb_instance vào main_tc()")

    for idx, item in enumerate(config, 1):
        if _should_stop():
            logger.info("Dừng auto farm theo yêu cầu")
            break
        config_row = item.get('row')
        path_may = item.get('path_row')
        type_item = item['type']
        logger.info(f"--- Xử lý config {idx}/{len(config)}: Loại {type_item} ---")
        if not path_may:
            logger.warning(f"Config thiếu path_row, bỏ qua")
            continue

        logger.info(f"Xử lý config {idx}/{len(config)}: Hàng {item.get('row')}")

        # Tìm máy/hàng
        check = tim_may(path_may, config_row)
        logger.info(f"Kết quả tìm máy/hàng: {check}, hàng cấu hình: {config_row}")
        if check == False:
            logger.info("LỖI: Tìm mây bỏ qua cấu hình")
            continue

        if _should_stop():
            logger.info("Dừng trước khi xử lý")
            break

        if type_item == "MAY":
            logger.info(f"Xử lý máy sản xuất hàng {item.get('row')}...")
            set_thread_status(f"Máy SX hàng {config_row} ({idx}/{len(config)})...")
            set_state(PlayerState.MO_MAY)
            xu_ly_may(item, threshold=global_threshold or THRESHOLD, is_sua_may=is_sua_may)

        elif type_item == "TC":
            set_thread_status(f"Kiểm tra hàng {config_row} ({idx}/{len(config)})...")
            path_cay = item.get('path_item')
            path_cay_default = item.get('path_item_default')
            region = item.get('region')
            # Ưu tiên: threshold per-task > global_threshold > THRESHOLD code
            item_threshold = item.get('threshold', global_threshold or THRESHOLD)
            if not item.get('indexs'):
                logger.warning("Config TC thiếu indexs, bỏ qua")
                continue

            listIndex = lay_toa_do_tu_indexs(item['indexs'])
            tap = listIndex[3]
            x, y = tap
            adb.tap(x, y)
            _sleep(TIME_SLEEP)
            check_trong = check_trong_cay(threshold=item_threshold, is_retry=True, tap=(x, y))
            if check_trong == "chua_chin":
                logger.info("Cây chưa chín, bỏ qua thu hoạch")
                set_thread_status(f"Cây hàng {config_row} chưa chín", "#7f8c8d")
                continue
            elif check_trong == "next_gieo":
                logger.info("Chuyển sang cây tiếp theo")
                if _should_stop():
                    break
                set_thread_status(f"Trồng cây hàng {config_row}...")
                set_state(PlayerState.TRONG_CAY)
                trong_cay(path_cay, path_cay_default, listIndex, tap,
                          threshold=item_threshold, region=region)
            elif check_trong == "gio_hang":
                logger.info("Tìm thấy giỏ hàng, tiến hành thu hoạch")
                set_thread_status(f"Thu hoạch hàng {config_row}...")
                set_state(PlayerState.THU_HOACH)
                thuhoach(listIndex, tap, threshold=item_threshold)
                adb.tap(x, y)
                _sleep(TIME_SLEEP)
                set_thread_status(f"Gieo hạt hàng {config_row}...")
                set_state(PlayerState.TRONG_CAY)
                trong_cay(path_cay, path_cay_default, listIndex, tap,
                          threshold=item_threshold, region=region)

        logger.info(f"Hoàn thành config {idx}/{len(config)}")

    logger.info("Hoàn thành tất cả config")


def tim_cay_trong(template_path, template_path_default=None, count=1,
                  threshold: float=THRESHOLD, region=None):
    """Tìm cây để gieo. Tối ưu: 1 screenshot cho cả cây + next_gieo.

    - count 1-3: tìm template chính (VD: cay_bong.png)
    - count 4-5: tìm template mặc định (VD: cay_hong.png)
    - count > 5: bỏ cuộc
    Giữa mỗi lần thử, bấm next_gieo để lật trang.
    """
    adb = _get_adb()
    if _should_stop():
        return None

    set_state(PlayerState.TIM_CAY)
    tpl_name = os.path.basename(template_path).replace(".png", "")
    next_gieo = "assets/items/core_next_gieo.png"

    if count > 5:
        logger.info(f"Đã thử tìm cây {count} lần, dừng tìm kiếm")
        return None

    # Chụp 1 screenshot dùng cho cả tìm cây + tìm next_gieo
    screen = adb.screenshot_full()
    if screen is None:
        return None

    # Chọn template cần tìm
    if count <= 3:
        search_path = template_path
        label = tpl_name
    else:
        search_path = template_path_default
        label = "default"

    # Tìm cây trên screenshot đã chụp (không retry, không chụp lại)
    pos = img.find_template_color(search_path, threshold=threshold, screen_img=screen,
                                  region=region)
    _save_debug_screenshot(screen, search_path, pos, f"tim_cay_lan_{count}", region=region)
    if pos:
        logger.info(f"Tìm được {label} tại {pos} (lần {count}, threshold={threshold})")
        return pos

    # Không thấy cây → tìm nút next_gieo trên cùng screenshot
    logger.info(f"Không tìm được {label} lần {count}")
    pos_next = img.find_template_color(next_gieo, threshold=threshold, screen_img=screen)
    _save_debug_screenshot(screen, next_gieo, pos_next, f"tim_next_gieo_lan_{count}")
    if pos_next:
        x, y = pos_next
        adb.tap(x, y)
        _sleep(TIME_SLEEP_SHORT)
        return tim_cay_trong(template_path, template_path_default, count + 1,
                             threshold=threshold, region=region)
    else:
        logger.info(f"Không tìm thấy nút next_gieo")
        return None


def trong_cay(template_path, template_path_default, points: list, tap,
              duration_ms: int = 800, threshold: float = THRESHOLD, region=None):
    """Trồng cây: tìm icon cây → kéo qua các vị trí.
    duration_ms giảm từ 1500 → 800ms cho nhanh hơn."""
    adb = _get_adb()
    x, y = tap

    pos = tim_cay_trong(template_path, template_path_default, threshold=threshold,
                        region=region)
    logger.info(f"Tìm cây tại: {pos}")

    if pos:
        path_points = [pos] + list(points)
        logger.info(f"Kéo cây từ {pos} qua {len(path_points)-1} vị trí")
        adb.drag_smooth(path_points, total_duration_ms=duration_ms)
        time.sleep(0.3)
    else:
        logger.warning("Không tìm thấy loại cây, tap lại")
        adb.tap(*INDEX_THOAT_SAN_XUAT_MAC_DINH)



def check_trong_cay(threshold=None, is_retry = False, tap = None):
    """Kiểm tra trạng thái cây: giỏ hàng / next_gieo / chưa chín.
    Tối ưu: chụp 1 screenshot, tìm tất cả template trên cùng ảnh đó."""
    th = threshold or THRESHOLD
    adb = _get_adb()
    screen = adb.screenshot_full()
    if screen is None:
        return "chua_chin"

    # Tìm tất cả trên cùng 1 screenshot (không retry, không chụp lại)
    pos_TH = img.find_template_color("assets/items/core_thu_hoach.png", threshold=th, screen_img=screen)
    if pos_TH:
        _save_debug_screenshot(screen, "assets/items/core_thu_hoach.png", pos_TH, "check_gio_hang")
        logger.info("Tìm được giỏ hàng (thu_hoach)")
        return "gio_hang"
    pos_TH = img.find_template_color("assets/items/core_thu_hoach_1.png", threshold=th, screen_img=screen)
    if pos_TH:
        _save_debug_screenshot(screen, "assets/items/core_thu_hoach_1.png", pos_TH, "check_gio_hang_1")
        logger.info("Tìm được giỏ hàng (thu_hoach_1)")
        return "gio_hang"
    pos = img.find_template_color("assets/items/core_next_gieo.png", threshold=th, screen_img=screen)
    if pos:
        _save_debug_screenshot(screen, "assets/items/core_next_gieo.png", pos, "check_next_gieo")
        logger.info("Tìm được nút next gieo")
        return "next_gieo"
    pos_cay_chin = img.find_template_color("assets/items/core_cay_chua_chin.png", threshold=th, screen_img=screen)
    if pos_cay_chin:
        _save_debug_screenshot(screen, "assets/items/core_cay_chua_chin.png", pos_cay_chin, "check_cay_chua_chin")
        logger.info("Tìm được cây chưa chín")
        return "chua_chin"

    _save_debug_screenshot(screen, "assets/items/core_thu_hoach.png", None, "check_trong_cay_khong_thay")
    if is_retry:
        logger.info("Chưa ấn vào cây, tiến hành ấn vào cây")
        adb.tap(tap[0], tap[1])
        _sleep(TIME_SLEEP_SHORT)
        return check_trong_cay(threshold=th, is_retry=False, tap=tap)
    return "chua_chin"


# Ghi chú: Logic xử lý máy sản xuất (xu_ly_may, sua_may, tim_vp) đã được tách riêng sang module core/san_xuat.py
# và được import ở đầu file để đảm bảo tương thích ngược hoàn toàn.

