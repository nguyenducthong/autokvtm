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


def thuhoach():
    points = [(300,755),(360,920),(455,920),(550,920),(645,920),(740,920),(835,920)]
    adb.tap(360,920)

    adb.drag_smooth(points, 1200)

