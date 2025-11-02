import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from .adb import ADBController 
from .image import ImageProcessor 
from config import GARDEN_REGION, PLANTS, NUM_ROWS, ROW_HEIGHT, ROW_END_X, SWIPE_DURATION, ROW_START_POINTS, DEVICE_SERIAL
import time
import logging

logger = logging.getLogger(__name__)
adb = ADBController(serial=DEVICE_SERIAL)        
img = ImageProcessor()      
MAX_ATTEMPTS = 3
THRESHOLD = 0.75                  # Độ chính xác tìm kiếm
CLICK_DELAY = 1.5

def tim_cua_hang():
    adb.press_key(19, False, 2)

    adb.tap(674, 831)
    return True

def nhat_vang():
    screen_path = "cache/screen.png"
    template_path = "assets/items/vang3.png"
    found = False
    attempt = 0
    while attempt < MAX_ATTEMPTS and not found:
        adb.screenshot_full(screen_path)
        points = img.find_template(screen_path=screen_path, template_path=template_path, threshold=THRESHOLD)
        if points:
            x, y = points
            logger.info(f"[FOUND] Bảng tại: ({x}, {y}) → Tap được!")
            adb.tap(x, y)  # Tự động nhấn nếu cần
        else:
            logger.warning("Không tìm thấy bảng!")
            attempt += 1
            time.sleep(1)
    return True
def tim_o_trong():
    screen_path = "cache/screen.png"
    template_path = "assets/items/ch_trong.png"
    found = False
    attempt = 0
    while attempt < MAX_ATTEMPTS and not found:
        adb.screenshot_full(screen_path)
        points = img.find_template(screen_path=screen_path, template_path=template_path, threshold=THRESHOLD)
        if points:
            x, y = points
            logger.info(f"[FOUND] Bảng tại: ({x}, {y}) → Tap được!")
            return points
            # adb.tap(x, y)  # Tự động nhấn nếu cần
        else:
            logger.warning("Không tìm thấy bảng!")
            attempt += 1
            time.sleep(1)
    return None

def select_kho2():
    screen_path = "cache/screen.png"
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
def select_kho(template_path_not_select: str, template_path_select: str):
    screen_path = "cache/screen.png"
    adb.screenshot_full(screen_path)
    pos = img.find_template(screen_path=screen_path, template_path=template_path_select, threshold=THRESHOLD)
    if pos:
        return pos
    pos = img.find_template(screen_path=screen_path, template_path=template_path_not_select, threshold=THRESHOLD)
    if pos:
        # x, y = pos
        # adb.tap(x, y)
        return pos
    else:
        logger.warning("Không tìm thấy bảng!")
        return None

def keo_cua_hang_sang_phai():
    screen_path = "cache/screen.png"
    template_path = "assets/items/quay_hang_on.png"
    adb.screenshot_full(screen_path)
    pos = img.find_template(screen_path=screen_path, template_path=template_path, threshold=THRESHOLD)   
    if pos:
        x, y = pos
        logger.info(f"[FOUND] Bảng tại: ({x}, {y}) → Tap được!")     
        adb.scroll_right(500,300,540, 600)

def keo_cua_hang_sang_trai():
    screen_path = "cache/screen.png"
    template_path = "assets/items/quay_hang_on.png"
    adb.screenshot_full(screen_path)
    pos = img.find_template(screen_path=screen_path, template_path=template_path, threshold=THRESHOLD)   
    if pos:
        x, y = pos
        logger.info(f"[FOUND] Bảng tại: ({x}, {y}) → Tap được!")     
        adb.scroll_left(300, 500,540, 600)

def len_may(count: int=1, duration: int=50,sleep: float=0.7):
    for _ in range(count):
        adb.scroll_up(450, 500, 70, duration)
        time.sleep(sleep)

def xuong_may(count: int=1, duration: int=50,sleep: float=0.7):
    for _ in range(count):
        adb.scroll_down(500, 450, 70, duration)
        time.sleep(sleep)

def xuong_nha(duration: int=50,sleep: float=0.7):
    adb.scroll_up(450, 500, 70, duration)
    time.sleep(sleep)
    adb.scroll_up(450, 500, 70, duration)

def dat_vp(template_path_kho_not_select: str, template_path_kho: str, template_path_vp: str, repeat: int=1):
    for i in range(repeat):
        dat_vq_1_man(template_path_kho_not_select, template_path_kho, template_path_vp)
        

def dat_vq_1_man(template_path_kho_not_select: str, template_path_kho: str, template_path_vp: str):
    # thu hoach vang
    nhat_vang()
    time.sleep(3)
    check = True
    while check == True:
        pos = tim_o_trong()
        if (pos):
            x,y = pos
            adb.tap(x,y)
            # select kho
            pos = select_kho(template_path_kho_not_select, template_path_kho)
            if (pos):
                x,y = pos
                adb.tap(x,y)  
                # tim_vp_truyen vào
                lua_chon_vp(template_path_vp)
        else:
            check = False
    
def lua_chon_vp(path_vp: str, select_quang_cao: bool=False):
    screen_path = "cache/screen.png"
    # template_path = "assets/items/kho_thanh_pham.png"
    adb.screenshot_full(screen_path)
    pos = img.find_template(screen_path=screen_path, template_path=path_vp, threshold=THRESHOLD)

    if (pos):
        item = img.find_template_item(screen_path=screen_path, template_path=path_vp, threshold=THRESHOLD)
        if (item):
            x,y, number = item
            adb.tap(x,y)
            dat_ban_vp_qc(select_quang_cao, number)


def dat_ban_vp_qc(select_quang_cao: bool=False, number: int=10):
    screen_path = "cache/screen.png"
    template_path_cong = "assets/items/cong.png"
    template_path_qc = "assets/items/cua_hang_qc.png"
    template_path_dat_ban = "assets/items/dat_ban.png"
    adb.screenshot_full(screen_path)
    if (select_quang_cao == False):
        pos = img.find_template(screen_path=screen_path, template_path=template_path_qc, threshold=THRESHOLD)
        # Tắt qc
        if (pos):
            x,y = pos
            adb.tap(x,y)
    if (number < 20):
        for i in range(2):
            pos = img.find_template(screen_path=screen_path, template_path=template_path_cong, threshold=THRESHOLD) 
            if (pos):
                x,y = pos
                adb.taps(x,y,10,0.1)
                if(i==0):
                    adb.screenshot_full(screen_path)
    pos = img.find_template(screen_path=screen_path, template_path=template_path_dat_ban, threshold=THRESHOLD)
    if (pos):
        x,y = pos
        adb.taps(x,y,10,0.1)


