import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from .adb import ADBController 
from .image import ImageProcessor 
from config import DEVICE_SERIAL
import time
import logging

logger = logging.getLogger(__name__)
adb = ADBController(serial=DEVICE_SERIAL)        
img = ImageProcessor()      
MAX_ATTEMPTS = 3
THRESHOLD = 0.75                  # Độ chính xác tìm kiếm
CLICK_DELAY = 1.5


def thuhoach(points: list, tap):
    x,y = tap 
    adb.tap(x,y)
    pos = tim_gio_thu_hoach()
    if (pos):
        points.insert(0,pos)
        print(f"pos {pos}, points {points}")
        harvest_sendevent_android9(points)
    else:
        adb.tap(x,y)

def harvest_sendevent_android9(points):
    adb.send_touch_sendevent(points)


def tim_gio_thu_hoach():
    pos = find_image("assets/items/thu_hoach.png", True)
    if (pos):
        print("Tim được giỏ")
        return pos
    else:
        print("Không Tìm được giỏ")
        return None

def find_image(template_path, screen):
    screen_path = "cache/screen.png"
    if (screen):
        adb.screenshot_full(screen_path)
    return img.find_template(screen_path=screen_path, template_path=template_path, threshold=THRESHOLD)
    
