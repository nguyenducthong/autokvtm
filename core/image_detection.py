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

        # Đọc template
        template = cv2.imread(template_path)
        if template is None:
            raise FileNotFoundError(f"Không tìm thấy template: {template_path}")

        # Convert sang grayscale
        screenshot_gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        # Template matching
        result = cv2.matchTemplate(screenshot_gray, template_gray, cv2.TM_CCOEFF_NORMED)

        # Tìm vị trí có độ tương đồng cao nhất
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            # Lấy tâm của template
            h, w = template_gray.shape
            center_x = max_loc[0] + w // 2
            center_y = max_loc[1] + h // 2
            return (center_x, center_y)

        return None

    def detect_basket(self, screenshot: np.ndarray, basket_template_path: str = "assets/items/thu_hoach.png") -> Optional[Tuple[int, int]]:
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
                      basket_template: str = "assets/items/thu_hoach.png",
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
