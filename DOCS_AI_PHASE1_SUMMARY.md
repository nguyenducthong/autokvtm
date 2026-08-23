# 📋 TỔNG HỢP KIẾN TRÚC & KẾT QUẢ TÍCH HỢP AI (PHASE 1)
> **Dự án:** Auto KVTM (Khu Vườn Trên Mây)  
> **Phiên bản:** v1.0.9  
> **Tài liệu bàn giao:** Dành cho việc tiếp tục phát triển Phase 2

---

## 📌 1. TỔNG QUAN HỆ THỐNG AI ĐÃ TÍCH HỢP

Trong Phase 1, hệ thống đã được nâng cấp với **2 module AI bổ trợ nhau**:
1. **YOLOv8 AI (Chạy Offline trên máy):** Nhận diện thị giác siêu tốc (0.05s) cho Quầy hàng (ô trống `o_trong`, ô vàng `o_vang`) và hỗ trợ ánh xạ động tên vật phẩm kho.
2. **Google Gemini VLM (Gọi qua Cloud API):** Trợ lý đa phương thức phân tích toàn màn hình khi bot bị kẹt (AI Recovery) và đọc số lượng kho thành phẩm.

---

## 🛠️ 2. CHI TIẾT CÁC TÍNH NĂNG ĐÃ TRIỂN KHAI

### A. Hệ thống huấn luyện YOLO tự động (`run_train.py`)
* **Tích hợp Roboflow:** Kết nối tự động với Workspace `thong-nguyen-duc-mwv9c`, Project `farming-game-plants-pots-and-w`.
* **Quy trình 1-Click:** Tải Dataset mới nhất (hiện tại là Version 4) ➡️ Huấn luyện 100 Epochs bằng YOLOv8-nano trên CPU ➡️ Tối ưu ONNX Slim (`onnxslim`) ➡️ Xuất thẳng vào `configs/kvtm_yolo.onnx`.
* **Trích xuất Metadata:** Tự động đọc danh sách nhãn lớp từ Metadata của file ONNX (`yolo_detector.py`), tránh lệch index nhãn.

### B. Nhận diện Quầy hàng & Nhặt vàng siêu tốc (`core/ban_do.py`)
* **Ánh xạ nhãn động (`_find_on_screen`):**
  * Tự động cắt đường dẫn ảnh (ví dụ `assets/items/kho_tra_hoa_hong.png` ➡️ `kho_tra_hoa_hong` hoặc `tra_hoa_hong`).
  * Tự động ánh xạ `core_vang3.png` ➡️ nhãn `o_vang`.
  * Tự động ánh xạ `core_o_trong.png` ➡️ nhãn `o_trong`.
  * Nếu YOLO không có nhãn hoặc không tìm thấy, hệ thống **tự động fallback sang OpenCV Template Matching** mà không gây lỗi.
* **Cơ chế Nhặt vàng & Đặt bán 2-in-1:** Khi phát hiện ô vàng, bot double-tap `(x, y, 2, 0.3)`:
  * *Tap 1:* Nhặt vàng vào túi.
  * *Tap 2 (sau 0.3s):* Mở thẳng ô vừa trống đó để đăng bán vật phẩm mới.

### C. Module Phục Hồi Khi Kẹt (`core/ai_recovery.py`)
* Khi bot bị kẹt màn hình (sau số lần thử lại thất bại), bot chụp ảnh màn hình, gửi đến Google Gemini VLM.
* Gemini phân tích popup quảng cáo, captcha, bảng sự kiện, thông báo mất kết nối và trả về tọa độ nút X/Đóng/Thoát để bot tự click giải thoát.
* **Tối ưu hóa ảnh:** Nén JPEG 95% kích thước 900px, giảm 90% dung lượng upload (~80KB) giúp phản hồi nhanh và chính xác.

### D. Tái cấu trúc Giao diện Tab "Cấu Hình Chung" (`gui_auto_config.py`)
* **Tách biệt khỏi Profile:** Tạo riêng Tab `  Cấu Hình Chung  ` trên thanh điều hướng chính. Toàn bộ thông tin:
  * Gemini API Key
  * Bật/Tắt AI Recovery
  * Bật/Tắt YOLO Detection
  * Đường dẫn file ONNX
* **Tự động lưu (Auto-Save):** Lưu độc lập vào `configs/global_settings.json`, không bị mất hoặc ghi đè khi đổi profile bán hàng/trồng cây.
* **Nút hỗ trợ `?`:** Mở Popup hướng dẫn 6 bước tạo Gemini API Key miễn phí kèm nút bấm 1-click mở trực tiếp trang Google AI Studio.

