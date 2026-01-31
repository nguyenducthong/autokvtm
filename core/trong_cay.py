import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from .adb import ADBController
from .image import ImageProcessor
from utils.utils import lay_toa_do_tu_indexs, tim_may, find_image
from config import DEVICE_SERIAL, INDEX_HANG, CONFIG_TEMP_TC, INDEX_MAY, INDEX_SAN_XUAT_MAC_DINH, INDEX_NEXT_SAN_XUAT_MAC_DINH, INDEX_THOAT_SAN_XUAT_MAC_DINH
import time
import logging
from .thu_hoach import thuhoach
THRESHOLD = 0.85
logger = logging.getLogger(__name__)

# Không khởi tạo ADB ngay, sẽ khởi tạo khi cần
adb = None
img = ImageProcessor()

def init_adb(serial=None):
    """Khởi tạo ADB controller"""
    global adb
    if serial is None:
        serial = DEVICE_SERIAL
    adb = ADBController(serial=serial)
    return adb

def main_tc(config: list, adb_instance=None, stop_callback=None):
    """
    Chạy auto farm theo config

    Args:
        config: Danh sách config trồng cây
        adb_instance: ADB controller instance (nếu None sẽ dùng global adb)
        stop_callback: Hàm callback để kiểm tra yêu cầu dừng (trả về True nếu cần dừng)
    """
    global adb

    # Sử dụng adb instance được truyền vào, hoặc dùng global adb
    if adb_instance:
        adb = adb_instance
        # Cập nhật adb cho các module khác
        import core.thu_hoach as thu_hoach_module
        import utils.utils as utils_module
        thu_hoach_module.adb = adb_instance
        utils_module.adb = adb_instance

    if not adb:
        raise RuntimeError("ADB chưa được khởi tạo! Vui lòng gọi init_adb() hoặc truyền adb_instance")

    for idx, item in enumerate(config, 1):
        # Kiểm tra stop callback
        if stop_callback and stop_callback():
            logger.info("⛔ Dừng auto farm theo yêu cầu")
            break

        path_may = item.get('path_row')
        type_item = item['type']
        logger.info(f"--- Xử lý config {idx}/{len(config)}: Loại {type_item} ---")
        if not path_may:
            logger.warning(f"Config thiếu path_row, bỏ qua")
            continue

        logger.info(f"🌾 Xử lý config {idx}/{len(config)}: Hàng {item.get('row')}")

        # Tìm máy/hàng
        check = tim_may(path_may)
        if check == False:
            logger.info("LỖI: Tìm mây bỏ qua cấu hình")
            continue

        # Kiểm tra stop trước khi xử lý
        if stop_callback and stop_callback():
            logger.info("⛔ Dừng trước khi xử lý")
            break

        if type_item == "MAY":
            # Xử lý máy sản xuất (không cần indexs)
            logger.info(f"🏭 Xử lý máy sản xuất hàng {item.get('row')}...")
            xu_ly_may(item, stop_callback)

        elif type_item == "TC":
            # Trồng cây - cần indexs và path_item
            path_cay = item.get('path_item')
            if not item.get('indexs'):
                logger.warning("Config TC thiếu indexs, bỏ qua")
                continue

            listIndex = lay_toa_do_tu_indexs(item['indexs'])
            tap = listIndex[0]
            x, y = tap
            adb.tap(x, y, 1)
            check_trong = check_trong_cay()
            if check_trong == "chua_chin":
                logger.info("Cây chưa chín, bỏ qua thu hoạch")
                continue
            elif check_trong == "next_gieo":
                logger.info("Chuyển sang cây tiếp theo")
                if stop_callback and stop_callback():
                    logger.info("⛔ Dừng trước khi trồng cây")
                    break
                time.sleep(0.5)
                # Trồng cây
                logger.info(f"🌱 Trồng cây tại {len(listIndex)} vị trí...")
                trong_cay(path_cay, listIndex, tap)
            elif check_trong == "gio_hang":
                logger.info("Tìm thấy giỏ hàng, tiến hành thu hoạch")
                time.sleep(0.5)
                # Thu hoạch
                logger.info(f"🧺 Thu hoạch {len(listIndex)} vị trí...")
                thuhoach(listIndex, tap)
                adb.tap(x, y, 1)
                logger.info(f"🌱 Trồng cây tại {len(listIndex)} vị trí...")
                trong_cay(path_cay, listIndex, tap)

        logger.info(f"✓ Hoàn thành config {idx}/{len(config)}")

    logger.info("✓ Hoàn thành tất cả config")

