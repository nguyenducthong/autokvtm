# Hướng dẫn Auto Detect - Tự động nhận diện & hành động

## 🤖 Tổng quan

Tính năng **Auto Detect** tự động nhận diện màn hình game và quyết định hành động:
- **Phát hiện giỏ thu hoạch** → Tự động kéo giỏ thu hoạch
- **Phát hiện menu trồng cây** → Tự động chọn cây và trồng

**Không cần click chọn vị trí thủ công nữa!**

## 🎯 Cách hoạt động

### Quy trình tự động:

```
1. Click nút "🤖 Auto Detect & Action"
      ↓
2. Chụp màn hình game
      ↓
3. Phân tích hình ảnh
      ↓
4a. Nếu thấy giỏ:           4b. Nếu thấy menu trồng cây:
    → Lưu vị trí giỏ            → Lưu vị trí hạt giống
    → Thu hoạch các hàng        → Trồng cây các hàng
      ↓                            ↓
5. Hoàn thành!             5. Hoàn thành!
```

## 📋 Chuẩn bị

### Bước 1: Chuẩn bị template ảnh

Bạn cần có các file ảnh template trong `assets/items/`:

**Thu hoạch:**
- `thu_hoach.png` - Ảnh icon giỏ thu hoạch (crop từ screenshot)

**Trồng cây:**
- `cay_hong.png` - Icon hạt hồng
- `cay_tao.png` - Icon hạt táo
- `cay_bong.png` - Icon hạt bông
- `cay_tuyet.png` - Icon hạt tuyết

### Bước 2: Crop ảnh template

Cách lấy template:
1. Chụp màn hình game (Screenshot Tool)
2. Crop chính xác icon giỏ/hạt (chỉ icon, không lấy background)
3. Lưu vào `assets/items/`
4. Đặt tên đúng format

**Ví dụ crop giỏ thu hoạch:**
```
Screenshot game → Crop icon giỏ (30x30px) → Lưu: thu_hoach.png
```

## 🚀 Cách sử dụng

### Trường hợp 1: Thu hoạch tự động

**Khi nào dùng:** Cây đã chín, giỏ thu hoạch đang hiển thị

**Bước:**
1. Đảm bảo giỏ thu hoạch **đang hiển thị** trên màn hình
2. Chọn các hàng cần thu hoạch (hoặc để trống = chọn tất cả)
3. Click **"🤖 Auto Detect & Action"**
4. Hệ thống sẽ:
   - Phát hiện vị trí giỏ
   - Tự động kéo giỏ qua tất cả cây
   - Báo hoàn thành

**Kết quả:**
```
📸 Đang chụp màn hình...
🔍 Đang phát hiện giỏ/menu trồng cây...
✓ Phát hiện giỏ thu hoạch tại: (100, 700)
🧺 Bắt đầu thu hoạch...
✓ Hoàn thành thu hoạch!
```

### Trường hợp 2: Trồng cây tự động

**Khi nào dùng:** Ô trống, menu chọn cây đang mở

**Bước:**
1. **Tap vào ô trống** trong game để mở menu chọn cây
2. Menu cây hiển thị (hồng, táo, bông, tuyết...)
3. Chọn các hàng cần trồng (hoặc để trống = tất cả)
4. Click **"🤖 Auto Detect & Action"**
5. Hệ thống sẽ:
   - Phát hiện loại cây nào có trong menu
   - Lưu vị trí icon hạt
   - Tự động kéo hạt đến các ô
   - Báo hoàn thành

**Kết quả:**
```
📸 Đang chụp màn hình...
🔍 Đang phát hiện giỏ/menu trồng cây...
✓ Phát hiện menu trồng cây: hong tại (150, 100)
🌱 Bắt đầu trồng hong...
✓ Hoàn thành trồng cây!
```

## ⚙️ Cấu hình Template

### Ngưỡng nhận diện (Threshold)

Mặc định: `0.7` (70% độ tương đồng)

**Chỉnh sửa trong code:**
```python
# gui_auto_farm.py, dòng 41
self.image_detector = ImageDetector(threshold=0.7)
```

**Gợi ý:**
- `0.6` - Nhận diện lỏng lẻo hơn (nhiều kết quả giả)
- `0.7` - **Khuyến nghị** (cân bằng)
- `0.8` - Chặt chẽ hơn (ít kết quả giả nhưng có thể bỏ sót)

### Thêm template cây mới

**File:** `core/image_detection.py`

Tìm dòng:
```python
plant_templates = [
    "assets/items/cay_hong.png",
    "assets/items/cay_tao.png",
    "assets/items/cay_bong.png",
    "assets/items/cay_tuyet.png"
]
```

Thêm template mới:
```python
plant_templates = [
    "assets/items/cay_hong.png",
    "assets/items/cay_tao.png",
    "assets/items/cay_bong.png",
    "assets/items/cay_tuyet.png",
    "assets/items/cay_dau.png"  # ← Thêm cây dâu
]
```

