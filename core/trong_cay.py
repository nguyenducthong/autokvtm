import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from .adb import ADBController 
from .image import ImageProcessor 
from utils.utils import lay_toa_do_tu_indexs, tim_may, find_image
from config import DEVICE_SERIAL, INDEX_HANG, CONFIG_TEMP_TC
import time
import logging
from .thu_hoach import thuhoach
THRESHOLD = 0.85
logger = logging.getLogger(__name__)
adb = ADBController(serial=DEVICE_SERIAL) 
img = ImageProcessor()

def main_tc(config: list):
    for idx, item in enumerate(config, 1):
        path_may = item['path_row']
        path_cay = item['path_item']
        if (path_may):
            listIndex =lay_toa_do_tu_indexs(item['indexs'])
            tap = listIndex[0]
            tim_may(path_may)
            thuhoach(listIndex, tap)
            time.sleep(0.5)
            trong_cay(path_cay, listIndex, tap)

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

def trong_cay(template_path, points: list, tap):
    x,y = tap 
    adb.tap(x,y)
    pos = tim_cay_trong(template_path)
    logger.info(f"pos {pos}")
    if (pos):
        points.insert(0,pos)
        logger.info(f"pos {pos}, points {points}")
        harvest_sendevent_android9(points)
    else:
        adb.tap(x,y)

def harvest_sendevent_android9(points):
    adb.send_touch_sendevent(points)    

