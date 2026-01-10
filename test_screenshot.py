"""
Test script - Kiểm tra chức năng chụp màn hình
"""

from core.adb import ADBController
from gui_select_device import get_selected_device
import os

def test_screenshot():
    """Test chụp màn hình"""
    print("="*60)
    print("   TEST CHỤP MÀN HÌNH")
    print("="*60)

    # 1. Lấy thiết bị
    print("\n[1] Đang lấy thông tin thiết bị...")
    try:
        device_serial = get_selected_device()
        print(f"✓ Thiết bị: {device_serial}")
    except Exception as e:
        print(f"✗ Lỗi khi lấy thiết bị: {e}")
        return

    # 2. Kết nối ADB
    print("\n[2] Đang kết nối ADB...")
    try:
        adb = ADBController(serial=device_serial)
        print(f"✓ Đã kết nối: {adb.device.get_serial_no()}")
    except Exception as e:
        print(f"✗ Lỗi kết nối ADB: {e}")
        return

    # 3. Kiểm tra kết nối
    print("\n[3] Kiểm tra kết nối thiết bị...")
    try:
        if adb.is_connected():
            print("✓ Thiết bị đang kết nối")
        else:
            print("✗ Thiết bị không phản hồi")
            return
    except Exception as e:
        print(f"✗ Lỗi kiểm tra kết nối: {e}")
        return

    # 4. Tạo thư mục cache
    print("\n[4] Đang tạo thư mục cache...")
    try:
        os.makedirs("cache", exist_ok=True)
        print("✓ Thư mục cache đã sẵn sàng")
    except Exception as e:
        print(f"✗ Lỗi tạo thư mục: {e}")
        return

    # 5. Chụp màn hình
    print("\n[5] Đang chụp màn hình...")
    try:
        screenshot = adb.screenshot_full("cache/test_screenshot.png")
        h, w = screenshot.shape[:2]
        print(f"✓ Chụp thành công!")
        print(f"  - Kích thước: {w}x{h}")
        print(f"  - Đã lưu: cache/test_screenshot.png")
    except Exception as e:
        print(f"✗ Lỗi chụp màn hình: {e}")
        print("\nChi tiết lỗi:")
        import traceback
        traceback.print_exc()
        return

    # 6. Thành công
    print("\n" + "="*60)
    print("✓ TEST HOÀN THÀNH - Chụp màn hình thành công!")
    print("="*60)

if __name__ == "__main__":
    test_screenshot()
    input("\nNhấn Enter để thoát...")
