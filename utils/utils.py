import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from core.adb import ADBController 
from core.image import ImageProcessor 
from config import DEVICE_SERIAL, INDEX_HANG, CONFIG_TEMP_TC
import time
import logging
THRESHOLD = 0.85
logger = logging.getLogger(__name__)
adb = ADBController(serial=DEVICE_SERIAL) 
img = ImageProcessor()

def tim_may(template_path, count=1):
    pos = find_image(template_path, True)
    if (pos):
        print(f"tim duoc {template_path} {pos}")
        return
    else:
        count= +1
        print(f"khong tim duoc {template_path}" )
        may_10 = "assets/items/num/10.png"
        pos = find_image(may_10, False)
        if (pos):
            xuong_nha()
        if (count == 10):
            xuong_nha()
        len_may(1, 50)
        tim_may(template_path, count)  


def lay_toa_do_tu_indexs(indexs_list):
    return [INDEX_HANG[idx] for idx in indexs_list if idx in INDEX_HANG]


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
    adb.scroll_down(500, 450, 70, duration)
    time.sleep(sleep)
    pos = find_image("assets/items/check_xuong_1.png", True)
    if (pos):
        (x,y) = pos
        adb.tap(x,y)
        time.sleep(sleep)

def find_image(template_path, screen):
    screen_path = "cache/screen.png"
    if (screen):
        adb.screenshot_full(screen_path)
    return img.find_template(screen_path=screen_path, template_path=template_path, threshold=THRESHOLD)
