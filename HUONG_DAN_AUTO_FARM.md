# Hướng dẫn Auto Farm - Thu hoạch & Trồng cây tự động

## 📋 Tổng quan

Auto Farm giúp tự động hóa hoàn toàn việc thu hoạch và trồng cây trong game farm.

### ✨ Tính năng

1. **Thu hoạch tự động**: Tap từng cây để thu hoạch
2. **Trồng cây tự động**: Tap từng ô trống để trồng cây mới
3. **Chu trình hoàn chỉnh**: Thu hoạch xong → Trồng lại ngay
4. **Vuốt nhanh**: Vuốt cả hàng để thu hoạch siêu nhanh
5. **Chọn hàng**: Chọn hàng nào cần thu hoạch/trồng
6. **Tùy chỉnh delay**: Điều chỉnh tốc độ tap

## 🚀 Cách sử dụng

### Cách 1: Chạy từ GUI chính
```bash
python main.py
```
→ Click **🌾 Thu hoạch** hoặc **🌱 Trồng cây**

### Cách 2: Chạy trực tiếp
```bash
# Double-click
run_auto_farm.bat

# Hoặc
python gui_auto_farm.py
```

## 🎮 Hướng dẫn chi tiết

### Bước 1: Chuẩn bị

1. **Mở game farm** trên LDPlayer
2. **Vào màn hình farm** (màn hình có các hàng cây)
3. **Đảm bảo cây đã chín** (có icon trên đầu cây)

### Bước 2: Cấu hình

#### 2.1. Chọn hàng cần xử lý

Tick chọn hàng bạn muốn:
```
☑ Hàng 1 (dưới cùng)
☑ Hàng 2
☑ Hàng 3
☑ Hàng 4 (trên cùng)
```

**Tips**:
- Bấm "✓ Chọn tất cả" để chọn cả 4 hàng
- Bấm "✗ Bỏ chọn tất cả" để reset

#### 2.2. Cài đặt vị trí icon hạt giống (cho trồng cây)

**Cách lấy tọa độ:**

1. Mở **Screenshot Tool**
2. Chụp màn hình game
3. Crop vùng icon hạt giống (vd: icon cà chua)
4. Xem tọa độ X, Y
5. Nhập vào ô "Vị trí icon hạt giống"

**Ví dụ**: X=400, Y=300

#### 2.3. Điều chỉnh delay (tùy chọn)

```
Tap delay: 300ms (tốc độ tap thường)
Harvest delay: 500ms (thời gian chờ sau thu hoạch)
Plant delay: 500ms (thời gian chờ sau trồng cây)
```

**Lưu ý**: Delay nhỏ = nhanh hơn nhưng có thể bị miss

### Bước 3: Chạy

#### 3.1. Thu hoạch

Click **🌾 Thu hoạch**
- Bot sẽ tap từng cây trong các hàng đã chọn
- Thu hoạch tuần tự từ trái sang phải
- Hoàn thành 1 hàng rồi chuyển sang hàng tiếp theo

#### 3.2. Trồng cây

Click **🌱 Trồng cây**
- Bot sẽ tap từng ô trống
- Tự động chọn hạt giống (nếu đã cài đặt tọa độ)
- Trồng tuần tự từ trái sang phải

#### 3.3. Chu trình hoàn chỉnh

Click **🔄 Thu hoạch + Trồng lại**
- Thu hoạch hàng 1 → Trồng lại hàng 1
- Thu hoạch hàng 2 → Trồng lại hàng 2
- ...
- Tiết kiệm thời gian chờ

#### 3.4. Vuốt nhanh (khuyên dùng cho thu hoạch)

Click **💨 Vuốt thu hoạch nhanh**
- Vuốt cả hàng 1 lần
- Nhanh gấp 5-10 lần so với tap từng cây
- Chỉ dùng để thu hoạch, không trồng được

## 📐 Tọa độ mặc định

Bot sử dụng tọa độ cố định cho các hàng cây:

```python
Hàng 1 (dưới): Y=730, X: 310→785 (6 cây)
Hàng 2:        Y=550, X: 310→785 (6 cây)
Hàng 3:        Y=380, X: 310→785 (6 cây)
Hàng 4 (trên): Y=210, X: 310→785 (6 cây)

Spacing giữa các cây: 95px
```

### Điều chỉnh tọa độ (nếu cần)

Nếu tọa độ không chính xác, sửa trong file [core/auto_farm.py](core/auto_farm.py):

```python
self.ROWS = {
    1: {"y": 730, "x_start": 310, "spacing": 95, "count": 6},
    # Sửa y, x_start, spacing theo màn hình của bạn
}
```

**Cách lấy tọa độ chính xác:**
1. Dùng Screenshot Tool chụp màn hình
2. Crop vùng cây đầu tiên của hàng
3. Xem tọa độ X, Y → Đó là x_start, y
4. Crop vùng cây thứ 2
5. Tính spacing = X_cây2 - X_cây1

## 🎯 Chiến thuật hiệu quả

### Chiến thuật 1: Thu hoạch nhanh
```
1. Vuốt thu hoạch tất cả (💨)
2. Trồng cây từng hàng (🌱)
```

