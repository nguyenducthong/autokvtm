"""
GUI chọn thiết bị LDPlayer
Tự động quét các thiết bị đang kết nối và cho phép chọn
"""

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import json
import os
from typing import List, Dict
from core.adb_helper import get_adb_helper

class DeviceSelector:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Chọn LDPlayer - Auto Khu Vườn Trên Mây")
        self.root.geometry("600x400")
        self.root.resizable(False, False)

        self.selected_device = None
        self.devices = []
        self.config_file = "selected_device.json"
        self.adb_helper = get_adb_helper()

        self.setup_ui()
        self.scan_devices()

    def setup_ui(self):
        """Thiết lập giao diện"""
        # Menu bar
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="📁 File", menu=file_menu)
        file_menu.add_command(label="Làm mới danh sách", command=self.scan_devices, accelerator="F5")
        file_menu.add_command(label="Xóa thiết bị đã lưu", command=self.clear_saved_device)
        file_menu.add_separator()
        file_menu.add_command(label="Thoát", command=self.root.quit, accelerator="Alt+F4")

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="🔧 Công cụ", menu=tools_menu)
        tools_menu.add_command(label="Kiểm tra ADB", command=self.check_adb)
        tools_menu.add_command(label="Khởi động lại ADB Server", command=self.restart_adb_server)
        tools_menu.add_command(label="Xem thông tin thiết bị", command=self.show_device_info)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="❓ Trợ giúp", menu=help_menu)
        help_menu.add_command(label="Hướng dẫn", command=self.show_help)
        help_menu.add_command(label="Về phần mềm", command=self.show_about)

        # Bind F5 key
        self.root.bind('<F5>', lambda _: self.scan_devices())

        # Header
        header_frame = tk.Frame(self.root, bg="#2c3e50", height=60)
        header_frame.pack(fill=tk.X)

        title_label = tk.Label(
            header_frame,
            text="🎮 CHỌN LDPLAYER",
            font=("Arial", 16, "bold"),
            fg="white",
            bg="#2c3e50"
        )
        title_label.pack(pady=15)

        # Main content
        content_frame = tk.Frame(self.root, bg="#ecf0f1")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Instruction
        instruction = tk.Label(
            content_frame,
            text="Chọn thiết bị LDPlayer bạn muốn điều khiển:",
            font=("Arial", 10),
            bg="#ecf0f1"
        )
        instruction.pack(anchor=tk.W, pady=(0, 10))

        # Device list frame
        list_frame = tk.Frame(content_frame, bg="white", relief=tk.SUNKEN, bd=1)
        list_frame.pack(fill=tk.BOTH, expand=True)

        # Scrollbar
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Listbox
        self.device_listbox = tk.Listbox(
            list_frame,
            font=("Consolas", 10),
            yscrollcommand=scrollbar.set,
            selectmode=tk.SINGLE,
            height=10,
            bg="white",
            selectbackground="#3498db",
            selectforeground="white"
        )
        self.device_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.config(command=self.device_listbox.yview)

        # Bind double-click và Enter
        self.device_listbox.bind('<Double-Button-1>', lambda _: self.select_device())
        self.device_listbox.bind('<Return>', lambda _: self.select_device())

        # Button frame
        button_frame = tk.Frame(content_frame, bg="#ecf0f1")
        button_frame.pack(fill=tk.X, pady=(10, 0))

        # Refresh button
        refresh_btn = tk.Button(
            button_frame,
            text="🔄 Làm mới",
            command=self.scan_devices,
            font=("Arial", 10),
            bg="#95a5a6",
            fg="white",
            relief=tk.FLAT,
            padx=20,
            pady=8,
            cursor="hand2"
        )
        refresh_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Select button
        select_btn = tk.Button(
            button_frame,
            text="✓ Chọn thiết bị",
            command=self.select_device,
            font=("Arial", 10, "bold"),
            bg="#27ae60",
            fg="white",
            relief=tk.FLAT,
            padx=20,
            pady=8,
            cursor="hand2"
        )
        select_btn.pack(side=tk.RIGHT)

        # Status bar
        self.status_label = tk.Label(
            self.root,
            text="Đang quét thiết bị...",
            font=("Arial", 9),
            bg="#34495e",
            fg="white",
            anchor=tk.W,
            padx=10
        )
        self.status_label.pack(fill=tk.X, side=tk.BOTTOM)

    def scan_devices(self):
        """Quét các thiết bị ADB đang kết nối"""
        self.device_listbox.delete(0, tk.END)
        self.devices = []
        self.status_label.config(text="Đang quét thiết bị...")
        self.root.update()

        try:
            # Kiểm tra ADB có tồn tại không
            if not self.adb_helper.adb_path:
                raise FileNotFoundError("Không tìm thấy ADB")

            # Chạy lệnh adb devices bằng ADB Helper
            result = self.adb_helper.run_adb(["devices"], timeout=15)

            lines = result.stdout.strip().split('\n')[1:]  # Bỏ dòng header

            for line in lines:
                if line.strip():
                    parts = line.split('\t')
                    if len(parts) >= 2 and parts[1] == 'device':
                        serial = parts[0].strip()
                        self.devices.append({
                            'serial': serial,
                            'name': self.get_device_name(serial)
                        })

            # Hiển thị danh sách
            if self.devices:
                for idx, device in enumerate(self.devices, 1):
                    display_text = f"{idx}. {device['name']} ({device['serial']})"
                    self.device_listbox.insert(tk.END, display_text)

                self.status_label.config(text=f"✓ Tìm thấy {len(self.devices)} thiết bị")

                # Tự động chọn thiết bị đã lưu
                self.load_saved_selection()
            else:
                self.status_label.config(text="⚠ Không tìm thấy thiết bị nào!")
                messagebox.showwarning(
                    "Không có thiết bị",
                    "Không tìm thấy thiết bị LDPlayer nào!\n\n"
                    "Hãy đảm bảo:\n"
                    "1. LDPlayer đang chạy\n"
                    "2. ADB đã được kích hoạt trong LDPlayer Settings\n"
                    "3. Thử khởi động lại ADB Server (menu Công cụ)"
                )

        except FileNotFoundError:
            self.status_label.config(text="✗ Lỗi: Không tìm thấy ADB")
            messagebox.showerror(
                "Lỗi ADB",
                f"Không tìm thấy ADB!\n\n"
                f"Đã tìm ở: {self.adb_helper.adb_path}\n\n"
                f"Hãy đảm bảo LDPlayer đã được cài đặt."
            )
        except subprocess.TimeoutExpired:
            self.status_label.config(text="✗ Timeout khi quét thiết bị")
            messagebox.showerror("Timeout", "Quá trình quét thiết bị bị timeout!")
        except Exception as e:
            self.status_label.config(text=f"✗ Lỗi: {str(e)}")
            messagebox.showerror("Lỗi", f"Có lỗi xảy ra: {str(e)}")

    def get_device_name(self, serial: str) -> str:
        """Lấy tên thiết bị từ serial"""
        # Dùng ADB Helper để lấy tên LDPlayer
        return self.adb_helper.get_device_name(serial)

    def select_device(self):
        """Xử lý khi người dùng chọn thiết bị"""
        selection = self.device_listbox.curselection()

        if not selection:
            messagebox.showwarning("Chưa chọn", "Vui lòng chọn một thiết bị!")
            return

        idx = selection[0]
        selected = self.devices[idx]

        # Lưu lựa chọn
        self.save_selection(selected)

        # Hiển thị thông báo
        messagebox.showinfo(
            "Đã chọn thiết bị",
            f"Đã chọn: {selected['name']}\n"
            f"Serial: {selected['serial']}\n\n"
            f"Thiết bị này sẽ được sử dụng cho các lần chạy tiếp theo."
        )

        self.selected_device = selected
        self.root.quit()
        self.root.destroy()

    def save_selection(self, device: Dict):
        """Lưu lựa chọn vào file"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(device, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Lỗi khi lưu config: {e}")

    def load_saved_selection(self):
        """Tự động chọn thiết bị đã lưu"""
        if not os.path.exists(self.config_file):
            return

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                saved = json.load(f)

            # Tìm thiết bị trong danh sách hiện tại
            for idx, device in enumerate(self.devices):
                if device['serial'] == saved['serial']:
                    self.device_listbox.selection_set(idx)
                    self.device_listbox.see(idx)
                    self.status_label.config(text=f"✓ Đã chọn: {device['name']}")
                    break
        except Exception as e:
            print(f"Lỗi khi load config: {e}")

    def clear_saved_device(self):
        """Xóa thiết bị đã lưu"""
        if os.path.exists(self.config_file):
            try:
                os.remove(self.config_file)
                messagebox.showinfo(
                    "Đã xóa",
                    "Đã xóa thiết bị đã lưu.\n"
                    "Lần chạy tiếp theo bạn sẽ cần chọn lại thiết bị."
                )
                self.status_label.config(text="✓ Đã xóa thiết bị đã lưu")
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể xóa file: {e}")
        else:
            messagebox.showinfo("Thông báo", "Chưa có thiết bị nào được lưu.")

    def check_adb(self):
        """Kiểm tra ADB có hoạt động không"""
        try:
            result = subprocess.run(
                ["adb", "version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            version = result.stdout.strip().split('\n')[0]
            messagebox.showinfo(
                "✓ ADB hoạt động tốt",
                f"{version}\n\n"
                f"ADB đang hoạt động bình thường."
            )
        except FileNotFoundError:
            messagebox.showerror(
                "✗ Không tìm thấy ADB",
                "ADB chưa được cài đặt hoặc chưa thêm vào PATH!\n\n"
                "Hãy cài đặt Android SDK Platform Tools."
            )
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi khi kiểm tra ADB: {e}")

    def restart_adb_server(self):
        """Khởi động lại ADB Server"""
        self.status_label.config(text="Đang khởi động lại ADB Server...")
        self.root.update()

        try:
            # Kill server
            subprocess.run(["adb", "kill-server"], timeout=5)
            # Start server
            subprocess.run(["adb", "start-server"], timeout=10)

            messagebox.showinfo(
                "✓ Thành công",
                "Đã khởi động lại ADB Server.\n\n"
                "Bấm OK để quét lại thiết bị."
            )
            self.scan_devices()
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể khởi động lại ADB: {e}")
            self.status_label.config(text="✗ Lỗi khi khởi động lại ADB")

    def show_device_info(self):
        """Hiển thị thông tin chi tiết của thiết bị được chọn"""
        selection = self.device_listbox.curselection()

        if not selection:
            messagebox.showwarning("Chưa chọn", "Vui lòng chọn một thiết bị để xem thông tin!")
            return

        idx = selection[0]
        device = self.devices[idx]

        try:
            # Lấy thông tin thiết bị
            model = subprocess.run(
                ["adb", "-s", device['serial'], "shell", "getprop", "ro.product.model"],
                capture_output=True, text=True, timeout=3
            ).stdout.strip()

            manufacturer = subprocess.run(
                ["adb", "-s", device['serial'], "shell", "getprop", "ro.product.manufacturer"],
                capture_output=True, text=True, timeout=3
            ).stdout.strip()

            android_version = subprocess.run(
                ["adb", "-s", device['serial'], "shell", "getprop", "ro.build.version.release"],
                capture_output=True, text=True, timeout=3
            ).stdout.strip()

            sdk_version = subprocess.run(
                ["adb", "-s", device['serial'], "shell", "getprop", "ro.build.version.sdk"],
                capture_output=True, text=True, timeout=3
            ).stdout.strip()

            info = (
                f"📱 Thông tin thiết bị\n"
                f"{'='*40}\n\n"
                f"Tên: {device['name']}\n"
                f"Serial: {device['serial']}\n"
                f"Model: {model}\n"
                f"Nhà sản xuất: {manufacturer}\n"
                f"Android: {android_version} (API {sdk_version})\n"
            )

            messagebox.showinfo("Thông tin thiết bị", info)

        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể lấy thông tin thiết bị: {e}")

    def show_help(self):
        """Hiển thị hướng dẫn"""
        help_text = """
