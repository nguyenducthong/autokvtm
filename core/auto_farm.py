"""
Auto Farm System - Thu hoạch và trồng cây tự động
"""

import time
import logging
from typing import List, Tuple, Dict
from core.adb import ADBController

logger = logging.getLogger(__name__)


class AutoFarm:
    """
    Hệ thống tự động hóa farm
    """

    def __init__(self, adb: ADBController):
        self.adb = adb

        # Tọa độ các hàng cây (từ dưới lên)
        # Format: (x_start, y, spacing_x)
        self.ROWS = {
            1: {"y": 730, "x_start": 310, "spacing": 95, "count": 6},  # Hàng dưới cùng
            2: {"y": 550, "x_start": 310, "spacing": 95, "count": 6},  # Hàng 2
            3: {"y": 380, "x_start": 310, "spacing": 95, "count": 6},  # Hàng 3
            4: {"y": 210, "x_start": 310, "spacing": 95, "count": 6},  # Hàng trên cùng
        }

        # Vùng kiểm tra cây (offset từ tâm cây)
        self.TREE_CHECK_OFFSET = (0, -40)  # Vùng có icon trên đầu cây

        # Delay
        self.TAP_DELAY = 0.3
        self.HARVEST_DELAY = 0.5
        self.PLANT_DELAY = 0.5

    def get_tree_positions(self, row: int) -> List[Tuple[int, int]]:
        """
        Lấy tọa độ tất cả cây trong 1 hàng
        """
        if row not in self.ROWS:
            raise ValueError(f"Row {row} không hợp lệ!")

        row_data = self.ROWS[row]
        positions = []

        for i in range(row_data["count"]):
            x = row_data["x_start"] + (i * row_data["spacing"])
            y = row_data["y"]
            positions.append((x, y))

        return positions

    def tap_tree(self, x: int, y: int):
        """Tap vào cây"""
        self.adb.tap(x, y, self.TAP_DELAY)
        logger.info(f"[FARM] Tap cây tại ({x}, {y})")

    def harvest_tree(self, x: int, y: int, basket_pos: Tuple[int, int] = None):
        """
        Thu hoạch 1 cây bằng cách kéo giỏ
        - Kéo giỏ từ vị trí ban đầu qua cây
        """
        if basket_pos is None:
            # Vị trí giỏ mặc định (góc dưới trái màn hình)
            basket_pos = (100, 700)

        logger.info(f"[FARM] Thu hoạch cây tại ({x}, {y}) - Kéo giỏ từ {basket_pos}")

        # Kéo giỏ từ vị trí ban đầu đến cây
        self.adb.swipe(basket_pos[0], basket_pos[1], x, y, 300)
        time.sleep(self.HARVEST_DELAY)

    def plant_tree(self, x: int, y: int, seed_icon_pos: Tuple[int, int] = None):
        """
        Trồng cây bằng cách kéo hạt giống
        - Kéo icon hạt giống từ menu qua ô trống
        """
        if seed_icon_pos is None:
            logger.warning(f"[FARM] Chưa cài đặt vị trí icon hạt giống!")
            return

        logger.info(f"[FARM] Trồng cây tại ({x}, {y}) - Kéo hạt từ {seed_icon_pos}")

        # Kéo hạt giống từ menu đến vị trí trống
        self.adb.swipe(seed_icon_pos[0], seed_icon_pos[1], x, y, 300)
        time.sleep(self.PLANT_DELAY)

    def harvest_row(self, row: int, basket_pos: Tuple[int, int] = None):
        """
        Thu hoạch tất cả cây trong 1 hàng bằng cách kéo giỏ qua từng cây
        """
        logger.info(f"[FARM] Bắt đầu thu hoạch hàng {row}")

        positions = self.get_tree_positions(row)

        for i, (x, y) in enumerate(positions, 1):
            logger.info(f"[FARM] Thu hoạch cây {i}/{len(positions)} - Hàng {row}")
            self.harvest_tree(x, y, basket_pos)
            time.sleep(self.HARVEST_DELAY)

        logger.info(f"[FARM] Hoàn thành thu hoạch hàng {row}")

    def harvest_row_drag(self, row: int, basket_pos: Tuple[int, int] = None):
        """
        Thu hoạch cả hàng bằng cách kéo giỏ qua tất cả cây 1 lần
        - Nhanh hơn nhiều so với kéo từng cây
        """
        if basket_pos is None:
            basket_pos = (100, 700)

        logger.info(f"[FARM] Kéo giỏ thu hoạch hàng {row}")

        positions = self.get_tree_positions(row)

        if not positions:
            return

        # Lấy vị trí đầu và cuối hàng
        first_tree = positions[0]
        last_tree = positions[-1]

        # Tạo đường đi qua tất cả cây
        # Bắt đầu từ giỏ → cây đầu → cây cuối
        path_points = [basket_pos, first_tree] + positions[1:]

        logger.info(f"[FARM] Kéo giỏ qua {len(path_points)} điểm")

        # Kéo theo đường path
        for i in range(len(path_points) - 1):
            start = path_points[i]
            end = path_points[i + 1]
            self.adb.swipe(start[0], start[1], end[0], end[1], 200)
            time.sleep(0.1)

        logger.info(f"[FARM] Hoàn thành kéo giỏ thu hoạch hàng {row}")

    def plant_row(self, row: int, seed_icon_pos: Tuple[int, int] = None):
        """
        Trồng cây cho tất cả vị trí trong 1 hàng
        """
        logger.info(f"[FARM] Bắt đầu trồng cây hàng {row}")

        positions = self.get_tree_positions(row)

        for i, (x, y) in enumerate(positions, 1):
            logger.info(f"[FARM] Trồng cây {i}/{len(positions)} - Hàng {row}")
            self.plant_tree(x, y, seed_icon_pos)
            time.sleep(self.PLANT_DELAY)

        logger.info(f"[FARM] Hoàn thành trồng cây hàng {row}")

    def harvest_all(self, rows: List[int] = None):
        """
        Thu hoạch tất cả các hàng
        """
        if rows is None:
            rows = [1, 2, 3, 4]

        logger.info(f"[FARM] Bắt đầu thu hoạch {len(rows)} hàng")

        for row in rows:
            self.harvest_row(row)
            time.sleep(0.5)

        logger.info(f"[FARM] Hoàn thành thu hoạch tất cả")

    def plant_all(self, rows: List[int] = None, seed_icon_pos: Tuple[int, int] = None):
        """
        Trồng cây cho tất cả các hàng
        """
        if rows is None:
            rows = [1, 2, 3, 4]

        logger.info(f"[FARM] Bắt đầu trồng cây {len(rows)} hàng")

        for row in rows:
            self.plant_row(row, seed_icon_pos)
            time.sleep(0.5)

        logger.info(f"[FARM] Hoàn thành trồng cây tất cả")

    def harvest_and_plant(self, rows: List[int] = None, seed_icon_pos: Tuple[int, int] = None):
        """
        Thu hoạch rồi trồng lại ngay
        """
        if rows is None:
            rows = [1, 2, 3, 4]

        logger.info(f"[FARM] Bắt đầu chu trình thu hoạch + trồng cây")

        for row in rows:
            logger.info(f"[FARM] Xử lý hàng {row}")

            # Thu hoạch hàng này
            self.harvest_row(row)
            time.sleep(1)

            # Trồng lại hàng này
            self.plant_row(row, seed_icon_pos)
            time.sleep(1)

        logger.info(f"[FARM] Hoàn thành chu trình thu hoạch + trồng cây")

    def harvest_specific_trees(self, tree_positions: List[Dict]):
        """
        Thu hoạch các cây cụ thể
        tree_positions: [{"row": 1, "index": 1}, {"row": 2, "index": 3}, ...]
        """
        logger.info(f"[FARM] Thu hoạch {len(tree_positions)} cây cụ thể")

        for tree in tree_positions:
            row = tree["row"]
            index = tree["index"]

            positions = self.get_tree_positions(row)

            if 0 <= index < len(positions):
                x, y = positions[index]
                self.harvest_tree(x, y)
                time.sleep(self.HARVEST_DELAY)
            else:
                logger.warning(f"[FARM] Index {index} không hợp lệ cho hàng {row}")

    def swipe_collect(self, start_pos: Tuple[int, int], end_pos: Tuple[int, int]):
        """
        Vuốt để thu hoạch nhiều cây cùng lúc
        """
        logger.info(f"[FARM] Vuốt thu hoạch từ {start_pos} đến {end_pos}")
        self.adb.swipe(start_pos[0], start_pos[1], end_pos[0], end_pos[1], 800)

    def swipe_harvest_row(self, row: int):
        """
        Vuốt thu hoạch cả hàng
        """
        logger.info(f"[FARM] Vuốt thu hoạch hàng {row}")

        row_data = self.ROWS[row]
        y = row_data["y"] + self.TREE_CHECK_OFFSET[1]

        # Tính tọa độ đầu và cuối hàng
        start_x = row_data["x_start"]
        end_x = start_x + (row_data["spacing"] * (row_data["count"] - 1))

        # Vuốt từ trái sang phải
        self.adb.swipe(start_x, y, end_x, y, 1000)
        time.sleep(0.5)

    def swipe_harvest_all(self):
        """
        Vuốt thu hoạch tất cả các hàng
        """
        logger.info(f"[FARM] Vuốt thu hoạch tất cả hàng")

        for row in [1, 2, 3, 4]:
            self.swipe_harvest_row(row)
            time.sleep(0.5)

        logger.info(f"[FARM] Hoàn thành vuốt thu hoạch tất cả")


