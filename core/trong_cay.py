import sys
import os

from adbutils import adb
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from .adb import ADBController
from .image import ImageProcessor
from utils.utils import (
    lay_toa_do_tu_indexs, tim_may, find_image_v2,
    setup_thread, _should_stop, _sleep, _get_adb, get_device_name,
    set_state, get_state, PlayerState
)
from config import (
    DEVICE_SERIAL, INDEX_HANG, CONFIG_TEMP_TC, INDEX_MAY,
    INDEX_SAN_XUAT_MAC_DINH, INDEX_NEXT_SAN_XUAT_MAC_DINH, INDEX_SUA_MAY_MAC_DINH,
    INDEX_THOAT_SAN_XUAT_MAC_DINH
)
import time
import logging
from .thu_hoach import thuhoach

THRESHOLD = 0.85
logger = logging.getLogger(__name__)
TIME_SLEEP = 0.5          # Giảm từ 1s → 0.5s (đủ cho UI update)
TIME_SLEEP_SHORT = 0.3    # Cho các thao tác nhanh (lật trang, tap)
img = ImageProcessor()


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
            set_state(PlayerState.MO_MAY)
            xu_ly_may(item, threshold=global_threshold or THRESHOLD, is_sua_may=is_sua_may)

        elif type_item == "TC":
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
                continue
            elif check_trong == "next_gieo":
                logger.info("Chuyển sang cây tiếp theo")
                if _should_stop():
                    break
                set_state(PlayerState.TRONG_CAY)
                trong_cay(path_cay, path_cay_default, listIndex, tap,
                          threshold=item_threshold, region=region)
            elif check_trong == "gio_hang":
                logger.info("Tìm thấy giỏ hàng, tiến hành thu hoạch")
                set_state(PlayerState.THU_HOACH)
                thuhoach(listIndex, tap, threshold=item_threshold)
                adb.tap(x, y)
                _sleep(TIME_SLEEP)
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
    if pos:
        logger.info(f"Tìm được {label} tại {pos} (lần {count}, threshold={threshold})")
        return pos

    # Không thấy cây → tìm nút next_gieo trên cùng screenshot
    logger.info(f"Không tìm được {label} lần {count}")
    pos_next = img.find_template_color(next_gieo, threshold=threshold, screen_img=screen)
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
        points.insert(0, pos)
        logger.info(f"Kéo cây từ {pos} qua {len(points)-1} vị trí")
        adb.drag_smooth(points, total_duration_ms=duration_ms)
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
        logger.info("Tìm được giỏ hàng (thu_hoach)")
        return "gio_hang"
    pos_TH = img.find_template_color("assets/items/core_thu_hoach_1.png", threshold=th, screen_img=screen)
    if pos_TH:
        logger.info("Tìm được giỏ hàng (thu_hoach_1)")
        return "gio_hang"
    pos = img.find_template_color("assets/items/core_next_gieo.png", threshold=th, screen_img=screen)
    if pos:
        logger.info("Tìm được nút next gieo")
        return "next_gieo"
    pos_cay_chin = img.find_template_color("assets/items/core_cay_chua_chin.png", threshold=th, screen_img=screen)
    if pos_cay_chin:
        logger.info("Tìm được cây chưa chín")
        return "chua_chin"
    if is_retry:
        logger.info("Chưa ấn vào cây, tiến hành ấn vào cây")
        adb.tap(tap[0], tap[1])
        _sleep(TIME_SLEEP_SHORT)
        return check_trong_cay(threshold=th, is_retry=False, tap=tap)
    return "chua_chin"


