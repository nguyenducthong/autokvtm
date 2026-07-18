import os
import json
import subprocess
from typing import Optional
import glob
import csv

class ADBHelper:
    """Tìm và quản lý ADB của LDPlayer"""

    def __init__(self):
        self.adb_path = None
        self.ldplayer_dir = None
        self.adb_path = self.find_adb()

    @staticmethod
    def _hidden_subprocess_kwargs():
        if os.name != "nt":
            return {}
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        return {
            "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
            "startupinfo": startupinfo,
        }

    def find_adb(self) -> Optional[str]:
        """Tìm đường dẫn ADB bằng cách tìm thư mục LDPlayer."""

        # Thử tìm ADB trong PATH
        try:
            result = subprocess.run(
                ["adb", "version"],
                capture_output=True,
                text=True,
                timeout=2,
                **self._hidden_subprocess_kwargs()
            )
            if result.returncode == 0:
                print("[OK] Tim thay ADB trong PATH")
                return "adb"
        except:
            pass

        # Thử dùng đường dẫn ADB đã lưu trong cấu hình
        saved_path = self._load_saved_adb_path()
        if saved_path:
            print(f"[OK] Sử dụng ADB từ cấu hình: {saved_path}")
            return saved_path

        # Thử tìm thư mục LDPlayer và dùng adb.exe trong đó
        ldplayer_dir = self._find_ldplayer_dir()
        if ldplayer_dir:
            adb_path = os.path.join(ldplayer_dir, "adb.exe")
            if os.path.isfile(adb_path):
                self.ldplayer_dir = ldplayer_dir
                print(f"[OK] Tim thay ADB trong LDPlayer: {adb_path}")
                return adb_path

        # Không tìm thấy
        print("[ERROR] Khong tim thay ADB!")
        return None

    def _load_saved_adb_path(self) -> Optional[str]:
        config_file = "selected_device.json"
        if not os.path.isfile(config_file):
            return None
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                saved = json.load(f)

            ldplayer_dir = saved.get("ldplayer_dir")
            if ldplayer_dir and os.path.isdir(ldplayer_dir):
                self.ldplayer_dir = ldplayer_dir  # Lưu lại để dùng sau
                adb_path = os.path.join(ldplayer_dir, "adb.exe")
                if os.path.isfile(adb_path):
                    return adb_path

            path = saved.get("adb_path")
            if path:
                if os.path.isdir(path):
                    adb_path = os.path.join(path, "adb.exe")
                    if os.path.isfile(adb_path):
                        return adb_path
                elif os.path.isfile(path) and os.path.basename(path).lower() == "adb.exe":
                    return path
        except Exception:
            pass
        return None

    def run_adb(self, args: list, timeout: int = 5) -> subprocess.CompletedProcess:
        """Chạy lệnh ADB"""
        if not self.adb_path:
            raise FileNotFoundError("Không tìm thấy ADB! Vui lòng cài đặt LDPlayer.")

        cmd = [self.adb_path] + args

        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            **self._hidden_subprocess_kwargs()
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

    def get_ldplayers(self) -> list:
        """Lay tat ca LDPlayer instance, ke ca instance chua start."""
        running_serials = set()
        try:
            running_serials = set(self.get_devices())
        except Exception:
            running_serials = set()

        players_by_index = {}
        for player in self._get_ldplayers_from_config(running_serials):
            players_by_index[player["index"]] = player

        # ldconsole list2 co may ban chi tra instance da tung mo, nen chi dung de bo sung/ghi de ten.
        for player in self._get_ldplayers_from_console(running_serials):
            current = players_by_index.get(player["index"])
            if current:
                current.update({
                    "name": current["name"] or player["name"],
                    "running": player["running"],
                    "serial": player["serial"],
                    "adb_port": player["adb_port"],
                })
            else:
                players_by_index[player["index"]] = player

        self._apply_ldplayer_isrunning(players_by_index)
        players = list(players_by_index.values())

        if not players:
            for serial in sorted(running_serials):
                players.append({
                    "index": None,
                    "name": self.get_device_name(serial),
                    "serial": serial,
                    "running": True,
                    "adb_port": None,
                })

        return sorted(players, key=lambda p: (p["index"] is None, p["index"] if p["index"] is not None else 9999, p["name"]))

    def _make_ldplayer_info(self, idx: int, name: str, running_serials: set, running_override=None) -> dict:
        port = 5555 + 2 * idx
        serial_emu = f"emulator-{port - 1}"
        serial_ip = f"127.0.0.1:{port}"
        running = serial_emu in running_serials or serial_ip in running_serials
        if running_override is not None:
            running = running_override
        serial = serial_emu if serial_emu in running_serials else serial_ip if serial_ip in running_serials else serial_emu
        return {
            "index": idx,
            "name": name or f"LDPlayer-{idx}",
            "serial": serial,
            "running": running,
            "adb_port": port,
        }

    def _get_ldplayers_from_console(self, running_serials: set) -> list:
        console_path = self._find_ldconsole_path()
        if not console_path:
            return []
        try:
            result = subprocess.run(
                [console_path, "list2"],
                capture_output=True,
                text=True,
                timeout=8,
                **self._hidden_subprocess_kwargs()
            )
        except Exception:
            return []
        if result.returncode != 0:
            return []

        players = []
        for row in csv.reader(result.stdout.splitlines()):
            if len(row) < 2:
                continue
            try:
                idx = int(row[0])
            except ValueError:
                continue
            running = None
            if len(row) >= 7:
                try:
                    android_started = int(row[4])
                    pid = int(row[5])
                    vbox_pid = int(row[6])
                    running = android_started == 1 or pid > 0 or vbox_pid > 0
                except ValueError:
                    running = None
            players.append(self._make_ldplayer_info(idx, row[1].strip(), running_serials, running_override=running))
        return players

    def _apply_ldplayer_isrunning(self, players_by_index: dict):
        console_path = self._find_ldconsole_path()
        if not console_path:
            return
        for idx, player in players_by_index.items():
            if idx is None:
                continue
            try:
                result = subprocess.run(
                    [console_path, "isrunning", "--index", str(idx)],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    **self._hidden_subprocess_kwargs()
                )
            except Exception:
                continue
            status = (result.stdout or "").strip().lower()
            if "running" in status:
                player["running"] = True
            elif "stop" in status or "not" in status or status == "false":
                player["running"] = False

    def _get_ldplayers_from_config(self, running_serials: set) -> list:
        ld_dir = self._find_ldplayer_dir()
        players = []
        if ld_dir:
            config_dir = os.path.join(ld_dir, "vms", "config")
            for cfg_path in glob.glob(os.path.join(config_dir, "leidian*.config")):
                filename = os.path.basename(cfg_path)
                idx_str = filename.replace("leidian", "").replace(".config", "")
                try:
                    idx = int(idx_str)
                except ValueError:
                    continue

                name = f"LDPlayer-{idx}"
                try:
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    status_settings = cfg.get("statusSettings")
                    if isinstance(status_settings, dict):
                        name = status_settings.get("playerName") or name
                    else:
                        name = cfg.get("statusSettings.playerName") or name
                except Exception:
                    pass
                players.append(self._make_ldplayer_info(idx, name, running_serials))
        return players

    def _find_ldconsole_path(self) -> Optional[str]:
        ld_dir = self._find_ldplayer_dir()
        candidates = []
        if ld_dir:
            candidates.extend([
                os.path.join(ld_dir, "ldconsole.exe"),
                os.path.join(ld_dir, "dnconsole.exe"),
            ])
        if self.adb_path and os.path.isabs(self.adb_path):
            adb_dir = os.path.dirname(self.adb_path)
            candidates.extend([
                os.path.join(adb_dir, "ldconsole.exe"),
                os.path.join(adb_dir, "dnconsole.exe"),
            ])
        for path in candidates:
            if os.path.isfile(path):
                return path
        return None

    def start_ldplayer(self, index: int = None, name: str = None) -> bool:
        """Start LDPlayer instance bang ldconsole/dnconsole."""
        console_path = self._find_ldconsole_path()
        if not console_path:
            raise FileNotFoundError("Khong tim thay ldconsole.exe/dnconsole.exe")
        if index is not None:
            args = [console_path, "launch", "--index", str(index)]
        elif name:
            args = [console_path, "launch", "--name", name]
        else:
            raise ValueError("Can index hoac name de start LDPlayer")

        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         **self._hidden_subprocess_kwargs())
        return True

    def stop_ldplayer(self, index: int = None, name: str = None) -> bool:
        """Stop LDPlayer instance bang ldconsole/dnconsole."""
        console_path = self._find_ldconsole_path()
        if not console_path:
            raise FileNotFoundError("Khong tim thay ldconsole.exe/dnconsole.exe")
        if index is not None:
            args = [console_path, "quit", "--index", str(index)]
        elif name:
            args = [console_path, "quit", "--name", name]
        else:
            raise ValueError("Can index hoac name de stop LDPlayer")

        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         **self._hidden_subprocess_kwargs())
        return True

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


    def _find_ldplayer_dir(self):
        
        """Tìm thư mục cài đặt LDPlayer."""
        if self.ldplayer_dir and os.path.isdir(self.ldplayer_dir):
            return self.ldplayer_dir
        candidates = []

        # Các đường dẫn LDPlayer thường gặp
        candidates.extend([
            r"D:\LDPlayer\LDPlayer9",
            r"D:\LDPlayer\LDPlayer4",
            r"C:\LDPlayer\LDPlayer9",
            r"C:\LDPlayer\LDPlayer4",
            r"C:\Program Files\LDPlayer\LDPlayer9",
            r"C:\Program Files\LDPlayer\LDPlayer4",
            r"C:\Program Files (x86)\LDPlayer\LDPlayer9",
            r"C:\Program Files (x86)\LDPlayer\LDPlayer4",
            r"C:\Program Files\LDPlayer",
            r"C:\Program Files (x86)\LDPlayer",
            r"D:\LDPlayer",
            r"C:\LDPlayer",
        ])

        # Thử dựng từ adb_path nếu đã biết
        adb_path_value = getattr(self, 'adb_path', None)
        print(f"[DEBUG] adb_path_value: {adb_path_value}")
        if isinstance(adb_path_value, str) and os.path.isabs(adb_path_value):
            adb_parent = os.path.dirname(adb_path_value)
            if os.path.isdir(adb_parent):
                candidates.insert(0, adb_parent)
        
        # print(f"[DEBUG] Candidates after adding from adb_path: {candidates}")
        # Duyệt qua các ứng cử viên
        for d in candidates:
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
        print(f"[DEBUG] LDPlayer directory for building name map: {ld_dir}")
        if not ld_dir:
            # Nếu không tìm thấy thư mục LDPlayer, thử lấy từ adb_path
            if self.adb_path and os.path.isabs(self.adb_path):
                adb_dir = os.path.dirname(self.adb_path)
                if os.path.isdir(adb_dir):
                    ld_dir = adb_dir
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
