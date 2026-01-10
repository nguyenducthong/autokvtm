# Khắc phục lỗi ADB - Không kết nối được LDPlayer

## 🔍 Vấn đề

Khi chạy Auto Farm bị lỗi:
```
[ADB] Không thể kết nối đến emulator-5554
```

hoặc không thấy thiết bị LDPlayer trong danh sách.

## ✅ Giải pháp đã áp dụng

### Phiên bản mới (V3.1)

Phần mềm đã được cập nhật với **ADB Helper** - tự động tìm ADB của LDPlayer!

**Không cần cấu hình PATH nữa!** Hệ thống tự động tìm ADB ở các vị trí:
- `D:\LDPlayer\LDPlayer9\adb.exe`
- `C:\LDPlayer\LDPlayer9\adb.exe`
- `C:\LDPlayer\LDPlayer4\adb.exe`
- Và nhiều vị trí khác...

## 🚀 Hướng dẫn sử dụng

### Bước 1: Kích hoạt ADB trong LDPlayer

1. Mở **LDPlayer**
2. Click **menu 3 gạch** (góc phải trên)
3. Chọn **"Cài đặt"** (Settings)
4. Vào tab **"Khác"** (Other settings)
5. Tìm **"ADB Debugging"**
6. **BẬT lên** (ON)
7. Click **Save** và **khởi động lại** LDPlayer

### Bước 2: Chạy Auto Farm

```bash
python gui_auto_farm.py
```

Hệ thống sẽ tự động:
1. Tìm ADB của LDPlayer
2. Quét danh sách thiết bị
3. Kết nối tự động

## 🔧 Nếu vẫn gặp lỗi

### Lỗi 1: Không tìm thấy thiết bị

**Kiểm tra:**
```bash
# Chạy ADB Helper để test
python core/adb_helper.py
```

**Kết quả mong đợi:**
```
[OK] Tim thay ADB: D:\LDPlayer\LDPlayer9\adb.exe
[INFO] Devices: 1
  - emulator-5564
```

**Nếu không tìm thấy thiết bị:**
1. Đảm bảo LDPlayer đang **chạy** (không tắt/pause)
2. Kiểm tra **ADB Debugging** đã bật chưa
3. Thử **khởi động lại LDPlayer**

### Lỗi 2: Không tìm thấy ADB

**Kết quả:**
```
[ERROR] Khong tim thay ADB!
```

**Giải pháp:**
1. Kiểm tra LDPlayer đã cài đặt chưa
2. Xác nhận đường dẫn cài đặt (C:\ hay D:\)
3. Nếu cài ở ổ khác, thêm vào file `core/adb_helper.py`:

```python
possible_paths = [
    r"E:\LDPlayer\LDPlayer9\adb.exe",  # Thêm ổ E
    r"D:\LDPlayer\LDPlayer9\adb.exe",
    # ...
]
```

### Lỗi 3: Port không đúng

**Triệu chứng:** Tìm thấy thiết bị nhưng không kết nối được

**Kiểm tra port:**
```bash
python core/adb_helper.py
```

Xem serial hiển thị (vd: `emulator-5564`)

**Sửa trong code nếu cần:**
Nếu port khác 5554, cập nhật file `selected_device.json`:
```json
{
  "serial": "emulator-5564",
  "name": "LDPlayer"
}
```

## 📋 Checklist khắc phục

- [ ] LDPlayer đã cài đặt
- [ ] LDPlayer đang chạy
- [ ] ADB Debugging đã BẬT trong Settings
- [ ] Đã test `python core/adb_helper.py` và thấy thiết bị
- [ ] Đã khởi động lại LDPlayer (nếu cần)

## 💡 Tips

### Tip 1: Dùng GUI để restart ADB

1. Mở Auto Farm GUI
2. Nếu không thấy thiết bị
3. Thử **Menu Công cụ > Khởi động lại ADB Server**

### Tip 2: Kiểm tra nhiều LDPlayer

Nếu bạn chạy nhiều LDPlayer cùng lúc:
- Mỗi LDPlayer sẽ có serial riêng (emulator-5554, emulator-5556, ...)
- GUI sẽ hiển thị tất cả
- Chọn đúng LDPlayer bạn muốn điều khiển

### Tip 3: Khởi động lại sạch

Nếu mọi cách đều thất bại:
```bash
# 1. Tắt LDPlayer
# 2. Chạy lệnh này
python core/adb_helper.py

# 3. Nếu báo lỗi, restart ADB:
D:\LDPlayer\LDPlayer9\adb.exe kill-server
D:\LDPlayer\LDPlayer9\adb.exe start-server

# 4. Mở LDPlayer lại
# 5. Test:
python core/adb_helper.py
```

## 🎯 Kết luận

Với **ADB Helper**, bạn không cần:
- ❌ Thêm ADB vào PATH
- ❌ Copy adb.exe ra folder khác
- ❌ Cấu hình môi trường phức tạp

Chỉ cần:
- ✅ Cài LDPlayer
- ✅ Bật ADB Debugging
- ✅ Chạy Auto Farm

Hệ thống tự động lo phần còn lại! 🎉

---

**Nếu vẫn gặp vấn đề, kiểm tra:**
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Xử lý lỗi chung
- [README.md](README.md) - Hướng dẫn tổng quan