def xu_ly_may(config_may: dict, threshold: float = THRESHOLD, is_sua_may: bool = False):
    adb = _get_adb()
    row = str(config_may['row'])
    data = config_may.get('data', [])
    region = config_may.get('region')

    if row not in INDEX_MAY:
        logger.error(f"Không tìm thấy INDEX_MAY cho row {row}")
        return False

    x_may, y_may = INDEX_MAY[row]
    logger.info(f"Xử lý máy hàng {row} tại ({x_may}, {y_may})")

    max_tap = 3
    found_next_sanxuat = False

    for i in range(max_tap):
        if _should_stop():
            return False

        adb.tap_sendevent_fast(x_may, y_may, 10)
        _sleep(TIME_SLEEP_SHORT)

        # Chụp 1 screenshot, tìm cả 2 template
        screen = adb.screenshot_full()
        if screen is None:
            continue
        pos_slot = img.find_template_color("assets/items/core_sanxuat_vp.png", threshold=threshold, screen_img=screen)
        if pos_slot:
            logger.info(f"Máy rảnh sau {i+1} lần tap")
            found_next_sanxuat = True
            break

        logger.info(f"Máy chưa rảnh, tap lần {i+1}")
        pos_next_sx = img.find_template_color("assets/items/core_next_sanxuat.png", threshold=threshold, screen_img=screen)
        if pos_next_sx:
            logger.info(f"Tìm thấy next_sanxuat sau {i+1} lần tap")
            found_next_sanxuat = True
            break

    if INDEX_SAN_XUAT_MAC_DINH:
        pos_slot = INDEX_SAN_XUAT_MAC_DINH

    for item_data in data:
        if _should_stop():
            return False

        path_item = item_data['path_item']
        total = item_data.get('total', 1)

        set_state(PlayerState.SAN_XUAT)
        logger.info(f"Sản xuất {total} x {path_item}")
        pos_item = tim_vp(path_item, threshold=threshold, region=region)
        if pos_item:
            x_item, y_item = pos_item
        else:
            logger.warning(f"Không tìm thấy vật phẩm {path_item}")
            break
        for _ in range(total):
            if _should_stop():
                return False
            x_slot, y_slot = pos_slot
            adb.swipe(x_item, y_item, x_slot, y_slot, 70)

        # Check hết nguyên liệu — 1 screenshot
        screen = adb.screenshot_full()
        pos_nut_x = img.find_template_color("assets/items/core_nut_x.png",
                                            threshold=threshold, screen_img=screen) if screen is not None else None
        if pos_nut_x:
            logger.info("Máy hết nguyên liệu, đóng máy")
            x_x, y_x = pos_nut_x
            adb.tap(x_x, y_x)
            _sleep(TIME_SLEEP_SHORT)
            break
    if is_sua_may:
        sua_may(threshold=threshold)
    else:
        (x, y) = INDEX_THOAT_SAN_XUAT_MAC_DINH
        adb.tap_fast(x, y, 2)

    logger.info(f"Hoàn thành xử lý máy hàng {row}")
    _sleep(TIME_SLEEP_SHORT)
    return True


def tim_vp(template_path, count=1, threshold: float=THRESHOLD, region=None):
    """Tìm vật phẩm sản xuất. Tối ưu: 1 screenshot cho cả VP + next_sanxuat."""
    adb = _get_adb()
    if _should_stop():
        return None
    if count > 5:
        logger.info(f"Đã thử tìm VP {count} lần, dừng")
        return None

    # 1 screenshot dùng cho cả tìm VP + tìm next_sanxuat
    screen = adb.screenshot_full()
    if screen is None:
        return None

    pos = img.find_template_color(template_path, threshold=threshold, screen_img=screen, region=region)
    if pos:
        logger.info(f"Tìm được {template_path} tại {pos}")
        return pos

    logger.info(f"Không tìm được {template_path} lần {count}")
    # Tìm nút next trên cùng screenshot
    # next_sanxuat = "assets/items/core_next_sanxuat.png"
    # pos_next = img.find_template_color(next_sanxuat, threshold=threshold, screen_img=screen)
    # if pos_next:
    #     x, y = pos_next
    #     adb.tap(x, y)
    # else:
    #     logger.info(f"Không tìm thấy {next_sanxuat}, dùng vị trí mặc định")
    #     (x, y) = INDEX_NEXT_SAN_XUAT_MAC_DINH
    #     adb.tap(x, y)
    (x, y) = INDEX_NEXT_SAN_XUAT_MAC_DINH
    adb.tap(x, y)
    _sleep(TIME_SLEEP_SHORT)
    return tim_vp(template_path, count + 1, threshold=threshold, region=region)


def sua_may(threshold: float = THRESHOLD):
    
    adb = _get_adb()
    set_state(PlayerState.SUA_MAY)
    pos_sua = find_image_v2("assets/items/core_sua_may.png", True, threshold=threshold,
                            max_retry=0)
    if pos_sua:
        x_sua, y_sua = pos_sua
        adb.tap(x_sua, y_sua)
        _sleep(TIME_SLEEP_SHORT)
        if INDEX_SUA_MAY_MAC_DINH is not None:
            (x_vang, y_vang) = INDEX_SUA_MAY_MAC_DINH
            adb.tap(x_vang, y_vang)
            _sleep(TIME_SLEEP_SHORT)
            logger.info("Sửa máy thành công")
        else:    
            pos_vang = find_image_v2("assets/items/core_sua_may_vang.png", True, threshold=threshold,
                                    max_retry=0)
            if pos_vang:
                x_vang, y_vang = pos_vang
                adb.tap(x_vang, y_vang)
                _sleep(TIME_SLEEP_SHORT)
                logger.info("Sửa máy thành công")
            else:
                logger.info("Không tìm thấy nút sửa máy vàng")

    (x, y) = INDEX_THOAT_SAN_XUAT_MAC_DINH
    adb.tap_fast(x, y, 2)  
