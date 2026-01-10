# Hướng dẫn Auto Farm V2 - Kéo giỏ & Kéo hạt

## 📋 Cơ chế game

Game sử dụng cơ chế **kéo thả (drag & drop)**:

1. **Thu hoạch**: 🧺 Kéo **giỏ** qua các cây đã chín
2. **Trồng cây**: 🌱 Kéo **icon hạt giống** từ menu qua ô trống

## ✨ Tính năng

### 1. Kéo giỏ thu hoạch (từng cây) 🧺
- Kéo giỏ từ vị trí ban đầu → qua từng cây
- Chính xác, không bỏ sót
- Tốc độ: ~15 giây / 24 cây

### 2. Kéo giỏ nhanh (cả hàng) 🧺💨
- Kéo giỏ qua tất cả cây trong hàng 1 lần
- Siêu nhanh: ~3 giây / 24 cây
- **Khuyên dùng nhất!**

### 3. Kéo hạt trồng cây 🌱
- Kéo icon hạt từ menu → qua từng ô trống
- Tự động trồng loại hạt đã chọn

### 4. Chu trình hoàn chỉnh 🔄
- Thu hoạch hàng → Trồng lại hàng → Lặp lại

## 🚀 Hướng dẫn sử dụng

### Bước 1: Chuẩn bị

1. **Mở game** trên LDPlayer
2. **Vào màn hình farm** (màn hình có hàng cây)
3. **Đảm bảo có cây chín** (cây có icon trên đầu)

### Bước 2: Lấy tọa độ

#### 2.1. Lấy vị trí giỏ thu hoạch 🧺

**Quan trọng**: Khi cây chín, giỏ sẽ xuất hiện ở đâu đó trên màn hình (thường góc dưới trái)

Cách lấy:
1. Mở **Screenshot Tool** (F2)
2. Chụp màn hình khi có cây chín
3. Crop vùng **icon giỏ** (giỏ màu nâu/vàng)
4. Xem tọa độ X, Y ở góc dưới
5. Nhập vào ô "🧺 Vị trí giỏ thu hoạch"

**Ví dụ từ ảnh**: X=100, Y=700

#### 2.2. Lấy vị trí hạt giống 🌱

Khi tap vào ô trống, menu hạt giống sẽ xuất hiện

Cách lấy:
1. Chụp màn hình khi menu hạt giống đang mở
2. Crop vùng **icon hạt** mà bạn muốn trồng
   - Ví dụ: hạt cà chua, hạt bông, hạt táo...
3. Xem tọa độ X, Y
4. Nhập vào ô "🌱 Vị trí icon hạt giống"

**Ví dụ từ ảnh**: X=150, Y=100

### Bước 3: Chọn hàng

```
☑ Hàng 1 (dưới cùng - hàng con bò/cừu)
☑ Hàng 2 (hàng con gà)
☑ Hàng 3 (hàng rau có menu)
☑ Hàng 4 (trên cùng - hàng con vịt)
```

### Bước 4: Chọn chức năng

| Chức năng | Mô tả | Tốc độ | Khi nào dùng |
|-----------|-------|--------|--------------|
| **🧺 Kéo giỏ (từng cây)** | Kéo giỏ qua từng cây | Chậm | Cẩn thận, chắc chắn |
| **🧺💨 Kéo giỏ nhanh** | Kéo giỏ qua cả hàng | Rất nhanh | **Khuyên dùng** |
| **🌱 Kéo hạt** | Kéo hạt qua ô trống | Trung bình | Trồng cây mới |
| **🔄 Chu trình** | Thu + Trồng | Tổng hợp | Farm liên tục |

## 📐 Tọa độ mặc định

### Tọa độ các hàng cây

Dựa trên ảnh bạn gửi:

```python
Hàng 1 (con bò/cừu):  Y=730, X: 310→785 (6 cây)
Hàng 2 (con gà):      Y=550, X: 310→785 (6 cây)
Hàng 3 (rau có menu): Y=380, X: 310→785 (6 cây)
Hàng 4 (con vịt):     Y=210, X: 310→785 (6 cây)
```

