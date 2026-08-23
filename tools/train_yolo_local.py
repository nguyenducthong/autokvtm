# tools/train_yolo_local.py
"""
Script hướng dẫn và khởi chạy huấn luyện mô hình YOLOv8 trên máy cá nhân hoặc Google Colab.
"""

import sys
import os

def main():
    print("====================================================================")
    # Hướng dẫn quy trình chuẩn bị dữ liệu
    print(" HƯỚNG DẪN HUẤN LUYỆN AI YOLOv8 NHẬN DIỆN VƯỜN KVTM")
    print("====================================================================")
    print("\n1. CHUẨN BỊ DATASET:")
    print("   - Chụp và gom ảnh trong thư mục 'data/yolo_dataset/' (Dùng nút 'Lưu Dataset YOLO' trên giao diện).")
    print("   - Đăng nhập vào trang web Roboflow (https://roboflow.com/) - Tạo tài khoản miễn phí.")
    print("   - Tạo một Project mới dạng 'Object Detection' (Phát hiện vật thể).")
    print("   - Upload ảnh lên, tiến hành dán nhãn các đối tượng:")
    print("     + chau_trong (chậu trống)")
    print("     + cay_chin (hoặc cay_hong, cay_tao, cay_bong, cay_tuyet nếu muốn phân loại cây)")
    print("     + sau_benh (sâu bọ)")
    print("     + dat_kho (đất khô)")
    print("   - Sau khi dán nhãn xong, bấm 'Generate New Version' và chọn Export dataset dạng 'YOLOv8'.")
    print("   - Roboflow sẽ cung cấp một đoạn code tải dữ liệu (chứa API key hoặc link tải zip).")
    
    print("\n2. CÀI ĐẶT THƯ VIỆN HUẤN LUYỆN:")
    print("   Chạy lệnh sau trong Terminal máy của bạn (yêu cầu máy có Python):")
    print("   pip install ultralytics requests")

    print("\n3. CODE HUẤN LUYỆN (PYTHON):")
    print("   Tạo một file python (ví dụ: run_train.py) với nội dung sau và chạy:")
    print("   -------------------------------------------------")
    print("   from ultralytics import YOLO")
    print("   ")
    print("   # Tải mô hình YOLOv8-nano pretrained siêu nhẹ")
    print("   model = YOLO('yolov8n.pt')")
    print("   ")
    print("   # Bắt đầu huấn luyện với tệp data.yaml tải về từ Roboflow")
    print("   # epochs=100 là số lượt học (có thể tăng lên 150-200 để chính xác hơn)")
    print("   model.train(data='data.yaml', epochs=100, imgsz=640, device='cpu')")
    print("   ")
    print("   # Xuất mô hình đã train sang định dạng ONNX")
    print("   path_onnx = model.export(format='onnx')")
    print("   print(f'✓ Đã xuất file ONNX thành công: {path_onnx}')")
    print("   -------------------------------------------------")
    
    print("\n4. SAU KHI TRAIN XONG:")
    print("   - Tìm file 'best.onnx' xuất ra (thường nằm ở: runs/detect/train/weights/best.onnx).")
    print("   - Copy file đó bỏ vào thư mục dự án này: 'configs/kvtm_yolo.onnx'.")
    print("   - Mở Giao diện Tool, chọn 'Bật YOLO Detection' và tận hưởng thành quả!")
    print("====================================================================")

if __name__ == "__main__":
    main()