class SmartFarm(AutoFarm):
    """
    Farm thông minh - Tự động phát hiện cây chín và thu hoạch
    """

    def __init__(self, adb: ADBController):
        super().__init__(adb)

    def check_tree_ripe(self, x: int, y: int) -> bool:
        """
        Kiểm tra cây đã chín chưa bằng cách chụp màn hình
        và check pixel màu vùng icon trên đầu cây
        """
        # TODO: Implement image detection
        # Tạm thời return True để test
        return True

    def smart_harvest_row(self, row: int):
        """
        Thu hoạch thông minh - Chỉ thu hoạch cây đã chín
        """
        logger.info(f"[FARM] Smart harvest hàng {row}")

        positions = self.get_tree_positions(row)

        harvested_count = 0
        for i, (x, y) in enumerate(positions, 1):
            if self.check_tree_ripe(x, y):
                logger.info(f"[FARM] Cây {i} đã chín - Thu hoạch")
                self.harvest_tree(x, y)
                harvested_count += 1
                time.sleep(self.HARVEST_DELAY)
            else:
                logger.info(f"[FARM] Cây {i} chưa chín - Bỏ qua")

        logger.info(f"[FARM] Thu hoạch {harvested_count}/{len(positions)} cây - Hàng {row}")

    def smart_harvest_all(self):
        """
        Thu hoạch thông minh tất cả
        """
        logger.info(f"[FARM] Bắt đầu smart harvest tất cả")

        total_harvested = 0
        for row in [1, 2, 3, 4]:
            self.smart_harvest_row(row)
            time.sleep(0.5)

        logger.info(f"[FARM] Hoàn thành smart harvest")


# ============== Helper Functions ==============

def create_farm_bot(adb: ADBController, smart: bool = False) -> AutoFarm:
    """
    Tạo farm bot
    smart=True: Sử dụng SmartFarm (có phát hiện cây chín)
    smart=False: Sử dụng AutoFarm thường (thu hoạch tất cả)
    """
    if smart:
        return SmartFarm(adb)
    else:
        return AutoFarm(adb)


def quick_harvest_and_plant(adb: ADBController, seed_icon_pos: Tuple[int, int] = None):
    """
    Quick function - Thu hoạch và trồng lại tất cả
    """
    farm = AutoFarm(adb)
    farm.harvest_and_plant(seed_icon_pos=seed_icon_pos)


def quick_harvest_all(adb: ADBController):
    """
    Quick function - Thu hoạch tất cả
    """
    farm = AutoFarm(adb)
    farm.harvest_all()


def quick_plant_all(adb: ADBController, seed_icon_pos: Tuple[int, int] = None):
    """
    Quick function - Trồng cây tất cả
    """
    farm = AutoFarm(adb)
    farm.plant_all(seed_icon_pos=seed_icon_pos)