##
def tim_cay_trong(template_path, count=1, sleep: float=0.7):
    pos = find_image(template_path, True)
    if (pos):
        logger.info(f"tim duoc {template_path} {pos}")
        return pos
    else:
        count= +1
        logger.info(f"khong tim duoc {template_path}") 
        next_gieo = "assets/items/next_gieo.png"
        pos = find_image(next_gieo, False)
        if (pos):
            x,y = pos
            adb.tap(x,y)
            time.sleep(sleep)
            return tim_cay_trong(template_path, count)
        else:
            logger.info(f"Không tìm thấy {next_gieo}") 

def trong_cay(template_path, points: list, tap, duration_ms: int = 1500):
    """
    Trồng cây bằng cách kéo hạt giống qua các vị trí

    Args:
        template_path: Đường dẫn template hình ảnh cây cần trồng
        points: Danh sách các vị trí cần trồng
        tap: Vị trí đầu tiên để tap (mở menu)
        duration_ms: Tổng thời gian kéo (ms), mặc định 1500ms
    """
    x, y = tap
    # adb.tap(x, y)
    # time.sleep(0.5)  # Đợi menu hiển thị

    pos = tim_cay_trong(template_path)
    logger.info(f"Tìm cây tại: {pos}")

    if pos:
        points.insert(0, pos)
        logger.info(f"Kéo cây từ {pos} qua {len(points)-1} vị trí: {points}")

        # Sử dụng drag_smooth thay vì send_touch_sendevent
        adb.drag_smooth(points, total_duration_ms=duration_ms)
    else:
        logger.warning("Không tìm thấy loại cây, tap lại")
        adb.tap(x, y)

# Kiểm tra lại xem có giỏ hàng hay next_gieo 
def check_trong_cay():
    pos_TH = find_image("assets/items/thu_hoach.png", True)
    if (pos_TH):
        logger.info("Tìm được giỏ hàng")
        return "gio_hang"
    pos = find_image("assets/items/next_gieo.png", True)
    if (pos):
        logger.info("Tìm được nút next gieo")
        return "next_gieo"
    logger.info("Cây chưa chín")
    return "chua_chin"

