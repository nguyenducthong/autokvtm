"""
GUI Auto + Config - Hệ Thống Quản Lý & Tự Động Hóa Nông Trại
Phiên bản module hóa gọn gàng theo mô hình Mixin.
"""

import os
import sys
import json
import logging
import threading
import multiprocessing
import tkinter as tk
from tkinter import ttk

# Đảm bảo đường dẫn gốc chuẩn
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    if os.getcwd() != BASE_DIR:
        os.chdir(BASE_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import CURRENT_VERSION
from core.adb_helper import get_adb_helper

# Import các hằng số và hàm tiện ích dùng chung
from gui.constants import (
    CONFIG_DIR,
    SELECTED_DEVICE_FILE,
    ITEMS_DIR,
    DEFAULT_SETTINGS,
    DEFAULT_BAN_DO,
    GUI_LOG_MAX_LINES,
    scan_all_templates,
    scan_kho_templates,
    normalize_region,
    format_region,
    scan_row_templates,
)

# Import các widget
from gui.widgets import (
    SplashScreen,
    TreeTooltip,
    AutocompleteCombobox,
    DeviceButtonState,
)

# Import logging utilities
from gui.logging_utils import (
    DeviceNameFilter,
    DailySizeZipFileHandler,
)

# Import Updater Mixin
from gui.updater import UpdaterMixin

# Import 7 Tab Mixins
from gui.tabs import (
    AutoTabMixin,
    ConfigTabMixin,
    ConfigChungTabMixin,
    ScreenshotTabMixin,
    MatchTestTabMixin,
    CoreImagesTabMixin,
    LogTabMixin,
)

logger = logging.getLogger(__name__)


class AutoConfigGUI(
    AutoTabMixin,
    ConfigTabMixin,
    ConfigChungTabMixin,
    ScreenshotTabMixin,
    MatchTestTabMixin,
    CoreImagesTabMixin,
    LogTabMixin,
    UpdaterMixin,
):
    """Lớp giao diện chính Auto KVTM, kế thừa các Tab Mixin module hóa."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Auto KVTM - Auto & Config")
        w, h = 960, 800
        sx = self.root.winfo_screenwidth()
        sy = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sx - w) // 2}+{(sy - h) // 2}")
        self.root.resizable(True, True)
        self.root.withdraw()

        self.adb_helper = None
        self.adb = None
        self.is_running = False
        self.stop_event = threading.Event()

        # Hiện màn hình loading ngay khi bắt đầu
        self.splash = SplashScreen(self.root)

        # Lên lịch thực hiện chuỗi khởi động tuần tự
        self.root.after(40, self._startup_sequence)

    def _startup_sequence(self):
        try:
            # Bước 1: Khởi tạo thư mục và giao diện (20%)
            if self.splash:
                self.splash.update_progress(20, "Đang nạp cấu hình và khởi tạo giao diện...")
            os.makedirs(CONFIG_DIR, exist_ok=True)
            self._build_ui()
            self.root.update_idletasks()

            # Bước 2: Nạp ADB Helper (45%)
            if self.splash:
                self.splash.update_progress(45, "Đang kiểm tra kết nối công cụ ADB...")
            self.adb_helper = get_adb_helper()
            if hasattr(self, 'ldplayer_dir_var') and getattr(self.adb_helper, 'adb_path', None):
                self.ldplayer_dir_var.set(os.path.dirname(self.adb_helper.adb_path))
            if hasattr(self, '_update_ldplayer_status_display'):
                self._update_ldplayer_status_display()
            self.root.update_idletasks()

            # Bước 3: Tìm kiếm thiết bị giả lập LDPlayer (70%)
            if self.splash:
                self.splash.update_progress(70, "Đang tìm kiếm giả lập LDPlayer...")
            self._refresh_devices(silent=True)
            self._refresh_configs()
            self.root.update_idletasks()

            # Bước 4: Đồng bộ thiết bị & lên lịch làm mới (90%)
            if self.splash:
                self.splash.update_progress(90, "Đang đồng bộ thiết bị & giao diện...")
            self._ss_refresh_devices(silent=True)
            self._schedule_device_auto_refresh()
            self.root.update_idletasks()

            # Bước 5: Hoàn tất (100%)
            if self.splash:
                self.splash.update_progress(100, "Khởi động thành công! Đang mở ứng dụng...")
            self.root.update_idletasks()

            # Không tự động chạy cập nhật khi khởi động theo yêu cầu người dùng
            pass

        except Exception as e:
            logger.exception("Lỗi trong quá trình khởi động: %s", e)
        finally:
            self.root.after(250, self._finish_startup)

    def _finish_startup(self):
        try:
            if hasattr(self, "splash") and self.splash:
                self.splash.close()
                self.splash = None
        except Exception:
            pass
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

        # Kiểm tra sau khi khởi động: Nếu chưa có LDPlayer/ADB thì điều hướng sang tab Cấu hình chung
        self.root.after(300, self._check_adb_post_startup)

    def _check_adb_post_startup(self):
        """Kiểm tra đường dẫn ADB/LDPlayer sau khi giao diện chính đã mở hoàn tất (không làm treo ứng dụng)."""
        adb_path = getattr(self.adb_helper, 'adb_path', None)
        if not adb_path or not os.path.isfile(adb_path):
            self.status_label.config(
                text="⚠️ Chưa kết nối LDPlayer! Vui lòng chọn thư mục cài đặt LDPlayer trong tab 'Cấu hình chung'.",
                bg="#e67e22"
            )
            # Tự động chuyển người dùng sang tab Cấu hình chung để chọn thư mục trực quan
            if hasattr(self, 'notebook') and hasattr(self, 'tab_config_chung'):
                try:
                    self.notebook.select(self.tab_config_chung)
                except Exception:
                    pass

    # ================================================================
    # UI TỔNG THỂ
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

        # Dựng các tab từ Mixin tương ứng
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

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    multiprocessing.freeze_support()
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
