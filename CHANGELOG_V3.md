# Changelog - Phiên bản V3

## 🎉 Tính năng mới

### 1. Click để chọn vị trí (V3.0)
- ✅ Click trực tiếp vào icon giỏ thu hoạch
- ✅ Click vào icon hạt giống muốn trồng
- ✅ Marker đỏ hiển thị vị trí đã chọn
- ✅ Chụp lại màn hình nếu cần
- ✅ Tọa độ tự động điền vào ô nhập

### 2. ADB Helper - Tự động tìm ADB (V3.1)
- ✅ Tự động tìm ADB của LDPlayer
- ✅ Không cần thêm ADB vào PATH
- ✅ Hỗ trợ nhiều phiên bản LDPlayer (4, 9)
- ✅ Tự động phát hiện thiết bị

### 3. Hiển thị tên LDPlayer (V3.1)
- ✅ Hiển thị tên thật của LDPlayer thay vì "emulator-5564"
- ✅ Dùng ldconsole để lấy tên
- ✅ Map chính xác theo thứ tự
- ✅ Dễ phân biệt nhiều LDPlayer

**Ví dụ:**
```
Trước: emulator-5564
Sau:   LDPlayer-Th
```

### 4. Quản lý thiết bị linh hoạt (V3.2) - MỚI!
- ✅ Xóa DEVICE_SERIAL mặc định
- ✅ Hiển thị danh sách thiết bị khi khởi động
- ✅ Nút "🔄 Chọn lại" để đổi thiết bị
- ✅ Tự động hiển thị GUI chọn thiết bị nếu lỗi kết nối
- ✅ Hiển thị tên LDPlayer thân thiện

## 📋 Thay đổi chi tiết

### Files đã cập nhật:

1. **[core/adb_helper.py](core/adb_helper.py)**
   - Thêm `get_ldplayer_names()` - Lấy tên LDPlayer từ ldconsole
   - Thêm `get_device_name()` - Map serial với tên
   - Cache danh sách tên để tăng tốc

2. **[gui_select_device.py](gui_select_device.py)**
   - Tích hợp ADB Helper
   - Hiển thị tên LDPlayer thay vì device model
   - Thêm `force_select` parameter
   - Thêm `clear_selected_device()` function

3. **[gui_auto_farm.py](gui_auto_farm.py)**
   - Thêm nút "🔄 Chọn lại" thiết bị
   - Cập nhật `load_device()` nhận tên thiết bị
   - Thêm `select_device()` để chọn lại
   - Hiển thị tên LDPlayer trong device bar
   - Tự động hiển thị GUI chọn thiết bị nếu lỗi

4. **[config.py](config.py)**
   - Xóa `DEVICE_SERIAL = "emulator-5554"` mặc định
   - Đổi thành `DEVICE_SERIAL = None`
   - Comment giải thích rõ ràng

5. **Files hướng dẫn mới:**
   - [HUONG_DAN_CLICK_CHON_VI_TRI.md](HUONG_DAN_CLICK_CHON_VI_TRI.md)
   - [KHAC_PHUC_LOI_ADB.md](KHAC_PHUC_LOI_ADB.md)
   - [CHANGELOG_V3.md](CHANGELOG_V3.md) - file này

## 🚀 Cách sử dụng mới

### Lần đầu khởi động:
```bash
python gui_auto_farm.py
```

**Kết quả:**
1. Tự động hiển thị danh sách LDPlayer
2. Chọn thiết bị muốn dùng
3. Tên LDPlayer hiển thị rõ ràng: "LDPlayer-Th", "LDPlayer", v.v.
4. Bắt đầu sử dụng!

### Đổi thiết bị:
- Click nút **"🔄 Chọn lại"** trên thanh thiết bị
- Chọn LDPlayer khác từ danh sách
- Kết nối lại tự động

### Click chọn vị trí:
1. Click **"📍 Click chọn"** bên cạnh ô giỏ/hạt
2. Click vào icon trên màn hình game
3. Click **"✓ Xác nhận"**
4. Tọa độ tự động điền!

## 🎯 Ưu điểm