# Xử lý thu hoạch vp máy
def xu_ly_may(config_may: dict, stop_callback=None):
    """
    Xử lý sản xuất vật phẩm từ máy

    Args:
        config_may: Config máy với format:
            {
                "row": 1,
                "type": "MAY",
                "path_row": "assets/items/num/1.png",
                "data": [{"path_item": "...", "total": 8}]
            }
        stop_callback: Hàm callback để kiểm tra yêu cầu dừng
    """
    row = str(config_may['row'])
    data = config_may.get('data', [])

    if row not in INDEX_MAY:
        logger.error(f"Không tìm thấy INDEX_MAY cho row {row}")
        return False

    # Lấy tọa độ máy
    x_may, y_may = INDEX_MAY[row]
    logger.info(f"🏭 Xử lý máy hàng {row} tại ({x_may}, {y_may})")

    # Tap vào máy cho đến khi thấy next_sanxuat (máy rảnh)
    max_tap = 2  # Giới hạn số lần tap
    found_next_sanxuat = False

    for i in range(max_tap):
        if stop_callback and stop_callback():
            logger.info("⛔ Dừng theo yêu cầu")
            return False

        adb.tap_fast(x_may, y_may, 10)
        time.sleep(0.5)

        # Kiểm tra xem máy đã rảnh chưa (hiện next_sanxuat)
        pos_slot = find_image("assets/items/sanxuat_vp.png", False)
        if pos_slot:
            logger.info(f"✓ Máy rảnh sau {i+1} lần tap")
            found_next_sanxuat = True
            break
        else:
            logger.info(f"Máy chưa rảnh không tìm thấy sanxuat_vp, tap lần {i+1}")
            pos_next_sx = find_image("assets/items/next_sanxuat.png", False)
            if pos_next_sx:
                logger.info(f"✓ Tìm thấy next_sanxuat sau {i+1} lần tap")
                found_next_sanxuat = True
                break
            else:
                logger.info(f"Không tìm thấy next_sanxuat, tiếp tục tap...")

    # if not found_next_sanxuat:
    #     logger.warning("Không tìm thấy next_sanxuat sau nhiều lần tap")
    #     return False
    # Tìm vị trí slot sản xuất (sanxuat_vp.png)
    # pos_slot = find_image("assets/items/sanxuat_vp.png", False)
    if pos_slot is None:
        logger.warning("Không tìm thấy slot sản xuất, lấy default")
        pos_slot = INDEX_SAN_XUAT_MAC_DINH
    # Kéo vật phẩm vào sản xuất
    for item in data:
        if stop_callback and stop_callback():
            return False

        path_item = item['path_item']
        total = item.get('total', 1)

        logger.info(f"🔧 Sản xuất {total} x {path_item}")
        pos_item = tim_vp(path_item)
        if pos_item:
            x_item, y_item = pos_item
        else:
            logger.warning(f"Không tìm thấy vật phẩm {path_item}")
            break
        for _ in range(total):
            if stop_callback and stop_callback():
                return False
            # Tìm vật phẩm
            # Kéo vật phẩm vào slot
            x_slot, y_slot = pos_slot
            adb.swipe(x_item, y_item, x_slot, y_slot, 50)
            logger.info(f"Kéo {path_item} vào slot")
            # time.sleep(0.3)
        # KIỂM TRA LẠI XEM MÁY CÓ HẾT NGUYÊN LIỆU KHÔNG
        pos_nut_x = find_image("assets/items/nut_x.png", True)
        if (pos_nut_x):
            logger.info("Máy hết nguyên liệu, đóng máy")
            x_x, y_x = pos_nut_x
            adb.tap(x_x, y_x)
            time.sleep(0.5)
            break
    sua_may()        
    logger.info(f"✓ Hoàn thành xử lý máy hàng {row}")
    return True
def tim_vp(template_path, count=1, sleep: float=0.7):
    pos = find_image(template_path, True)
    if (pos):
        logger.info(f"tim duoc {template_path} {pos}")
        return pos
    else:
        count= count + 1
        if count > 5:
            return None
        logger.info(f"khong tim duoc {template_path}") 
        next_sanxuat = "assets/items/next_sanxuat.png"
        pos = find_image(next_sanxuat, False)
        if (pos):
            x,y = pos
            adb.tap(x,y)
            time.sleep(sleep)
            return tim_vp(template_path, count)
        else:
            logger.info(f"Không tìm thấy {next_sanxuat}")
            (x,y) = INDEX_NEXT_SAN_XUAT_MAC_DINH
            adb.tap(x,y)
            time.sleep(sleep)
            return tim_vp(template_path, count)

def sua_may():
    pos_sua = find_image("assets/items/sua_may.png", True)
    if (pos_sua):
        x_sua, y_sua = pos_sua
        adb.tap(x_sua, y_sua)
        time.sleep(0.5)
        pos_vang = find_image("assets/items/sua_may_vang.png", True)
        if (pos_vang):
            x_vang, y_vang = pos_vang
            adb.tap(x_vang, y_vang)
            time.sleep(0.5)
            logger.info("Sửa máy thành công")
            
        else:
            logger.info("Không tìm thấy nút sửa máy vàng")
    
    (x,y) = INDEX_THOAT_SAN_XUAT_MAC_DINH
    adb.tap_fast(x,y,2)