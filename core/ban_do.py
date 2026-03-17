import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from .adb import ADBController 
from .image import ImageProcessor 
from config import INDEX_CUA_HANG_MAC_DINH
from utils.utils import len_may, xuong_may, find_image
import time
import logging
from utils.logger import log_time
from utils.utils import init_adb
logger = logging.getLogger(__name__)       
img = ImageProcessor()      
MAX_ATTEMPTS = 3
THRESHOLD = 0.9                  # Độ chính xác tìm kiếm
CLICK_DELAY = 1.5

def tim_cua_hang(adb):
    
    adb.press_key(19, False, 2)

    adb.tap(674, 831)
    return True

"""
main đăt vập phẩm cửa hàng lấy config 
{
    "loai_kho": "KTP", # loại kho: KSK, KNS, KTP
    "so_lan_dat_vp": 4 # số lần đặt vật phẩm vào kho mỗi lần chạy
    "data": "assets/items/kho_tra_hoa_hong.png, assets/items/kho_tinh_dau_tao.png, assets/items/kho_vai_vang.png"
    "xoa_kc": True # có xóa kho không
    "dat_quang_cao": True # có đặt quảng cáo không
}
1. Tìm cửa hàng
2. Tìm ô trống hoặc ô vàng => có thể kéo cửa hàng sang phải hoặc trái để tìm
3. Chọn kho theo config loai_kho => CONFIG_LOAI_KHO => Lấy path_warehouse_not_select, path_warehouse_select
4. Chọn vật phẩm theo config data (danh sách path vật phẩm cách bởi dấu ,) 
=> 
5. Đặt bán vập phẩm theo số lần cấu hình so_lan_dat_vp, các 
vật phẩm trong data random trong mỗi lần đặt hoặc tìm kiếm cái nào có số lượng lớn nhất để đặt
"""    
def main_dat_vp(adb:ADBController, config: dict):
    so_lan_dat_vp = config.get("so_lan_dat_vp", 4)
    loai_kho = config.get("loai_kho", "KTP")
    data_vp = config.get("data", "")
    xoa_kc = config.get("xoa_kc", True)
    dat_quang_cao = config.get("dat_quang_cao", True)

    # Lấy thông tin kho từ cấu hình
    from config import CONFIG_LOAI_KHO
    kho_info = next((kho for kho in CONFIG_LOAI_KHO if kho["code"] == loai_kho), None)
    if not kho_info:
        logger.error(f"Loại kho không hợp lệ: {loai_kho}")
        return

    template_path_kho_not_select = kho_info["path_warehouse_not_select"]
    template_path_kho = kho_info["path_warehouse_select"]

    # Tách danh sách vật phẩm từ cấu hình, bỏ khoăng trắng ở đầu cuối
    danh_sach_vp = [vp.strip() for vp in data_vp.split(",") if vp.strip()]
    if not danh_sach_vp:
        logger.error("Danh sách vật phẩm trống!")
        return

    logger.info(f"Bắt đầu đặt vật phẩm vào kho '{loai_kho}' với {so_lan_dat_vp} lần, vật phẩm: {danh_sach_vp}, xóa kho: {xoa_kc}, đặt quảng cáo: {dat_quang_cao}")

    # Thực hiện đặt vật phẩm
    for i in range(so_lan_dat_vp):
        logger.info(f"=== Lần đặt vật phẩm thứ {i + 1} ===")
        # Tìm ô để đăt vật phẩm (Tìm ô có vàng hoặc ô trống)
        # pos = 

        for vp_path in danh_sach_vp:
            logger.info(f"Đang đặt vật phẩm: {vp_path}")
            dat_vp(
                template_path_kho_not_select,
                template_path_kho,
                vp_path,
                repeat=1,
                select_quang_cao=dat_quang_cao,
                adb=adb
            )
            time.sleep(1)  # Thời gian nghỉ giữa các lần đặt

def nhat_vang(adb):
    # adb = ADBController(serial=serial) 
    screen_path = f"cache/{adb.serial}_screen.png"
    template_path = "assets/items/vang3.png"
    found = False
    attempt = 0
    while attempt < MAX_ATTEMPTS and not found:
        adb.screenshot_full(screen_path)
        points = img.find_template(screen_path=screen_path, template_path=template_path, threshold=THRESHOLD)
        if points:
            x, y = points
            logger.info(f"Thu hoạch vàng: ({x}, {y}) → Tap được!")
            adb.tap(x, y, 0.1)  # Tự động nhấn nếu cần
        else:
            logger.warning("Không tìm thấy ô vàng!")
            attempt += 1
            time.sleep(0.1)
    return True
def tim_o_trong(adb):
    # adb = ADBController(serial=serial) 
    screen_path = f"cache/{adb.serial}_screen.png"
    template_path = "assets/items/o_trong.png"
    found = False
    attempt = 0
    while attempt < MAX_ATTEMPTS and not found:
        adb.screenshot_full(screen_path)
        points = img.find_template(screen_path=screen_path, template_path=template_path, threshold=THRESHOLD)
        if points:
            x, y = points
            logger.info(f"Đạt VP tại: ({x}, {y})")
            return points
            # adb.tap(x, y)  # Tự động nhấn nếu cần
        else:
            logger.warning("Không tìm thấy ô đặt vật phẩm")
            attempt += 1
            time.sleep(0.5)
    return None

