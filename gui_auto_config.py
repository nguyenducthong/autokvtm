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

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    if os.getcwd() != BASE_DIR:
        os.chdir(BASE_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.adb_helper import get_adb_helper, ADBHelper
from core.adb import ADBController
from core.trong_cay import main_tc
from core.image import ImageProcessor, get_resource_path
from PIL import Image, ImageTk
import config

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

from config import get_configs_dir
CONFIG_DIR = get_configs_dir()
SELECTED_DEVICE_FILE = os.path.join(BASE_DIR, "selected_device.json")
ITEMS_DIR = os.path.join(BASE_DIR, "assets", "items")


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
    "bat_sang_ban_be": False,
    "bat_cap_nhat_khoi_dong": True,
    "bat_khoi_dong_lai_ld": False,
    "thoi_gian_khoi_dong_lai": 5.0,
    "bat_ai_recovery": False,
    "gemini_api_key": "",
    "bat_yolo": False,
    "yolo_model_path": "configs/kvtm_yolo.onnx"
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

        # Check settings for update check on startup
        run_update_check = True
        try:
            name = self.config_var.get()
            if name:
                path = os.path.join(CONFIG_DIR, f"{name}.json")
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        raw = json.load(f)
                    if isinstance(raw, dict):
                        run_update_check = raw.get("settings", {}).get("bat_cap_nhat_khoi_dong", True)
        except Exception:
            pass

        if run_update_check:
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
        self.tab_config_chung = tk.Frame(self.notebook, bg="#ecf0f1")
        self.tab_screenshot = tk.Frame(self.notebook, bg="#ecf0f1")
        self.tab_match_test = tk.Frame(self.notebook, bg="#ecf0f1")
        self.tab_core_images = tk.Frame(self.notebook, bg="#ecf0f1")
        self.tab_log = tk.Frame(self.notebook, bg="#1e1e1e")

        self.notebook.add(self.tab_auto, text="  Auto  ")
        self.notebook.add(self.tab_config, text="  Cấu Hình  ")
        self.notebook.add(self.tab_config_chung, text="  Cấu Hình Chung  ")
        self.notebook.add(self.tab_screenshot, text="  Chụp & Cắt ảnh  ")
        self.notebook.add(self.tab_match_test, text="  So Sánh Ảnh  ")
        self.notebook.add(self.tab_core_images, text="  Hình ảnh Core  ")
        self.notebook.add(self.tab_log, text="  Nhật Ký  ")

        self._build_tab_auto()
        self._build_tab_config()
        self._build_tab_config_chung()
        self._build_tab_screenshot()
        self._build_tab_match_test()
        self._build_tab_core_images()
        self._build_tab_log()
        self._load_global_settings()

        # Status bar
        self.status_bar_frame = tk.Frame(self.root, bg="#27ae60")
        self.status_bar_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_label = tk.Label(self.status_bar_frame, text="Sẵn sàng", font=("Arial", 9),
                                     bg="#27ae60", fg="white", anchor=tk.W, padx=10)
        self.status_label.pack(side=tk.LEFT)

        self.gemini_stats_lbl = tk.Label(self.status_bar_frame, text="🤖 Gemini AI: 0 reqs", font=("Arial", 9, "bold"),
                                         bg="#8e44ad", fg="white", padx=12, pady=2, cursor="hand2")
        self.gemini_stats_lbl.pack(side=tk.RIGHT)
        self.gemini_stats_lbl.bind("<Button-1>", lambda e: self._open_gemini_log_dialog())

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
        self.use_gemini_kho_var = tk.BooleanVar(value=True)
        tk.Checkbutton(dev_toolbar, text="🤖 Gemini AI", variable=self.use_gemini_kho_var,
                       bg="#ecf0f1", font=("Arial", 8, "bold")).pack(side=tk.LEFT, padx=(0, 4))
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

        dev_name = self.device_cards.get(serial, {}).get("name") or serial

        def run():
            try:
                from utils.utils import setup_thread
                setup_thread(None, device_name=dev_name)
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
        # Lọc bỏ global_settings vì đây là file cấu hình hệ thống, không phải bài chạy nhiệm vụ
        names = sorted([
            os.path.splitext(os.path.basename(f))[0]
            for f in files
            if not os.path.basename(f).startswith("global_setting")
        ])
        self.config_combo["values"] = names
        if names:
            if "mac_dinh" in names:
                self.config_combo.set("mac_dinh")
            else:
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

                # Đồng bộ cấu hình AI toàn cục từ Tab Cấu Hình Chung
                import config as global_config
                global_config.GEMINI_API_KEY = self.gemini_api_key_var.get().strip()
                global_config.ENABLE_AI_RECOVERY = self.bat_ai_recovery_var.get()
                global_config.ENABLE_YOLO = self.bat_yolo_var.get()
                global_config.YOLO_MODEL_PATH = self.yolo_model_path_var.get().strip()

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
                if settings.get("bat_sang_ban_be"):
                    from core.sang_nha_ban_be import can_sang_ban_be, sang_ban_be

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

                    if not stop_ev.is_set() and settings.get("bat_sang_ban_be") and can_sang_ban_be(serial):
                        self._set_card_status(serial, f"{config_name} | Sang bạn...", "#e67e22")
                        handled_sbb = sang_ban_be(adb_inst, serial=serial, stop_event=stop_ev)
                        if handled_sbb:
                            self._log(f"{dev_label} [{config_name}] Đã xử lý sang nhà bạn bè")
                            self._set_card_status(serial, f"{config_name} | Đã sang bạn", "#27ae60")

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

                use_gemini = self.use_gemini_kho_var.get() if hasattr(self, 'use_gemini_kho_var') else False
                for serial, name in targets:
                    self._set_card_status(serial, "Quét kho thành phẩm...", "#8e44ad")
                    adb_inst = ADBController(serial=serial)
                    data = scan_kho_thanh_pham(adb_inst, device_name=name, use_gemini=use_gemini)
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
                self._update_gemini_stats_ui()
            except tk.TclError:
                pass

        try:
            self.root.after(0, _write)
        except (RuntimeError, tk.TclError):
            pass

    def _update_gemini_stats_ui(self):
        """Cập nhật nhãn thống kê số lần gọi Gemini API real-time trên giao diện."""
        try:
            from core.ai_recovery import AIRecovery
            st = AIRecovery.get_stats()
            txt = f"🤖 Gemini AI: {st['total']} reqs ({st['success']} OK"
            if st['ratelimit_429'] > 0:
                txt += f" | {st['ratelimit_429']} lỗi 429"
            if st['failed'] > 0:
                txt += f" | {st['failed']} lỗi"
            txt += ")"
            if hasattr(self, 'gemini_stats_lbl'):
                self.gemini_stats_lbl.config(text=txt)
        except Exception:
            pass

    def _open_gemini_log_dialog(self):
        """Mở popup xem nhật ký chi tiết các lượt gọi Gemini AI (Phân loại theo ngày, tự động xóa quá 3 ngày)."""
        import csv
        from core.ai_recovery import (
            AIRecovery, GEMINI_LOG_DIR, list_gemini_log_files,
            get_current_gemini_csv_path, cleanup_old_gemini_logs
        )

        # Dọn dẹp các file cũ hơn 3 ngày trước khi hiển thị
        cleanup_old_gemini_logs(max_days=3)

        popup = tk.Toplevel(self.root)
        popup.title("📊 Nhật ký Yêu cầu Gemini AI (Gemini Logs theo ngày)")
        popup.geometry("900x640")
        popup.transient(self.root)
        popup.grab_set()

        # Header
        hdr = tk.Frame(popup, bg="#8e44ad", height=45)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        st = AIRecovery.get_stats()
        hdr_lbl = tk.Label(hdr, text=f"🤖 NHẬT KÝ GỌI AI GEMINI | Hôm nay: {st['total']} reqs | OK: {st['success']} | Lỗi 429: {st['ratelimit_429']} | Lỗi khác: {st['failed']}",
                           font=("Arial", 10, "bold"), fg="white", bg="#8e44ad")
        hdr_lbl.pack(pady=12)

        content = tk.Frame(popup, bg="#ecf0f1", padx=12, pady=10)
        content.pack(fill=tk.BOTH, expand=True)

        # Toolbar Lọc
        fltr_frame = tk.Frame(content, bg="#ecf0f1")
        fltr_frame.pack(fill=tk.X, pady=(0, 8))

        # Chọn ngày
        tk.Label(fltr_frame, text="Ngày log:", bg="#ecf0f1", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        log_files = list_gemini_log_files()
        selected_file_var = tk.StringVar()
        if log_files:
            selected_file_var.set(log_files[0])

        date_combo = ttk.Combobox(fltr_frame, textvariable=selected_file_var, values=log_files,
                                  state="readonly", width=18, font=("Arial", 9))
        date_combo.pack(side=tk.LEFT, padx=(4, 15))

        tk.Label(fltr_frame, text="Trạng thái:", bg="#ecf0f1", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        status_fltr_var = tk.StringVar(value="TẤT CẢ")
        status_combo = ttk.Combobox(fltr_frame, textvariable=status_fltr_var,
                                    values=["TẤT CẢ", "SUCCESS", "RATELIMIT_429", "ERROR"],
                                    state="readonly", width=14, font=("Arial", 9))
        status_combo.pack(side=tk.LEFT, padx=(4, 15))

        tk.Label(fltr_frame, text="(Tự động xóa nhật ký cũ hơn 3 ngày)", bg="#ecf0f1", fg="#7f8c8d",
                 font=("Arial", 8, "italic")).pack(side=tk.RIGHT)

        # Bảng Treeview
        tree_frame = tk.Frame(content, bg="#ecf0f1")
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        cols = ("req_id", "timestamp", "device", "model", "status", "http_code", "reason")
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=12)

        tree.heading("req_id", text="ID")
        tree.heading("timestamp", text="Thời gian")
        tree.heading("device", text="Thiết bị")
        tree.heading("model", text="Model AI")
        tree.heading("status", text="Trạng thái")
        tree.heading("http_code", text="Mã HTTP")
        tree.heading("reason", text="Mô tả / Nguyên nhân")

        tree.column("req_id", width=50, anchor=tk.CENTER)
        tree.column("timestamp", width=130, anchor=tk.CENTER)
        tree.column("device", width=100, anchor=tk.W)
        tree.column("model", width=130, anchor=tk.CENTER)
        tree.column("status", width=100, anchor=tk.CENTER)
        tree.column("http_code", width=65, anchor=tk.CENTER)
        tree.column("reason", width=250, anchor=tk.W)

        tree_scroll = tk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(fill=tk.BOTH, expand=True)

        # Tags màu sắc
        tree.tag_configure("SUCCESS", foreground="#27ae60")
        tree.tag_configure("RATELIMIT_429", foreground="#d35400")
        tree.tag_configure("ERROR", foreground="#c0392b")

        # Khung xem chi tiết lỗi / response raw bên dưới
        detail_frame = tk.LabelFrame(content, text="Chi tiết phản hồi / Chi tiết lỗi", font=("Arial", 9, "bold"),
                                     bg="#ecf0f1", padx=8, pady=6)
        detail_frame.pack(fill=tk.X, pady=(0, 8))

        detail_text = tk.Text(detail_frame, font=("Consolas", 9), bg="white", height=6, wrap=tk.WORD, relief=tk.SOLID, bd=1)
        detail_scroll = tk.Scrollbar(detail_frame, command=detail_text.yview)
        detail_text.config(yscrollcommand=detail_scroll.set)
        detail_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        detail_text.pack(fill=tk.BOTH, expand=True)

        loaded_entries = []

        def load_logs_to_tree():
            nonlocal loaded_entries
            for item in tree.get_children():
                tree.delete(item)

            loaded_entries.clear()

            # Cập nhật thống kê header và footer
            st = AIRecovery.get_stats()
            hdr_lbl.config(text=f"🤖 NHẬT KÝ GỌI AI GEMINI | Hôm nay: {st['total']} reqs | OK: {st['success']} | Lỗi 429: {st['ratelimit_429']} | Lỗi khác: {st['failed']}")
            self._update_gemini_stats_ui()

            # Lấy danh sách file log mới nhất
            updated_files = list_gemini_log_files()
            date_combo.config(values=updated_files)

            curr_file = selected_file_var.get()
            if not curr_file and updated_files:
                curr_file = updated_files[0]
                selected_file_var.set(curr_file)

            if curr_file:
                target_csv = os.path.join(GEMINI_LOG_DIR, curr_file)
                if os.path.isfile(target_csv):
                    try:
                        with open(target_csv, mode="r", encoding="utf-8-sig") as f:
                            reader = csv.DictReader(f)
                            for row in reader:
                                loaded_entries.append({
                                    "req_id": row.get("RequestID", ""),
                                    "timestamp": row.get("Timestamp", ""),
                                    "device": row.get("Device", ""),
                                    "model": (row.get("Model") or "").strip(),
                                    "status": row.get("Status", ""),
                                    "http_code": row.get("HTTPCode", ""),
                                    "reason": row.get("Reason", ""),
                                    "error_details": row.get("ErrorDetails", ""),
                                    "raw_response": ""
                                })
                    except Exception as ex:
                        logger.error(f"Lỗi đọc CSV log: {ex}")

            # Nếu không đọc được từ file mà bộ nhớ có thì nạp bộ nhớ
            if not loaded_entries and AIRecovery.log_history:
                loaded_entries = list(AIRecovery.log_history)

            selected_st = status_fltr_var.get()
            for idx, entry in enumerate(reversed(loaded_entries)):
                st_name = entry.get("status", "")
                if selected_st != "TẤT CẢ" and st_name != selected_st:
                    continue

                tree.insert("", tk.END, iid=str(idx), values=(
                    entry.get("req_id", ""),
                    entry.get("timestamp", ""),
                    entry.get("device", ""),
                    entry.get("model") or "—",
                    st_name,
                    entry.get("http_code", ""),
                    entry.get("reason", "")
                ), tags=(st_name,))

        def on_tree_select(event):
            sel = tree.selection()
            if not sel:
                return
            idx = int(sel[0])
            reversed_list = list(reversed(loaded_entries))
            if 0 <= idx < len(reversed_list):
                entry = reversed_list[idx]
                detail_text.config(state=tk.NORMAL)
                detail_text.delete("1.0", tk.END)
                model_used = entry.get('model') or "Không xác định"
                api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_used}:generateContent" if entry.get('model') else "—"
                detail_text.insert(tk.END, f"📌 [{entry.get('req_id')}] - Thiết bị: {entry.get('device')} ({entry.get('timestamp')})\n")
                detail_text.insert(tk.END, f"🤖 Model AI (thời điểm gọi): {model_used} | Trạng thái: {entry.get('status')} | Mã HTTP: {entry.get('http_code')}\n")
                detail_text.insert(tk.END, f"🔗 API URL: {api_url}\n")
                detail_text.insert(tk.END, "━" * 65 + "\n")
                if entry.get("error_details"):
                    detail_text.insert(tk.END, f"❌ CHI TIẾT LỖI:\n{entry.get('error_details')}\n\n")
                if entry.get("raw_response"):
                    detail_text.insert(tk.END, f"💬 PHẢN HỒI GỐC (RAW):\n{entry.get('raw_response')}\n")
                elif not entry.get("error_details"):
                    detail_text.insert(tk.END, f"Nội dung / Nguyên nhân: {entry.get('reason')}\n")
                detail_text.config(state=tk.DISABLED)

        tree.bind("<<TreeviewSelect>>", on_tree_select)
        date_combo.bind("<<ComboboxSelected>>", lambda e: load_logs_to_tree())
        status_combo.bind("<<ComboboxSelected>>", lambda e: load_logs_to_tree())
        load_logs_to_tree()

        # Nút bấm hành động
        btn_bar = tk.Frame(content, bg="#ecf0f1")
        btn_bar.pack(fill=tk.X)

        def open_csv_file():
            curr_file = selected_file_var.get()
            if curr_file:
                target_csv = os.path.join(GEMINI_LOG_DIR, curr_file)
                if os.path.isfile(target_csv):
                    os.startfile(os.path.abspath(target_csv))
                    return
            messagebox.showinfo("Thông báo", "Chưa có file log CSV nào!")

        def clear_logs():
            if messagebox.askyesno("Xác nhận", "Xóa toàn bộ nhật ký Gemini log hiện tại?"):
                AIRecovery.reset_stats()
                curr_file = selected_file_var.get()
                if curr_file:
                    target_csv = os.path.join(GEMINI_LOG_DIR, curr_file)
                    if os.path.isfile(target_csv):
                        try:
                            os.remove(target_csv)
                        except Exception:
                            pass
                cleanup_old_gemini_logs(max_days=3)
                load_logs_to_tree()
                detail_text.config(state=tk.NORMAL)
                detail_text.delete("1.0", tk.END)
                detail_text.config(state=tk.DISABLED)
                self._update_gemini_stats_ui()

        tk.Button(btn_bar, text="📂 Mở file CSV ngày chọn", command=open_csv_file,
                  bg="#27ae60", fg="white", relief=tk.FLAT, cursor="hand2",
                  padx=12, pady=4, font=("Arial", 9, "bold")).pack(side=tk.LEFT)

        tk.Button(btn_bar, text="🔄 Làm mới", command=load_logs_to_tree,
                  bg="#3498db", fg="white", relief=tk.FLAT, cursor="hand2",
                  padx=12, pady=4, font=("Arial", 9)).pack(side=tk.LEFT, padx=6)

        tk.Button(btn_bar, text="🗑️ Xóa log ngày chọn", command=clear_logs,
                  bg="#e74c3c", fg="white", relief=tk.FLAT, cursor="hand2",
                  padx=12, pady=4, font=("Arial", 9)).pack(side=tk.LEFT)

        tk.Button(btn_bar, text="Đóng", command=popup.destroy,
                  bg="#95a5a6", fg="white", relief=tk.FLAT, cursor="hand2",
                  padx=16, pady=4, font=("Arial", 9)).pack(side=tk.RIGHT)

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
    # TAB: CẤU HÌNH CHUNG (AI & YOLO)
    # ----------------------------------------------------------------
    def _build_tab_config_chung(self):
        """Tạo giao diện cho tab Cấu Hình Chung."""
        import config
        # Container
        pad = tk.Frame(self.tab_config_chung, bg="#ecf0f1", padx=15, pady=15)
        pad.pack(fill=tk.BOTH, expand=True)

        title = tk.Label(pad, text="CẤU HÌNH AI & YOLO TOÀN CỤC (Dùng chung cho mọi cấu hình)", 
                         font=("Arial", 11, "bold"), bg="#ecf0f1", fg="#2c3e50")
        title.pack(anchor=tk.W, pady=(0, 12))

        # 1. Gemini AI Frame
        ai_frame = tk.LabelFrame(pad, text="Cấu hình Gemini AI (Gỡ kẹt màn hình)", font=("Arial", 10, "bold"),
                                  bg="#ecf0f1", fg="#2980b9", padx=15, pady=12)
        ai_frame.pack(fill=tk.X, pady=8)

        ai_row = tk.Frame(ai_frame, bg="#ecf0f1")
        ai_row.pack(fill=tk.X, pady=4)
        tk.Label(ai_row, text="Gemini AI Recovery:", bg="#ecf0f1", width=20, anchor=tk.W, font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        self.bat_ai_recovery_var = tk.BooleanVar(value=getattr(config, "ENABLE_AI_RECOVERY", True))
        tk.Checkbutton(ai_row, text="Bật AI Recovery (Tự động đóng popup, quảng cáo, captcha khi bị kẹt)", 
                       variable=self.bat_ai_recovery_var, bg="#ecf0f1",
                       font=("Arial", 9), activebackground="#ecf0f1").pack(side=tk.LEFT)

        key_row = tk.Frame(ai_frame, bg="#ecf0f1")
        key_row.pack(fill=tk.X, pady=4)
        tk.Label(key_row, text="Gemini API Key:", bg="#ecf0f1", width=20, anchor=tk.W, font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        self.gemini_api_key_var = tk.StringVar(value=getattr(config, "GEMINI_API_KEY", ""))
        self.gemini_api_key_entry = tk.Entry(key_row, textvariable=self.gemini_api_key_var, width=50, font=("Arial", 9))
        self.gemini_api_key_entry.pack(side=tk.LEFT, padx=(0, 6))

        # Nút ghi chú ? hướng dẫn tạo API Key
        help_btn = tk.Button(key_row, text="?", command=self._show_gemini_guide_popup,
                             bg="#3498db", fg="white", font=("Arial", 9, "bold"),
                             width=2, relief=tk.FLAT, cursor="hand2", title_text="Hướng dẫn tạo API Key" if hasattr(tk.Button, 'title_text') else None)
        help_btn.pack(side=tk.LEFT, padx=2)

        model_row = tk.Frame(ai_frame, bg="#ecf0f1")
        model_row.pack(fill=tk.X, pady=4)
        tk.Label(model_row, text="Gemini AI Model:", bg="#ecf0f1", width=20, anchor=tk.W, font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        self.gemini_model_var = tk.StringVar(value=getattr(config, "GEMINI_MODEL", "gemini-3.5-flash-lite"))
        model_options = [
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemini-3.7-flash"
        ]
        self.gemini_model_cb = ttk.Combobox(model_row, textvariable=self.gemini_model_var, values=model_options, width=24, state="readonly")
        self.gemini_model_cb.pack(side=tk.LEFT, padx=(0, 6))

        fetch_btn = tk.Button(model_row, text="🔄 Tải danh sách Model từ API Key", command=self._fetch_gemini_models_from_api,
                              bg="#27ae60", fg="white", font=("Arial", 8, "bold"),
                              relief=tk.FLAT, cursor="hand2", padx=6, pady=2)
        fetch_btn.pack(side=tk.LEFT, padx=(0, 6))

        # 2. YOLO Frame
        yolo_frame = tk.LabelFrame(pad, text="Cấu hình YOLO Detection (Quầy hàng)", font=("Arial", 10, "bold"),
                                    bg="#ecf0f1", fg="#27ae60", padx=15, pady=12)
        yolo_frame.pack(fill=tk.X, pady=8)

        yolo_row = tk.Frame(yolo_frame, bg="#ecf0f1")
        yolo_row.pack(fill=tk.X, pady=4)
        tk.Label(yolo_row, text="YOLO Detection:", bg="#ecf0f1", width=20, anchor=tk.W, font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        self.bat_yolo_var = tk.BooleanVar(value=getattr(config, "ENABLE_YOLO", False))
        tk.Checkbutton(yolo_row, text="Bật YOLO Detection (Tìm ô trống, nhặt vàng siêu tốc)", 
                       variable=self.bat_yolo_var, bg="#ecf0f1",
                       font=("Arial", 9), activebackground="#ecf0f1").pack(side=tk.LEFT)

        path_row = tk.Frame(yolo_frame, bg="#ecf0f1")
        path_row.pack(fill=tk.X, pady=4)
        tk.Label(path_row, text="Model ONNX Path:", bg="#ecf0f1", width=20, anchor=tk.W, font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        self.yolo_model_path_var = tk.StringVar(value=getattr(config, "YOLO_MODEL_PATH", "configs/kvtm_yolo.onnx"))
        self.yolo_model_path_entry = tk.Entry(path_row, textvariable=self.yolo_model_path_var, width=55, font=("Arial", 9))
        self.yolo_model_path_entry.pack(side=tk.LEFT)

        # 3. Delay Frame (Cấu hình Thời Gian Chờ cho từng tác vụ)
        delay_frame = tk.LabelFrame(pad, text="Cấu hình Thời Gian Chờ & Delay (Đơn vị: Giây)", font=("Arial", 10, "bold"),
                                    bg="#ecf0f1", fg="#8e44ad", padx=15, pady=12)
        delay_frame.pack(fill=tk.X, pady=8)

        # Hàng 1: Trồng cây (core/trong_cay.py)
        row_tc = tk.Frame(delay_frame, bg="#ecf0f1")
        row_tc.pack(fill=tk.X, pady=4)
        tk.Label(row_tc, text="[Trồng cây] TIME_SLEEP (s):", bg="#ecf0f1", width=25, anchor=tk.W, font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        self.time_sleep_trong_cay_var = tk.StringVar(value=str(getattr(config, "TIME_SLEEP_TRONG_CAY", 0.5)))
        tk.Entry(row_tc, textvariable=self.time_sleep_trong_cay_var, width=8, font=("Arial", 9)).pack(side=tk.LEFT, padx=(0, 20))
        tk.Label(row_tc, text="TIME_SLEEP_SHORT (s):", bg="#ecf0f1", width=22, anchor=tk.W, font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        self.time_sleep_short_trong_cay_var = tk.StringVar(value=str(getattr(config, "TIME_SLEEP_SHORT_TRONG_CAY", 0.3)))
        tk.Entry(row_tc, textvariable=self.time_sleep_short_trong_cay_var, width=8, font=("Arial", 9)).pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(row_tc, text="(Chờ cập nhật cây chín, mở giỏ hạt, lật trang)", bg="#ecf0f1", fg="#7f8c8d", font=("Arial", 8, "italic")).pack(side=tk.LEFT)

        # Hàng 2: Máy Sản Xuất (core/san_xuat.py)
        row_sx = tk.Frame(delay_frame, bg="#ecf0f1")
        row_sx.pack(fill=tk.X, pady=4)
        tk.Label(row_sx, text="[Sản xuất] TIME_SLEEP (s):", bg="#ecf0f1", width=25, anchor=tk.W, font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        self.time_sleep_san_xuat_var = tk.StringVar(value=str(getattr(config, "TIME_SLEEP_SAN_XUAT", 0.15)))
        tk.Entry(row_sx, textvariable=self.time_sleep_san_xuat_var, width=8, font=("Arial", 9)).pack(side=tk.LEFT, padx=(0, 20))
        tk.Label(row_sx, text="TIME_SLEEP_SHORT (s):", bg="#ecf0f1", width=22, anchor=tk.W, font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        self.time_sleep_short_san_xuat_var = tk.StringVar(value=str(getattr(config, "TIME_SLEEP_SHORT_SAN_XUAT", 0.3)))
        tk.Entry(row_sx, textvariable=self.time_sleep_short_san_xuat_var, width=8, font=("Arial", 9)).pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(row_sx, text="(Nghỉ giữa các lượt kéo vào ô, mở popup máy)", bg="#ecf0f1", fg="#7f8c8d", font=("Arial", 8, "italic")).pack(side=tk.LEFT)

        # Hàng 3: Thu hoạch, Cám, Bán đồ
        row_khac = tk.Frame(delay_frame, bg="#ecf0f1")
        row_khac.pack(fill=tk.X, pady=4)
        tk.Label(row_khac, text="[Thu hoạch] CLICK_DELAY (s):", bg="#ecf0f1", width=25, anchor=tk.W, font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        self.click_delay_thu_hoach_var = tk.StringVar(value=str(getattr(config, "CLICK_DELAY_THU_HOACH", 0.35)))
        tk.Entry(row_khac, textvariable=self.click_delay_thu_hoach_var, width=8, font=("Arial", 9)).pack(side=tk.LEFT, padx=(0, 20))
        tk.Label(row_khac, text="[Cám] TIME_SLEEP (s):", bg="#ecf0f1", width=22, anchor=tk.W, font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        self.time_sleep_sxcam_var = tk.StringVar(value=str(getattr(config, "TIME_SLEEP_SXCAM", 0.35)))
        tk.Entry(row_khac, textvariable=self.time_sleep_sxcam_var, width=8, font=("Arial", 9)).pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(row_khac, text="[Bán đồ] DELAY (s):", bg="#ecf0f1", width=18, anchor=tk.W, font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        self.click_delay_ban_do_var = tk.StringVar(value=str(getattr(config, "CLICK_DELAY_BAN_DO", 1.0)))
        tk.Entry(row_khac, textvariable=self.click_delay_ban_do_var, width=8, font=("Arial", 9)).pack(side=tk.LEFT)

        # Tự động lưu cấu hình chung khi có bất kỳ thay đổi nào
        self.bat_ai_recovery_var.trace_add("write", lambda *args: self._save_global_settings())
        self.gemini_api_key_var.trace_add("write", lambda *args: self._save_global_settings())
        self.gemini_model_var.trace_add("write", lambda *args: self._save_global_settings())
        self.bat_yolo_var.trace_add("write", lambda *args: self._save_global_settings())
        self.yolo_model_path_var.trace_add("write", lambda *args: self._save_global_settings())
        self.time_sleep_trong_cay_var.trace_add("write", lambda *args: self._save_global_settings())
        self.time_sleep_short_trong_cay_var.trace_add("write", lambda *args: self._save_global_settings())
        self.time_sleep_san_xuat_var.trace_add("write", lambda *args: self._save_global_settings())
        self.time_sleep_short_san_xuat_var.trace_add("write", lambda *args: self._save_global_settings())
        self.click_delay_thu_hoach_var.trace_add("write", lambda *args: self._save_global_settings())
        self.time_sleep_sxcam_var.trace_add("write", lambda *args: self._save_global_settings())
        self.click_delay_ban_do_var.trace_add("write", lambda *args: self._save_global_settings())

    def _fetch_gemini_models_from_api(self):
        """Tải danh sách mô hình AI khả dụng từ API Key của Google Gemini."""
        api_key = self.gemini_api_key_var.get().strip()
        if not api_key:
            messagebox.showwarning("Thiếu API Key", "Vui lòng nhập Gemini API Key trước khi tải danh sách Model!")
            return

        def task():
            try:
                import requests
                url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
                res = requests.get(url, timeout=10)
                if res.status_code == 200:
                    data = res.json()
                    raw_models = data.get("models", [])
                    fetched = []
                    for m in raw_models:
                        methods = m.get("supportedGenerationMethods", [])
                        if "generateContent" in methods:
                            name = m.get("name", "").replace("models/", "").strip()
                            if name:
                                fetched.append(name)

                    if fetched:
                        unique_fetched = list(dict.fromkeys(fetched))
                        def update_ui():
                            curr = self.gemini_model_var.get().strip()
                            self.gemini_model_cb['values'] = unique_fetched
                            if curr in unique_fetched:
                                self.gemini_model_var.set(curr)
                            elif "gemini-3.5-flash-lite" in unique_fetched:
                                self.gemini_model_var.set("gemini-3.5-flash-lite")
                            else:
                                self.gemini_model_var.set(unique_fetched[0])
                            messagebox.showinfo("Thành công", f"Đã tải thành công {len(unique_fetched)} mô hình Gemini từ API Key của bạn!")

                        self.root.after(0, update_ui)
                    else:
                        self.root.after(0, lambda: messagebox.showwarning("Thông báo", "Không tìm thấy mô hình generateContent nào khả dụng cho API Key này."))
                else:
                    err_msg = res.text
                    self.root.after(0, lambda: messagebox.showerror("Lỗi API", f"Không thể lấy danh sách Model (Mã lỗi {res.status_code}):\n{err_msg[:200]}"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Lỗi kết nối", f"Lỗi kết nối khi tải danh sách Model: {e}"))

        threading.Thread(target=task, daemon=True).start()

    def _save_global_settings(self):
        """Lưu cấu hình chung (API Key, YOLO, Time Delays) vào file global_settings.json mà không làm mất các cài đặt khác."""
        GLOBAL_SETTINGS_FILE = os.path.join(CONFIG_DIR, "global_settings.json")
        existing = {}
        if os.path.exists(GLOBAL_SETTINGS_FILE):
            try:
                with open(GLOBAL_SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    existing = json.load(f) or {}
            except Exception:
                pass
        existing["gemini_api_key"] = self.gemini_api_key_var.get().strip()
        existing["gemini_model"] = self.gemini_model_var.get().strip() or "gemini-3.5-flash-lite"
        existing["bat_ai_recovery"] = self.bat_ai_recovery_var.get()
        existing["bat_yolo"] = self.bat_yolo_var.get()
        existing["yolo_model_path"] = self.yolo_model_path_var.get().strip()

        # Lưu time_delays
        time_delays = existing.get("time_delays", {})
        if not isinstance(time_delays, dict):
            time_delays = {}

        def _safe_float(var, default_val):
            try:
                return float(var.get().strip())
            except Exception:
                return default_val

        import config
        time_delays["time_sleep_trong_cay"] = _safe_float(self.time_sleep_trong_cay_var, 0.5)
        time_delays["time_sleep_short_trong_cay"] = _safe_float(self.time_sleep_short_trong_cay_var, 0.3)
        time_delays["time_sleep_san_xuat"] = _safe_float(self.time_sleep_san_xuat_var, 0.15)
        time_delays["time_sleep_short_san_xuat"] = _safe_float(self.time_sleep_short_san_xuat_var, 0.3)
        time_delays["click_delay_thu_hoach"] = _safe_float(self.click_delay_thu_hoach_var, 0.35)
        time_delays["time_sleep_sxcam"] = _safe_float(self.time_sleep_sxcam_var, 0.35)
        time_delays["click_delay_ban_do"] = _safe_float(self.click_delay_ban_do_var, 1.0)
        existing["time_delays"] = time_delays

        # Đồng bộ trực tiếp vào module config đang chạy
        config.TIME_SLEEP_TRONG_CAY = time_delays["time_sleep_trong_cay"]
        config.TIME_SLEEP_SHORT_TRONG_CAY = time_delays["time_sleep_short_trong_cay"]
        config.TIME_SLEEP_SAN_XUAT = time_delays["time_sleep_san_xuat"]
        config.TIME_SLEEP_SHORT_SAN_XUAT = time_delays["time_sleep_short_san_xuat"]
        config.CLICK_DELAY_THU_HOACH = time_delays["click_delay_thu_hoach"]
        config.TIME_SLEEP_SXCAM = time_delays["time_sleep_sxcam"]
        config.CLICK_DELAY_BAN_DO = time_delays["click_delay_ban_do"]
        config.TIME_SLEEP = time_delays["time_sleep_trong_cay"]
        config.TIME_SLEEP_SHORT = time_delays["time_sleep_short_trong_cay"]

        try:
            os.makedirs(os.path.dirname(GLOBAL_SETTINGS_FILE), exist_ok=True)
            with open(GLOBAL_SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.exception(f"Lỗi khi lưu cấu hình chung: {e}")


    def _load_global_settings(self):
        """Tải cấu hình chung từ file global_settings.json hoặc từ config.py mặc định."""
        GLOBAL_SETTINGS_FILE = os.path.join(CONFIG_DIR, "global_settings.json")
        import config
        default_key = ""
        
        data = {
            "gemini_api_key": getattr(config, "GEMINI_API_KEY", "") or default_key,
            "gemini_model": getattr(config, "GEMINI_MODEL", "gemini-3.5-flash-lite"),
            "bat_ai_recovery": getattr(config, "ENABLE_AI_RECOVERY", True),
            "bat_yolo": getattr(config, "ENABLE_YOLO", False),
            "yolo_model_path": getattr(config, "YOLO_MODEL_PATH", "configs/kvtm_yolo.onnx")
        }
        if os.path.exists(GLOBAL_SETTINGS_FILE):
            try:
                with open(GLOBAL_SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    file_data = json.load(f) or {}
                    for k, v in file_data.items():
                        if v is not None:
                            data[k] = v
            except Exception:
                pass
                
        self.gemini_api_key_var.set(data["gemini_api_key"])
        self.gemini_model_var.set(data.get("gemini_model", "gemini-3.6-flash"))
        self.bat_ai_recovery_var.set(data["bat_ai_recovery"])
        self.bat_yolo_var.set(data["bat_yolo"])
        self.yolo_model_path_var.set(data["yolo_model_path"])
        
        # Đồng bộ trực tiếp vào module config
        config.GEMINI_API_KEY = data["gemini_api_key"]
        config.GEMINI_MODEL = data.get("gemini_model", "gemini-3.6-flash")
        config.ENABLE_AI_RECOVERY = data["bat_ai_recovery"]
        config.ENABLE_YOLO = data["bat_yolo"]
        config.YOLO_MODEL_PATH = data["yolo_model_path"]

        # Tải time_delays
        delays = data.get("time_delays", {})
        if not isinstance(delays, dict):
            delays = {}
        ts_tc = float(delays.get("time_sleep_trong_cay", getattr(config, "TIME_SLEEP_TRONG_CAY", 0.5)))
        tss_tc = float(delays.get("time_sleep_short_trong_cay", getattr(config, "TIME_SLEEP_SHORT_TRONG_CAY", 0.3)))
        ts_sx = float(delays.get("time_sleep_san_xuat", getattr(config, "TIME_SLEEP_SAN_XUAT", 0.15)))
        tss_sx = float(delays.get("time_sleep_short_san_xuat", getattr(config, "TIME_SLEEP_SHORT_SAN_XUAT", 0.3)))
        cd_th = float(delays.get("click_delay_thu_hoach", getattr(config, "CLICK_DELAY_THU_HOACH", 0.35)))
        ts_cam = float(delays.get("time_sleep_sxcam", getattr(config, "TIME_SLEEP_SXCAM", 0.35)))
        cd_bd = float(delays.get("click_delay_ban_do", getattr(config, "CLICK_DELAY_BAN_DO", 1.0)))

        self.time_sleep_trong_cay_var.set(str(ts_tc))
        self.time_sleep_short_trong_cay_var.set(str(tss_tc))
        self.time_sleep_san_xuat_var.set(str(ts_sx))
        self.time_sleep_short_san_xuat_var.set(str(tss_sx))
        self.click_delay_thu_hoach_var.set(str(cd_th))
        self.time_sleep_sxcam_var.set(str(ts_cam))
        self.click_delay_ban_do_var.set(str(cd_bd))

        config.TIME_SLEEP_TRONG_CAY = ts_tc
        config.TIME_SLEEP_SHORT_TRONG_CAY = tss_tc
        config.TIME_SLEEP_SAN_XUAT = ts_sx
        config.TIME_SLEEP_SHORT_SAN_XUAT = tss_sx
        config.CLICK_DELAY_THU_HOACH = cd_th
        config.TIME_SLEEP_SXCAM = ts_cam
        config.CLICK_DELAY_BAN_DO = cd_bd
        config.TIME_SLEEP = ts_tc
        config.TIME_SLEEP_SHORT = tss_tc


    def _show_gemini_guide_popup(self):
        """Hiển thị popup hướng dẫn cách tạo và lấy API Key miễn phí từ Google Gemini."""
        import webbrowser
        
        popup = tk.Toplevel(self.root)
        popup.title("Hướng Dẫn Lấy Gemini API Key Miễn Phí")
        w, h = 540, 420
        sx = self.root.winfo_screenwidth()
        sy = self.root.winfo_screenheight()
        popup.geometry(f"{w}x{h}+{(sx - w) // 2}+{(sy - h) // 2}")
        popup.resizable(False, False)
        popup.configure(bg="#ecf0f1")
        popup.grab_set()  # Modal popup

        # Header
        hdr = tk.Frame(popup, bg="#2980b9", height=45)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="HƯỚNG DẪN TẠO GEMINI API KEY MIỄN PHÍ",
                 font=("Arial", 11, "bold"), fg="white", bg="#2980b9").pack(pady=10)

        # Content container
        body = tk.Frame(popup, bg="#ecf0f1", padx=20, pady=15)
        body.pack(fill=tk.BOTH, expand=True)

        guide_text = (
            "Google cung cấp Gemini API hoàn toàn MIỄN PHÍ để hỗ trợ người dùng.\n"
            "Các bước thực hiện nhanh để lấy API Key:\n\n"
            "1. Bấm nút [Mở Google AI Studio] bên dưới để mở trang tạo Key.\n"
            "2. Đăng nhập bằng tài khoản Google (Gmail) của bạn.\n"
            "3. Bấm vào nút 'Get API key' ở góc trên bên trái màn hình.\n"
            "4. Chọn 'Create API key' ➡️ Chọn 'Create API key in new project'.\n"
            "5. Sao chép (Copy) chuỗi API Key vừa tạo.\n"
            "6. Dán vào ô 'Gemini API Key' trong Tool và sử dụng ngay!\n\n"
            "Lưu ý: API Key là mã riêng tư của bạn, không nên chia sẻ công khai."
        )

        tk.Label(body, text=guide_text, font=("Arial", 9), bg="#ecf0f1",
                 fg="#2c3e50", justify=tk.LEFT, wraplength=490).pack(anchor=tk.W, pady=(0, 15))

        # Action buttons
        btn_row = tk.Frame(body, bg="#ecf0f1")
        btn_row.pack(fill=tk.X, pady=5)

        def open_url():
            webbrowser.open("https://aistudio.google.com/app/apikey")

        open_btn = tk.Button(btn_row, text="🌐 Mở Google AI Studio để tạo Key", command=open_url,
                             bg="#27ae60", fg="white", font=("Arial", 9, "bold"),
                             padx=12, pady=6, relief=tk.FLAT, cursor="hand2")
        open_btn.pack(side=tk.LEFT, padx=(0, 10))

        close_btn = tk.Button(btn_row, text="Đóng", command=popup.destroy,
                              bg="#95a5a6", fg="white", font=("Arial", 9, "bold"),
                              padx=15, pady=6, relief=tk.FLAT, cursor="hand2")
        close_btn.pack(side=tk.LEFT)

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

        # Công cụ AI & Gỡ kẹt
        ai_tool_frame = tk.LabelFrame(right, text="Công cụ AI & Gỡ kẹt", font=("Arial", 10, "bold"),
                                      bg="#ecf0f1", padx=8, pady=8)
        ai_tool_frame.pack(fill=tk.X, padx=8, pady=4)
        tk.Button(ai_tool_frame, text="Quét YOLO (Test model)", command=self._ss_test_yolo,
                  bg="#9b59b6", fg="white", relief=tk.FLAT, cursor="hand2").pack(fill=tk.X, pady=2)
        tk.Button(ai_tool_frame, text="Gửi Gemini VLM (Gỡ kẹt)", command=self._ss_test_gemini,
                  bg="#34495e", fg="white", relief=tk.FLAT, cursor="hand2").pack(fill=tk.X, pady=2)
        tk.Button(ai_tool_frame, text="Lưu Dataset YOLO", command=self._ss_save_yolo_dataset,
                  bg="#16a085", fg="white", relief=tk.FLAT, cursor="hand2").pack(fill=tk.X, pady=2)

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

    def _ss_display_clean(self):
        """Vẽ lại ảnh gốc sạch lên canvas để xóa các nét vẽ cũ"""
        if self.ss_screenshot is not None:
            self.ss_canvas.delete("all")
            self.ss_canvas.create_image(0, 0, anchor=tk.NW, image=self.ss_photo)
            self.ss_crop_rect = None

    def _ss_test_yolo(self):
        if self.ss_screenshot is None:
            messagebox.showwarning("Cảnh báo", "Vui lòng chụp ảnh (F2) trước!")
            return
        
        model_path = self.yolo_model_path_var.get().strip()
        if not os.path.exists(model_path):
            messagebox.showerror("Lỗi", f"Không tìm thấy mô hình YOLO tại:\n{model_path}\nVui lòng tạo hoặc đặt mô hình ONNX đúng thư mục.")
            return

        import threading

        def run():
            from core.yolo_detector import YOLODetector
            import config
            old_val = config.ENABLE_YOLO
            old_path = config.YOLO_MODEL_PATH
            try:
                config.ENABLE_YOLO = True
                config.YOLO_MODEL_PATH = model_path
                
                detector = YOLODetector()
                if not detector.is_available():
                    self.root.after(0, lambda: messagebox.showerror("Lỗi", "Không thể khởi tạo mô hình YOLO. Vui lòng kiểm tra log."))
                    return

                self.root.after(0, lambda: self.status_label.config(text="Đang nhận diện YOLO...", bg="#f39c12"))
                
                detections = detector.detect(self.ss_screenshot)
                self.root.after(0, lambda: self._ss_on_yolo_done(detections))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Lỗi", f"Lỗi nhận diện YOLO: {e}"))
            finally:
                config.ENABLE_YOLO = old_val
                config.YOLO_MODEL_PATH = old_path

        threading.Thread(target=run, daemon=True).start()

    def _ss_on_yolo_done(self, detections):
        self._ss_display_clean()
        info_lines = [f"--- KẾT QUẢ YOLO ({len(detections)} vật thể) ---"]
        for det in detections:
            label = det["class"]
            conf = det["confidence"]
            box = det["box"]
            cx, cy = det["center"]
            
            info_lines.append(f"• {label} ({conf*100:.1f}%) tại ({cx},{cy})")
            
            x, y, w, h = box
            self.ss_canvas.create_rectangle(x, y, x + w, y + h, outline="#9b59b6", width=2)
            self.ss_canvas.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill="red", outline="white")
            self.ss_canvas.create_text(x, max(y - 8, 10), text=f"{label} {conf:.2f}", fill="#9b59b6", font=("Arial", 8, "bold"), anchor=tk.W)
            
        self._ss_set_info("\n".join(info_lines))
        self.status_label.config(text=f"Đã nhận diện {len(detections)} vật thể", bg="#27ae60")

    def _ss_test_gemini(self):
        if self.ss_screenshot is None:
            messagebox.showwarning("Cảnh báo", "Vui lòng chụp ảnh (F2) trước!")
            return
            
        api_key = self.gemini_api_key_var.get().strip()
        if not api_key:
            import config
            api_key = getattr(config, "GEMINI_API_KEY", "").strip()
            
        if not api_key:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập Gemini API Key ở mục cài đặt chung!")
            return
            
        import threading
        
        def run():
            from core.ai_recovery import AIRecovery
            import config
            old_val = config.ENABLE_AI_RECOVERY
            old_key = config.GEMINI_API_KEY
            old_model = getattr(config, "GEMINI_MODEL", "gemini-3.5-flash-lite")
            try:
                config.ENABLE_AI_RECOVERY = True
                config.GEMINI_API_KEY = api_key
                config.GEMINI_MODEL = self.gemini_model_var.get().strip() or old_model
                
                ai_rec = AIRecovery()
                self.root.after(0, lambda: self.status_label.config(text="Đang gửi ảnh tới Gemini VLM...", bg="#f39c12"))
                
                result = ai_rec.analyze_and_recover(self.ss_screenshot)
                self.root.after(0, lambda: self._ss_on_gemini_done(result))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Lỗi", f"Lỗi kết nối Gemini: {e}"))
                self.root.after(0, lambda: self.status_label.config(text="Lỗi kết nối", bg="#e74c3c"))
            finally:
                config.ENABLE_AI_RECOVERY = old_val
                config.GEMINI_API_KEY = old_key
                config.GEMINI_MODEL = old_model

        threading.Thread(target=run, daemon=True).start()

    def _ss_on_gemini_done(self, result):
        self._ss_display_clean()
        if result:
            import json
            info_text = "--- KẾT QUẢ GEMINI API ---\n"
            info_text += json.dumps(result, indent=2, ensure_ascii=False)
            self._ss_set_info(info_text)
            
            if result.get("is_stuck") and result.get("action") == "click" and result.get("original_coords"):
                cx, cy = result["original_coords"]
                self.ss_canvas.create_oval(cx - 15, cy - 15, cx + 15, cy + 15, outline="red", width=2)
                self.ss_canvas.create_line(cx - 20, cy, cx + 20, cy, fill="red", width=2)
                self.ss_canvas.create_line(cx, cy - 20, cx, cy + 20, fill="red", width=2)
                self.ss_canvas.create_text(cx + 18, cy + 18, text="CLICK HERE", fill="red", font=("Arial", 10, "bold"), anchor=tk.NW)
                
            self.status_label.config(text="Gemini phân tích xong", bg="#27ae60")
        else:
            self._ss_set_info("Lỗi: Không nhận được phản hồi hợp lệ từ Gemini.")
            self.status_label.config(text="Lỗi Gemini", bg="#e74c3c")

    def _ss_save_yolo_dataset(self):
        if self.ss_screenshot is None:
            messagebox.showwarning("Cảnh báo", "Vui lòng chụp ảnh (F2) trước!")
            return
            
        try:
            from core.yolo_detector import save_screenshot_for_training
            filepath = save_screenshot_for_training(self.ss_screenshot)
            if filepath:
                messagebox.showinfo("Thành công", f"Đã lưu ảnh chụp làm dữ liệu YOLO:\n{filepath}")
            else:
                raise Exception("Lưu ảnh thất bại")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không lưu được ảnh: {e}")

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
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            req = urllib.request.Request(
                GITHUB_API_URL,
                headers={"User-Agent": "AutoKVTM-Updater"}
            )
            with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
                data = json.loads(response.read().decode("utf-8"))

            latest_tag = data.get("tag_name", "").strip()
            # Bỏ ký tự 'v' ở đầu phiên bản nếu có (ví dụ 'v1.0.1' -> '1.0.1')
            latest_version = latest_tag[1:] if latest_tag.lower().startswith('v') else latest_tag
            changelog = data.get("body") or "Không có thông tin thay đổi."
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
                    self._download_update(download_url, latest_version, changelog)
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
                
                import ssl
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE

                # Kiểm tra & thử tải qua Mirror Proxy trước
                urls_to_try = [download_url]
                if "github.com" in download_url:
                    proxy_url = f"https://mirror.ghproxy.com/{download_url}"
                    urls_to_try.insert(0, proxy_url)
                    logger.info(f"[UPDATER] Thử tải qua Mirror Proxy: {proxy_url}")
                else:
                    logger.info(f"[UPDATER] Tải trực tiếp: {download_url}")

                response = None
                for idx, url in enumerate(urls_to_try):
                    try:
                        # Timeout cho proxy là 12s để chuyển nhanh sang link gốc nếu lỗi
                        timeout = 12 if idx == 0 and len(urls_to_try) > 1 else 30
                        req = urllib.request.Request(
                            url,
                            headers={"User-Agent": "AutoKVTM-Updater"}
                        )
                        response = urllib.request.urlopen(req, timeout=timeout, context=ctx)
                        logger.info(f"[UPDATER] Kết nối thành công tới: {url}")
                        break
                    except Exception as conn_err:
                        logger.warning(f"[UPDATER] Kết nối thất bại tới {url}: {conn_err}")
                        if idx == len(urls_to_try) - 1:
                            raise conn_err

                if response is None:
                    raise RuntimeError("Không thể kết nối đến máy chủ tải xuống!")

                with response, open(new_exe_path, 'wb') as out_file:
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

        # Kích hoạt luồng tải về ngầm
        threading.Thread(target=_download_thread, daemon=True).start()

    def _apply_update_windows(self, current_exe, new_exe_path):
        try:
            dir_name = os.path.dirname(current_exe)
            current_exe_name = os.path.basename(current_exe)
            new_exe_name = os.path.basename(new_exe_path)
            bat_path = os.path.join(dir_name, "updater.bat")
            
            # Script batch để đợi ứng dụng chính đóng hẳn, xoá exe cũ, đổi tên file mới và chạy lại
            bat_content = f"""@echo off
set _MEIPASS=
set _MEIPASS2=
set PYINSTALLER_PARENT_PID=
set PYINSTALLER_STRICT_UNPACK_MODE=
set _PYI_SPLASH_IPC=
set PYTHONHOME=
set PYTHONPATH=
timeout /t 1 /nobreak >nul
:loop
taskkill /f /im "{current_exe_name}" >nul 2>&1
timeout /t 1 /nobreak >nul
del /f /q "{current_exe}" >nul 2>&1
if exist "{current_exe}" (
    timeout /t 1 /nobreak >nul
    goto loop
)
move /y "{new_exe_name}" "{current_exe_name}" >nul 2>&1
start "" "{current_exe_name}"
timeout /t 1 /nobreak >nul
del "%~f0"
"""
            # Ghi file script bat
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write(bat_content)
                
            # Tạo bản sao môi trường sạch, loại bỏ các biến PyInstaller
            clean_env = os.environ.copy()
            for key in ["_MEIPASS", "_MEIPASS2", "PYINSTALLER_PARENT_PID", "PYINSTALLER_STRICT_UNPACK_MODE", "_PYI_SPLASH_IPC", "PYTHONHOME", "PYTHONPATH"]:
                clean_env.pop(key, None)

            # Flags để tiến trình bat hoàn toàn tách rời khỏi process cha
            flags = 0
            if hasattr(subprocess, 'CREATE_NEW_PROCESS_GROUP'):
                flags |= subprocess.CREATE_NEW_PROCESS_GROUP
            if hasattr(subprocess, 'DETACHED_PROCESS'):
                flags |= subprocess.DETACHED_PROCESS

            # Khởi chạy file bat ngầm hoàn toàn độc lập
            subprocess.Popen(["cmd.exe", "/c", bat_path], cwd=dir_name, env=clean_env, creationflags=flags)
            
            # Đóng ngay ứng dụng chính để script bat hoạt động
            sys.exit(0)
        except Exception as e:
            logger.error(f"Lỗi khởi động updater.bat: {e}")
            messagebox.showerror(
                "Lỗi cập nhật",
                f"Không thể áp dụng bản cập nhật tự động:\n{e}"
            )

    # ----------------------------------------------------------------
    # TAB: SO SÁNH ẢNH (MATCH TEST)
    # ----------------------------------------------------------------
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
    # TAB: CORE IMAGES
    # ----------------------------------------------------------------
    def _build_tab_core_images(self):
        self.core_images = [
            {
                "id": "core_nut_x",
                "name": "Nút X đóng bảng",
                "path": "assets/items/core_nut_x.png",
                "desc": "Nút đóng (X) các bảng giao diện hoặc popup trong game."
            },
            {
                "id": "core_back",
                "name": "Nút Quay lại (Back)",
                "path": "assets/items/core_back.png",
                "desc": "Nút quay lại (mũi tên) trong các giao diện (như Giao Cú)."
            },
            {
                "id": "core_thu_hoach",
                "name": "Giỏ thu hoạch",
                "path": "assets/items/core_thu_hoach.png",
                "desc": "Biểu tượng giỏ thu hoạch kéo vào cây để thu hoạch nông sản."
            },
            {
                "id": "core_thu_hoach_1",
                "name": "Giỏ thu hoạch 1",
                "path": "assets/items/core_thu_hoach_1.png",
                "desc": "Biểu tượng giỏ thu hoạch phụ."
            },
            {
                "id": "core_next_gieo",
                "name": "Mũi tên gieo tiếp",
                "path": "assets/items/core_next_gieo.png",
                "desc": "Mũi tên để chuyển trang danh sách hạt giống."
            },
            {
                "id": "core_cay_chua_chin",
                "name": "Cây chưa chín",
                "path": "assets/items/core_cay_chua_chin.png",
                "desc": "Dùng để nhận diện cây trồng chưa chín."
            },
            {
                "id": "core_tom",
                "name": "Biểu tượng Tôm",
                "path": "assets/items/core_tom.png",
                "desc": "Biểu tượng chú Tôm bán dạo/giao hàng."
            },
            {
                "id": "core_tim_hang",
                "name": "Tôm - Tìm hàng",
                "path": "assets/items/core_tim_hang.png",
                "desc": "Nút 'Tìm hàng' trong bảng giao dịch của Tôm."
            },
            {
                "id": "core_tom_thay_hang",
                "name": "Tôm - Thay hàng",
                "path": "assets/items/core_tom_thay_hang.png",
                "desc": "Nút 'Thay hàng' trong bảng giao dịch của Tôm."
            },
            {
                "id": "core_quay_items_tom",
                "name": "Tôm - Quay vật phẩm",
                "path": "assets/items/core_quay_items_tom.png",
                "desc": "Nút quay hoặc nhận vật phẩm từ Tôm."
            },
            {
                "id": "core_not_buy_tom",
                "name": "Tôm - Không mua",
                "path": "assets/items/core_not_buy_tom.png",
                "desc": "Nút từ chối mua hoặc đóng bảng Tôm."
            },
            {
                "id": "core_day_di_ma",
                "name": "Đẩy Tôm đi",
                "path": "assets/items/core_day_di_ma.png",
                "desc": "Nút từ chối giao dịch và đuổi Tôm đi chỗ khác."
            },
            {
                "id": "core_giao_cu_co_don",
                "name": "Giao Cú - Đơn sẵn sàng",
                "path": "assets/items/core_giao_cu_co_don.png",
                "desc": "Biểu tượng đơn hàng có thể giao trong bảng Giao Cú."
            },
            {
                "id": "core_giao_cu_giao_don",
                "name": "Giao Cú - Nút giao đơn",
                "path": "assets/items/core_giao_cu_giao_don.png",
                "desc": "Nút 'Giao Đơn' để tiến hành giao hàng."
            },
            {
                "id": "core_giao_cu_don_hang_off",
                "name": "Giao Cú - Đơn chưa sẵn sàng",
                "path": "assets/items/core_giao_cu_don_hang_off.png",
                "desc": "Đơn hàng Giao Cú thiếu nguyên liệu."
            },
            {
                "id": "core_chest",
                "name": "Mở rương - Rương gỗ",
                "path": "assets/items/core_chest.png",
                "desc": "Biểu tượng rương gỗ hoặc vị trí rương."
            },
            {
                "id": "core_ruong_go",
                "name": "Mở rương - Rương gỗ phụ",
                "path": "assets/items/core_ruong_go.png",
                "desc": "Biểu tượng rương gỗ loại khác."
            },
            {
                "id": "core_open_chest",
                "name": "Mở rương - Nút mở",
                "path": "assets/items/core_open_chest.png",
                "desc": "Nút bấm để mở rương nhận thưởng."
            },
            {
                "id": "core_cham_de_mo_ruong",
                "name": "Chạm để mở rương",
                "path": "assets/items/core_cham_de_mo_ruong.png",
                "desc": "Yêu cầu chạm màn hình để mở rương."
            },
            {
                "id": "core_full_kho",
                "name": "Thông báo đầy kho",
                "path": "assets/items/core_full_kho.png",
                "desc": "Thông báo kho đã bị đầy khi thu hoạch hoặc mở rương."
            },
            {
                "id": "core_quay_hang_on",
                "name": "Quầy hàng đang mở",
                "path": "assets/items/core_quay_hang_on.png",
                "desc": "Nhận diện đang ở giao diện quầy hàng bán lẻ."
            },
            {
                "id": "core_o_trong",
                "name": "Ô bán hàng trống",
                "path": "assets/items/core_o_trong.png",
                "desc": "Ô trống trong quầy hàng để đặt sản phẩm mới lên bán."
            },
            {
                "id": "core_vang3",
                "name": "Đồng tiền vàng",
                "path": "assets/items/core_vang3.png",
                "desc": "Đồng vàng hiển thị giá tiền của ô vật phẩm đang bán."
            },
            {
                "id": "core_dat_quang_cao",
                "name": "Nút Đặt quảng cáo",
                "path": "assets/items/core_dat_quang_cao.png",
                "desc": "Nút tick để đưa vật phẩm lên trang quảng cáo toàn game."
            },
            {
                "id": "core_xoa_vp_kc",
                "name": "Xóa vật phẩm (KC)",
                "path": "assets/items/core_xoa_vp_kc.png",
                "desc": "Nút xóa vật phẩm bày bán bằng kim cương."
            },
            {
                "id": "core_dong_y",
                "name": "Nút Đồng ý",
                "path": "assets/items/core_dong_y.png",
                "desc": "Nút xác nhận Đồng Ý trong một số hộp thoại popup."
            },
            {
                "id": "core_kho_thanh_pham",
                "name": "Kho Thành Phẩm (chọn)",
                "path": "assets/items/core_kho_thanh_pham.png",
                "desc": "Biểu tượng tab Kho Thành Phẩm khi được chọn."
            },
            {
                "id": "core_kho_thanh_pham_0",
                "name": "Kho Thành Phẩm (chưa)",
                "path": "assets/items/core_kho_thanh_pham_0.png",
                "desc": "Biểu tượng tab Kho Thành Phẩm khi chưa chọn."
            },
            {
                "id": "core_kho_nong_san",
                "name": "Kho Nông Sản",
                "path": "assets/items/core_kho_nong_san.png",
                "desc": "Biểu tượng tab Kho Nông Sản."
            },
            {
                "id": "core_kho_event",
                "name": "Kho Sự Kiện (chọn)",
                "path": "assets/items/core_kho_event.png",
                "desc": "Biểu tượng tab Kho Sự Kiện khi được chọn."
            },
            {
                "id": "core_kho_event_0",
                "name": "Kho Sự Kiện (chưa)",
                "path": "assets/items/core_kho_event_0.png",
                "desc": "Biểu tượng tab Kho Sự Kiện khi chưa chọn."
            },
            {
                "id": "core_kho_vat_dung",
                "name": "Kho Vật Dụng",
                "path": "assets/items/core_kho_vat_dung.png",
                "desc": "Biểu tượng tab Kho Vật Dụng."
            },
            {
                "id": "core_sanxuat_vp",
                "name": "Nút sản xuất máy",
                "path": "assets/items/core_sanxuat_vp.png",
                "desc": "Ô kéo nguyên liệu vào để sản xuất trong máy."
            },
            {
                "id": "core_next_sanxuat",
                "name": "Sản xuất tiếp theo",
                "path": "assets/items/core_next_sanxuat.png",
                "desc": "Mũi tên chuyển trang sản phẩm sản xuất."
            },
            {
                "id": "core_sua_may",
                "name": "Biểu tượng sửa máy",
                "path": "assets/items/core_sua_may.png",
                "desc": "Biểu tượng clay/sửa máy khi máy sản xuất bị hỏng."
            },
            {
                "id": "core_sua_may_vang",
                "name": "Biểu tượng sửa máy vàng",
                "path": "assets/items/core_sua_may_vang.png",
                "desc": "Biểu tượng sửa máy màu vàng nổi bật hơn."
            },
            {
                "id": "core_sxcam_soi",
                "name": "Sản xuất Cam - Soi cam",
                "path": "assets/items/core_sxcam_soi.png",
                "desc": "Nút/Vùng Soi trong tính năng sản xuất cam."
            },
            {
                "id": "core_sxcam_log",
                "name": "Sản xuất Cam - Log",
                "path": "assets/items/core_sxcam_log.png",
                "desc": "Nhật ký sản xuất cam."
            },
            {
                "id": "core_sxcam_sx",
                "name": "Sản xuất Cam - Nút SX",
                "path": "assets/items/core_sxcam_sx.png",
                "desc": "Nút Sản xuất trong nhà máy cam."
            },
            {
                "id": "core_sxcam_luami",
                "name": "Sản xuất Cam - Lúa mì",
                "path": "assets/items/core_sxcam_luami.png",
                "desc": "Lúa mì dùng để sản xuất cam."
            },
            {
                "id": "core_sxcam_venha",
                "name": "Sản xuất Cam - Về nhà",
                "path": "assets/items/core_sxcam_venha.png",
                "desc": "Nút quay trở về nhà vườn từ máy cam."
            },
            {
                "id": "core_icon_game",
                "name": "Icon Game",
                "path": "assets/items/core_icon_game.png",
                "desc": "Biểu tượng game trên màn hình giả lập."
            },
            {
                "id": "core_tai_khoan",
                "name": "Tài khoản (Avatar)",
                "path": "assets/items/core_tai_khoan.png",
                "desc": "Ảnh đại diện/Tài khoản game."
            },
            {
                "id": "core_tai_khoan_on",
                "name": "Tài khoản hoạt động",
                "path": "assets/items/core_tai_khoan_on.png",
                "desc": "Tài khoản game đang hoạt động."
            },
            {
                "id": "core_ban_be",
                "name": "Bạn Bè",
                "path": "assets/items/core_ban_be.png",
                "desc": "Nút mở danh sách Bạn Bè."
            },
            {
                "id": "core_quay_ve",
                "name": "Quay về nhà",
                "path": "assets/items/core_quay_ve.png",
                "desc": "Nút quay trở về nhà từ nhà bạn bè."
            }
        ]

        pad = tk.Frame(self.tab_core_images, bg="#ecf0f1", padx=15, pady=15)
        pad.pack(fill=tk.BOTH, expand=True)

        title_lbl = tk.Label(
            pad, 
            text="DANH SÁCH HÌNH ẢNH CORE HỆ THỐNG", 
            font=("Arial", 11, "bold"), 
            bg="#ecf0f1", 
            fg="#2c3e50"
        )
        title_lbl.pack(anchor=tk.W, pady=(0, 10))

        paned = tk.PanedWindow(pad, orient=tk.HORIZONTAL, bg="#ecf0f1", bd=0, sashwidth=4)
        paned.pack(fill=tk.BOTH, expand=True)

        left_frame = tk.Frame(paned, bg="#ecf0f1")
        paned.add(left_frame, minsize=400)

        cols = ("name", "path", "status")
        self.img_tree = ttk.Treeview(left_frame, columns=cols, show="headings")
        self.img_tree.heading("name", text="Tên ảnh")
        self.img_tree.heading("path", text="Đường dẫn")
        self.img_tree.heading("status", text="Trạng thái")

        self.img_tree.column("name", width=150, anchor=tk.W)
        self.img_tree.column("path", width=180, anchor=tk.W)
        self.img_tree.column("status", width=70, anchor=tk.CENTER)

        tree_scroll = tk.Scrollbar(left_frame, command=self.img_tree.yview)
        self.img_tree.config(yscrollcommand=tree_scroll.set)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.img_tree.pack(fill=tk.BOTH, expand=True)

        right_frame = tk.Frame(paned, bg="#ffffff", bd=1, relief=tk.GROOVE, padx=12, pady=12)
        paned.add(right_frame, minsize=350)

        self.detail_title = tk.Label(right_frame, text="Chọn một ảnh để xem chi tiết", font=("Arial", 10, "bold"), bg="#ffffff", fg="#2c3e50")
        self.detail_title.pack(anchor=tk.W, pady=(0, 5))

        self.detail_path = tk.Label(right_frame, text="", font=("Consolas", 9), bg="#ffffff", fg="#7f8c8d", wraplength=320, justify=tk.LEFT)
        self.detail_path.pack(anchor=tk.W, pady=(0, 10))

        preview_container = tk.Frame(right_frame, bg="#f5f6fa", bd=1, relief=tk.SUNKEN, width=150, height=150)
        preview_container.pack_propagate(False)
        preview_container.pack(pady=10)

        self.preview_lbl = tk.Label(preview_container, text="Không có xem trước", bg="#f5f6fa", fg="#7f8c8d")
        self.preview_lbl.pack(fill=tk.BOTH, expand=True)

        self.detail_desc = tk.Label(right_frame, text="", font=("Arial", 9), bg="#ffffff", fg="#2c3e50", wraplength=320, justify=tk.LEFT)
        self.detail_desc.pack(anchor=tk.W, pady=(10, 10))

        self.detail_size = tk.Label(right_frame, text="", font=("Arial", 9, "italic"), bg="#ffffff", fg="#7f8c8d")
        self.detail_size.pack(anchor=tk.W, pady=(0, 15))

        btn_container = tk.Frame(right_frame, bg="#ffffff")
        btn_container.pack(fill=tk.X, side=tk.BOTTOM, pady=5)

        self.btn_replace = tk.Button(
            btn_container, 
            text="Thay thế ảnh", 
            command=self._replace_core_image,
            bg="#2ecc71", 
            fg="white", 
            font=("Arial", 9, "bold"),
            relief=tk.FLAT, 
            cursor="hand2", 
            state=tk.DISABLED
        )
        self.btn_replace.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        self.btn_open_folder = tk.Button(
            btn_container, 
            text="Mở thư mục", 
            command=self._open_core_image_folder,
            bg="#3498db", 
            fg="white", 
            font=("Arial", 9),
            relief=tk.FLAT, 
            cursor="hand2",
            state=tk.DISABLED
        )
        self.btn_open_folder.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        self.btn_restore = tk.Button(
            btn_container,
            text="Khôi phục gốc",
            command=self._restore_core_image_backup,
            bg="#e74c3c",
            fg="white",
            font=("Arial", 9),
            relief=tk.FLAT,
            cursor="hand2",
            state=tk.DISABLED
        )
        self.btn_restore.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        self.img_tree.bind("<<TreeviewSelect>>", self._on_core_image_select)
        self._current_tk_img = None
        self._refresh_core_images_list()

    def _get_resource_path(self, path):
        if not path:
            return path
        if os.path.exists(path):
            return path
        import sys
        if getattr(sys, 'frozen', False):
            base_dir = getattr(sys, '_MEIPASS', os.path.abspath('.'))
            bundled_path = os.path.join(base_dir, path)
            if os.path.exists(bundled_path):
                return bundled_path
        return path

    def _get_image_status(self, path):
        import sys
        is_frozen = getattr(sys, 'frozen', False)
        if is_frozen:
            # Check external override
            if os.path.exists(path):
                return "Đã đổi"
            # Check PyInstaller bundle
            base_dir = getattr(sys, '_MEIPASS', os.path.abspath('.'))
            bundled_path = os.path.join(base_dir, path)
            if os.path.exists(bundled_path):
                return "Mặc định"
            return "Thiếu"
        else:
            # Running from source
            if os.path.exists(path):
                if os.path.exists(path + ".bak"):
                    return "Đã đổi"
                return "Mặc định"
            return "Thiếu"

    def _refresh_core_images_list(self):
        for item in self.img_tree.get_children():
            self.img_tree.delete(item)

        for img in self.core_images:
            path = img["path"]
            status = self._get_image_status(path)
            self.img_tree.insert("", tk.END, iid=img["id"], values=(img["name"], path, status))

    def _on_core_image_select(self, event):
        selected = self.img_tree.selection()
        if not selected:
            self.detail_title.config(text="Chọn một ảnh để xem chi tiết")
            self.detail_path.config(text="")
            self.detail_desc.config(text="")
            self.detail_size.config(text="")
            self.preview_lbl.config(image="", text="Không có xem trước")
            self._current_tk_img = None
            self.btn_replace.config(state=tk.DISABLED)
            self.btn_open_folder.config(state=tk.DISABLED)
            self.btn_restore.config(state=tk.DISABLED)
            return

        img_id = selected[0]
        img_info = next((img for img in self.core_images if img["id"] == img_id), None)
        if not img_info:
            return

        self.detail_title.config(text=img_info["name"])
        self.detail_path.config(text=img_info["path"])
        self.detail_desc.config(text=img_info["desc"])
        
        path = img_info["path"]
        status = self._get_image_status(path)
        exists = (status != "Thiếu")

        self.btn_replace.config(state=tk.NORMAL)
        self.btn_open_folder.config(state=tk.NORMAL)

        bak_path = path + ".bak"
        if os.path.exists(bak_path):
            self.btn_restore.config(state=tk.NORMAL)
        else:
            self.btn_restore.config(state=tk.DISABLED)

        if exists:
            try:
                from PIL import Image, ImageTk
                resolved_path = self._get_resource_path(path)
                pil_img = Image.open(resolved_path)
                w, h = pil_img.size
                self.detail_size.config(text=f"Kích thước gốc: {w}x{h} px")

                max_size = 140
                ratio = min(max_size / w, max_size / h)
                new_w = int(w * ratio)
                new_h = int(h * ratio)
                if new_w < 1: new_w = 1
                if new_h < 1: new_h = 1

                scaled_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.ANTIALIAS)
                
                tk_img = ImageTk.PhotoImage(scaled_img)
                self.preview_lbl.config(image=tk_img, text="")
                self._current_tk_img = tk_img
            except Exception as e:
                self.preview_lbl.config(image="", text="Lỗi hiển thị ảnh")
                self.detail_size.config(text=f"Lỗi: {e}")
                self._current_tk_img = None
        else:
            self.preview_lbl.config(image="", text="Tệp không tồn tại")
            self.detail_size.config(text="Không tìm thấy tệp tin")
            self._current_tk_img = None

    def _replace_core_image(self):
        selected = self.img_tree.selection()
        if not selected:
            return
        img_id = selected[0]
        img_info = next((img for img in self.core_images if img["id"] == img_id), None)
        if not img_info:
            return

        dest_path = img_info["path"]
        
        file_path = filedialog.askopenfilename(
            title=f"Chọn ảnh thay thế cho '{img_info['name']}'",
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg"), ("All Files", "*.*")]
        )
        if not file_path:
            return

        try:
            from PIL import Image
            src_img = Image.open(file_path)
            
            dest_dir = os.path.dirname(dest_path)
            if dest_dir:
                os.makedirs(dest_dir, exist_ok=True)

            if os.path.exists(dest_path):
                bak_path = dest_path + ".bak"
                if not os.path.exists(bak_path):
                    shutil.copy2(dest_path, bak_path)

            src_img.save(dest_path, "PNG")
            
            messagebox.showinfo("Thành công", f"Đã thay thế hình ảnh '{img_info['name']}' thành công!")
            
            self._refresh_core_images_list()
            self.img_tree.selection_set(img_id)
            self._on_core_image_select(None)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể thay thế hình ảnh:\n{e}")

    def _open_core_image_folder(self):
        selected = self.img_tree.selection()
        if not selected:
            return
        img_id = selected[0]
        img_info = next((img for img in self.core_images if img["id"] == img_id), None)
        if not img_info:
            return

        path = os.path.abspath(img_info["path"])
        dir_path = os.path.dirname(path)
        if os.path.exists(dir_path):
            try:
                subprocess.Popen(f'explorer /select,"{path}"')
            except Exception:
                try:
                    os.startfile(dir_path)
                except Exception as e:
                    messagebox.showerror("Lỗi", f"Không thể mở thư mục:\n{e}")

    def _restore_core_image_backup(self):
        selected = self.img_tree.selection()
        if not selected:
            return
        img_id = selected[0]
        img_info = next((img for img in self.core_images if img["id"] == img_id), None)
        if not img_info:
            return

        path = img_info["path"]
        bak_path = path + ".bak"
        if not os.path.exists(bak_path):
            messagebox.showwarning("Cảnh báo", "Không tìm thấy bản sao lưu gốc (.bak) cho ảnh này.")
            return

        if not messagebox.askyesno("Khôi phục", f"Bạn có muốn khôi phục hình ảnh gốc cho '{img_info['name']}'?"):
            return

        try:
            shutil.copy2(bak_path, path)
            os.remove(bak_path)
            
            messagebox.showinfo("Thành công", f"Đã khôi phục hình ảnh '{img_info['name']}' về ban đầu!")
            
            self._refresh_core_images_list()
            self.img_tree.selection_set(img_id)
            self._on_core_image_select(None)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể khôi phục ảnh sao lưu:\n{e}")


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
