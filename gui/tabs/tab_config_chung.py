import os
import sys
import json
import logging
import threading
import urllib.request
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import config
from gui.constants import CONFIG_DIR, BASE_DIR, SELECTED_DEVICE_FILE
from gui.widgets import TreeTooltip

logger = logging.getLogger(__name__)


class ConfigChungTabMixin:
    """Tab 3: Cấu hình chung cho toàn bộ hệ thống (Gemini, YOLO, Delays, LDPlayer)."""
    def _build_tab_config_chung(self):
        """Tạo giao diện cho tab Cấu Hình Chung."""
        import config
        # Container
        pad = tk.Frame(self.tab_config_chung, bg="#ecf0f1", padx=15, pady=15)
        pad.pack(fill=tk.BOTH, expand=True)

        title = tk.Label(pad, text="CẤU HÌNH CHUNG TOÀN CỤC (Áp dụng cho mọi cấu hình và thiết bị)", 
                         font=("Arial", 11, "bold"), bg="#ecf0f1", fg="#2c3e50")
        title.pack(anchor=tk.W, pady=(0, 12))

        # 0. Cấu hình Giả lập LDPlayer & ADB
        ld_frame = tk.LabelFrame(pad, text="Cấu hình Giả lập LDPlayer & ADB", font=("Arial", 10, "bold"),
                                  bg="#ecf0f1", fg="#2c3e50", padx=15, pady=10)
        ld_frame.pack(fill=tk.X, pady=(0, 8))

        row_ld = tk.Frame(ld_frame, bg="#ecf0f1")
        row_ld.pack(fill=tk.X, pady=2)
        tk.Label(row_ld, text="Thư mục LDPlayer:", bg="#ecf0f1", width=20, anchor=tk.W, font=("Arial", 9, "bold")).pack(side=tk.LEFT)

        initial_ld_dir = ""
        adb_p = getattr(self.adb_helper, "adb_path", None) if hasattr(self, "adb_helper") and self.adb_helper else None
        if adb_p and isinstance(adb_p, str) and os.path.isfile(adb_p):
            initial_ld_dir = os.path.dirname(adb_p)
        elif os.path.exists(SELECTED_DEVICE_FILE):
            try:
                with open(SELECTED_DEVICE_FILE, "r", encoding="utf-8") as f:
                    s_data = json.load(f) or {}
                    initial_ld_dir = s_data.get("ldplayer_dir") or (os.path.dirname(s_data.get("adb_path")) if s_data.get("adb_path") else "")
            except Exception:
                pass

        self.ldplayer_dir_var = tk.StringVar(value=initial_ld_dir)
        self.ldplayer_dir_entry = tk.Entry(row_ld, textvariable=self.ldplayer_dir_var, font=("Arial", 9))
        self.ldplayer_dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        tk.Button(row_ld, text="📁 Chọn thư mục...", command=self._choose_ldplayer_folder_chung,
                  bg="#3498db", fg="white", font=("Arial", 9, "bold"),
                  relief=tk.FLAT, cursor="hand2", padx=10, pady=2).pack(side=tk.LEFT, padx=(0, 6))

        tk.Button(row_ld, text="🔄 Nhận diện lại", command=self._detect_ldplayer_again,
                  bg="#27ae60", fg="white", font=("Arial", 9, "bold"),
                  relief=tk.FLAT, cursor="hand2", padx=10, pady=2).pack(side=tk.LEFT)

        row_ld_status = tk.Frame(ld_frame, bg="#ecf0f1")
        row_ld_status.pack(fill=tk.X, pady=(4, 0))
        tk.Label(row_ld_status, text="Trạng thái kết nối:", bg="#ecf0f1", width=20, anchor=tk.W, font=("Arial", 9)).pack(side=tk.LEFT)

        self.lbl_ld_status = tk.Label(row_ld_status, text="", bg="#ecf0f1", font=("Arial", 9, "bold"))
        self.lbl_ld_status.pack(side=tk.LEFT)

        self._update_ldplayer_status_display()

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
                             width=2, relief=tk.FLAT, cursor="hand2")
        help_btn.pack(side=tk.LEFT, padx=2)
        help_tooltip = TreeTooltip(help_btn)
        help_btn.bind("<Enter>", lambda e: help_tooltip.show("Hướng dẫn tạo API Key", e.x_root, e.y_root))
        help_btn.bind("<Leave>", lambda e: help_tooltip.hide())

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

    def _update_ldplayer_status_display(self):
        """Cập nhật nhãn trạng thái kết nối ADB/LDPlayer trên giao diện Cấu hình chung."""
        if not hasattr(self, 'lbl_ld_status') or not self.lbl_ld_status.winfo_exists():
            return
        cur_dir = self.ldplayer_dir_var.get().strip() if hasattr(self, 'ldplayer_dir_var') else ""
        adb_p = getattr(self.adb_helper, 'adb_path', None)

        if adb_p and os.path.isfile(adb_p):
            self.lbl_ld_status.config(text=f"✅ Đã kết nối ADB ({adb_p})", fg="#27ae60")
        elif cur_dir and os.path.isfile(os.path.join(cur_dir, "adb.exe")):
            self.lbl_ld_status.config(text=f"✅ Tìm thấy adb.exe trong {cur_dir}", fg="#27ae60")
        else:
            self.lbl_ld_status.config(text="❌ Chưa tìm thấy file adb.exe (Vui lòng chọn thư mục cài đặt gốc của LDPlayer)", fg="#e74c3c")

    def _choose_ldplayer_folder_chung(self):
        """Mở hộp thoại chọn thư mục LDPlayer từ tab Cấu hình chung."""
        if self._choose_adb_path():
            if hasattr(self.adb_helper, 'adb_path') and self.adb_helper.adb_path:
                self.ldplayer_dir_var.set(os.path.dirname(self.adb_helper.adb_path))
            self._update_ldplayer_status_display()
            self._refresh_devices()

    def _detect_ldplayer_again(self):
        """Thử quét tự động lại LDPlayer từ hệ thống."""
        found_adb = None
        if hasattr(self.adb_helper, 'find_adb'):
            found_adb = self.adb_helper.find_adb()
        if found_adb and os.path.isfile(found_adb):
            self.adb_helper.adb_path = found_adb
            ld_dir = os.path.dirname(found_adb)
            self._save_adb_path(ld_dir)
            self.ldplayer_dir_var.set(ld_dir)
            self._update_ldplayer_status_display()
            self._refresh_devices()
            messagebox.showinfo("Thành công", f"Đã nhận diện thành công LDPlayer:\n{found_adb}", parent=self.root)
        else:
            self._update_ldplayer_status_display()
            messagebox.showwarning(
                "Không tìm thấy tự động",
                "Không tự động tìm thấy LDPlayer trong các đường dẫn mặc định.\n\n"
                "Vui lòng nhấn nút 'Chọn thư mục...' để chỉ định thư mục cài đặt LDPlayer của bạn.",
                parent=self.root
            )

    # ----------------------------------------------------------------
