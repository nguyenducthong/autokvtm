import cv2
import numpy as np
import os
import json
import hashlib
from datetime import datetime
from typing import List, Tuple, Optional, Dict
import logging
import pytesseract
# from .adb import ADBController 
# from config import DEVICE_SERIAL
from PIL import Image, ImageEnhance, ImageFilter
logger = logging.getLogger(__name__)
# adb = ADBController(serial=DEVICE_SERIAL)  
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
class ImageProcessor:
    def __init__(self, cache_dir: str = "cache/images"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    # =============================================================
    # 1. TÌM ẢNH MẪU (TEMPLATE MATCHING)
    # =============================================================


    # =============================================================
    # 2. TÌM NHIỀU ẢNH MẪU (MULTI-TEMPLATE)
    # =============================================================
 

    # =============================================================
    # 3. DEBUG: VẼ KHUNG TÌM ĐƯỢC
    # =============================================================
    def draw_matches(
        self,
        screen: np.ndarray,
        points: List[Tuple[int, int]],
        template_path: str,
        save_path: str = "debug/matched.png"
    ):
        """Vẽ khung + lưu ảnh debug"""
        os.makedirs("debug", exist_ok=True)
        img = screen.copy()
        template = cv2.imread(template_path)
        h, w = template.shape[:2]
        for (cx, cy) in points:
            cv2.rectangle(img, (cx - w//2, cy - h//2), (cx + w//2, cy + h//2), (0, 255, 0), 2)
            cv2.putText(img, "MATCH", (cx - 30, cy - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.imwrite(save_path, img)
        logger.debug(f"[DEBUG] Đã lưu ảnh debug: {save_path}")

    # =============================================================
    # 4. CACHE ẢNH + KẾT QUẢ
    # =============================================================
    def _get_cache_key(self, screen: np.ndarray, template_path: str, threshold: float) -> str:
        """Tạo key cache từ ảnh + template + ngưỡng"""
        screen_hash = hashlib.md5(screen.tobytes()).hexdigest()[:8]
        template_hash = hashlib.md5(open(template_path, "rb").read()).hexdigest()[:8]
        return f"{screen_hash}_{template_hash}_{threshold:.2f}"

    def _save_cache(self, key: str, data: List[Tuple[int, int]]):
        path = os.path.join(self.cache_dir, f"{key}.json")
        json.dump({
            "data": data,
            "time": datetime.now().isoformat()
        }, open(path, "w"))

    def _load_cache(self, key: str) -> Optional[List[Tuple[int, int]]]:
        path = os.path.join(self.cache_dir, f"{key}.json")
        if not os.path.exists(path):
            return None
        cache = json.load(open(path))
        age = (datetime.now() - datetime.fromisoformat(cache["time"])).total_seconds()
        if age < 30:  # Cache 30 giây
            return cache["data"]
        return None

    # =============================================================
    # 5. TỰ ĐỘNG RESIZE ẢNH MẪU
    # =============================================================
    def auto_resize_template(self, template_path: str, target_width: int = 1080):
        """Resize ảnh mẫu theo độ phân giải chuẩn"""
        img = cv2.imread(template_path)
        if img.shape[1] == target_width:
            return template_path
        scale = target_width / img.shape[1]
        h, w = img.shape[:2]
        resized = cv2.resize(img, (int(w * scale), int(h * scale)))
        new_path = template_path.replace(".png", "_resized.png")
        cv2.imwrite(new_path, resized)
        logger.info(f"[RESIZE] {template_path} → {new_path}")
        return new_path
    

    def find_ui_element(self, screen_path: str, template_path: str, threshold: float = 0.7):
        """Tìm giao diện (bảng, nút, giỏ) trong ảnh"""
        screen = cv2.imread(screen_path)
        template = cv2.imread(template_path, cv2.IMREAD_UNCHANGED)
        
        if template.shape[2] == 4:  # Có alpha
            template = template[:, :, :3]

        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)
        points = list(zip(*locations[::-1]))  # (x, y)

        # Vẽ khung + lưu ảnh debug
        debug_img = screen.copy()
        for pt in points:
            cv2.rectangle(debug_img, pt, (pt[0] + template.shape[1], pt[1] + template.shape[0]), (0, 255, 0), 2)
        
        debug_path = "debug/found_table.png"
        os.makedirs("debug", exist_ok=True)
        cv2.imwrite(debug_path, debug_img)

        logger.info(f"[MATCH] Tìm thấy {len(points)} vị trí → Xem: {debug_path}")
        return points
    
    def find_template(self, template_path: str, threshold: float=0.8, screen_path: str=None, screen_img: np.ndarray=None):
        """
        Tìm template trong screen với color verification
        :param template_path: Đường dẫn ảnh mẫu
        :param threshold: Ngưỡng match
        :param screen_path: Đường dẫn ảnh screen (dùng 1 trong 2)
        :param screen_img: Numpy array của screen (ưu tiên nếu có)
        :return: Tuple (cx, cy) tọa độ tâm template, hoặc None nếu không tìm thấy
        """
        # Ưu tiên dùng screen_img nếu có, không thì đọc từ file
        if screen_img is not None:
            screen = screen_img
        elif screen_path:
            screen = cv2.imread(screen_path)
        else:
            logger.warning("Cần truyền screen_path hoặc screen_img")
            return None

        # Load template (giữ alpha nếu có)
        template = cv2.imread(str(template_path), cv2.IMREAD_UNCHANGED)
        if template is None:
            logger.warning(f"Không tải được ảnh mẫu: {template_path}")
            return None

        # Nếu template có alpha channel, bỏ alpha trước khi match
        if template.ndim == 3 and template.shape[2] == 4:
            template_rgb = template[:, :, :3]
        else:
            template_rgb = template

        th, tw = template_rgb.shape[:2]

        # Nếu template lớn hơn màn hình thì bỏ qua
        if th > screen.shape[0] or tw > screen.shape[1]:
            return None

        # Chuyển sang grayscale để giảm ảnh hưởng màu sắc
        gray_screen = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        gray_template = cv2.cvtColor(template_rgb, cv2.COLOR_BGR2GRAY)

        # Bình thường hóa tương phản ảnh mẫu
        gray_template = cv2.equalizeHist(gray_template)

        # Match trên grayscale
        result_gray = cv2.matchTemplate(gray_screen, gray_template, cv2.TM_CCOEFF_NORMED)
        min_g, max_g, min_loc_g, max_loc_g = cv2.minMaxLoc(result_gray)

        # Match trên cạnh để tăng độ bền với biến đổi màu
        edges_screen = cv2.Canny(gray_screen, 50, 150)
        edges_template = cv2.Canny(gray_template, 50, 150)
        result_edge = cv2.matchTemplate(edges_screen, edges_template, cv2.TM_CCOEFF_NORMED)
        min_e, max_e, min_loc_e, max_loc_e = cv2.minMaxLoc(result_edge)

        template_name = os.path.basename(template_path)
        logger.debug(f"[MATCH] {template_name}: gray={max_g:.3f}, edge={max_e:.3f} (thresh={threshold})")
        
        # 🔥 DEBUG: log khi matching cao để debug false positive
        if max_g >= 0.75 or max_e >= 0.75:
            logger.info(f"[⚠️ HIGH_MATCH] {template_name}: gray={max_g:.3f}, edge={max_e:.3f}")

        # Chọn kết quả tốt nhất giữa 2 phép match
        if max_g >= threshold or max_e >= threshold:
            # Chọn score và location tốt nhất
            if max_g >= max_e:
                best_score = max_g
                chosen_loc = max_loc_g
                match_method = "gray"
            else:
                best_score = max_e
                chosen_loc = max_loc_e
                match_method = "edge"

            # Tính tâm template
            cx = chosen_loc[0] + tw // 2
            cy = chosen_loc[1] + th // 2

            # ===== COLOR VERIFICATION =====
            try:
                # Extract template color info
                tpl_has_alpha = (template.ndim == 3 and template.shape[2] == 4)
                if tpl_has_alpha:
                    alpha = template[:, :, 3]
                    tpl_mask = (alpha > 10).astype('uint8')
                    tpl_bgr = template[:, :, :3]
                else:
                    tpl_mask = None
                    tpl_bgr = template_rgb

                tpl_hsv = cv2.cvtColor(tpl_bgr, cv2.COLOR_BGR2HSV)

                # Compute dominant hue via histogram (18 bins)
                hist = cv2.calcHist([tpl_hsv], [0], tpl_mask, [18], [0, 180])
                dominant_idx = int(np.argmax(hist))
                dominant_hue = (dominant_idx + 0.5) * (180.0 / 18.0)

                # Median saturation
                tpl_sat = tpl_hsv[:, :, 1]
                if tpl_mask is not None:
                    sat_vals = tpl_sat[tpl_mask.astype(bool)]
                else:
                    sat_vals = tpl_sat.flatten()
                mean_s = float(np.median(sat_vals)) if sat_vals.size > 0 else 0.0

                # Only validate color if template is sufficiently saturated (lowered to 20 to catch pale colors)
                if mean_s > 20:
                    # Extract matched region from screen
                    x0 = int(max(chosen_loc[0], 0))
                    y0 = int(max(chosen_loc[1], 0))
                    x1 = int(min(chosen_loc[0] + tw, screen.shape[1]))
                    y1 = int(min(chosen_loc[1] + th, screen.shape[0]))
                    region = screen[y0:y1, x0:x1]
                    
                    if region.size == 0 or region.shape[0] == 0 or region.shape[1] == 0:
                        return None
                    
                    reg_hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)

                    # Compute dominant hue for region
                    reg_hist = cv2.calcHist([reg_hsv], [0], None, [18], [0, 180])
                    reg_idx = int(np.argmax(reg_hist))
                    reg_hue = (reg_idx + 0.5) * (180.0 / 18.0)

                    # Median saturation for region
                    reg_sat = float(np.median(reg_hsv[:, :, 1].flatten()))

                    # Circular hue difference
                    hue_diff = abs(dominant_hue - reg_hue)
                    hue_diff = min(hue_diff, 180 - hue_diff)

                    sat_ratio = (reg_sat + 1.0) / (mean_s + 1.0)

                    # Stricter thresholds: hue_diff <= 10 deg, sat_ratio within [0.90, 1.25]
                    if hue_diff > 10 or not (0.90 <= sat_ratio <= 1.25):
                        logger.info(f"[COLOR_CHECK_REJECT] {template_name} at ({cx},{cy}): hue_diff={hue_diff:.1f}°, sat_ratio={sat_ratio:.2f} (tpl_h={dominant_hue:.1f}°, reg_h={reg_hue:.1f}°)")
                        os.makedirs('debug/color_check', exist_ok=True)
                        dbg_path = f"debug/color_check/{template_name}__{cx}_{cy}.png"
                        cv2.imwrite(dbg_path, region)
                        return None
                    else:
                        logger.info(f"[COLOR_CHECK_PASS] {template_name}: hue_diff={hue_diff:.1f}°, sat_ratio={sat_ratio:.2f}")
                        
            except Exception as e:
                logger.info(f"[COLOR_CHECK_ERROR] {template_name}: {e}")
                # Nếu lỗi color check, vẫn trả về kết quả matching
                pass

            # Trả về tọa độ tâm template
            logger.info(f"[MATCH_SUCCESS] {template_name} at ({cx},{cy}) score={best_score:.3f} method={match_method}")
            return (cx, cy)

        return None

    def find_exact(self, template_path: str, threshold: float = 0.8, screen_path: str = None, screen_img: np.ndarray = None) -> Optional[Tuple[int, int]]:
        """
        Tìm ảnh mẫu trong screenshot - PHÂN BIỆT MÀU CHÍNH XÁC
        Bước 1: Grayscale matching → tìm tất cả vị trí có hình dạng giống
        Bước 2: So sánh mean color BGR → chọn vị trí đúng màu

        :param template_path: Đường dẫn ảnh mẫu
        :param threshold: Ngưỡng matching hình dạng (0-1)
        :param screen_path: Đường dẫn screenshot
        :param screen_img: Hoặc numpy array screenshot
        :return: (cx, cy) tọa độ tâm, hoặc None
        """
        if screen_img is not None:
            screen = screen_img
        elif screen_path:
            screen = cv2.imread(screen_path)
        else:
            logger.warning("Cần truyền screen_path hoặc screen_img")
            return None

        template = cv2.imread(str(template_path), cv2.IMREAD_UNCHANGED)
        if template is None:
            logger.warning(f"Không tải được ảnh mẫu: {template_path}")
            return None

        # Bỏ alpha nếu có
        if template.ndim == 3 and template.shape[2] == 4:
            template = template[:, :, :3]

        th, tw = template.shape[:2]
        template_name = os.path.basename(template_path).replace('.png', '')

        if th > screen.shape[0] or tw > screen.shape[1]:
            return None

        # ===== BƯỚC 1: Grayscale matching → tìm TẤT CẢ vị trí candidate =====
        gray_screen = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        gray_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        result = cv2.matchTemplate(gray_screen, gray_template, cv2.TM_CCOEFF_NORMED)

        # Lấy tất cả vị trí vượt ngưỡng shape
        locations = np.where(result >= threshold)
        candidates = []
        used = []

        for pt in zip(*locations[::-1]):  # (x, y)
            # Loại trùng lặp (vị trí quá gần nhau)
            is_dup = False
            for u in used:
                if abs(pt[0] - u[0]) < tw // 2 and abs(pt[1] - u[1]) < th // 2:
                    is_dup = True
                    break
            if not is_dup:
                score = float(result[pt[1], pt[0]])
                candidates.append((pt[0], pt[1], score))
                used.append(pt)

        if not candidates:
            logger.debug(f"[FIND_EXACT] {template_name} NOT found (no shape match)")
            return None

        # ===== BƯỚC 2: So sánh mean color BGR → chọn đúng màu =====
        tpl_mean = np.mean(template.astype(np.float32), axis=(0, 1))  # [B, G, R]

        best_match = None
        best_color_dist = 999

        for (x, y, score) in candidates:
            region = screen[y:y+th, x:x+tw]
            if region.shape[0] != th or region.shape[1] != tw:
                continue

            reg_mean = np.mean(region.astype(np.float32), axis=(0, 1))
            color_dist = float(np.sqrt(np.sum((tpl_mean - reg_mean) ** 2)))

            logger.debug(f"[FIND_EXACT] candidate ({x},{y}) score={score:.3f} color_dist={color_dist:.1f}")

            if color_dist < best_color_dist:
                best_color_dist = color_dist
                best_match = (x, y, score)

        if best_match is None:
            return None

        x, y, score = best_match
        cx = x + tw // 2
        cy = y + th // 2

        # Ngưỡng màu: color_dist < 80 mới chấp nhận
        if best_color_dist > 80:
            logger.info(f"[FIND_EXACT] {template_name} REJECT all candidates (best_color_dist={best_color_dist:.1f})")
            return None

        logger.info(f"[FIND_EXACT] {template_name}: ({cx},{cy}) score={score:.3f} color_dist={best_color_dist:.1f}")
        return (cx, cy)

