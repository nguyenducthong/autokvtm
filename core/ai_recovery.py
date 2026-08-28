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
import time
import csv
import datetime
import os
from typing import Tuple, Optional, Dict
import config

logger = logging.getLogger(__name__)

GEMINI_LOG_DIR = "data/gemini_logs"


def cleanup_old_gemini_logs(max_days: int = 3):
    """Tự động xóa các file CSV nhật ký Gemini cũ hơn max_days (mặc định 3 ngày)."""
    if not os.path.exists(GEMINI_LOG_DIR):
        return
    now = datetime.datetime.now()
    cutoff_date = (now - datetime.timedelta(days=max_days)).date()

    try:
        for fname in os.listdir(GEMINI_LOG_DIR):
            if fname.endswith(".csv"):
                date_part = fname.replace(".csv", "").strip()
                try:
                    file_date = datetime.datetime.strptime(date_part, "%Y-%m-%d").date()
                    if file_date < cutoff_date:
                        fpath = os.path.join(GEMINI_LOG_DIR, fname)
                        os.remove(fpath)
                        logger.info(f"[AI_RECOVERY] Đã tự động xóa file log Gemini cũ quá 3 ngày: {fname}")
                except ValueError:
                    pass
    except Exception as e:
        logger.error(f"[AI_RECOVERY] Lỗi khi dọn dẹp file log Gemini cũ: {e}")


def get_current_gemini_csv_path() -> str:
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    return os.path.join(GEMINI_LOG_DIR, f"{today_str}.csv")


def list_gemini_log_files() -> list:
    """Trả về danh sách file csv trong thư mục data/gemini_logs, sắp xếp mới nhất lên đầu."""
    cleanup_old_gemini_logs(max_days=3)
    if not os.path.exists(GEMINI_LOG_DIR):
        return []
    files = [f for f in os.listdir(GEMINI_LOG_DIR) if f.endswith(".csv")]
    files.sort(reverse=True)
    return files


def log_gemini_request(device_name: str, req_id: int, status: str, http_code: int, reason: str = "", error_details: str = "", raw_response: str = "", model: str = ""):
    """Ghi 1 dòng nhật ký request Gemini vào file CSV của ngày hôm nay và bộ nhớ."""
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    model_str = model or getattr(config, "GEMINI_MODEL", "gemini-3.5-flash-lite") or "gemini-3.5-flash-lite"
    entry = {
        "timestamp": now_str,
        "device": device_name or "main",
        "req_id": req_id,
        "model": model_str,
        "status": status,
        "http_code": http_code,
        "reason": reason,
        "error_details": error_details,
        "raw_response": raw_response
    }

    AIRecovery.log_history.append(entry)
    if len(AIRecovery.log_history) > 500:
        AIRecovery.log_history.pop(0)

    # Cập nhật bộ đếm trong bộ nhớ
    AIRecovery.total_requests += 1
    st_upper = (status or "").upper()
    if st_upper == "SUCCESS":
        AIRecovery.successful_requests += 1
    elif st_upper == "RATELIMIT_429" or http_code == 429:
        AIRecovery.ratelimit_429_count += 1
    else:
        AIRecovery.failed_requests += 1

    # Tự động dọn file cũ quá 3 ngày
    cleanup_old_gemini_logs(max_days=3)

    csv_path = get_current_gemini_csv_path()
    try:
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        file_exists = os.path.isfile(csv_path)
        with open(csv_path, mode="a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Timestamp", "Device", "RequestID", "Model", "Status", "HTTPCode", "Reason", "ErrorDetails"])
            writer.writerow([now_str, device_name or "main", f"#{req_id}", model_str, status, http_code, reason, error_details])
    except Exception as e:
        logger.error(f"[AI_RECOVERY] Lỗi khi ghi file CSV Gemini log: {e}")


