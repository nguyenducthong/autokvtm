# core/adb.py
"""
ADB Controller – Quản lý toàn bộ thao tác với thiết bị Android (LDPlayer, Nox, v.v.)
Tính năng:
    - Chụp màn hình (toàn bộ / vùng)
    - Tap, Swipe (kéo thả)
    - Nhập văn bản
    - Mở ứng dụng
    - Kiểm tra kết nối + tự retry
"""

from ppadb.client import Client as AdbClient
import cv2
import numpy as np
import time
import os
import logging
import subprocess
# from lxml import html
from typing import Tuple, Optional, List

# Cấu hình log
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ADBController:
    def __init__(self, serial: str = "emulator-5566", host: str = "127.0.0.1", port: int = 5037, timeout: int = 10):
        """
        Khởi tạo kết nối ADB
        :param serial: Serial thiết bị (xem bằng `adb devices`)
        :param host: Host ADB (mặc định 127.0.0.1)
        :param port: Port ADB (mặc định 5037)
        :param timeout: Timeout kết nối (giây)
        """
        self.serial = serial
        self.host = host
        self.port = port
        self.timeout = timeout
        self.device = None
        self._connect()

    def _connect(self):
        """Kết nối ADB – Tự retry 3 lần"""
        client = AdbClient(host=self.host, port=self.port)
        for attempt in range(3):
            try:
                self.device = client.device(self.serial)
                if self.device:
                    logger.info(f"[ADB] Kết nối thành công: {self.device.get_serial_no()}")
                    return
            except Exception as e:
                logger.warning(f"[ADB] Lần {attempt + 1} thất bại: {e}")
                time.sleep(2)
        raise ConnectionError(f"[ADB] Không thể kết nối đến {self.serial}")

    # =============================================================
    # 1. CHỤP MÀN HÌNH
    # =============================================================
    def screenshot_full(self, save_path: str = "cache/full.png") -> np.ndarray:
        """
        Chụp toàn màn hình → lưu + trả về ảnh OpenCV
        :param save_path: Đường dẫn lưu ảnh
        :return: np.ndarray (BGR)
        """
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        self.device.shell("screencap -p /sdcard/full.png")
        self.device.pull("/sdcard/full.png", save_path)
        img = cv2.imread(save_path)
        if img is None:
            raise ValueError(f"Không đọc được ảnh: {save_path}")
        logger.debug(f"[SCREEN] Chụp toàn màn: {save_path}")
        return img

    def screenshot_region(self, region: Tuple[int, int, int, int], save_path: str = "cache/region.png") -> np.ndarray:
        """
        Chụp toàn màn → cắt vùng → lưu + trả về
        :param region: (left, top, width, height)
        :return: np.ndarray
        """
        left, top, w, h = region

        # 1. Chụp toàn màn
        full_path = "cache/full.png"
        self.device.shell("screencap -p /sdcard/full.png")
        self.device.pull("/sdcard/full.png", full_path)

        # 2. Đọc ảnh
        full_img = cv2.imread(full_path)
        if full_img is None:
            raise ValueError("Không đọc được ảnh toàn màn!")

        # 3. Cắt vùng
        cropped = full_img[top:top+h, left:left+w]

        # 4. Lưu vùng đã cắt
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        cv2.imwrite(save_path, cropped)

        logger.debug(f"[SCREEN] Chụp vùng {region} → {save_path} (kích thước: {cropped.shape})")
        return cropped

    # =============================================================
    # 2. TAP / CLICK
    # =============================================================
    def tap(self, x: int, y: int, delay: float = 0.5):
        """Tap vào tọa độ tuyệt đối"""
        self.device.shell(f"input tap {x} {y}")
        logger.info(f"[TAP] ({x}, {y})")
        time.sleep(delay)
    def taps(self, x: int, y: int, count: int= 1, delay: float = 0.5):
        """Tap nhiều vào tọa độ tuyệt đối"""
        for i in range(count):
            self.tap(x, y, delay)
    def tap_relative(self, x: int, y: int, offset: Tuple[int, int] = (0, 0), delay: float = 0.5):
        """Tap tọa độ tương đối + offset (dùng với vùng chụp)"""
        abs_x, abs_y = x + offset[0], y + offset[1]
        self.tap(abs_x, abs_y, delay)

    # =============================================================
    # 3. KÉO THẢ (SWIPE / DRAG & DROP)
    # =============================================================
    def swipe(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: int = 500):
        """
        Kéo từ (start) → (end)
        :param duration: Thời gian kéo (ms), 300–1000
        """
        self.device.shell(f"input swipe {start_x} {start_y} {end_x} {end_y} {duration}")
        logger.info(f"[SWIPE] ({start_x},{start_y}) → ({end_x},{end_y}) [{duration}ms]")
        time.sleep(max(0.5, duration / 1000 + 0.3))

    # =============================================================
    # 4. NHẬP VĂN BẢN
    # =============================================================
    def input_text(self, text: str):
        """Nhập text (dùng cho tìm kiếm, chat, tên cây...)"""
        import urllib.parse
        encoded = urllib.parse.quote(text)
        self.device.shell(f"input text '{encoded}'")
        logger.info(f"[INPUT] {text}")

    # =============================================================
    # 5. MỞ ỨNG DỤNG
    # =============================================================
    def open_app(self, package_name: str, activity: Optional[str] = None):
        """
        Mở ứng dụng
        :param package_name: com.zingplay.garden
        :param activity: .MainActivity (tùy chọn)
        """
        if activity:
            cmd = f"am start -n {package_name}/{activity}"
        else:
            cmd = f"monkey -p {package_name} 1"
        self.device.shell(cmd)
        logger.info(f"[APP] Mở {package_name}")
        time.sleep(5)

    # =============================================================
    # 6. KIỂM TRA KẾT NỐI
    # =============================================================
    def is_connected(self) -> bool:
        """Kiểm tra thiết bị còn sống không"""
        try:
            self.device.shell("echo test")
            return True
        except:
            return False

    def reconnect(self):
        """Tự động kết nối lại nếu mất"""
        if not self.is_connected():
            logger.warning("[ADB] Mất kết nối → Đang kết nối lại...")
            self._connect()

    # =============================================================
    # 7. DỌN DẸP (CLEAN UP)
    # =============================================================
    def cleanup(self):
        """Xóa file tạm trên thiết bị"""
        self.device.shell("rm -f /sdcard/*.png")
        logger.info("[ADB] Đã dọn file tạm")

    # =============================================================
    # 8. DI CHUYỂN LÊN / XUỐNG / TRÁI / PHẢI (SCROLL / SWIPE)
    # =============================================================
    def scroll_down(self, start_y: int, end_y: int, x: int, duration: int = 600):
        """
        Cuộn xuống: từ (x, start_y) → (x, end_y)
        Dùng để xem cây ở dưới vườn
        """
        self.swipe(x, start_y, x, end_y, duration)
        logger.info(f"[SCROLL DOWN] từ y={start_y} → y={end_y}")

    def scroll_up(self, start_y: int, end_y: int, x: int, duration: int = 600):
        """
        Cuộn lên: từ (x, start_y) → (x, end_y)
        """
        self.swipe(x, start_y, x, end_y, duration)
        logger.info(f"[SCROLL UP] từ y={start_y} → y={end_y}")

    # def scroll_to_bottom(self, screen_height: int = 2400, x: int = 540, duration: int = 1200):
    #     """
    #     Cuộn nhanh xuống đáy màn hình (dùng khi vườn dài)
    #     """
    #     self.scroll_down(400, screen_height - 400, x, duration)

    # def scroll_to_top(self, screen_height: int = 2400, x: int = 540, duration: int = 1200):
    #     """
    #     Cuộn nhanh lên đầu màn hình
    #     """
    #     self.scroll_up(screen_height - 400, 400, x, duration)
    def scroll_right(self, start_x: int, end_x: int, y: int, duration: int = 600):
   
        self.swipe(start_x, y, end_x, y, duration)
        logger.info(f"[SCROLL phai] từ x={start_x} → y={end_x}")

    def scroll_left(self, start_x: int, end_x: int, y: int, duration: int = 600):
   
        self.swipe(start_x, y, end_x, y, duration)
        logger.info(f"[SCROLL trai] từ x={start_x} → y={end_x}")
        # =============================================================
    # 9. GỬI PHÍM ẢO (KEY EVENT) – MŨI TÊN, BACK, HOME...
    # =============================================================
    def press_key(self, keycode: int, long_press: bool = False):
        """
        Gửi phím ảo theo keycode Android
        :param keycode: Mã phím (xem bảng dưới)
        :param long_press: Giữ phím lâu (thêm --longpress)
        """
        cmd = f"input keyevent {keycode}"
        if long_press:
            cmd += " --longpress"
        self.device.shell(cmd)
        logger.info(f"[KEY] {self._keycode_to_name(keycode)} (code: {keycode})" + (" [LONG]" if long_press else ""))
    
    def _keycode_to_name(self, code: int) -> str:
        """Chuyển keycode → tên dễ đọc"""
        names = {
            19: "UP", 20: "DOWN", 21: "LEFT", 22: "RIGHT",
            4: "BACK", 3: "HOME", 82: "MENU", 66: "ENTER"
        }
        return names.get(code, f"KEY_{code}")

 

    def swipe_path(self, points: List[Tuple[int, int]], duration_per_segment: int = 200):
        """Kéo theo danh sách điểm liên tiếp (đường xanh)"""
        if len(points) < 2:
            logger.warning("[SWIPE PATH] Danh sách điểm quá ngắn")
            return

        for i in range(1, len(points)):
            sx, sy = points[i-1]
            ex, ey = points[i]
            self.swipe(sx, sy, ex, ey, duration_per_segment)
            time.sleep(0.1)  
    def drag_smooth(self, points: list, total_duration_ms: int = 1200):
        if len(points) < 2:
            logger.warning("Cần ít nhất 2 điểm để kéo!")
            return

        seg_count = len(points) - 1
        seg_ms = max(30, total_duration_ms // seg_count)  # tối thiểu 30ms

        logger.info(f"[DRAG] {seg_count} đoạn, mỗi đoạn {seg_ms}ms")

        for i in range(seg_count):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            self.device.shell(f"input swipe {x1} {y1} {x2} {y2} {31}")

    def wait_for_tap(self, timeout: int = 30):
        """
        Chờ bạn TAP trên scrcpy → ADB nhận → trả tọa độ
        """
        logger.info(f"Chờ bạn TAP trên cửa sổ scrcpy... (timeout: {timeout}s)")

        start_time = time.time()
        self.device.shell("rm -f /sdcard/tap.log")  # Xóa log cũ

        # Bắt sự kiện input
        self.device.shell("getevent -l /dev/input/event* > /sdcard/tap.log &")
        time.sleep(1)

        while time.time() - start_time < timeout:
            output = self.device.shell("cat /sdcard/tap.log | tail -n 20")
            if "ABS_MT_POSITION_X" in output and "ABS_MT_POSITION_Y" in output:
                import re
                lines = output.strip().split('\n')
                x, y = None, None
                for line in lines:
                    if "ABS_MT_POSITION_X" in line:
                        x = int(re.search(r"ABS_MT_POSITION_X +([0-9a-fA-F]+)", line).group(1), 16)
                    if "ABS_MT_POSITION_Y" in line:
                        y = int(re.search(r"ABS_MT_POSITION_Y +([0-9a-fA-F]+)", line).group(1), 16)
                        if x is not None and y is not None:
                            logger.info(f"TAP NHẬN ĐƯỢC: ({x}, {y})")
                            self.device.shell("pkill -f getevent")
                            return (x, y)
            time.sleep(0.2)

        logger.warning("Hết thời gian chờ TAP!")
        self.device.shell("pkill -f getevent")
        return None
    
  
# core/adb.py
def screenshot_scrcpy(save_path="cache/screen.png"):
    """Dùng scrcpy + screencap → ảnh sạch 100%"""
    os.system("adb shell screencap -p /sdcard/screen.png")
    os.system(f"adb pull /sdcard/screen.png {save_path}")
    return cv2.imread(save_path)