### Chiến thuật 2: Chu trình ổn định
```
1. Thu hoạch + Trồng lại (🔄)
   → Đảm bảo không có ô trống
```

### Chiến thuật 3: Thu hoạch chọn lọc
```
1. Bỏ tick hàng chưa chín
2. Chỉ thu hoạch hàng đã chín
3. Quay lại sau để thu hoạch hàng còn lại
```

## ⚙️ Tùy chỉnh nâng cao

### 1. Thay đổi số lượng cây mỗi hàng

Sửa trong [core/auto_farm.py](core/auto_farm.py):
```python
self.ROWS = {
    1: {"y": 730, "x_start": 310, "spacing": 95, "count": 8},  # 8 cây
}
```

### 2. Thêm hàng mới

```python
self.ROWS = {
    1: {...},
    2: {...},
    3: {...},
    4: {...},
    5: {"y": 100, "x_start": 310, "spacing": 95, "count": 6},  # Hàng 5
}
```

### 3. Điều chỉnh vùng thu hoạch

```python
self.TREE_CHECK_OFFSET = (0, -50)  # Tap cao hơn 50px
```

## 🐛 Xử lý lỗi

### Lỗi: Tap sai vị trí

**Nguyên nhân**: Tọa độ không chính xác

**Giải pháp**:
1. Dùng Screenshot Tool chụp màn hình
2. Kiểm tra vị trí cây
3. Điều chỉnh tọa độ trong code

### Lỗi: Không trồng được cây

**Nguyên nhân**: Chưa cài đặt tọa độ icon hạt giống

**Giải pháp**:
1. Lấy tọa độ icon hạt giống bằng Screenshot Tool
2. Nhập vào ô "Vị trí icon hạt giống"

### Lỗi: Bot chạy quá nhanh, bị miss

**Giải pháp**: Tăng delay
```
Tap delay: 500ms
Harvest delay: 800ms
Plant delay: 800ms
```

### Lỗi: Bot chạy quá chậm

**Giải pháp**:
1. Giảm delay xuống 200-300ms
2. Hoặc dùng "Vuốt thu hoạch nhanh"

## 📊 Hiệu suất

### Tốc độ thu hoạch

**Tap từng cây:**
- 24 cây (4 hàng x 6 cây)
- Delay 500ms/cây
- Tổng thời gian: ~12-15 giây

**Vuốt nhanh:**
- 4 hàng
- Delay 500ms/hàng
- Tổng thời gian: ~2-3 giây

**→ Vuốt nhanh hơn gấp 5 lần!**

### Tốc độ chu trình (Thu hoạch + Trồng)

- Thu hoạch: ~15 giây
- Trồng lại: ~15 giây
- **Tổng: ~30 giây cho 1 chu trình hoàn chỉnh**

## 💡 Tips & Tricks

### Tip 1: Dùng vuốt cho thu hoạch

Vuốt nhanh hơn nhiều so với tap từng cây. Chỉ cần vuốt qua là tất cả cây trong hàng đều được thu hoạch.

### Tip 2: Cài đặt tọa độ hạt giống chính xác

Điều này giúp bot trồng đúng loại cây bạn muốn. Nếu không cài đặt, bot sẽ chỉ tap vào ô trống (có thể không trồng được).

### Tip 3: Chọn hàng linh hoạt

Không nhất thiết phải chọn cả 4 hàng. Chọn hàng nào đã chín thì thu hoạch hàng đó.

### Tip 4: Kết hợp với Screenshot Tool

Dùng Screenshot Tool để:
- Lấy tọa độ chính xác
- Debug vị trí tap
- Crop icon hạt giống

### Tip 5: Chạy loop

Nếu muốn chạy nhiều lần:
```python
from core.auto_farm import AutoFarm
from core.adb import ADBController

adb = ADBController(serial="emulator-5554")
farm = AutoFarm(adb)

# Chạy 10 lần
for i in range(10):
    print(f"Lần {i+1}")
    farm.harvest_and_plant(seed_icon_pos=(400, 300))
    import time
    time.sleep(60)  # Chờ 60s giữa các lần
```

## 🔧 Code tham khảo

### Thu hoạch từng hàng cụ thể

```python
from core.auto_farm import AutoFarm
from core.adb import ADBController

adb = ADBController(serial="emulator-5554")
farm = AutoFarm(adb)

# Thu hoạch chỉ hàng 1 và 3
farm.harvest_all(rows=[1, 3])
```

### Trồng cây với hạt giống tùy chọn

```python
# Vị trí icon hạt cà chua
tomato_seed = (400, 300)

farm.plant_all(rows=[1, 2], seed_icon_pos=tomato_seed)
```

### Vuốt thu hoạch

```python
# Vuốt tất cả
farm.swipe_harvest_all()

# Hoặc vuốt từng hàng
farm.swipe_harvest_row(1)
```

## 📞 Hỗ trợ

Nếu gặp vấn đề:
1. Kiểm tra LDPlayer đang chạy
2. Kiểm tra ADB kết nối: `adb devices`
3. Kiểm tra tọa độ bằng Screenshot Tool
4. Xem log trong cửa sổ Auto Farm

---

**Good luck farming! 🌾🌱**
