"""
GUI Screenshot Tool - Công cụ chụp màn hình và cắt ảnh
Cho phép chụp màn hình LDPlayer, crop vùng, và lưu ảnh
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk, ImageDraw
import cv2
import numpy as np
from core.adb import ADBController
from gui_select_device import get_selected_device
import os
from datetime import datetime

class ScreenshotTool:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Screenshot Tool - Auto KVTM")
        self.root.geometry("1200x800")

        self.device_serial = None
        self.adb = None
        self.current_screenshot = None
        self.display_image = None
        self.photo_image = None

        # Crop selection
        self.crop_start = None
        self.crop_end = None
        self.crop_rect = None
        self.is_cropping = False

        # History
        self.screenshot_history = []

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
        file_menu.add_command(label="Chụp màn hình", command=self.take_screenshot, accelerator="F2")
        file_menu.add_command(label="Lưu ảnh...", command=self.save_screenshot, accelerator="Ctrl+S")
        file_menu.add_command(label="Lưu vùng đã crop...", command=self.save_cropped, accelerator="Ctrl+Shift+S")
        file_menu.add_separator()
        file_menu.add_command(label="Thoát", command=self.root.quit)

        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="✂️ Chỉnh sửa", menu=edit_menu)
        edit_menu.add_command(label="Reset crop", command=self.reset_crop, accelerator="Esc")
        edit_menu.add_command(label="Crop nhanh (chọn vùng)", command=self.quick_crop)

        # Device menu
        device_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="📱 Thiết bị", menu=device_menu)
        device_menu.add_command(label="Đổi thiết bị", command=self.change_device)
        device_menu.add_command(label="Refresh kết nối", command=self.load_device)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="❓ Trợ giúp", menu=help_menu)
        help_menu.add_command(label="Hướng dẫn", command=self.show_help)

        # Bind keys
        self.root.bind('<F2>', lambda _: self.take_screenshot())
        self.root.bind('<Control-s>', lambda _: self.save_screenshot())
        self.root.bind('<Control-Shift-S>', lambda _: self.save_cropped())
        self.root.bind('<Escape>', lambda _: self.reset_crop())

        # Top toolbar
        toolbar = tk.Frame(self.root, bg="#34495e", height=50)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)

        # Device label
        self.device_label = tk.Label(
            toolbar,
            text="📱 Thiết bị: Chưa kết nối",
            font=("Arial", 10),
            bg="#34495e",
            fg="white",
            padx=10
        )
        self.device_label.pack(side=tk.LEFT, pady=10)

        # Buttons
        btn_frame = tk.Frame(toolbar, bg="#34495e")
        btn_frame.pack(side=tk.RIGHT, padx=10)

        tk.Button(
            btn_frame,
            text="📸 Chụp (F2)",
            command=self.take_screenshot,
            bg="#3498db",
            fg="white",
            relief=tk.FLAT,
            padx=15,
            pady=5,
            cursor="hand2",
            font=("Arial", 9, "bold")
        ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            btn_frame,
            text="💾 Lưu",
            command=self.save_screenshot,
            bg="#27ae60",
            fg="white",
            relief=tk.FLAT,
            padx=15,
            pady=5,
            cursor="hand2",
            font=("Arial", 9)
        ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            btn_frame,
            text="✂️ Lưu vùng crop",
            command=self.save_cropped,
            bg="#e67e22",
            fg="white",
            relief=tk.FLAT,
            padx=15,
            pady=5,
            cursor="hand2",
            font=("Arial", 9)
        ).pack(side=tk.LEFT, padx=2)

        # Main content
        content = tk.Frame(self.root)
        content.pack(fill=tk.BOTH, expand=True)

        # Left panel - Canvas
        left_panel = tk.Frame(content, bg="#2c3e50")
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Canvas title
        tk.Label(
            left_panel,
            text="🖼️ Màn hình LDPlayer (Click và kéo để crop)",
            font=("Arial", 10, "bold"),
            bg="#2c3e50",
            fg="white",
            pady=10
        ).pack()

        # Canvas frame with scrollbars
        canvas_frame = tk.Frame(left_panel)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Scrollbars
        h_scroll = tk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        v_scroll = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Canvas
        self.canvas = tk.Canvas(
            canvas_frame,
            bg="#34495e",
            xscrollcommand=h_scroll.set,
            yscrollcommand=v_scroll.set,
            cursor="crosshair"
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        h_scroll.config(command=self.canvas.xview)
        v_scroll.config(command=self.canvas.yview)

        # Canvas events
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)

        # Right panel - Info & Controls
        right_panel = tk.Frame(content, bg="#ecf0f1", width=300)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        right_panel.pack_propagate(False)

        # Info section
        info_frame = tk.LabelFrame(
            right_panel,
            text="📊 Thông tin",
            font=("Arial", 10, "bold"),
            bg="#ecf0f1",
            padx=10,
            pady=10
        )
        info_frame.pack(fill=tk.X, padx=10, pady=10)

        self.info_text = tk.Text(
            info_frame,
            font=("Consolas", 9),
            height=12,
            bg="white",
            wrap=tk.WORD
        )
        self.info_text.pack(fill=tk.X)
        self.update_info("Chưa có ảnh")

        # Crop coordinates
        crop_frame = tk.LabelFrame(
            right_panel,
            text="✂️ Tọa độ Crop",
            font=("Arial", 10, "bold"),
            bg="#ecf0f1",
            padx=10,
            pady=10
        )
        crop_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(crop_frame, text="X:", bg="#ecf0f1").grid(row=0, column=0, sticky=tk.W)
        self.crop_x_entry = tk.Entry(crop_frame, width=8)
        self.crop_x_entry.grid(row=0, column=1, padx=5)

        tk.Label(crop_frame, text="Y:", bg="#ecf0f1").grid(row=0, column=2, sticky=tk.W)
        self.crop_y_entry = tk.Entry(crop_frame, width=8)
        self.crop_y_entry.grid(row=0, column=3, padx=5)

        tk.Label(crop_frame, text="W:", bg="#ecf0f1").grid(row=1, column=0, sticky=tk.W)
        self.crop_w_entry = tk.Entry(crop_frame, width=8)
        self.crop_w_entry.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(crop_frame, text="H:", bg="#ecf0f1").grid(row=1, column=2, sticky=tk.W)
        self.crop_h_entry = tk.Entry(crop_frame, width=8)
        self.crop_h_entry.grid(row=1, column=3, padx=5, pady=5)

        tk.Button(
            crop_frame,
            text="Áp dụng tọa độ",
            command=self.apply_manual_crop,
            bg="#3498db",
            fg="white",
            relief=tk.FLAT,
            cursor="hand2"
        ).grid(row=2, column=0, columnspan=4, pady=5, sticky=tk.EW)

        # Quick save templates
        template_frame = tk.LabelFrame(
            right_panel,
            text="📁 Lưu nhanh",
            font=("Arial", 10, "bold"),
            bg="#ecf0f1",
            padx=10,
            pady=10
        )
        template_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(template_frame, text="Tên file:", bg="#ecf0f1").pack(anchor=tk.W)

        self.filename_entry = tk.Entry(template_frame, font=("Arial", 10))
        self.filename_entry.pack(fill=tk.X, pady=5)
        self.filename_entry.insert(0, f"screenshot_{datetime.now().strftime('%H%M%S')}")

        tk.Label(template_frame, text="Thư mục:", bg="#ecf0f1").pack(anchor=tk.W, pady=(10, 0))

        folder_frame = tk.Frame(template_frame, bg="#ecf0f1")
        folder_frame.pack(fill=tk.X, pady=5)

        self.folder_entry = tk.Entry(folder_frame, font=("Arial", 9))
        self.folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.folder_entry.insert(0, "assets/items")

        tk.Button(
            folder_frame,
            text="...",
            command=self.browse_folder,
            width=3
        ).pack(side=tk.RIGHT, padx=(5, 0))

        tk.Button(
            template_frame,
            text="💾 Lưu ảnh gốc",
            command=self.quick_save_original,
            bg="#27ae60",
            fg="white",
            relief=tk.FLAT,
            cursor="hand2"
        ).pack(fill=tk.X, pady=2)

        tk.Button(
            template_frame,
            text="✂️ Lưu ảnh đã crop",
            command=self.quick_save_cropped,
            bg="#e67e22",
            fg="white",
            relief=tk.FLAT,
            cursor="hand2"
        ).pack(fill=tk.X, pady=2)

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

    def load_device(self):
        """Load thiết bị"""
        try:
            self.device_serial = get_selected_device()
            self.adb = ADBController(serial=self.device_serial)
            self.device_label.config(text=f"📱 Thiết bị: {self.device_serial}")
            self.status_label.config(text=f"✓ Đã kết nối: {self.device_serial}", bg="#27ae60")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể kết nối thiết bị:\n{e}")
            self.status_label.config(text="✗ Chưa kết nối thiết bị", bg="#e74c3c")

    def change_device(self):
        """Đổi thiết bị"""
        from gui_select_device import DeviceSelector
        selector = DeviceSelector()
        device = selector.run()
        if device:
            self.device_serial = device['serial']
            self.adb = ADBController(serial=self.device_serial)
            self.device_label.config(text=f"📱 Thiết bị: {self.device_serial}")
            self.status_label.config(text=f"✓ Đã kết nối: {self.device_serial}", bg="#27ae60")

    def take_screenshot(self):
        """Chụp màn hình"""
        if not self.adb:
            messagebox.showwarning("Chưa kết nối", "Vui lòng kết nối thiết bị trước!")
            self.change_device()
            return

        try:
            self.status_label.config(text="📸 Đang chụp màn hình...", bg="#f39c12")
            self.root.update()

            # Tạo thư mục cache
            import os
            os.makedirs("cache", exist_ok=True)

            # Kiểm tra kết nối
            if not self.adb.is_connected():
                raise Exception("Thiết bị không phản hồi. Vui lòng kiểm tra kết nối!")

            # Chụp màn hình
            self.update_info("Đang chụp màn hình...")
            self.root.update()

            screenshot = self.adb.screenshot_full("cache/screenshot_tool.png")

            if screenshot is None:
                raise Exception("Không nhận được ảnh từ thiết bị")

            self.current_screenshot = screenshot

            # Hiển thị lên canvas
            self.display_screenshot(screenshot)

            # Update info
            h, w = screenshot.shape[:2]
            self.update_info(f"✓ Chụp thành công!\n\nKích thước: {w}x{h} pixels\nĐịnh dạng: BGR (OpenCV)\nFile: cache/screenshot_tool.png")

            self.status_label.config(text="✓ Đã chụp màn hình", bg="#27ae60")

            # Add to history
            self.screenshot_history.append({
                'image': screenshot.copy(),
                'timestamp': datetime.now()
            })

        except Exception as e:
            error_msg = str(e)
            self.update_info(f"✗ Lỗi chụp màn hình:\n\n{error_msg}")
            messagebox.showerror("Lỗi chụp màn hình", f"Không thể chụp màn hình:\n\n{error_msg}\n\nVui lòng kiểm tra:\n1. LDPlayer đang chạy\n2. ADB đã kết nối\n3. Thiết bị phản hồi")
            self.status_label.config(text="✗ Lỗi chụp màn hình", bg="#e74c3c")

    def display_screenshot(self, image):
        """Hiển thị ảnh lên canvas"""
        # Convert BGR to RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Convert to PIL Image
        pil_image = Image.fromarray(image_rgb)
        self.display_image = pil_image

        # Convert to PhotoImage
        self.photo_image = ImageTk.PhotoImage(pil_image)

        # Update canvas
        self.canvas.config(scrollregion=(0, 0, pil_image.width, pil_image.height))
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo_image, tags="image")

        # Reset crop
        self.reset_crop()

    def on_mouse_down(self, event):
        """Mouse down - bắt đầu crop"""
        if not self.current_screenshot is None:
            self.crop_start = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
            self.is_cropping = True

    def on_mouse_drag(self, event):
        """Mouse drag - vẽ vùng crop"""
        if self.is_cropping and self.crop_start:
            # Xóa rectangle cũ
            if self.crop_rect:
                self.canvas.delete(self.crop_rect)

            # Vẽ rectangle mới
            x1, y1 = self.crop_start
            x2, y2 = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

            self.crop_rect = self.canvas.create_rectangle(
                x1, y1, x2, y2,
                outline="red",
                width=2,
                dash=(5, 5)
            )

            # Update coordinates
            w = abs(x2 - x1)
            h = abs(y2 - y1)
            self.update_info(f"Crop: ({int(min(x1,x2))}, {int(min(y1,y2))}) - {int(w)}x{int(h)}")

    def on_mouse_up(self, event):
        """Mouse up - kết thúc crop"""
        if self.is_cropping and self.crop_start:
            x2, y2 = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
            self.crop_end = (x2, y2)
            self.is_cropping = False

            # Update entry fields
            x1, y1 = self.crop_start
            x = int(min(x1, x2))
            y = int(min(y1, y2))
            w = int(abs(x2 - x1))
            h = int(abs(y2 - y1))

            self.crop_x_entry.delete(0, tk.END)
            self.crop_x_entry.insert(0, str(x))

            self.crop_y_entry.delete(0, tk.END)
            self.crop_y_entry.insert(0, str(y))

            self.crop_w_entry.delete(0, tk.END)
            self.crop_w_entry.insert(0, str(w))

            self.crop_h_entry.delete(0, tk.END)
            self.crop_h_entry.insert(0, str(h))

            self.update_info(f"Crop đã chọn:\nX: {x}, Y: {y}\nWidth: {w}\nHeight: {h}")

    def reset_crop(self):
        """Reset vùng crop"""
        self.crop_start = None
        self.crop_end = None
        if self.crop_rect:
            self.canvas.delete(self.crop_rect)
            self.crop_rect = None
        self.is_cropping = False

        # Clear entries
        self.crop_x_entry.delete(0, tk.END)
        self.crop_y_entry.delete(0, tk.END)
        self.crop_w_entry.delete(0, tk.END)
        self.crop_h_entry.delete(0, tk.END)

    def apply_manual_crop(self):
        """Áp dụng crop thủ công từ entry"""
        try:
            x = int(self.crop_x_entry.get())
            y = int(self.crop_y_entry.get())
            w = int(self.crop_w_entry.get())
            h = int(self.crop_h_entry.get())

            # Vẽ rectangle
            if self.crop_rect:
                self.canvas.delete(self.crop_rect)

            self.crop_rect = self.canvas.create_rectangle(
                x, y, x + w, y + h,
                outline="red",
                width=2,
                dash=(5, 5)
            )

            self.crop_start = (x, y)
            self.crop_end = (x + w, y + h)

            self.update_info(f"Crop thủ công:\nX: {x}, Y: {y}\nWidth: {w}\nHeight: {h}")

        except ValueError:
            messagebox.showerror("Lỗi", "Vui lòng nhập số hợp lệ!")

    def get_cropped_image(self):
        """Lấy ảnh đã crop"""
        if self.current_screenshot is None:
            return None

        if not self.crop_start or not self.crop_end:
            return None

        x1, y1 = self.crop_start
        x2, y2 = self.crop_end

        x = int(min(x1, x2))
        y = int(min(y1, y2))
        w = int(abs(x2 - x1))
        h = int(abs(y2 - y1))

        # Crop ảnh
        cropped = self.current_screenshot[y:y+h, x:x+w]
        return cropped

    def save_screenshot(self):
        """Lưu ảnh gốc"""
        if self.current_screenshot is None:
            messagebox.showwarning("Chưa có ảnh", "Vui lòng chụp màn hình trước!")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
            initialfile=f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        )

        if filepath:
            cv2.imwrite(filepath, self.current_screenshot)
            messagebox.showinfo("Thành công", f"Đã lưu ảnh:\n{filepath}")
            self.status_label.config(text=f"✓ Đã lưu: {os.path.basename(filepath)}", bg="#27ae60")

    def save_cropped(self):
        """Lưu ảnh đã crop"""
        cropped = self.get_cropped_image()

        if cropped is None:
            messagebox.showwarning("Chưa crop", "Vui lòng chọn vùng crop trước!")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
            initialfile=f"cropped_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        )

        if filepath:
            cv2.imwrite(filepath, cropped)
            messagebox.showinfo("Thành công", f"Đã lưu ảnh crop:\n{filepath}")
            self.status_label.config(text=f"✓ Đã lưu crop: {os.path.basename(filepath)}", bg="#27ae60")

    def browse_folder(self):
        """Chọn thư mục"""
        folder = filedialog.askdirectory()
        if folder:
            self.folder_entry.delete(0, tk.END)
            self.folder_entry.insert(0, folder)

    def quick_save_original(self):
        """Lưu nhanh ảnh gốc"""
        if self.current_screenshot is None:
            messagebox.showwarning("Chưa có ảnh", "Vui lòng chụp màn hình trước!")
            return

        folder = self.folder_entry.get()
        filename = self.filename_entry.get()

        if not filename:
            messagebox.showwarning("Chưa có tên", "Vui lòng nhập tên file!")
            return

        os.makedirs(folder, exist_ok=True)
        filepath = os.path.join(folder, f"{filename}.png")

        cv2.imwrite(filepath, self.current_screenshot)
        messagebox.showinfo("Thành công", f"Đã lưu:\n{filepath}")
        self.status_label.config(text=f"✓ Đã lưu: {filename}.png", bg="#27ae60")

        # Auto increment filename
        self.filename_entry.delete(0, tk.END)
        self.filename_entry.insert(0, f"screenshot_{datetime.now().strftime('%H%M%S')}")

    def quick_save_cropped(self):
        """Lưu nhanh ảnh crop"""
        cropped = self.get_cropped_image()

        if cropped is None:
            messagebox.showwarning("Chưa crop", "Vui lòng chọn vùng crop trước!")
            return

        folder = self.folder_entry.get()
        filename = self.filename_entry.get()

        if not filename:
            messagebox.showwarning("Chưa có tên", "Vui lòng nhập tên file!")
            return

        os.makedirs(folder, exist_ok=True)
        filepath = os.path.join(folder, f"{filename}.png")

        cv2.imwrite(filepath, cropped)
        messagebox.showinfo("Thành công", f"Đã lưu crop:\n{filepath}")
        self.status_label.config(text=f"✓ Đã lưu crop: {filename}.png", bg="#27ae60")

        # Auto increment filename
        self.filename_entry.delete(0, tk.END)
        self.filename_entry.insert(0, f"screenshot_{datetime.now().strftime('%H%M%S')}")

    def quick_crop(self):
        """Crop nhanh các vùng preset"""
        messagebox.showinfo("Crop nhanh", "Tính năng này sẽ có trong phiên bản sau!")

    def update_info(self, text):
        """Update info text"""
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(1.0, text)

    def show_help(self):
        """Hiển thị hướng dẫn"""
        help_text = """
