# run_train.py
import os
import shutil
import logging
import urllib.request
import zipfile
import requests

# Disable verbose ultralytics logs
logging.getLogger("ultralytics").setLevel(logging.WARNING)

def train_ai():
    try:
        from ultralytics import YOLO
    except ImportError:
        print("[INFO] Installing Ultralytics (YOLOv8) library...")
        os.system("pip install ultralytics")
        from ultralytics import YOLO

    # Roboflow settings
    api_key = "RWflBPrSPihBte0w5o2e"
    workspace = "thong-nguyen-duc-mwv9c"
    project_name = "farming-game-plants-pots-and-w"

    print("\n--- STEP 1: FETCHING LATEST DATASET VERSION ---")
    try:
        # 1. Gọi API lấy thông tin Project để lấy version mới nhất
        project_url = f"https://api.roboflow.com/{workspace}/{project_name}?api_key={api_key}"
        r = requests.get(project_url, timeout=10)
        r.raise_for_status()
        project_data = r.json()
        latest_version = project_data["project"]["versions"]
        print(f"[INFO] Latest version on Roboflow: Version {latest_version}")

        # 2. Gọi API lấy link tải zip của version mới nhất
        version_url = f"https://api.roboflow.com/{workspace}/{project_name}/{latest_version}/yolov8?api_key={api_key}"
        rv = requests.get(version_url, timeout=10)
        rv.raise_for_status()
        version_data = rv.json()
        
        zip_url = version_data["export"]["link"]
        print(f"[INFO] Fetching download link for Version {latest_version}...")
    except Exception as e:
        print(f"[ERROR] Failed to query Roboflow API: {e}")
        return

    zip_dest = "dataset.zip"
    extract_dir = "dataset"
    
    # 3. Tải và giải nén Dataset
    try:
        print(f"Downloading dataset zip from: {zip_url}")
        urllib.request.urlretrieve(zip_url, zip_dest)
        
        print("Extracting dataset zip...")
        # Xóa thư mục cũ nếu có để tránh lẫn dữ liệu cũ
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
            
        with zipfile.ZipFile(zip_dest, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
            
        print(f"[SUCCESS] Dataset successfully extracted to: {extract_dir}")
        
        # Dọn dẹp file zip
        if os.path.exists(zip_dest):
            os.remove(zip_dest)
    except Exception as e:
        print(f"[ERROR] Failed to download or extract dataset: {e}")
        return

    data_yaml_path = os.path.join(extract_dir, "data.yaml")
    if not os.path.exists(data_yaml_path):
        print(f"[ERROR] data.yaml not found at {data_yaml_path}!")
        return

    # 4. Huấn luyện mô hình YOLOv8-nano
    print("\n--- STEP 2: TRAINING MODEL (100 EPOCHS) ---")
    print("Training on CPU has started, this will take a few minutes...")
    model = YOLO("yolov8n.pt") # Tải mô hình nền yolov8n
    
    # Huấn luyện 100 epochs, ảnh kích thước 640, sử dụng CPU
    model.train(data=data_yaml_path, epochs=100, imgsz=640, device="cpu", workers=2)

    # 5. Xuất sang định dạng ONNX
    print("\n--- STEP 3: EXPORTING MODEL TO ONNX ---")
    onnx_path = model.export(format="onnx")
    
    # 6. Tự động sao chép file ONNX vào thư mục configs của Bot
    dest_path = os.path.join("configs", "kvtm_yolo.onnx")
    os.makedirs("configs", exist_ok=True)
    
    copied = False
    if onnx_path and os.path.exists(onnx_path):
        shutil.copy(onnx_path, dest_path)
        copied = True
    else:
        # Dự phòng tìm trong runs/detect/train/weights/best.onnx
        fallback_onnx = os.path.join("runs", "detect", "train", "weights", "best.onnx")
        if os.path.exists(fallback_onnx):
            shutil.copy(fallback_onnx, dest_path)
            copied = True
            
    if copied:
        print("\n=======================================================")
        print("[SUCCESS] TRAINING COMPLETE!")
        print(f"Your new AI model has been saved to: {dest_path}")
        print("You can now open the Tool, select 'Bật YOLO' and run the bot.")
        print("=======================================================")
    else:
        print("\n[WARNING] Training completed but best.onnx was not found to copy.")
        print("Please check the 'runs/detect/...' directory.")

if __name__ == "__main__":
    train_ai()
