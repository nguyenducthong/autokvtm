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
from config import SIZE
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
    def screenshot_full(self, save_path: str = None) -> np.ndarray:
        """
        Chụp toàn màn hình → trả về ảnh OpenCV (không lưu file nếu không cần)
        :param save_path: Đường dẫn lưu ảnh (None = chỉ trả về memory)
        :return: np.ndarray (BGR)
        """
        try:
            # Chụp màn hình trực tiếp vào memory (không qua file)
            logger.debug(f"[SCREEN] Đang chụp màn hình...")
            png_bytes = self.device.screencap()

            # Decode từ bytes sang numpy array
            img_array = np.frombuffer(png_bytes, dtype=np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

            if img is None:
                raise ValueError("Không decode được ảnh từ screencap")

            # Chỉ lưu file nếu có yêu cầu
            if save_path:
                save_dir = os.path.dirname(save_path)
                if save_dir and save_dir != '':
                    os.makedirs(save_dir, exist_ok=True)
                cv2.imwrite(save_path, img)

            logger.debug(f"[SCREEN] Chụp thành công: {img.shape[1]}x{img.shape[0]}")
            return img

        except Exception as e:
            logger.error(f"[SCREEN] Lỗi chụp màn hình: {e}")
            raise Exception(f"Không thể chụp màn hình: {str(e)}")

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
    def tap(self, x: int, y: int, delay: float = 0.1):
        """Tap vào tọa độ tuyệt đối"""
        self.device.shell(f"input tap {x} {y}")
        logger.debug(f"[TAP] ({x}, {y})")
        time.sleep(delay)
    def taps(self, x: int, y: int, count: int= 1, delay: float = 0.01):
        """Tap nhiều vào tọa độ tuyệt đối"""
        for i in range(count):
            self.tap(x, y, delay)

    def tap_fast(self, x: int, y: int, count: int = 1):
        """
        Tap nhanh liên tục - gộp nhiều tap thành 1 lệnh shell
        Nhanh hơn taps() vì chỉ gửi 1 lệnh duy nhất
        """
        if count <= 0:
            return
        # Gộp nhiều lệnh tap thành 1 chuỗi
        cmd = " && ".join([f"input tap {x} {y}" for _ in range(count)])
        self.device.shell(cmd)
        logger.debug(f"[TAP_FAST] ({x}, {y}) x{count}")

    def tap_sendevent_fast(self, x: int, y: int, count: int = 1, event: str = "/dev/input/event2"):
        """Tap nhanh bang sendevent. Dung tot tren LDPlayer khi event2 dung la touch device."""
        if count <= 0:
            return
        sx, sy = self.px_to_system(x, y)
        cmds = []
        for _ in range(count):
            cmds.extend([
                f"sendevent {event} 1 330 1",
                f"sendevent {event} 3 57 0",
                f"sendevent {event} 3 53 {sx}",
                f"sendevent {event} 3 54 {sy}",
                f"sendevent {event} 0 0 0",
                f"sendevent {event} 1 330 0",
                f"sendevent {event} 3 57 -1",
                f"sendevent {event} 0 0 0",
            ])
        try:
            self.device.shell(";".join(cmds))
            logger.debug(f"[TAP_SENDEVENT_FAST] ({x}, {y}) x{count}")
        except Exception as e:
            logger.warning(f"[TAP_SENDEVENT_FAST] failed, fallback tap_fast: {e}")
            self.tap_fast(x, y, count)
        
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
        logger.debug(f"[SWIPE] ({start_x},{start_y}) → ({end_x},{end_y}) [{duration}ms]")
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

    def scroll_right(self, start_x: int, end_x: int, y: int, duration: int = 600):
   
        self.swipe(start_x, y, end_x, y, duration)
        logger.info(f"[SCROLL phai] từ x={start_x} → y={end_x}")

    def scroll_left(self, start_x: int, end_x: int, y: int, duration: int = 600):
   
        self.swipe(start_x, y, end_x, y, duration)
        logger.info(f"[SCROLL trai] từ x={start_x} → y={end_x}")

 
    def drag_smooth(self, points: list, total_duration_ms: int = 1200):
        """
        Kéo mượt qua nhiều điểm - sử dụng send_touch_sendevent để giữ touch liên tục

        Args:
            points: Danh sách các điểm (x, y)
            total_duration_ms: Tổng thời gian kéo (không dùng)
        """
        if len(points) < 2:
            logger.warning("[DRAG] Cần ít nhất 2 điểm để kéo!")
            return

        logger.info(f"[DRAG_SMOOTH] Kéo qua {len(points)} điểm bằng sendevent")
        logger.info(f"[DRAG_SMOOTH] Điểm đầu: {points[0]}, Điểm cuối: {points[-1]}")

        # Sử dụng send_touch_sendevent - giữ touch liên tục thực sự
        self.send_touch_sendevent(points)

    def drag_item(self, start_pos: Tuple[int, int], end_pos: Tuple[int, int], hold_ms: int = 100):
        """
        Kéo thả 1 vật phẩm (nguyên liệu máy, cám, phân bón) từ start_pos sang end_pos.
        Tối ưu: Giữ 100ms ở điểm đầu để game KVTM chắc chắn nhấc được vật phẩm,
        kéo mượt mà vào ô sản xuất và thả tay. Loại bỏ hiện tượng trượt, hụt hoặc khựng.
        """
        self.send_touch_sendevent([start_pos, end_pos], hold_start_ms=hold_ms)


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
    
  
    def screenshot_scrcpy(save_path="cache/screen.png"):
        """Dùng scrcpy + screencap → ảnh sạch 100%"""
        os.system("adb shell screencap -p /sdcard/screen.png")
        os.system(f"adb pull /sdcard/screen.png {save_path}")
        return cv2.imread(save_path)



    def get_touch_device_event(self) -> str:
        """Tự động kiểm tra node thiết bị cảm ứng, mặc định /dev/input/event2."""
        if hasattr(self, "_touch_device_cached") and self._touch_device_cached:
            return self._touch_device_cached
        dev = "/dev/input/event2"
        try:
            out = self.device.shell("getevent -lp")
            import re
            blocks = out.split("add device ")
            for block in blocks:
                if "0035" in block or "ABS_MT_POSITION_X" in block:
                    lines = block.splitlines()
                    if lines:
                        candidate = lines[0].strip()
                        if candidate.startswith("/dev/input/event"):
                            dev = candidate
                            break
        except Exception:
            pass
        self._touch_device_cached = dev
        return dev

    def send_touch_sendevent(self, points, hold_start_ms: int = 120):
        """Gửi touch bằng sendevent qua batch script trên device.
        Tối ưu: Giữ touch 120ms ở điểm đầu để game kịp nhấc giỏ/hạt giống,
        kéo mượt mà qua các chậu (22-25 điểm) thay vì 73 điểm làm giật lag.
        """
        if len(points) < 2:
            return

        points = self.interpolate_points(points=points)
        event = self.get_touch_device_event()
        logger.info(f"[SENDEVENT] Kéo mượt qua {len(points)} điểm trên {event} (hold: {hold_start_ms}ms)")

        cmds = []
        # 1. BTN_TOUCH DOWN + Tọa độ đầu
        cmds.append(f"sendevent {event} 1 330 1")
        cmds.append(f"sendevent {event} 3 57 0")
        cmds.append(f"sendevent {event} 3 53 {points[0][0]}")
        cmds.append(f"sendevent {event} 3 54 {points[0][1]}")
        cmds.append(f"sendevent {event} 0 0 0")

        # Giữ ngón tay một chút ở điểm đầu để game nhận công cụ (giỏ/hạt)
        if hold_start_ms > 0:
            cmds.append(f"sleep {hold_start_ms / 1000.0:.3f}")

        # 2. MOVE qua các điểm (nhịp 8ms/bước mượt mà, không bị khựng)
        for x, y in points[1:]:
            cmds.append(f"sendevent {event} 3 53 {x}")
            cmds.append(f"sendevent {event} 3 54 {y}")
            cmds.append(f"sendevent {event} 0 0 0")
            cmds.append("usleep 8000")

        # 3. BTN_TOUCH UP
        cmds.append(f"sendevent {event} 1 330 0")
        cmds.append(f"sendevent {event} 3 57 -1")
        cmds.append(f"sendevent {event} 0 0 0")

        script_content = "\n".join(cmds)
        try:
            self.device.shell(f"cat << 'EOF' > /data/local/tmp/drag.sh\n{script_content}\nEOF")
            self.device.shell("sh /data/local/tmp/drag.sh")
            logger.info(f"[SENDEVENT] Hoàn thành kéo mượt qua {len(points)} điểm")
        except Exception as e:
            logger.warning(f"[SENDEVENT] Batch script thất bại, fallback gom lệnh shell: {e}")
            try:
                full_cmd = ";".join(cmds)
                self.device.shell(full_cmd)
                logger.info(f"[SENDEVENT] Hoàn thành (fallback inline)")
            except Exception as e2:
                logger.error(f"[SENDEVENT] Lỗi khi gửi sendevent: {e2}")

    def send_touch_sendevent_raw(self, points):
        """Gửi touch bằng sendevent từng lệnh (không gom batch)."""
        self.send_touch_sendevent(points, hold_start_ms=100)

    def px_to_system(self, x_px, y_px):
        """Chuyển tọa độ bạn thấy (px) → hệ thống nhận (LDPlayer 800x800 rot 90: SIZE - y, x)."""
        hx = max(0, min(int(SIZE - y_px), SIZE))
        hy = max(0, min(int(x_px), SIZE))
        return hx, hy

    def interpolate_points(self, points, steps_per_segment=None, max_step_dist: int = 120):
        """
        Nội suy thông minh theo khoảng cách thực tế (Adaptive Distance-based):
        - Các chậu gần nhau trong cùng hàng (khoảng cách 60px <= 120px): lướt trực tiếp qua tâm chậu,
          không chèn điểm thừa để tránh ngón tay bị giật giật, khựng từng nấc 15px.
        - Các đoạn chuyển hàng xa (> 150px): chèn 2-3 điểm dẫn đường để ngón tay không bị teleport.
        -> Giảm tổng số điểm từ 73 điểm xuống ~25 điểm, kéo cực kỳ mượt mà, tự nhiên và dứt khoát.
        """
        if len(points) < 2:
            return [self.px_to_system(p[0], p[1]) for p in points]

        interpolated = [points[0]]

        for i in range(len(points) - 1):
            p1 = points[i]
            p2 = points[i + 1]
            dist = ((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2) ** 0.5

            # Chỉ chèn điểm trung gian nếu khoảng cách giữa 2 điểm xa (chuyển hàng hoặc từ giỏ)
            if dist > max_step_dist:
                steps = max(1, min(int(dist // 90), 4))
                for step in range(1, steps + 1):
                    t = step / float(steps + 1)
                    ix = int(p1[0] + (p2[0] - p1[0]) * t)
                    iy = int(p1[1] + (p2[1] - p1[1]) * t)
                    interpolated.append((ix, iy))

            interpolated.append(p2)

        return [self.px_to_system(p[0], p[1]) for p in interpolated]