class AIRecovery:
    _last_call_time: float = 0.0
    _min_interval: float = 10.0  # Khoảng cách tối thiểu giữa 2 lần gọi (giây) để tránh HTTP 429

    # Bộ đếm số lần Request tới Gemini AI
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    ratelimit_429_count: int = 0
    log_history: list = []  # Lịch sử các request

    @classmethod
    def get_stats(cls) -> Dict[str, int]:
        """Lấy thống kê request Gemini hôm nay (tự động đếm trực tiếp từ file CSV ngày hôm nay)."""
        today_csv = get_current_gemini_csv_path()
        if os.path.isfile(today_csv):
            total = 0
            success = 0
            ratelimit_429 = 0
            failed = 0
            try:
                with open(today_csv, mode="r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        total += 1
                        st = (row.get("Status") or "").upper()
                        code = str(row.get("HTTPCode") or "")
                        if st == "SUCCESS":
                            success += 1
                        elif st == "RATELIMIT_429" or code == "429":
                            ratelimit_429 += 1
                        else:
                            failed += 1
                cls.total_requests = total
                cls.successful_requests = success
                cls.ratelimit_429_count = ratelimit_429
                cls.failed_requests = failed
            except Exception as e:
                logger.error(f"[AI_RECOVERY] Lỗi đếm stats từ CSV: {e}")

        return {
            "total": cls.total_requests,
            "success": cls.successful_requests,
            "failed": cls.failed_requests,
            "ratelimit_429": cls.ratelimit_429_count
        }

    @classmethod
    def reset_stats(cls):
        cls.total_requests = 0
        cls.successful_requests = 0
        cls.failed_requests = 0
        cls.ratelimit_429_count = 0
        cls.log_history.clear()

    def __init__(self, api_key: str = None):
        self.api_key = api_key or getattr(config, "GEMINI_API_KEY", "")
        
    def is_enabled(self) -> bool:
        return bool(self.api_key and getattr(config, "ENABLE_AI_RECOVERY", False))

    def analyze_and_recover(self, screenshot: np.ndarray, device_name: str = None) -> Optional[Dict]:
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

        if not device_name:
            try:
                from utils.utils import get_device_name
                device_name = get_device_name() or "main"
            except Exception:
                device_name = "main"

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
            f"CHÚ Ý TỌA ĐỘ: Tọa độ target_coords [x, y] BẮT BUỘC dùng hệ tọa độ chuẩn hóa từ 0 đến 1000 (normalized scale [0, 1000]). Trong đó x từ 0 (mép trái) đến 1000 (mép phải), y từ 0 (mép trên) đến 1000 (mép dưới). "
            "Trực quan hóa hệ tọa độ với gốc [0,0] là gốc trên cùng bên trái. "
            "Hãy ước lượng thật chính xác tâm của nút cần click."
        )

        # 3. Gọi Gemini API với cơ chế Retry Exponential Backoff (Tối ưu cho tài khoản Pro khi bị burst request)
        model_name = getattr(config, "GEMINI_MODEL", "gemini-3.5-flash-lite") or "gemini-3.5-flash-lite"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
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

        # Tăng bộ đếm Request
        AIRecovery.total_requests += 1
        req_id = AIRecovery.total_requests
        clean_url_endpoint = url.split("?key=")[0] if "?key=" in url else url
        logger.info(f"[AI_RECOVERY] [Gemini Request #{req_id}] [{device_name}] [Model: {model_name}] Đang gửi yêu cầu phân tích kẹt tới URL: {clean_url_endpoint}...")

        max_retries = 3
        backoff_delays = [1.0, 2.0, 4.0]

        for attempt in range(max_retries + 1):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=25)

                if response.status_code == 429:
                    AIRecovery.ratelimit_429_count += 1
                    log_gemini_request(device_name, req_id, "RATELIMIT_429", 429, reason="Vượt quá hạn mức request (Rate Limit)", error_details=f"HTTP 429 Too Many Requests (Thử lại lần {attempt + 1})", model=model_name)
                    if attempt < max_retries:
                        delay = backoff_delays[attempt]
                        logger.warning(f"[AI_RECOVERY] [Request #{req_id}] Gặp HTTP 429. Retry lần {attempt + 1} sau {delay}s...")
                        time.sleep(delay)
                        continue
                    else:
                        AIRecovery.failed_requests += 1
                        logger.error(f"[AI_RECOVERY] [Request #{req_id}] Vẫn gặp lỗi 429 sau 3 lần thử lại.")
                        return None

                response.raise_for_status()
                res_json = response.json()

                AIRecovery.successful_requests += 1

                # Trích xuất text phản hồi
                resp_text = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                logger.info(f"[AI_RECOVERY] [Request #{req_id}] Phản hồi thành công từ Gemini ({model_name}): {resp_text}")

                # Parse JSON kết quả
                data = json.loads(resp_text)
                reason_str = data.get("reason", "Phân tích xong")

                log_gemini_request(device_name, req_id, "SUCCESS", 200, reason=reason_str, error_details="", raw_response=resp_text, model=model_name)

                # 4. Map tọa độ ngược lại kích thước màn hình gốc nếu có click action
                if data.get("is_stuck") and data.get("action") == "click" and data.get("target_coords"):
                    tx, ty = data["target_coords"]
                    # Xử lý tọa độ Gemini: ưu tiên chuẩn hóa 0..1000 -> scale sang kích thước thật (w, h)
                    if tx <= 1000 and ty <= 1000:
                        orig_x = int((tx / 1000.0) * w)
                        orig_y = int((ty / 1000.0) * h)
                    else:
                        orig_x = int(tx / scale)
                        orig_y = int(ty / scale)
                    data["original_coords"] = [orig_x, orig_y]
                    logger.info(f"[AI_RECOVERY] [Request #{req_id}] Phát hiện kẹt: {data['reason']}. Tọa độ AI ({tx}, {ty}) -> Tọa độ click màn hình ({w}x{h}): ({orig_x}, {orig_y})")
                else:
                    logger.info(f"[AI_RECOVERY] [Request #{req_id}] Gemini đánh giá không bị kẹt hoặc không cần hành động click.")

                return data

            except requests.exceptions.HTTPError as http_err:
                code = response.status_code if 'response' in locals() and hasattr(response, 'status_code') else 500
                if code == 429:
                    AIRecovery.ratelimit_429_count += 1
                    log_gemini_request(device_name, req_id, "RATELIMIT_429", 429, reason="Lỗi 429 quá tải", error_details=str(http_err), model=model_name)
                    if attempt < max_retries:
                        delay = backoff_delays[attempt]
                        logger.warning(f"[AI_RECOVERY] [Request #{req_id}] Gặp HTTP 429. Retry lần {attempt + 1} sau {delay}s...")
                        time.sleep(delay)
                        continue
                AIRecovery.failed_requests += 1
                log_gemini_request(device_name, req_id, "ERROR", code, reason="Lỗi HTTP API", error_details=str(http_err), model=model_name)
                logger.error(f"[AI_RECOVERY] [Request #{req_id}] Lỗi HTTP API ({model_name}): {http_err}")
                return None
            except Exception as e:
                AIRecovery.failed_requests += 1
                log_gemini_request(device_name, req_id, "ERROR", 500, reason="Lỗi xử lý Exception", error_details=str(e), model=model_name)
                logger.error(f"[AI_RECOVERY] [Request #{req_id}] Lỗi khi gọi Gemini API ({model_name}) hoặc parse kết quả: {e}")
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
