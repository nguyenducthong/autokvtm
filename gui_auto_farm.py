"""
GUI Auto Farm - Giao diện điều khiển tự động farm
"""

import tkinter as tk
from tkinter import ttk, messagebox
from core.auto_farm import AutoFarm, SmartFarm
from core.adb import ADBController
from gui_select_device import get_selected_device
import threading
import time
import cv2
from PIL import Image, ImageTk
import numpy as np
from core.image_detection import ImageDetector


class AutoFarmGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Auto Farm - Thu hoạch & Trồng cây")
        self.root.geometry("700x650")
        self.root.resizable(False, False)

        self.device_serial = None
        self.adb = None
        self.farm_bot = None
        self.is_running = False
        self.stop_flag = False  # Cờ để dừng auto

        # Positions
        self.seed_icon_pos = None
        self.basket_pos = None

        # Screenshot window
        self.screenshot_window = None
        self.screenshot_img = None
        self.canvas = None
        self.selecting_for = None  # "basket" hoặc "seed"

        # Image detector
        self.image_detector = ImageDetector(threshold=0.7)

        self.setup_ui()
        self.load_device()

    def setup_ui(self):
        """Thiết lập giao diện"""
        # Header
        header = tk.Frame(self.root, bg="#2c3e50", height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header,
            text="🌾 AUTO FARM - THU HOẠCH & TRỒNG CÂY",
            font=("Arial", 14, "bold"),
            fg="white",
            bg="#2c3e50"
        ).pack(pady=15)

        # Device bar
        device_bar = tk.Frame(self.root, bg="#34495e", height=35)
        device_bar.pack(fill=tk.X)
        device_bar.pack_propagate(False)

        self.device_label = tk.Label(
            device_bar,
            text="📱 Thiết bị: Chưa kết nối",
            font=("Arial", 9),
            bg="#34495e",
            fg="white",
            padx=10
        )
        self.device_label.pack(side=tk.LEFT)

        # Nút chọn lại thiết bị
        tk.Button(
            device_bar,
            text="🔄 Chọn lại",
            command=self.select_device,
            bg="#3498db",
            fg="white",
            font=("Arial", 8),
            relief=tk.FLAT,
            cursor="hand2",
            padx=10,
            pady=2
        ).pack(side=tk.RIGHT, padx=5)

        # Main content
        content = tk.Frame(self.root, bg="#ecf0f1", padx=20, pady=15)
        content.pack(fill=tk.BOTH, expand=True)

        # Row selection
        row_frame = tk.LabelFrame(
            content,
            text="🎯 Chọn hàng cây",
            font=("Arial", 10, "bold"),
            bg="#ecf0f1",
            padx=10,
            pady=10
        )
        row_frame.pack(fill=tk.X, pady=(0, 10))

        self.row_vars = {}
        row_grid = tk.Frame(row_frame, bg="#ecf0f1")
        row_grid.pack()

        for i in range(1, 5):
            var = tk.BooleanVar(value=True)
            self.row_vars[i] = var

            cb = tk.Checkbutton(
                row_grid,
                text=f"Hàng {i}",
                variable=var,
                font=("Arial", 10),
                bg="#ecf0f1",
                selectcolor="#3498db"
            )
            cb.grid(row=0, column=i-1, padx=10)

        tk.Button(
            row_frame,
            text="✓ Chọn tất cả",
            command=self.select_all_rows,
            bg="#27ae60",
            fg="white",
            relief=tk.FLAT,
            padx=10
        ).pack(side=tk.LEFT, padx=5, pady=5)

        tk.Button(
            row_frame,
            text="✗ Bỏ chọn tất cả",
            command=self.deselect_all_rows,
            bg="#e74c3c",
            fg="white",
            relief=tk.FLAT,
            padx=10
        ).pack(side=tk.LEFT, padx=5)

        # Actions
        action_frame = tk.LabelFrame(
            content,
            text="⚡ Hành động",
            font=("Arial", 10, "bold"),
            bg="#ecf0f1",
            padx=10,
            pady=10
        )
        action_frame.pack(fill=tk.X, pady=(0, 10))

        buttons = [
            ("🤖 Auto Detect & Action", self.start_auto_detect, "#9b59b6"),
            ("🧺 Kéo giỏ thu hoạch (từng cây)", self.start_harvest, "#f39c12"),
            ("🧺💨 Kéo giỏ nhanh (cả hàng)", self.start_drag_harvest, "#e67e22"),
            ("🌱 Kéo hạt trồng cây", self.start_plant, "#27ae60"),
            ("🔄 Thu hoạch + Trồng lại", self.start_harvest_and_plant, "#3498db"),
            ("🧪 TEST Config Auto (TC)", self.test_config_auto, "#e91e63"),
        ]

        for text, command, color in buttons:
            tk.Button(
                action_frame,
                text=text,
                command=command,
                font=("Arial", 10),
                bg=color,
                fg="white",
                relief=tk.FLAT,
                padx=15,
                pady=10,
                cursor="hand2",
                width=25
            ).pack(pady=3)

        # Nút STOP - nổi bật
        self.stop_button = tk.Button(
            action_frame,
            text="⛔ DỪNG AUTO",
            command=self.stop_auto,
            font=("Arial", 11, "bold"),
            bg="#c0392b",
            fg="white",
            relief=tk.RAISED,
            padx=15,
            pady=12,
            cursor="hand2",
            width=25,
            state=tk.DISABLED  # Disable khi chưa chạy
        )
        self.stop_button.pack(pady=8)

        # Settings
        settings_frame = tk.LabelFrame(
            content,
            text="⚙️ Cài đặt",
            font=("Arial", 10, "bold"),
            bg="#ecf0f1",
            padx=10,
            pady=10
        )
        settings_frame.pack(fill=tk.X, pady=(0, 10))

        # Basket position
        basket_frame = tk.Frame(settings_frame, bg="#ecf0f1")
        basket_frame.pack(fill=tk.X, pady=5)

        tk.Label(
            basket_frame,
            text="🧺 Vị trí giỏ thu hoạch (X, Y):",
            bg="#ecf0f1",
            font=("Arial", 9, "bold")
        ).pack(side=tk.LEFT)

        self.basket_x_entry = tk.Entry(basket_frame, width=8, font=("Arial", 9))
        self.basket_x_entry.pack(side=tk.LEFT, padx=5)
        self.basket_x_entry.insert(0, "100")

        self.basket_y_entry = tk.Entry(basket_frame, width=8, font=("Arial", 9))
        self.basket_y_entry.pack(side=tk.LEFT, padx=5)
        self.basket_y_entry.insert(0, "700")

        tk.Button(
            basket_frame,
            text="📍 Click chọn",
            command=lambda: self.open_position_selector("basket"),
            bg="#9b59b6",
            fg="white",
            relief=tk.FLAT,
            cursor="hand2",
            padx=10
        ).pack(side=tk.LEFT, padx=5)

        # Seed icon position
        seed_frame = tk.Frame(settings_frame, bg="#ecf0f1")
        seed_frame.pack(fill=tk.X, pady=5)

        tk.Label(
            seed_frame,
            text="🌱 Vị trí icon hạt giống (X, Y):",
            bg="#ecf0f1",
            font=("Arial", 9, "bold")
        ).pack(side=tk.LEFT)

        self.seed_x_entry = tk.Entry(seed_frame, width=8, font=("Arial", 9))
        self.seed_x_entry.pack(side=tk.LEFT, padx=5)
        self.seed_x_entry.insert(0, "150")

        self.seed_y_entry = tk.Entry(seed_frame, width=8, font=("Arial", 9))
        self.seed_y_entry.pack(side=tk.LEFT, padx=5)
        self.seed_y_entry.insert(0, "100")

        tk.Button(
            seed_frame,
            text="📍 Click chọn",
            command=lambda: self.open_position_selector("seed"),
            bg="#9b59b6",
            fg="white",
            relief=tk.FLAT,
            cursor="hand2",
            padx=10
        ).pack(side=tk.LEFT, padx=5)

        # Delays
        delay_frame = tk.Frame(settings_frame, bg="#ecf0f1")
        delay_frame.pack(fill=tk.X, pady=5)

        tk.Label(
            delay_frame,
            text="Delay (ms):",
            bg="#ecf0f1",
            font=("Arial", 9)
        ).grid(row=0, column=0, sticky=tk.W)

        tk.Label(delay_frame, text="Tap:", bg="#ecf0f1").grid(row=0, column=1, padx=5)
        self.tap_delay_entry = tk.Entry(delay_frame, width=6)
        self.tap_delay_entry.grid(row=0, column=2, padx=2)
        self.tap_delay_entry.insert(0, "300")

        tk.Label(delay_frame, text="Thu hoạch:", bg="#ecf0f1").grid(row=0, column=3, padx=5)
        self.harvest_delay_entry = tk.Entry(delay_frame, width=6)
        self.harvest_delay_entry.grid(row=0, column=4, padx=2)
        self.harvest_delay_entry.insert(0, "500")

        tk.Label(delay_frame, text="Trồng:", bg="#ecf0f1").grid(row=0, column=5, padx=5)
        self.plant_delay_entry = tk.Entry(delay_frame, width=6)
        self.plant_delay_entry.grid(row=0, column=6, padx=2)
        self.plant_delay_entry.insert(0, "500")

        # Log
        log_frame = tk.LabelFrame(
            content,
            text="📋 Nhật ký",
            font=("Arial", 10, "bold"),
            bg="#ecf0f1",
            padx=10,
            pady=10
        )
        log_frame.pack(fill=tk.BOTH, expand=True)

        log_scroll = tk.Scrollbar(log_frame)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_text = tk.Text(
            log_frame,
            font=("Consolas", 8),
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

    def log(self, message):
        """Thêm log"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def select_device(self):
        """Chọn thiết bị từ danh sách"""
        from gui_select_device import DeviceSelector

        # Mở GUI chọn thiết bị
        selector = DeviceSelector()
        device = selector.run()

        if device:
            self.load_device(device['serial'], device['name'])
        else:
            if not self.device_serial:
                messagebox.showwarning("Chưa chọn", "Chưa chọn thiết bị! Vui lòng chọn thiết bị để tiếp tục.")

    def load_device(self, serial=None, name=None):
        """Load thiết bị"""
        try:
            # Nếu không truyền serial, thử lấy từ file đã lưu
            if not serial:
                serial = get_selected_device()
                # Lấy tên từ ADB Helper
                from core.adb_helper import get_adb_helper
                adb_helper = get_adb_helper()
                name = adb_helper.get_device_name(serial)

            self.device_serial = serial
            self.adb = ADBController(serial=self.device_serial)
            self.farm_bot = AutoFarm(self.adb)

            # Hiển thị tên thân thiện
            display_name = name if name else self.device_serial
            self.device_label.config(text=f"📱 Thiết bị: {display_name}")
            self.log(f"✓ Đã kết nối: {display_name} ({self.device_serial})")
            self.status_label.config(text="✓ Đã kết nối thiết bị", bg="#27ae60")
        except Exception as e:
            self.log(f"✗ Lỗi kết nối: {e}")
            self.device_label.config(text="📱 Thiết bị: Chưa kết nối")
            self.status_label.config(text="✗ Chưa kết nối", bg="#e74c3c")
            # Hiển thị dialog chọn thiết bị
            response = messagebox.askyesno(
                "Lỗi kết nối",
                f"Không thể kết nối thiết bị:\n{e}\n\nBạn có muốn chọn thiết bị khác không?"
            )
            if response:
                self.select_device()

    def get_selected_rows(self):
        """Lấy danh sách hàng được chọn"""
        return [row for row, var in self.row_vars.items() if var.get()]

    def get_seed_position(self):
        """Lấy vị trí icon hạt giống"""
        try:
            x = int(self.seed_x_entry.get())
            y = int(self.seed_y_entry.get())
            return (x, y)
        except:
            return None

    def get_basket_position(self):
        """Lấy vị trí giỏ thu hoạch"""
        try:
            x = int(self.basket_x_entry.get())
            y = int(self.basket_y_entry.get())
            return (x, y)
        except:
            return (100, 700)  # Mặc định

    def update_delays(self):
        """Cập nhật delay cho farm bot"""
        try:
            self.farm_bot.TAP_DELAY = int(self.tap_delay_entry.get()) / 1000
            self.farm_bot.HARVEST_DELAY = int(self.harvest_delay_entry.get()) / 1000
            self.farm_bot.PLANT_DELAY = int(self.plant_delay_entry.get()) / 1000
        except:
            pass

    def select_all_rows(self):
        """Chọn tất cả hàng"""
        for var in self.row_vars.values():
            var.set(True)

    def deselect_all_rows(self):
        """Bỏ chọn tất cả"""
        for var in self.row_vars.values():
            var.set(False)

    def start_harvest(self):
        """Bắt đầu thu hoạch"""
        if not self.check_ready():
            return

        rows = self.get_selected_rows()
        if not rows:
            messagebox.showwarning("Chưa chọn hàng", "Vui lòng chọn ít nhất 1 hàng!")
            return

        self.log(f"\n▶ Bắt đầu thu hoạch hàng: {rows}")
        self.status_label.config(text="⏳ Đang thu hoạch...", bg="#f39c12")

        def run():
            try:
                self.update_delays()
                self.farm_bot.harvest_all(rows)
                self.log("✓ Hoàn thành thu hoạch!")
                self.status_label.config(text="✓ Hoàn thành", bg="#27ae60")
                messagebox.showinfo("Thành công", "Đã thu hoạch xong!")
            except Exception as e:
                self.log(f"✗ Lỗi: {e}")
                self.status_label.config(text="✗ Lỗi", bg="#e74c3c")
                messagebox.showerror("Lỗi", f"Có lỗi xảy ra:\n{e}")

        threading.Thread(target=run, daemon=True).start()

    def start_plant(self):
        """Bắt đầu trồng cây"""
        if not self.check_ready():
            return

        rows = self.get_selected_rows()
        if not rows:
            messagebox.showwarning("Chưa chọn hàng", "Vui lòng chọn ít nhất 1 hàng!")
            return

        seed_pos = self.get_seed_position()

        self.log(f"\n▶ Bắt đầu trồng cây hàng: {rows}")
        if seed_pos:
            self.log(f"  Icon hạt giống: {seed_pos}")

        self.status_label.config(text="⏳ Đang trồng cây...", bg="#f39c12")

        def run():
            try:
                self.update_delays()
                self.farm_bot.plant_all(rows, seed_pos)
                self.log("✓ Hoàn thành trồng cây!")
                self.status_label.config(text="✓ Hoàn thành", bg="#27ae60")
                messagebox.showinfo("Thành công", "Đã trồng cây xong!")
            except Exception as e:
                self.log(f"✗ Lỗi: {e}")
                self.status_label.config(text="✗ Lỗi", bg="#e74c3c")
                messagebox.showerror("Lỗi", f"Có lỗi xảy ra:\n{e}")

        threading.Thread(target=run, daemon=True).start()

    def start_harvest_and_plant(self):
        """Thu hoạch rồi trồng lại"""
        if not self.check_ready():
            return

        rows = self.get_selected_rows()
        if not rows:
            messagebox.showwarning("Chưa chọn hàng", "Vui lòng chọn ít nhất 1 hàng!")
            return

        seed_pos = self.get_seed_position()

        self.log(f"\n▶ Bắt đầu thu hoạch + trồng lại hàng: {rows}")
        self.status_label.config(text="⏳ Đang thu hoạch + trồng...", bg="#f39c12")

        def run():
            try:
                self.update_delays()
                self.farm_bot.harvest_and_plant(rows, seed_pos)
                self.log("✓ Hoàn thành chu trình!")
                self.status_label.config(text="✓ Hoàn thành", bg="#27ae60")
                messagebox.showinfo("Thành công", "Đã hoàn thành chu trình!")
            except Exception as e:
                self.log(f"✗ Lỗi: {e}")
                self.status_label.config(text="✗ Lỗi", bg="#e74c3c")
                messagebox.showerror("Lỗi", f"Có lỗi xảy ra:\n{e}")

        threading.Thread(target=run, daemon=True).start()

    def start_auto_detect(self):
        """Auto detect giỏ hoặc menu trồng cây và thực hiện action"""
        if not self.check_ready():
            return

        self.log(f"\n▶ Bắt đầu Auto Detect...")
        self.status_label.config(text="⏳ Đang phân tích màn hình...", bg="#9b59b6")

        def run():
            try:
                # Chụp màn hình
                self.log("📸 Đang chụp màn hình...")
                screenshot = self.adb.screenshot_full()

                # Phân tích màn hình
                self.log("🔍 Đang phát hiện giỏ/menu trồng cây...")
                result = self.image_detector.analyze_screen(screenshot)

                self.log(f"[DEBUG] Kết quả: {result}")

                if result['action'] == 'harvest':
                    # Phát hiện giỏ thu hoạch
                    self.log(f"✓ Phát hiện giỏ thu hoạch tại: {result['position']}")
                    self.basket_pos = result['position']

                    # Cập nhật vào entry
                    self.basket_x_entry.delete(0, tk.END)
                    self.basket_x_entry.insert(0, str(result['position'][0]))
                    self.basket_y_entry.delete(0, tk.END)
                    self.basket_y_entry.insert(0, str(result['position'][1]))

                    # Thực hiện thu hoạch
                    self.log("🧺 Bắt đầu thu hoạch...")
                    rows = self.get_selected_rows()
                    if not rows:
                        self.log("⚠ Chưa chọn hàng! Chọn tất cả 4 hàng...")
                        rows = [1, 2, 3, 4]

                    for row in rows:
                        self.farm_bot.harvest_row_drag(row, result['position'])
                        time.sleep(0.5)

                    self.log("✓ Hoàn thành thu hoạch!")
                    self.status_label.config(text="✓ Hoàn thành", bg="#27ae60")
                    messagebox.showinfo("Thành công", "Đã thu hoạch xong!")

                elif result['action'] == 'plant':
                    # Phát hiện menu trồng cây
                    self.log(f"✓ Phát hiện menu trồng cây: {result['plant_name']} tại {result['position']}")
                    self.seed_icon_pos = result['position']

                    # Cập nhật vào entry
                    self.seed_x_entry.delete(0, tk.END)
                    self.seed_x_entry.insert(0, str(result['position'][0]))
                    self.seed_y_entry.delete(0, tk.END)
                    self.seed_y_entry.insert(0, str(result['position'][1]))

                    # Thực hiện trồng cây
                    self.log(f"🌱 Bắt đầu trồng {result['plant_name']}...")
                    rows = self.get_selected_rows()
                    if not rows:
                        self.log("⚠ Chưa chọn hàng! Chọn tất cả 4 hàng...")
                        rows = [1, 2, 3, 4]

                    self.update_delays()
                    self.farm_bot.plant_all(rows, result['position'])

                    self.log("✓ Hoàn thành trồng cây!")
                    self.status_label.config(text="✓ Hoàn thành", bg="#27ae60")
                    messagebox.showinfo("Thành công", f"Đã trồng {result['plant_name']} xong!")

                else:
                    # Không phát hiện được
                    self.log("✗ Không phát hiện được giỏ hoặc menu trồng cây!")
                    self.status_label.config(text="✗ Không phát hiện", bg="#e74c3c")
                    messagebox.showwarning(
                        "Không phát hiện",
                        "Không tìm thấy giỏ thu hoạch hoặc menu trồng cây!\n\n"
                        "Đảm bảo:\n"
                        "1. Giỏ đang hiển thị (nếu cây chín)\n"
                        "2. Menu trồng cây đang mở (nếu ô trống)\n"
                        "3. Template ảnh đã được thêm vào assets/items/"
                    )

            except Exception as e:
                self.log(f"✗ Lỗi: {e}")
                self.status_label.config(text="✗ Lỗi", bg="#e74c3c")
                messagebox.showerror("Lỗi", f"Có lỗi xảy ra:\n{e}")

        threading.Thread(target=run, daemon=True).start()

    def start_drag_harvest(self):
        """Kéo giỏ nhanh qua cả hàng"""
        if not self.check_ready():
            return

        rows = self.get_selected_rows()
        if not rows:
            messagebox.showwarning("Chưa chọn hàng", "Vui lòng chọn ít nhất 1 hàng!")
            return

        basket_pos = self.get_basket_position()

        self.log(f"\n▶ Kéo giỏ nhanh thu hoạch hàng: {rows}")
        self.log(f"  Vị trí giỏ: {basket_pos}")
        self.status_label.config(text="⏳ Đang kéo giỏ thu hoạch...", bg="#f39c12")

        def run():
            try:
                self.update_delays()
                for row in rows:
                    self.farm_bot.harvest_row_drag(row, basket_pos)
                    time.sleep(0.5)

                self.log("✓ Hoàn thành kéo giỏ thu hoạch!")
                self.status_label.config(text="✓ Hoàn thành", bg="#27ae60")
                messagebox.showinfo("Thành công", "Đã kéo giỏ thu hoạch xong!")
            except Exception as e:
                self.log(f"✗ Lỗi: {e}")
                self.status_label.config(text="✗ Lỗi", bg="#e74c3c")
                messagebox.showerror("Lỗi", f"Có lỗi xảy ra:\n{e}")

        threading.Thread(target=run, daemon=True).start()

    def open_position_selector(self, position_type):
        """Mở cửa sổ chọn vị trí bằng click"""
        if not self.adb:
            messagebox.showerror("Lỗi", "Chưa kết nối thiết bị!")
            return

        self.selecting_for = position_type

        # Chụp màn hình
        try:
            self.log(f"📸 Đang chụp màn hình để chọn vị trí {position_type}...")
            img = self.adb.screenshot_full()
            self.screenshot_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            self.show_position_selector_window()
        except Exception as e:
            self.log(f"✗ Lỗi chụp màn hình: {e}")
            messagebox.showerror("Lỗi", f"Không thể chụp màn hình:\n{e}")

    def show_position_selector_window(self):
        """Hiển thị cửa sổ chọn vị trí"""
        # Tạo cửa sổ mới
        self.screenshot_window = tk.Toplevel(self.root)

        if self.selecting_for == "basket":
            title = "🧺 Click vào vị trí giỏ thu hoạch"
            instruction = "Click vào icon giỏ thu hoạch (giỏ sẽ xuất hiện khi cây chín)"
        else:
            title = "🌱 Click vào vị trí hạt giống"
            instruction = "Click vào icon hạt giống mà bạn muốn trồng (trong menu)"

        self.screenshot_window.title(title)
        self.screenshot_window.geometry("900x700")

        # Instruction
        instruction_frame = tk.Frame(self.screenshot_window, bg="#3498db", height=50)
        instruction_frame.pack(fill=tk.X)
        instruction_frame.pack_propagate(False)

        tk.Label(
            instruction_frame,
            text=instruction,
            font=("Arial", 11, "bold"),
            bg="#3498db",
            fg="white"
        ).pack(pady=12)

        # Canvas để hiển thị ảnh
        canvas_frame = tk.Frame(self.screenshot_window)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Scrollbars
        h_scroll = tk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        v_scroll = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas = tk.Canvas(
            canvas_frame,
            xscrollcommand=h_scroll.set,
            yscrollcommand=v_scroll.set,
            bg="#2c3e50",
            cursor="crosshair"
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        h_scroll.config(command=self.canvas.xview)
        v_scroll.config(command=self.canvas.yview)

        # Hiển thị ảnh
        pil_img = Image.fromarray(self.screenshot_img)
        self.photo = ImageTk.PhotoImage(pil_img)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
        self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))

        # Bind click event
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        # Info panel
        info_frame = tk.Frame(self.screenshot_window, bg="#ecf0f1")
        info_frame.pack(fill=tk.X, padx=10, pady=5)

        self.position_label = tk.Label(
            info_frame,
            text="Vị trí: Click vào ảnh để chọn",
            font=("Arial", 10),
            bg="#ecf0f1",
            fg="#2c3e50"
        )
        self.position_label.pack(side=tk.LEFT, padx=10)

        # Buttons
        btn_frame = tk.Frame(self.screenshot_window, bg="#ecf0f1")
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Button(
            btn_frame,
            text="✓ Xác nhận",
            command=self.confirm_position,
            bg="#27ae60",
            fg="white",
            font=("Arial", 10, "bold"),
            relief=tk.FLAT,
            padx=20,
            pady=8,
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            btn_frame,
            text="✗ Hủy",
            command=self.cancel_position_selection,
            bg="#e74c3c",
            fg="white",
            font=("Arial", 10, "bold"),
            relief=tk.FLAT,
            padx=20,
            pady=8,
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            btn_frame,
            text="🔄 Chụp lại",
            command=lambda: self.refresh_screenshot(),
            bg="#3498db",
            fg="white",
            font=("Arial", 10, "bold"),
            relief=tk.FLAT,
            padx=20,
            pady=8,
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=5)

    def on_canvas_click(self, event):
        """Xử lý khi click vào canvas"""
        # Lấy tọa độ thực tế (tính cả scroll)
        x = int(self.canvas.canvasx(event.x))
        y = int(self.canvas.canvasy(event.y))

        # Cập nhật label
        self.position_label.config(
            text=f"Vị trí đã chọn: X={x}, Y={y}",
            fg="#27ae60",
            font=("Arial", 10, "bold")
        )

        # Lưu tạm
        if self.selecting_for == "basket":
            self.basket_pos = (x, y)
        else:
            self.seed_icon_pos = (x, y)

        # Vẽ điểm đánh dấu
        self.canvas.delete("marker")
        self.canvas.create_oval(
            x-10, y-10, x+10, y+10,
            outline="red", width=3, tags="marker"
        )
        self.canvas.create_line(
            x-15, y, x+15, y,
            fill="red", width=2, tags="marker"
        )
        self.canvas.create_line(
            x, y-15, x, y+15,
            fill="red", width=2, tags="marker"
        )

    def confirm_position(self):
        """Xác nhận vị trí đã chọn"""
        if self.selecting_for == "basket":
            if self.basket_pos:
                self.basket_x_entry.delete(0, tk.END)
                self.basket_x_entry.insert(0, str(self.basket_pos[0]))
                self.basket_y_entry.delete(0, tk.END)
                self.basket_y_entry.insert(0, str(self.basket_pos[1]))
                self.log(f"✓ Đã chọn vị trí giỏ: {self.basket_pos}")
                messagebox.showinfo("Thành công", f"Đã chọn vị trí giỏ:\nX={self.basket_pos[0]}, Y={self.basket_pos[1]}")
            else:
                messagebox.showwarning("Chưa chọn", "Vui lòng click vào ảnh để chọn vị trí!")
                return
        else:
            if self.seed_icon_pos:
                self.seed_x_entry.delete(0, tk.END)
                self.seed_x_entry.insert(0, str(self.seed_icon_pos[0]))
                self.seed_y_entry.delete(0, tk.END)
                self.seed_y_entry.insert(0, str(self.seed_icon_pos[1]))
                self.log(f"✓ Đã chọn vị trí hạt giống: {self.seed_icon_pos}")
                messagebox.showinfo("Thành công", f"Đã chọn vị trí hạt giống:\nX={self.seed_icon_pos[0]}, Y={self.seed_icon_pos[1]}")
            else:
                messagebox.showwarning("Chưa chọn", "Vui lòng click vào ảnh để chọn vị trí!")
                return

        self.screenshot_window.destroy()
        self.screenshot_window = None

    def cancel_position_selection(self):
        """Hủy chọn vị trí"""
        self.screenshot_window.destroy()
        self.screenshot_window = None

    def refresh_screenshot(self):
        """Chụp lại màn hình"""
        try:
            self.log("📸 Đang chụp lại màn hình...")
            img = self.adb.screenshot_full()
            self.screenshot_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            # Cập nhật canvas
            pil_img = Image.fromarray(self.screenshot_img)
            self.photo = ImageTk.PhotoImage(pil_img)
            self.canvas.delete(tk.ALL)
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
            self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))

            self.log("✓ Đã chụp lại màn hình")
        except Exception as e:
            self.log(f"✗ Lỗi chụp lại: {e}")
            messagebox.showerror("Lỗi", f"Không thể chụp lại:\n{e}")

    def test_config_auto(self):
        """Test auto farm theo CONFIG_TEMP_TC"""
        if not self.check_ready():
            return

        from config import CONFIG_TEMP_TC, INDEX_HANG
        from core.trong_cay import main_tc

        self.log(f"\n▶ BẮT ĐẦU TEST CONFIG AUTO")
        self.log(f"📋 Tổng số config: {len(CONFIG_TEMP_TC)}")
        self.status_label.config(text="⏳ Đang chạy test config...", bg="#e91e63")
        self.set_running(True)  # Enable nút Stop

        def run():
            try:
                # Ưu tiên nạp config từ thư mục configs bên ngoài nếu có
                from config import get_configs_dir
                configs_dir = get_configs_dir()
                tc_configs = CONFIG_TEMP_TC
                if os.path.exists(configs_dir):
                    import glob, json
                    mac_dinh_path = os.path.join(configs_dir, "mac_dinh.json")
                    target_json = mac_dinh_path if os.path.exists(mac_dinh_path) else None
                    if not target_json:
                        json_files = glob.glob(os.path.join(configs_dir, "*.json"))
                        for jf in json_files:
                            if not os.path.basename(jf).startswith("global_setting"):
                                target_json = jf
                                break
                    if target_json and os.path.exists(target_json):
                        try:
                            with open(target_json, "r", encoding="utf-8") as f:
                                raw = json.load(f)
                            if isinstance(raw, dict) and "tasks" in raw:
                                loaded_tc = [t for t in raw["tasks"] if t.get("type") == "TC"]
                                if loaded_tc:
                                    tc_configs = loaded_tc
                                    self.log(f"📋 Nạp cấu hình trồng cây từ bên ngoài: {os.path.basename(target_json)}")
                        except Exception as e:
                            self.log(f"⚠️ Lỗi đọc {target_json}: {e}")


                self.log(f"🌾 Tìm thấy {len(tc_configs)} config trồng cây (TC)")

                # Hiển thị thông tin config
                for idx, cfg in enumerate(tc_configs, 1):
                    if self.check_stop():  # Kiểm tra stop
                        return

                    self.log(f"\n--- Config {idx}/{len(tc_configs)} ---")
                    self.log(f"  Hàng: {cfg.get('row')}")
                    self.log(f"  Loại cây: {cfg.get('path_item')}")
                    self.log(f"  Số vị trí: {len(cfg.get('indexs', []))}")

                if self.check_stop():  # Kiểm tra stop trước khi chạy
                    return

                # Gọi hàm main_tc với ADB instance và callback check stop
                self.log(f"\n🚀 Bắt đầu chạy auto farm...")
                main_tc(tc_configs, adb_instance=self.adb, stop_callback=self.check_stop)

                if not self.stop_flag:  # Chỉ hiển thị success nếu không bị dừng
                    self.log("\n✓ Hoàn thành test config auto!")
                    self.status_label.config(text="✓ Hoàn thành", bg="#27ae60")
                    messagebox.showinfo("Thành công", "Đã chạy xong test config!")

            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                self.log(f"✗ Lỗi: {e}")
                self.log(f"Chi tiết:\n{error_detail}")
                self.status_label.config(text="✗ Lỗi", bg="#e74c3c")
                messagebox.showerror("Lỗi", f"Có lỗi xảy ra:\n{e}")
            finally:
                self.set_running(False)  # Disable nút Stop

        threading.Thread(target=run, daemon=True).start()

    def stop_auto(self):
        """Dừng auto đang chạy"""
        self.stop_flag = True
        self.log("\n⛔ Đã nhấn DỪNG - Đang dừng auto...")
        self.status_label.config(text="⛔ Đang dừng...", bg="#c0392b")
        self.stop_button.config(state=tk.DISABLED)

    def set_running(self, running: bool):
        """Cập nhật trạng thái chạy và enable/disable nút Stop"""
        self.is_running = running
        if running:
            self.stop_flag = False
            self.stop_button.config(state=tk.NORMAL, bg="#e74c3c")
        else:
            self.stop_button.config(state=tk.DISABLED, bg="#c0392b")

    def check_stop(self):
        """Kiểm tra xem có yêu cầu dừng không"""
        if self.stop_flag:
            self.log("⛔ Auto đã bị dừng bởi người dùng")
            self.status_label.config(text="⛔ Đã dừng", bg="#c0392b")
            self.set_running(False)
            return True
        return False

    def check_ready(self):
        """Kiểm tra sẵn sàng"""
        if not self.adb or not self.farm_bot:
            messagebox.showwarning("Chưa kết nối", "Vui lòng kết nối thiết bị!")
            return False
        return True

    def run(self):
        """Chạy GUI"""
        self.root.mainloop()


if __name__ == "__main__":
    app = AutoFarmGUI()
    app.run()