🖼️ HƯỚNG DẪN SỬ DỤNG

1️⃣ Chụp màn hình:
   - Bấm F2 hoặc nút "Chụp"
   - Ảnh sẽ hiển thị trên canvas

2️⃣ Crop vùng ảnh:
   - Click và kéo chuột trên ảnh
   - Hoặc nhập tọa độ thủ công
   - Rectangle đỏ sẽ hiển thị vùng crop

3️⃣ Lưu ảnh:
   - Lưu ảnh gốc: Ctrl+S
   - Lưu ảnh crop: Ctrl+Shift+S
   - Hoặc dùng nút "Lưu nhanh"

4️⃣ Lưu nhanh:
   - Nhập tên file
   - Chọn thư mục (mặc định: assets/screenshots)
   - Bấm nút tương ứng

📌 Phím tắt:
   F2: Chụp màn hình
   Ctrl+S: Lưu ảnh gốc
   Ctrl+Shift+S: Lưu ảnh crop
   Esc: Reset crop

💡 Tips:
   - Dùng scroll để xem ảnh lớn
   - Crop chính xác bằng cách nhập tọa độ
   - Tên file tự động tăng sau khi lưu
        """
        messagebox.showinfo("Hướng dẫn", help_text)

    def run(self):
        """Chạy ứng dụng"""
        self.root.mainloop()


if __name__ == "__main__":
    app = ScreenshotTool()
    app.run()