🎮 HƯỚNG DẪN SỬ DỤNG

1️⃣ Chọn thiết bị:
   - Click vào thiết bị trong danh sách
   - Bấm "Chọn thiết bị" hoặc Enter

2️⃣ Làm mới danh sách:
   - Bấm nút "🔄 Làm mới"
   - Hoặc nhấn F5
   - Hoặc menu File > Làm mới danh sách

3️⃣ Xem thông tin:
   - Chọn thiết bị
   - Menu Công cụ > Xem thông tin thiết bị

4️⃣ Khắc phục sự cố:
   - Không thấy thiết bị?
     → Kiểm tra LDPlayer đã chạy chưa
     → Menu Công cụ > Khởi động lại ADB Server

   - ADB không hoạt động?
     → Menu Công cụ > Kiểm tra ADB

📌 Phím tắt:
   F5: Làm mới danh sách
   Alt+F4: Thoát
        """
        messagebox.showinfo("Hướng dẫn", help_text)

    def show_about(self):
        """Hiển thị thông tin về phần mềm"""
        about_text = """
╔══════════════════════════════════╗
║  AUTO KHU VƯỜN TRÊN MÂY         ║
║  LDPlayer Device Selector        ║
╚══════════════════════════════════╝

Version: 1.0.0
Build: 2026.01

