# HƯỚNG DẪN SỬ DỤNG AUTO KHU VƯỜN TRÊN MÂY (AUTO KVTM)

Tài liệu này hướng dẫn chi tiết cách cài đặt, cấu hình và sử dụng công cụ **Auto Khu Vườn Trên Mây (Auto KVTM)** chạy trên giả lập Android (LDPlayer / BlueStacks / Nox) hoặc thiết bị Android thật thông qua kết nối ADB.

---

## 📋 MỤC LỤC
1. [Yêu cầu hệ thống & Chuẩn bị](#1-yêu-cầu-hệ-thống--chuẩn-bị)
2. [Cài đặt môi trường Python & Thư viện](#2-cài-đặt-môi-trường-python--thư-viện)
3. [Cấu hình Giả lập LDPlayer](#3-cấu-hình-giả-lập-ldplayer)
4. [Hướng dẫn sử dụng Giao diện Auto (`gui_auto_config.py`)](#4-hướng-dẫn-sử-dụng-giao-diện-auto-gui_auto_configpy)
   - [Tab 1: Chạy Auto](#tab-1-chạy-auto)
   - [Tab 2: Quản lý & Chỉnh sửa Cấu hình](#tab-2-quản-lý--chỉnh-sửa-cấu-hình)
5. [Chi tiết các tính năng Auto](#5-chi-tiết-các-tính-năng-auto)
6. [Quản lý File Cấu hình (JSON)](#6-quản-lý-file-cấu-hình-json)
7. [Cập nhật phiên bản & Đóng gói release](#7-cập-nhật-phiên-bản--đóng-gói-release)
8. [Xử lý sự cố thường gặp (Troubleshooting)](#8-xử-lý-sự-cố-thường-gặp-troubleshooting)

---

## 1. Yêu cầu hệ thống & Chuẩn bị
- **Hệ điều hành**: Windows 10 / 11 (64-bit).
- **Giả lập Android**: LDPlayer 9 (khuyên dùng) hoặc BlueStacks / NoxPlayer.
- **Game**: Game **Khu Vườn Trên Mây** (ZingPlay - Package: `vn.kvtm.js`).
- **ADB (Android Debug Bridge)**: Đã bật tính năng Debugging trong giả lập / thiết bị.

> [!NOTE]
> **Dành cho Người Dùng Cuối (Dùng file `.exe`)**: 
> Bạn **KHÔNG CẦN** cài đặt Python hay bất kỳ thư viện nào! File `.exe` đã được đóng gói sẵn toàn bộ môi trường cần thiết. Bạn chỉ cần giải nén thư mục release (bao gồm file `gui_auto_config.exe` cùng các thư mục `assets/`, `configs/`) và nhấp đúp vào file `.exe` để chạy ngay.

---

## 2. Cài đặt môi trường Python (Chỉ dành cho Dev / Chạy từ mã nguồn `.py`)

*Nếu bạn chạy trực tiếp file `.exe`, bạn có thể bỏ qua bước này.*

### Bước 1: Kiểm tra Python
Mở **Command Prompt** (CMD) hoặc **PowerShell** và kiểm tra phiên bản Python:
```bash
py --version
```

### Bước 2: Nâng cấp `pip` và cài đặt các thư viện phụ thuộc
Chạy các lệnh sau để cài đặt đầy đủ các gói cần thiết:
```bash
# Nâng cấp pip
py -m ensurepip --upgrade
py -m pip install --upgrade pip

# Thư viện xử lý ảnh và OCR
py -m pip install opencv-python numpy pillow pytesseract

# Thư viện ADB và tự động hóa
py -m pip install pure-python-adb adbutils

# Thư viện điều khiển và tiện ích
py -m pip install requests pyautogui keyboard mouse
```

---

## 3. Cấu hình Giả lập LDPlayer

Để Auto nhận diện chính xác hình ảnh và tọa độ thao tác, hãy cài đặt giả lập LDPlayer theo chuẩn sau:

1. **Độ phân giải màn hình**:
   - Cài đặt độ phân giải tùy chỉnh: **800 x 800 (DPI 240)**.
2. **Cấu hình ADB**:
   - Vào **Cài đặt LDPlayer** -> **Cài đặt khác** -> **Bật ADB Debugging** (Chọn *Open local connection* / *Mở kết nối cục bộ*).
3. **Cài đặt Game**:
   - Đảm bảo đã đăng nhập và mở game KVTM ổn định trước khi bắt đầu Auto.

---

## 4. Hướng dẫn sử dụng Giao diện Auto (`gui_auto_config.exe` hoặc `gui_auto_config.py`)

- **Cách 1 (Dùng file `.exe`)**: Nhấp đúp trực tiếp vào file `gui_auto_config.exe`.
- **Cách 2 (Dùng file `.py`)**: Mở CMD tại thư mục project và gõ `py gui_auto_config.py`.

Giao diện chương trình gồm **2 Tab chính**:

![Giao diện chính](assets/items/num/1.png) *(Tùy chọn minh họa)*

---

### Tab 1: Chạy Auto
Tab này dùng để điều khiển và giám sát quá trình chạy tự động trên một hoặc nhiều thiết bị.

#### Các bước vận hành:
1. **Quét thiết bị ADB**:
   - Nhấn nút **"Quét thiết bị"** để Auto tự động tìm các cửa sổ LDPlayer hoặc thiết bị Android đang kết nối.
2. **Chọn Cấu hình**:
   - Tại danh sách thiết bị tương ứng, chọn cấu hình Auto mong muốn từ menu thả xuống (ví dụ: `mac_dinh.json`, `ban_dua.json`, `tcsk.json`).
3. **Bắt đầu Chạy**:
   - Nhấn nút **"Chạy"** tại dòng thiết bị muốn làm việc, hoặc nhấn **"Chạy tất cả"** để khởi chạy đồng loạt.
   - Để ngưng Auto, nhấn nút **"Dừng"**.
4. **Theo dõi Nhật ký & Thống kê**:
   - Ô **Khung Log** phía dưới hiển thị chi tiết từng hành động (Thu hoạch, Gieo hạt, Sản xuất, Bán đồ, Lỗi nếu có).
   - Bảng **Thống kê hàng ngày** hỗ trợ theo dõi số lượng nông sản / sản phẩm đã thu hoạch hoặc giao dịch trong ngày.

---

### Tab 2: Quản lý & Chỉnh sửa Cấu hình (Config Editor)
Tab này cho phép bạn xem, tạo mới, sao chép, quản lý danh sách nhiệm vụ (Task List) và chỉnh sửa mọi tham số hoạt động của các kịch bản Auto lưu dưới dạng file `.json`.

![Tab Cấu hình](assets/items/num/2.png) *(Tùy chọn minh họa)*

---

#### 📌 1. Thanh Quản lý Profile Cấu hình (Profile Bar)
Nằm ở đầu tab, giúp quản lý các tập tin kịch bản kịch bản:
- **Danh sách Profile (`Combobox`)**: Hiển thị tất cả các file cấu hình `.json` hiện có trong thư mục `configs/` (ví dụ: `mac_dinh.json`, `ban_dua.json`, `tcsk.json`).
- **Nút "Tạo mới"**: Tạo một kịch bản mới với các tham số trống/mặc định.
- **Nút "Sao chép" (Duplicate)**: Nhân bản cấu hình đang chọn thành một file mới để tùy biến mà không làm hỏng file gốc.
- **Nút "Xóa"**: Xóa file cấu hình hiện tại khỏi hệ thống.
- **Nút "Lưu cấu hình"**: Lưu toàn bộ các chỉnh sửa trên giao diện vào file `.json`.

---

#### ⚙️ 2. Cài đặt Tổng quan (Global Settings Panel)
Nơi thiết lập quy tắc hoạt động chung cho kịch bản:

- **Chế độ vòng lặp tổng (`loop_tong_mode`)**:
  - `Vô hạn (forever)`: Auto sẽ lặp lại toàn bộ kịch bản liên tục cho đến khi người dùng bấm **Dừng**.
  - `Số lượt quy định (count)`: Chạy đủ số vòng lặp quy định tại ô `loop_tong` rồi tự động ngắt.
- **Số lượt lặp tổng (`loop_tong`)**: Số chu kỳ lặp lại của toàn bộ kịch bản (chỉ áp dụng khi chọn chế độ `count`).
- **Số lượt lặp sub-task (`loop`)**: Số lần lặp lại thao tác nhỏ trong một vòng quét nhiệm vụ.
- **Ngưỡng nhận diện ảnh (`threshold`)**:
  - Tỷ lệ chính xác khi so khớp hình ảnh mẫu với màn hình game (Giá trị từ `0.10` đến `1.00`, Mặc định: `0.85`).
  - *Mẹo*: Nếu Auto không nhận dạng được hình ảnh -> Hạ threshold xuống `0.80` - `0.82`. Nếu Auto bấm nhầm -> Nâng threshold lên `0.88` - `0.90`.
- **Các công tắc Bật/Tắt tính năng (`Checkbuttons`)**:
  - `bat_trong_cay`: Cho phép tự động gieo hạt theo từng tầng.
  - `bat_thu_hoach`: Cho phép tự động quét và thu hoạch nông sản đã chín.
  - `bat_may`: Cho phép tự động đưa nguyên liệu vào máy chế biến / máy sản xuất cám.
  - `bat_ban_vp`: Cho phép bán sản phẩm trên quầy hàng / đơn hàng.
  - `bat_ban_kho`: Cho phép mở kho và xả bớt vật phẩm tích trữ.
  - `bat_giao_cu`: Cho phép nhận và hoàn thành đơn hàng Cú vận chuyển.
  - `bat_giao_tom`: Cho phép nhận và hoàn thành đơn hàng Tôm.
  - `bat_mo_ruong`: Cho phép tự động kiểm tra và mở rương quà định kỳ.

---

#### 📋 3. Bảng Danh sách Nhiệm vụ (Task List Treeview)
Hiển thị danh sách các bước nhiệm vụ được Auto thực hiện theo thứ tự từ trên xuống dưới:
- **Thông tin cột**:
  - `STT`: Thứ tự ưu tiên thực thi nhiệm vụ.
  - `Loại Task`: Loại hành động (`TC` - Trồng cây, `MAY` - Sản xuất, `BAN` - Bán hàng, `GIAO_CU`, `GIAO_TOM`).
  - `Tầng (Row)`: Số tầng chậu mây áp dụng (dành cho task Trồng cây).
  - `Danh sách ô`: Các chậu cây cụ thể được gieo (ví dụ: `1.1, 1.2, 1.3...`).
  - `Cây / Sản phẩm`: Loại nông sản (Hồng, Táo, Bông, Tuyết...) hoặc sản phẩm chế biến.
  - `Vùng quét (Region)`: Tọa độ giới hạn quét ảnh `[X, Y, W, H]`.
  - `Threshold`: Ngưỡng nhận diện riêng của task.

- **Thao tác quản lý Task**:
  - **Nút "Thêm Task"**: Mở form để nhập thông tin task mới vào cuối danh sách.
  - **Nút "Sửa Task"**: Chọn 1 dòng trong bảng và nhấn nút này để nạp thông tin lên form chỉnh sửa.
  - **Nút "Xóa Task"**: Xóa nhiệm vụ đang chọn khỏi danh sách.
  - **Nút "Lên" / "Xuống"**: Thay đổi thứ tự ưu tiên thực thi của nhiệm vụ được chọn.

---

#### 📝 4. Form Cấu hình Chi tiết Nhiệm vụ (Task Form Panel)

##### A. Khi chọn Loại Task: `TC` (Trồng Cây)
- **Số tầng (`row`)**: Chọn từ tầng `1` đến tầng `6` (hoặc tầng tùy chỉnh).
- **Danh sách ô chậu (`indexs`)**: Chọn các ô chậu mây cụ thể (Ví dụ: Tầng 1 gồm `1.1`, `1.2`, `1.3`, `1.4`, `1.5`, `1.6`).
- **Loại cây gieo (`path_item`)**: Chọn loại hạt giống cần gieo (Táo, Hồng, Bông, Tuyết, Dừa, v.v.). Danh sách hạt giống được tải tự động từ thư mục `assets/items/`.
- **Cây mặc định (`path_item_default`)**: Loại hạt gieo dự phòng trường hợp loại cây chính hết hạt trong kho.

##### B. Cấu hình Vùng Quét (Region Settings)
Giúp khu vực quét ảnh chính xác hơn, tăng tốc độ nhận diện và tránh bấm nhầm ra ngoài:
- **Preset vùng có sẵn (`Preset Dropdown`)**:
  - `Toàn màn`: Quét trên toàn bộ màn hình giả lập.
  - `Cây và gieo`: Vùng giới hạn chứa chậu cây và bảng chọn hạt giống.
  - `Máy sản xuất`: Vùng giới hạn chứa các nhà máy chế biến.
  - `Mây`: Vùng quét mây.
  - `Quầy hàng`: Vùng chứa quầy bán hàng.
  - `Tôm`: Vùng nhận đơn hàng Tôm.
- **Chọn "Vùng từ crop hiện tại"**: Tự động lấy tọa độ `[X, Y, W, H]` vừa kéo chọn từ **Tab 3 (Chụp & Cắt ảnh)**.
- **Tọa độ thủ công**: Nhập trực tiếp các thông số `X`, `Y`, `Chiều rộng (W)`, `Chiều cao (H)`.

---

#### 🛒 5. Cài đặt Bán Hàng Kho & Đơn Hàng (Warehouse & Sell Options)
Cấu hình danh mục sản phẩm sự kiện / vật phẩm tích trữ cần xả kho:
- **Danh sách vật phẩm kho chọn bán**:
  - `KSK_KEM` (Kem)
  - `KSK_KINH` (Kính)
  - `KSK_DUA` (Dừa)
  - `KSK_BO` (Bò)
  - `KSK_CUU` (Cừu)
  - `KSK_GA` (Gà)
  - `KSK_HEO` (Heo)
- **Vùng quét bán đồ kho (`bd_region`)**: Cấu hình vùng hiển thị của giao diện bán kho để Auto click chính xác nút Bán.

---

---

## 5. Chi tiết các tính năng Auto

### 🌾 1. Trồng cây & Thu hoạch
- Auto tự động quét vùng chậu mây theo tầng (`row 1` đến `row 6`).
- Thu hoạch cây chín trước, sau đó gieo loại hạt được cấu hình (Táo, Hồng, Bông, Tuyết, v.v.).
- Hỗ trợ ưu tiên trồng nông sản sự kiện hoặc nông sản nhiệm vụ.

### 🏭 2. Máy Sản xuất & Sản xuất Cám
- Tự động kéo nguyên liệu vào máy chế biến khi máy rảnh.
- Sản xuất các loại thức ăn gia súc / cám chăn nuôi cho Heo, Bò, Cừu, Gà.

### 🏪 3. Bán đồ kho & Sự kiện (Event)
- Tự động mở kho thành phẩm, chọn vật phẩm cần bán (Kem, Kính, Dừa, Bò, Cừu, Gà, Heo, v.v.).
- Xử lý các đợt bán hàng theo giá niêm yết hoặc xả kho khi kho đầy.

### 📦 4. Giao Cú & Giao Tôm
- Tự động kiểm tra danh sách đơn hàng Cú / Tôm.
- Nếu đủ nguyên liệu trong kho -> Nhấn hoàn thành đơn hàng để nhận kinh nghiệm và tiền vàng.

---

## 6. Quản lý File Cấu hình (JSON)

Tất cả các kịch bản lưu trong thư mục `configs/` dưới dạng file JSON. Có thể chỉnh sửa trực tiếp qua file nếu cần:

Ví dụ cấu trúc mẫu file `configs/mac_dinh.json`:
```json
{
  "settings": {
    "loop_tong_mode": "forever",
    "loop_tong": 1,
    "loop": 3,
    "threshold": 0.85,
    "bat_trong_cay": true,
    "bat_may": true,
    "bat_ban_vp": true,
    "bat_thu_hoach": true,
    "bat_mo_ruong": true,
    "bat_giao_cu": false
  },
  "tasks": [
    {
      "id": 1,
      "row": 1,
      "type": "TC",
      "indexs": ["1.1", "1.2", "1.3", "1.4", "1.5", "1.6"],
      "path_row": "assets/items/num/1.png",
      "path_item": "assets/items/cay_tao.png",
      "threshold": 0.85
    }
  ]
}
```

---

## 7. Cập nhật phiên bản & Đóng gói release

### Kiểm tra bản cập nhật
Ứng dụng tự động kiểm tra phiên bản mới nhất từ **GitHub Releases**. Khi có phiên bản mới, ứng dụng sẽ hiển thị thông báo hỗ trợ tải về.

### Đóng gói Release mới (Dành cho Developer)
Khi muốn phát hành phiên bản mới:
1. Chạy script release:
   ```bash
   py release.py
   ```
2. Nhập số phiên bản mới (ví dụ: `1.0.6`).
3. Script sẽ tự động cập nhật `CURRENT_VERSION` trong [config.py](file:///d:/ldplay/autokvtm/config.py), tạo git tag và push lên GitHub. GitHub Actions sẽ tự động build và upload file zip release.

---

## 8. Xử lý sự cố thường gặp (Troubleshooting)

| Sự cố | Nguyên nhân | Cách khắc phục |
| :--- | :--- | :--- |
| **Không tìm thấy thiết bị ADB** | Chưa bật ADB Debugging hoặc Server ADB bị đơ. | Bật ADB trong LDPlayer; Bấm nút **"Quét thiết bị"** lại hoặc gõ `adb kill-server` rồi `adb start-server` trong CMD. |
| **Auto click trượt / Không nhận diện được cây** | Độ phân giải LDPlayer không chuẩn hoặc màn hình bị che khuất. | Chỉnh độ phân giải LDPlayer về chuẩn **800x800 (DPI 240)**. Đảm bảo giao diện game không bị rương quà che. |
| **Lỗi thiếu thư viện Python** | Chưa cài đủ gói dependency. | Chạy lệnh `py -m pip install -r install.txt` hoặc cài từng gói theo [Mục 2](#2-cài-đặt-môi-trường-python--thư-viện). |
| **Game văng ra ngoài màn hình chính** | App KVTM bị crash. | Bật tùy chọn `AUTO_OPEN_GAME_AFTER_LD_START = True` trong `config.py` để Auto tự khởi động lại game. |

---
*Tài liệu hướng dẫn sử dụng Auto Khu Vườn Trên Mây - Phiên bản 1.0+*
