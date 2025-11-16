import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from .adb import ADBController 
from .image import ImageProcessor 
from config import DEVICE_SERIAL, GARDEN_REGION, PLANTS
import time
import logging

logger = logging.getLogger(__name__)
adb = ADBController(serial=DEVICE_SERIAL)       # THÊM DÒNG NÀY
img = ImageProcessor()       # THÊM DÒNG NÀY
# core/actions.py
def harvest_all_plants():
    """Thu hoạch TẤT CẢ LOẠI CÂY – TỰ ĐỘNG SẮP XẾP"""
    screen = adb.screenshot_region(GARDEN_REGION)
    all_ripe = []

    # 1. Tìm cây chín của từng loại
    for plant in PLANTS:
        pts = img.find_template(screen, plant["ripe"], threshold=0.82)
        if pts:
            for pt in pts:
                all_ripe.append({
                    "x": pt[0],
                    "y": pt[1],
                    "type": plant["name"],
                    "seed": plant["seed"]
                })

    if not all_ripe:
        logger.info("Không có cây chín nào.")
        return []

    # 2. Sắp xếp: ưu tiên + vị trí (trái → phải, trên → dưới)
    all_ripe = sorted(all_ripe, key=lambda p: (p["type"], p["y"], p["x"]))

    # 3. Thu hoạch theo thứ tự
    first = all_ripe[0]
    adb.tap_relative(first["x"], first["y"], (GARDEN_REGION[0], GARDEN_REGION[1]))
    time.sleep(1.5)

    prev_x = first["x"] + GARDEN_REGION[0]
    prev_y = first["y"] + GARDEN_REGION[1]

    harvested_types = {first["type"]}

    for item in all_ripe[1:]:
        curr_x = item["x"] + GARDEN_REGION[0]
        curr_y = item["y"] + GARDEN_REGION[1]

        distance = ((curr_x - prev_x) ** 2 + (curr_y - prev_y) ** 2) ** 0.5
        if distance > 600:
            continue

        duration = max(200, min(600, int(distance * 0.8)))
        adb.swipe(prev_x, prev_y, curr_x, curr_y, duration)
        prev_x, prev_y = curr_x, curr_y
        time.sleep(0.15)

        harvested_types.add(item["type"])

    logger.info(f"Thu hoạch xong: {', '.join(harvested_types)}")
    return harvested_types

def replant_harvested(types_harvested):
    """Trồng lại các loại cây đã thu hoạch"""
    # for plant_type in types_harvested:
    #     for plant in PLANTS:
    #         if plant["name"] == plant_type:
    #             # success = plant_tree(plant["seed"])
    #             if success:
    #                 logger.info(f"Đã trồng lại: {plant_type}")
    #             time.sleep(2)
    #             break
# def main_loop():
#     logger.info("AUTO NHIỀU LOẠI CÂY – KHỞI ĐỘNG!")
#     while True:
#         try:
#             # 1. Thu hoạch tất cả
#             harvested = harvest_all_plants()
#             if harvested:
#                 time.sleep(3)
#                 # 2. Trồng lại
#                 # replant_harvested(harvested)

#             # 3. Cuộn vườn
#             # scroll_garden(steps=3, direction="down")
#             time.sleep(30)

#         except Exception as e:
#             logger.error(f"Lỗi: {e}")
#             time.sleep(10)



def main_loop():
    logger.info("AUTO KÉO 2 HÀNG – CHỈ CẦN 2 TỌA ĐỘ!")
    while True:
        try:
            harvest_by_config()
            time.sleep(3)

            # Cuộn lên xem hàng mới
            adb.arrow_up(count=3)
            time.sleep(1.5)

            time.sleep(25)  # Nghỉ giữa các vòng

        except Exception as e:
            logger.error(f"Lỗi: {e}")
            time.sleep(10)