### Tọa độ icon quan trọng

```python
Giỏ thu hoạch:     X=100,  Y=700  (góc dưới trái)
Icon hạt giống:    X=150,  Y=100  (trong menu)
```

**Lưu ý**: Tọa độ này có thể khác nhau tùy độ phân giải màn hình. Hãy dùng Screenshot Tool để lấy chính xác!

## 🎯 Quy trình làm việc

### Quy trình 1: Thu hoạch nhanh nhất

```
1. Lấy tọa độ giỏ (chỉ cần lấy 1 lần)
2. Chọn tất cả hàng
3. Click "🧺💨 Kéo giỏ nhanh"
4. Hoàn thành trong 3-5 giây!
```

### Quy trình 2: Thu hoạch + Trồng lại

```
1. Lấy tọa độ giỏ (1 lần)
2. Lấy tọa độ hạt giống (1 lần)
3. Chọn hàng cần xử lý
4. Click "🔄 Thu hoạch + Trồng lại"
5. Bot tự động:
   - Thu hoạch hàng 1 → Trồng lại hàng 1
   - Thu hoạch hàng 2 → Trồng lại hàng 2
   - ...
```

### Quy trình 3: Trồng cây mới

```
1. Lấy tọa độ hạt giống
2. Chọn hàng cần trồng
3. Click "🌱 Kéo hạt trồng cây"
4. Bot kéo hạt qua từng ô trống
```

## 💡 Tips quan trọng

### Tip 1: Dùng "Kéo giỏ nhanh"

**Đây là cách nhanh nhất!**
- Kéo giỏ qua tất cả cây trong 1 đường
- Nhanh gấp 5 lần so với kéo từng cây
- 24 cây chỉ mất ~3 giây

### Tip 2: Lấy tọa độ chính xác

**Quan trọng nhất!** Nếu tọa độ sai, bot sẽ kéo sai chỗ.

Cách kiểm tra:
1. Chụp màn hình
2. Mở trong Screenshot Tool
3. Zoom vào xem rõ icon
4. Crop chính xác vào giữa icon
5. Copy tọa độ

### Tip 3: Kiểm tra giỏ xuất hiện ở đâu

Giỏ thu hoạch chỉ xuất hiện khi có cây chín. Hãy:
1. Chờ cây chín
2. Xem giỏ xuất hiện ở đâu
3. Lấy tọa độ giỏ

### Tip 4: Menu hạt giống

Menu hạt chỉ xuất hiện khi tap vào ô trống. Hãy:
1. Tap vào ô trống
2. Menu hiện lên
3. Chụp màn hình ngay
4. Lấy tọa độ hạt

## 🎮 Các trường hợp sử dụng

### Trường hợp 1: Farm nhanh (chỉ thu hoạch)

**Mục tiêu**: Thu hoạch cây chín nhanh nhất

```
Hành động: 🧺💨 Kéo giỏ nhanh
Thời gian: 3-5 giây / 24 cây
Cần cài đặt: Vị trí giỏ
```

### Trường hợp 2: Farm liên tục (thu + trồng)

**Mục tiêu**: Thu hoạch xong trồng lại ngay

```
Hành động: 🔄 Thu hoạch + Trồng lại
Thời gian: ~30 giây / chu trình
Cần cài đặt: Vị trí giỏ + Vị trí hạt
```

### Trường hợp 3: Trồng loại cây mới

**Mục tiêu**: Đổi loại cây trồng

```
Hành động: 🌱 Kéo hạt trồng cây
Cần cài đặt: Vị trí hạt loại mới
```

### Trường hợp 4: Thu hoạch chọn lọc

**Mục tiêu**: Chỉ thu hoạch hàng đã chín

```
1. Bỏ tick hàng chưa chín
2. Chỉ chọn hàng đã chín
3. 🧺💨 Kéo giỏ nhanh
```

## 🔧 Điều chỉnh tọa độ

### Nếu bot kéo sai vị trí

**Nguyên nhân**: Tọa độ không chính xác

**Giải pháp**:
1. Dùng Screenshot Tool
2. Chụp lại màn hình
3. Crop chính xác vào giữa icon
4. Nhập tọa độ mới

