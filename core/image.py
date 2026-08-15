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

def get_resource_path(path: str) -> str:
    """Lấy đường dẫn tài nguyên (hỗ trợ đọc cả file trên ổ đĩa và file đóng gói trong .exe)."""
    if not path:
        return path
    if os.path.exists(path):
        return path
    import sys
    if getattr(sys, 'frozen', False):
        base_dir = getattr(sys, '_MEIPASS', os.path.abspath('.'))
        bundled_path = os.path.join(base_dir, path)
        if os.path.exists(bundled_path):
            return bundled_path
    return path

# adb = ADBController(serial=DEVICE_SERIAL)  
tesseract_bin = os.path.join("tools", "tesseract", "tesseract.exe")
pytesseract.pytesseract.tesseract_cmd = get_resource_path(tesseract_bin)
class ImageProcessor:
    def __init__(self, cache_dir: str = "cache/images"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        
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
    

    def find_ui_element(self, screen_path: str, template_path: str, threshold: float = 0.7, region: Optional[Tuple[int, int, int, int]] = None):
        """Tìm giao diện (bảng, nút, giỏ) trong ảnh"""
        screen = cv2.imread(screen_path)
        template = cv2.imread(template_path, cv2.IMREAD_UNCHANGED)
        
        if template.shape[2] == 4:  # Có alpha
            template = template[:, :, :3]

        rx, ry = 0, 0
        if region is not None:
            rx, ry, rw, rh = region
            h_max, w_max = screen.shape[:2]
            rx = max(0, min(rx, w_max - 1))
            ry = max(0, min(ry, h_max - 1))
            rw = max(1, min(rw, w_max - rx))
            rh = max(1, min(rh, h_max - ry))
            screen = screen[ry:ry+rh, rx:rx+rw]

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
        
        if region is not None:
            points = [(pt[0] + rx, pt[1] + ry) for pt in points]
        return points
    
    def find_template(self, template_path: str, threshold: float=0.8, screen_path: str=None, screen_img: np.ndarray=None, region: Optional[Tuple[int, int, int, int]] = None):
        """
        Tìm template trong screen với color verification
        :param template_path: Đường dẫn ảnh mẫu
        :param threshold: Ngưỡng match
        :param screen_path: Đường dẫn ảnh screen (dùng 1 trong 2)
        :param screen_img: Numpy array của screen (ưu tiên nếu có)
        :param region: Vùng tìm kiếm (x, y, w, h)
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

        rx, ry = 0, 0
        if region is not None:
            rx, ry, rw, rh = region
            h_max, w_max = screen.shape[:2]
            rx = max(0, min(rx, w_max - 1))
            ry = max(0, min(ry, h_max - 1))
            rw = max(1, min(rw, w_max - rx))
            rh = max(1, min(rh, h_max - ry))
            screen = screen[ry:ry+rh, rx:rx+rw]

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
                    matched_region = screen[y0:y1, x0:x1]
                    
                    if matched_region.size == 0 or matched_region.shape[0] == 0 or matched_region.shape[1] == 0:
                        return None
                    
                    reg_hsv = cv2.cvtColor(matched_region, cv2.COLOR_BGR2HSV)

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
                        logger.info(f"[COLOR_CHECK_REJECT] {template_name} at ({cx + rx},{cy + ry}): hue_diff={hue_diff:.1f}°, sat_ratio={sat_ratio:.2f} (tpl_h={dominant_hue:.1f}°, reg_h={reg_hue:.1f}°)")
                        os.makedirs('debug/color_check', exist_ok=True)
                        dbg_path = f"debug/color_check/{template_name}__{cx + rx}_{cy + ry}.png"
                        cv2.imwrite(dbg_path, matched_region)
                        return None
                    else:
                        logger.info(f"[COLOR_CHECK_PASS] {template_name}: hue_diff={hue_diff:.1f}°, sat_ratio={sat_ratio:.2f}")
                        
            except Exception as e:
                logger.info(f"[COLOR_CHECK_ERROR] {template_name}: {e}")
                # Nếu lỗi color check, vẫn trả về kết quả matching
                pass

            # Trả về tọa độ tâm template
            logger.info(f"[MATCH_SUCCESS] {template_name} at ({cx + rx},{cy + ry}) score={best_score:.3f} method={match_method}")
            return (cx + rx, cy + ry)

        return None

    def _match_one(
        self,
        template_path: str,
        threshold: float = 0.8,
        screen_path: str = None,
        screen_img: np.ndarray = None,
        region: Optional[Tuple[int, int, int, int]] = None
    ) -> Optional[Tuple[int, int]]:
        """
        So khop 1 template tren screen (grayscale + color verification).
        Tra ve (x, y) neu tim thay, nguoc lai None.
        """
        if screen_img is not None:
            screen = screen_img
        elif screen_path:
            screen = cv2.imread(screen_path)
        else:
            logger.warning("Can truyen screen_path hoac screen_img")
            return None

        template = cv2.imread(str(template_path), cv2.IMREAD_UNCHANGED)
        if template is None:
            logger.warning(f"Khong tai duoc anh mau: {template_path}")
            return None

        if template.ndim == 3 and template.shape[2] == 4:
            tpl_bgr = template[:, :, :3]
            tpl_alpha = template[:, :, 3]
            tpl_mask = (tpl_alpha > 10).astype("uint8")
        else:
            tpl_bgr = template
            tpl_mask = None

        rx, ry = 0, 0
        if region is not None:
            rx, ry, rw, rh = region
            h_max, w_max = screen.shape[:2]
            rx = max(0, min(rx, w_max - 1))
            ry = max(0, min(ry, h_max - 1))
            rw = max(1, min(rw, w_max - rx))
            rh = max(1, min(rh, h_max - ry))
            screen = screen[ry:ry+rh, rx:rx+rw]

        h, w = tpl_bgr.shape[:2]
        if h > screen.shape[0] or w > screen.shape[1]:
            return None

        gray_screen = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        gray_tpl = cv2.cvtColor(tpl_bgr, cv2.COLOR_BGR2GRAY)
        result = cv2.matchTemplate(gray_screen, gray_tpl, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)
        if locations[0].size == 0:
            return None

        candidates = []
        for pt in zip(*locations[::-1]):
            score = float(result[pt[1], pt[0]])
            candidates.append((score, pt[0], pt[1]))
        candidates.sort(reverse=True, key=lambda x: x[0])
        candidates = candidates[:120]

        for score, x, y in candidates:
            matched_region = screen[y:y + h, x:x + w]
            if matched_region.shape[0] != h or matched_region.shape[1] != w:
                continue
            if self._color_pass(tpl_bgr, matched_region, tpl_mask):
                return (x + rx, y + ry)

        return None

    def _color_pass(self, tpl_bgr: np.ndarray, region_bgr: np.ndarray, tpl_mask: Optional[np.ndarray] = None) -> bool:
        # HSV dominant hue + saturation check to reject wrong colors
        tpl_hsv = cv2.cvtColor(tpl_bgr, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([tpl_hsv], [0], tpl_mask, [18], [0, 180])
        dominant_idx = int(np.argmax(hist))
        tpl_hue = (dominant_idx + 0.5) * (180.0 / 18.0)

        tpl_sat = tpl_hsv[:, :, 1]
        if tpl_mask is not None:
            sat_vals = tpl_sat[tpl_mask.astype(bool)]
        else:
            sat_vals = tpl_sat.flatten()
        tpl_sat_med = float(np.median(sat_vals)) if sat_vals.size > 0 else 0.0

        reg_hsv = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2HSV)
        reg_hist = cv2.calcHist([reg_hsv], [0], None, [18], [0, 180])
        reg_idx = int(np.argmax(reg_hist))
        reg_hue = (reg_idx + 0.5) * (180.0 / 18.0)
        reg_sat_med = float(np.median(reg_hsv[:, :, 1].flatten()))

        hue_diff = abs(tpl_hue - reg_hue)
        hue_diff = min(hue_diff, 180 - hue_diff)
        sat_ratio = (reg_sat_med + 1.0) / (tpl_sat_med + 1.0)

        if tpl_sat_med > 20:
            if hue_diff > 12:
                return False
            if not (0.85 <= sat_ratio <= 1.35):
                return False
            return True

        # Low saturation: fallback to mean color distance
        tpl_mean = np.mean(tpl_bgr.astype(np.float32), axis=(0, 1))
        reg_mean = np.mean(region_bgr.astype(np.float32), axis=(0, 1))
        color_dist = float(np.sqrt(np.sum((tpl_mean - reg_mean) ** 2)))
        return color_dist <= 80

    def find_template_color_detail(
        self,
        template_path: str,
        threshold: float = 0.75,
        color_threshold: float = 0.6,
        screen_path: str = None,
        screen_img: np.ndarray = None,
        region: Optional[Tuple[int, int, int, int]] = None,
        find_all: bool = False
    ) -> Dict:
        """
        Tìm template với thuật toán kết hợp BGR/Alpha Mask Shape + 2D HSV Color Histogram.
        Trả về dictionary chi tiết kết quả phục vụ vẽ khung, debug và phân tích so sánh.
        """
        if screen_img is not None:
            screen = screen_img
        elif screen_path:
            screen = cv2.imread(screen_path)
        else:
            logger.warning("Cần truyền screen_path hoặc screen_img")
            return {"found": False, "reason": "Thiếu ảnh màn hình (screen_img hoặc screen_path)"}

        template_path = get_resource_path(str(template_path))
        template = cv2.imread(template_path, cv2.IMREAD_UNCHANGED)
        if template is None:
            logger.warning(f"Không tải được ảnh mẫu: {template_path}")
            return {"found": False, "reason": f"Không tải được ảnh mẫu: {template_path}"}

        rx, ry = 0, 0
        if region is not None:
            rx, ry, rw, rh = region
            h_max, w_max = screen.shape[:2]
            rx = max(0, min(rx, w_max - 1))
            ry = max(0, min(ry, h_max - 1))
            rw = max(1, min(rw, w_max - rx))
            rh = max(1, min(rh, h_max - ry))
            screen = screen[ry:ry+rh, rx:rx+rw]

        th_orig, tw_orig = template.shape[:2]
        template_name = os.path.basename(template_path).replace('.png', '')
        template_name_lower = template_name.lower()
        is_item_template = (
            (template_name_lower.startswith("kho_") or template_name_lower.startswith("ch_")) and
            not any(h in template_name_lower for h in ["_thanh_pham", "_nong_san", "_vat_dung", "_event"]) and
            th_orig >= 40 and tw_orig >= 50
        )

        alpha_mask = None
        if template.ndim == 3 and template.shape[2] == 4:
            alpha_mask = template[:, :, 3].copy()
            alpha_mask = (alpha_mask > 10).astype(np.uint8) * 255
            template_bgr = template[:, :, :3]
        else:
            template_bgr = template.copy()
            if is_item_template:
                th, tw = template_bgr.shape[:2]
                alpha_mask = np.ones((th, tw), dtype=np.uint8) * 255

        if is_item_template and alpha_mask is not None:
            th, tw = template_bgr.shape[:2]
            x_start = int(tw * 0.55)
            y_start = int(th * 0.60)
            alpha_mask[y_start:, x_start:] = 0

        th, tw = template_bgr.shape[:2]

        if th > screen.shape[0] or tw > screen.shape[1]:
            return {
                "found": False,
                "reason": f"Kích thước ảnh mẫu ({tw}x{th}) lớn hơn màn hình ({screen.shape[1]}x{screen.shape[0]})",
                "template_name": template_name,
                "template_size": (tw, th)
            }

        # BUG FIX 1: dùng masked matchTemplate nếu có alpha
        if alpha_mask is not None:
            result = cv2.matchTemplate(
                screen, template_bgr, cv2.TM_CCORR_NORMED, mask=alpha_mask
            )
        else:
            result = cv2.matchTemplate(screen, template_bgr, cv2.TM_CCOEFF_NORMED)

        locations = np.where(result >= threshold)
        candidates = []
        used = []

        for pt in zip(*locations[::-1]):
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
            logger.debug(f"[FIND_COLOR] {template_name} NOT found (no BGR match >= {threshold})")
            return {
                "found": False,
                "reason": f"Không có vị trí nào khớp hình dạng >= {threshold:.2f}",
                "template_name": template_name,
                "template_size": (tw, th),
                "candidates_count": 0,
                "matches_count": 0
            }

        tpl_hsv = cv2.cvtColor(template_bgr, cv2.COLOR_BGR2HSV)
        h_bins, s_bins = 30, 32
        hist_ranges = [0, 180, 0, 256]
        tpl_hist = cv2.calcHist([tpl_hsv], [0, 1], alpha_mask, [h_bins, s_bins], hist_ranges)
        cv2.normalize(tpl_hist, tpl_hist, 0, 1, cv2.NORM_MINMAX)

        matches = []
        best_match = None
        best_combined_score = 0.0
        best_rejected = None

        for (x, y, shape_score) in candidates:
            matched_region = screen[y:y+th, x:x+tw]
            if matched_region.shape[0] != th or matched_region.shape[1] != tw:
                continue

            reg_hsv = cv2.cvtColor(matched_region, cv2.COLOR_BGR2HSV)
            reg_hist = cv2.calcHist([reg_hsv], [0, 1], alpha_mask, [h_bins, s_bins], hist_ranges)
            cv2.normalize(reg_hist, reg_hist, 0, 1, cv2.NORM_MINMAX)

            color_score = float(cv2.compareHist(tpl_hist, reg_hist, cv2.HISTCMP_CORREL))

            # Loại ngay nếu color_score âm (màu ngược chiều)
            if color_score < 0:
                continue

            combined = float(0.4 * shape_score + 0.6 * color_score)
            item_info = {
                "x": int(x + rx),
                "y": int(y + ry),
                "w": int(tw),
                "h": int(th),
                "center": (int(x + rx + tw // 2), int(y + ry + th // 2)),
                "shape_score": float(shape_score),
                "color_score": float(color_score),
                "combined_score": float(combined),
                "matched_region": matched_region
            }

            logger.debug(
                f"[FIND_COLOR] {template_name} candidate ({x + rx},{y + ry}): "
                f"shape={shape_score:.3f} color={color_score:.3f} combined={combined:.3f}"
            )

            if color_score >= color_threshold:
                matches.append(item_info)
                if combined > best_combined_score:
                    best_combined_score = combined
                    best_match = item_info
            else:
                if best_rejected is None or combined > best_rejected["combined_score"]:
                    best_rejected = item_info

        if not matches:
            reason = f"Tìm thấy {len(candidates)} vị trí hình dạng nhưng bị loại do điểm màu < {color_threshold:.2f}"
            if best_rejected:
                reason += f" (điểm màu cao nhất: {best_rejected['color_score']:.3f})"
            logger.info(f"[FIND_COLOR] {template_name} REJECT ({reason})")
            return {
                "found": False,
                "reason": reason,
                "template_name": template_name,
                "template_size": (tw, th),
                "candidates_count": len(candidates),
                "matches_count": 0,
                "best_rejected": best_rejected
            }

        return {
            "found": True,
            "center": best_match["center"],
            "box": (best_match["x"], best_match["y"], best_match["w"], best_match["h"]),
            "shape_score": best_match["shape_score"],
            "color_score": best_match["color_score"],
            "combined_score": best_match["combined_score"],
            "template_name": template_name,
            "template_size": (tw, th),
            "candidates_count": len(candidates),
            "matches_count": len(matches),
            "all_matches": matches,
            "matched_region": best_match["matched_region"]
        }

    def find_template_color(
        self,
        template_path: str,
        threshold: float = 0.75,
        color_threshold: float = 0.6,
        screen_path: str = None,
        screen_img: np.ndarray = None,
        region: Optional[Tuple[int, int, int, int]] = None
    ) -> Optional[Tuple[int, int]]:
        detail = self.find_template_color_detail(
            template_path=template_path,
            threshold=threshold,
            color_threshold=color_threshold,
            screen_path=screen_path,
            screen_img=screen_img,
            region=region,
            find_all=False
        )
        if detail.get("found"):
            cx, cy = detail["center"]
            logger.info(
                f"[FIND_COLOR] {detail.get('template_name')}: ({cx},{cy}) "
                f"shape={detail.get('shape_score', 0):.3f} color={detail.get('color_score', 0):.3f} combined={detail.get('combined_score', 0):.3f}"
            )
            return detail["center"]
        return None

    def count_template_color(
        self,
        template_path: str,
        threshold: float = 0.75,
        color_threshold: float = 0.6,
        screen_img: np.ndarray = None,
        region: Optional[Tuple[int, int, int, int]] = None
    ) -> int:
        """
        Đếm số lượng template xuất hiện trên screen (dùng color matching).
        Cùng thuật toán find_template_color nhưng trả về count thay vì vị trí.
        """
        if screen_img is None:
            return 0
        detail = self.find_template_color_detail(
            template_path=template_path,
            threshold=threshold,
            color_threshold=color_threshold,
            screen_img=screen_img,
            region=region,
            find_all=True
        )
        count = detail.get("matches_count", 0)
        template_name = os.path.basename(template_path).replace('.png', '')
        logger.debug(f"[COUNT_COLOR] {template_name}: {count} matches")
        return count

    def find_exact(self, template_path: str, threshold: float = 0.8, screen_path: str = None, screen_img: np.ndarray = None, region: Optional[Tuple[int, int, int, int]] = None) -> Optional[Tuple[int, int]]:
        """
        Tìm ảnh mẫu trong screenshot - PHÂN BIỆT MÀU CHÍNH XÁC
        Bước 1: Grayscale matching → tìm tất cả vị trí có hình dạng giống
        Bước 2: So sánh mean color BGR → chọn vị trí đúng màu

        :param template_path: Đường dẫn ảnh mẫu
        :param threshold: Ngưỡng matching hình dạng (0-1)
        :param screen_path: Đường dẫn screenshot
        :param screen_img: Hoặc numpy array screenshot
        :param region: Vùng tìm kiếm (x, y, w, h)
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

        rx, ry = 0, 0
        if region is not None:
            rx, ry, rw, rh = region
            h_max, w_max = screen.shape[:2]
            rx = max(0, min(rx, w_max - 1))
            ry = max(0, min(ry, h_max - 1))
            rw = max(1, min(rw, w_max - rx))
            rh = max(1, min(rh, h_max - ry))
            screen = screen[ry:ry+rh, rx:rx+rw]

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
            matched_region = screen[y:y+th, x:x+tw]
            if matched_region.shape[0] != th or matched_region.shape[1] != tw:
                continue

            reg_mean = np.mean(matched_region.astype(np.float32), axis=(0, 1))
            color_dist = float(np.sqrt(np.sum((tpl_mean - reg_mean) ** 2)))

            logger.debug(f"[FIND_EXACT] candidate ({x + rx},{y + ry}) score={score:.3f} color_dist={color_dist:.1f}")

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

        logger.info(f"[FIND_EXACT] {template_name}: ({cx + rx},{cy + ry}) score={score:.3f} color_dist={best_color_dist:.1f}")
        return (cx + rx, cy + ry)