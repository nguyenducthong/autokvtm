"""
Tool script: Test và debug trực tiếp tính năng Mở Rương trên LDPlayer
Chạy bằng lệnh: python tools/test_mo_ruong.py
"""

import sys
import os
import time
import logging

# Thêm root dir vào sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.adb_helper import get_adb_helper
from core.adb import ADBController
from core.mo_ruong import mo_ruong, reset_day_kho

# Thiết lập log console rõ ràng
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("TEST_MO_RUONG")


def main():
    print("=" * 65)
    print(" 🎁 TOOL DEBUG VÀ KIỂM TRA CHỨC NĂNG MỞ RƯƠNG")
    print("=" * 65)

    helper = get_adb_helper()
    devices = helper.get_devices()

    if not devices:
        print("\n❌ Không tìm thấy thiết bị LDPlayer nào đang kết nối!")
        print("💡 Hãy mở giả lập LDPlayer và thử lại.")
        return

    print(f"\n📱 Tìm thấy {len(devices)} thiết bị đang kết nối:")
    for idx, d in enumerate(devices):
        name = helper.get_device_name(d)
        print(f"  [{idx + 1}] {name} (Serial: {d})")

    # Mặc định chọn thiết bị đầu tiên nếu chỉ có 1
    if len(devices) == 1:
        target_serial = devices[0]
        print(f"\n👉 Tự động chọn: {helper.get_device_name(target_serial)} ({target_serial})")
    else:
        choice = input(f"\nChọn thiết bị (1-{len(devices)}, Enter chọn [1]): ").strip()
        try:
            target_idx = int(choice) - 1 if choice else 0
            target_serial = devices[target_idx]
        except Exception:
            target_serial = devices[0]

    dev_name = helper.get_device_name(target_serial)
    print(f"\n🚀 Bắt đầu test Mở Rương trên: {dev_name} ({target_serial})")
    print("-" * 65)

    # Khởi tạo ADB
    adb = ADBController(serial=target_serial)

    # Reset cờ đầy kho nếu có từ trước
    reset_day_kho(target_serial)

    # Chạy mở rương với force=True (bỏ qua giới hạn 20 phút)
    t0 = time.time()
    success = mo_ruong(adb, serial=target_serial, force=True)
    elapsed = time.time() - t0

    print("-" * 65)
    if success:
        print(f"✅ KẾT QUẢ: Mở rương THÀNH CÔNG! (Thời gian: {elapsed:.1f}s)")
    else:
        print(f"⚠️ KẾT QUẢ: Không mở được rương hoặc đã bỏ qua (Thời gian: {elapsed:.1f}s)")
    print("=" * 65)


if __name__ == "__main__":
    main()