| Tính năng | Trước (V2) | Sau (V3.2) |
|-----------|-----------|------------|
| **Chọn thiết bị** | Hardcode trong config | Danh sách GUI |
| **Hiển thị tên** | emulator-5564 | LDPlayer-Th |
| **Đổi thiết bị** | Sửa code/config | Nút "Chọn lại" |
| **Lấy tọa độ** | Screenshot Tool riêng | Click trực tiếp |
| **Cài đặt ADB** | Phải thêm vào PATH | Tự động tìm |
| **Lỗi kết nối** | Crash | Hiện GUI chọn lại |

## 🔧 Breaking Changes

### ⚠️ DEVICE_SERIAL mặc định đã bị xóa!

**Trước:**
```python
DEVICE_SERIAL = "emulator-5554"  # Hardcode
```

**Sau:**
```python
DEVICE_SERIAL = None  # Phải chọn từ GUI
```

**Cách fix:**
- Không cần fix gì! Chương trình tự động hiển thị GUI chọn thiết bị
- Nếu muốn chọn lại: Click nút "🔄 Chọn lại"

### ⚠️ get_selected_device() có parameter mới

**Cũ:**
```python
serial = get_selected_device()
```

**Mới:**
```python
serial = get_selected_device(force_select=False)  # False: dùng cache
serial = get_selected_device(force_select=True)   # True: hiện GUI
```

## 🐛 Bug Fixes

1. **Lỗi ADB không tìm thấy** → Fixed bằng ADB Helper
2. **Không phân biệt được nhiều LDPlayer** → Fixed bằng ldconsole
3. **Crash khi không có thiết bị** → Fixed bằng GUI chọn lại
4. **Hardcode device serial** → Fixed bằng dynamic selection

## 📊 Test Results

### Trước V3.2:
```
[ERROR] Không kết nối được emulator-5554
[BUG] Không biết thiết bị nào là LDPlayer nào
[ISSUE] Phải sửa config.py để đổi thiết bị
```

### Sau V3.2:
```
[OK] Tim thay ADB: D:\LDPlayer\LDPlayer9\adb.exe
[INFO] Devices: 2
  - emulator-5554 -> LDPlayer
  - emulator-5564 -> LDPlayer-Th
[OK] Đã kết nối: LDPlayer-Th (emulator-5564)
```

## 🎓 Migration Guide

### Nếu bạn đang dùng V2:

1. **Xóa file config cũ (nếu có):**
   ```bash
   python -c "from gui_select_device import clear_selected_device; clear_selected_device()"
   ```

2. **Chạy Auto Farm:**
   ```bash
   python gui_auto_farm.py
   ```

3. **Chọn thiết bị từ danh sách**
   - Danh sách sẽ tự động hiện lên
   - Tên LDPlayer hiển thị rõ ràng
   - Click "Chọn thiết bị"

4. **Hoàn tất!**
   - Thiết bị được lưu
   - Lần sau không cần chọn lại (trừ khi muốn đổi)

### Nếu muốn đổi thiết bị:

- Click nút **"🔄 Chọn lại"** trong Auto Farm GUI
- Chọn LDPlayer khác
- Xong!

## 📝 Notes

### Lưu ý quan trọng:
1. **File `selected_device.json` lưu thiết bị đã chọn**
   - Tự động tạo khi chọn thiết bị
   - Xóa file này để reset

2. **Danh sách LDPlayer cập nhật real-time**
   - Click "🔄 Làm mới" để cập nhật danh sách
   - Tự động phát hiện LDPlayer mới

3. **Tên LDPlayer lấy từ ldconsole**
   - Map theo thứ tự trong `adb devices`
   - Nếu đổi tên LDPlayer, restart để cập nhật

## 🎉 Summary

**Phiên bản V3.2 mang đến:**
- ✅ Không còn hardcode device serial
- ✅ Chọn thiết bị từ danh sách GUI
- ✅ Hiển thị tên LDPlayer thân thiện
- ✅ Đổi thiết bị dễ dàng (1 click)
- ✅ Tự động xử lý lỗi kết nối
- ✅ Click chọn vị trí trực quan
- ✅ ADB Helper tự động

**Kết quả:**
- Dễ dùng hơn 10 lần!
- Không cần config thủ công
- Hỗ trợ nhiều LDPlayer
- Phù hợp mọi người dùng

---

**Happy farming with dynamic device selection! 🎮🌾**

*Updated: 2026-01-09*
*Version: 3.2.0*
