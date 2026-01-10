"""
ADB Helper - Tự động tìm ADB của LDPlayer
"""

import os
import subprocess
from typing import Optional

class ADBHelper:
    """Tìm và quản lý ADB của LDPlayer"""

    def __init__(self):
        self.adb_path = self.find_adb()

    def find_adb(self) -> Optional[str]:
        """Tìm đường dẫn ADB"""

        # Thử các vị trí phổ biến của LDPlayer
        possible_paths = [
            r"D:\LDPlayer\LDPlayer9\adb.exe",
            r"D:\LDPlayer\LDPlayer4\adb.exe",
            r"C:\LDPlayer\LDPlayer9\adb.exe",
            r"C:\LDPlayer\LDPlayer4\adb.exe",
            r"C:\Program Files\LDPlayer\LDPlayer9\adb.exe",
            r"C:\Program Files\LDPlayer\LDPlayer4\adb.exe",
        ]

        # Kiểm tra từng đường dẫn
        for path in possible_paths:
            if os.path.exists(path):
                print(f"[OK] Tim thay ADB: {path}")
                return path

        # Thử tìm ADB trong PATH
        try:
            result = subprocess.run(
                ["adb", "version"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                print("[OK] Tim thay ADB trong PATH")
                return "adb"
        except:
            pass

        # Không tìm thấy
        print("[ERROR] Khong tim thay ADB!")
        return None

    def run_adb(self, args: list, timeout: int = 5) -> subprocess.CompletedProcess:
        """Chạy lệnh ADB"""
        if not self.adb_path:
            raise Exception("Không tìm thấy ADB! Vui lòng cài đặt LDPlayer.")

        cmd = [self.adb_path] + args

        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )

    def get_devices(self) -> list:
        """Lấy danh sách thiết bị"""
        result = self.run_adb(["devices"])

        devices = []
        lines = result.stdout.strip().split('\n')[1:]  # Bỏ header

        for line in lines:
            if line.strip():
                parts = line.split('\t')
                if len(parts) >= 2 and parts[1] == 'device':
                    devices.append(parts[0].strip())

        return devices

    def connect_emulator(self, port: int = 5554) -> bool:
        """Kết nối với emulator"""
        try:
            result = self.run_adb(["connect", f"127.0.0.1:{port}"])
            return "connected" in result.stdout.lower()
        except:
            return False

    def restart_server(self):
        """Khởi động lại ADB server"""
        try:
            self.run_adb(["kill-server"])
            self.run_adb(["start-server"], timeout=10)
            return True
        except:
            return False

    def get_ldplayer_names(self):
        """Lấy danh sách tên LDPlayer đang chạy"""
        try:
            # Tìm ldconsole path
            ldconsole_paths = [
                r"D:\LDPlayer\LDPlayer9\ldconsole.exe",
                r"D:\LDPlayer\LDPlayer4\ldconsole.exe",
                r"C:\LDPlayer\LDPlayer9\ldconsole.exe",
                r"C:\LDPlayer\LDPlayer4\ldconsole.exe",
                r"C:\Program Files\LDPlayer\LDPlayer9\ldconsole.exe",
                r"C:\Program Files\LDPlayer\LDPlayer4\ldconsole.exe",
            ]

            ldconsole_path = None
            for path in ldconsole_paths:
                if os.path.exists(path):
                    ldconsole_path = path
                    break

            if ldconsole_path:
                # Chạy ldconsole runninglist để lấy LDPlayer đang chạy
                result = subprocess.run(
                    [ldconsole_path, "runninglist"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                    encoding='utf-8',
                    errors='ignore'
                )

                # Parse - mỗi dòng 1 tên
                names = []
                for line in result.stdout.strip().split('\n'):
                    name = line.strip()
                    if name:
                        names.append(name)
                return names

            return []
        except:
            return []

    def get_device_name(self, serial: str) -> str:
        """Lấy tên LDPlayer từ serial"""
        try:
            # Cache danh sách tên LDPlayer (gọi 1 lần cho tất cả devices)
            if not hasattr(self, '_ldplayer_names'):
                self._ldplayer_names = self.get_ldplayer_names()
                self._device_name_map = {}

            # Nếu đã map rồi thì return
            if serial in self._device_name_map:
                return self._device_name_map[serial]

            # Lấy danh sách devices hiện tại
            devices = self.get_devices()

            # Map theo thứ tự: device thứ i -> tên thứ i
            for i, dev_serial in enumerate(devices):
                if i < len(self._ldplayer_names):
                    self._device_name_map[dev_serial] = self._ldplayer_names[i]
                else:
                    self._device_name_map[dev_serial] = f"LDPlayer ({dev_serial})"

            # Trả về tên đã map
            if serial in self._device_name_map:
                return self._device_name_map[serial]

            # Fallback
            return f"LDPlayer ({serial})"

        except Exception as e:
            return f"LDPlayer ({serial})"


# Singleton instance
_adb_helper = None

def get_adb_helper() -> ADBHelper:
    """Lấy ADB Helper instance"""
    global _adb_helper
    if _adb_helper is None:
        _adb_helper = ADBHelper()
    return _adb_helper


if __name__ == "__main__":
    # Test
    helper = ADBHelper()

    print("\n" + "="*50)
    print("ADB Helper Test")
    print("="*50)

    if helper.adb_path:
        print(f"\n[OK] ADB Path: {helper.adb_path}")

        devices = helper.get_devices()
        print(f"\n[INFO] Devices: {len(devices)}")
        for device in devices:
            name = helper.get_device_name(device)
            print(f"  - {device} -> {name}")
    else:
        print("\n[ERROR] Khong tim thay ADB")
