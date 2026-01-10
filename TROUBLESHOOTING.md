# Khắc phục sự cố - Auto Khu Vườn Trên Mây

## ❌ Lỗi chụp màn hình

### Triệu chứng
- Bấm nút chụp màn hình báo lỗi
- Hiện thông báo "Không thể chụp màn hình"

### Nguyên nhân
1. LDPlayer chưa chạy hoặc đã tắt
2. ADB chưa kết nối đến thiết bị
3. Thiết bị không phản hồi
4. Không có quyền truy cập thư mục cache

### Giải pháp

#### Bước 1: Kiểm tra LDPlayer
```
✓ Mở LDPlayer
✓ Đảm bảo LDPlayer đang chạy game
✓ Không minimize LDPlayer
```

#### Bước 2: Kiểm tra ADB
```bash
# Mở Command Prompt/Terminal
adb devices
```

Kết quả mong đợi:
```
List of devices attached
emulator-5554   device
```

Nếu không có thiết bị:
```bash
# Khởi động lại ADB
adb kill-server
adb start-server
adb devices
```

#### Bước 3: Test chụp màn hình
```bash
# Chạy script test
python test_screenshot.py

# Hoặc double-click
test_screenshot.bat
```

Script sẽ kiểm tra từng bước:
1. Lấy thông tin thiết bị
2. Kết nối ADB
3. Kiểm tra kết nối
4. Tạo thư mục cache
5. Chụp màn hình

#### Bước 4: Kiểm tra thư mục cache
```bash
# Tạo thư mục cache thủ công
mkdir cache
```

Hoặc trong Python:
```python
import os
os.makedirs("cache", exist_ok=True)
```

#### Bước 5: Kiểm tra quyền ADB trong LDPlayer
1. Mở LDPlayer
2. Vào **Settings** (⚙️)
3. Chọn **Other settings**
4. Bật **ADB debugging**
5. Khởi động lại LDPlayer

### Kiểm tra chi tiết

**Test ADB trực tiếp:**
```bash
# Chụp màn hình thủ công
adb -s emulator-5554 shell screencap -p /sdcard/test.png
adb -s emulator-5554 pull /sdcard/test.png test.png
```

Nếu thành công → Vấn đề ở code Python
Nếu thất bại → Vấn đề ở ADB/LDPlayer

## ❌ Lỗi không tìm thấy thiết bị

### Giải pháp

#### Cách 1: Restart ADB
```bash
adb kill-server
adb start-server
```

#### Cách 2: Kết nối lại LDPlayer
```bash
# Tìm port của LDPlayer (thường là 5555, 5557, 5559...)
adb connect 127.0.0.1:5555
```

#### Cách 3: Sử dụng ADB của LDPlayer
LDPlayer có ADB riêng tại:
```
C:\Program Files\LDPlayer\adb.exe
```

Thêm vào PATH hoặc sử dụng trực tiếp:
```bash
"C:\Program Files\LDPlayer\adb.exe" devices
```

## ❌ Lỗi kết nối thiết bị

### Giải pháp

1. **Kiểm tra LDPlayer đang chạy**
   - Mở LDPlayer
   - Đợi boot xong hoàn toàn

2. **Kiểm tra số port**
   ```bash
   adb devices
   ```
   Lấy serial (vd: emulator-5554)

3. **Cập nhật serial trong code**
   - Chọn lại thiết bị trong GUI
   - Hoặc xóa file `selected_device.json`

## ❌ Lỗi "Không đọc được ảnh"

### Nguyên nhân
- File ảnh bị corrupt
- Đường dẫn không hợp lệ
- Không có quyền đọc file

### Giải pháp

1. **Kiểm tra file tồn tại:**
   ```bash
   dir cache\screenshot_tool.png
   ```

2. **Kiểm tra OpenCV:**
   ```python
   import cv2
   img = cv2.imread("cache/screenshot_tool.png")
   print(img.shape if img is not None else "NULL")
   ```

3. **Thử đường dẫn tuyệt đối:**
   ```python
   import os
   path = os.path.abspath("cache/screenshot_tool.png")
   img = cv2.imread(path)
   ```

## ❌ Lỗi PIL/Pillow

### Triệu chứng
```
ImportError: No module named 'PIL'
```

### Giải pháp
```bash
pip install Pillow
```

## ❌ Lỗi ppadb

### Triệu chứng
```
ImportError: No module named 'ppadb'
```

### Giải pháp
```bash
pip install pure-python-adb
```

## 🔧 Công cụ debug

### 1. Test toàn diện
```bash
python test_screenshot.py
```

### 2. Xem log chi tiết
Kiểm tra console output khi chạy GUI

### 3. Chụp màn hình thủ công
```bash
adb shell screencap -p /sdcard/test.png
adb pull /sdcard/test.png
```

## 📞 Vẫn gặp lỗi?

Nếu vẫn gặp lỗi, thu thập thông tin sau:

1. **Thông tin hệ thống:**
   - Windows version
   - Python version: `python --version`
   - LDPlayer version

2. **ADB info:**
   ```bash
   adb version
   adb devices -l
   ```

3. **Log lỗi:**
   - Copy full error message
   - Screenshot lỗi

4. **File log:**
   - Console output
   - Traceback (nếu có)

## ✅ Checklist khắc phục nhanh

- [ ] LDPlayer đang chạy
- [ ] ADB server đã start: `adb start-server`
- [ ] Thiết bị hiện trong `adb devices`
- [ ] Thư mục `cache` đã tồn tại
- [ ] Có quyền đọc/ghi thư mục
- [ ] OpenCV đã cài: `pip list | findstr opencv`
- [ ] Pillow đã cài: `pip list | findstr Pillow`
- [ ] ppadb đã cài: `pip list | findstr ppadb`

## 🎯 Test nhanh

Mở Python và chạy:
```python
from core.adb import ADBController
from gui_select_device import get_selected_device

# Test kết nối
serial = get_selected_device()
print(f"Serial: {serial}")

adb = ADBController(serial=serial)
print(f"Connected: {adb.is_connected()}")

# Test chụp
import os
os.makedirs("cache", exist_ok=True)
screenshot = adb.screenshot_full("cache/test.png")
print(f"Screenshot: {screenshot.shape}")
```

Nếu chạy thành công → Vấn đề đã fix!
