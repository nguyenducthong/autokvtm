# core/yolo_detector.py
"""
YOLO Detector - Nhận diện vật thể (chậu cây, sâu bệnh, khô nước) sử dụng mô hình YOLOv8 ONNX qua OpenCV DNN.
"""

import cv2
import numpy as np
import os
import logging
from typing import List, Tuple, Dict, Optional
import config

logger = logging.getLogger(__name__)


class YOLODetector:
    def __init__(self, model_path: str = None, conf_threshold: float = 0.3, nms_threshold: float = 0.4):
        import sys
        raw_path = model_path or getattr(config, "YOLO_MODEL_PATH", "configs/kvtm_yolo.onnx")
        if not os.path.exists(raw_path):
            from config import get_configs_dir
            candidate = os.path.join(get_configs_dir(), os.path.basename(raw_path))
            if os.path.exists(candidate):
                raw_path = candidate
        if not os.path.exists(raw_path) and hasattr(sys, "_MEIPASS"):
            mei_path = os.path.join(sys._MEIPASS, raw_path)
            if os.path.exists(mei_path):
                raw_path = mei_path
        self.model_path = raw_path
        self.conf_threshold = conf_threshold
        self.nms_threshold = nms_threshold
        
        # Tự động nạp danh sách classes từ metadata của file ONNX nếu có, tránh lệch nhãn
        self.classes = []
        self._load_classes_from_onnx()
        
        self.net = None
        self._load_model()

    def _load_classes_from_onnx(self):
        """Tải danh sách classes từ ONNX metadata để đồng bộ tuyệt đối"""
        if not os.path.exists(self.model_path):
            self._set_default_classes()
            return
        try:
            import onnx
            import ast
            onnx_model = onnx.load(self.model_path)
            for prop in onnx_model.metadata_props:
                if prop.key == "names":
                    names_dict = ast.literal_eval(prop.value)
                    max_idx = max(names_dict.keys())
                    self.classes = [names_dict.get(i, f"class_{i}") for i in range(max_idx + 1)]
                    logger.info(f"[YOLO] Nạp thành công {len(self.classes)} nhãn lớp từ metadata của file ONNX.")
                    return
        except Exception as e:
            logger.warning(f"[YOLO] Không thể đọc metadata từ ONNX, sử dụng nhãn mặc định: {e}")
        self._set_default_classes()

    def _set_default_classes(self):
        self.classes = ["o_trong", "o_vang"]
        for p in getattr(config, "PLANTS", []):
            plant_class = f"cay_{p['name']}"
            if plant_class not in self.classes:
                self.classes.append(plant_class)
        self.classes.extend(["sau_benh", "dat_kho"])

    def _load_model(self):
        """Tải mô hình ONNX bằng OpenCV DNN"""
        if not os.path.exists(self.model_path):
            logger.warning(f"[YOLO] File model không tồn tại tại: {self.model_path}. Tự động vô hiệu hóa YOLO.")
            return

        try:
            logger.info(f"[YOLO] Đang tải mô hình ONNX từ: {self.model_path}...")
            self.net = cv2.dnn.readNetFromONNX(self.model_path)
            self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            logger.info("[YOLO] Tải mô hình thành công.")
        except Exception as e:
            logger.error(f"[YOLO] Lỗi khi load mô hình ONNX: {e}")
            self.net = None

    def is_available(self) -> bool:
        return self.net is not None and getattr(config, "ENABLE_YOLO", False)

    def detect(self, screenshot: np.ndarray) -> List[Dict]:
        """
        Nhận diện các vật thể trên ảnh chụp màn hình.
        Trả về danh sách các detections:
        [
            {
                "class": "cay_chin",
                "confidence": 0.85,
                "box": [x, y, w, h],
                "center": (cx, cy)
            },
            ...
        ]
        """
        if not self.is_available():
            return []

        h_orig, w_orig = screenshot.shape[:2]
        
        # 1. Tạo blob chuẩn 640x640 cho YOLO
        blob = cv2.dnn.blobFromImage(
            screenshot, 
            scalefactor=1/255.0, 
            size=(640, 640), 
            mean=(0, 0, 0), 
            swapRB=True, 
            crop=False
        )
        
        self.net.setInput(blob)
        
        # 2. Suy luận
        try:
            outputs = self.net.forward()
        except Exception as e:
            logger.error(f"[YOLO] Lỗi suy luận model: {e}")
            return []

        # YOLOv8 output format: [1, 8, 8400] (cho 4 classes: cx, cy, w, h + 4 class scores)
        # Transpose sang [8400, 8]
        output = np.squeeze(outputs)
        if output.ndim == 2:
            output = output.T

        boxes = []
        confidences = []
        class_ids = []

        # Tính toán tỉ lệ scale
        x_factor = w_orig / 640
        y_factor = h_orig / 640

        for row in output:
            classes_scores = row[4:]
            class_id = np.argmax(classes_scores)
            confidence = classes_scores[class_id]
            
            if confidence >= self.conf_threshold:
                confidences.append(float(confidence))
                class_ids.append(int(class_id))
                
                # YOLO coordinates are [center_x, center_y, width, height]
                cx, cy, w, h = row[0], row[1], row[2], row[3]
                
                left = int((cx - w / 2) * x_factor)
                top = int((cy - h / 2) * y_factor)
                width = int(w * x_factor)
                height = int(h * y_factor)
                
                boxes.append([left, top, width, height])

        # 3. Chạy Non-Maximum Suppression để bỏ hộp trùng nhau
        indices = cv2.dnn.NMSBoxes(boxes, confidences, self.conf_threshold, self.nms_threshold)
        
        detections = []
        if len(indices) > 0:
            for i in indices.flatten():
                box = boxes[i]
                left, top, width, height = box
                cx = left + width // 2
                cy = top + height // 2
                
                class_name = self.classes[class_ids[i]] if class_ids[i] < len(self.classes) else f"class_{class_ids[i]}"
                
                # MAPPING THÔNG MINH về tên chuẩn của bot
                if class_name == "pot":
                    class_name = "chau_trong"
                elif class_name in ("core_gio_hang", "gio_hang"):
                    class_name = "cay_chin"
                
                detections.append({
                    "class": class_name,
                    "confidence": confidences[i],
                    "box": box,
                    "center": (cx, cy)
                })

        logger.info(f"[YOLO] Nhận diện được {len(detections)} vật thể.")
        return detections


def save_screenshot_for_training(screenshot: np.ndarray, save_dir: str = "data/yolo_dataset") -> Optional[str]:
    """
    Tiện ích lưu ảnh chụp màn hình để phục vụ dán nhãn huấn luyện YOLO
    """
    if screenshot is None:
        return None
    import time
    os.makedirs(save_dir, exist_ok=True)
    ts = int(time.time() * 1000)
    filename = f"kvtm_{ts}.png"
    filepath = os.path.join(save_dir, filename)
    cv2.imwrite(filepath, screenshot)
    logger.info(f"[DATASET] Đã lưu ảnh chụp để dán nhãn train: {filepath}")
    return filepath
