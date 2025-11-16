import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from .adb import ADBController 
from .image import ImageProcessor 
from config import GARDEN_REGION, PLANTS, DEVICE_SERIAL
import time
import logging
from utils.logger import log_time
logger = logging.getLogger(__name__)       
img = ImageProcessor()      
MAX_ATTEMPTS = 3
THRESHOLD = 0.9                  # Độ chính xác tìm kiếm
CLICK_DELAY = 1.5

def tim_cua_hang(adb):
    
    adb.press_key(19, False, 2)

    adb.tap(674, 831)
    return True

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

def len_may(count: int=1, duration: int=50,sleep: float=0.7, adb: ADBController=ADBController):
    for _ in range(count):
        adb.scroll_up(450, 500, 70, duration)
        time.sleep(sleep)

def xuong_may(count: int=1, duration: int=50,sleep: float=0.7, adb: ADBController=ADBController):
    for _ in range(count):
        adb.scroll_down(500, 450, 70, duration)
        time.sleep(sleep)

def xuong_nha(duration: int=50,sleep: float=0.7, adb: ADBController=ADBController):
    adb.scroll_up(450, 500, 70, duration)
    time.sleep(sleep)
    adb.scroll_up(450, 500, 70, duration)
    
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


