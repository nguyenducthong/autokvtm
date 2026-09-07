import os
import sys
import time
import logging
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk

import cv2
from core.adb_helper import get_adb_helper
from core.adb import ADBController
from core.image import ImageProcessor, get_resource_path
from gui.constants import BASE_DIR, ITEMS_DIR

logger = logging.getLogger(__name__)


class MatchTestTabMixin:
    """Tab 5: Thử nghiệm so sánh và khớp ảnh mẫu (Template Matching)."""
    def _build_tab_match_test(self):
        self.img_processor = ImageProcessor()
        self.mt_screenshot = None
        self.mt_drawn_img = None
        self.mt_template_path = ""
        self.mt_template_img = None
        self.mt_photo = None
        self.mt_devices_list = []
        self.mt_adb = None
        self.mt_templates_list = []

        pad = tk.Frame(self.tab_match_test, bg="#ecf0f1")
        pad.pack(fill=tk.BOTH, expand=True)

        # Toolbar
        toolbar = tk.Frame(pad, bg="#2c3e50", height=50)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)

        # 1. Device selection & Capture
        tk.Label(toolbar, text="Thiết bị:", font=("Arial", 9, "bold"),
                 bg="#2c3e50", fg="white").pack(side=tk.LEFT, padx=(10, 2))
        self.mt_device_var = tk.StringVar()
        self.mt_device_combo = ttk.Combobox(toolbar, textvariable=self.mt_device_var,
                                             state="readonly", width=22, font=("Arial", 9))
        self.mt_device_combo.pack(side=tk.LEFT, padx=3, pady=10)

        tk.Button(toolbar, text="🔄", command=self._mt_refresh_devices,
                  bg="#1abc9c", fg="white", relief=tk.FLAT, padx=6,
                  font=("Arial", 9), cursor="hand2").pack(side=tk.LEFT, padx=2, pady=10)

        tk.Button(toolbar, text="📸 Chụp LD (F3)", command=self._mt_take_screenshot,
                  bg="#3498db", fg="white", relief=tk.FLAT, padx=10,
                  font=("Arial", 9, "bold"), cursor="hand2").pack(side=tk.LEFT, padx=4, pady=8)

        tk.Button(toolbar, text="📁 Mở ảnh...", command=self._mt_load_screenshot_file,
                  bg="#7f8c8d", fg="white", relief=tk.FLAT, padx=8,
                  font=("Arial", 9), cursor="hand2").pack(side=tk.LEFT, padx=2, pady=8)

        # Separator
        tk.Frame(toolbar, bg="#7f8c8d", width=2).pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=8)

        # 2. Template selector
        tk.Label(toolbar, text="Ảnh mẫu:", font=("Arial", 9, "bold"),
                 bg="#2c3e50", fg="white").pack(side=tk.LEFT, padx=(4, 2))
        self.mt_tpl_var = tk.StringVar()
        self.mt_tpl_combo = ttk.Combobox(toolbar, textvariable=self.mt_tpl_var,
                                          width=28, font=("Arial", 9))
        self.mt_tpl_combo.pack(side=tk.LEFT, padx=3, pady=10)
        self.mt_tpl_combo.bind("<<ComboboxSelected>>", self._mt_on_template_selected)
        self.mt_tpl_combo.bind("<Return>", lambda _: self._mt_on_template_selected())

        tk.Button(toolbar, text="📂 Chọn file...", command=self._mt_browse_template,
                  bg="#e67e22", fg="white", relief=tk.FLAT, padx=8,
                  font=("Arial", 9), cursor="hand2").pack(side=tk.LEFT, padx=2, pady=8)

        # Separator
        tk.Frame(toolbar, bg="#7f8c8d", width=2).pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=8)

        # 3. Thresholds & Mode
        tk.Label(toolbar, text="Shape:", font=("Arial", 9),
                 bg="#2c3e50", fg="#bdc3c7").pack(side=tk.LEFT, padx=(4, 1))
        self.mt_thresh_var = tk.DoubleVar(value=0.75)
        self.mt_thresh_spin = ttk.Spinbox(toolbar, from_=0.1, to=1.0, increment=0.05,
                                          textvariable=self.mt_thresh_var, width=5, font=("Arial", 9))
        self.mt_thresh_spin.pack(side=tk.LEFT, padx=2, pady=10)

        tk.Label(toolbar, text="Color:", font=("Arial", 9),
                 bg="#2c3e50", fg="#bdc3c7").pack(side=tk.LEFT, padx=(4, 1))
        self.mt_color_thresh_var = tk.DoubleVar(value=0.60)
        self.mt_color_thresh_spin = ttk.Spinbox(toolbar, from_=0.1, to=1.0, increment=0.05,
                                                textvariable=self.mt_color_thresh_var, width=5, font=("Arial", 9))
        self.mt_color_thresh_spin.pack(side=tk.LEFT, padx=2, pady=10)

        self.mt_find_all_var = tk.BooleanVar(value=False)
        tk.Checkbutton(toolbar, text="Tìm tất cả", variable=self.mt_find_all_var,
                       bg="#2c3e50", fg="white", selectcolor="#34495e",
                       activebackground="#2c3e50", activeforeground="white",
                       font=("Arial", 8)).pack(side=tk.LEFT, padx=(6, 2))

        # 4. Action Match & Save
        tk.Button(toolbar, text="⚡ So Sánh Ngay", command=self._mt_run_match,
                  bg="#27ae60", fg="white", relief=tk.FLAT, padx=12,
                  font=("Arial", 9, "bold"), cursor="hand2").pack(side=tk.RIGHT, padx=(4, 10), pady=8)

        tk.Button(toolbar, text="💾 Lưu ảnh KQ", command=self._mt_save_result_image,
                  bg="#8e44ad", fg="white", relief=tk.FLAT, padx=8,
                  font=("Arial", 9), cursor="hand2").pack(side=tk.RIGHT, padx=4, pady=8)

        self.root.bind('<F3>', lambda _: self._mt_take_screenshot())

        # Main layout: Horizontal PanedWindow (Left: Canvas, Right: Info/Preview)
        paned = tk.PanedWindow(pad, orient=tk.HORIZONTAL, bg="#bdc3c7", bd=0, sashwidth=5)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left: Canvas area with scrollbars & status bar
        left_frame = tk.Frame(paned, bg="#34495e")
        paned.add(left_frame, minsize=500)

        canvas_header = tk.Frame(left_frame, bg="#34495e", height=28)
        canvas_header.pack(fill=tk.X, padx=8, pady=(4, 0))
        self.mt_canvas_title = tk.Label(canvas_header, text="Màn hình LDPlayer (Chưa có ảnh. Ấn F3 hoặc Chụp)",
                                        font=("Arial", 9, "bold"), bg="#34495e", fg="white")
        self.mt_canvas_title.pack(side=tk.LEFT)

        canvas_container = tk.Frame(left_frame, bg="#2c3e50")
        canvas_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        h_scroll = tk.Scrollbar(canvas_container, orient=tk.HORIZONTAL)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        v_scroll = tk.Scrollbar(canvas_container, orient=tk.VERTICAL)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.mt_canvas = tk.Canvas(canvas_container, bg="#1e272e", cursor="crosshair",
                                   xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        self.mt_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        h_scroll.config(command=self.mt_canvas.xview)
        v_scroll.config(command=self.mt_canvas.yview)

        self.mt_canvas.bind("<Motion>", self._mt_on_canvas_mouse_move)

        # Canvas bottom info bar (Cursor pos & RGB)
        canvas_footer = tk.Frame(left_frame, bg="#2c3e50", height=24)
        canvas_footer.pack(fill=tk.X, padx=8, pady=(0, 4))
        self.mt_pixel_info = tk.Label(canvas_footer, text="Tọa độ: (0, 0) | RGB: (0, 0, 0)",
                                      font=("Consolas", 9), bg="#2c3e50", fg="#ecf0f1")
        self.mt_pixel_info.pack(side=tk.LEFT)

        # Right: Info & Preview Panel
        right_frame = tk.Frame(paned, bg="#ffffff", bd=1, relief=tk.GROOVE)
        paned.add(right_frame, minsize=380)

        # Right scrollable area
        right_canvas = tk.Canvas(right_frame, bg="#ffffff", bd=0, highlightthickness=0)
        right_scroll = tk.Scrollbar(right_frame, orient=tk.VERTICAL, command=right_canvas.yview)
        self.mt_scrollable_frame = tk.Frame(right_canvas, bg="#ffffff", padx=10, pady=10)

        self.mt_scrollable_frame.bind(
            "<Configure>",
            lambda e: right_canvas.configure(scrollregion=right_canvas.bbox("all"))
        )
        right_canvas.create_window((0, 0), window=self.mt_scrollable_frame, anchor="nw")
        right_canvas.configure(yscrollcommand=right_scroll.set)

        right_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        right_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Card 1: Template Preview
        tpl_card = tk.LabelFrame(self.mt_scrollable_frame, text="🖼️ Ảnh Mẫu Đang Chọn",
                                 font=("Arial", 10, "bold"), bg="#ffffff", fg="#2c3e50", padx=8, pady=6)
        tpl_card.pack(fill=tk.X, pady=(0, 8))

        tpl_preview_row = tk.Frame(tpl_card, bg="#ffffff")
        tpl_preview_row.pack(fill=tk.X)

        self.mt_tpl_preview_box = tk.Label(tpl_preview_row, text="Chưa chọn\nảnh mẫu",
                                           bg="#f1f2f6", fg="#747d8c", width=12, height=5,
                                           relief=tk.SUNKEN, bd=1)
        self.mt_tpl_preview_box.pack(side=tk.LEFT, padx=(0, 8))

        tpl_info_col = tk.Frame(tpl_preview_row, bg="#ffffff")
        tpl_info_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.mt_tpl_name_lbl = tk.Label(tpl_info_col, text="Tên: (Chưa chọn)", font=("Arial", 9, "bold"),
                                        bg="#ffffff", fg="#2f3542", anchor=tk.W)
        self.mt_tpl_name_lbl.pack(fill=tk.X)

        self.mt_tpl_size_lbl = tk.Label(tpl_info_col, text="Kích thước: --", font=("Arial", 8),
                                        bg="#ffffff", fg="#57606f", anchor=tk.W)
        self.mt_tpl_size_lbl.pack(fill=tk.X)

        self.mt_tpl_path_lbl = tk.Label(tpl_info_col, text="Đường dẫn: --", font=("Consolas", 8),
                                        bg="#ffffff", fg="#747d8c", wraplength=200, justify=tk.LEFT, anchor=tk.W)
        self.mt_tpl_path_lbl.pack(fill=tk.X)

        # Card 2: Match Results
        res_card = tk.LabelFrame(self.mt_scrollable_frame, text="📊 Kết Quả So Khớp",
                                 font=("Arial", 10, "bold"), bg="#ffffff", fg="#2c3e50", padx=8, pady=6)
        res_card.pack(fill=tk.X, pady=(0, 8))

        self.mt_status_banner = tk.Label(res_card, text="Chờ thực hiện so sánh",
                                         font=("Arial", 10, "bold"), bg="#95a5a6", fg="white",
                                         pady=4, relief=tk.FLAT)
        self.mt_status_banner.pack(fill=tk.X, pady=(0, 6))

        # Metrics grid
        metrics_frame = tk.Frame(res_card, bg="#f8f9fa", bd=1, relief=tk.SOLID, padx=6, pady=6)
        metrics_frame.pack(fill=tk.X)

        # Row 0: Center & Box
        tk.Label(metrics_frame, text="Tọa độ tâm:", font=("Arial", 9, "bold"), bg="#f8f9fa").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.mt_res_center_lbl = tk.Label(metrics_frame, text="--", font=("Consolas", 9, "bold"), bg="#f8f9fa", fg="#2980b9")
        self.mt_res_center_lbl.grid(row=0, column=1, sticky=tk.W, pady=2, padx=4)

        tk.Label(metrics_frame, text="Vùng quét Box:", font=("Arial", 9), bg="#f8f9fa").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.mt_res_box_lbl = tk.Label(metrics_frame, text="--", font=("Consolas", 9), bg="#f8f9fa", fg="#2c3e50")
        self.mt_res_box_lbl.grid(row=1, column=1, sticky=tk.W, pady=2, padx=4)

        # Row 2: Shape score
        tk.Label(metrics_frame, text="Điểm Shape (Hình):", font=("Arial", 9), bg="#f8f9fa").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.mt_res_shape_lbl = tk.Label(metrics_frame, text="--", font=("Consolas", 9), bg="#f8f9fa")
        self.mt_res_shape_lbl.grid(row=2, column=1, sticky=tk.W, pady=2, padx=4)

        # Row 3: Color score
        tk.Label(metrics_frame, text="Điểm Color (Màu):", font=("Arial", 9), bg="#f8f9fa").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.mt_res_color_lbl = tk.Label(metrics_frame, text="--", font=("Consolas", 9), bg="#f8f9fa")
        self.mt_res_color_lbl.grid(row=3, column=1, sticky=tk.W, pady=2, padx=4)

        # Row 4: Combined score
        tk.Label(metrics_frame, text="Điểm Tổng Hợp:", font=("Arial", 9, "bold"), bg="#f8f9fa").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.mt_res_comb_lbl = tk.Label(metrics_frame, text="--", font=("Consolas", 10, "bold"), bg="#f8f9fa", fg="#27ae60")
        self.mt_res_comb_lbl.grid(row=4, column=1, sticky=tk.W, pady=2, padx=4)

        # Row 5: Time elapsed
        tk.Label(metrics_frame, text="Thời gian xử lý:", font=("Arial", 9), bg="#f8f9fa").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.mt_res_time_lbl = tk.Label(metrics_frame, text="--", font=("Consolas", 9), bg="#f8f9fa", fg="#7f8c8d")
        self.mt_res_time_lbl.grid(row=5, column=1, sticky=tk.W, pady=2, padx=4)

        # Card 3: Visual Comparison (Template vs Matched region)
        cmp_card = tk.LabelFrame(self.mt_scrollable_frame, text="🔍 Đối Chiếu Trực Quan",
                                 font=("Arial", 10, "bold"), bg="#ffffff", fg="#2c3e50", padx=8, pady=6)
        cmp_card.pack(fill=tk.X, pady=(0, 8))

        cmp_box_frame = tk.Frame(cmp_card, bg="#ffffff")
        cmp_box_frame.pack(fill=tk.X, pady=2)

        # Template Col
        col_tpl = tk.Frame(cmp_box_frame, bg="#ffffff")
        col_tpl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(col_tpl, text="Ảnh Mẫu (Template)", font=("Arial", 8, "bold"), bg="#ffffff", fg="#2c3e50").pack()
        self.mt_cmp_tpl_box = tk.Label(col_tpl, text="--", bg="#f1f2f6", relief=tk.SUNKEN, bd=1, width=12, height=5)
        self.mt_cmp_tpl_box.pack(pady=2)

        # Arrow
        tk.Label(cmp_box_frame, text="↔️", font=("Arial", 12), bg="#ffffff").pack(side=tk.LEFT, padx=4)

        # Crop Col
        col_crop = tk.Frame(cmp_box_frame, bg="#ffffff")
        col_crop.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(col_crop, text="Vùng Tìm Thấy", font=("Arial", 8, "bold"), bg="#ffffff", fg="#27ae60").pack()
        self.mt_cmp_crop_box = tk.Label(col_crop, text="--", bg="#f1f2f6", relief=tk.SUNKEN, bd=1, width=12, height=5)
        self.mt_cmp_crop_box.pack(pady=2)

        # Card 4: Candidates & Details Log
        log_card = tk.LabelFrame(self.mt_scrollable_frame, text="📝 Chi Tiết Ứng Viên / Nhật Ký Quét",
                                 font=("Arial", 10, "bold"), bg="#ffffff", fg="#2c3e50", padx=8, pady=6)
        log_card.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        self.mt_log_text = tk.Text(log_card, font=("Consolas", 8), bg="#f8f9fa", height=8, wrap=tk.WORD)
        log_scroll = tk.Scrollbar(log_card, command=self.mt_log_text.yview)
        self.mt_log_text.config(yscrollcommand=log_scroll.set)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.mt_log_text.pack(fill=tk.BOTH, expand=True)

        # Populate templates list and refresh devices
        self._mt_populate_templates()
        self._mt_refresh_devices()

    # --- Match test tab helper methods ---
    def _mt_populate_templates(self):
        items_dir = "assets/items"
        tpl_files = []
        if os.path.exists(items_dir):
            for root_dir, _, files in os.walk(items_dir):
                for f in files:
                    if f.lower().endswith(".png"):
                        full_path = os.path.join(root_dir, f).replace("\\", "/")
                        tpl_files.append(full_path)
        tpl_files.sort()
        self.mt_templates_list = tpl_files
        self.mt_tpl_combo["values"] = tpl_files
        if tpl_files:
            default_tpl = "assets/items/core_chest.png"
            if default_tpl in tpl_files:
                self.mt_tpl_combo.set(default_tpl)
            else:
                self.mt_tpl_combo.set(tpl_files[0])
            self._mt_on_template_selected()

    def _mt_refresh_devices(self):
        try:
            if not getattr(self.adb_helper, "adb_path", None):
                raise FileNotFoundError("Không tìm thấy ADB")
            serials = self.adb_helper.get_devices()
            self.mt_devices_list = []
            names = []
            for s in serials:
                name = self.adb_helper.get_device_name(s)
                self.mt_devices_list.append({"serial": s, "name": name})
                names.append(f"{name} ({s})")
            self.mt_device_combo["values"] = names
            if names:
                self.mt_device_combo.current(0)
            self.mt_adb = None
        except Exception as e:
            self.mt_device_combo["values"] = []
            self.mt_devices_list = []

    def _mt_get_adb(self):
        idx = self.mt_device_combo.current()
        if 0 <= idx < len(self.mt_devices_list):
            dev = self.mt_devices_list[idx]
            if self.mt_adb is None or self.mt_adb.serial != dev["serial"]:
                self.mt_adb = ADBController(serial=dev["serial"])
            return self.mt_adb
        messagebox.showwarning("Thiếu thiết bị", "Vui lòng chọn hoặc làm mới danh sách thiết bị LDPlayer!")
        return None

    def _mt_take_screenshot(self):
        adb = self._mt_get_adb()
        if not adb:
            return
        try:
            self.status_label.config(text="Đang chụp LDPlayer...", bg="#f39c12")
            self.root.update()
            os.makedirs("cache", exist_ok=True)
            img = adb.screenshot_full("cache/screenshot_match_test.png")
            if img is None:
                raise Exception("Không nhận được dữ liệu ảnh từ thiết bị.")
            self.mt_screenshot = img
            self.mt_drawn_img = img.copy()
            self._mt_display_screenshot(img)
            h, w = img.shape[:2]
            self.mt_canvas_title.config(text=f"Màn hình LDPlayer: {w}x{h} px")
            self.status_label.config(text="Đã chụp màn hình LDPlayer", bg="#27ae60")
            if self.mt_template_path:
                self._mt_run_match()
        except Exception as e:
            messagebox.showerror("Lỗi chụp ảnh", f"Không thể chụp màn hình từ LDPlayer:\n{e}")
            self.status_label.config(text="Lỗi chụp ảnh", bg="#e74c3c")

    def _mt_load_screenshot_file(self):
        path = filedialog.askopenfilename(
            title="Chọn ảnh màn hình",
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp"), ("All files", "*.*")]
        )
        if not path:
            return
        img = cv2.imread(path)
        if img is None:
            messagebox.showerror("Lỗi", f"Không thể đọc file ảnh:\n{path}")
            return
        self.mt_screenshot = img
        self.mt_drawn_img = img.copy()
        self._mt_display_screenshot(img)
        h, w = img.shape[:2]
        self.mt_canvas_title.config(text=f"Ảnh từ máy tính: {os.path.basename(path)} ({w}x{h} px)")
        if self.mt_template_path:
            self._mt_run_match()

    def _mt_browse_template(self):
        initial = "assets/items" if os.path.exists("assets/items") else "."
        path = filedialog.askopenfilename(
            initialdir=initial,
            title="Chọn ảnh mẫu so sánh",
            filetypes=[("PNG images", "*.png"), ("All images", "*.png;*.jpg;*.jpeg;*.bmp")]
        )
        if not path:
            return
        try:
            rel_path = os.path.relpath(path, os.getcwd()).replace("\\", "/")
        except Exception:
            rel_path = path.replace("\\", "/")
        self.mt_tpl_var.set(rel_path)
        self._mt_on_template_selected()

    def _mt_on_template_selected(self, event=None):
        path = self.mt_tpl_var.get().strip()
        if not path:
            return
        self.mt_template_path = path
        res_path = get_resource_path(path)
        tpl = cv2.imread(res_path, cv2.IMREAD_UNCHANGED)
        if tpl is None:
            self.mt_tpl_name_lbl.config(text=f"Tên: {os.path.basename(path)} (Không đọc được)")
            self.mt_tpl_size_lbl.config(text="Kích thước: Lỗi")
            self.mt_tpl_path_lbl.config(text=f"Đường dẫn: {path}")
            self.mt_tpl_preview_box.config(image="", text="Lỗi đọc\nảnh")
            self.mt_cmp_tpl_box.config(image="", text="Lỗi")
            return

        self.mt_template_img = tpl
        th, tw = tpl.shape[:2]
        channels = "BGRA (có alpha)" if tpl.ndim == 3 and tpl.shape[2] == 4 else ("BGR" if tpl.ndim == 3 else "Grayscale")
        self.mt_tpl_name_lbl.config(text=f"Tên: {os.path.basename(path)}")
        self.mt_tpl_size_lbl.config(text=f"Kích thước: {tw}x{th} px | Kênh: {channels}")
        self.mt_tpl_path_lbl.config(text=f"Đường dẫn: {path}")

        self._mt_render_preview_box(tpl, self.mt_tpl_preview_box, max_size=(90, 80))
        self._mt_render_preview_box(tpl, self.mt_cmp_tpl_box, max_size=(90, 80))

        if self.mt_screenshot is not None:
            self._mt_run_match()

    def _mt_render_preview_box(self, img_np, label_widget, max_size=(90, 80)):
        if img_np is None:
            label_widget.config(image="", text="Không có")
            return
        try:
            if img_np.ndim == 3 and img_np.shape[2] == 4:
                rgb = cv2.cvtColor(img_np[:, :, :3], cv2.COLOR_BGR2RGB)
                pil = Image.fromarray(rgb)
            elif img_np.ndim == 3:
                rgb = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
                pil = Image.fromarray(rgb)
            else:
                pil = Image.fromarray(img_np)

            pil.thumbnail(max_size, Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(pil)
            label_widget.image = photo
            label_widget.config(image=photo, text="")
        except Exception as e:
            label_widget.config(image="", text="Lỗi xem")

    def _mt_display_screenshot(self, img_bgr):
        try:
            rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            pil = Image.fromarray(rgb)
            self.mt_photo = ImageTk.PhotoImage(pil)
            self.mt_canvas.delete("all")
            self.mt_canvas.config(scrollregion=(0, 0, pil.width, pil.height))
            self.mt_canvas.create_image(0, 0, anchor=tk.NW, image=self.mt_photo)
        except Exception as e:
            logger.error(f"Lỗi hiển thị screenshot: {e}")

    def _mt_on_canvas_mouse_move(self, event):
        if self.mt_screenshot is None:
            return
        try:
            cx = int(self.mt_canvas.canvasx(event.x))
            cy = int(self.mt_canvas.canvasy(event.y))
            h, w = self.mt_screenshot.shape[:2]
            if 0 <= cx < w and 0 <= cy < h:
                b, g, r = [int(v) for v in self.mt_screenshot[cy, cx][:3]]
                hex_color = f"#{r:02x}{g:02x}{b:02x}".upper()
                self.mt_pixel_info.config(
                    text=f"Tọa độ: ({cx}, {cy}) | RGB: ({r}, {g}, {b}) | Hex: {hex_color}"
                )
        except Exception:
            pass

    def _mt_run_match(self):
        if self.mt_screenshot is None:
            messagebox.showinfo("Chưa có ảnh", "Vui lòng chụp màn hình LDPlayer (F3) hoặc mở ảnh từ máy tính trước!")
            return
        if not self.mt_template_path:
            messagebox.showinfo("Chưa chọn mẫu", "Vui lòng chọn một ảnh mẫu để so sánh!")
            return

        try:
            thresh = float(self.mt_thresh_var.get())
        except Exception:
            thresh = 0.75
            self.mt_thresh_var.set(0.75)

        try:
            color_thresh = float(self.mt_color_thresh_var.get())
        except Exception:
            color_thresh = 0.60
            self.mt_color_thresh_var.set(0.60)

        find_all = self.mt_find_all_var.get()

        t_start = time.time()
        detail = self.img_processor.find_template_color_detail(
            template_path=self.mt_template_path,
            threshold=thresh,
            color_threshold=color_thresh,
            screen_img=self.mt_screenshot,
            find_all=find_all
        )
        elapsed_ms = (time.time() - t_start) * 1000

        img_draw = self.mt_screenshot.copy()
        tpl_name = os.path.basename(self.mt_template_path)

        self.mt_log_text.delete("1.0", tk.END)
        self.mt_log_text.insert(tk.END, f"=== KẾT QUẢ QUÉT ẢNH [{tpl_name}] ===\n")
        self.mt_log_text.insert(tk.END, f"Ngưỡng Shape: {thresh:.2f} | Ngưỡng Color: {color_thresh:.2f}\n")
        self.mt_log_text.insert(tk.END, f"Thời gian: {elapsed_ms:.1f} ms | Số ứng viên hình dạng: {detail.get('candidates_count', 0)}\n\n")

        if detail.get("found"):
            all_matches = detail.get("all_matches", [detail])
            count = len(all_matches)

            if count == 1:
                self.mt_status_banner.config(
                    text=f"✅ TÌM THẤY 1 VỊ TRÍ (Combined: {detail['combined_score']:.3f})",
                    bg="#27ae60"
                )
            else:
                self.mt_status_banner.config(
                    text=f"✅ TÌM THẤY {count} VỊ TRÍ PHÙ HỢP",
                    bg="#27ae60"
                )

            cx, cy = detail["center"]
            bx, by, bw, bh = detail["box"]
            self.mt_res_center_lbl.config(text=f"X={cx}, Y={cy}")
            self.mt_res_box_lbl.config(text=f"[{bx}, {by}, {bw}, {bh}]")
            self.mt_res_shape_lbl.config(text=f"{detail['shape_score']:.3f} (>= {thresh:.2f})", fg="#27ae60")
            self.mt_res_color_lbl.config(text=f"{detail['color_score']:.3f} (>= {color_thresh:.2f})", fg="#27ae60")
            self.mt_res_comb_lbl.config(text=f"{detail['combined_score']:.3f}", fg="#27ae60")
            self.mt_res_time_lbl.config(text=f"{elapsed_ms:.1f} ms")

            for i, m in enumerate(all_matches, 1):
                mx, my, mw, mh = m["x"], m["y"], m["w"], m["h"]
                mcx, mcy = m["center"]

                cv2.rectangle(img_draw, (mx, my), (mx + mw, my + mh), (0, 255, 0), 3)

                cv2.circle(img_draw, (mcx, mcy), 6, (0, 0, 255), -1)
                cv2.line(img_draw, (mcx - 12, mcy), (mcx + 12, mcy), (0, 0, 255), 2)
                cv2.line(img_draw, (mcx, mcy - 12), (mcx, mcy + 12), (0, 0, 255), 2)

                lbl_text = f"#{i} {tpl_name}: {m['combined_score']:.2f} (S:{m['shape_score']:.2f} C:{m['color_score']:.2f})"
                label_y = max(my - 8, 20)
                (tw_txt, th_txt), _ = cv2.getTextSize(lbl_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(img_draw, (mx, label_y - th_txt - 4), (mx + tw_txt + 6, label_y + 4), (0, 0, 0), -1)
                cv2.putText(img_draw, lbl_text, (mx + 3, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)

                self.mt_log_text.insert(
                    tk.END,
                    f"#{i}: Tâm ({mcx}, {mcy}) | Box [{mx}, {my}, {mw}, {mh}] | Shape={m['shape_score']:.3f}, Color={m['color_score']:.3f}, Comb={m['combined_score']:.3f}\n"
                )

            matched_region = detail.get("matched_region")
            if matched_region is not None:
                self._mt_render_preview_box(matched_region, self.mt_cmp_crop_box, max_size=(90, 80))
            else:
                self.mt_cmp_crop_box.config(image="", text="--")

        else:
            reason = detail.get("reason", "Không tìm thấy")
            self.mt_status_banner.config(text=f"❌ KHÔNG TÌM THẤY ({reason})", bg="#e74c3c")
            self.mt_res_center_lbl.config(text="--")
            self.mt_res_box_lbl.config(text="--")
            self.mt_res_shape_lbl.config(text="--", fg="#2c3e50")
            self.mt_res_color_lbl.config(text="--", fg="#2c3e50")
            self.mt_res_comb_lbl.config(text="--", fg="#2c3e50")
            self.mt_res_time_lbl.config(text=f"{elapsed_ms:.1f} ms")
            self.mt_cmp_crop_box.config(image="", text="Không tìm thấy")

            self.mt_log_text.insert(tk.END, f"❌ Lý do: {reason}\n")
            best_rej = detail.get("best_rejected")
            if best_rej:
                self.mt_log_text.insert(
                    tk.END,
                    f"Ứng viên cao nhất bị loại: Tâm ({best_rej['center'][0]}, {best_rej['center'][1]}) | Shape={best_rej['shape_score']:.3f} | Color={best_rej['color_score']:.3f} (< {color_thresh:.2f})\n"
                )

        self.mt_drawn_img = img_draw
        self._mt_display_screenshot(img_draw)

    def _mt_save_result_image(self):
        if self.mt_drawn_img is None:
            messagebox.showinfo("Thông báo", "Chưa có ảnh kết quả để lưu!")
            return
        os.makedirs("debug/match_results", exist_ok=True)
        default_name = f"match_{int(time.time())}.png"
        path = filedialog.asksaveasfilename(
            initialdir="debug/match_results",
            initialfile=default_name,
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png"), ("JPEG Image", "*.jpg")]
        )
        if not path:
            return
        try:
            cv2.imwrite(path, self.mt_drawn_img)
            messagebox.showinfo("Thành công", f"Đã lưu ảnh kết quả tại:\n{path}")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể lưu file ảnh:\n{e}")

    # ----------------------------------------------------------------
