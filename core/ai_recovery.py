# core/ai_recovery.py
"""
AI Recovery System - Sử dụng Gemini VLM để tự động nhận diện và gỡ kẹt (popup, quảng cáo, mất kết nối)
"""

import cv2
import numpy as np
import base64
import requests
import json
import logging
from typing import Tuple, Optional, Dict
import config

logger = logging.getLogger(__name__)


class AIRecovery:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or getattr(config, "GEMINI_API_KEY", "")
        
    def is_enabled(self) -> bool:
        return bool(self.api_key and getattr(config, "ENABLE_AI_RECOVERY", False))

    def analyze_and_recover(self, screenshot: np.ndarray) -> Optional[Dict]:
        """
        Gửi ảnh chụp màn hình tới Gemini để phân tích trạng thái kẹt.
        Nếu phát hiện bị kẹt, trả về thông tin hành động và tọa độ click thực tế (đã scale lại).
        """
        if not self.is_enabled():
            logger.debug("[AI_RECOVERY] AI Recovery chưa được bật hoặc thiếu API Key.")
            return None

        if screenshot is None:
            logger.warning("[AI_RECOVERY] Ảnh screenshot đầu vào là None.")
            return None

        # 1. Resize ảnh để giảm dung lượng mạng và chuẩn hóa tọa độ nhận diện
        h, w = screenshot.shape[:2]
        target_width = 600
        scale = target_width / w
        target_height = int(h * scale)
        resized = cv2.resize(screenshot, (target_width, target_height))
        
        # Mã hóa thành bytes JPEG để tối ưu dung lượng (tiết kiệm 90% bandwidth)
        success, encoded_img = cv2.imencode(".jpg", resized, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not success:
            logger.error("[AI_RECOVERY] Lỗi encode ảnh.")
            return None
        image_bytes = encoded_img.tobytes()

        # 2. Chuẩn bị prompt hướng dẫn chi tiết
        prompt = (
            "Bạn là một trợ lý AI phân tích game Android (Khu Vườn Trên Mây).\n"
            "Đây là ảnh chụp màn hình hiện tại của game. Trạng thái hiện tại của bot là đang bị KẸT (không thể tiếp tục farm).\n"
            "Nhiệm vụ của bạn là:\n"
            "1. Xác định xem màn hình có đang hiển thị popup quảng cáo, thông báo lỗi, mất kết nối, captcha, hoặc bảng thông tin sự kiện che mất vườn hay không.\n"
            "2. Nếu có, hãy tìm vị trí nút đóng (thường là nút có dấu X, nút 'Đóng', 'Thoát', 'Xác nhận', 'Thử lại', hoặc nhấp ra ngoài để tắt popup).\n"
            "3. Trả về kết quả dưới định dạng JSON duy nhất, KHÔNG chứa các ký tự định dạng markdown như ```json.\n\n"
            "Cấu trúc JSON yêu cầu:\n"
            "{\n"
            '  "is_stuck": true/false,\n'
            '  "reason": "Mô tả ngắn gọn lỗi/popup bằng tiếng Việt",\n'
            '  "action": "click" hoặc "none",\n'
            '  "target_coords": [x, y],\n'
            '  "description": "Mô tả nút/hành động cần bấm"\n'
            "}\n\n"
            f"CHÚ Ý: Tọa độ target_coords [x, y] phải nằm trong kích thước ảnh này: Chiều rộng {target_width}px, Chiều cao {target_height}px. "
            "Trực quan hóa hệ tọa độ với gốc [0,0] là góc trên cùng bên trái. "
            "Hãy ước lượng thật chính xác tâm của nút cần click."
        )

        # 3. Gọi Gemini API qua direct HTTP requests
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inlineData": {
                                "mimeType": "image/jpeg",
                                "data": image_b64
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1
            }
        }

        logger.info("[AI_RECOVERY] Đang gửi yêu cầu phân tích kẹt tới Gemini API...")
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=25)
            response.raise_for_status()
            res_json = response.json()
            
            # Trích xuất text phản hồi
            resp_text = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
            logger.info(f"[AI_RECOVERY] Phản hồi từ Gemini: {resp_text}")
            
            # Parse JSON kết quả
            data = json.loads(resp_text)
            
            # 4. Map tọa độ ngược lại kích thước màn hình gốc nếu có click action
            if data.get("is_stuck") and data.get("action") == "click" and data.get("target_coords"):
                tx, ty = data["target_coords"]
                # Scale lại tọa độ gốc
                orig_x = int(tx / scale)
                orig_y = int(ty / scale)
                data["original_coords"] = [orig_x, orig_y]
                logger.info(f"[AI_RECOVERY] Phát hiện kẹt: {data['reason']}. Đề xuất click tọa độ gốc: ({orig_x}, {orig_y})")
            else:
                logger.info("[AI_RECOVERY] Gemini đánh giá không bị kẹt hoặc không cần hành động click.")
                
            return data

        except Exception as e:
            logger.error(f"[AI_RECOVERY] Lỗi khi gọi Gemini API hoặc parse kết quả: {e}")
            return None


if __name__ == "__main__":
    # Test nhanh module
    import sys
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) < 3:
        print("Usage: python ai_recovery.py <api_key> <path_to_screenshot>")
        sys.exit(1)
        
    api_key = sys.argv[1]
    img_path = sys.argv[2]
    
    img = cv2.imread(img_path)
    if img is None:
        print(f"Không thể đọc ảnh: {img_path}")
        sys.exit(1)
        
    config.ENABLE_AI_RECOVERY = True
    recovery = AIRecovery(api_key=api_key)
    result = recovery.analyze_and_recover(img)
    print("\nKết quả kiểm tra:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