## 🎮 Quy trình làm việc

### Workflow 1: Chu trình hoàn chỉnh

```
1. Cây chín
   → Click "🤖 Auto Detect" → Thu hoạch xong

2. Tap vào ô trống (mở menu)
   → Click "🤖 Auto Detect" → Trồng cây xong

3. Đợi cây chín
   → Lặp lại bước 1
```

### Workflow 2: Sử dụng cùng với manual

```
1. Dùng Auto Detect để thu hoạch
2. Manual click chọn vị trí hạt (nếu muốn trồng loại cây cụ thể)
3. Click "🌱 Kéo hạt trồng cây" (manual mode)
```

## 🐛 Xử lý lỗi

### Lỗi: "Không phát hiện được giỏ hoặc menu"

**Nguyên nhân:**
- Template ảnh không khớp với game
- Giỏ/menu không hiển thị
- Ngưỡng threshold quá cao

**Giải pháp:**
1. Kiểm tra file template có tồn tại không:
   - `assets/items/thu_hoach.png`
   - `assets/items/cay_*.png`

2. Kiểm tra giỏ/menu đang hiển thị:
   - Thu hoạch: Đảm bảo cây chín, giỏ xuất hiện
   - Trồng cây: Đảm bảo đã tap vào ô trống

3. Crop lại template:
   - Crop chính xác hơn
   - Chỉ lấy icon, không lấy background
   - Lưu đúng định dạng PNG

4. Giảm threshold:
   ```python
   self.image_detector = ImageDetector(threshold=0.6)
   ```

### Lỗi: Phát hiện sai vị trí

**Nguyên nhân:**
- Template quá nhỏ/lớn
- Có nhiều icon giống nhau trên màn hình

**Giải pháp:**
- Crop template có kích thước chuẩn (30x30px đến 50x50px)
- Đảm bảo icon unique (không trùng với icon khác)

### Lỗi: Không tìm thấy file template

**Lỗi:**
```
FileNotFoundError: Không tìm thấy template: assets/items/thu_hoach.png
```

**Giải pháp:**
1. Tạo thư mục `assets/items/` nếu chưa có
2. Đảm bảo file template tồn tại
3. Kiểm tra đường dẫn chính xác

## 💡 Tips

### Tip 1: Crop template tốt

**Tốt:**
- Chỉ lấy icon, không lấy viền
- Kích thước vừa phải (30-50px)
- Rõ nét, không bị mờ
- Background trong suốt (nếu được)

**Không tốt:**
- Lấy quá nhiều background
- Icon quá nhỏ (<20px)
- Bị mờ, nhiễu

### Tip 2: Test từng template

```bash
# Test template
python core/image_detection.py screenshot.png
```

Kết quả sẽ cho biết template nào được phát hiện.

### Tip 3: Dùng kết hợp

- **Auto Detect:** Khi cần nhanh, tự động
- **Click chọn vị trí:** Khi cần chính xác, kiểm soát

### Tip 4: Chọn hàng trước

Mặc dù Auto Detect sẽ chọn tất cả 4 hàng nếu không chọn, nhưng **nên chọn hàng trước** để:
- Kiểm soát hàng nào được xử lý
- Tiết kiệm thời gian (không xử lý hàng không cần)

## 📊 So sánh với Click chọn

| Tính năng | Auto Detect | Click chọn vị trí |
|-----------|-------------|-------------------|
| **Tốc độ** | Nhanh (1 click) | Chậm hơn (chụp → click → xác nhận) |
| **Độ chính xác** | Phụ thuộc template | Chính xác 100% |
| **Linh hoạt** | Tự động quyết định | Kiểm soát hoàn toàn |
| **Yêu cầu** | Cần template ảnh | Không cần template |
| **Dùng khi nào** | Farm nhanh, lặp đi lặp lại | Lần đầu setup, cần chính xác |

## 🎯 Kết luận

### Ưu điểm Auto Detect:
✅ Nhanh - 1 click duy nhất
✅ Tự động - không cần chọn vị trí
✅ Thông minh - tự quyết định thu hoạch hay trồng cây
✅ Tiện lợi - phù hợp farm nhiều lần

### Nhược điểm:
❌ Cần chuẩn bị template ảnh
❌ Độ chính xác phụ thuộc template
❌ Không linh hoạt như manual

### Khi nào dùng:
- ✅ Farm hàng ngày, lặp đi lặp lại
- ✅ Cây cố định (hồng, táo, bông...)
- ✅ Muốn tự động hoàn toàn

### Khi nào KHÔNG dùng:
- ❌ Lần đầu chơi, chưa có template
- ❌ Trồng cây mới, chưa có template
- ❌ Cần kiểm soát chính xác từng bước

---

**Happy auto-farming with Auto Detect! 🤖🌾**

*Updated: 2026-01-10*
*Version: 3.3.0 - Auto Detect*
