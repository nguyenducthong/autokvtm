# Import chỉ những gì cần thiết cho GUI mode
# Các module khác sẽ được import khi cần dùng (lazy import)
from config import WAREHOUSE_ITEM_KSK, CONFIG_TEMP_TC
import utils.logger  # Ensure logging is configured early (file + console)
import time
from core.adb import ADBController
from gui_select_device import DeviceSelector, get_selected_device
import os

# Biến toàn cục lưu serial hiện tại
current_device_serial = None
def hien_thi_menu_kho():
    print("\n" + "="*60)
    print("   CHỌN VẬT PHẨM ĐẶT VÀO KHO SỰ KIỆN (KSK)")
    print("="*60)
    for idx, item in enumerate(WAREHOUSE_ITEM_KSK, 1):
        print(f"  [{idx}] {item['name']}")
    print(f"  [0] Quay lại menu chính")
    print("-"*60)
def chon_thiet_bi():
    """Mở GUI chọn thiết bị"""
    global current_device_serial
    print("\n🔄 Đang mở GUI chọn thiết bị...")

    selector = DeviceSelector()
    device = selector.run()

    if device:
        current_device_serial = device['serial']
        print(f"✓ Đã chọn: {device['name']} ({device['serial']})")
    else:
        print("✗ Không chọn thiết bị")

def hien_thi_thiet_bi_hien_tai():
    """Hiển thị thiết bị đang dùng"""
    global current_device_serial

    if current_device_serial is None:
        # Thử load từ file
        current_device_serial = get_selected_device()

    print(f"\n📱 Thiết bị hiện tại: {current_device_serial}")

def chon_va_dat_vp():
    global current_device_serial

    # Import khi cần dùng
    from core.ban_do import dat_vp

    # Đảm bảo có thiết bị được chọn
    if current_device_serial is None:
        current_device_serial = get_selected_device()

    while True:
        adb = ADBController(serial=current_device_serial)
        hien_thi_menu_kho()
        try:
            choice = input("Chọn vật phẩm (0 để quay lại): ").strip()
            if choice == "0":
                return
            idx = int(choice) - 1
            if 0 <= idx < len(WAREHOUSE_ITEM_KSK):
                item = WAREHOUSE_ITEM_KSK[idx]
                print(f"\nĐang đặt: {item['name']}...")
                try:
                    dat_vp(
                        item["path_warehouse_not_select"],
                        item["path_warehouse_select"],
                        item["path"],
                        10,  # số lần đặt (có thể thêm menu chọn số lần sau),
                        False,
                        adb
                    )
                    print(f"Đã đặt xong: {item['name']}")
                except Exception as e:
                    print(f"Lỗi khi đặt {item['name']}: {e}")
                time.sleep(1)
            else:
                print("Lựa chọn không hợp lệ!")
        except ValueError:
            print("Vui lòng nhập số!")
        except KeyboardInterrupt:
            print("\nĐã hủy!")
            return

# === MENU CHÍNH ===
MENU_OPTIONS = {
    "1": ("Đặt vật phẩm vào kho sự kiện (KSK)", chon_va_dat_vp),
    "2": ("Chọn thiết bị LDPlayer", chon_thiet_bi),
    "3": ("Xem thiết bị hiện tại", hien_thi_thiet_bi_hien_tai),
    # "4": ("Thu hoạch cây", lambda: print("Chưa triển khai")),
    "0": ("Thoát", lambda: exit(0))
}

def hien_thi_menu_chinh():
    print("\n" + "="*50)
    print("   AUTO KHU VƯỜN TRÊN MÂY – MENU CHÍNH")
    print("="*50)
    for key, (mo_ta, _) in MENU_OPTIONS.items():
        if key != "0":
            print(f"  [{key}] {mo_ta}")
    print(f"  [0] Thoát")
    print("-"*50)

def main():
    global current_device_serial

    print("AUTO KHU VƯỜN TRÊN MÂY – KHỞI ĐỘNG!")
    print("\n🔧 Đang kiểm tra thiết bị...")

    # Tự động load thiết bị đã lưu hoặc mở GUI nếu chưa có
    current_device_serial = get_selected_device()
    print(f"✓ Thiết bị hiện tại: {current_device_serial}\n")

    while True:
        try:
            hien_thi_menu_chinh()
            choice = input("Nhập lựa chọn: ").strip()
            if choice in MENU_OPTIONS:
                ac, func = MENU_OPTIONS[choice]
                if choice == "0":
                    print("Tạm biệt!")
                    break
                print(f"\nChạy: {ac}")
                func()
            else:
                print("Lựa chọn không hợp lệ!")
            time.sleep(1)
        except KeyboardInterrupt:
            print("\nĐã dừng bởi người dùng!")
            break




if __name__ == "__main__":
    import sys

    # Kiểm tra tham số dòng lệnh
    if len(sys.argv) > 1 and sys.argv[1] == "--console":
        # Chế độ console
        print("AUTO KHU VƯỜN TRÊN MÂY – KHỞI ĐỘNG (Console Mode)!")
        main()
    else:
        # Chế độ GUI (mặc định)
        print("AUTO KHU VƯỜN TRÊN MÂY – Đang khởi động GUI...")
        try:
            from gui_main import MainGUI
            app = MainGUI()
            app.run()
        except Exception as e:
            print(f"Lỗi khi khởi động GUI: {e}")
            print("\nFallback sang chế độ console...")
            main()