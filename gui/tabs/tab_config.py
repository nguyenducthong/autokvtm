import os
import sys
import json
import copy
import logging
import glob as glob_mod
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk

from config import CONFIG_LOAI_KHO, REGION_PRESETS, REGION_FROM_CROP
from gui.constants import (
    BASE_DIR, CONFIG_DIR, ITEMS_DIR, DEFAULT_SETTINGS, DEFAULT_BAN_DO,
    scan_all_templates, scan_kho_templates, normalize_region, format_region, scan_row_templates
)
from gui.widgets import AutocompleteCombobox, TreeTooltip

logger = logging.getLogger(__name__)


class ConfigTabMixin:
    """Tab 2: Tạo, sửa, xóa cấu hình và cài đặt bán đồ, công thức thông minh."""
    def _build_tab_config(self):
        # Scrollable container
        canvas_outer = tk.Canvas(self.tab_config, bg="#ecf0f1", highlightthickness=0)
        scrollbar = tk.Scrollbar(self.tab_config, orient=tk.VERTICAL, command=canvas_outer.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas_outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        canvas_outer.configure(yscrollcommand=scrollbar.set)

        pad = tk.Frame(canvas_outer, bg="#ecf0f1", padx=15, pady=10)
        canvas_outer.create_window((0, 0), window=pad, anchor=tk.NW)
        pad.bind("<Configure>", lambda e: canvas_outer.configure(scrollregion=canvas_outer.bbox("all")))
        canvas_outer.bind_all("<MouseWheel>",
            lambda e: canvas_outer.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        # ===== Top: config name + save/load =====
        top = tk.Frame(pad, bg="#ecf0f1")
        top.pack(fill=tk.X, pady=(0, 8))

        tk.Label(top, text="Tên cấu hình:", bg="#ecf0f1", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        self.cfg_name_entry = tk.Entry(top, font=("Arial", 10), width=25)
        self.cfg_name_entry.pack(side=tk.LEFT, padx=8)
        self.cfg_name_entry.insert(0, "config_moi")

        tk.Button(top, text="Lưu", command=self._save_config, bg="#27ae60", fg="white",
                  relief=tk.FLAT, cursor="hand2", padx=12, font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="Tải cấu hình", command=self._load_config_to_editor, bg="#3498db", fg="white",
                  relief=tk.FLAT, cursor="hand2", padx=12, font=("Arial", 10)).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="Xóa file", command=self._delete_config_file, bg="#e74c3c", fg="white",
                  relief=tk.FLAT, cursor="hand2", padx=12, font=("Arial", 10)).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="⚡ Chu trình tự động", command=self._open_smart_recipe_dialog, bg="#8e44ad", fg="white",
                  relief=tk.FLAT, cursor="hand2", padx=12, font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=8)

        self.cfg_load_var = tk.StringVar()
        self.cfg_load_combo = ttk.Combobox(top, textvariable=self.cfg_load_var, state="readonly",
                                            width=20, font=("Arial", 9))
        self.cfg_load_combo.pack(side=tk.RIGHT)
        tk.Label(top, text="Tệp:", bg="#ecf0f1", font=("Arial", 9)).pack(side=tk.RIGHT, padx=(0, 4))
        self._refresh_cfg_load_combo()

        # ===== SECTION 1: SETTINGS (toggles + loop) =====
        settings_frame = tk.LabelFrame(pad, text="Cài đặt chung", font=("Arial", 10, "bold"),
                                        bg="#ecf0f1", padx=10, pady=8)
        settings_frame.pack(fill=tk.X, pady=(0, 8))

        # Lặp tong
        loop_tong_row = tk.Frame(settings_frame, bg="#ecf0f1")
        loop_tong_row.pack(fill=tk.X, pady=3)
        tk.Label(loop_tong_row, text="Lặp tổng:", bg="#ecf0f1", width=18, anchor=tk.W).pack(side=tk.LEFT)
        self.loop_tong_mode_var = tk.StringVar(value="count")
        tk.Radiobutton(loop_tong_row, text="Số lần:", variable=self.loop_tong_mode_var,
                       value="count", bg="#ecf0f1", font=("Arial", 9)).pack(side=tk.LEFT)
        self.loop_tong_var = tk.StringVar(value="1")
        self.loop_tong_spin = tk.Spinbox(loop_tong_row, from_=1, to=9999,
                                          textvariable=self.loop_tong_var, width=6,
                                          font=("Arial", 10))
        self.loop_tong_spin.pack(side=tk.LEFT, padx=(0, 12))
        tk.Radiobutton(loop_tong_row, text="Chạy mãi", variable=self.loop_tong_mode_var,
                       value="forever", bg="#ecf0f1", font=("Arial", 9)).pack(side=tk.LEFT)

        # Lặp TC+MAY
        loop_row = tk.Frame(settings_frame, bg="#ecf0f1")
        loop_row.pack(fill=tk.X, pady=3)
        tk.Label(loop_row, text="Lặp TC+MÁY:", bg="#ecf0f1", width=18, anchor=tk.W).pack(side=tk.LEFT)
        self.loop_var = tk.StringVar(value="1")
        tk.Spinbox(loop_row, from_=1, to=999, textvariable=self.loop_var, width=6,
                   font=("Arial", 10)).pack(side=tk.LEFT)
        tk.Label(loop_row, text="(Trồng+máy bao nhiêu lần rồi bán 1 lần)", bg="#ecf0f1",
                 fg="#7f8c8d", font=("Arial", 8)).pack(side=tk.LEFT, padx=8)

        # Toggles
        toggle_row = tk.Frame(settings_frame, bg="#ecf0f1")
        toggle_row.pack(fill=tk.X, pady=3)

        self.toggle_vars = {}
        toggles = [
            ("bat_trong_cay", "Trồng cây", True),
            ("bat_may", "Máy", True),
            ("bat_ban_vp", "Bán vật phẩm", False),
            ("bat_thu_hoach", "Thu hoạch", True),
            ("bat_mo_ruong", "Mở rương", False),
            ("bat_giao_cu", "Giao cú", False),
            ("bat_giao_tom", "Giao tôm", False),
            ("bat_sxcam", "Sản xuất cám", False),
            ("bat_sang_ban_be", "Sang nhà bạn", False),
            ("bat_cap_nhat_khoi_dong", "Kiểm tra cập nhật", True),
        ]
        for i, (key, label, default) in enumerate(toggles):
            var = tk.BooleanVar(value=default)
            self.toggle_vars[key] = var
            col = i % 3
            row_idx = i // 3
            cb = tk.Checkbutton(toggle_row, text=label, variable=var, bg="#ecf0f1",
                                font=("Arial", 9), activebackground="#ecf0f1")
            cb.grid(row=row_idx, column=col, sticky=tk.W, padx=(0, 20), pady=1)

        # Global threshold
        th_row = tk.Frame(settings_frame, bg="#ecf0f1")
        th_row.pack(fill=tk.X, pady=3)
        tk.Label(th_row, text="Ngưỡng mặc định:", bg="#ecf0f1", width=18, anchor=tk.W).pack(side=tk.LEFT)
        self.global_threshold_var = tk.DoubleVar(value=0.85)
        tk.Spinbox(th_row, from_=0.5, to=1.0, increment=0.05,
                   textvariable=self.global_threshold_var, width=6,
                   font=("Arial", 10)).pack(side=tk.LEFT)
        tk.Label(th_row, text="(áp dụng cho tất cả nếu task không có riêng)",
                 bg="#ecf0f1", fg="#7f8c8d", font=("Arial", 8)).pack(side=tk.LEFT, padx=8)

        # LDPlayer Auto-Restart settings
        restart_row = tk.Frame(settings_frame, bg="#ecf0f1")
        restart_row.pack(fill=tk.X, pady=3)
        tk.Label(restart_row, text="Restart LDPlayer:", bg="#ecf0f1", width=18, anchor=tk.W).pack(side=tk.LEFT)
        self.bat_khoi_dong_lai_ld_var = tk.BooleanVar(value=False)
        tk.Checkbutton(restart_row, text="Tự động restart LD", variable=self.bat_khoi_dong_lai_ld_var, bg="#ecf0f1",
                       font=("Arial", 9), activebackground="#ecf0f1").pack(side=tk.LEFT)
        tk.Label(restart_row, text="Mỗi (giờ):", bg="#ecf0f1", padx=10).pack(side=tk.LEFT)
        self.thoi_gian_khoi_dong_lai_var = tk.DoubleVar(value=5.0)
        tk.Spinbox(restart_row, from_=0.01, to=999.0, increment=0.5,
                   textvariable=self.thoi_gian_khoi_dong_lai_var, width=6,
                   font=("Arial", 10)).pack(side=tk.LEFT)
        tk.Label(restart_row, text="(vd: 5 hoặc 0.02 để test)", bg="#ecf0f1", fg="#7f8c8d", font=("Arial", 8)).pack(side=tk.LEFT, padx=8)



        # ===== SECTION 2: TASKS (TC + MAY) =====
        form_frame = tk.LabelFrame(pad, text="Thêm mục TC / MÁY", font=("Arial", 10, "bold"),
                                   bg="#ecf0f1", padx=10, pady=10)
        form_frame.pack(fill=tk.X, pady=(0, 8))

        # Type
        r1 = tk.Frame(form_frame, bg="#ecf0f1")
        r1.pack(fill=tk.X, pady=3)
        tk.Label(r1, text="Loại:", bg="#ecf0f1", width=14, anchor=tk.W).pack(side=tk.LEFT)
        self.type_var = tk.StringVar(value="TC")
        ttk.Combobox(r1, textvariable=self.type_var, values=["TC", "MAY"], state="readonly",
                     width=10).pack(side=tk.LEFT)

        # Row
        r2 = tk.Frame(form_frame, bg="#ecf0f1")
        r2.pack(fill=tk.X, pady=3)
        tk.Label(r2, text="Hàng:", bg="#ecf0f1", width=14, anchor=tk.W).pack(side=tk.LEFT)
        self.row_var = tk.StringVar(value="1")
        row_nums = [str(i) for i in range(1, 11)]
        ttk.Combobox(r2, textvariable=self.row_var, values=row_nums, state="readonly",
                     width=10).pack(side=tk.LEFT)

        # path_row
        r3 = tk.Frame(form_frame, bg="#ecf0f1")
        r3.pack(fill=tk.X, pady=3)
        tk.Label(r3, text="Ảnh hàng:", bg="#ecf0f1", width=14, anchor=tk.W).pack(side=tk.LEFT)
        self.path_row_var = tk.StringVar()
        row_templates = scan_row_templates()
        self.row_template_combo = AutocompleteCombobox(r3, textvariable=self.path_row_var,
                                                       values=row_templates, width=30)
        self.row_template_combo.pack(side=tk.LEFT)
        if row_templates:
            self.path_row_var.set(row_templates[0])

        # indexs (for TC) - grid picker
        r4 = tk.Frame(form_frame, bg="#ecf0f1")
        r4.pack(fill=tk.X, pady=3)
        tk.Label(r4, text="Vị trí:", bg="#ecf0f1", width=14, anchor=tk.W).pack(side=tk.LEFT)
        self.indexs_display = tk.Label(r4, text="(Chưa chọn)", bg="white", fg="#2c3e50",
                                        font=("Consolas", 9), relief=tk.SUNKEN, anchor=tk.W,
                                        padx=6, width=45)
        self.indexs_display.pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(r4, text="Chọn vị trí", command=self._open_index_picker,
                  bg="#9b59b6", fg="white", relief=tk.FLAT, cursor="hand2",
                  padx=10).pack(side=tk.LEFT)
        self.selected_indexs = []

        # path_item (cay) + preview
        r5 = tk.Frame(form_frame, bg="#ecf0f1")
        r5.pack(fill=tk.X, pady=3)
        tk.Label(r5, text="Ảnh vật phẩm:", bg="#ecf0f1", width=14, anchor=tk.W).pack(side=tk.LEFT)
        self.path_item_var = tk.StringVar()
        all_templates = scan_all_templates()
        self.cay_combo = AutocompleteCombobox(r5, textvariable=self.path_item_var,
                                               values=all_templates, width=30)
        self.cay_combo.pack(side=tk.LEFT)
        self._item_preview_photo = None
        item_pf = tk.Frame(r5, width=44, height=44, bg="white", relief=tk.SUNKEN, bd=1)
        item_pf.pack_propagate(False)
        item_pf.pack(side=tk.LEFT, padx=(8, 0))
        self.item_preview_label = tk.Label(item_pf, bg="white")
        self.item_preview_label.pack(expand=True)
        if all_templates:
            self.path_item_var.set(all_templates[0])
        self.path_item_var.trace_add("write", lambda *_: self._update_item_preview())
        self.cay_combo.bind("<<ComboboxSelected>>", lambda e: self._update_item_preview())
        self._update_item_preview()

        # path_item_default (for TC) + preview
        r6 = tk.Frame(form_frame, bg="#ecf0f1")
        r6.pack(fill=tk.X, pady=3)
        tk.Label(r6, text="Ảnh mặc định:", bg="#ecf0f1", width=14, anchor=tk.W).pack(side=tk.LEFT)
        self.path_item_default_var = tk.StringVar()
        self.default_combo = AutocompleteCombobox(r6, textvariable=self.path_item_default_var,
                                                  values=all_templates, width=30)
        self.default_combo.pack(side=tk.LEFT)
        self._default_preview_photo = None
        default_pf = tk.Frame(r6, width=44, height=44, bg="white", relief=tk.SUNKEN, bd=1)
        default_pf.pack_propagate(False)
        default_pf.pack(side=tk.LEFT, padx=(8, 0))
        self.default_preview_label = tk.Label(default_pf, bg="white")
        self.default_preview_label.pack(expand=True)
        if "cay_hong.png" in all_templates:
            self.path_item_default_var.set("cay_hong.png")
        self.path_item_default_var.trace_add("write", lambda *_: self._update_default_preview())
        self.default_combo.bind("<<ComboboxSelected>>", lambda e: self._update_default_preview())
        self._update_default_preview()

        # Threshold (cho TC)
        r_th = tk.Frame(form_frame, bg="#ecf0f1")
        r_th.pack(fill=tk.X, pady=3)
        tk.Label(r_th, text="Ngưỡng:", bg="#ecf0f1", width=14, anchor=tk.W).pack(side=tk.LEFT)
        self.threshold_var = tk.DoubleVar(value=0.85)
        tk.Spinbox(r_th, from_=0.5, to=1.0, increment=0.05, textvariable=self.threshold_var,
                   width=6, font=("Arial", 9)).pack(side=tk.LEFT)
        tk.Label(r_th, text="Độ chính xác tìm ảnh (0.5-1.0)",
                 bg="#ecf0f1", fg="#7f8c8d", font=("Arial", 8)).pack(side=tk.LEFT, padx=4)

        # Vùng optional: x,y,w,h
        r_region = tk.Frame(form_frame, bg="#ecf0f1")
        r_region.pack(fill=tk.X, pady=3)
        tk.Label(r_region, text="Vùng:", bg="#ecf0f1", width=14, anchor=tk.W).pack(side=tk.LEFT)
        self.region_preset_var = tk.StringVar(value=self._default_region_preset())
        self.region_x_var = tk.StringVar()
        self.region_y_var = tk.StringVar()
        self.region_w_var = tk.StringVar()
        self.region_h_var = tk.StringVar()
        self.region_preset_combo = ttk.Combobox(
            r_region,
            textvariable=self.region_preset_var,
            values=self._region_combo_values(),
            state="readonly",
            width=24,
            font=("Arial", 9)
        )
        self.region_preset_combo.pack(side=tk.LEFT)
        self.region_preset_combo.bind("<<ComboboxSelected>>", lambda e: self._auto_update_selected_task_region())
        tk.Button(r_region, text="Xóa", command=self._clear_task_region,
                  bg="#95a5a6", fg="white", relief=tk.FLAT, cursor="hand2",
                  font=("Arial", 8), padx=6).pack(side=tk.LEFT, padx=(4, 0))
        tk.Label(r_region, text="(có thể lấy từ vùng cắt hiện tại)",
                 bg="#ecf0f1", fg="#7f8c8d", font=("Arial", 8)).pack(side=tk.LEFT, padx=4)

        # MAY: data (total)
        r7 = tk.Frame(form_frame, bg="#ecf0f1")
        r7.pack(fill=tk.X, pady=3)
        tk.Label(r7, text="Tổng (MÁY):", bg="#ecf0f1", width=14, anchor=tk.W).pack(side=tk.LEFT)
        self.total_entry = tk.Entry(r7, font=("Arial", 9), width=10)
        self.total_entry.pack(side=tk.LEFT)
        self.total_entry.insert(0, "4")
        tk.Label(r7, text="(chỉ dùng cho Máy)", bg="#ecf0f1", fg="#7f8c8d",
                 font=("Arial", 8)).pack(side=tk.LEFT, padx=4)

        def on_row_change(*_):
            r = self.row_var.get()
            self.path_row_var.set(f"{r}.png")
        self.row_var.trace_add("write", on_row_change)

        form_btn_row = tk.Frame(form_frame, bg="#ecf0f1")
        form_btn_row.pack(fill=tk.X, pady=(8, 0))
        tk.Button(form_btn_row, text="+ Thêm vào danh sách", command=self._add_item_to_list,
                  bg="#27ae60", fg="white", relief=tk.FLAT, cursor="hand2",
                  font=("Arial", 10, "bold"), padx=15, pady=5).pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(form_btn_row, text="Cập nhật mục đang chọn", command=self._update_selected_item,
                  bg="#f39c12", fg="white", relief=tk.FLAT, cursor="hand2",
                  font=("Arial", 10, "bold"), padx=15, pady=5).pack(side=tk.LEFT)

        # Tracking edit index
        self._editing_index = None

        # --- Tasks list ---
        list_frame = tk.LabelFrame(pad, text="Danh sách công việc (TC + MÁY)", font=("Arial", 10, "bold"),
                                   bg="#ecf0f1", padx=10, pady=8)
        list_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("stt", "type", "row", "path_item", "indexs_or_data", "region")
        self.cfg_tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=8)
        self.cfg_tree.heading("stt", text="#")
        self.cfg_tree.heading("type", text="Loại")
        self.cfg_tree.heading("row", text="Hàng")
        self.cfg_tree.heading("path_item", text="Vật phẩm")
        self.cfg_tree.heading("indexs_or_data", text="Vị trí / Dữ liệu")
        self.cfg_tree.heading("region", text="Vùng")

        self.cfg_tree.column("stt", width=35, anchor=tk.CENTER)
        self.cfg_tree.column("type", width=50, anchor=tk.CENTER)
        self.cfg_tree.column("row", width=45, anchor=tk.CENTER)
        self.cfg_tree.column("path_item", width=160)
        self.cfg_tree.column("indexs_or_data", width=270)
        self.cfg_tree.column("region", width=110)

        tree_scroll = tk.Scrollbar(list_frame, command=self.cfg_tree.yview)
        self.cfg_tree.config(yscrollcommand=tree_scroll.set)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.cfg_tree.pack(fill=tk.BOTH, expand=True)

        btn_bar = tk.Frame(list_frame, bg="#ecf0f1")
        btn_bar.pack(fill=tk.X, pady=(6, 0))
        tk.Button(btn_bar, text="Sửa", command=self._edit_selected,
                  bg="#f39c12", fg="white", relief=tk.FLAT, cursor="hand2",
                  padx=10, font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_bar, text="Xóa", command=self._remove_selected,
                  bg="#e74c3c", fg="white", relief=tk.FLAT, cursor="hand2", padx=10).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_bar, text="Lên", command=lambda: self._move_item(-1),
                  bg="#95a5a6", fg="white", relief=tk.FLAT, cursor="hand2", padx=10).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_bar, text="Xuống", command=lambda: self._move_item(1),
                  bg="#95a5a6", fg="white", relief=tk.FLAT, cursor="hand2", padx=10).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_bar, text="⚡ Chu trình tự động", command=self._open_smart_recipe_dialog,
                  bg="#8e44ad", fg="white", relief=tk.FLAT, cursor="hand2", padx=10, font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=8)
        tk.Button(btn_bar, text="Xóa tất cả", command=self._clear_list,
                  bg="#e74c3c", fg="white", relief=tk.FLAT, cursor="hand2", padx=10).pack(side=tk.RIGHT, padx=4)

        # Double-click de sua
        self.cfg_tree.bind("<Double-1>", lambda e: self._edit_selected())

        # ===== SECTION 3: BAN DO (Bán vật phẩm) =====
        bando_frame = tk.LabelFrame(pad, text="Cấu hình bán vật phẩm", font=("Arial", 10, "bold"),
                                     bg="#ecf0f1", padx=10, pady=8)
        bando_frame.pack(fill=tk.X, pady=(8, 0))

        # Loai kho
        bk1 = tk.Frame(bando_frame, bg="#ecf0f1")
        bk1.pack(fill=tk.X, pady=3)
        tk.Label(bk1, text="Loại kho:", bg="#ecf0f1", width=16, anchor=tk.W).pack(side=tk.LEFT)
        self.bd_loai_kho_var = tk.StringVar(value="KTP")
        ttk.Combobox(bk1, textvariable=self.bd_loai_kho_var,
                     values=[kho["code"] for kho in CONFIG_LOAI_KHO], state="readonly", width=10).pack(side=tk.LEFT)
        tk.Label(bk1, text="(KSK=Sự Kiện, KNS=Nông Sản, KTP=Thành Phẩm)", bg="#ecf0f1",
                 fg="#7f8c8d", font=("Arial", 8)).pack(side=tk.LEFT, padx=8)

        # So lan dat VP
        bk2 = tk.Frame(bando_frame, bg="#ecf0f1")
        bk2.pack(fill=tk.X, pady=3)
        tk.Label(bk2, text="Số lần đặt VP:", bg="#ecf0f1", width=16, anchor=tk.W).pack(side=tk.LEFT)
        self.bd_so_lan_var = tk.StringVar(value="4")
        tk.Spinbox(bk2, from_=1, to=99, textvariable=self.bd_so_lan_var, width=6,
                   font=("Arial", 10)).pack(side=tk.LEFT)

        # Xóa kim cuong + Dat quang cao
        bk3 = tk.Frame(bando_frame, bg="#ecf0f1")
        bk3.pack(fill=tk.X, pady=3)
        self.bd_xoa_kc_var = tk.BooleanVar(value=True)
        tk.Checkbutton(bk3, text="Xé kim cương", variable=self.bd_xoa_kc_var,
                       bg="#ecf0f1", font=("Arial", 9)).pack(side=tk.LEFT)

        self.bd_dat_qc_var = tk.BooleanVar(value=True)
        tk.Checkbutton(bk3, text="Đặt quảng cáo", variable=self.bd_dat_qc_var,
                        bg="#ecf0f1", font=("Arial", 9)).pack(side=tk.LEFT, padx=(20, 0))

        self.bd_check_stock_var = tk.BooleanVar(value=False)
        tk.Checkbutton(bk3, text="Đọc stock", variable=self.bd_check_stock_var,
                       bg="#ecf0f1", font=("Arial", 9)).pack(side=tk.LEFT, padx=(20, 0))

        # Note: QC and xóa KC use list-based templates (managed below)

        # Threshold + Color threshold cho ban do
        bk3b = tk.Frame(bando_frame, bg="#ecf0f1")
        bk3b.pack(fill=tk.X, pady=3)
        tk.Label(bk3b, text="Ngưỡng:", bg="#ecf0f1", width=16, anchor=tk.W).pack(side=tk.LEFT)
        self.bd_threshold_var = tk.DoubleVar(value=0.85)
        tk.Spinbox(bk3b, from_=0.5, to=1.0, increment=0.05,
                   textvariable=self.bd_threshold_var, width=5,
                   font=("Arial", 10)).pack(side=tk.LEFT)
        tk.Label(bk3b, text="  Màu:", bg="#ecf0f1", anchor=tk.W).pack(side=tk.LEFT, padx=(8, 0))
        self.bd_color_threshold_var = tk.DoubleVar(value=0.6)
        tk.Spinbox(bk3b, from_=0.3, to=1.0, increment=0.05,
                   textvariable=self.bd_color_threshold_var, width=5,
                   font=("Arial", 10)).pack(side=tk.LEFT)
        tk.Label(bk3b, text="(Mặc định, VP có thể ghi đè)", bg="#ecf0f1",
                 fg="#7f8c8d", font=("Arial", 8)).pack(side=tk.LEFT, padx=8)

        # Vùng mac dinh cho ban do
        bk3c = tk.Frame(bando_frame, bg="#ecf0f1")
        bk3c.pack(fill=tk.X, pady=3)
        tk.Label(bk3c, text="Vùng bán đồ:", bg="#ecf0f1", width=16, anchor=tk.W).pack(side=tk.LEFT)
        self.bd_region_preset_var = tk.StringVar(value=self._default_region_preset())
        self.bd_region_x_var = tk.StringVar()
        self.bd_region_y_var = tk.StringVar()
        self.bd_region_w_var = tk.StringVar()
        self.bd_region_h_var = tk.StringVar()
        self.bd_region_preset_combo = ttk.Combobox(
            bk3c,
            textvariable=self.bd_region_preset_var,
            values=self._region_combo_values(),
            state="readonly",
            width=24,
            font=("Arial", 9)
        )
        self.bd_region_preset_combo.pack(side=tk.LEFT)
        tk.Button(bk3c, text="Xóa", command=self._clear_bd_region,
                  bg="#95a5a6", fg="white", relief=tk.FLAT, cursor="hand2",
                  font=("Arial", 8), padx=6).pack(side=tk.LEFT, padx=(4, 0))
        tk.Label(bk3c, text="(áp dụng cho VP không có vùng VP riêng)",
                 bg="#ecf0f1", fg="#7f8c8d", font=("Arial", 8)).pack(side=tk.LEFT, padx=4)

        # Danh sach VP can ban
        bk4 = tk.Frame(bando_frame, bg="#ecf0f1")
        bk4.pack(fill=tk.X, pady=3)
        tk.Label(bk4, text="VP cần bán:", bg="#ecf0f1", width=16, anchor=tk.W).pack(side=tk.LEFT, anchor=tk.N)

        bk4_right = tk.Frame(bk4, bg="#ecf0f1")
        bk4_right.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Add VP row
        bk4_add = tk.Frame(bk4_right, bg="#ecf0f1")
        bk4_add.pack(fill=tk.X, pady=2)
        self.bd_vp_var = tk.StringVar()
        kho_templates = scan_kho_templates()
        self.bd_vp_combo = AutocompleteCombobox(bk4_add, textvariable=self.bd_vp_var,
                                                 values=kho_templates, width=20)
        self.bd_vp_combo.pack(side=tk.LEFT)
        self._bd_vp_preview_photo = None
        bd_vp_pf = tk.Frame(bk4_add, width=44, height=44, bg="white", relief=tk.SUNKEN, bd=1)
        bd_vp_pf.pack_propagate(False)
        bd_vp_pf.pack(side=tk.LEFT, padx=(4, 0))
        self.bd_vp_preview_label = tk.Label(bd_vp_pf, bg="white")
        self.bd_vp_preview_label.pack(expand=True)
        self.bd_vp_var.trace_add("write", lambda *_: self._update_bd_vp_preview())
        self.bd_vp_combo.bind("<<ComboboxSelected>>", lambda e: self._update_bd_vp_preview())
        if kho_templates:
            self.bd_vp_var.set(kho_templates[0])
            self._update_bd_vp_preview()

        # Per-VP threshold + color
        tk.Label(bk4_add, text="t:", bg="#ecf0f1", font=("Arial", 8)).pack(side=tk.LEFT, padx=(6, 0))
        self.bd_vp_threshold_var = tk.StringVar(value="")
        tk.Entry(bk4_add, textvariable=self.bd_vp_threshold_var, width=4,
                 font=("Arial", 9)).pack(side=tk.LEFT)
        tk.Label(bk4_add, text="c:", bg="#ecf0f1", font=("Arial", 8)).pack(side=tk.LEFT, padx=(4, 0))
        self.bd_vp_color_var = tk.StringVar(value="")
        tk.Entry(bk4_add, textvariable=self.bd_vp_color_var, width=4,
                 font=("Arial", 9)).pack(side=tk.LEFT)

        tk.Button(bk4_add, text="+ Thêm", command=self._bd_add_vp,
                  bg="#27ae60", fg="white", relief=tk.FLAT, cursor="hand2",
                  padx=8).pack(side=tk.LEFT, padx=4)

        bk4_region = tk.Frame(bk4_right, bg="#ecf0f1")
        bk4_region.pack(fill=tk.X, pady=2)
        tk.Label(bk4_region, text="Vùng VP:", bg="#ecf0f1", font=("Arial", 8)).pack(side=tk.LEFT)
        self.bd_vp_region_preset_var = tk.StringVar(value=self._default_region_preset())
        self.bd_vp_region_x_var = tk.StringVar()
        self.bd_vp_region_y_var = tk.StringVar()
        self.bd_vp_region_w_var = tk.StringVar()
        self.bd_vp_region_h_var = tk.StringVar()
        self.bd_vp_region_preset_combo = ttk.Combobox(
            bk4_region,
            textvariable=self.bd_vp_region_preset_var,
            values=self._region_combo_values(),
            state="readonly",
            width=24,
            font=("Arial", 9)
        )
        self.bd_vp_region_preset_combo.pack(side=tk.LEFT, padx=(6, 0))
        self.bd_vp_region_preset_combo.bind("<<ComboboxSelected>>", lambda e: self._auto_update_selected_vp_region())
        tk.Button(bk4_region, text="Xóa", command=self._clear_bd_vp_region,
                  bg="#95a5a6", fg="white", relief=tk.FLAT, cursor="hand2",
                  font=("Arial", 8), padx=6).pack(side=tk.LEFT, padx=6)

        # VP list
        self.bd_vp_listbox = self._create_scrolled_listbox(bk4_right, height=4)
        self.bd_vp_listbox.bind("<<ListboxSelect>>", lambda e: self._bd_load_selected_vp())

        bk4_btns = tk.Frame(bk4_right, bg="#ecf0f1")
        bk4_btns.pack(fill=tk.X)
        tk.Button(bk4_btns, text="Cập nhật VP", command=self._bd_update_selected_vp,
                  bg="#f39c12", fg="white", relief=tk.FLAT, cursor="hand2",
                  padx=8).pack(side=tk.LEFT)
        tk.Button(bk4_btns, text="Xóa", command=self._bd_remove_vp,
                  bg="#e74c3c", fg="white", relief=tk.FLAT, cursor="hand2",
                  padx=8).pack(side=tk.LEFT, padx=4)
        tk.Button(bk4_btns, text="Xóa tất cả", command=self._bd_clear_vp,
                  bg="#e74c3c", fg="white", relief=tk.FLAT, cursor="hand2",
                  padx=8).pack(side=tk.LEFT, padx=4)


        bk_qc = tk.Frame(bando_frame, bg="#ecf0f1")
        bk_qc.pack(fill=tk.X, pady=6)
        tk.Label(bk_qc, text="DS quảng cáo:", bg="#ecf0f1", width=16, anchor=tk.W).pack(side=tk.LEFT, anchor=tk.N)
        bk_qc_r = tk.Frame(bk_qc, bg="#ecf0f1")
        bk_qc_r.pack(side=tk.LEFT, fill=tk.X, expand=True)

        bk_qc_add = tk.Frame(bk_qc_r, bg="#ecf0f1")
        bk_qc_add.pack(fill=tk.X, pady=2)
        self.bd_qc_var = tk.StringVar()
        all_templates = scan_all_templates()
        self.bd_qc_combo = AutocompleteCombobox(bk_qc_add, textvariable=self.bd_qc_var,
                               values=all_templates, width=20)
        self.bd_qc_combo.pack(side=tk.LEFT)
        self._bd_qc_preview_photo = None
        bd_qc_pf2 = tk.Frame(bk_qc_add, width=44, height=44, bg="white", relief=tk.SUNKEN, bd=1)
        bd_qc_pf2.pack_propagate(False)
        bd_qc_pf2.pack(side=tk.LEFT, padx=(4, 0))
        self.bd_qc_preview_label = tk.Label(bd_qc_pf2, bg="white")
        self.bd_qc_preview_label.pack(expand=True)
        self.bd_qc_var.trace_add("write", lambda *_: self._update_bd_qc_preview())
        self.bd_qc_combo.bind("<<ComboboxSelected>>", lambda e: self._update_bd_qc_preview())
        tk.Button(bk_qc_add, text="+ Thêm", command=self._bd_qc_add,
              bg="#27ae60", fg="white", relief=tk.FLAT, cursor="hand2",
              padx=8).pack(side=tk.LEFT, padx=6)

        self.bd_qc_listbox = self._create_scrolled_listbox(bk_qc_r, height=4)
        bk_qc_btns = tk.Frame(bk_qc_r, bg="#ecf0f1")
        bk_qc_btns.pack(fill=tk.X)
        tk.Button(bk_qc_btns, text="Xóa", command=self._bd_qc_remove,
              bg="#e74c3c", fg="white", relief=tk.FLAT, cursor="hand2",
              padx=8).pack(side=tk.LEFT)
        tk.Button(bk_qc_btns, text="Xóa tất cả", command=self._bd_qc_clear,
              bg="#e74c3c", fg="white", relief=tk.FLAT, cursor="hand2",
              padx=8).pack(side=tk.LEFT, padx=4)

        # --- Mẫu Xé KC (list giống VP) ---
        bk_xe = tk.Frame(bando_frame, bg="#ecf0f1")
        bk_xe.pack(fill=tk.X, pady=6)
        tk.Label(bk_xe, text="Danh sách xé KC:", bg="#ecf0f1", width=16, anchor=tk.W).pack(side=tk.LEFT, anchor=tk.N)
        bk_xe_r = tk.Frame(bk_xe, bg="#ecf0f1")
        bk_xe_r.pack(side=tk.LEFT, fill=tk.X, expand=True)

        bk_xe_add = tk.Frame(bk_xe_r, bg="#ecf0f1")
        bk_xe_add.pack(fill=tk.X, pady=2)
        self.bd_xe_var = tk.StringVar()
        self.bd_xe_combo = AutocompleteCombobox(bk_xe_add, textvariable=self.bd_xe_var,
                            values=all_templates, width=20)
        self.bd_xe_combo.pack(side=tk.LEFT)
        self._bd_xe_preview_photo = None
        bd_xe_pf2 = tk.Frame(bk_xe_add, width=44, height=44, bg="white", relief=tk.SUNKEN, bd=1)
        bd_xe_pf2.pack_propagate(False)
        bd_xe_pf2.pack(side=tk.LEFT, padx=(4, 0))
        self.bd_xoa_kc_preview_label = tk.Label(bd_xe_pf2, bg="white")
        self.bd_xoa_kc_preview_label.pack(expand=True)
        self.bd_xe_var.trace_add("write", lambda *_: self._update_bd_xoa_kc_preview())
        self.bd_xe_combo.bind("<<ComboboxSelected>>", lambda e: self._update_bd_xoa_kc_preview())
        tk.Button(bk_xe_add, text="+ Thêm", command=self._bd_xe_add,
              bg="#27ae60", fg="white", relief=tk.FLAT, cursor="hand2",
              padx=8).pack(side=tk.LEFT, padx=6)

        self.bd_xe_listbox = self._create_scrolled_listbox(bk_xe_r, height=4)
        bk_xe_btns = tk.Frame(bk_xe_r, bg="#ecf0f1")
        bk_xe_btns.pack(fill=tk.X)
        tk.Button(bk_xe_btns, text="Xóa", command=self._bd_xe_remove,
              bg="#e74c3c", fg="white", relief=tk.FLAT, cursor="hand2",
              padx=8).pack(side=tk.LEFT)
        tk.Button(bk_xe_btns, text="Xóa tất cả", command=self._bd_xe_clear,
              bg="#e74c3c", fg="white", relief=tk.FLAT, cursor="hand2",
              padx=8).pack(side=tk.LEFT, padx=4)

        # --- Cấu hình giao cú ---
        giao_cu_frame = tk.LabelFrame(pad, text="Cấu hình giao cú", font=("Arial", 10, "bold"),
                                      bg="#ecf0f1", padx=10, pady=8)
        giao_cu_frame.pack(fill=tk.X, pady=(8, 0))

        bk_gc_skip = tk.Frame(giao_cu_frame, bg="#ecf0f1")
        bk_gc_skip.pack(fill=tk.X, pady=3)
        tk.Label(bk_gc_skip, text="Giao cú bỏ qua:", bg="#ecf0f1", width=16, anchor=tk.W).pack(side=tk.LEFT, anchor=tk.N)
        bk_gc_skip_r = tk.Frame(bk_gc_skip, bg="#ecf0f1")
        bk_gc_skip_r.pack(side=tk.LEFT, fill=tk.X, expand=True)

        bk_gc_skip_add = tk.Frame(bk_gc_skip_r, bg="#ecf0f1")
        bk_gc_skip_add.pack(fill=tk.X, pady=2)
        self.gc_skip_var = tk.StringVar()
        all_templates = scan_all_templates()
        self.gc_skip_combo = AutocompleteCombobox(bk_gc_skip_add, textvariable=self.gc_skip_var,
                                                  values=all_templates, width=20)
        self.gc_skip_combo.pack(side=tk.LEFT)
        self._gc_skip_preview_photo = None
        gc_skip_pf = tk.Frame(bk_gc_skip_add, width=44, height=44, bg="white", relief=tk.SUNKEN, bd=1)
        gc_skip_pf.pack_propagate(False)
        gc_skip_pf.pack(side=tk.LEFT, padx=(4, 0))
        self.gc_skip_preview_label = tk.Label(gc_skip_pf, bg="white")
        self.gc_skip_preview_label.pack(expand=True)
        self.gc_skip_var.trace_add("write", lambda *_: self._update_gc_skip_preview())
        self.gc_skip_combo.bind("<<ComboboxSelected>>", lambda e: self._update_gc_skip_preview())
        tk.Button(bk_gc_skip_add, text="+ Thêm", command=self._gc_skip_add,
                  bg="#27ae60", fg="white", relief=tk.FLAT, cursor="hand2",
                  padx=8).pack(side=tk.LEFT, padx=6)

        self.gc_skip_listbox = self._create_scrolled_listbox(bk_gc_skip_r, height=4)
        bk_gc_skip_btns = tk.Frame(bk_gc_skip_r, bg="#ecf0f1")
        bk_gc_skip_btns.pack(fill=tk.X)
        tk.Button(bk_gc_skip_btns, text="Xóa", command=self._gc_skip_remove,
                  bg="#e74c3c", fg="white", relief=tk.FLAT, cursor="hand2",
                  padx=8).pack(side=tk.LEFT)
        tk.Button(bk_gc_skip_btns, text="Xóa tất cả", command=self._gc_skip_clear,
                  bg="#e74c3c", fg="white", relief=tk.FLAT, cursor="hand2",
                  padx=8).pack(side=tk.LEFT, padx=4)

        giao_tom_frame = tk.LabelFrame(pad, text="Cấu hình giao tôm", font=("Arial", 10, "bold"),
                                       bg="#ecf0f1", padx=10, pady=8)
        giao_tom_frame.pack(fill=tk.X, pady=(8, 0))

        tom_row = tk.Frame(giao_tom_frame, bg="#ecf0f1")
        tom_row.pack(fill=tk.X, pady=3)
        tk.Label(tom_row, text="VP tôm cần lấy:", bg="#ecf0f1", width=16, anchor=tk.W).pack(side=tk.LEFT)
        self.tom_vp_var = tk.StringVar()
        all_templates = scan_all_templates()
        self.tom_vp_combo = AutocompleteCombobox(tom_row, textvariable=self.tom_vp_var,
                                                 values=all_templates, width=20)
        self.tom_vp_combo.pack(side=tk.LEFT)
        self._tom_vp_preview_photo = None
        tom_vp_pf = tk.Frame(tom_row, width=44, height=44, bg="white", relief=tk.SUNKEN, bd=1)
        tom_vp_pf.pack_propagate(False)
        tom_vp_pf.pack(side=tk.LEFT, padx=(4, 0))
        self.tom_vp_preview_label = tk.Label(tom_vp_pf, bg="white")
        self.tom_vp_preview_label.pack(expand=True)
        self.tom_vp_var.trace_add("write", lambda *_: self._update_tom_vp_preview())
        self.tom_vp_combo.bind("<<ComboboxSelected>>", lambda e: self._update_tom_vp_preview())

        tk.Label(tom_row, text="Kho:", bg="#ecf0f1", padx=8).pack(side=tk.LEFT)
        self.tom_kho_var = tk.StringVar(value="KTP")
        ttk.Combobox(tom_row, textvariable=self.tom_kho_var,
                     values=["KTP", "KNS"], state="readonly", width=8).pack(side=tk.LEFT)
        # Internal data
        self.config_items = []
        self.bd_vp_list = []  # list of dict: {"path", "threshold", "color_threshold"}
        self.bd_qc_list = []
        self.bd_xe_list = []
        self.gc_skip_list = []
        self._bind_template_refresh_events()

    def _create_scrolled_listbox(self, parent, height=4):
        frame = tk.Frame(parent, bg="#ecf0f1")
        frame.pack(fill=tk.X, pady=4)
        scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox = tk.Listbox(
            frame,
            font=("Consolas", 9),
            height=height,
            selectmode=tk.SINGLE,
            bg="white",
            yscrollcommand=scrollbar.set
        )
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)
        return listbox

    def _bind_template_refresh_events(self):
        for combo in self._template_combos():
            combo.bind("<ButtonPress-1>", lambda e: self._refresh_template_combos(), add="+")
            combo.bind("<FocusIn>", lambda e: self._refresh_template_combos(), add="+")

    def _template_combos(self):
        names = (
            "row_template_combo",
            "cay_combo",
            "default_combo",
            "bd_vp_combo",
            "bd_qc_combo",
            "bd_xe_combo",
            "gc_skip_combo",
            "tom_vp_combo",
        )
        return [getattr(self, name) for name in names if hasattr(self, name)]

    def _refresh_template_combos(self):
        all_templates = scan_all_templates()
        kho_templates = scan_kho_templates()
        row_templates = scan_row_templates()
        values_by_name = {
            "row_template_combo": row_templates,
            "cay_combo": all_templates,
            "default_combo": all_templates,
            "bd_vp_combo": kho_templates,
            "bd_qc_combo": all_templates,
            "bd_xe_combo": all_templates,
            "gc_skip_combo": all_templates,
            "tom_vp_combo": all_templates,
        }
        for name, values in values_by_name.items():
            combo = getattr(self, name, None)
            if combo is not None and hasattr(combo, "set_values"):
                combo.set_values(values)

    def _template_path_from_name(self, name):
        if not name:
            return ""
        return name if name.startswith("assets/") or os.path.isabs(name) else f"assets/items/{name}"

    def _region_combo_values(self, extra=None):
        values = list(REGION_PRESETS.keys()) + [REGION_FROM_CROP]
        if extra and extra not in values:
            values.append(extra)
        return values

    def _default_region_preset(self):
        return next(iter(REGION_PRESETS), "Toan man")

    def _get_current_crop_region(self):
        try:
            raw = [
                self.ss_crop_x.get().strip(),
                self.ss_crop_y.get().strip(),
                self.ss_crop_w.get().strip(),
                self.ss_crop_h.get().strip(),
            ]
        except (AttributeError, tk.TclError):
            return None
        return normalize_region(raw)

    def _get_region_from_preset(self, preset_var, x_var, y_var, w_var, h_var):
        selected = preset_var.get().strip()
        if selected in REGION_PRESETS:
            return normalize_region(REGION_PRESETS[selected])
        if selected == REGION_FROM_CROP:
            region = self._get_current_crop_region()
            if region is None:
                messagebox.showwarning("Lỗi", "Chưa có vùng cắt hiện tại. Vào tab Chụp & Cắt ảnh để kéo chọn vùng trước.")
            return region
        if selected.startswith("Đã lưu:"):
            return normalize_region(selected.split(":", 1)[1].strip())
        return self._get_region_from_vars(x_var, y_var, w_var, h_var)

    def _set_region_preset(self, region, preset_var, combo, x_var, y_var, w_var, h_var):
        self._set_region_vars(region, x_var, y_var, w_var, h_var)
        normalized = normalize_region(region)
        if normalized is None:
            preset = self._default_region_preset()
        else:
            preset = None
            for name, preset_region in REGION_PRESETS.items():
                if normalize_region(preset_region) == normalized:
                    preset = name
                    break
            if preset is None:
                preset = f"Đã lưu: {format_region(normalized)}"
        preset_var.set(preset)
        if combo is not None:
            combo["values"] = self._region_combo_values(preset if preset.startswith("Đã lưu:") else None)

    def _get_region_from_vars(self, x_var, y_var, w_var, h_var):
        raw = [x_var.get().strip(), y_var.get().strip(),
               w_var.get().strip(), h_var.get().strip()]
        if not any(raw):
            return None
        region = normalize_region(raw)
        if region is None:
            messagebox.showwarning("Lỗi", "Vùng phải có dạng X, Y, W, H và W/H > 0")
        return region

    def _set_region_vars(self, region, x_var, y_var, w_var, h_var):
        values = normalize_region(region) or ["", "", "", ""]
        for var, value in zip([x_var, y_var, w_var, h_var], values):
            var.set(str(value) if value != "" else "")

    def _get_task_region_from_ui(self):
        return self._get_region_from_preset(
            self.region_preset_var,
            self.region_x_var, self.region_y_var,
            self.region_w_var, self.region_h_var
        )

    def _set_task_region_to_ui(self, region):
        self._set_region_preset(
            region,
            self.region_preset_var,
            getattr(self, "region_preset_combo", None),
            self.region_x_var, self.region_y_var,
            self.region_w_var, self.region_h_var
        )

    def _clear_task_region(self):
        self._set_task_region_to_ui(None)

    def _get_bd_region_from_ui(self):
        return self._get_region_from_preset(
            self.bd_region_preset_var,
            self.bd_region_x_var, self.bd_region_y_var,
            self.bd_region_w_var, self.bd_region_h_var
        )

    def _set_bd_region_to_ui(self, region):
        self._set_region_preset(
            region,
            self.bd_region_preset_var,
            getattr(self, "bd_region_preset_combo", None),
            self.bd_region_x_var, self.bd_region_y_var,
            self.bd_region_w_var, self.bd_region_h_var
        )

    def _clear_bd_region(self):
        self._set_bd_region_to_ui(None)

    def _auto_update_selected_task_region(self):
        region = self._get_task_region_from_ui()
        idx = self._editing_index
        if idx is None:
            sel = self.cfg_tree.selection() if hasattr(self, "cfg_tree") else ()
            if sel:
                idx = self.cfg_tree.index(sel[0])
        if idx is None or idx < 0 or idx >= len(self.config_items):
            return
        if region:
            self.config_items[idx]["region"] = region
        else:
            self.config_items[idx].pop("region", None)
        self._refresh_tree()
        children = self.cfg_tree.get_children()
        if idx < len(children):
            self.cfg_tree.selection_set(children[idx])
            self.cfg_tree.focus(children[idx])

    def _get_bd_vp_region_from_ui(self):
        return self._get_region_from_preset(
            self.bd_vp_region_preset_var,
            self.bd_vp_region_x_var, self.bd_vp_region_y_var,
            self.bd_vp_region_w_var, self.bd_vp_region_h_var
        )

    def _clear_bd_vp_region(self):
        self._set_region_preset(
            None,
            self.bd_vp_region_preset_var,
            getattr(self, "bd_vp_region_preset_combo", None),
            self.bd_vp_region_x_var, self.bd_vp_region_y_var,
            self.bd_vp_region_w_var, self.bd_vp_region_h_var
        )
        self._auto_update_selected_vp_region()

    def _auto_update_selected_vp_region(self):
        if getattr(self, "_loading_bd_vp", False):
            return
        sel = self.bd_vp_listbox.curselection() if hasattr(self, "bd_vp_listbox") else ()
        if not sel:
            return
        idx = sel[0]
        if idx < 0 or idx >= len(self.bd_vp_list):
            return
        item = self.bd_vp_list[idx]
        vp_info = {"path": item} if isinstance(item, str) else dict(item)
        region = self._get_bd_vp_region_from_ui()
        if region:
            vp_info["region"] = region
        else:
            vp_info.pop("region", None)
        self.bd_vp_list[idx] = vp_info
        self.bd_vp_listbox.delete(idx)
        self.bd_vp_listbox.insert(idx, self._bd_format_vp_display(vp_info))
        self.bd_vp_listbox.selection_set(idx)

    # --- Ban do VP list helpers ---
    def _update_bd_vp_preview(self):
        photo = self._load_preview(self.bd_vp_var.get())
        self._bd_vp_preview_photo = photo
        self.bd_vp_preview_label.config(image=photo if photo else "", text="")

    def _bd_add_vp(self):
        vp = self.bd_vp_var.get().strip()
        if not vp:
            return
        path = f"assets/items/{vp}"
        # Check trùng
        for item in self.bd_vp_list:
            existing_path = item["path"] if isinstance(item, dict) else item
            if existing_path == path:
                return

        # Parse per-VP threshold + color (để trống = dùng default)
        vp_info = {"path": path}
        t_str = self.bd_vp_threshold_var.get().strip()
        c_str = self.bd_vp_color_var.get().strip()
        if t_str:
            try:
                vp_info["threshold"] = float(t_str)
            except ValueError:
                pass
        if c_str:
            try:
                vp_info["color_threshold"] = float(c_str)
            except ValueError:
                pass
        region = self._get_bd_vp_region_from_ui()
        if region:
            vp_info["region"] = region

        self.bd_vp_list.append(vp_info)
        # Hiển thị trong listbox
        display = vp
        extras = []
        if "threshold" in vp_info:
            extras.append(f"t={vp_info['threshold']}")
        if "color_threshold" in vp_info:
            extras.append(f"c={vp_info['color_threshold']}")
        if "region" in vp_info:
            extras.append(f"r={format_region(vp_info['region'])}")
        if extras:
            display += f"  ({', '.join(extras)})"
        self.bd_vp_listbox.insert(tk.END, display)

    def _bd_format_vp_display(self, vp_info):
        if isinstance(vp_info, str):
            vp_info = {"path": vp_info}
        display = os.path.basename(vp_info.get("path", ""))
        extras = []
        if "threshold" in vp_info:
            extras.append(f"t={vp_info['threshold']}")
        if "color_threshold" in vp_info:
            extras.append(f"c={vp_info['color_threshold']}")
        if "region" in vp_info:
            extras.append(f"r={format_region(vp_info['region'])}")
        if extras:
            display += f"  ({', '.join(extras)})"
        return display

    def _bd_load_selected_vp(self):
        sel = self.bd_vp_listbox.curselection()
        if not sel:
            return
        self._loading_bd_vp = True
        try:
            item = self.bd_vp_list[sel[0]]
            vp_info = {"path": item} if isinstance(item, str) else dict(item)
            self.bd_vp_var.set(os.path.basename(vp_info.get("path", "")))
            self.bd_vp_threshold_var.set(str(vp_info.get("threshold", "")))
            self.bd_vp_color_var.set(str(vp_info.get("color_threshold", "")))
            self._set_region_preset(
                vp_info.get("region"),
                self.bd_vp_region_preset_var,
                getattr(self, "bd_vp_region_preset_combo", None),
                self.bd_vp_region_x_var, self.bd_vp_region_y_var,
                self.bd_vp_region_w_var, self.bd_vp_region_h_var
            )
            self._update_bd_vp_preview()
        finally:
            self._loading_bd_vp = False

    def _bd_update_selected_vp(self):
        sel = self.bd_vp_listbox.curselection()
        if not sel:
            messagebox.showinfo("Thông báo", "Chọn 1 VP trong danh sách để cập nhật!")
            return
        idx = sel[0]
        vp = self.bd_vp_var.get().strip()
        if not vp:
            return
        vp_info = {"path": f"assets/items/{vp}" if not vp.startswith("assets/") else vp}
        t_str = self.bd_vp_threshold_var.get().strip()
        c_str = self.bd_vp_color_var.get().strip()
        if t_str:
            try:
                vp_info["threshold"] = float(t_str)
            except ValueError:
                pass
        if c_str:
            try:
                vp_info["color_threshold"] = float(c_str)
            except ValueError:
                pass
        region = self._get_bd_vp_region_from_ui()
        if region:
            vp_info["region"] = region

        new_path = vp_info["path"]
        for i, item in enumerate(self.bd_vp_list):
            if i == idx:
                continue
            existing_path = item["path"] if isinstance(item, dict) else item
            if existing_path == new_path:
                messagebox.showwarning("Lỗi", "VP này đã có trong danh sách!")
                return

        self.bd_vp_list[idx] = vp_info
        self.bd_vp_listbox.delete(idx)
        self.bd_vp_listbox.insert(idx, self._bd_format_vp_display(vp_info))
        self.bd_vp_listbox.selection_set(idx)

    def _bd_remove_vp(self):
        sel = self.bd_vp_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self.bd_vp_list.pop(idx)
        self.bd_vp_listbox.delete(idx)

    def _bd_clear_vp(self):
        self.bd_vp_list.clear()
        self.bd_vp_listbox.delete(0, tk.END)

    # --- QC list helpers ---
    def _bd_qc_add(self):
        sel = self.bd_qc_var.get().strip()
        if not sel:
            return
        path = f"assets/items/{sel}" if not sel.startswith("assets/") else sel
        # avoid duplicates
        existing = [p if isinstance(p, str) else p.get("path") for p in getattr(self, 'bd_qc_list', [])]
        if path in existing:
            return
        if not hasattr(self, 'bd_qc_list'):
            self.bd_qc_list = []
        self.bd_qc_list.append(path)
        self.bd_qc_listbox.insert(tk.END, os.path.basename(path))

    def _bd_qc_remove(self):
        sel = self.bd_qc_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if hasattr(self, 'bd_qc_list'):
            self.bd_qc_list.pop(idx)
        self.bd_qc_listbox.delete(idx)

    def _bd_qc_clear(self):
        self.bd_qc_list = []
        self.bd_qc_listbox.delete(0, tk.END)

    # --- Xé KC list helpers ---
    def _bd_xe_add(self):
        sel = self.bd_xe_var.get().strip()
        if not sel:
            return
        path = f"assets/items/{sel}" if not sel.startswith("assets/") else sel
        existing = [p if isinstance(p, str) else p.get("path") for p in getattr(self, 'bd_xe_list', [])]
        if path in existing:
            return
        if not hasattr(self, 'bd_xe_list'):
            self.bd_xe_list = []
        self.bd_xe_list.append(path)
        self.bd_xe_listbox.insert(tk.END, os.path.basename(path))

    def _bd_xe_remove(self):
        sel = self.bd_xe_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if hasattr(self, 'bd_xe_list'):
            self.bd_xe_list.pop(idx)
        self.bd_xe_listbox.delete(idx)

    def _bd_xe_clear(self):
        self.bd_xe_list = []
        self.bd_xe_listbox.delete(0, tk.END)

    def _gc_skip_add(self):
        sel = self.gc_skip_var.get().strip()
        if not sel:
            return
        path = f"assets/items/{sel}" if not sel.startswith("assets/") else sel
        if not hasattr(self, 'gc_skip_list'):
            self.gc_skip_list = []
        if path in self.gc_skip_list:
            return
        self.gc_skip_list.append(path)
        self.gc_skip_listbox.insert(tk.END, os.path.basename(path))

    def _gc_skip_remove(self):
        sel = self.gc_skip_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if hasattr(self, 'gc_skip_list'):
            self.gc_skip_list.pop(idx)
        self.gc_skip_listbox.delete(idx)

    def _gc_skip_clear(self):
        self.gc_skip_list = []
        self.gc_skip_listbox.delete(0, tk.END)

    def _get_settings_from_ui(self):
        settings = {}
        settings["loop_tong_mode"] = self.loop_tong_mode_var.get()
        try:
            settings["loop_tong"] = int(self.loop_tong_var.get())
        except ValueError:
            settings["loop_tong"] = 1
        try:
            settings["loop"] = int(self.loop_var.get())
        except ValueError:
            settings["loop"] = 1
        try:
            settings["threshold"] = self.global_threshold_var.get()
        except (ValueError, tk.TclError):
            settings["threshold"] = 0.85
        for key, var in self.toggle_vars.items():
            settings[key] = var.get()
        settings["bat_khoi_dong_lai_ld"] = self.bat_khoi_dong_lai_ld_var.get()
        try:
            settings["thoi_gian_khoi_dong_lai"] = float(self.thoi_gian_khoi_dong_lai_var.get())
        except (ValueError, tk.TclError):
            settings["thoi_gian_khoi_dong_lai"] = 5.0
        return settings

    def _get_ban_do_from_ui(self):
        ban_do = {
            "loai_kho": self.bd_loai_kho_var.get(),
            "so_lan_dat_vp": int(self.bd_so_lan_var.get()) if self.bd_so_lan_var.get().isdigit() else 4,
            "data": list(self.bd_vp_list),
            "xoa_kc": self.bd_xoa_kc_var.get(),
            "dat_quang_cao": self.bd_dat_qc_var.get(),
            "check_stock": self.bd_check_stock_var.get(),
            "qc_templates": list(getattr(self, 'bd_qc_list', [])),
            "xoa_kc_templates": list(getattr(self, 'bd_xe_list', [])),
            "dsvp_bo_qua": list(getattr(self, 'gc_skip_list', [])),
            "tom_vp": self._template_path_from_name(self.tom_vp_var.get().strip()),
            "tom_kho": self.tom_kho_var.get(),
        }
        try:
            ban_do["threshold"] = self.bd_threshold_var.get()
        except (ValueError, tk.TclError):
            ban_do["threshold"] = 0.85
        try:
            ban_do["color_threshold"] = self.bd_color_threshold_var.get()
        except (ValueError, tk.TclError):
            ban_do["color_threshold"] = 0.6
        region = self._get_bd_region_from_ui()
        if region:
            ban_do["region"] = region
        return ban_do

    def _set_settings_to_ui(self, settings):
        self.loop_tong_mode_var.set(settings.get("loop_tong_mode", "count"))
        self.loop_tong_var.set(str(settings.get("loop_tong", 1)))
        self.loop_var.set(str(settings.get("loop", 1)))
        self.global_threshold_var.set(settings.get("threshold", 0.85))
        for key, var in self.toggle_vars.items():
            var.set(settings.get(key, DEFAULT_SETTINGS.get(key, False)))
        self.bat_khoi_dong_lai_ld_var.set(settings.get("bat_khoi_dong_lai_ld", False))
        self.thoi_gian_khoi_dong_lai_var.set(float(settings.get("thoi_gian_khoi_dong_lai", 5.0)))


    def _set_ban_do_to_ui(self, ban_do):
        self.bd_loai_kho_var.set(ban_do.get("loai_kho", "KTP"))
        self.bd_so_lan_var.set(str(ban_do.get("so_lan_dat_vp", 4)))
        self.bd_xoa_kc_var.set(ban_do.get("xoa_kc", True))
        self.bd_dat_qc_var.set(ban_do.get("dat_quang_cao", True))
        self.bd_check_stock_var.set(ban_do.get("check_stock", False))
        self._set_bd_region_to_ui(ban_do.get("region"))
        # Set QC/XE lists
        qc_list = ban_do.get("qc_templates", [])
        xe_list = ban_do.get("xoa_kc_templates", [])
        gc_skip_list = ban_do.get("dsvp_bo_qua", [])
        tom_vp = ban_do.get("tom_vp", "")
        self.tom_kho_var.set(ban_do.get("tom_kho", "KTP"))
        # Set first item into the small selector vars (for quick add preview)
        if qc_list:
            self.bd_qc_var.set(os.path.basename(qc_list[0]))
        if xe_list:
            self.bd_xe_var.set(os.path.basename(xe_list[0]))
        if gc_skip_list:
            first_gc_skip = gc_skip_list[0].get("path") if isinstance(gc_skip_list[0], dict) else gc_skip_list[0]
            if first_gc_skip:
                self.gc_skip_var.set(os.path.basename(first_gc_skip))
        if tom_vp:
            self.tom_vp_var.set(os.path.basename(tom_vp))
        self.gc_skip_list = list(gc_skip_list)
        self.gc_skip_listbox.delete(0, tk.END)
        for path in self.gc_skip_list:
            self.gc_skip_listbox.insert(tk.END, os.path.basename(path))
        self.bd_threshold_var.set(ban_do.get("threshold", 0.85))
        self.bd_color_threshold_var.set(ban_do.get("color_threshold", 0.6))

        # Chuẩn hóa data: hỗ trợ cả list[str] (legacy) và list[dict] (mới)
        raw_data = ban_do.get("data", [])
        self.bd_vp_list = []
        self.bd_vp_listbox.delete(0, tk.END)
        for item in raw_data:
            if isinstance(item, str):
                vp_info = {"path": item}
            elif isinstance(item, dict):
                vp_info = dict(item)
            else:
                continue
            self.bd_vp_list.append(vp_info)
            # Hiển thị
            name = os.path.basename(vp_info.get("path", ""))
            extras = []
            if "threshold" in vp_info:
                extras.append(f"t={vp_info['threshold']}")
            if "color_threshold" in vp_info:
                extras.append(f"c={vp_info['color_threshold']}")
            if "region" in vp_info:
                extras.append(f"r={format_region(vp_info['region'])}")
            display = name + (f"  ({', '.join(extras)})" if extras else "")
            self.bd_vp_listbox.insert(tk.END, display)
        # Load qc list
        self.bd_qc_list = []
        self.bd_qc_listbox.delete(0, tk.END)
        for tpl in qc_list:
            if isinstance(tpl, dict):
                path = tpl.get("path")
            else:
                path = tpl
            if not path:
                continue
            self.bd_qc_list.append(path)
            self.bd_qc_listbox.insert(tk.END, os.path.basename(path))

        # Load xoa kc list
        self.bd_xe_list = []
        self.bd_xe_listbox.delete(0, tk.END)
        for tpl in xe_list:
            if isinstance(tpl, dict):
                path = tpl.get("path")
            else:
                path = tpl
            if not path:
                continue
            self.bd_xe_list.append(path)
            self.bd_xe_listbox.insert(tk.END, os.path.basename(path))

    def _load_preview(self, filename, max_size=40):
        """Load anh preview tu assets/items/, tra ve ImageTk.PhotoImage hoac None."""
        if not filename:
            return None
        if os.path.isabs(filename) or filename.startswith("assets"):
            path = filename
        else:
            path = os.path.join(ITEMS_DIR, filename)
        if not os.path.isfile(path):
            return None
        try:
            from PIL import Image, ImageTk
            img = Image.open(path)
            img.thumbnail((max_size, max_size), Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception:
            return None

    def _update_item_preview(self):
        photo = self._load_preview(self.path_item_var.get())
        self._item_preview_photo = photo
        self.item_preview_label.config(image=photo if photo else "", text="")

    def _update_default_preview(self):
        photo = self._load_preview(self.path_item_default_var.get())
        self._default_preview_photo = photo
        self.default_preview_label.config(image=photo if photo else "", text="")

    def _update_bd_vp_preview(self):
        photo = self._load_preview(self.bd_vp_var.get())
        self._bd_vp_preview_photo = photo
        self.bd_vp_preview_label.config(image=photo if photo else "", text="")

    def _update_bd_qc_preview(self):
        photo = self._load_preview(self.bd_qc_var.get())
        self._bd_qc_preview_photo = photo
        self.bd_qc_preview_label.config(image=photo if photo else "", text="")

    def _update_bd_xoa_kc_preview(self):
        photo = self._load_preview(self.bd_xe_var.get())
        self._bd_xoa_kc_preview_photo = photo
        self.bd_xoa_kc_preview_label.config(image=photo if photo else "", text="")

    def _update_gc_skip_preview(self):
        photo = self._load_preview(self.gc_skip_var.get())
        self._gc_skip_preview_photo = photo
        self.gc_skip_preview_label.config(image=photo if photo else "", text="")

    def _update_tom_vp_preview(self):
        photo = self._load_preview(self.tom_vp_var.get())
        self._tom_vp_preview_photo = photo
        self.tom_vp_preview_label.config(image=photo if photo else "", text="")

    def _open_index_picker(self):
        """Mo popup grid 4x6 de chon vi tri indexs."""
        popup = tk.Toplevel(self.root)
        popup.title("Chọn vị trí")
        popup.geometry("420x320")
        popup.resizable(False, False)
        popup.transient(self.root)
        popup.grab_set()

        tk.Label(popup, text="Tích chọn các vị trí cần trồng/thu hoạch:",
                 font=("Arial", 10, "bold"), pady=8).pack()

        grid_frame = tk.Frame(popup, padx=20, pady=5)
        grid_frame.pack()

        # Header cot
        tk.Label(grid_frame, text="", width=6).grid(row=0, column=0)
        for col in range(1, 7):
            tk.Label(grid_frame, text=f"Cột {col}", font=("Arial", 9, "bold"),
                     width=6, anchor=tk.CENTER).grid(row=0, column=col)

        # Checkboxes 4 hang x 6 cot
        cb_vars = {}
        for row in range(1, 5):
            tk.Label(grid_frame, text=f"Hàng {row}", font=("Arial", 9, "bold"),
                     anchor=tk.W).grid(row=row, column=0, sticky=tk.W)
            for col in range(1, 7):
                key = f"{row}.{col}"
                var = tk.BooleanVar(value=key in self.selected_indexs)
                cb_vars[key] = var
                cb = tk.Checkbutton(grid_frame, variable=var, width=4,
                                     relief=tk.GROOVE, bd=1, indicatoron=True)
                cb.grid(row=row, column=col, padx=2, pady=2)

        # Quick select buttons
        quick_frame = tk.Frame(popup, pady=8)
        quick_frame.pack()

        def select_row(r):
            for col in range(1, 7):
                cb_vars[f"{r}.{col}"].set(True)

        def select_all():
            for var in cb_vars.values():
                var.set(True)

        def clear_all():
            for var in cb_vars.values():
                var.set(False)

        for r in range(1, 5):
            tk.Button(quick_frame, text=f"Hàng {r}", command=lambda r=r: select_row(r),
                      bg="#3498db", fg="white", relief=tk.FLAT, padx=6,
                      font=("Arial", 8), cursor="hand2").pack(side=tk.LEFT, padx=3)

        tk.Button(quick_frame, text="Tất cả", command=select_all,
                  bg="#27ae60", fg="white", relief=tk.FLAT, padx=8,
                  font=("Arial", 8), cursor="hand2").pack(side=tk.LEFT, padx=3)
        tk.Button(quick_frame, text="Bỏ chọn", command=clear_all,
                  bg="#e74c3c", fg="white", relief=tk.FLAT, padx=8,
                  font=("Arial", 8), cursor="hand2").pack(side=tk.LEFT, padx=3)

        # OK / Cancel
        btn_frame = tk.Frame(popup, pady=8)
        btn_frame.pack()

        def on_ok():
            self.selected_indexs = [k for k in sorted(cb_vars.keys(),
                                    key=lambda x: (int(x.split('.')[0]), int(x.split('.')[1])))
                                    if cb_vars[k].get()]
            if self.selected_indexs:
                self.indexs_display.config(text=", ".join(self.selected_indexs))
            else:
                self.indexs_display.config(text="(chưa chọn)")
            popup.destroy()

        tk.Button(btn_frame, text="Xác nhận", command=on_ok,
                  bg="#27ae60", fg="white", relief=tk.FLAT, padx=20, pady=5,
                  font=("Arial", 10, "bold"), cursor="hand2").pack(side=tk.LEFT, padx=8)
        tk.Button(btn_frame, text="Hủy", command=popup.destroy,
                  bg="#95a5a6", fg="white", relief=tk.FLAT, padx=20, pady=5,
                  font=("Arial", 10), cursor="hand2").pack(side=tk.LEFT, padx=8)

    def _add_item_to_list(self):
        self._editing_index = None  # Thêm mới, không phải sửa
        t = self.type_var.get()
        row = self.row_var.get()
        path_row_file = self.path_row_var.get()
        path_row = f"assets/items/num/{path_row_file}"
        region = self._get_task_region_from_ui()

        if t == "TC":
            indexs = list(self.selected_indexs)
            if not indexs:
                messagebox.showwarning("Lỗi", "Vui lòng chọn vị trí!")
                return

            path_item_file = self.path_item_var.get()
            path_item = f"assets/items/{path_item_file}"
            path_default_file = self.path_item_default_var.get()
            path_default = f"assets/items/{path_default_file}" if path_default_file else path_item

            th = self.threshold_var.get()
            item = {
                "id": 1,
                "row": int(row),
                "type": "TC",
                "indexs": indexs,
                "path_row": path_row,
                "path_item": path_item,
                "path_item_default": path_default,
                "threshold": th
            }
            if region:
                item["region"] = region
            th_label = f" th={th}" if th != 0.85 else ""
            display_extra = ", ".join(indexs[:6]) + ("..." if len(indexs) > 6 else "") + th_label
            display_item = path_item_file

        elif t == "MAY":
            path_item_file = self.path_item_var.get()
            path_item = f"assets/items/{path_item_file}"
            try:
                total = int(self.total_entry.get().strip())
            except ValueError:
                total = 4

            item = {
                "id": 2,
                "row": int(row),
                "type": "MAY",
                "path_row": path_row,
                "data": [{"path_item": path_item, "total": total}]
            }
            if region:
                item["region"] = region
            display_extra = f"{path_item_file} x{total}"
            display_item = path_item_file
        else:
            return

        self.config_items.append(item)
        self._refresh_tree()

    def _refresh_tree(self):
        for item in self.cfg_tree.get_children():
            self.cfg_tree.delete(item)
        for i, cfg in enumerate(self.config_items, 1):
            t = cfg.get("type", "?")
            row = cfg.get("row", "?")
            if t == "TC":
                pi = os.path.basename(cfg.get("path_item", ""))
                idxs = cfg.get("indexs", [])
                extra = ", ".join(idxs[:8]) + ("..." if len(idxs) > 8 else "")
            elif t == "MAY":
                data = cfg.get("data", [])
                pi = ", ".join(os.path.basename(d["path_item"]) for d in data)
                extra = ", ".join(f"x{d.get('total',1)}" for d in data)
            else:
                pi = ""
                extra = ""
            self.cfg_tree.insert("", tk.END, values=(i, t, row, pi, extra, format_region(cfg.get("region"))))

    def _remove_selected(self):
        sel = self.cfg_tree.selection()
        if not sel:
            return
        idx = self.cfg_tree.index(sel[0])
        self.config_items.pop(idx)
        self._refresh_tree()

    def _move_item(self, direction):
        sel = self.cfg_tree.selection()
        if not sel:
            return
        idx = self.cfg_tree.index(sel[0])
        new_idx = idx + direction
        if 0 <= new_idx < len(self.config_items):
            self.config_items[idx], self.config_items[new_idx] = \
                self.config_items[new_idx], self.config_items[idx]
            self._refresh_tree()
            children = self.cfg_tree.get_children()
            self.cfg_tree.selection_set(children[new_idx])

    def _clear_list(self):
        if self.config_items:
            if messagebox.askyesno("Xác nhận", "Xóa tất cả mục trong danh sách?"):
                self.config_items.clear()
                self._refresh_tree()

    def _edit_selected(self):
        """Load mục đang chọn trong tree lên form để sửa."""
        sel = self.cfg_tree.selection()
        if not sel:
            messagebox.showinfo("Thông báo", "Chọn 1 mục trong danh sách để sửa!")
            return
        idx = self.cfg_tree.index(sel[0])
        item = self.config_items[idx]
        self._editing_index = idx

        t = item.get("type", "TC")
        self.type_var.set(t)
        self.row_var.set(str(item.get("row", 1)))
        self._set_task_region_to_ui(item.get("region"))

        path_row = item.get("path_row", "")
        self.path_row_var.set(os.path.basename(path_row))

        if t == "TC":
            path_item = item.get("path_item", "")
            self.path_item_var.set(os.path.basename(path_item))

            path_default = item.get("path_item_default", "")
            self.path_item_default_var.set(os.path.basename(path_default))

            self.selected_indexs = list(item.get("indexs", []))
            if self.selected_indexs:
                self.indexs_display.config(text=", ".join(self.selected_indexs))
            else:
                self.indexs_display.config(text="(chưa chọn)")

            th = item.get("threshold", 0.85)
            self.threshold_var.set(th)

        elif t == "MAY":
            data = item.get("data", [])
            if data:
                self.path_item_var.set(os.path.basename(data[0].get("path_item", "")))
                self.total_entry.delete(0, tk.END)
                self.total_entry.insert(0, str(data[0].get("total", 4)))

        self._update_item_preview()
        self._update_default_preview()

        # Highlight row đang sửa
        self.cfg_tree.selection_set(sel[0])
        self.cfg_tree.focus(sel[0])

    def _update_selected_item(self):
        """Cập nhật mục đang sửa (thay vì thêm mới)."""
        if self._editing_index is None:
            messagebox.showinfo("Thông báo", "Chưa chọn mục để sửa!\n"
                                "Bấm 'Sửa' hoặc double-click 1 mục trước.")
            return

        idx = self._editing_index
        if idx < 0 or idx >= len(self.config_items):
            self._editing_index = None
            return

        t = self.type_var.get()
        row = self.row_var.get()
        path_row_file = self.path_row_var.get()
        path_row = f"assets/items/num/{path_row_file}"
        region = self._get_task_region_from_ui()

        if t == "TC":
            indexs = list(self.selected_indexs)
            if not indexs:
                messagebox.showwarning("Lỗi", "Vui lòng chọn vị trí!")
                return

            path_item_file = self.path_item_var.get()
            path_item = f"assets/items/{path_item_file}"
            path_default_file = self.path_item_default_var.get()
            path_default = f"assets/items/{path_default_file}" if path_default_file else path_item
            th = self.threshold_var.get()

            new_item = {
                "id": 1,
                "row": int(row),
                "type": "TC",
                "indexs": indexs,
                "path_row": path_row,
                "path_item": path_item,
                "path_item_default": path_default,
                "threshold": th
            }
            if region:
                new_item["region"] = region

        elif t == "MAY":
            path_item_file = self.path_item_var.get()
            path_item = f"assets/items/{path_item_file}"
            try:
                total = int(self.total_entry.get().strip())
            except ValueError:
                total = 4

            new_item = {
                "id": 2,
                "row": int(row),
                "type": "MAY",
                "path_row": path_row,
                "data": [{"path_item": path_item, "total": total}]
            }
            if region:
                new_item["region"] = region
        else:
            return

        self.config_items[idx] = new_item
        self._editing_index = None
        self._refresh_tree()

        # Highlight mục vừa sửa
        children = self.cfg_tree.get_children()
        if idx < len(children):
            self.cfg_tree.selection_set(children[idx])
            self.cfg_tree.focus(children[idx])

    def _open_smart_recipe_dialog(self):
        """Mở popup tính toán & tự động tạo chu trình sản xuất (Hỗ trợ nhiều vật phẩm)."""
        from core.recipe_builder import (
            get_available_products, calculate_multi_requirements,
            generate_multi_product_config, generate_plant_tasks, RECIPES, CROPS
        )

        popup = tk.Toplevel(self.root)
        popup.title("⚡ Tạo chu trình tự động (Smart Recipe)")
        popup.geometry("720x680")
        popup.resizable(True, True)
        popup.transient(self.root)
        popup.grab_set()

        # Header
        hdr = tk.Frame(popup, bg="#8e44ad", height=45)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="⚡ TỰ ĐỘNG TÍNH TOÁN & TẠO CHU TRÌNH SẢN XUẤT (ĐA VẬT PHẨM)",
                 font=("Arial", 11, "bold"), fg="white", bg="#8e44ad").pack(pady=12)

        content = tk.Frame(popup, bg="#ecf0f1", padx=15, pady=10)
        content.pack(fill=tk.BOTH, expand=True)

        # 1. Chọn sản phẩm & Thêm vào giỏ
        f_select = tk.LabelFrame(content, text="1. Chọn thành phẩm & Số lượng", font=("Arial", 9, "bold"),
                                 bg="#ecf0f1", padx=10, pady=8)
        f_select.pack(fill=tk.X, pady=(0, 6))

        r_p = tk.Frame(f_select, bg="#ecf0f1")
        r_p.pack(fill=tk.X, pady=2)
        tk.Label(r_p, text="Thành phẩm:", bg="#ecf0f1", width=12, anchor=tk.W, font=("Arial", 9)).pack(side=tk.LEFT)

        products = get_available_products()
        prod_dict = {name: key for key, name in products}
        prod_names = [name for _, name in products]

        selected_prod_name_var = tk.StringVar()
        if prod_names:
            selected_prod_name_var.set(prod_names[0])

        prod_combo = ttk.Combobox(r_p, textvariable=selected_prod_name_var, values=prod_names,
                                  state="readonly", width=32, font=("Arial", 9))
        prod_combo.pack(side=tk.LEFT, padx=(0, 6))

        # Preview ảnh thành phẩm
        item_preview_f = tk.Frame(r_p, width=34, height=34, bg="white", relief=tk.SUNKEN, bd=1)
        item_preview_f.pack_propagate(False)
        item_preview_f.pack(side=tk.LEFT, padx=(0, 10))
        prod_preview_lbl = tk.Label(item_preview_f, bg="white")
        prod_preview_lbl.pack(expand=True)

        tk.Label(r_p, text="SL:", bg="#ecf0f1", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        qty_var = tk.StringVar(value="4")
        qty_spin = tk.Spinbox(r_p, from_=1, to=999, textvariable=qty_var, width=5, font=("Arial", 9))
        qty_spin.pack(side=tk.LEFT, padx=(4, 8))

        # Danh sách giỏ hàng sản xuất
        basket_items = []  # List of {"key": p_key, "name": p_name, "quantity": q}

        # 2. Danh sách các món đã chọn
        f_basket = tk.LabelFrame(content, text="2. Danh sách sản phẩm cần auto (Giỏ hàng)", font=("Arial", 9, "bold"),
                                 bg="#ecf0f1", padx=10, pady=6)
        f_basket.pack(fill=tk.X, pady=(0, 6))

        basket_list_frame = tk.Frame(f_basket, bg="#ecf0f1")
        basket_list_frame.pack(fill=tk.X)

        basket_listbox = tk.Listbox(basket_list_frame, font=("Arial", 9), height=4, relief=tk.SOLID, bd=1)
        basket_scroll = tk.Scrollbar(basket_list_frame, command=basket_listbox.yview)
        basket_listbox.config(yscrollcommand=basket_scroll.set)
        basket_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        basket_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)

        basket_btn_bar = tk.Frame(f_basket, bg="#ecf0f1")
        basket_btn_bar.pack(fill=tk.X, pady=(4, 0))

        # 3. Chi tiết tính toán
        f_calc = tk.LabelFrame(content, text="3. Bảng tổng hợp nguyên liệu & các bước máy", font=("Arial", 9, "bold"),
                               bg="#ecf0f1", padx=10, pady=6)
        f_calc.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        calc_text = tk.Text(f_calc, font=("Consolas", 9), bg="white", height=8, wrap=tk.WORD, relief=tk.SOLID, bd=1)
        calc_scroll = tk.Scrollbar(f_calc, command=calc_text.yview)
        calc_text.config(yscrollcommand=calc_scroll.set)
        calc_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        calc_text.pack(fill=tk.BOTH, expand=True)

        def update_calc_view(*_):
            # Cập nhật preview ảnh món đang chọn
            p_name = selected_prod_name_var.get()
            p_key = prod_dict.get(p_name)
            if p_key:
                item_path = RECIPES[p_key]["path_item"]
                photo = self._load_preview(item_path, max_size=30)
                prod_preview_lbl.config(image=photo if photo else "", text="")
                prod_preview_lbl.image = photo

            # Nếu giỏ hàng có đồ thì tính theo giỏ hàng, nếu chưa có thì tính theo món đang chọn
            current_items = list(basket_items)
            if not current_items:
                try:
                    q = int(qty_var.get())
                    if q <= 0:
                        q = 1
                except ValueError:
                    q = 4
                if p_key:
                    current_items = [{"key": p_key, "name": p_name, "quantity": q}]

            if not current_items:
                calc_text.config(state=tk.NORMAL)
                calc_text.delete("1.0", tk.END)
                calc_text.insert(tk.END, "Chưa chọn sản phẩm nào.")
                calc_text.config(state=tk.DISABLED)
                return

            try:
                multi_reqs = calculate_multi_requirements(current_items)
                total_crops = sum(multi_reqs["raw_crops"].values())

                calc_text.config(state=tk.NORMAL)
                calc_text.delete("1.0", tk.END)

                calc_text.insert(tk.END, "🎯 MỤC TIÊU SẢN XUẤT:\n")
                for itm in current_items:
                    calc_text.insert(tk.END, f"   • {itm['name']} x {itm['quantity']}\n")

                calc_text.insert(tk.END, "━" * 50 + "\n")
                calc_text.insert(tk.END, f"🌾 TỔNG NGUYÊN LIỆU CÂY TRỒNG ({total_crops} chậu):\n")
                for c_key, count in multi_reqs["raw_crops"].items():
                    c_name = CROPS.get(c_key, {}).get("name", c_key)
                    calc_text.insert(tk.END, f"   • Cây {c_name}: {count} cây\n")

                calc_text.insert(tk.END, "\n🏭 CÁC BƯỚC MÁY SẢN XUẤT (THEO THỨ TỰ LOGIC):\n")
                for idx_m, m in enumerate(multi_reqs["machines"], 1):
                    item_file = os.path.basename(m["path_item"])
                    calc_text.insert(tk.END, f"   {idx_m}. Máy {m['machine_row']} (Tầng {m['machine_row']}): {item_file} x{m['total']}\n")

                calc_text.insert(tk.END, "\n☁️ PHÂN BỔ CỤM TẦNG MÂY:\n")
                plant_tasks = generate_plant_tasks(multi_reqs["raw_crops"])
                for pt in plant_tasks:
                    c_file = os.path.basename(pt["path_item"])
                    calc_text.insert(tk.END, f"   • Dừng Row {pt['row']}: Gieo {c_file} vào {len(pt['indexs'])} ô ({', '.join(pt['indexs'][:4])}...)\n")

                calc_text.config(state=tk.DISABLED)
            except Exception as ex:
                calc_text.config(state=tk.NORMAL)
                calc_text.delete("1.0", tk.END)
                calc_text.insert(tk.END, f"Lỗi tính toán: {ex}")
                calc_text.config(state=tk.DISABLED)

        def add_to_basket():
            p_name = selected_prod_name_var.get()
            p_key = prod_dict.get(p_name)
            if not p_key:
                return
            try:
                q = int(qty_var.get())
                if q <= 0:
                    q = 1
            except ValueError:
                q = 4

            # Nếu đã có trong giỏ thì cộng dồn số lượng
            found = False
            for itm in basket_items:
                if itm["key"] == p_key:
                    itm["quantity"] += q
                    found = True
                    break
            if not found:
                basket_items.append({"key": p_key, "name": p_name, "quantity": q})

            _refresh_basket_listbox()
            update_calc_view()

        def remove_from_basket():
            sel = basket_listbox.curselection()
            if not sel:
                return
            idx = sel[0]
            basket_items.pop(idx)
            _refresh_basket_listbox()
            update_calc_view()

        def clear_basket():
            basket_items.clear()
            _refresh_basket_listbox()
            update_calc_view()

        def _refresh_basket_listbox():
            basket_listbox.delete(0, tk.END)
            for idx, itm in enumerate(basket_items, 1):
                basket_listbox.insert(tk.END, f"{idx}. {itm['name']}  ───  Số lượng: {itm['quantity']}")

        tk.Button(r_p, text="+ Thêm vào giỏ", command=add_to_basket,
                  bg="#2980b9", fg="white", relief=tk.FLAT, cursor="hand2",
                  font=("Arial", 9, "bold"), padx=10).pack(side=tk.LEFT)

        tk.Button(basket_btn_bar, text="Xóa món chọn", command=remove_from_basket,
                  bg="#e67e22", fg="white", relief=tk.FLAT, cursor="hand2",
                  font=("Arial", 8), padx=8).pack(side=tk.LEFT)
        tk.Button(basket_btn_bar, text="Xóa tất cả", command=clear_basket,
                  bg="#e74c3c", fg="white", relief=tk.FLAT, cursor="hand2",
                  font=("Arial", 8), padx=8).pack(side=tk.LEFT, padx=6)

        selected_prod_name_var.trace_add("write", update_calc_view)
        qty_var.trace_add("write", update_calc_view)
        prod_combo.bind("<<ComboboxSelected>>", update_calc_view)
        update_calc_view()

        # 4. Chế độ áp dụng
        f_mode = tk.Frame(content, bg="#ecf0f1")
        f_mode.pack(fill=tk.X, pady=(0, 6))
        mode_var = tk.StringVar(value="replace")
        tk.Radiobutton(f_mode, text="Ghi đè danh sách công việc", variable=mode_var,
                       value="replace", bg="#ecf0f1", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        tk.Radiobutton(f_mode, text="Nối tiếp vào cuối danh sách", variable=mode_var,
                       value="append", bg="#ecf0f1", font=("Arial", 9)).pack(side=tk.LEFT, padx=15)

        # 5. Buttons
        btn_bar = tk.Frame(content, bg="#ecf0f1")
        btn_bar.pack(fill=tk.X, pady=(4, 0))

        def apply_recipe():
            current_items = list(basket_items)
            if not current_items:
                p_name = selected_prod_name_var.get()
                p_key = prod_dict.get(p_name)
                if not p_key:
                    return
                try:
                    q = int(qty_var.get())
                    if q <= 0:
                        q = 1
                except ValueError:
                    q = 4
                current_items = [{"key": p_key, "name": p_name, "quantity": q}]

            new_tasks = generate_multi_product_config(current_items)
            if not new_tasks:
                messagebox.showerror("Lỗi", "Không thể tạo danh sách công việc!")
                return

            if mode_var.get() == "replace":
                self.config_items = list(new_tasks)
            else:
                self.config_items.extend(new_tasks)

            self._refresh_tree()
            popup.destroy()
            summary_str = ", ".join(f"{it['name']} x{it['quantity']}" for it in current_items)
            messagebox.showinfo("Thành công", f"Đã tự động tạo {len(new_tasks)} công việc cho:\n{summary_str}!")

        tk.Button(btn_bar, text="⚡ Áp dụng toàn bộ vào cấu hình", command=apply_recipe,
                  bg="#27ae60", fg="white", relief=tk.FLAT, cursor="hand2",
                  padx=16, pady=6, font=("Arial", 10, "bold")).pack(side=tk.LEFT)

        tk.Button(btn_bar, text="Đóng", command=popup.destroy,
                  bg="#95a5a6", fg="white", relief=tk.FLAT, cursor="hand2",
                  padx=16, pady=6, font=("Arial", 10)).pack(side=tk.RIGHT)


    def _save_config(self):
        name = self.cfg_name_entry.get().strip()
        if not name:
            messagebox.showwarning("Lỗi", "Vui lòng nhập tên cấu hình!")
            return

        safe_name = "".join(c for c in name if c.isalnum() or c in "_- ").strip()
        if not safe_name:
            safe_name = "config"

        path = os.path.join(CONFIG_DIR, f"{safe_name}.json")
        if os.path.exists(path):
            if not messagebox.askyesno("Xác nhận", f"File '{safe_name}.json' đã tồn tại. Ghi đè?"):
                return

        config_data = {
            "settings": self._get_settings_from_ui(),
            "tasks": list(self.config_items),
            "ban_do": self._get_ban_do_from_ui()
        }

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Thành công", f"Đã lưu: {path}")
            self._refresh_configs()
            self._refresh_cfg_load_combo()
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không lưu được: {e}")

    def _refresh_cfg_load_combo(self):
        files = glob_mod.glob(os.path.join(CONFIG_DIR, "*.json"))
        names = sorted([
            os.path.splitext(os.path.basename(f))[0]
            for f in files
            if not os.path.basename(f).startswith("global_setting")
        ])
        self.cfg_load_combo["values"] = names
        if names:
            if "mac_dinh" in names:
                self.cfg_load_combo.set("mac_dinh")
            else:
                self.cfg_load_combo.current(0)


    def _load_config_to_editor(self):
        name = self.cfg_load_var.get()
        if not name:
            messagebox.showwarning("Lỗi", "Chọn file cấu hình cần tải!")
            return
        path = os.path.join(CONFIG_DIR, f"{name}.json")
        if not os.path.exists(path):
            messagebox.showerror("Lỗi", f"File không tồn tại: {path}")
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, dict) and "tasks" in data:
                self._set_settings_to_ui(data.get("settings", DEFAULT_SETTINGS))
                self.config_items = data.get("tasks", [])
                self._set_ban_do_to_ui(data.get("ban_do", DEFAULT_BAN_DO))
            elif isinstance(data, list):
                self._set_settings_to_ui(DEFAULT_SETTINGS)
                self.config_items = data
                self._set_ban_do_to_ui(DEFAULT_BAN_DO)
            else:
                self.config_items = []

            self._refresh_tree()
            self.cfg_name_entry.delete(0, tk.END)
            self.cfg_name_entry.insert(0, name)
            messagebox.showinfo("Thành công", f"Đã tải {len(self.config_items)} tasks từ '{name}.json'")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không đọc được file: {e}")

    def _delete_config_file(self):
        name = self.cfg_load_var.get()
        if not name:
            messagebox.showwarning("Lỗi", "Chọn file cần xóa!")
            return
        path = os.path.join(CONFIG_DIR, f"{name}.json")
        if not os.path.exists(path):
            return
        if messagebox.askyesno("Xác nhận", f"Xóa file '{name}.json'?"):
            os.remove(path)
            self._refresh_configs()
            self._refresh_cfg_load_combo()
            messagebox.showinfo("Xong", f"Đã xóa '{name}.json'")

