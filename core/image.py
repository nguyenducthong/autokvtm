# core/image.py
"""
Image Processor – Xử lý toàn bộ ảnh trong Auto Khu Vườn Trên Mây
Tính năng:
    - Template matching (tìm ảnh mẫu)
    - Cache ảnh + kết quả
    - Tự động resize ảnh mẫu
    - Lọc nhiễu, tăng độ chính xác
    - Debug: vẽ khung tìm được
"""

import cv2
import numpy as np
import os
import json
import hashlib
from datetime import datetime
from typing import List, Tuple, Optional, Dict
import logging

logger = logging.getLogger(__name__)

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
    
    def find_template(self, screen_path: str, template_path: str, threshold: float=0.8):
        screen = cv2.imread(screen_path)
        template = cv2.imread(template_path)
        if template is None:
            print(f"Không tải được ảnh mẫu: {template_path}")
            return None

        h, w = template.shape[:2]
        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)

        if len(locations[0]) > 0:
            # Lấy vị trí tốt nhất
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            center_x = max_loc[0] + w // 2
            center_y = max_loc[1] + h // 2
            return (center_x, center_y)
        return None