### E. Dọn dẹp Code Gieo Trồng & Thu Hoạch
* Loại bỏ toàn bộ code thử nghiệm YOLO ở phần Sân vườn (`core/trong_cay.py`, `core/auto_farm.py`).
* Phần trồng cây và thu hoạch chạy **Offline 100% bằng OpenCV**, giữ mã nguồn gọn gàng, nhẹ máy và cực kỳ ổn định.
* Tạm tắt đọc stock kho bằng Gemini (`ENABLE_GEMINI_STOCK = False`) trong chu kỳ bán hàng để tối ưu tốc độ tối đa.

---

## 📁 3. BẢN ĐỒ CÁC FILE QUAN TRỌNG

| Đường dẫn file | Vai trò / Chức năng |
|---|---|
| `configs/kvtm_yolo.onnx` | Model mạng nơ-ron YOLOv8 ONNX (Version 4, chứa `o_trong`, `o_vang`). |
| `configs/global_settings.json` | File cấu hình chung toàn cục (API Key, YOLO toggle, Model path). |
| `core/yolo_detector.py` | Lớp Engine nạp ONNX và chạy inference bằng OpenCV DNN (hỗ trợ cả `_MEIPASS`). |
| `core/ai_recovery.py` | Module gửi ảnh kẹt màn hình lên Gemini VLM để lấy tọa độ nút đóng. |
| `core/ban_do.py` | Logic quầy hàng, nhặt vàng, chọn kho, ánh xạ template động sang YOLO. |
| `run_train.py` | Script 1-Click tải dataset Roboflow và train mô hình YOLO mới. |
| `gui_auto_config.py` | Giao diện điều khiển chính, chứa Tab Cấu Hình Chung và popup hướng dẫn. |
| `gui_auto_config.spec` | Cấu hình đóng gói PyInstaller (đã đính kèm thư mục `configs/` và thư viện `onnx`). |
| `.github/workflows/release.yml` | Workflow GitHub Actions tự động build ra file `.exe` khi đẩy Tag. |

---

## 🎯 4. ĐỊNH HƯỚNG & KẾ HOẠCH CHO PHASE 2

Khi bắt đầu Phase 2, bạn có thể dựa vào nền tảng này để mở rộng các tính năng nâng cao sau:

### 1. Đọc số lượng kho Offline bằng YOLO Digits (0 - 9)
* **Ý tưởng:** Huấn luyện YOLO nhận diện 10 chữ số từ `0` đến `9`.
* **Cách làm:**
  * Dán nhãn các con số nhỏ ở góc vật phẩm kho trên Roboflow (lớp `0`, `1`, `2`,... `9`).
  * Viết thuật toán ghép các box chữ số nằm cạnh nhau theo trục X thành số lượng hoàn chỉnh (`1` + `5` + `2` ➡️ `152`).
  * **Lợi ích:** Đọc số lượng kho thành phẩm **hoàn toàn Offline trong 0.05s**, không cần dùng Gemini API.

### 2. Mở rộng thêm Class vật phẩm kho vào YOLO
* Nhờ cơ chế `_find_on_screen` đã được viết sẵn dạng động, khi bạn dán nhãn thêm các vật phẩm kho vào Roboflow (ví dụ: `kho_tra_hoa_hong`, `kho_tinh_dau_tao`, `kho_vai_vang`):
  * Chỉ cần chạy lại `python run_train.py` để ra file `kvtm_yolo.onnx` mới.
  * Bot sẽ tự động nhận diện và click đúng sản phẩm trong kho bằng AI thay cho OpenCV.

### 3. Tối ưu hóa đa luồng (Multi-threading) cho nhiều LDPlayer
* Hiện tại `global_settings.json` đã được tách riêng. Ở Phase 2 có thể hỗ trợ cấu hình từng API Key hoặc từng Model riêng biệt cho từng giả lập nếu cần chạy quy mô lớn.

---

## 🚀 5. LỆNH NHANH CHO NHÀ PHÁT TRIỂN

* **Chạy giao diện Tool:**
  ```bash
  python gui_auto_config.py
  ```
* **Huấn luyện lại Model mới từ Roboflow:**
  ```bash
  python run_train.py
  ```
* **Build file EXE cục bộ:**
  ```bash
  pyinstaller --clean gui_auto_config.spec
  ```
* **Tạo Release tự động trên GitHub:**
  ```bash
  git add .
  git commit -m "feat: release new version"
  git tag -a v1.0.X -m "Ghi chu release"
  git push origin main
  git push origin v1.0.X
  ```
