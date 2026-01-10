# Hướng dẫn sử dụng GUI - Auto Khu Vườn Trên Mây

## Tính năng mới

Đã có GUI (giao diện đồ họa) hoàn chỉnh với menu và các chức năng!

## Cách chạy

### 1. Chạy GUI (Khuyên dùng)

**Cách 1: Double-click file batch**
```
run_gui.bat
```

**Cách 2: Dòng lệnh**
```bash
python main.py
```

**Cách 3: Chạy trực tiếp GUI**
```bash
python gui_main.py
```

### 2. Chạy Console (Dạng text)

**Cách 1: Double-click file batch**
```
run_console.bat
```

**Cách 2: Dòng lệnh**
```bash
python main.py --console
```

### 2. Chọn thiết bị lần đầu

Khi chạy lần đầu, chương trình sẽ tự động:
- Quét tất cả LDPlayer đang chạy
- Hiển thị GUI để bạn chọn
- Lưu lựa chọn của bạn vào file `selected_device.json`

### 3. Các lần chạy sau

Chương trình sẽ tự động sử dụng thiết bị đã chọn trước đó.

### 4. Đổi thiết bị

Từ menu chính, chọn:
```
[2] Chọn thiết bị LDPlayer
```

## Menu chính

```
==================================================
   AUTO KHU VƯỜN TRÊN MÂY – MENU CHÍNH
==================================================
  [1] Đặt vật phẩm vào kho sự kiện (KSK)
  [2] Chọn thiết bị LDPlayer
  [3] Xem thiết bị hiện tại
  [0] Thoát
--------------------------------------------------
```

## Giao diện GUI

GUI hiển thị:
- Danh sách tất cả LDPlayer đang chạy
- Tên và serial của từng thiết bị
- Nút "Làm mới" để quét lại
- Nút "Chọn thiết bị" để xác nhận

## Yêu cầu

- Python 3.7+
- Tkinter (đã có sẵn với Python)
- ADB đã được cài đặt và trong PATH
- LDPlayer đang chạy

## Xử lý lỗi

### Không tìm thấy thiết bị?

1. Kiểm tra LDPlayer đã chạy chưa
2. Chạy lệnh để kiểm tra:
   ```bash
   adb devices
   ```
3. Đảm bảo ADB đã được bật trong LDPlayer

### Không tìm thấy ADB?

Cài đặt Android SDK Platform Tools hoặc sử dụng ADB đi kèm LDPlayer:
```
C:\Program Files\LDPlayer\adb.exe
```

## File cấu hình

File `selected_device.json` lưu thiết bị đã chọn:
```json
{
  "serial": "emulator-5554",
  "name": "LDPlayer"
}
```

Bạn có thể xóa file này để chọn lại từ đầu.

## Demo

### GUI chọn thiết bị
```
╔════════════════════════════════════╗
║    🎮 CHỌN LDPLAYER               ║
╠════════════════════════════════════╣
║ Chọn thiết bị LDPlayer:           ║
║                                    ║
║ [1] LDPlayer (emulator-5554)      ║
║ [2] LDPlayer (emulator-5556)      ║
║ [3] LDPlayer (emulator-5558)      ║
║                                    ║
║ [🔄 Làm mới]  [✓ Chọn thiết bị]   ║
╚════════════════════════════════════╝
```

## Lưu ý

- GUI tự động chọn lại thiết bị đã lưu
- Serial thiết bị có dạng: `emulator-XXXX`
- Mỗi LDPlayer có một serial riêng
- Có thể chạy nhiều LDPlayer và chọn từng cái

## Code tham khảo

Nếu muốn sử dụng trong code khác:

```python
from gui_select_device import get_selected_device, DeviceSelector

# Cách 1: Lấy serial tự động (load từ file hoặc mở GUI)
serial = get_selected_device()

# Cách 2: Mở GUI trực tiếp
selector = DeviceSelector()
device = selector.run()
if device:
    print(f"Đã chọn: {device['serial']}")
```

## Troubleshooting

### GUI không hiện?

Kiểm tra Tkinter:
```bash
python -c "import tkinter; print('OK')"
```

### Lỗi permission?

Chạy cmd/terminal với quyền Administrator.

### LDPlayer không xuất hiện?

1. Mở LDPlayer
2. Vào Settings > Others > Enable ADB
3. Restart LDPlayer
4. Chạy: `adb kill-server && adb start-server`