✨ Tính năng:
• Tự động quét thiết bị LDPlayer
• Lưu lựa chọn tự động
• Quản lý nhiều thiết bị
• Giao diện thân thiện

🛠️ Công nghệ:
• Python 3.7+
• Tkinter GUI
• ADB (Android Debug Bridge)

📧 Hỗ trợ:
Nếu gặp vấn đề, hãy kiểm tra:
1. LDPlayer đã chạy chưa
2. ADB đã cài đặt chưa
3. Đường dẫn ADB trong PATH

© 2026 - Auto KVTM Team
        """
        messagebox.showinfo("Về phần mềm", about_text)

    def run(self) -> Dict:
        """Chạy GUI và trả về thiết bị được chọn"""
        self.root.mainloop()
        return self.selected_device


def get_selected_device(force_select=False) -> str:
    """
    Hàm tiện ích để lấy serial thiết bị đã chọn
    Trả về serial string hoặc mở GUI nếu chưa có

    Args:
        force_select: Nếu True, bắt buộc hiển thị GUI chọn thiết bị (không dùng cache)
    """
    config_file = "selected_device.json"

    # Nếu không force, thử đọc từ file
    if not force_select and os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                device = json.load(f)
                return device['serial']
        except:
            pass

    # Nếu chưa có hoặc force_select, mở GUI
    selector = DeviceSelector()
    device = selector.run()

    if device:
        return device['serial']
    else:
        # Không có thiết bị nào được chọn
        raise Exception("Chưa chọn thiết bị! Vui lòng chọn thiết bị LDPlayer để tiếp tục.")


def clear_selected_device():
    """Xóa thiết bị đã lưu"""
    config_file = "selected_device.json"
    if os.path.exists(config_file):
        os.remove(config_file)


if __name__ == "__main__":
    # Test
    selector = DeviceSelector()
    device = selector.run()

    if device:
        print(f"\n✓ Đã chọn: {device['name']}")
        print(f"  Serial: {device['serial']}")
    else:
        print("\n✗ Không chọn thiết bị")
