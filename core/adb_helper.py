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
        result = self.run_adb(["devices"], timeout=15)

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

    def _find_ldconsole(self):
        """Tìm đường dẫn ldconsole.exe"""
        ldconsole_paths = [
            r"D:\LDPlayer\LDPlayer9\ldconsole.exe",
            r"D:\LDPlayer\LDPlayer4\ldconsole.exe",
            r"C:\LDPlayer\LDPlayer9\ldconsole.exe",
            r"C:\LDPlayer\LDPlayer4\ldconsole.exe",
            r"C:\Program Files\LDPlayer\LDPlayer9\ldconsole.exe",
            r"C:\Program Files\LDPlayer\LDPlayer4\ldconsole.exe",
        ]
        for path in ldconsole_paths:
            if os.path.exists(path):
                return path
        return None

    def _find_ldplayer_dir(self):
        """Tìm thư mục cài đặt LDPlayer"""
        dirs = [
            r"D:\LDPlayer\LDPlayer9",
            r"D:\LDPlayer\LDPlayer4",
            r"C:\LDPlayer\LDPlayer9",
            r"C:\LDPlayer\LDPlayer4",
            r"C:\Program Files\LDPlayer\LDPlayer9",
            r"C:\Program Files\LDPlayer\LDPlayer4",
        ]
        for d in dirs:
            if os.path.isdir(d):
                return d
        return None

    def _build_serial_name_map(self):
        """Đọc tên LDPlayer từ file config (statusSettings.playerName).

        File: {ldplayer_dir}/vms/config/leidian{index}.config (JSON)
        ADB port cho instance index N = 5555 + 2*N
        Serial = emulator-{port-1}  hoặc  127.0.0.1:{port}
        """
        self._device_name_map = {}
        ld_dir = self._find_ldplayer_dir()
        if not ld_dir:
            return

        config_dir = os.path.join(ld_dir, "vms", "config")
        if not os.path.isdir(config_dir):
            return

        import json as _json
        import glob as _glob

        for cfg_path in _glob.glob(os.path.join(config_dir, "leidian*.config")):
            filename = os.path.basename(cfg_path)
            # leidian4.config -> index 4
            idx_str = filename.replace("leidian", "").replace(".config", "")
            try:
                idx = int(idx_str)
            except ValueError:
                continue

            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = _json.load(f)
                name = cfg.get("statusSettings.playerName", "")
                if not name:
                    name = f"LDPlayer-{idx}"
            except Exception:
                name = f"LDPlayer-{idx}"

            port = 5555 + 2 * idx
            serial_emu = f"emulator-{port - 1}"
            serial_ip = f"127.0.0.1:{port}"
            self._device_name_map[serial_emu] = name
            self._device_name_map[serial_ip] = name

    def get_ldplayer_names(self):
        """Lấy danh sách tên LDPlayer đang chạy"""
        ldconsole = self._find_ldconsole()
        if not ldconsole:
            return []
        try:
            result = subprocess.run(
                [ldconsole, "list2"],
                capture_output=True,
                timeout=10,
                encoding='utf-8',
                errors='replace'
            )
            names = []
            for line in result.stdout.strip().split('\n'):
                line = line.strip()
                if not line:
                    continue
                parts = line.split(',')
                if len(parts) >= 5 and parts[4] == '1':
                    names.append(parts[1])
            return names
        except Exception:
            return []

    def get_device_name(self, serial: str) -> str:
        """Lấy tên LDPlayer từ serial ADB"""
        if not hasattr(self, '_device_name_map') or not self._device_name_map:
            self._build_serial_name_map()

        if serial in self._device_name_map:
            return self._device_name_map[serial]

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
