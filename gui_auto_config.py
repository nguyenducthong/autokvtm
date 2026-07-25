"""
GUI Auto + Config - 2 tab:
  Tab 1: Chạy auto (chọn LDPlayer + chọn cấu hình)
  Tab 2: Tạo/sửa/xóa cấu hình và lưu file JSON
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import shutil
import threading
import time
import logging
import glob as glob_mod
import zipfile
from datetime import date
import cv2
import urllib.request
import subprocess
import webbrowser
import sys

from core.adb_helper import get_adb_helper, ADBHelper
from core.adb import ADBController
from core.trong_cay import main_tc
from config import CONFIG_LOAI_KHO, REGION_PRESETS, REGION_FROM_CROP, CURRENT_VERSION, GITHUB_API_URL
from utils.daily_stats import format_daily_counts

logger = logging.getLogger(__name__)
GUI_LOG_MAX_LINES = 1000


class DeviceButtonState:
    def __init__(self, owner, serial, state_key):
        self.owner = owner
        self.serial = serial
        self.state_key = state_key

    def config(self, **kwargs):
        if "state" in kwargs:
            card = self.owner.device_cards.get(self.serial)
            if card:
                card[self.state_key] = kwargs["state"]
                self.owner._update_device_row(self.serial)
                self.owner._refresh_device_action_buttons()


class TreeTooltip:
    def __init__(self, widget):
        self.widget = widget
        self.tip = None
        self.text = None

    def show(self, text, x, y):
        if self.text == text and self.tip:
            self.tip.geometry(f"+{x + 14}+{y + 14}")
            return
        self.hide()
        self.text = text
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.geometry(f"+{x + 14}+{y + 14}")
        label = tk.Label(self.tip, text=text, bg="#2c3e50", fg="white",
                         font=("Arial", 8), padx=6, pady=3, relief=tk.SOLID, bd=1)
        label.pack()

    def hide(self):
        if self.tip:
            try:
                self.tip.destroy()
            except tk.TclError:
                pass
        self.tip = None
        self.text = None


class AutocompleteCombobox(ttk.Combobox):
    """Combobox click mo het danh sach, go de loc."""

    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        self._all_values = list(kw.get("values", []))
        self._popup = None
        self._listbox = None
        self.bind("<KeyRelease>", self._on_key)
        self.bind("<ButtonPress-1>", lambda e: self.after(100, self._toggle_popup))
        self.bind("<FocusOut>", lambda e: self.after(150, self._close_popup))
        self.bind("<Return>", self._on_return)

    def set_values(self, values):
        self._all_values = list(values)
        self["values"] = self._all_values

    def _toggle_popup(self):
        if self._popup and self._popup.winfo_exists():
            self._close_popup()
            return
        typed = self.get().strip().lower()
        if typed:
            filtered = [v for v in self._all_values if typed in v.lower()]
            self._show_popup(filtered if filtered else self._all_values)
        else:
            self._show_popup(self._all_values)

    def _on_key(self, event):
        if event.keysym in ("Return", "Escape", "Up", "Down",
                            "Shift_L", "Shift_R", "Control_L", "Control_R"):
            if event.keysym == "Escape":
                self._close_popup()
            elif event.keysym == "Down" and self._listbox:
                self._listbox.focus_set()
                if self._listbox.size() > 0:
                    self._listbox.selection_set(0)
            return

        typed = self.get().strip().lower()
        if not typed:
            self["values"] = self._all_values
            self._show_popup(self._all_values)
            return

        filtered = [v for v in self._all_values if typed in v.lower()]
        self["values"] = filtered if filtered else self._all_values
        self._show_popup(filtered if filtered else self._all_values)

    def _show_popup(self, items):
        MAX_VISIBLE = 5
        if not items:
            self._close_popup()
            return
        if self._popup and self._popup.winfo_exists():
            self._listbox.delete(0, tk.END)
        else:
            self._popup = tk.Toplevel(self)
            self._popup.wm_overrideredirect(True)
            frame = tk.Frame(self._popup, bd=1, relief=tk.SOLID)
            frame.pack(fill=tk.BOTH, expand=True)
            self._lb_scroll = tk.Scrollbar(frame, orient=tk.VERTICAL)
            self._listbox = tk.Listbox(frame, font=("Arial", 9),
                                        selectbackground="#3498db",
                                        selectforeground="white", bd=0,
                                        yscrollcommand=self._lb_scroll.set)
            self._lb_scroll.config(command=self._listbox.yview)
            self._listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            if len(items) > MAX_VISIBLE:
                self._lb_scroll.pack(side=tk.RIGHT, fill=tk.Y)
            self._listbox.bind("<ButtonRelease-1>", self._on_select)
            self._listbox.bind("<Return>", self._on_select)

        for item in items:
            self._listbox.insert(tk.END, item)

        if len(items) > MAX_VISIBLE and hasattr(self, '_lb_scroll'):
            self._lb_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        elif hasattr(self, '_lb_scroll'):
            self._lb_scroll.pack_forget()

        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        w = self.winfo_width()
        h = min(len(items), MAX_VISIBLE) * 20
        self._popup.geometry(f"{w}x{h}+{x}+{y}")
        self._popup.lift()

    def _on_select(self, event):
        if not self._listbox:
            return
        sel = self._listbox.curselection()
        if sel:
            value = self._listbox.get(sel[0])
            self.set(value)
            self["values"] = self._all_values
        self._close_popup()
        self.focus_set()

    def _on_return(self, event):
        self._close_popup()

    def _close_popup(self):
        if self._popup and self._popup.winfo_exists():
            self._popup.destroy()
        self._popup = None
        self._listbox = None

CONFIG_DIR = "configs"
SELECTED_DEVICE_FILE = "selected_device.json"
ITEMS_DIR = "assets/items"

def scan_all_templates():
    """Scan all *.png in assets/items/"""
    files = glob_mod.glob(os.path.join(ITEMS_DIR, "*.png"))
    return sorted([os.path.basename(f) for f in files])

def scan_kho_templates():
    """Scan assets/items/kho_*.png"""
    files = glob_mod.glob(os.path.join(ITEMS_DIR, "*.png"))
    return sorted([os.path.basename(f) for f in files])

DEFAULT_SETTINGS = {
    "loop_tong_mode": "count",
    "loop_tong": 1,
    "loop": 1,
    "threshold": 0.85,
    "bat_trong_cay": True,
    "bat_may": True,
    "bat_ban_vp": False,
    "bat_thu_hoach": True,
    "bat_mo_ruong": False,
    "bat_giao_cu": False,
    "bat_giao_tom": False,
    "bat_sxcam": False,
    "bat_khoi_dong_lai_ld": False,
    "thoi_gian_khoi_dong_lai": 5.0
}

DEFAULT_BAN_DO = {
    "loai_kho": "KTP",
    "so_lan_dat_vp": 4,
    "data": [],
    "xoa_kc": True,
    "dat_quang_cao": True,
    "check_stock": False,
    "qc_templates": [],
    "xoa_kc_templates": [],
    "dsvp_bo_qua": [],
    "tom_vp": "",
    "tom_kho": "KTP",
    "threshold": 0.85,
    "color_threshold": 0.6
}

def normalize_region(region):
    """Return region as [x, y, w, h] or None."""
    if region in (None, "", []):
        return None
    if isinstance(region, str):
        parts = [p.strip() for p in region.replace(";", ",").split(",")]
    elif isinstance(region, (list, tuple)):
        parts = list(region)
    else:
        return None
    if len(parts) != 4:
        return None
    try:
        x, y, w, h = [int(float(p)) for p in parts]
    except (TypeError, ValueError):
        return None
    if w <= 0 or h <= 0:
        return None
    return [x, y, w, h]

def format_region(region):
    region = normalize_region(region)
    return "" if region is None else ",".join(str(v) for v in region)

def scan_row_templates():
    """Scan assets/items/num/*.png"""
    files = glob_mod.glob(os.path.join(ITEMS_DIR, "num", "*.png"))
    results = []
    for f in files:
        name = os.path.basename(f)
        if name.replace(".png", "").isdigit():
            results.append(name)
    return sorted(results, key=lambda x: int(x.replace(".png", "")))


class AutoConfigGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Auto KVTM - Auto & Config")
        w, h = 960, 800
        sx = self.root.winfo_screenwidth()
        sy = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sx - w) // 2}+{(sy - h) // 2}")
        self.root.resizable(True, True)

        self.adb_helper = get_adb_helper()
        self.adb = None
        self.is_running = False
        self.stop_event = threading.Event()

        os.makedirs(CONFIG_DIR, exist_ok=True)

        self._build_ui()
        self._refresh_devices()
        self._refresh_configs()
        self._ss_refresh_devices()
        self._schedule_device_auto_refresh()
        self.check_update_action(silent=True)

    # ================================================================
    # UI
    # ================================================================
    def _build_ui(self):
        # Header
        header = tk.Frame(self.root, bg="#2c3e50", height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="AUTO KHU VƯỜN TRÊN MÂY",
                 font=("Arial", 14, "bold"), fg="white", bg="#2c3e50").pack(side=tk.LEFT, padx=15, pady=12)

        # Version & Update button on the right side of header
        version_frame = tk.Frame(header, bg="#2c3e50")
        version_frame.pack(side=tk.RIGHT, padx=15, pady=10)
        
        tk.Label(version_frame, text=f"v{CURRENT_VERSION}",
                 font=("Arial", 9, "bold"), fg="#bdc3c7", bg="#2c3e50").pack(side=tk.LEFT, padx=(0, 8))
                 
        self.update_btn = tk.Button(version_frame, text="Cập nhật", command=self.check_update_action,
                                    bg="#e74c3c", fg="white", font=("Arial", 9, "bold"),
                                    relief=tk.FLAT, cursor="hand2", padx=10, pady=1)
        self.update_btn.pack(side=tk.LEFT)

        # Notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.tab_auto = tk.Frame(self.notebook, bg="#ecf0f1")
        self.tab_config = tk.Frame(self.notebook, bg="#ecf0f1")
        self.tab_screenshot = tk.Frame(self.notebook, bg="#ecf0f1")
        self.tab_log = tk.Frame(self.notebook, bg="#1e1e1e")

        self.notebook.add(self.tab_auto, text="  Auto  ")
        self.notebook.add(self.tab_config, text="  Cấu Hình  ")
        self.notebook.add(self.tab_screenshot, text="  Chụp & Cắt ảnh  ")
        self.notebook.add(self.tab_log, text="  Nhật Ký  ")

        self._build_tab_auto()
        self._build_tab_config()
        self._build_tab_screenshot()
        self._build_tab_log()

        # Status bar
        self.status_label = tk.Label(self.root, text="Sẵn sàng", font=("Arial", 9),
                                     bg="#27ae60", fg="white", anchor=tk.W, padx=10)
        self.status_label.pack(fill=tk.X, side=tk.BOTTOM)

    # ----------------------------------------------------------------
    # TAB 1: AUTO
    # ----------------------------------------------------------------
    def _build_tab_auto(self):
        pad = tk.Frame(self.tab_auto, bg="#ecf0f1", padx=20, pady=15)
        pad.pack(fill=tk.BOTH, expand=True)

        # --- Config selection ---
        cfg_frame = tk.LabelFrame(pad, text="Cấu hình chạy", font=("Arial", 10, "bold"),
                                  bg="#ecf0f1", padx=12, pady=10)
        cfg_frame.pack(fill=tk.X, pady=(0, 8))

        row1 = tk.Frame(cfg_frame, bg="#ecf0f1")
        row1.pack(fill=tk.X)
        tk.Label(row1, text="Chọn cấu hình:", bg="#ecf0f1", font=("Arial", 10)).pack(side=tk.LEFT)
        self.config_var = tk.StringVar()
        self.config_combo = ttk.Combobox(row1, textvariable=self.config_var, state="readonly",
                                          width=40, font=("Arial", 10))
        self.config_combo.pack(side=tk.LEFT, padx=(8, 8))
        tk.Button(row1, text="Làm mới", command=self._refresh_configs,
                  bg="#3498db", fg="white", relief=tk.FLAT, cursor="hand2",
                  padx=10).pack(side=tk.LEFT)
        self.config_combo.bind("<<ComboboxSelected>>", lambda e: self._preview_config())

        # Preview
        preview_frame = tk.LabelFrame(pad, text="Xem trước", font=("Arial", 10, "bold"),
                                      bg="#ecf0f1", padx=8, pady=6)
        preview_frame.pack(fill=tk.X, pady=(0, 8))
        self.preview_text = tk.Text(preview_frame, font=("Consolas", 8), bg="white",
                                     height=5, wrap=tk.WORD, state=tk.DISABLED)
        preview_scroll = tk.Scrollbar(preview_frame, command=self.preview_text.yview)
        self.preview_text.config(yscrollcommand=preview_scroll.set)
        preview_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.preview_text.pack(fill=tk.BOTH, expand=True)

        # --- Device list (visual cards) ---
        dev_frame = tk.LabelFrame(pad, text="Thiết bị LDPlayer", font=("Arial", 10, "bold"),
                                  bg="#ecf0f1", padx=8, pady=6)
        dev_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        dev_toolbar = tk.Frame(dev_frame, bg="#ecf0f1")
        dev_toolbar.pack(fill=tk.X, pady=(0, 6))
        tk.Button(dev_toolbar, text="Làm mới thiết bị", command=self._refresh_devices,
                  bg="#3498db", fg="white", relief=tk.FLAT, cursor="hand2",
                  padx=10, font=("Arial", 9)).pack(side=tk.LEFT)
        tk.Button(dev_toolbar, text="Chạy tất cả", command=self._start_all,
                  bg="#27ae60", fg="white", relief=tk.FLAT, cursor="hand2",
                  padx=10, font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=4)
        tk.Button(dev_toolbar, text="Dừng tất cả", command=self._stop_all,
                  bg="#c0392b", fg="white", relief=tk.FLAT, cursor="hand2",
                  padx=10, font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        tk.Button(dev_toolbar, text="Quét kho TP", command=self._scan_kho_thanh_pham_all,
                  bg="#8e44ad", fg="white", relief=tk.FLAT, cursor="hand2",
                  padx=10, font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=4)
        tk.Button(dev_toolbar, text="Tải CSV kho TP", command=self._download_kho_thanh_pham_csv,
                  bg="#16a085", fg="white", relief=tk.FLAT, cursor="hand2",
                  padx=10, font=("Arial", 9)).pack(side=tk.LEFT, padx=4)

        # Debug mode checkbox
        self.debug_mode_var = tk.BooleanVar(value=False)
        tk.Checkbutton(dev_toolbar, text="Gỡ lỗi (lưu ảnh)", variable=self.debug_mode_var,
                       bg="#ecf0f1", font=("Arial", 8),
                       command=self._toggle_debug_mode).pack(side=tk.LEFT, padx=(12, 0))
        tk.Button(dev_toolbar, text="Mở thư mục gỡ lỗi", command=self._open_debug_folder,
                  bg="#7f8c8d", fg="white", relief=tk.FLAT, cursor="hand2",
                  font=("Arial", 8), padx=6).pack(side=tk.LEFT, padx=4)

        action_bar = tk.Frame(dev_frame, bg="#ecf0f1")
        self.btn_selected_start_ld = tk.Button(action_bar, text="Mở LD", command=self._start_selected_ldplayer,
                                              bg="#2980b9", fg="white", relief=tk.FLAT, cursor="hand2",
                                              padx=10, font=("Arial", 9, "bold"), state=tk.DISABLED)
        self.btn_selected_start_ld.pack(side=tk.LEFT)
        self.btn_selected_start = tk.Button(action_bar, text="Chạy", command=self._start_selected_device,
                                            bg="#27ae60", fg="white", relief=tk.FLAT, cursor="hand2",
                                            padx=10, font=("Arial", 9, "bold"), state=tk.DISABLED)
        self.btn_selected_start.pack(side=tk.LEFT, padx=4)
        self.btn_selected_stop = tk.Button(action_bar, text="Dừng", command=self._stop_selected_device,
                                           bg="#c0392b", fg="white", relief=tk.FLAT, cursor="hand2",
                                           padx=10, font=("Arial", 9, "bold"), state=tk.DISABLED)
        self.btn_selected_stop.pack(side=tk.LEFT)

        # Device table
        self.device_table = tk.Frame(dev_frame, bg="#cfd8df", bd=1, relief=tk.SOLID)
        self.device_table.pack(fill=tk.BOTH, expand=True)
        self.device_table_tooltip = TreeTooltip(self.device_table)

        header = tk.Frame(self.device_table, bg="#e9eef2")
        header.pack(fill=tk.X)
        self.device_col_widths = (55, 220, 90, 315, 50, 50, 50)
        self.device_col_weights = (0, 1, 0, 1, 0, 0, 0)
        headers = [
            ("STT", tk.CENTER),
            ("Tên LDPlayer", tk.W),
            ("LD", tk.CENTER),
            ("Trạng thái tác vụ", tk.W),
            ("Mở", tk.CENTER),
            ("Chạy", tk.CENTER),
            ("Dừng", tk.CENTER),
        ]
        for col, (text, anchor) in enumerate(headers):
            lbl = tk.Label(header, text=text, bg="#e9eef2", fg="#111111",
                           font=("Arial", 10, "bold"), anchor=anchor,
                           padx=6, pady=6, bd=0, relief=tk.FLAT)
            lbl.grid(row=0, column=col, sticky="nsew", padx=(0, 1), pady=(0, 1))
            header.grid_columnconfigure(col, weight=self.device_col_weights[col],
                                        minsize=self.device_col_widths[col])

        self.device_rows_frame = tk.Frame(self.device_table, bg="#cfd8df")
        self.device_rows_frame.pack(fill=tk.BOTH, expand=True)
        for col in range(len(self.device_col_widths)):
            self.device_rows_frame.grid_columnconfigure(col, weight=self.device_col_weights[col],
                                                       minsize=self.device_col_widths[col])

        self.devices_list = []
        self.device_cards = {}  # serial -> state row cua LDPlayer

        # --- Mini log (5 dong gan nhat) ---
        mini_log_frame = tk.LabelFrame(pad, text="Nhật ký gần đây (xem đầy đủ ở tab Nhật Ký)",
                                        font=("Arial", 9), bg="#ecf0f1", padx=6, pady=4)
        mini_log_frame.pack(fill=tk.X, pady=(4, 0))
        self.mini_log_text = tk.Text(mini_log_frame, font=("Consolas", 8), bg="#2c3e50",
                                      fg="#ecf0f1", height=4, wrap=tk.WORD, state=tk.DISABLED)
        self.mini_log_text.pack(fill=tk.X)

    # ----------------------------------------------------------------
    # TAB 2: CONFIG
    # ----------------------------------------------------------------
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

    def _choose_adb_path(self) -> bool:
        """Cho phép người dùng chọn thư mục LDPlayer chứa adb.exe."""
        adb_path = getattr(self.adb_helper, 'adb_path', None)
        initial_dir = os.path.dirname(adb_path) if isinstance(adb_path, str) else None
        if not initial_dir:
            initial_dir = os.path.expanduser("~")
        selected_dir = filedialog.askdirectory(
            title="Chọn thư mục LDPlayer",
            initialdir=initial_dir
        )
        if not selected_dir:
            return False

        adb_path = os.path.join(selected_dir, "adb.exe")
        if not os.path.isfile(adb_path):
            messagebox.showerror("Lỗi chọn LDPlayer", "Vui lòng chọn thư mục LDPlayer hợp lệ chứa adb.exe.")
            return False

        self.adb_helper.adb_path = adb_path
        self._save_adb_path(selected_dir)
        messagebox.showinfo("Đã chọn LDPlayer", f"Đã đặt thư mục LDPlayer:\n{selected_dir}")
        return True

    def _save_adb_path(self, ldplayer_dir: str):
        """Lưu thư mục LDPlayer vào file cấu hình."""
        data = {}
        if os.path.exists(SELECTED_DEVICE_FILE):
            try:
                with open(SELECTED_DEVICE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f) or {}
            except Exception:
                data = {}

        adb_path = os.path.join(ldplayer_dir, "adb.exe")
        data['ldplayer_dir'] = ldplayer_dir
        if os.path.isfile(adb_path):
            data['adb_path'] = adb_path

        try:
            with open(SELECTED_DEVICE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.exception(f"Lỗi khi lưu đường dẫn ADB: {e}")

    # ================================================================
    # TAB AUTO: LOGIC
    # ================================================================
    def _schedule_device_auto_refresh(self):
        try:
            if not getattr(self, "_device_refresh_busy", False):
                self._refresh_devices(silent=True)
        finally:
            self.root.after(10000, self._schedule_device_auto_refresh)

    def _refresh_devices(self, silent=False):
        try:
            self._device_refresh_busy = True
            players = self.adb_helper.get_ldplayers()
            self.devices_list = []
            old_states = {}
            for old_serial, old_card in self.device_cards.items():
                key = old_card.get("index") if old_card.get("index") is not None else old_serial
                thread = old_card.get("thread")
                try:
                    status_text = old_card["status_label"].cget("text")
                    status_fg = old_card["status_label"].cget("fg")
                    dot_fg = old_card["status_dot"].cget("fg")
                except tk.TclError:
                    status_text = None
                    status_fg = None
                    dot_fg = None
                old_states[key] = {
                    "thread": thread,
                    "stop_event": old_card.get("stop_event"),
                    "status_text": status_text,
                    "status_fg": status_fg,
                    "dot_fg": dot_fg,
                }
            # Xóa cards cũ
            for w in self.dev_list_frame.winfo_children():
                w.destroy()
            self.device_cards = {}

            for player in players:
                self.devices_list.append(player)
                self._create_device_card(
                    player["serial"],
                    player["name"],
                    index=player.get("index"),
                    running=player.get("running", False),
                    adb_port=player.get("adb_port"),
                )
                key = player.get("index") if player.get("index") is not None else player["serial"]
                old_state = old_states.get(key)
                if old_state:
                    self._restore_card_state(player["serial"], old_state)

            if not players:
                tk.Label(self.dev_list_frame, text="Không tìm thấy thiết bị. Bấm 'Làm mới'.",
                         bg="#ecf0f1", fg="#7f8c8d", font=("Arial", 10)).pack(pady=10)
            running_count = sum(1 for p in players if p.get("running"))
            if not silent:
                self.status_label.config(text=f"Tìm thấy {len(players)} LDPlayer | Đang chạy {running_count}")
        except (FileNotFoundError, OSError) as e:
            if silent:
                return
            self.status_label.config(text="✗ Lỗi: Không tìm thấy ADB")
            if messagebox.askyesno(
                "Lỗi ADB",
                "Không tìm thấy ADB!\n\n"
                "Bạn có muốn chọn thư mục LDPlayer thủ công không?"
            ):
                if self._choose_adb_path():
                    self._refresh_devices()
                    return
            messagebox.showerror(
                "Lỗi ADB",
                f"Không tìm thấy ADB!\n\n{e}"
            )
        except Exception as e:
            if "Không tìm thấy ADB" in str(e):
                self.status_label.config(text="✗ Lỗi: Không tìm thấy ADB")
                if messagebox.askyesno(
                    "Lỗi ADB",
                    "Không tìm thấy ADB!\n\n"
                    "Bạn có muốn chọn thư mục LDPlayer thủ công không?"
                ):
                    if self._choose_adb_path():
                        self._refresh_devices()
                        return
            else:
                self.status_label.config(text=f"Lỗi quét thiết bị: {e}")
            messagebox.showerror("Lỗi", f"Có lỗi xảy ra: {e}")
        finally:
            self._device_refresh_busy = False

    def _restore_card_state(self, serial, old_state):
        card = self.device_cards.get(serial)
        if not card:
            return

        thread = old_state.get("thread")
        is_job_running = bool(thread and thread.is_alive())
        card["thread"] = thread
        card["stop_event"] = old_state.get("stop_event")

        if not is_job_running and not card.get("running", False):
            card["status_label"].config(text="Chưa chạy", fg="#7f8c8d")
            card["status_dot"].config(fg="#95a5a6")
            card["btn_start"].config(state=tk.DISABLED)
            card["btn_stop"].config(state=tk.DISABLED)
            card["btn_ld_start"].config(state=tk.NORMAL)
            return

        if not is_job_running:
            return

        if old_state.get("status_text"):
            card["status_label"].config(
                text=old_state["status_text"],
                fg=old_state.get("status_fg") or card["status_label"].cget("fg")
            )
        if old_state.get("dot_fg"):
            card["status_dot"].config(fg=old_state["dot_fg"])

        card["btn_start"].config(state=tk.DISABLED)
        card["btn_stop"].config(state=tk.NORMAL)
        card["btn_ld_start"].config(state=tk.DISABLED)

    def _config_current_card(self, serial, widget_key, **kwargs):
        card = self.device_cards.get(serial)
        if not card:
            return
        widget = card.get(widget_key)
        if not widget:
            return
        try:
            widget.config(**kwargs)
        except tk.TclError:
            pass

    def _create_device_card(self, serial, name, index=None, running=True, adb_port=None):
        """Tạo 1 card cho 1 thiết bị."""
        card = tk.Frame(self.dev_list_frame, bg="white", relief=tk.RIDGE, bd=1, padx=10, pady=6)
        card.pack(fill=tk.X, pady=2)

        # Đèn trạng thái
        status_dot = tk.Label(card, text="●", font=("Arial", 14), fg="#27ae60" if running else "#95a5a6", bg="white")
        status_dot.pack(side=tk.LEFT, padx=(0, 8))

        # Tên + serial
        info = tk.Frame(card, bg="white")
        info.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(info, text=name, font=("Arial", 11, "bold"), bg="white", anchor=tk.W).pack(anchor=tk.W)
        meta = f"index={index} | {serial}" if index is not None else serial
        tk.Label(info, text=meta, font=("Arial", 8), fg="#7f8c8d", bg="white", anchor=tk.W).pack(anchor=tk.W)

        # Trạng thái text
        status_label = tk.Label(card, text="Sẵn sàng" if running else "Chưa chạy", font=("Arial", 9), fg="#27ae60" if running else "#7f8c8d",
                                 bg="white", width=18, anchor=tk.W)
        status_label.pack(side=tk.LEFT, padx=8)

        # Nút Chạy
        btn_ld_start = tk.Button(card, text="Mở LD", font=("Arial", 9, "bold"),
                                 bg="#2980b9", fg="white", relief=tk.FLAT, cursor="hand2",
                                 padx=10, state=tk.DISABLED if running else tk.NORMAL,
                                 command=lambda i=index, s=serial: self._start_ldplayer(i, s))
        btn_ld_start.pack(side=tk.RIGHT, padx=2)

        btn_start = tk.Button(card, text="Chạy", font=("Arial", 9, "bold"),
                               bg="#27ae60", fg="white", relief=tk.FLAT, cursor="hand2",
                               padx=12, state=tk.NORMAL if running else tk.DISABLED, command=lambda s=serial: self._start_one(s))
        btn_start.pack(side=tk.RIGHT, padx=2)

        # Nút Dừng
        btn_stop = tk.Button(card, text="Dừng", font=("Arial", 9, "bold"),
                              bg="#c0392b", fg="white", relief=tk.FLAT, cursor="hand2",
                              padx=12, state=tk.DISABLED,
                              command=lambda s=serial: self._stop_one(s))
        btn_stop.pack(side=tk.RIGHT, padx=2)

        self.device_cards[serial] = {
            "frame": card,
            "status_dot": status_dot,
            "status_label": status_label,
            "btn_start": btn_start,
            "btn_stop": btn_stop,
            "btn_ld_start": btn_ld_start,
            "stop_event": None,
            "thread": None,
            "name": name,
            "index": index,
            "running": running,
            "adb_port": adb_port,
        }

    def _set_card_status(self, serial, status, color):
        """Cập nhật trạng thái card — an toàn từ mọi thread."""
        def _update():
            try:
                if serial not in self.device_cards:
                    return
                c = self.device_cards[serial]
                c["status_label"].config(text=status, fg=color)
            except tk.TclError:
                pass

        try:
            self.root.after(0, _update)
        except RuntimeError:
            pass

    def _start_ldplayer(self, index, serial, silent=False):
        card = self.device_cards.get(serial)
        if card:
            card["btn_ld_start"].config(state=tk.DISABLED)
            card["status_label"].config(text="Đang mở...", fg="#2980b9")
        try:
            self.adb_helper.start_ldplayer(index=index)
            self.status_label.config(text=f"Đang mở LDPlayer index={index}", bg="#2980b9")
            self._open_game_after_ld_start(serial)
            self.root.after(3000, self._refresh_devices)
            self.root.after(8000, self._refresh_devices)
            self.root.after(14000, self._refresh_devices)
            self.root.after(22000, self._refresh_devices)
        except Exception as e:
            if silent:
                return
            if card:
                card["btn_ld_start"].config(state=tk.NORMAL)
                card["status_label"].config(text="Mở lỗi", fg="#e74c3c")
            messagebox.showerror("Lỗi mở LDPlayer", str(e))

    def _refresh_devices(self, silent=False):
        try:
            self._device_refresh_busy = True
            if not getattr(self.adb_helper, "adb_path", None):
                raise FileNotFoundError("Không tìm thấy ADB")
            players = self.adb_helper.get_ldplayers()
            self._sync_device_rows(players)
            running_count = sum(1 for p in players if p.get("running"))
            if not silent:
                self.status_label.config(text=f"Tìm thấy {len(players)} LDPlayer | Đang chạy {running_count}")
            self._refresh_device_action_buttons()
        except (FileNotFoundError, OSError) as e:
            if silent:
                return
            self.status_label.config(text="Lỗi: Không tìm thấy ADB")
            if messagebox.askyesno(
                "Lỗi ADB",
                "Không tìm thấy ADB!\n\nBạn có muốn chọn thư mục LDPlayer thủ công không?"
            ):
                if self._choose_adb_path():
                    self._refresh_devices()
                    return
            messagebox.showerror("Lỗi ADB", f"Không tìm thấy ADB!\n\n{e}")
        except Exception as e:
            if silent:
                return
            self.status_label.config(text=f"Lỗi quét thiết bị: {e}")
            messagebox.showerror("Lỗi", f"Có lỗi xảy ra: {e}")
        finally:
            self._device_refresh_busy = False

    def _sync_device_rows(self, players):
        self.devices_list = list(players)
        old_states = {
            (card.get("index") if card.get("index") is not None else serial): card
            for serial, card in self.device_cards.items()
        }
        seen_serials = set()

        for pos, player in enumerate(players):
            key = player.get("index") if player.get("index") is not None else player["serial"]
            card = self._upsert_device_row(
                player["serial"],
                player["name"],
                index=player.get("index"),
                running=player.get("running", False),
                adb_port=player.get("adb_port"),
                old_state=old_states.get(key),
            )
            seen_serials.add(player["serial"])
            card["row"].pack_forget()
            card["row"].pack(fill=tk.X)
            self._update_device_row(player["serial"])

        for serial, card in list(self.device_cards.items()):
            if serial not in seen_serials:
                try:
                    card["row"].destroy()
                except tk.TclError:
                    pass
                self.device_cards.pop(serial, None)

    def _upsert_device_row(self, serial, name, index=None, running=True, adb_port=None, old_state=None):
        old_state = old_state or {}
        old_serial = old_state.get("serial")
        if old_serial and old_serial != serial and old_serial in self.device_cards:
            self.device_cards.pop(old_serial, None)

        row = old_state.get("row")
        widgets = old_state.get("widgets")
        if not row or not row.winfo_exists():
            row = tk.Frame(self.device_rows_frame, bg="#cfd8df", bd=0, relief=tk.FLAT)
            widgets = self._create_device_row_widgets(row, serial)

        thread = old_state.get("thread")
        is_job_running = bool(thread and thread.is_alive())
        if is_job_running:
            job_status = old_state.get("status", "Đang chạy")
            tag = old_state.get("tag", "working")
            start_state = tk.DISABLED
            stop_state = tk.NORMAL
            ld_start_state = tk.DISABLED
        else:
            job_status = "Sẵn sàng" if running else "Chưa chạy"
            tag = "running" if running else "stopped"
            start_state = tk.NORMAL if running else tk.DISABLED
            stop_state = tk.DISABLED
            ld_start_state = tk.DISABLED if running else tk.NORMAL

        card = {
            "row": row,
            "widgets": widgets,
            "serial": serial,
            "name": name,
            "index": index,
            "running": running,
            "adb_port": adb_port,
            "thread": thread,
            "stop_event": old_state.get("stop_event"),
            "status": job_status,
            "tag": tag,
            "start_state": old_state.get("start_state", start_state) if is_job_running else start_state,
            "stop_state": old_state.get("stop_state", stop_state) if is_job_running else stop_state,
            "ld_start_state": old_state.get("ld_start_state", ld_start_state) if is_job_running else ld_start_state,
        }
        card["btn_start"] = DeviceButtonState(self, serial, "start_state")
        card["btn_stop"] = DeviceButtonState(self, serial, "stop_state")
        card["btn_ld_start"] = DeviceButtonState(self, serial, "ld_start_state")
        self.device_cards[serial] = card
        self._bind_device_row_actions(serial)
        self._update_device_row(serial)
        return card

    def _create_device_row_widgets(self, row, serial):
        anchors = (tk.CENTER, tk.W, tk.CENTER, tk.W, tk.CENTER, tk.CENTER, tk.CENTER)
        keys = ("index", "name", "ld_status", "job_status")
        widgets = {}

        for col, key in enumerate(keys):
            lbl = tk.Label(row, bg="white", fg="#111111", font=("Arial", 10),
                           anchor=anchors[col], padx=6, pady=5,
                           bd=0, relief=tk.FLAT)
            lbl.grid(row=0, column=col, sticky="nsew", padx=(0, 1), pady=(0, 1))
            row.grid_columnconfigure(col, weight=self.device_col_weights[col],
                                     minsize=self.device_col_widths[col])
            widgets[key] = lbl

        button_specs = [
            ("btn_ld", 4, "⏻", "#2980b9", "Mở LDPlayer này"),
            ("btn_run", 5, "▶", "#27ae60", "Chạy auto cho LDPlayer này"),
            ("btn_stop", 6, "■", "#c0392b", "Dừng auto của LDPlayer này"),
        ]
        for key, col, text, color, tooltip in button_specs:
            btn = tk.Label(row, text=text, bg="white", fg=color,
                           font=("Segoe UI Symbol", 14, "bold"),
                           anchor=tk.CENTER, padx=0, pady=0, bd=0, relief=tk.FLAT)
            btn.grid(row=0, column=col, sticky="nsew", padx=(0, 1), pady=(0, 1))
            row.grid_columnconfigure(col, weight=self.device_col_weights[col],
                                     minsize=self.device_col_widths[col])
            btn.bind("<Enter>", lambda e, b=btn, t=tooltip: self._show_device_action_tooltip(e, b, t))
            btn.bind("<Leave>", lambda e: self.device_table_tooltip.hide())
            widgets[key] = btn

        return widgets

    def _show_device_action_tooltip(self, event, button, text):
        if button.cget("text"):
            self.device_table_tooltip.show(text, event.x_root, event.y_root)
        else:
            self.device_table_tooltip.hide()

    def _bind_device_row_actions(self, serial):
        card = self.device_cards.get(serial)
        if not card:
            return
        widgets = card.get("widgets", {})
        widgets["btn_ld"].bind("<Button-1>", lambda e, s=serial: self._start_row_ldplayer(s))
        widgets["btn_run"].bind("<Button-1>", lambda e, s=serial: self._start_row_device(s))
        widgets["btn_stop"].bind("<Button-1>", lambda e, s=serial: self._stop_row_device(s))

    def _start_row_ldplayer(self, serial):
        card = self.device_cards.get(serial)
        if card and card.get("ld_start_state") == tk.NORMAL:
            self._start_ldplayer(card.get("index"), serial)

    def _start_row_device(self, serial):
        card = self.device_cards.get(serial)
        if card and card.get("start_state") == tk.NORMAL:
            self._start_one(serial)

    def _stop_row_device(self, serial):
        card = self.device_cards.get(serial)
        if card and card.get("stop_state") == tk.NORMAL:
            self._stop_one(serial)

    def _update_device_row(self, serial):
        card = self.device_cards.get(serial)
        if not card:
            return
        ld_status = "Đang chạy" if card.get("running") else "Tắt"
        index_text = "" if card.get("index") is None else str(card.get("index"))
        row_bg = "#f4f7f9" if list(self.device_cards).index(serial) % 2 else "#ffffff"
        widgets = card.get("widgets", {})
        widgets["index"].config(text=index_text, bg=row_bg)
        widgets["name"].config(text=card.get("name", ""), bg=row_bg)
        widgets["ld_status"].config(text=ld_status, bg=row_bg)
        status_text = card.get("status", "")
        stats_text = format_daily_counts(serial)
        widgets["job_status"].config(text=f"{status_text}\n{stats_text}", bg=row_bg, justify=tk.LEFT)
        action_state = [
            ("btn_ld", card.get("ld_start_state", tk.DISABLED), "⏻", "#2980b9"),
            ("btn_run", card.get("start_state", tk.DISABLED), "▶", "#27ae60"),
            ("btn_stop", card.get("stop_state", tk.DISABLED), "■", "#c0392b"),
        ]
        for key, state, text, color in action_state:
            enabled = state == tk.NORMAL
            widgets[key].config(
                text=text if enabled else "",
                bg=row_bg,
                fg=color,
                cursor="hand2" if enabled else "",
            )

    def _get_selected_serial(self):
        selected = self.device_tree.selection()
        if not selected:
            return None
        item = selected[0]
        return self._get_serial_by_item(item)

    def _get_serial_by_item(self, item):
        for serial, card in self.device_cards.items():
            if card.get("item") == item:
                return serial
        return None

    def _device_tree_action_at_event(self, event):
        item = self.device_tree.identify_row(event.y)
        col = self.device_tree.identify_column(event.x)
        if not item or col not in ("#6", "#7", "#8"):
            return None, None
        serial = self._get_serial_by_item(item)
        if not serial:
            return None, None
        action = {"#6": "start_ld", "#7": "run", "#8": "stop"}[col]
        return serial, action

    def _on_device_tree_click(self, event):
        serial, action = self._device_tree_action_at_event(event)
        if not serial:
            return
        card = self.device_cards.get(serial)
        if not card:
            return
        self.device_tree.selection_set(card["item"])
        if action == "start_ld" and card.get("ld_start_state") == tk.NORMAL:
            self._start_ldplayer(card.get("index"), serial)
            return "break"
        if action == "run" and card.get("start_state") == tk.NORMAL:
            self._start_one(serial)
            return "break"
        if action == "stop" and card.get("stop_state") == tk.NORMAL:
            self._stop_one(serial)
            return "break"

    def _on_device_tree_motion(self, event):
        serial, action = self._device_tree_action_at_event(event)
        card = self.device_cards.get(serial) if serial else None
        if not card:
            self.device_tree.configure(cursor="")
            self.device_tree_tooltip.hide()
            return
        labels = {
            "start_ld": ("Mở LDPlayer này", card.get("ld_start_state") == tk.NORMAL),
            "run": ("Chạy auto cho LDPlayer này", card.get("start_state") == tk.NORMAL),
            "stop": ("Dừng auto của LDPlayer này", card.get("stop_state") == tk.NORMAL),
        }
        text, enabled = labels.get(action, ("", False))
        if not enabled:
            text = {
                "start_ld": "LDPlayer đang chạy hoặc đang mở",
                "run": "Chỉ chạy khi LDPlayer đang mở và tác vụ đang dừng",
                "stop": "Chỉ dừng khi tác vụ đang chạy",
            }.get(action, "")
        self.device_tree.configure(cursor="hand2" if enabled else "")
        if text:
            self.device_tree_tooltip.show(text, event.x_root, event.y_root)
        else:
            self.device_tree_tooltip.hide()

    def _refresh_device_action_buttons(self):
        if not hasattr(self, "device_tree"):
            return
        serial = self._get_selected_serial()
        card = self.device_cards.get(serial) if serial else None
        if not card:
            self.btn_selected_start_ld.config(state=tk.DISABLED)
            self.btn_selected_start.config(state=tk.DISABLED)
            self.btn_selected_stop.config(state=tk.DISABLED)
            return
        self.btn_selected_start_ld.config(state=card.get("ld_start_state", tk.DISABLED))
        self.btn_selected_start.config(state=card.get("start_state", tk.DISABLED))
        self.btn_selected_stop.config(state=card.get("stop_state", tk.DISABLED))

    def _start_selected_ldplayer(self):
        serial = self._get_selected_serial()
        card = self.device_cards.get(serial) if serial else None
        if card:
            self._start_ldplayer(card.get("index"), serial)

    def _start_selected_device(self):
        serial = self._get_selected_serial()
        if serial:
            self._start_one(serial)

    def _stop_selected_device(self):
        serial = self._get_selected_serial()
        if serial:
            self._stop_one(serial)

    def _set_card_status(self, serial, status, color):
        def _update():
            card = self.device_cards.get(serial)
            if not card:
                return
            card["status"] = status
            if color == "#e74c3c":
                card["tag"] = "error"
            elif color in ("#f39c12", "#e67e22"):
                card["tag"] = "working"
            elif color == "#27ae60":
                card["tag"] = "running"
            elif color == "#c0392b":
                card["tag"] = "error"
            else:
                card["tag"] = "stopped"
            self._update_device_row(serial)
            self._refresh_device_action_buttons()

        self._ui_safe(_update)

    def _config_current_card(self, serial, widget_key, **kwargs):
        card = self.device_cards.get(serial)
        if not card:
            return
        if widget_key == "btn_start" and "state" in kwargs:
            card["start_state"] = kwargs["state"]
        elif widget_key == "btn_stop" and "state" in kwargs:
            card["stop_state"] = kwargs["state"]
        elif widget_key == "btn_ld_start" and "state" in kwargs:
            card["ld_start_state"] = kwargs["state"]
        self._update_device_row(serial)
        self._refresh_device_action_buttons()

    def _start_ldplayer(self, index, serial):
        card = self.device_cards.get(serial)
        if card:
            card["ld_start_state"] = tk.DISABLED
            card["status"] = "Đang mở..."
            card["tag"] = "working"
            self._update_device_row(serial)
            self._refresh_device_action_buttons()
        try:
            self.adb_helper.start_ldplayer(index=index)
            self.status_label.config(text=f"Đang mở LDPlayer index={index}", bg="#2980b9")
            self._open_game_after_ld_start(serial)
            self.root.after(3000, self._refresh_devices)
            self.root.after(8000, self._refresh_devices)
            self.root.after(14000, self._refresh_devices)
            self.root.after(22000, self._refresh_devices)
        except Exception as e:
            if card:
                card["ld_start_state"] = tk.NORMAL
                card["status"] = "Mở lỗi"
                card["tag"] = "error"
                self._update_device_row(serial)
                self._refresh_device_action_buttons()
            messagebox.showerror("Lỗi mở LDPlayer", str(e))

    def _open_game_after_ld_start(self, serial):
        try:
            from config import AUTO_OPEN_GAME_AFTER_LD_START
        except Exception:
            AUTO_OPEN_GAME_AFTER_LD_START = True
        if not AUTO_OPEN_GAME_AFTER_LD_START:
            return

        def run():
            try:
                self._set_card_status(serial, "Đợi LD sẵn sàng...", "#f39c12")
                from core.vao_game import vao_game_sau_khi_start_ld
                ok = vao_game_sau_khi_start_ld(serial)
                if ok:
                    self._set_card_status(serial, "Đã vào game", "#27ae60")
                    self._ui_safe(lambda: self.status_label.config(text=f"Đã vào game: {serial}", bg="#27ae60"))
                else:
                    self._set_card_status(serial, "Không vào được game", "#e74c3c")
                    self._ui_safe(lambda: self.status_label.config(text=f"Không vào được game: {serial}", bg="#e74c3c"))
            except Exception as e:
                self._set_card_status(serial, "Lỗi vào game", "#e74c3c")
                self._log(f"[{serial}] Lỗi vào game: {e}", "error")

        threading.Thread(target=run, daemon=True).start()

    def _reset_runtime_flags_for_start(self, serial):
        try:
            from core.mo_ruong import reset_day_kho
            reset_day_kho(serial)
            self._log(f"[{serial}] Reset cờ đầy kho")
        except Exception as e:
            self._log(f"[{serial}] Không reset được cờ đầy kho: {e}", "warning")

    def _refresh_configs(self):
        files = glob_mod.glob(os.path.join(CONFIG_DIR, "*.json"))
        names = [os.path.splitext(os.path.basename(f))[0] for f in files]
        self.config_combo["values"] = names
        if names:
            self.config_combo.current(0)
            self._preview_config()

    def _preview_config(self):
        name = self.config_var.get()
        if not name:
            return
        path = os.path.join(CONFIG_DIR, f"{name}.json")
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)

            if isinstance(raw, dict) and "tasks" in raw:
                settings = raw.get("settings", {})
                tasks = raw.get("tasks", [])
                ban_do = raw.get("ban_do", {})
            elif isinstance(raw, list):
                settings = DEFAULT_SETTINGS
                tasks = raw
                ban_do = DEFAULT_BAN_DO
            else:
                tasks = []
                settings = DEFAULT_SETTINGS
                ban_do = DEFAULT_BAN_DO

            self.preview_text.config(state=tk.NORMAL)
            self.preview_text.delete("1.0", tk.END)

            # Settings summary
            lt_mode = settings.get("loop_tong_mode", "count")
            lt_val = "vinh vien" if lt_mode == "forever" else str(settings.get("loop_tong", 1))
            loop = settings.get("loop", 1)
            toggles_on = [k.replace("bat_", "") for k, v in settings.items() if k.startswith("bat_") and v]
            g_th = settings.get("threshold", 0.85)
            self.preview_text.insert(tk.END, f"[Settings] loop tong={lt_val}  loop TC+MAY={loop}  threshold={g_th}  bat: {', '.join(toggles_on)}\n")

            # Tasks
            for i, item in enumerate(tasks, 1):
                t = item.get("type", "?")
                row = item.get("row", "?")
                if t == "TC":
                    pi = os.path.basename(item.get("path_item", ""))
                    idxs = item.get("indexs", [])
                    th_txt = f"  th={item['threshold']}" if 'threshold' in item else ""
                    rg_txt = f"  vùng={format_region(item.get('region'))}" if item.get('region') else ""
                    self.preview_text.insert(tk.END,
                        f"#{i}  [{t}]  Hàng {row}  |  {pi}  |  {len(idxs)} vị trí{th_txt}{rg_txt}\n")
                elif t == "MAY":
                    data_items = item.get("data", [])
                    parts = [f"{os.path.basename(d['path_item'])} x{d.get('total',1)}" for d in data_items]
                    rg_txt = f"  vùng={format_region(item.get('region'))}" if item.get('region') else ""
                    self.preview_text.insert(tk.END,
                        f"#{i}  [{t}]  Hàng {row}  |  {', '.join(parts)}{rg_txt}\n")

            # Ban do summary
            if ban_do.get("data"):
                vp_displays = []
                for item in ban_do["data"]:
                    if isinstance(item, str):
                        vp_displays.append(os.path.basename(item))
                    elif isinstance(item, dict):
                        name = os.path.basename(item.get("path", ""))
                        extras = []
                        if "threshold" in item:
                            extras.append(f"t={item['threshold']}")
                        if "color_threshold" in item:
                            extras.append(f"c={item['color_threshold']}")
                        if "region" in item:
                            extras.append(f"r={format_region(item['region'])}")
                        vp_displays.append(name + (f"({','.join(extras)})" if extras else ""))
                bd_th = ban_do.get('threshold', 0.85)
                bd_ct = ban_do.get('color_threshold', 0.6)
                self.preview_text.insert(tk.END,
                    f"\n[Ban VP] kho={ban_do.get('loai_kho','')} x{ban_do.get('so_lan_dat_vp',0)}  "
                    f"KC={'có' if ban_do.get('xoa_kc') else 'không'}  "
                    f"QC={'có' if ban_do.get('dat_quang_cao') else 'không'}  "
                    f"threshold={bd_th}  color={bd_ct}\n"
                    f"  VP: {', '.join(vp_displays)}\n")

            self.preview_text.config(state=tk.DISABLED)
        except Exception as e:
            self.preview_text.config(state=tk.NORMAL)
            self.preview_text.delete("1.0", tk.END)
            self.preview_text.insert("1.0", f"Lỗi đọc file: {e}")
            self.preview_text.config(state=tk.DISABLED)

    def _log(self, msg, level="info"):
        """Ghi log — tu dong hien len tab Nhat Ky qua GUILogHandler."""
        log_func = getattr(logger, level, logger.info)
        log_func(msg)

    def _ui_safe(self, func):
        """Gọi func trên main thread (an toàn cho tkinter từ background thread)."""
        try:
            self.root.after(0, func)
        except (RuntimeError, tk.TclError):
            pass

    def _load_config(self):
        """Đọc config hiện tại, trả về (settings, tasks, ban_do) hoặc None."""
        config_name = self.config_var.get()
        if not config_name:
            messagebox.showwarning("Lỗi", "Vui lòng chọn cấu hình!")
            return None
        config_path = os.path.join(CONFIG_DIR, f"{config_name}.json")
        if not os.path.exists(config_path):
            messagebox.showerror("Lỗi", f"File không tồn tại: {config_path}")
            return None
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không đọc được: {e}")
            return None

        if isinstance(raw, dict) and "tasks" in raw:
            return raw.get("settings", DEFAULT_SETTINGS), raw.get("tasks", []), raw.get("ban_do", DEFAULT_BAN_DO)
        elif isinstance(raw, list):
            return DEFAULT_SETTINGS, raw, DEFAULT_BAN_DO
        messagebox.showerror("Lỗi", "Định dạng cấu hình không hợp lệ!")
        return None

    def _start_one(self, serial, cfg=None):
        """Chạy auto cho 1 nick."""
        cfg = cfg or self._load_config()
        if not cfg:
            return
        settings, tasks, ban_do = cfg

        card = self.device_cards.get(serial)
        if not card:
            return
        # Đang chạy rồi thì bỏ qua
        if not card.get("running", True):
            self._set_card_status(serial, "Chưa mở LD", "#7f8c8d")
            return
        if card["thread"] and card["thread"].is_alive():
            return

        config_name = self.config_var.get()
        self._reset_runtime_flags_for_start(serial)

        stop_ev = threading.Event()
        card["stop_event"] = stop_ev
        card["btn_start"].config(state=tk.DISABLED)
        card["btn_stop"].config(state=tk.NORMAL)
        self._set_card_status(serial, f"Đang chạy: {config_name}", "#f39c12")
        self._config_current_card(serial, "status_dot", fg="#27ae60")

        loop_tc_may = settings.get("loop", 1)
        loop_tong_mode = settings.get("loop_tong_mode", "count")
        loop_tong_count = settings.get("loop_tong", 1)
        dev_name = card["name"]
        dev_label = f"[{dev_name}]"

        self._log(f"{dev_label} Bắt đầu auto | Config: {config_name}")

        is_debug = self.debug_mode_var.get()

        def run():
            try:
                # Set debug mode trong thread
                if is_debug:
                    from utils.utils import set_debug_mode as utils_debug
                    from core.ban_do import set_debug_mode as ban_do_debug
                    utils_debug(True)
                    ban_do_debug(True)

                adb_inst = ADBController(serial=serial)

                # Setup thread với device_name → tất cả log tự động có [tên nick]
                from utils.utils import setup_thread
                setup_thread(adb_inst, stop_ev, device_name=dev_name)

                self._log(f"{dev_label} Kết nối thành công | Config: {config_name}")

                tc_tasks = [t for t in tasks if
                            (t.get("type") == "TC" and settings.get("bat_trong_cay")) or
                            (t.get("type") == "MAY" and settings.get("bat_may"))]
                if settings.get("bat_mo_ruong"):
                    from core.mo_ruong import can_mo_ruong, da_day_kho, mo_ruong
                if settings.get("bat_giao_cu"):
                    from core.giao_cu import can_giao_cu, giao_cu
                if settings.get("bat_giao_tom"):
                    from core.giao_tom import giao_tom
                if settings.get("bat_sxcam"):
                    from core.sxcam import can_sxcam, run_sxcam

                tong_i = 0
                last_ld_restart_time = time.time()
                while not stop_ev.is_set():
                    # Check restart LDPlayer
                    elapsed_hours = (time.time() - last_ld_restart_time) / 3600.0
                    if settings.get("bat_khoi_dong_lai_ld"):
                        self._log(f"{dev_label} [DEBUG RESTART] Đã chạy: {elapsed_hours*60:.2f} phút / Yêu cầu: {settings.get('thoi_gian_khoi_dong_lai', 5.0)*60:.2f} phút")
                    if settings.get("bat_khoi_dong_lai_ld") and elapsed_hours >= settings.get("thoi_gian_khoi_dong_lai", 5.0):
                        restart_hours = settings.get("thoi_gian_khoi_dong_lai", 5.0)
                        self._log(f"{dev_label} Đã chạy liên tục {restart_hours} giờ. Tiến hành restart LDPlayer...")
                        
                        ld_index = card.get("index")
                        if ld_index is not None:
                            restart_success = False
                            for attempt in range(3):
                                if stop_ev.is_set():
                                    break
                                self._log(f"{dev_label} Tiến hành khởi động lại LDPlayer (Lần thử {attempt+1}/3)...")
                                self._set_card_status(serial, f"Restart LD (Lần {attempt+1})...", "#e74c3c")
                                try:
                                    self.adb_helper.stop_ldplayer(index=ld_index)
                                except Exception as stop_err:
                                    self._log(f"{dev_label} Lỗi khi dừng LDPlayer: {stop_err}", "warning")
                                time.sleep(10)
                                
                                self._set_card_status(serial, "Đang mở LD...", "#f39c12")
                                try:
                                    self.adb_helper.start_ldplayer(index=ld_index)
                                except Exception as start_err:
                                    self._log(f"{dev_label} Lỗi khi khởi động LDPlayer: {start_err}", "error")
                                
                                self._log(f"{dev_label} Đang chờ LDPlayer khởi động và kết nối ADB...")
                                adb_ready = False
                                for _ in range(36): # 3 phút
                                    if stop_ev.is_set():
                                        break
                                    if serial in self.adb_helper.get_devices():
                                        adb_ready = True
                                        break
                                    time.sleep(5)
                                
                                if adb_ready and not stop_ev.is_set():
                                    self._log(f"{dev_label} LDPlayer đã sẵn sàng. Mở game...")
                                    self._set_card_status(serial, "Đang vào game...", "#f39c12")
                                    try:
                                        from core.vao_game import vao_game
                                        if vao_game(serial):
                                            self._log(f"{dev_label} Hoàn tất mở game sau khi restart LD. Đợi 10 giây để game ổn định...")
                                            time.sleep(10)
                                            last_ld_restart_time = time.time()
                                            restart_success = True
                                            break
                                        else:
                                            self._log(f"{dev_label} Vào game lỗi (Chưa thấy log_game.png). Thử lại...", "warning")
                                    except Exception as game_err:
                                        self._log(f"{dev_label} Lỗi mở game sau khi restart: {game_err}", "error")
                                else:
                                    self._log(f"{dev_label} Lỗi: Quá thời gian chờ LDPlayer kết nối ADB!", "error")
                            
                            if not restart_success and not stop_ev.is_set():
                                self._log(f"{dev_label} Đã thử khởi động lại 3 lần nhưng đều thất bại vào game!", "error")
                        else:
                            self._log(f"{dev_label} Không tìm thấy index của LDPlayer để restart!", "warning")

                    tong_i += 1
                    if loop_tong_mode != "forever" and tong_i > loop_tong_count:
                        break
                    lbl = f"{tong_i}{'/' + str(loop_tong_count) if loop_tong_mode != 'forever' else ''}"
                    self._log(f"{dev_label} [{config_name}] LẶP {lbl}")
                    self._set_card_status(serial, f"{config_name} | Lặp {lbl}", "#f39c12")

                    if settings.get("bat_mo_ruong"):
                        if da_day_kho(serial):
                            self._log(f"{dev_label} [{config_name}] Bỏ qua mở rương vì kho đã đầy")
                        elif can_mo_ruong(serial):
                            self._set_card_status(serial, f"{config_name} | Kiểm tra rương...", "#e67e22")
                            opened = mo_ruong(adb_inst, serial=serial, stop_event=stop_ev)
                            if opened:
                                self._log(f"{dev_label} [{config_name}] Đã mở rương")
                                self._set_card_status(serial, f"{config_name} | Đã mở rương", "#27ae60")

                    if settings.get("bat_giao_cu") and can_giao_cu(serial):
                        self._set_card_status(serial, f"{config_name} | Giao cú...", "#e67e22")
                        handled_gc = giao_cu(
                            adb_inst,
                            serial=serial,
                            dsvp_bo_qua=ban_do.get("dsvp_bo_qua", []),
                            stop_event=stop_ev
                        )
                        if handled_gc:
                            self._log(f"{dev_label} [{config_name}] Đã xử lý giao cú")
                            self._set_card_status(serial, f"{config_name} | Đã giao cú", "#27ae60")

                    if settings.get("bat_giao_tom") and ban_do.get("tom_vp"):
                        self._set_card_status(serial, f"{config_name} | Giao tôm...", "#e67e22")
                        handled_tom = giao_tom(
                            adb_inst,
                            vp_path=ban_do.get("tom_vp"),
                            kho=ban_do.get("tom_kho", "KTP"),
                            stop_event=stop_ev
                        )
                        if handled_tom:
                            self._log(f"{dev_label} [{config_name}] Đã xử lý giao tôm")
                            self._set_card_status(serial, f"{config_name} | Đã giao tôm", "#27ae60")

                    if settings.get("bat_sxcam") and can_sxcam(serial):
                        self._set_card_status(serial, f"{config_name} | SX Cám...", "#e67e22")
                        handled_sxcam = run_sxcam(adb_inst, serial=serial, stop_event=stop_ev)
                        if handled_sxcam:
                            self._log(f"{dev_label} [{config_name}] Đã xử lý sản xuất cám")
                            self._set_card_status(serial, f"{config_name} | Đã SX Cám", "#27ae60")

                    if tc_tasks:
                        start_time = time.time()
                        for loop_i in range(loop_tc_may):
                            # tính thời gian chạy mỗi vòng để ước lượng thời gian hoàn thành
                            start_time_item = time.time()
                            if stop_ev.is_set():
                                break
                            self._log(f"{dev_label} [{config_name}] TC+MAY {loop_i+1}/{loop_tc_may}")
                            main_tc(tc_tasks, adb_instance=adb_inst, stop_event=stop_ev,
                                    global_threshold=settings.get("threshold"), is_sua_may= (loop_i == loop_tc_may-1))
                            end_time_item = time.time()
                            elapsed = end_time_item - start_time_item
                            self._log(f"{dev_label} [{config_name}] TC+MAY {loop_i+1}/{loop_tc_may} hoàn thành trong {elapsed:.1f}s")
                        end_time = time.time()
                        elapsed = end_time - start_time
                        self._log(f"{dev_label} [{config_name}] TC+MAY x{loop_tc_may} hoàn thành trong {elapsed:.1f}s")
                        
                    if stop_ev.is_set():
                        break

                    if settings.get("bat_ban_vp") and ban_do.get("data"):
                        self._log(f"{dev_label} [{config_name}] Bán vật phẩm")
                        self._set_card_status(serial, f"{config_name} | Bán VP...", "#e67e22")
                        from core.ban_do import main_ban_hang
                        ban_do_cfg = {
                            "loai_kho": ban_do.get("loai_kho", "KTP"),
                            "so_lan_dat_vp": ban_do.get("so_lan_dat_vp", 4),
                            "data": ban_do.get("data", []),
                            "xoa_kc": ban_do.get("xoa_kc", False),
                            "dat_quang_cao": ban_do.get("dat_quang_cao", True),
                            "check_stock": ban_do.get("check_stock", False),
                            "debug": self.debug_mode_var.get(),
                            "threshold": ban_do.get("threshold") or settings.get("threshold"),
                            "color_threshold": ban_do.get("color_threshold", 0.6),
                            "region": ban_do.get("region"),
                            "qc_templates": ban_do.get("qc_templates", []),
                            "xoa_kc_templates": ban_do.get("xoa_kc_templates", [])
                        }
                        main_ban_hang(adb_inst, ban_do_cfg, stop_event=stop_ev)

                if not stop_ev.is_set():
                    self._log(f"{dev_label} [{config_name}] Hoàn thành!")
                    self._set_card_status(serial, f"{config_name} | Hoàn thành", "#27ae60")
                    self._ui_safe(lambda: self._config_current_card(serial, "status_dot", fg="#3498db"))
                else:
                    self._log(f"{dev_label} [{config_name}] Đã dừng.")
                    self._set_card_status(serial, f"{config_name} | Đã dừng", "#c0392b")
                    self._ui_safe(lambda: self._config_current_card(serial, "status_dot", fg="#c0392b"))
            except Exception as e:
                self._log(f"{dev_label} [{config_name}] Lỗi: {e}", "error")
                self._set_card_status(serial, f"{config_name} | Lỗi!", "#e74c3c")
                self._ui_safe(lambda: self._config_current_card(serial, "status_dot", fg="#e74c3c"))
            finally:
                self._ui_safe(lambda: self._config_current_card(serial, "btn_start", state=tk.NORMAL))
                self._ui_safe(lambda: self._config_current_card(serial, "btn_stop", state=tk.DISABLED))

        t = threading.Thread(target=run, daemon=True)
        card["thread"] = t
        t.start()

    def _stop_one(self, serial):
        """Dừng 1 nick."""
        card = self.device_cards.get(serial)
        if card and card["stop_event"]:
            card["stop_event"].set()
            self._log(f"[{card['name']}] Đang dừng...")
            card["btn_stop"].config(state=tk.DISABLED)

    def _start_all(self):
        """Chạy tất cả nick."""
        if getattr(self, "_start_all_queue_running", False):
            self.status_label.config(text="Đang chạy tất cả, vui lòng đợi...")
            return

        cfg = self._load_config()
        if not cfg:
            return

        targets = []
        skipped_not_running = 0
        for serial, card in list(self.device_cards.items()):
            if card["thread"] and card["thread"].is_alive():
                continue
            if not card.get("running", True):
                skipped_not_running += 1
                self._set_card_status(serial, "Chưa mở LD", "#7f8c8d")
                continue
            targets.append(serial)

        if not targets:
            self.status_label.config(text="Không có LDPlayer nào sẵn sàng để chạy")
            return

        self.status_label.config(text=f"Đang xếp lịch chạy {len(targets)} LDPlayer")
        self._start_all_queue_running = True

        def start_next(pos=0):
            if not getattr(self, "_start_all_queue_running", False):
                self.status_label.config(text="Đã hủy xếp lịch chạy tất cả")
                return
            if pos >= len(targets):
                self._start_all_queue_running = False
                if skipped_not_running:
                    self.status_label.config(text=f"Đã chạy {len(targets)} tác vụ | Bỏ qua {skipped_not_running} LD chưa mở")
                else:
                    self.status_label.config(text=f"Đã chạy {len(targets)} tác vụ")
                return
            self._start_one(targets[pos], cfg=cfg)
            self.root.after(700, lambda: start_next(pos + 1))

        self.root.after(0, start_next)

    def _scan_kho_thanh_pham_all(self):
        """Quét kho thành phẩm các LDPlayer đang mở rồi xuất CSV ma trận."""
        if getattr(self, "_scan_kho_tp_running", False):
            self.status_label.config(text="Đang quét kho thành phẩm, vui lòng đợi...")
            return

        targets = []
        for serial, card in list(self.device_cards.items()):
            if card.get("thread") and card["thread"].is_alive():
                continue
            if not card.get("running", True):
                continue
            targets.append((serial, card.get("name") or serial))

        if not targets:
            messagebox.showwarning("Quét kho TP", "Không có LDPlayer đang mở để quét.")
            return

        self._scan_kho_tp_running = True
        self.status_label.config(text=f"Đang quét kho thành phẩm {len(targets)} LDPlayer", bg="#8e44ad")

        def worker():
            results = {}
            output_path = None
            try:
                from core.adb import ADBController
                from core.kho_thanh_pham import scan_kho_thanh_pham, export_kho_thanh_pham_csv

                for serial, name in targets:
                    self._set_card_status(serial, "Quét kho thành phẩm...", "#8e44ad")
                    adb_inst = ADBController(serial=serial)
                    data = scan_kho_thanh_pham(adb_inst, device_name=name)
                    results[name] = data
                    self._set_card_status(serial, f"Đã quét kho TP: {len(data)} SP", "#27ae60")

                output_path = export_kho_thanh_pham_csv(results)
            except Exception as e:
                logger.exception("Lỗi quét kho thành phẩm")
                self._ui_safe(lambda: messagebox.showerror("Quét kho TP", f"Lỗi quét kho thành phẩm:\n{e}"))
            finally:
                self._scan_kho_tp_running = False
                if output_path:
                    self._ui_safe(lambda: self.status_label.config(
                        text=f"Đã quét xong kho thành phẩm: {output_path}", bg="#27ae60"
                    ))
                    self._ui_safe(lambda: messagebox.showinfo(
                        "Quét kho TP", f"Đã quét xong kho thành phẩm.\nCSV:\n{output_path}"
                    ))

        threading.Thread(target=worker, daemon=True).start()

    def _download_kho_thanh_pham_csv(self):
        """Copy file CSV kho thành phẩm của hôm nay ra vị trí người dùng chọn."""
        try:
            from core.kho_thanh_pham import get_today_kho_thanh_pham_csv_path

            src = get_today_kho_thanh_pham_csv_path()
            if not os.path.exists(src):
                os.makedirs(os.path.dirname(src), exist_ok=True)
                with open(src, "w", encoding="utf-8-sig", newline="") as f:
                    f.write("item\n")

            dst = filedialog.asksaveasfilename(
                title="Tải CSV kho thành phẩm",
                defaultextension=".csv",
                initialfile=os.path.basename(src),
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if not dst:
                return

            shutil.copyfile(src, dst)
            messagebox.showinfo("Tải CSV kho TP", f"Đã lưu CSV:\n{dst}")
        except Exception as e:
            messagebox.showerror("Tải CSV kho TP", f"Không tải được CSV:\n{e}")

    def _stop_all(self):
        """Dừng tất cả nick."""
        self._start_all_queue_running = False
        for serial in list(self.device_cards):
            self._stop_one(serial)

    def _toggle_debug_mode(self):
        enabled = self.debug_mode_var.get()
        from core.ban_do import set_debug_mode as ban_do_debug
        from utils.utils import set_debug_mode as utils_debug
        ban_do_debug(enabled)
        utils_debug(enabled)
        self._log(f"Gỡ lỗi: {'Bật' if enabled else 'Tắt'}")

    def _open_debug_folder(self):
        debug_dir = os.path.abspath("debug")
        os.makedirs(debug_dir, exist_ok=True)
        os.startfile(debug_dir)

    # ----------------------------------------------------------------
    # TAB 4: NHAT KY (LOG)
    # ----------------------------------------------------------------
    def _build_tab_log(self):
        pad = tk.Frame(self.tab_log, bg="#1e1e1e")
        pad.pack(fill=tk.BOTH, expand=True)

        # --- Toolbar ---
        toolbar = tk.Frame(pad, bg="#2d2d2d", padx=8, pady=6)
        toolbar.pack(fill=tk.X)

        # Filter level
        tk.Label(toolbar, text="Lọc:", bg="#2d2d2d", fg="#cccccc",
                 font=("Arial", 9)).pack(side=tk.LEFT)
        self.log_filter_var = tk.StringVar(value="TAT CA")
        for lvl, label in [("TAT CA", "TẤT CẢ"), ("INFO", "THÔNG TIN"), ("WARNING", "CẢNH BÁO"), ("ERROR", "LỖI")]:
            tk.Radiobutton(toolbar, text=label, variable=self.log_filter_var, value=lvl,
                           bg="#2d2d2d", fg="#cccccc", selectcolor="#3c3c3c",
                           activebackground="#3c3c3c", activeforeground="white",
                           font=("Arial", 8), command=self._filter_log
                           ).pack(side=tk.LEFT, padx=2)

        # Search
        tk.Label(toolbar, text="  Tìm:", bg="#2d2d2d", fg="#cccccc",
                 font=("Arial", 9)).pack(side=tk.LEFT, padx=(12, 4))
        self.log_search_var = tk.StringVar()
        search_entry = tk.Entry(toolbar, textvariable=self.log_search_var, width=25,
                                font=("Consolas", 9), bg="#3c3c3c", fg="white",
                                insertbackground="white", relief=tk.FLAT)
        search_entry.pack(side=tk.LEFT, padx=2)
        search_entry.bind("<KeyRelease>", lambda e: self._filter_log())

        # Auto-scroll toggle
        self.log_autoscroll_var = tk.BooleanVar(value=True)
        tk.Checkbutton(toolbar, text="Tự cuộn", variable=self.log_autoscroll_var,
                       bg="#2d2d2d", fg="#cccccc", selectcolor="#3c3c3c",
                       activebackground="#3c3c3c", activeforeground="white",
                       font=("Arial", 8)).pack(side=tk.LEFT, padx=(12, 4))

        # Buttons
        tk.Button(toolbar, text="Xóa nhật ký", command=self._clear_log,
                  bg="#c0392b", fg="white", relief=tk.FLAT, cursor="hand2",
                  font=("Arial", 8, "bold"), padx=8).pack(side=tk.RIGHT)
        tk.Button(toolbar, text="Mở tệp nhật ký", command=self._open_log_file,
                  bg="#2980b9", fg="white", relief=tk.FLAT, cursor="hand2",
                  font=("Arial", 8, "bold"), padx=8).pack(side=tk.RIGHT, padx=4)

        # --- Line count ---
        self.log_count_label = tk.Label(pad, text="0 dòng", bg="#2d2d2d", fg="#888888",
                                         font=("Consolas", 8), anchor=tk.E, padx=8)
        self.log_count_label.pack(fill=tk.X)

        # --- Main log text ---
        log_container = tk.Frame(pad, bg="#1e1e1e")
        log_container.pack(fill=tk.BOTH, expand=True)

        log_scroll = tk.Scrollbar(log_container)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_text = tk.Text(log_container, font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4",
                                yscrollcommand=log_scroll.set, wrap=tk.WORD,
                                state=tk.DISABLED, padx=8, pady=4,
                                selectbackground="#264f78", selectforeground="white")
        self.log_text.pack(fill=tk.BOTH, expand=True)
        log_scroll.config(command=self.log_text.yview)

        # Tag colors cho cac level
        self.log_text.tag_config("INFO", foreground="#d4d4d4")
        self.log_text.tag_config("WARNING", foreground="#e5c07b")
        self.log_text.tag_config("ERROR", foreground="#e06c75")
        self.log_text.tag_config("CRITICAL", foreground="#ff0000", underline=True)
        self.log_text.tag_config("timestamp", foreground="#6a9955")
        self.log_text.tag_config("nick", foreground="#569cd6")
        self.log_text.tag_config("config_name", foreground="#c586c0")
        self.log_text.tag_config("search_highlight", background="#613214")

        # Luu tat ca log lines de filter
        self._all_log_lines = []
        self._max_gui_log_lines = GUI_LOG_MAX_LINES

        # Cai dat GUI logging handler
        self._setup_gui_log_handler()

    def _setup_gui_log_handler(self):
        """Tao logging.Handler de bat tat ca log tu moi module hien len GUI."""

        gui_ref = self  # prevent GC

        class GUILogHandler(logging.Handler):
            def emit(self, record):
                try:
                    # Đảm bảo có device field
                    if not hasattr(record, 'device'):
                        from utils.utils import get_device_name
                        name = get_device_name()
                        record.device = f"[{name}]" if name else "[main]"
                    msg = self.format(record)
                    level = record.levelname
                    gui_ref._append_log_line(msg, level)
                except Exception:
                    pass

        handler = GUILogHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(device)s %(name)s: %(message)s",
            datefmt="%H:%M:%S"))
        # Them vao root logger de bat moi module
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)

    def _append_log_line(self, line, level="INFO"):
        """Them 1 dong log — thread-safe, co mau theo level."""
        self._all_log_lines.append((line, level))
        if len(self._all_log_lines) > self._max_gui_log_lines:
            del self._all_log_lines[:len(self._all_log_lines) - self._max_gui_log_lines]

        # Check filter
        if not self._should_show_line(line, level):
            return

        def _write():
            try:
                self.log_text.config(state=tk.NORMAL)
                self.log_text.insert(tk.END, line + "\n", level)
                self._trim_log_text_widget()
                if self.log_autoscroll_var.get():
                    self.log_text.see(tk.END)
                self.log_text.config(state=tk.DISABLED)
                self.log_count_label.config(text=f"{len(self._all_log_lines)} dòng")

                # Cap nhat mini log (tab Auto)
                self._update_mini_log(line)
            except tk.TclError:
                pass

        try:
            self.root.after(0, _write)
        except RuntimeError:
            pass

    def _trim_log_text_widget(self):
        """Giu Text widget khong vuot qua gioi han dong hien thi."""
        line_count = int(self.log_text.index("end-1c").split(".")[0])
        if line_count > self._max_gui_log_lines:
            self.log_text.delete("1.0", f"{line_count - self._max_gui_log_lines + 1}.0")

    def _update_mini_log(self, line):
        """Cap nhat mini log o tab Auto — chi hien 4 dong gan nhat."""
        try:
            self.mini_log_text.config(state=tk.NORMAL)
            self.mini_log_text.insert(tk.END, line + "\n")
            # Giu toi da 30 dong, xoa cu
            line_count = int(self.mini_log_text.index("end-1c").split(".")[0])
            if line_count > 30:
                self.mini_log_text.delete("1.0", f"{line_count - 30}.0")
            self.mini_log_text.see(tk.END)
            self.mini_log_text.config(state=tk.DISABLED)
        except tk.TclError:
            pass

    def _should_show_line(self, line, level):
        """Kiem tra dong log co match filter hien tai khong."""
        # Filter level
        fltr = self.log_filter_var.get()
        if fltr != "TAT CA":
            if fltr == "ERROR" and level not in ("ERROR", "CRITICAL"):
                return False
            if fltr == "WARNING" and level not in ("WARNING", "ERROR", "CRITICAL"):
                return False
            if fltr == "INFO" and level not in ("INFO", "WARNING", "ERROR", "CRITICAL"):
                return False

        # Filter search
        search = self.log_search_var.get().strip().lower()
        if search and search not in line.lower():
            return False

        return True

    def _filter_log(self):
        """Ap dung lai filter — ve lai toan bo log text."""
        def _rewrite():
            try:
                self.log_text.config(state=tk.NORMAL)
                self.log_text.delete("1.0", tk.END)
                count = 0
                for line, level in self._all_log_lines:
                    if self._should_show_line(line, level):
                        self.log_text.insert(tk.END, line + "\n", level)
                        count += 1
                # Highlight search
                search = self.log_search_var.get().strip()
                if search:
                    self._highlight_search(search)
                if self.log_autoscroll_var.get():
                    self.log_text.see(tk.END)
                self.log_text.config(state=tk.DISABLED)
                self.log_count_label.config(text=f"{count}/{len(self._all_log_lines)} dòng")
            except tk.TclError:
                pass

        try:
            self.root.after(0, _rewrite)
        except RuntimeError:
            pass

    def _highlight_search(self, search_text):
        """To mau cac tu khoa tim kiem trong log."""
        self.log_text.tag_remove("search_highlight", "1.0", tk.END)
        if not search_text:
            return
        start = "1.0"
        while True:
            pos = self.log_text.search(search_text, start, stopindex=tk.END, nocase=True)
            if not pos:
                break
            end = f"{pos}+{len(search_text)}c"
            self.log_text.tag_add("search_highlight", pos, end)
            start = end

    def _clear_log(self):
        """Xóa tat ca log."""
        self._all_log_lines.clear()
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.log_count_label.config(text="0 dòng")
        # Xóa mini log
        self.mini_log_text.config(state=tk.NORMAL)
        self.mini_log_text.delete("1.0", tk.END)
        self.mini_log_text.config(state=tk.DISABLED)

    def _open_log_file(self):
        """Mo file log bang notepad."""
        log_path = os.path.abspath("logs/auto_config.log")
        if os.path.exists(log_path):
            os.startfile(log_path)
        else:
            messagebox.showinfo("Thông báo", "Chưa có tệp nhật ký!")

    # ----------------------------------------------------------------
    # TAB 3: SCREENSHOT & CROP
    # ----------------------------------------------------------------
    def _build_tab_screenshot(self):
        pad = tk.Frame(self.tab_screenshot, bg="#ecf0f1")
        pad.pack(fill=tk.BOTH, expand=True)

        # Toolbar
        toolbar = tk.Frame(pad, bg="#34495e", height=45)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)

        tk.Label(toolbar, text="Thiết bị:", font=("Arial", 9),
                 bg="#34495e", fg="white").pack(side=tk.LEFT, padx=(10, 2))
        self.ss_device_var = tk.StringVar()
        self.ss_device_combo = ttk.Combobox(toolbar, textvariable=self.ss_device_var,
                                             state="readonly", width=28, font=("Arial", 9))
        self.ss_device_combo.pack(side=tk.LEFT, padx=4, pady=8)
        tk.Button(toolbar, text="Làm mới", command=self._ss_refresh_devices,
                  bg="#1abc9c", fg="white", relief=tk.FLAT, padx=6,
                  font=("Arial", 8), cursor="hand2").pack(side=tk.LEFT, padx=2, pady=8)

        tk.Button(toolbar, text="Chụp (F2)", command=self._ss_take,
                  bg="#3498db", fg="white", relief=tk.FLAT, padx=12,
                  font=("Arial", 9, "bold"), cursor="hand2").pack(side=tk.RIGHT, padx=4, pady=6)
        tk.Button(toolbar, text="Lưu ảnh gốc", command=self._ss_save_original,
                  bg="#27ae60", fg="white", relief=tk.FLAT, padx=10,
                  font=("Arial", 9), cursor="hand2").pack(side=tk.RIGHT, padx=4, pady=6)
        tk.Button(toolbar, text="Lưu vùng cắt", command=self._ss_save_cropped,
                  bg="#e67e22", fg="white", relief=tk.FLAT, padx=10,
                  font=("Arial", 9), cursor="hand2").pack(side=tk.RIGHT, padx=4, pady=6)
        tk.Button(toolbar, text="Đặt lại vùng cắt", command=self._ss_reset_crop,
                  bg="#95a5a6", fg="white", relief=tk.FLAT, padx=10,
                  font=("Arial", 9), cursor="hand2").pack(side=tk.RIGHT, padx=4, pady=6)

        self.root.bind('<F2>', lambda _: self._ss_take())

        # Content: canvas left + controls right
        content = tk.Frame(pad, bg="#ecf0f1")
        content.pack(fill=tk.BOTH, expand=True)

        # Canvas
        left = tk.Frame(content, bg="#2c3e50")
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(left, text="Nhấn và kéo để chọn vùng ảnh", bg="#2c3e50", fg="white",
                 font=("Arial", 9), pady=4).pack()

        canvas_frame = tk.Frame(left)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        h_scroll = tk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        v_scroll = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.ss_canvas = tk.Canvas(canvas_frame, bg="#34495e", cursor="crosshair",
                                    xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        self.ss_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        h_scroll.config(command=self.ss_canvas.xview)
        v_scroll.config(command=self.ss_canvas.yview)

        self.ss_canvas.bind("<ButtonPress-1>", self._ss_mouse_down)
        self.ss_canvas.bind("<B1-Motion>", self._ss_mouse_drag)
        self.ss_canvas.bind("<ButtonRelease-1>", self._ss_mouse_up)

        # Right panel
        right = tk.Frame(content, bg="#ecf0f1", width=260)
        right.pack(side=tk.RIGHT, fill=tk.Y)
        right.pack_propagate(False)

        # Info
        info_frame = tk.LabelFrame(right, text="Thông tin", font=("Arial", 10, "bold"),
                                   bg="#ecf0f1", padx=8, pady=8)
        info_frame.pack(fill=tk.X, padx=8, pady=8)
        self.ss_info = tk.Text(info_frame, font=("Consolas", 9), height=6, bg="white", wrap=tk.WORD)
        self.ss_info.pack(fill=tk.X)
        self._ss_set_info("Chưa có ảnh. Ấn Chụp (F2).")

        # Crop coords
        crop_frame = tk.LabelFrame(right, text="Tọa độ vùng cắt", font=("Arial", 10, "bold"),
                                   bg="#ecf0f1", padx=8, pady=8)
        crop_frame.pack(fill=tk.X, padx=8, pady=4)

        for i, lbl in enumerate(["X:", "Y:", "W:", "H:"]):
            tk.Label(crop_frame, text=lbl, bg="#ecf0f1").grid(row=i // 2, column=(i % 2) * 2, sticky=tk.W)
        self.ss_crop_x = tk.Entry(crop_frame, width=8); self.ss_crop_x.grid(row=0, column=1, padx=4)
        self.ss_crop_y = tk.Entry(crop_frame, width=8); self.ss_crop_y.grid(row=0, column=3, padx=4)
        self.ss_crop_w = tk.Entry(crop_frame, width=8); self.ss_crop_w.grid(row=1, column=1, padx=4, pady=4)
        self.ss_crop_h = tk.Entry(crop_frame, width=8); self.ss_crop_h.grid(row=1, column=3, padx=4, pady=4)

        tk.Button(crop_frame, text="Áp dụng tọa độ", command=self._ss_apply_manual_crop,
                  bg="#3498db", fg="white", relief=tk.FLAT, cursor="hand2"
                  ).grid(row=2, column=0, columnspan=4, pady=4, sticky=tk.EW)

        # Quick save
        save_frame = tk.LabelFrame(right, text="Lưu nhanh", font=("Arial", 10, "bold"),
                                   bg="#ecf0f1", padx=8, pady=8)
        save_frame.pack(fill=tk.X, padx=8, pady=4)

        tk.Label(save_frame, text="Tên file:", bg="#ecf0f1").pack(anchor=tk.W)
        self.ss_filename = tk.Entry(save_frame, font=("Arial", 9))
        self.ss_filename.pack(fill=tk.X, pady=4)
        self.ss_filename.insert(0, "template")

        tk.Label(save_frame, text="Thư mục:", bg="#ecf0f1").pack(anchor=tk.W)
        folder_row = tk.Frame(save_frame, bg="#ecf0f1")
        folder_row.pack(fill=tk.X, pady=4)
        self.ss_folder = tk.Entry(folder_row, font=("Arial", 9))
        self.ss_folder.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.ss_folder.insert(0, "assets/items")
        tk.Button(folder_row, text="...", width=3,
                  command=lambda: self._ss_browse_folder()).pack(side=tk.RIGHT, padx=(4, 0))

        tk.Button(save_frame, text="Lưu ảnh gốc", command=self._ss_quick_save_original,
                  bg="#27ae60", fg="white", relief=tk.FLAT, cursor="hand2").pack(fill=tk.X, pady=2)
        tk.Button(save_frame, text="Lưu ảnh đã cắt", command=self._ss_quick_save_cropped,
                  bg="#e67e22", fg="white", relief=tk.FLAT, cursor="hand2").pack(fill=tk.X, pady=2)

        # Crop preview
        preview_frame = tk.LabelFrame(right, text="Xem trước vùng cắt", font=("Arial", 10, "bold"),
                                      bg="#ecf0f1", padx=8, pady=8)
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        self.ss_preview_label = tk.Label(preview_frame, bg="white", relief=tk.SUNKEN, bd=1)
        self.ss_preview_label.pack(fill=tk.BOTH, expand=True)

        # State
        self.ss_screenshot = None
        self.ss_photo = None
        self.ss_crop_start = None
        self.ss_crop_end = None
        self.ss_crop_rect = None
        self.ss_preview_photo = None
        self.ss_devices_list = []
        self.ss_adb = None

    # --- Screenshot tab logic ---
    def _ss_refresh_devices(self):
        try:
            if not getattr(self.adb_helper, "adb_path", None):
                raise FileNotFoundError("Không tìm thấy ADB")
            serials = self.adb_helper.get_devices()
            self.ss_devices_list = []
            names = []
            for s in serials:
                name = self.adb_helper.get_device_name(s)
                self.ss_devices_list.append({"serial": s, "name": name})
                names.append(f"{name} ({s})")
            self.ss_device_combo["values"] = names
            if names:
                self.ss_device_combo.current(0)
            self.ss_adb = None
        except Exception as e:
            self.ss_device_combo["values"] = []
            self.ss_devices_list = []
            if isinstance(e, (FileNotFoundError, OSError)):
                if messagebox.askyesno(
                    "Lỗi ADB",
                    "Không tìm thấy ADB!\n\nBạn có muốn chọn thư mục LDPlayer thủ công không?"
                ):
                    if self._choose_adb_path():
                        self._ss_refresh_devices()

    def _ss_set_info(self, text):
        self.ss_info.delete("1.0", tk.END)
        self.ss_info.insert("1.0", text)

    def _ss_get_adb(self):
        """Lay ADB tu dropdown cua tab Screenshot."""
        idx = self.ss_device_combo.current()
        if idx >= 0 and idx < len(self.ss_devices_list):
            dev = self.ss_devices_list[idx]
            if self.ss_adb is None or self.ss_adb.serial != dev["serial"]:
                self.ss_adb = ADBController(serial=dev["serial"])
            return self.ss_adb
        messagebox.showwarning("Lỗi", "Chọn thiết bị trước!")
        return None

    def _ss_take(self):
        adb = self._ss_get_adb()
        if not adb:
            return
        try:
            self.status_label.config(text="Đang chụp...", bg="#f39c12")
            self.root.update()
            os.makedirs("cache", exist_ok=True)
            img = adb.screenshot_full("cache/screenshot_tool.png")
            if img is None:
                raise Exception("Không nhận được ảnh")
            self.ss_screenshot = img
            self._ss_display(img)
            h, w = img.shape[:2]
            self._ss_set_info(f"Chụp thành công!\ních thước: {w}x{h}")
            self.status_label.config(text="Đã chụp màn hình", bg="#27ae60")
        except Exception as e:
            self._ss_set_info(f"Lỗi: {e}")
            messagebox.showerror("Lỗi", f"Không chụp được:\n{e}")
            self.status_label.config(text="Lỗi chụp", bg="#e74c3c")

    def _ss_display(self, img_bgr):
        from PIL import Image, ImageTk
        rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        self.ss_photo = ImageTk.PhotoImage(pil)
        self.ss_canvas.delete("all")
        self.ss_canvas.config(scrollregion=(0, 0, pil.width, pil.height))
        self.ss_canvas.create_image(0, 0, anchor=tk.NW, image=self.ss_photo)
        self._ss_reset_crop()

    def _ss_mouse_down(self, event):
        if self.ss_screenshot is not None:
            self.ss_crop_start = (self.ss_canvas.canvasx(event.x), self.ss_canvas.canvasy(event.y))

    def _ss_mouse_drag(self, event):
        if self.ss_crop_start:
            if self.ss_crop_rect:
                self.ss_canvas.delete(self.ss_crop_rect)
            x1, y1 = self.ss_crop_start
            x2 = self.ss_canvas.canvasx(event.x)
            y2 = self.ss_canvas.canvasy(event.y)
            self.ss_crop_rect = self.ss_canvas.create_rectangle(
                x1, y1, x2, y2, outline="red", width=2, dash=(5, 5))
            w, h = abs(x2 - x1), abs(y2 - y1)
            self._ss_set_info(f"Vùng cắt: ({int(min(x1,x2))},{int(min(y1,y2))}) {int(w)}x{int(h)}")

    def _ss_mouse_up(self, event):
        if self.ss_crop_start:
            x2 = self.ss_canvas.canvasx(event.x)
            y2 = self.ss_canvas.canvasy(event.y)
            self.ss_crop_end = (x2, y2)
            x1, y1 = self.ss_crop_start
            x, y = int(min(x1, x2)), int(min(y1, y2))
            w, h = int(abs(x2 - x1)), int(abs(y2 - y1))
            for entry, val in [(self.ss_crop_x, x), (self.ss_crop_y, y),
                               (self.ss_crop_w, w), (self.ss_crop_h, h)]:
                entry.delete(0, tk.END)
                entry.insert(0, str(val))
            self._ss_set_info(f"Vùng cắt: X={x} Y={y}\nW={w} H={h}")
            self._ss_update_preview()

    def _ss_reset_crop(self):
        self.ss_crop_start = None
        self.ss_crop_end = None
        if self.ss_crop_rect:
            self.ss_canvas.delete(self.ss_crop_rect)
            self.ss_crop_rect = None
        for entry in [self.ss_crop_x, self.ss_crop_y, self.ss_crop_w, self.ss_crop_h]:
            entry.delete(0, tk.END)
        self.ss_preview_photo = None
        self.ss_preview_label.config(image="")

    def _ss_apply_manual_crop(self):
        try:
            x = int(self.ss_crop_x.get())
            y = int(self.ss_crop_y.get())
            w = int(self.ss_crop_w.get())
            h = int(self.ss_crop_h.get())
        except ValueError:
            messagebox.showerror("Lỗi", "Nhập số hợp lệ!")
            return
        if self.ss_crop_rect:
            self.ss_canvas.delete(self.ss_crop_rect)
        self.ss_crop_rect = self.ss_canvas.create_rectangle(
            x, y, x + w, y + h, outline="red", width=2, dash=(5, 5))
        self.ss_crop_start = (x, y)
        self.ss_crop_end = (x + w, y + h)
        self._ss_update_preview()

    def _ss_get_cropped(self):
        if self.ss_screenshot is None or not self.ss_crop_start or not self.ss_crop_end:
            return None
        x1, y1 = self.ss_crop_start
        x2, y2 = self.ss_crop_end
        x, y = int(min(x1, x2)), int(min(y1, y2))
        w, h = int(abs(x2 - x1)), int(abs(y2 - y1))
        if w < 1 or h < 1:
            return None
        return self.ss_screenshot[y:y+h, x:x+w]

    def _ss_update_preview(self):
        cropped = self._ss_get_cropped()
        if cropped is None or cropped.size == 0:
            return
        from PIL import Image, ImageTk
        rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        max_sz = 200
        pil.thumbnail((max_sz, max_sz), Image.LANCZOS)
        self.ss_preview_photo = ImageTk.PhotoImage(pil)
        self.ss_preview_label.config(image=self.ss_preview_photo)

    def _ss_browse_folder(self):
        from tkinter import filedialog
        folder = filedialog.askdirectory()
        if folder:
            self.ss_folder.delete(0, tk.END)
            self.ss_folder.insert(0, folder)

    def _ss_save_original(self):
        if self.ss_screenshot is None:
            messagebox.showwarning("Chưa có ảnh", "Chụp màn hình trước!")
            return
        from tkinter import filedialog
        from datetime import datetime
        path = filedialog.asksaveasfilename(
            defaultextension=".png", filetypes=[("PNG", "*.png")],
            initialfile=f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        if path:
            cv2.imwrite(path, self.ss_screenshot)
            self._refresh_template_combos()
            messagebox.showinfo("Xong", f"Đã lưu:\n{path}")

    def _ss_save_cropped(self):
        cropped = self._ss_get_cropped()
        if cropped is None:
            messagebox.showwarning("Chưa chọn vùng cắt", "Chọn vùng cắt trước!")
            return
        from tkinter import filedialog
        from datetime import datetime
        path = filedialog.asksaveasfilename(
            defaultextension=".png", filetypes=[("PNG", "*.png")],
            initialfile=f"cropped_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        if path:
            cv2.imwrite(path, cropped)
            self._refresh_template_combos()
            messagebox.showinfo("Xong", f"Đã lưu ảnh cắt:\n{path}")

    def _ss_quick_save_original(self):
        if self.ss_screenshot is None:
            messagebox.showwarning("Chưa có ảnh", "Chụp màn hình trước!")
            return
        folder = self.ss_folder.get()
        name = self.ss_filename.get().strip()
        if not name:
            messagebox.showwarning("Lỗi", "Nhập tên file!")
            return
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"{name}.png")
        cv2.imwrite(path, self.ss_screenshot)
        self._refresh_template_combos()
        messagebox.showinfo("Xong", f"Đã lưu:\n{path}")
        self.status_label.config(text=f"Đã lưu: {name}.png", bg="#27ae60")

    def _ss_quick_save_cropped(self):
        cropped = self._ss_get_cropped()
        if cropped is None:
            messagebox.showwarning("Chưa chọn vùng cắt", "Chọn vùng cắt trước!")
            return
        folder = self.ss_folder.get()
        name = self.ss_filename.get().strip()
        if not name:
            messagebox.showwarning("Lỗi", "Nhập tên file!")
            return
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"{name}.png")
        cv2.imwrite(path, cropped)
        self._refresh_template_combos()
        messagebox.showinfo("Xong", f"Đã lưu ảnh cắt:\n{path}")
        self.status_label.config(text=f"Đã lưu ảnh cắt: {name}.png", bg="#27ae60")

    # ================================================================
    # TAB CONFIG: LOGIC
    # ================================================================
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
        names = [os.path.splitext(os.path.basename(f))[0] for f in files]
        self.cfg_load_combo["values"] = names
        if names:
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

    # ================================================================
    # RUN
    # ================================================================
    def run(self):
        self.root.mainloop()

    # ================================================================
    # AUTO UPDATE
    # ================================================================
    def check_update_action(self, silent=False):
        """Khởi chạy luồng kiểm tra cập nhật để tránh đơ giao diện chính."""
        threading.Thread(
            target=self._check_for_updates_thread,
            args=(silent,),
            daemon=True
        ).start()

    def _check_for_updates_thread(self, silent):
        try:
            # Gửi request lên GitHub Releases API với User-Agent để tránh bị 403
            req = urllib.request.Request(
                GITHUB_API_URL,
                headers={"User-Agent": "AutoKVTM-Updater"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))

            latest_tag = data.get("tag_name", "").strip()
            # Bỏ ký tự 'v' ở đầu phiên bản nếu có (ví dụ 'v1.0.1' -> '1.0.1')
            latest_version = latest_tag[1:] if latest_tag.lower().startswith('v') else latest_tag
            changelog = data.get("body", "Không có thông tin thay đổi.")
            html_url = data.get("html_url", "https://github.com/nguyenducthong/autokvtm/releases")

            # Tìm file .exe trong danh sách assets
            download_url = None
            for asset in data.get("assets", []):
                if asset.get("name", "").endswith(".exe"):
                    download_url = asset.get("browser_download_url")
                    break

            # So sánh phiên bản (phân tích thành list of int để so sánh chính xác)
            def parse_version(v):
                try:
                    return [int(x) for x in v.split(".")]
                except ValueError:
                    return [0]

            if parse_version(latest_version) > parse_version(CURRENT_VERSION):
                # Có phiên bản mới! Gọi hàm hiển thị thông báo trên luồng UI chính
                if silent:
                    # Chạy ngầm: tự động tải xuống luôn
                    if download_url:
                        self._download_update(download_url, latest_version, changelog, silent=True)
                else:
                    self.root.after(
                        0,
                        lambda: self._prompt_update(latest_version, download_url, html_url, changelog)
                    )
            else:
                if not silent:
                    self.root.after(
                        0,
                        lambda: messagebox.showinfo(
                            "Kiểm tra cập nhật",
                            f"Bạn đang sử dụng phiên bản mới nhất ({CURRENT_VERSION})."
                        )
                    )
        except Exception as e:
            logger.error(f"Lỗi kiểm tra cập nhật: {e}")
            if not silent:
                error_msg = f"Không thể kết nối đến máy chủ GitHub để kiểm tra cập nhật:\n{e}"
                if hasattr(e, "code") and e.code == 404:
                    error_msg = "Chưa có bản phát hành (Release) nào được tạo trên GitHub cho dự án này.\n\n" \
                                "Vui lòng tạo một Release trên GitHub (ví dụ: v1.0.1) và đính kèm file gui_auto_config.exe."
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Lỗi kiểm tra cập nhật",
                        error_msg
                    )
                )

    def _prompt_update(self, latest_version, download_url, html_url, changelog):
        msg = f"Đã có phiên bản mới: {latest_version}\n" \
              f"(Phiên bản hiện tại: {CURRENT_VERSION})\n\n" \
              f"Nội dung cập nhật:\n{changelog}\n\n" \
              f"Bạn có muốn cập nhật ngay bây giờ không?"
              
        if messagebox.askyesno("Tìm thấy bản cập nhật mới", msg):
            if not getattr(sys, 'frozen', False):
                # Đang chạy từ mã nguồn .py -> Mở trình duyệt web tới trang release
                messagebox.showinfo(
                    "Thông báo",
                    "Bạn đang chạy ứng dụng từ mã nguồn (source code).\n"
                    "Hệ thống sẽ mở trình duyệt để bạn tải file hoặc git pull bản mới nhất.",
                    parent=self.root
                )
                webbrowser.open(html_url)
            else:
                # Đang chạy file đóng gói .exe -> Tải và tự động cài đặt cập nhật
                if download_url:
                    self._download_update(download_url)
                else:
                    messagebox.showwarning(
                        "Cảnh báo",
                        "Không tìm thấy file thực thi (.exe) trong bản phát hành mới trên GitHub.\n"
                        "Hệ thống sẽ mở trình duyệt để bạn tải về thủ công.",
                        parent=self.root
                    )
                    webbrowser.open(html_url)

    def _download_update(self, download_url, latest_version=None, changelog=None, silent=False):
        # Tạo cửa sổ con hiển thị tiến trình tải
        progress_win = tk.Toplevel(self.root)
        if silent:
            progress_win.title("Cập nhật chạy ngầm...")
        else:
            progress_win.title("Đang tải bản cập nhật...")
        progress_win.geometry("400x140")
        progress_win.resizable(False, False)
        
        # Chỉ chặn tương tác với cửa sổ chính khi người dùng nhấn nút cập nhật thủ công
        if not silent:
            progress_win.grab_set()
            
        # Căn giữa cửa sổ con theo cửa sổ chính
        x = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 140) // 2
        progress_win.geometry(f"+{x}+{y}")

        if silent:
            lbl = tk.Label(progress_win, text="Đang tải bản cập nhật mới trong nền...\n(Bạn vẫn có thể tương tác với ứng dụng chính bình thường)", font=("Arial", 10), justify=tk.CENTER)
        else:
            lbl = tk.Label(progress_win, text="Đang tải về bản cập nhật, vui lòng đợi...", font=("Arial", 10))
        lbl.pack(pady=15)
        
        progress = ttk.Progressbar(progress_win, orient=tk.HORIZONTAL, length=320, mode='determinate')
        progress.pack(pady=5)
        
        def _download_thread():
            try:
                is_frozen = getattr(sys, 'frozen', False)
                current_exe = sys.executable if is_frozen else os.path.abspath(sys.argv[0])
                dir_name = os.path.dirname(current_exe)
                filename = os.path.basename(current_exe)
                
                if is_frozen:
                    base, ext = os.path.splitext(filename)
                    new_exe_name = f"{base}_new{ext}"
                else:
                    new_exe_name = "gui_auto_config_new.exe"
                
                new_exe_path = os.path.join(dir_name, new_exe_name)
                
                req = urllib.request.Request(
                    download_url,
                    headers={"User-Agent": "AutoKVTM-Updater"}
                )
                with urllib.request.urlopen(req) as response, open(new_exe_path, 'wb') as out_file:
                    total_size = int(response.headers.get('content-length', 0))
                    block_size = 16384
                    read_size = 0
                    while True:
                        data = response.read(block_size)
                        if not data:
                            break
                        out_file.write(data)
                        read_size += len(data)
                        if total_size > 0 and progress_win and progress:
                            percent = (read_size / total_size) * 100
                            progress_win.after(0, lambda p=percent: progress.config(value=p))
                
                # Tắt cửa sổ tiến trình tải
                progress_win.after(0, progress_win.destroy)
                
                if not is_frozen:
                    # Nếu chạy từ source code, báo hoàn tất tải về thử nghiệm
                    def prompt_source_complete():
                        messagebox.showinfo(
                            "Đã tải xong cập nhật",
                            f"Đã tải bản cập nhật mới (phiên bản {latest_version}) trong nền thành công!\n\n"
                            f"Đường dẫn file: {new_exe_name}\n"
                            f"(Do chạy từ mã nguồn .py nên ứng dụng không tự khởi động lại)",
                            parent=self.root
                        )
                    self.root.after(0, prompt_source_complete)
                    return
                
                if silent:
                    def prompt_apply():
                        msg = f"Đã tự động tải xong bản cập nhật mới (phiên bản {latest_version}) trong nền.\n\n" \
                              f"Nội dung thay đổi:\n{changelog}\n\n" \
                              f"Bạn có muốn khởi động lại phần mềm để áp dụng cập nhật ngay bây giờ không?"
                        if messagebox.askyesno("Đã tải xong bản cập nhật", msg, parent=self.root):
                            self._apply_update_windows(current_exe, new_exe_path)
                    self.root.after(0, prompt_apply)
                else:
                    # Thực hiện cập nhật thay thế exe trên Windows
                    self.root.after(100, lambda: self._apply_update_windows(current_exe, new_exe_path))
                
            except Exception as e:
                logger.error(f"Lỗi tải file cập nhật: {e}")
                progress_win.after(0, progress_win.destroy)
                if not silent:
                    self.root.after(0, lambda: messagebox.showerror(
                        "Lỗi tải xuống",
                        f"Có lỗi xảy ra khi đang tải cập nhật:\n{e}"
                    ))

    def _apply_update_windows(self, current_exe, new_exe_path):
        try:
            dir_name = os.path.dirname(current_exe)
            current_exe_name = os.path.basename(current_exe)
            new_exe_name = os.path.basename(new_exe_path)
            bat_path = os.path.join(dir_name, "updater.bat")
            
            # Script batch để đợi ứng dụng chính đóng hẳn, xoá exe cũ, đổi tên file mới và chạy lại
            bat_content = f"""@echo off
set _MEIPASS=
taskkill /f /im "{current_exe_name}" >nul 2>&1
timeout /t 2 /nobreak >nul
del /f /q "{current_exe}"
ren "{new_exe_name}" "{current_exe_name}"
start "" "{current_exe}"
del "%~f0"
"""
            # Ghi file script bat
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write(bat_content)
                
            # Khởi chạy file bat ngầm
            subprocess.Popen([bat_path], shell=True, cwd=dir_name)
            
            # Đóng ngay ứng dụng chính để script bat hoạt động
            sys.exit(0)
        except Exception as e:
            logger.error(f"Lỗi khởi động updater.bat: {e}")
            messagebox.showerror(
                "Lỗi cập nhật",
                f"Không thể áp dụng bản cập nhật tự động:\n{e}"
            )


class DeviceNameFilter(logging.Filter):
    """Tự động thêm [device_name] vào mọi log message từ mọi module."""
    def filter(self, record):
        from utils.utils import get_device_name
        name = get_device_name()
        record.device = f"[{name}]" if name else "[main]"
        return True


class DailySizeZipFileHandler(logging.FileHandler):
    """Write to one active log file, then zip old chunks by date and size."""

    def __init__(self, filename, max_bytes=10 * 1024 * 1024, encoding=None):
        super().__init__(filename, mode="a", encoding=encoding, delay=True)
        self.max_bytes = max_bytes
        if os.path.exists(filename) and os.path.getsize(filename) > 0:
            self.current_date = date.fromtimestamp(os.path.getmtime(filename)).isoformat()
        else:
            self.current_date = date.today().isoformat()
        self.archive_dir = os.path.join(os.path.dirname(os.path.abspath(filename)), "archive")
        os.makedirs(self.archive_dir, exist_ok=True)

    def emit(self, record):
        try:
            if self._should_rollover():
                self._rollover()
            super().emit(record)
            if self._should_rollover(size_only=True):
                self._rollover()
        except Exception:
            self.handleError(record)

    def _should_rollover(self, size_only=False):
        if not os.path.exists(self.baseFilename):
            return False

        if os.path.getsize(self.baseFilename) <= 0:
            if not size_only:
                self.current_date = date.today().isoformat()
            return False

        if os.path.getsize(self.baseFilename) >= self.max_bytes:
            return True

        if not size_only and date.today().isoformat() != self.current_date:
            return True

        return False

    def _next_archive_paths(self, archive_date):
        idx = 1
        while True:
            stem = f"auto_config_{archive_date}_{idx:03d}"
            zip_path = os.path.join(self.archive_dir, f"{stem}.zip")
            log_name = f"{stem}.log"
            if not os.path.exists(zip_path):
                return zip_path, log_name
            idx += 1

    def _rollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None

        if not os.path.exists(self.baseFilename) or os.path.getsize(self.baseFilename) <= 0:
            self.current_date = date.today().isoformat()
            return

        archive_date = self.current_date
        zip_path, log_name = self._next_archive_paths(archive_date)
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(self.baseFilename, arcname=log_name)
        os.remove(self.baseFilename)
        self.current_date = date.today().isoformat()


if __name__ == "__main__":
    os.makedirs("logs", exist_ok=True)

    # Thêm filter vào handler để mọi module đều có %(device)s khi ghi file.
    device_filter = DeviceNameFilter()
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # core.adb có thể đã gọi basicConfig() lúc import, nên cần thay handler
    # ở đây để logs/auto_config.log luôn được ghi đúng.
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()

    file_handler = DailySizeZipFileHandler("logs/auto_config.log", max_bytes=10 * 1024 * 1024, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(device)s %(name)s: %(message)s"
    ))
    file_handler.addFilter(device_filter)
    root_logger.addHandler(file_handler)

    app = AutoConfigGUI()
    app.run()