### Nếu bot kéo quá nhanh/chậm

**Điều chỉnh delay**:
```
Tap delay: 300ms
Harvest delay: 500ms
Plant delay: 500ms
```

Tăng lên nếu máy chậm, giảm xuống nếu muốn nhanh hơn.

## 📊 So sánh hiệu suất

### Thu hoạch 24 cây (4 hàng x 6 cây)

| Phương pháp | Thời gian | Cơ chế |
|-------------|-----------|--------|
| **Tap từng cây (old)** | 15s | Tap 24 lần |
| **Kéo giỏ từng cây** | 12s | Kéo 24 lần |
| **Kéo giỏ nhanh** | 3s | Kéo 4 lần |

**→ Kéo giỏ nhanh = nhanh nhất!**

### Chu trình đầy đủ (Thu + Trồng)

```
Thu hoạch (kéo giỏ nhanh): 3s
Trồng lại (kéo hạt):        15s
Delay giữa các hàng:        2s
-------------------------------------
Tổng:                       20s
```

## 🐛 Xử lý lỗi

### Lỗi: Bot kéo không đúng chỗ

**Nguyên nhân**: Tọa độ sai

**Giải pháp**:
1. Kiểm tra tọa độ bằng Screenshot Tool
2. Đảm bảo crop đúng giữa icon
3. Nhập lại tọa độ

### Lỗi: Không thu hoạch được

**Nguyên nhân**:
- Giỏ chưa xuất hiện (cây chưa chín)
- Tọa độ giỏ sai

**Giải pháp**:
1. Chờ cây chín (giỏ mới xuất hiện)
2. Lấy lại tọa độ giỏ

### Lỗi: Không trồng được cây

**Nguyên nhân**:
- Tọa độ hạt giống sai
- Menu chưa mở

**Giải pháp**:
1. Tap vào ô trống để mở menu
2. Chụp màn hình khi menu đang mở
3. Lấy tọa độ hạt chính xác

## 📸 Hướng dẫn lấy tọa độ bằng Screenshot Tool

### Bước 1: Chụp màn hình game

1. Mở Screenshot Tool
2. Bấm F2
3. Ảnh hiện lên canvas

### Bước 2: Crop icon cần lấy

1. Click và kéo chuột để chọn vùng icon
2. Rectangle đỏ sẽ hiển thị
3. Nhả chuột

### Bước 3: Xem tọa độ

```
Xem ở panel bên phải:
X: 100
Y: 700
W: 50
H: 50
```

→ Lấy X, Y (bỏ W, H)

### Bước 4: Copy vào Auto Farm

Nhập X, Y vào ô tương ứng trong Auto Farm GUI

## 🎯 Checklist trước khi chạy

- [ ] LDPlayer đang chạy game
- [ ] Đang ở màn hình farm
- [ ] Có cây chín (giỏ đã xuất hiện)
- [ ] Đã lấy tọa độ giỏ
- [ ] Đã lấy tọa độ hạt (nếu cần trồng)
- [ ] Đã chọn hàng cần xử lý
- [ ] Đã kiểm tra delay

## 💻 Code tham khảo

### Kéo giỏ thu hoạch 1 hàng

```python
from core.auto_farm import AutoFarm
from core.adb import ADBController

adb = ADBController(serial="emulator-5554")
farm = AutoFarm(adb)

# Vị trí giỏ
basket = (100, 700)

# Kéo giỏ qua hàng 1
farm.harvest_row_drag(row=1, basket_pos=basket)
```

### Kéo hạt trồng cây

```python
# Vị trí icon hạt cà chua
tomato_seed = (150, 100)

# Trồng hàng 2
farm.plant_row(row=2, seed_icon_pos=tomato_seed)
```

### Chu trình hoàn chỉnh

```python
basket = (100, 700)
seed = (150, 100)

# Thu hoạch + trồng lại
for row in [1, 2, 3, 4]:
    farm.harvest_row_drag(row, basket)
    farm.plant_row(row, seed)
```

---

**Happy farming! 🧺🌱**
