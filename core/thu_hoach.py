import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from .adb import ADBController 
from .image import ImageProcessor 
from config import GARDEN_REGION, NUM_ROWS, ROW_HEIGHT, ROW_END_X, SWIPE_DURATION, ROW_START_POINTS, DEVICE_SERIAL
import time
import logging

logger = logging.getLogger(__name__)
adb = ADBController(serial=DEVICE_SERIAL)        
img = ImageProcessor()      
MAX_ATTEMPTS = 3
THRESHOLD = 0.75                  # Độ chính xác tìm kiếm
CLICK_DELAY = 1.5


def thuhoach():
    points = [(330,790), (330,930), (900,930), (330,700),(900,700),(330,480),(900,480),(330,260),(900,260)]
    adb.tap(380,930)
    harvest_sendevent_android9(points)

def harvest_sendevent_android9(points):
    # DOWN
    adb.send_touch_sendevent(points)

