"""
GUI Menu chính - Auto Khu Vườn Trên Mây
Giao diện chính với các chức năng
"""

import tkinter as tk
from tkinter import ttk, messagebox
from gui_select_device import DeviceSelector, get_selected_device
from core.adb import ADBController
from config import WAREHOUSE_ITEM_KSK, CONFIG_TEMP_TC
from core.ban_do import dat_vp
import threading
import os

class MainGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Auto Khu Vườn Trên Mây")
        self.root.geometry("800x600")
        self.root.resizable(True, True)

        self.current_device = None
        self.adb = None
        self.is_running = False

        self.setup_ui()
        self.load_device()

    def setup_ui(self):
        """Thiết lập giao diện"""
        # Menu bar
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="📁 File", menu=file_menu)
        file_menu.add_command(label="Chọn thiết bị", command=self.select_device)
        file_menu.add_separator()
        file_menu.add_command(label="Thoát", command=self.on_closing, accelerator="Alt+F4")

        # Chức năng menu
        function_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="🎮 Chức năng", menu=function_menu)
        function_menu.add_command(label="Đặt vật phẩm vào kho", command=self.open_warehouse_window)
        function_menu.add_command(label="Thu hoạch", command=self.thu_hoach)
        function_menu.add_command(label="Trồng cây", command=self.trong_cay)
        function_menu.add_separator()
        function_menu.add_command(label="📸 Screenshot Tool", command=self.open_screenshot_tool)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="❓ Trợ giúp", menu=help_menu)
        help_menu.add_command(label="Hướng dẫn", command=self.show_help)
        help_menu.add_command(label="Về phần mềm", command=self.show_about)

        # Header
        header_frame = tk.Frame(self.root, bg="#2c3e50", height=80)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        title_label = tk.Label(
            header_frame,
            text="🌳 AUTO KHU VƯỜN TRÊN MÂY",
            font=("Arial", 20, "bold"),
            fg="white",
            bg="#2c3e50"
        )
        title_label.pack(pady=20)

        # Device info bar
        device_frame = tk.Frame(self.root, bg="#34495e", height=40)
        device_frame.pack(fill=tk.X)
        device_frame.pack_propagate(False)

        self.device_label = tk.Label(
            device_frame,
            text="📱 Thiết bị: Chưa chọn",
            font=("Arial", 10),
            fg="white",
            bg="#34495e",
            anchor=tk.W,
            padx=20
        )
        self.device_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        change_device_btn = tk.Button(
            device_frame,
            text="Đổi thiết bị",
            command=self.select_device,
            bg="#3498db",
            fg="white",
            relief=tk.FLAT,
            padx=15,
            cursor="hand2"
        )
        change_device_btn.pack(side=tk.RIGHT, padx=10, pady=5)

        # Main content
        content_frame = tk.Frame(self.root, bg="#ecf0f1")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Title
        tk.Label(
            content_frame,
            text="Chọn chức năng:",
            font=("Arial", 12, "bold"),
            bg="#ecf0f1"
        ).pack(anchor=tk.W, pady=(0, 15))

        # Function buttons
        button_config = [
            ("🏪 Đặt vật phẩm vào kho sự kiện", self.open_warehouse_window, "#27ae60"),
            ("🌾 Thu hoạch", self.thu_hoach, "#f39c12"),
            ("🌱 Trồng cây", self.trong_cay, "#e74c3c"),
            ("📸 Screenshot Tool - Chụp & Cắt ảnh", self.open_screenshot_tool, "#9b59b6"),
            ("⚙️ Cài đặt", self.open_settings, "#95a5a6"),
        ]

        for text, command, color in button_config:
            btn = tk.Button(
                content_frame,
                text=text,
                command=command,
                font=("Arial", 12),
                bg=color,
                fg="white",
                relief=tk.FLAT,
                padx=20,
                pady=15,
                cursor="hand2",
                anchor=tk.W
            )
            btn.pack(fill=tk.X, pady=5)

            # Hover effect
            btn.bind("<Enter>", lambda e, b=btn: b.config(relief=tk.RAISED))
            btn.bind("<Leave>", lambda e, b=btn: b.config(relief=tk.FLAT))

        # Log frame
        log_frame = tk.LabelFrame(
            content_frame,
            text="📋 Nhật ký hoạt động",
            font=("Arial", 10, "bold"),
            bg="#ecf0f1",
            padx=10,
            pady=10
        )
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(20, 0))

        # Scrollbar for log
        log_scroll = tk.Scrollbar(log_frame)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_text = tk.Text(
            log_frame,
            font=("Consolas", 9),
            bg="#2c3e50",
            fg="#ecf0f1",
            yscrollcommand=log_scroll.set,
            height=8,
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        log_scroll.config(command=self.log_text.yview)

        # Status bar
        self.status_label = tk.Label(
            self.root,
            text="✓ Sẵn sàng",
            font=("Arial", 9),
            bg="#27ae60",
            fg="white",
            anchor=tk.W,
            padx=10
        )
        self.status_label.pack(fill=tk.X, side=tk.BOTTOM)

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def log(self, message, level="INFO"):
        """Thêm log vào text area"""
        self.log_text.config(state=tk.NORMAL)

        # Color coding
        if level == "ERROR":
            tag = "error"
            self.log_text.tag_config("error", foreground="#e74c3c")
        elif level == "SUCCESS":
            tag = "success"
            self.log_text.tag_config("success", foreground="#27ae60")
        elif level == "WARNING":
            tag = "warning"
            self.log_text.tag_config("warning", foreground="#f39c12")
        else:
            tag = "info"
            self.log_text.tag_config("info", foreground="#ecf0f1")

        self.log_text.insert(tk.END, f"[{level}] {message}\n", tag)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def load_device(self):
        """Tự động load thiết bị đã lưu"""
        try:
            self.current_device = get_selected_device()
            self.device_label.config(text=f"📱 Thiết bị: {self.current_device}")
            self.adb = ADBController(serial=self.current_device)
            self.log(f"Đã kết nối thiết bị: {self.current_device}", "SUCCESS")
            self.status_label.config(text="✓ Đã kết nối thiết bị", bg="#27ae60")
        except Exception as e:
            self.log(f"Lỗi khi load thiết bị: {e}", "ERROR")
            self.status_label.config(text="✗ Chưa kết nối thiết bị", bg="#e74c3c")

    def select_device(self):
        """Mở GUI chọn thiết bị"""
        self.log("Đang mở GUI chọn thiết bị...", "INFO")
        selector = DeviceSelector()
        device = selector.run()

        if device:
            self.current_device = device['serial']
            self.device_label.config(text=f"📱 Thiết bị: {self.current_device}")
            self.adb = ADBController(serial=self.current_device)
            self.log(f"Đã chọn thiết bị: {device['name']} ({device['serial']})", "SUCCESS")
            self.status_label.config(text="✓ Đã kết nối thiết bị", bg="#27ae60")
        else:
            self.log("Hủy chọn thiết bị", "WARNING")

    def open_warehouse_window(self):
        """Mở cửa sổ chọn vật phẩm kho"""
        if not self.check_device():
            return

        # Tạo cửa sổ mới
        warehouse_window = tk.Toplevel(self.root)
        warehouse_window.title("Đặt vật phẩm vào kho sự kiện")
        warehouse_window.geometry("600x500")
        warehouse_window.transient(self.root)
        warehouse_window.grab_set()

        # Header
        header = tk.Frame(warehouse_window, bg="#2c3e50", height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header,
            text="🏪 CHỌN VẬT PHẨM",
            font=("Arial", 16, "bold"),
            fg="white",
            bg="#2c3e50"
        ).pack(pady=15)

        # Content
        content = tk.Frame(warehouse_window, bg="#ecf0f1", padx=20, pady=20)
        content.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            content,
            text="Chọn vật phẩm cần đặt vào kho:",
            font=("Arial", 10),
            bg="#ecf0f1"
        ).pack(anchor=tk.W, pady=(0, 10))

        # Listbox frame
        list_frame = tk.Frame(content, bg="white", relief=tk.SUNKEN, bd=1)
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        item_listbox = tk.Listbox(
            list_frame,
            font=("Arial", 10),
            yscrollcommand=scrollbar.set,
            selectmode=tk.SINGLE,
            bg="white",
            selectbackground="#3498db",
            selectforeground="white"
        )
        item_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.config(command=item_listbox.yview)

        # Thêm items
        for idx, item in enumerate(WAREHOUSE_ITEM_KSK):
            item_listbox.insert(tk.END, f"{idx + 1}. {item['name']}")

        # Số lần đặt
        count_frame = tk.Frame(content, bg="#ecf0f1")
        count_frame.pack(fill=tk.X, pady=(10, 0))

        tk.Label(
            count_frame,
            text="Số lần đặt:",
            font=("Arial", 10),
            bg="#ecf0f1"
        ).pack(side=tk.LEFT)

        count_spinbox = tk.Spinbox(
            count_frame,
            from_=1,
            to=100,
            width=10,
            font=("Arial", 10)
        )
        count_spinbox.pack(side=tk.LEFT, padx=10)
        count_spinbox.delete(0, tk.END)
        count_spinbox.insert(0, "10")

        # Buttons
        btn_frame = tk.Frame(content, bg="#ecf0f1")
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        def start_placing():
            selection = item_listbox.curselection()
            if not selection:
                messagebox.showwarning("Chưa chọn", "Vui lòng chọn vật phẩm!")
                return

            idx = selection[0]
            item = WAREHOUSE_ITEM_KSK[idx]
            count = int(count_spinbox.get())

            warehouse_window.destroy()
            self.execute_dat_vp(item, count)

        tk.Button(
            btn_frame,
            text="✓ Bắt đầu đặt",
            command=start_placing,
            font=("Arial", 10, "bold"),
            bg="#27ae60",
            fg="white",
            relief=tk.FLAT,
            padx=20,
            pady=8,
            cursor="hand2"
        ).pack(side=tk.RIGHT)

        tk.Button(
            btn_frame,
            text="✗ Hủy",
            command=warehouse_window.destroy,
            font=("Arial", 10),
            bg="#95a5a6",
            fg="white",
            relief=tk.FLAT,
            padx=20,
            pady=8,
            cursor="hand2"
        ).pack(side=tk.RIGHT, padx=(0, 10))

    def execute_dat_vp(self, item, count):
        """Thực hiện đặt vật phẩm"""
        self.log(f"Bắt đầu đặt {item['name']} x{count}", "INFO")
        self.status_label.config(text=f"⏳ Đang đặt {item['name']}...", bg="#f39c12")
        self.is_running = True

        def run():
            try:
                dat_vp(
                    item["path_warehouse_not_select"],
                    item["path_warehouse_select"],
                    item["path"],
                    count,
                    False,
                    self.adb
                )
                self.log(f"Đã đặt xong {item['name']} x{count}", "SUCCESS")
                self.status_label.config(text="✓ Hoàn thành", bg="#27ae60")
                messagebox.showinfo("Thành công", f"Đã đặt xong {item['name']} x{count}!")
            except Exception as e:
                self.log(f"Lỗi khi đặt {item['name']}: {e}", "ERROR")
                self.status_label.config(text="✗ Lỗi", bg="#e74c3c")
                messagebox.showerror("Lỗi", f"Có lỗi xảy ra:\n{e}")
            finally:
                self.is_running = False

        # Run in thread để không block UI
        thread = threading.Thread(target=run, daemon=True)
        thread.start()

    def thu_hoach(self):
        """Thu hoạch"""
        if not self.check_device():
            return

        self.log("Đang mở Auto Farm Tool...", "INFO")
        self.open_auto_farm()

    def trong_cay(self):
        """Trồng cây"""
        if not self.check_device():
            return

        self.log("Đang mở Auto Farm Tool...", "INFO")
        self.open_auto_farm()

    def open_auto_farm(self):
        """Mở Auto Farm GUI"""
        try:
            from gui_auto_farm import AutoFarmGUI
            self.log("Đang khởi động Auto Farm GUI...", "INFO")
            farm_gui = AutoFarmGUI()
            farm_gui.run()
        except Exception as e:
            self.log(f"Lỗi khi mở Auto Farm: {e}", "ERROR")
            messagebox.showerror("Lỗi", f"Không thể mở Auto Farm:\n{e}")

    def open_screenshot_tool(self):
        """Mở Screenshot Tool"""
        self.log("Đang mở Screenshot Tool...", "INFO")
        try:
            from gui_screenshot_tool import ScreenshotTool
            # Chạy trong cửa sổ mới
            tool = ScreenshotTool()
            tool.run()
        except Exception as e:
            self.log(f"Lỗi khi mở Screenshot Tool: {e}", "ERROR")
            messagebox.showerror("Lỗi", f"Không thể mở Screenshot Tool:\n{e}")

    def open_settings(self):
        """Mở cài đặt"""
        self.log("Mở cài đặt...", "INFO")
        messagebox.showinfo("Cài đặt", "Cài đặt sẽ có trong phiên bản tiếp theo!")

    def check_device(self):
        """Kiểm tra thiết bị đã kết nối chưa"""
        if not self.adb or not self.current_device:
            messagebox.showwarning(
                "Chưa kết nối thiết bị",
                "Vui lòng chọn thiết bị trước khi sử dụng chức năng này!"
            )
            self.select_device()
            return False
        return True

    def show_help(self):
        """Hiển thị hướng dẫn"""
        help_text = """
🎮 HƯỚNG DẪN SỬ DỤNG

1️⃣ Chọn thiết bị:
   - File > Chọn thiết bị
   - Hoặc nhấn nút "Đổi thiết bị"

2️⃣ Sử dụng chức năng:
   - Nhấn vào nút chức năng tương ứng
   - Làm theo hướng dẫn trên màn hình

3️⃣ Theo dõi:
   - Xem nhật ký hoạt động ở phần dưới
   - Thanh trạng thái hiển thị trạng thái hiện tại

📌 Lưu ý:
   - Đảm bảo LDPlayer đang chạy
   - Không tắt ứng dụng khi đang thực hiện chức năng
        """
        messagebox.showinfo("Hướng dẫn", help_text)

    def show_about(self):
        """Hiển thị thông tin về phần mềm"""
        about_text = """
╔══════════════════════════════════╗
║  AUTO KHU VƯỜN TRÊN MÂY         ║
║  Main Application GUI            ║
╚══════════════════════════════════╝

Version: 1.0.0
Build: 2026.01

✨ Tính năng:
• Đặt vật phẩm vào kho tự động
• Thu hoạch tự động
• Trồng cây tự động
• Giao diện thân thiện

🛠️ Công nghệ:
• Python 3.7+
• Tkinter GUI
• ADB (Android Debug Bridge)
• Multi-threading

© 2026 - Auto KVTM Team
        """
        messagebox.showinfo("Về phần mềm", about_text)

    def on_closing(self):
        """Xử lý khi đóng cửa sổ"""
        if self.is_running:
            if messagebox.askyesno("Xác nhận", "Chức năng đang chạy. Bạn có chắc muốn thoát?"):
                self.root.destroy()
        else:
            self.root.destroy()

    def run(self):
        """Chạy ứng dụng"""
        self.root.mainloop()


if __name__ == "__main__":
    app = MainGUI()
    app.run()
