# tools/test_yolo_detection.py
"""
Script test nhanh tính năng nhận diện YOLOv8 trên ảnh chụp màn hình.
"""

import sys
import os
import cv2

# Thêm thư mục gốc vào path để import core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.yolo_detector import YOLODetector
import config

def main():
    if len(sys.argv) < 2:
        print("Cách dùng: python tools/test_yolo_detection.py <duong_dan_anh_screenshot>")
        print("Ví dụ: python tools/test_yolo_detection.py debug/found_table.png")
        sys.exit(1)

    img_path = sys.argv[1]
    if not os.path.exists(img_path):
        print(f"Lỗi: Không tìm thấy ảnh tại {img_path}")
        sys.exit(1)

    # Đọc ảnh đầu vào
    img = cv2.imread(img_path)
    if img is None:
        print(f"Lỗi: Không thể đọc ảnh {img_path}")
        sys.exit(1)

    # Cấu hình cứng để phục vụ chạy test
    config.ENABLE_YOLO = True
    config.YOLO_MODEL_PATH = "configs/kvtm_yolo.onnx"

    print("--- KHỞI TẠO YOLO DETECTOR ---")
    detector = YOLODetector()
    
    if not os.path.exists(config.YOLO_MODEL_PATH):
        print(f"\n⚠️ CẢNH BÁO: Chưa tìm thấy file mô hình tại '{config.YOLO_MODEL_PATH}'")
        print("Vui lòng đặt file model YOLOv8 (định dạng ONNX) của bạn vào thư mục configs/ trước khi test.")
        print("Lớp detector hiện tại sẽ tự động bị tắt (is_available() = False).")
        sys.exit(0)

    print(f"Model Path: {detector.model_path}")
    print(f"Trạng thái hoạt động (is_available): {detector.is_available()}")

    print("\n--- ĐANG CHẠY SUY LUẬN (INFERENCE) ---")
    detections = detector.detect(img)

    # Vẽ kết quả lên ảnh
    output_img = img.copy()
    print(f"\nTìm thấy {len(detections)} vật thể:")
    for i, det in enumerate(detections, 1):
        label = det["class"]
        conf = det["confidence"]
        box = det["box"]
        cx, cy = det["center"]
        
        print(f"[{i}] {label} (Độ tin cậy: {conf:.2f}) tại Tâm: ({cx}, {cy}), Khung: {box}")
        
        # Vẽ bounding box
        x, y, w, h = box
        cv2.rectangle(output_img, (x, y), (x + w, y + h), (0, 255, 0), 2)
        # Vẽ tâm vật thể
        cv2.circle(output_img, (cx, cy), 5, (0, 0, 255), -1)
        # Ghi tên class và conf
        text = f"{label} {conf:.2f}"
        cv2.putText(output_img, text, (x, max(y - 8, 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

    # Lưu ảnh kết quả
    os.makedirs("debug", exist_ok=True)
    out_path = "debug/yolo_test_result.png"
    cv2.imwrite(out_path, output_img)
    print(f"\n✓ Hoàn tất! Ảnh kết quả trực quan đã được lưu tại: {out_path}")

if __name__ == "__main__":
    main()
