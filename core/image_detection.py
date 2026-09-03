"""
Image Detection - Phát hiện giỏ thu hoạch và menu trồng cây
"""

import cv2
import numpy as np
from typing import Tuple, Optional, List


class ImageDetector:
    """Phát hiện hình ảnh trong screenshot"""

    def __init__(self, threshold=0.7):
        """
        Args:
            threshold: Ngưỡng độ tương đồng (0-1), mặc định 0.7
        """
        self.threshold = threshold

    def _match_one(self, screenshot: np.ndarray, template_path: str, threshold: float = None) -> Optional[Tuple[int, int]]:
        """
        Tìm template trong screenshot

        Args:
            screenshot: Ảnh màn hình (numpy array)
            template_path: Đường dẫn đến ảnh template
            threshold: Ngưỡng tương đồng (nếu None thì dùng self.threshold)

        Returns:
            Tuple (x, y) tọa độ tâm của template, hoặc None nếu không tìm thấy
        """
        if threshold is None:
            threshold = self.threshold

        # Đọc template hỗ trợ alpha
        template = cv2.imread(template_path, cv2.IMREAD_UNCHANGED)
        if template is None:
            return None

        has_alpha = (template.ndim == 3 and template.shape[2] == 4)
        if has_alpha:
            alpha = template[:, :, 3]
            mask = (alpha > 15).astype(np.uint8) * 255
            tpl_bgr = template[:, :, :3]
        else:
            tpl_bgr = template
            mask = None

        h, w = tpl_bgr.shape[:2]
        if h > screenshot.shape[0] or w > screenshot.shape[1]:
            return None

        # Multi-scale matching
        for scale in [1.0, 0.92, 1.08]:
            if abs(scale - 1.0) < 0.01:
                cur_tpl = tpl_bgr
                cur_mask = mask
            else:
                nw, nh = max(4, int(w * scale)), max(4, int(h * scale))
                if nh > screenshot.shape[0] or nw > screenshot.shape[1]:
                    continue
                interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
                cur_tpl = cv2.resize(tpl_bgr, (nw, nh), interpolation=interp)
                cur_mask = cv2.resize(mask, (nw, nh), interpolation=cv2.INTER_NEAREST) if mask is not None else None

            ch, cw = cur_tpl.shape[:2]
            if cur_mask is not None:
                res = cv2.matchTemplate(screenshot, cur_tpl, cv2.TM_CCORR_NORMED, mask=cur_mask)
            else:
                s_gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
                t_gray = cv2.cvtColor(cur_tpl, cv2.COLOR_BGR2GRAY)
                res = cv2.matchTemplate(s_gray, t_gray, cv2.TM_CCOEFF_NORMED)

            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
            if max_val >= threshold:
                center_x = max_loc[0] + cw // 2
                center_y = max_loc[1] + ch // 2
                return (center_x, center_y)

        return None


    def detect_basket(self, screenshot: np.ndarray, basket_template_path: str = "assets/items/core_thu_hoach.png") -> Optional[Tuple[int, int]]:
        """
        Phát hiện giỏ thu hoạch

        Args:
            screenshot: Ảnh màn hình
            basket_template_path: Đường dẫn đến ảnh giỏ thu hoạch

        Returns:
            Tọa độ (x, y) của giỏ, hoặc None nếu không tìm thấy
        """
        return self._match_one(screenshot, basket_template_path)

    def detect_plant_menu(self, screenshot: np.ndarray, plant_templates: List[str]) -> Optional[Tuple[str, int, int]]:
        """
        Phát hiện menu trồng cây và loại cây

        Args:
            screenshot: Ảnh màn hình
            plant_templates: Danh sách đường dẫn template các loại cây

        Returns:
            Tuple (tên_cây, x, y) hoặc None nếu không tìm thấy
        """
        for template_path in plant_templates:
            position = self._match_one(screenshot, template_path)
            if position:
                # Lấy tên cây từ đường dẫn (vd: assets/items/cay_hong.png -> hong)
                import os
                filename = os.path.basename(template_path)
                plant_name = filename.replace("cay_", "").replace(".png", "")
                return (plant_name, position[0], position[1])

        return None

    def analyze_screen(self, screenshot: np.ndarray,
                      basket_template: str = "assets/items/core_thu_hoach.png",
                      plant_templates: List[str] = None) -> dict:
        """
        Phân tích màn hình để quyết định hành động

        Args:
            screenshot: Ảnh màn hình
            basket_template: Template giỏ thu hoạch
            plant_templates: Danh sách template cây trồng

        Returns:
            Dictionary với thông tin:
            {
                'action': 'harvest' | 'plant' | 'none',
                'position': (x, y) hoặc None,
                'plant_name': tên cây (nếu action='plant')
            }
        """
        if plant_templates is None:
            plant_templates = [
                "assets/items/cay_hong.png",
                "assets/items/cay_tao.png",
                "assets/items/cay_bong.png",
                "assets/items/cay_tuyet.png"
            ]

        result = {
            'action': 'none',
            'position': None,
            'plant_name': None
        }

        # Kiểm tra giỏ thu hoạch trước (ưu tiên cao hơn)
        basket_pos = self.detect_basket(screenshot, basket_template)
        if basket_pos:
            result['action'] = 'harvest'
            result['position'] = basket_pos
            return result

        # Nếu không có giỏ, kiểm tra menu trồng cây
        plant_info = self.detect_plant_menu(screenshot, plant_templates)
        if plant_info:
            result['action'] = 'plant'
            result['plant_name'] = plant_info[0]
            result['position'] = (plant_info[1], plant_info[2])
            return result

        return result


if __name__ == "__main__":
    # Test
    detector = ImageDetector(threshold=0.7)

    # Test với ảnh mẫu
    import sys
    if len(sys.argv) > 1:
        screenshot_path = sys.argv[1]
        screenshot = cv2.imread(screenshot_path)

        result = detector.analyze_screen(screenshot)
        print(f"\n[RESULT]")
        print(f"  Action: {result['action']}")
        print(f"  Position: {result['position']}")
        if result['plant_name']:
            print(f"  Plant: {result['plant_name']}")
    else:
        print("Usage: python image_detection.py <screenshot_path>")