def select_kho2(adb:ADBController):
    screen_path = f"cache/{adb.serial}_screen.png"
    template_path_0 = "assets/items/kho_thanh_pham_0.png"
    template_path = "assets/items/kho_thanh_pham.png"
    adb.screenshot_full(screen_path)
    pos = img.find_template(screen_path=screen_path, template_path=template_path, threshold=THRESHOLD)
    if pos:
        return True
    pos = img.find_template(screen_path=screen_path, template_path=template_path_0, threshold=THRESHOLD)
    if pos:
        x, y = pos
        adb.tap(x, y)
        return True
    else:
        logger.warning("Không tìm thấy bảng!")
    return False
def select_kho(template_path_not_select: str, template_path_select: str, adb:ADBController):
    screen_path = f"cache/{adb.serial}_screen.png"
    adb.screenshot_full(screen_path)
    pos = img.find_template(screen_path=screen_path, template_path=template_path_select, threshold=THRESHOLD)
    if pos:
        x, y = pos
        logger.info(f"Tìm thấy kho đã select: ({x}, {y})")
        return pos
    else:
        logger.warning(f"Không tìm thấy kho kiểm tra file {template_path_select}")
    pos = img.find_template(screen_path=screen_path, template_path=template_path_not_select, threshold=THRESHOLD)
    if pos:
        x, y = pos
        logger.info(f"Tìm thấy kho chưa select: ({x}, {y})")
        return pos
    else:
        logger.warning(f"Không tìm thấy kho kiểm tra file {template_path_not_select}")
        return None

def keo_cua_hang_sang_phai(adb:ADBController):
    screen_path = f"cache/{adb.serial}_screen.png"
    template_path = "assets/items/quay_hang_on.png"
    adb.screenshot_full(screen_path)
    pos = img.find_template(screen_path=screen_path, template_path=template_path, threshold=THRESHOLD)   
    if pos:
        x, y = pos
        logger.info(f"[FOUND] Bảng tại: ({x}, {y}) → Tap được!")     
        adb.scroll_right(500,300,540, 600)

def keo_cua_hang_sang_trai(adb:ADBController):
    screen_path = f"cache/{adb.serial}_screen.png"
    template_path = "assets/items/quay_hang_on.png"
    adb.screenshot_full(screen_path)
    pos = img.find_template(screen_path=screen_path, template_path=template_path, threshold=THRESHOLD)   
    if pos:
        x, y = pos
        logger.info(f"[FOUND] Bảng tại: ({x}, {y}) → Tap được!")     
        adb.scroll_left(300, 500,540, 600)
    
@log_time
def dat_vp(template_path_kho_not_select: str, template_path_kho: str, template_path_vp: str, repeat: int=1, select_quang_cao: bool=False, adb: ADBController=ADBController):
    for i in range(repeat):
        print(f"Chay lần {i}")
        dat_vq_1_man(template_path_kho_not_select, template_path_kho, template_path_vp, select_quang_cao, adb)

def dat_vq_1_man(template_path_kho_not_select: str, template_path_kho: str, template_path_vp: str, select_quang_cao: bool, adb):
    # thu hoach vang
    # adb = ADBController(serial)
    nhat_vang(adb)
    time.sleep(1)
    check = True
    while check == True:
        pos = tim_o_trong(adb)
        if (pos):
            x,y = pos
            adb.tap(x,y)
            # select kho
            pos = select_kho(template_path_kho_not_select, template_path_kho, adb)
            if (pos):
                x,y = pos
                adb.tap(x,y,0.1)  
                # tim_vp_truyen vào
                lua_chon_vp(adb, template_path_vp, select_quang_cao)
            else:
                check = False
        else:
            check = False
    
def lua_chon_vp(adb:ADBController, path_vp: str, select_quang_cao: bool=False):
    logger.info("Start lua_chon_vp")
    screen_path = f"cache/{adb.serial}_screen.png"
    # template_path = "assets/items/kho_thanh_pham.png"
    adb.screenshot_full(screen_path)
    
    item = img.find_template_item(screen_path=screen_path, template_path=path_vp, threshold=THRESHOLD)
    if (item):
        x,y, number = item
        logger.info(f"Tìm được {path_vp} tại vị trí {x}|{y} với sl {number}")
        adb.tap(x,y,0.1)
        dat_ban_vp_qc(adb, select_quang_cao, number)
    else:
        logger.info(f"Không Tìm được {path_vp}")

def dat_ban_vp_qc(adb:ADBController, select_quang_cao: bool=False, number: int=10):
    screen_path = f"cache/{adb.serial}_screen.png"
    template_path_cong = "assets/items/cong.png"
    template_path_qc = "assets/items/cua_hang_qc.png"
    template_path_dat_ban = "assets/items/dat_ban.png"
    adb.screenshot_full(screen_path)
    if (select_quang_cao == False):
        pos = img.find_template(screen_path=screen_path, template_path=template_path_qc, threshold=THRESHOLD)
        # Tắt qc
        if (pos):
            x,y = pos
            adb.tap(x,y,0.01)
    if (number < 20):
        for i in range(2):
            pos = img.find_template(screen_path=screen_path, template_path=template_path_cong, threshold=0.9) 
            if (pos):
                print("tìm được o +")
                x,y = pos
                adb.taps(x,y,8,0.01)
                if(i==0):
                    adb.screenshot_full(screen_path)
    pos = img.find_template(screen_path=screen_path, template_path=template_path_dat_ban, threshold=THRESHOLD)
    if (pos):
        x,y = pos
        adb.tap(x,y,0.01)


