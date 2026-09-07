import os
import sys
import json
import time
import shutil
import logging
import threading
import subprocess
import glob as glob_mod
from datetime import date
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk

import config as global_config
from core.adb_helper import get_adb_helper, ADBHelper
from core.adb import ADBController
from core.trong_cay import main_tc, set_debug_mode as set_trong_cay_debug_mode
from core.ban_do import main_ban_hang, set_debug_mode as set_ban_do_debug_mode
from core.thu_hoach import set_debug_mode as set_thu_hoach_debug_mode
from core.san_xuat import set_debug_mode as set_san_xuat_debug_mode
from core.sxcam import can_sxcam, run_sxcam, set_debug_mode as set_sxcam_debug_mode
from core.mo_ruong import can_mo_ruong, da_day_kho, mo_ruong
from core.giao_cu import can_giao_cu, giao_cu
from core.giao_tom import giao_tom
from core.sang_nha_ban_be import can_sang_ban_be, sang_ban_be
from core.vao_game import vao_game
from utils.utils import setup_thread, set_debug_mode as set_utils_debug_mode
from utils.daily_stats import format_daily_counts, record_loop_run, get_today_stats_path
from gui.constants import (
    BASE_DIR, CONFIG_DIR, SELECTED_DEVICE_FILE, ITEMS_DIR,
    DEFAULT_SETTINGS, DEFAULT_BAN_DO, format_region
)
from gui.widgets import TreeTooltip, DeviceButtonState

logger = logging.getLogger(__name__)


class AutoTabMixin:
    """Tab 1: Quản lý thiết bị LDPlayer, cấu hình chạy và điều khiển tự động."""
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

        # Toolbar Row 1: Điều khiển Auto chính (trái) & Tóm tắt số lượng (phải)
        tb_row1 = tk.Frame(dev_frame, bg="#ecf0f1")
        tb_row1.pack(fill=tk.X, pady=(0, 4))

        tk.Button(tb_row1, text="Làm mới", command=self._refresh_devices,
                  bg="#2980b9", fg="white", relief=tk.FLAT, cursor="hand2",
                  width=10, pady=3, font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=(0, 4))
        tk.Button(tb_row1, text="Chạy tất cả", command=self._start_all,
                  bg="#27ae60", fg="white", relief=tk.FLAT, cursor="hand2",
                  width=11, pady=3, font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=3)
        tk.Button(tb_row1, text="Tạm dừng", command=self._pause_all,
                  bg="#f39c12", fg="white", relief=tk.FLAT, cursor="hand2",
                  width=10, pady=3, font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=3)
        tk.Button(tb_row1, text="Dừng tất cả", command=self._stop_all,
                  bg="#c0392b", fg="white", relief=tk.FLAT, cursor="hand2",
                  width=11, pady=3, font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=3)
        btn_csv = tk.Button(tb_row1, text="CSV Thống kê", command=self._open_daily_stats_csv,
                            bg="#1565c0", fg="white", relief=tk.FLAT, cursor="hand2",
                            width=12, pady=3, font=("Arial", 9, "bold"))
        btn_csv.pack(side=tk.LEFT, padx=3)
        btn_csv.bind("<Button-3>", lambda e: self._open_daily_stats_folder())

        self.lbl_device_summary = tk.Label(tb_row1, text="", bg="#ecf0f1", fg="#0c2461",
                                           font=("Arial", 9, "bold"))
        self.lbl_device_summary.pack(side=tk.RIGHT, padx=2)

        # Toolbar Row 2: Kho thành phẩm, Thư mục ảnh & Tùy chọn
        tb_row2 = tk.Frame(dev_frame, bg="#ecf0f1")
        tb_row2.pack(fill=tk.X, pady=(0, 6))

        tk.Button(tb_row2, text="Quét kho TP", command=self._scan_kho_thanh_pham_all,
                  bg="#8e44ad", fg="white", relief=tk.FLAT, cursor="hand2",
                  width=11, pady=3, font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=(0, 4))
        tk.Button(tb_row2, text="Tải CSV kho", command=self._download_kho_thanh_pham_csv,
                  bg="#16a085", fg="white", relief=tk.FLAT, cursor="hand2",
                  width=11, pady=3, font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=4)
        tk.Button(tb_row2, text="Thư mục ảnh", command=self._open_debug_folder,
                  bg="#d35400", fg="white", relief=tk.FLAT, cursor="hand2",
                  width=11, pady=3, font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=4)
        tk.Button(tb_row2, text="Xóa ảnh debug", command=self._clear_debug_folder,
                  bg="#c2185b", fg="white", relief=tk.FLAT, cursor="hand2",
                  width=12, pady=3, font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=4)

        self.debug_mode_var = tk.BooleanVar(value=False)
        tk.Checkbutton(tb_row2, text="Gỡ lỗi (lưu ảnh)", variable=self.debug_mode_var,
                       bg="#ecf0f1", font=("Arial", 8),
                       command=self._toggle_debug_mode).pack(side=tk.RIGHT, padx=(4, 0))
        self.use_gemini_kho_var = tk.BooleanVar(value=True)
        tk.Checkbutton(tb_row2, text="Gemini AI", variable=self.use_gemini_kho_var,
                       bg="#ecf0f1", font=("Arial", 8, "bold")).pack(side=tk.RIGHT, padx=(0, 6))

        # Giữ dummy action buttons tránh lỗi tham chiếu nếu có
        dummy_bar = tk.Frame(dev_frame)
        self.btn_selected_start_ld = tk.Button(dummy_bar)
        self.btn_selected_start = tk.Button(dummy_bar)
        self.btn_selected_stop = tk.Button(dummy_bar)

        # Device table
        self.device_table = tk.Frame(dev_frame, bg="#cfd8df", bd=1, relief=tk.SOLID)
        self.device_table.pack(fill=tk.BOTH, expand=True)
        self.device_table_tooltip = TreeTooltip(self.device_table)

        header = tk.Frame(self.device_table, bg="#e9eef2")
        header.pack(fill=tk.X)
        self.device_col_widths = (35, 120, 70, 395, 70, 70, 70, 70)
        self.device_col_weights = (0, 0, 0, 1, 0, 0, 0, 0)
        headers = [
            ("STT", tk.CENTER),
            ("Tên LD", tk.W),
            ("LD", tk.CENTER),
            ("Trạng thái tác vụ", tk.W),
            ("Mở", tk.CENTER),
            ("Chạy", tk.CENTER),
            ("Tạm dừng", tk.CENTER),
            ("Dừng", tk.CENTER),
        ]
        for col, (text, anchor) in enumerate(headers):
            lbl = tk.Label(header, text=text, bg="#e9eef2", fg="#2c3e50",
                           font=("Arial", 9, "bold"), anchor=anchor,
                           padx=2, pady=6, bd=0, relief=tk.FLAT)
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


    def _manual_choose_ldplayer(self):
        """Mở hộp thoại cho phép người dùng chọn thư mục LDPlayer thủ công."""
        if self._choose_adb_path():
            self._refresh_devices()

    def _choose_adb_path(self) -> bool:
        """Cho phép người dùng chọn thư mục LDPlayer chứa adb.exe với khả năng tự dò thư mục con."""
        adb_path = getattr(self.adb_helper, 'adb_path', None)
        initial_dir = os.path.dirname(adb_path) if isinstance(adb_path, str) and os.path.isdir(os.path.dirname(adb_path)) else None

        if not initial_dir and hasattr(self.adb_helper, '_find_from_registry'):
            reg_paths = self.adb_helper._find_from_registry()
            for rp in reg_paths:
                if os.path.isdir(rp):
                    initial_dir = rp
                    break

        if not initial_dir:
            for cand in ["E:\\LDPlayer\\LDPlayer9", "D:\\LDPlayer\\LDPlayer9", "C:\\LDPlayer\\LDPlayer9", "E:\\leidian\\LDPlayer9", "C:\\leidian\\LDPlayer9"]:
                if os.path.isdir(cand):
                    initial_dir = cand
                    break

        if not initial_dir:
            initial_dir = os.path.expanduser("~")

        selected_dir = filedialog.askdirectory(
            title="Chọn thư mục cài đặt LDPlayer (chứa file dnplayer.exe hoặc adb.exe)",
            initialdir=initial_dir,
            parent=self.root
        )
        if not selected_dir:
            return False

        # Kiểm tra trực tiếp adb.exe trong thư mục được chọn
        direct_adb = os.path.join(selected_dir, "adb.exe")
        resolved_adb = None
        resolved_dir = selected_dir

        if os.path.isfile(direct_adb):
            resolved_adb = direct_adb
        else:
            # Người dùng có thể chọn thư mục gốc (ví dụ E:\LDPlayer thay vì E:\LDPlayer\LDPlayer9)
            for sub in ("LDPlayer9", "leidian9", "LDPlayer4", "leidian4"):
                sub_path = os.path.join(selected_dir, sub, "adb.exe")
                if os.path.isfile(sub_path):
                    resolved_adb = sub_path
                    resolved_dir = os.path.dirname(sub_path)
                    break

            if not resolved_adb:
                # Quét nông tìm adb.exe trong các thư mục con cấp 1
                try:
                    for item in os.listdir(selected_dir):
                        item_path = os.path.join(selected_dir, item)
                        if os.path.isdir(item_path):
                            candidate = os.path.join(item_path, "adb.exe")
                            if os.path.isfile(candidate):
                                resolved_adb = candidate
                                resolved_dir = item_path
                                break
                except Exception:
                    pass

        if not resolved_adb:
            messagebox.showerror(
                "Lỗi chọn LDPlayer",
                "Không tìm thấy file adb.exe trong thư mục vừa chọn!\n\n"
                "Vui lòng chọn thư mục cài đặt thực tế của LDPlayer (ví dụ: E:\\LDPlayer\\LDPlayer9 hoặc C:\\LDPlayer\\LDPlayer9).",
                parent=self.root
            )
            return False

        self.adb_helper.adb_path = resolved_adb
        self.adb_helper.ldplayer_dir = resolved_dir
        self._save_adb_path(resolved_dir)

        if hasattr(self, 'ldplayer_dir_var'):
            self.ldplayer_dir_var.set(resolved_dir)
        if hasattr(self, '_update_ldplayer_status_display'):
            self._update_ldplayer_status_display()

        messagebox.showinfo(
            "Đã nhận diện LDPlayer",
            f"Đã thiết lập thư mục LDPlayer thành công:\n{resolved_dir}\n\nADB: {resolved_adb}",
            parent=self.root
        )
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


    def _schedule_device_auto_refresh(self):
        try:
            if not getattr(self, "_device_refresh_busy", False):
                self._refresh_devices(silent=True)
        finally:
            self.root.after(10000, self._schedule_device_auto_refresh)


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
            self.status_label.config(text="Lỗi: Không tìm thấy ADB / LDPlayer")
            if messagebox.askyesno(
                "Lỗi ADB / LDPlayer",
                "Không tìm thấy ADB hoặc giả lập LDPlayer!\n\nBạn có muốn chọn thư mục LDPlayer thủ công không?",
                parent=self.root
            ):
                if self._choose_adb_path():
                    self._refresh_devices()
                    return
            messagebox.showerror("Lỗi ADB", f"Không tìm thấy ADB hoặc thư mục LDPlayer!\n\n{e}", parent=self.root)
        except Exception as e:
            if silent:
                return
            self.status_label.config(text=f"Lỗi quét thiết bị: {e}")
            messagebox.showerror("Lỗi", f"Có lỗi xảy ra: {e}", parent=self.root)
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
            # Chỉ pack nếu hàng chưa được pack vào bảng (tránh giật/nháy giao diện)
            if not card["row"].winfo_ismapped():
                card["row"].pack(fill=tk.X)
            self._update_device_row(player["serial"])

        for serial, card in list(self.device_cards.items()):
            if serial not in seen_serials:
                try:
                    card["row"].destroy()
                except tk.TclError:
                    pass
                self.device_cards.pop(serial, None)

        self._update_device_summary_label()

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
        is_paused = bool(old_state.get("is_paused", False))
        if is_job_running:
            job_status = old_state.get("status", "Đang chạy")
            tag = old_state.get("tag", "working")
            start_state = tk.NORMAL if is_paused else tk.DISABLED
            pause_state = tk.DISABLED if is_paused else tk.NORMAL
            stop_state = tk.NORMAL
            ld_start_state = tk.DISABLED
        else:
            is_paused = False
            job_status = "Sẵn sàng" if running else "Chưa chạy"
            tag = "running" if running else "stopped"
            start_state = tk.NORMAL if running else tk.DISABLED
            pause_state = tk.DISABLED
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
            "pause_event": old_state.get("pause_event"),
            "is_paused": is_paused,
            "status": job_status,
            "tag": tag,
            "start_state": old_state.get("start_state", start_state) if is_job_running else start_state,
            "pause_state": old_state.get("pause_state", pause_state) if is_job_running else pause_state,
            "stop_state": old_state.get("stop_state", stop_state) if is_job_running else stop_state,
            "ld_start_state": old_state.get("ld_start_state", ld_start_state) if is_job_running else ld_start_state,
        }
        card["btn_start"] = DeviceButtonState(self, serial, "start_state")
        card["btn_pause"] = DeviceButtonState(self, serial, "pause_state")
        card["btn_stop"] = DeviceButtonState(self, serial, "stop_state")
        card["btn_ld_start"] = DeviceButtonState(self, serial, "ld_start_state")
        self.device_cards[serial] = card
        self._bind_device_row_actions(serial)
        self._update_device_row(serial)
        return card

    def _create_device_row_widgets(self, row, serial):
        anchors = (tk.CENTER, tk.W, tk.CENTER, tk.W, tk.CENTER, tk.CENTER, tk.CENTER, tk.CENTER)
        keys = ("index", "name", "ld_status", "job_status")
        widgets = {}

        for col, key in enumerate(keys):
            font = ("Arial", 8) if key == "name" else ("Arial", 9)
            lbl = tk.Label(row, bg="white", fg="#111111", font=font,
                           anchor=anchors[col], padx=4, pady=5,
                           bd=0, relief=tk.FLAT)
            lbl.grid(row=0, column=col, sticky="nsew", padx=(0, 1), pady=(0, 1))
            row.grid_columnconfigure(col, weight=self.device_col_weights[col],
                                     minsize=self.device_col_widths[col])
            widgets[key] = lbl

        button_specs = [
            ("btn_ld", 4, "⚡", "#2980b9", "Mở LDPlayer này"),
            ("btn_run", 5, "▶", "#27ae60", "Chạy / Tiếp tục auto cho LDPlayer này"),
            ("btn_pause", 6, "⏸", "#f39c12", "Tạm dừng auto cho LDPlayer này"),
            ("btn_stop", 7, "■", "#c0392b", "Dừng hẳn auto của LDPlayer này"),
        ]
        for key, col, text, color, tooltip in button_specs:
            btn = tk.Label(row, text=text, bg="white", fg="#bdc3c7",
                           font=("Segoe UI Symbol", 12, "bold"),
                           anchor=tk.CENTER, padx=0, pady=0, bd=0, relief=tk.FLAT)
            btn.grid(row=0, column=col, sticky="nsew", padx=(0, 1), pady=(0, 1))
            row.grid_columnconfigure(col, weight=self.device_col_weights[col],
                                     minsize=self.device_col_widths[col])
            btn.bind("<Enter>", lambda e, b=btn, s=serial, k=key: self._show_device_action_tooltip_dyn(e, b, s, k))
            btn.bind("<Leave>", lambda e, b=btn: self._hide_device_action_tooltip(b))
            widgets[key] = btn

        return widgets

    def _show_device_action_tooltip_dyn(self, event, button, serial, key):
        if button.cget("cursor") == "hand2" and button.cget("text"):
            card = self.device_cards.get(serial, {})
            if key == "btn_run":
                tip = "Tiếp tục auto cho LDPlayer này" if card.get("is_paused") else "Chạy auto cho LDPlayer này"
            elif key == "btn_pause":
                tip = "Tạm dừng auto cho LDPlayer này"
            elif key == "btn_stop":
                tip = "Dừng hẳn auto của LDPlayer này"
            elif key == "btn_ld":
                tip = "Mở LDPlayer này"
            else:
                tip = ""
            self.device_table_tooltip.show(tip, event.x_root, event.y_root)
        else:
            self.device_table_tooltip.hide()

    def _show_device_action_tooltip(self, event, button, text):
        if button.cget("cursor") == "hand2":
            self.device_table_tooltip.show(text, event.x_root, event.y_root)
        else:
            self.device_table_tooltip.hide()

    def _hide_device_action_tooltip(self, button):
        self.device_table_tooltip.hide()

    def _bind_device_row_actions(self, serial):
        card = self.device_cards.get(serial)
        if not card:
            return
        widgets = card.get("widgets", {})
        widgets["btn_ld"].bind("<Button-1>", lambda e, s=serial: self._start_row_ldplayer(s))
        widgets["btn_run"].bind("<Button-1>", lambda e, s=serial: self._start_row_device(s))
        widgets["btn_pause"].bind("<Button-1>", lambda e, s=serial: self._pause_row_device(s))
        widgets["btn_stop"].bind("<Button-1>", lambda e, s=serial: self._stop_row_device(s))

    def _start_row_ldplayer(self, serial):
        card = self.device_cards.get(serial)
        if card and card.get("ld_start_state") == tk.NORMAL:
            self._start_ldplayer(card.get("index"), serial)

    def _start_row_device(self, serial):
        card = self.device_cards.get(serial)
        if not card or card.get("start_state") != tk.NORMAL:
            return
        if card.get("is_paused"):
            self._resume_one(serial)
        else:
            self._start_one(serial)

    def _pause_row_device(self, serial):
        card = self.device_cards.get(serial)
        if card and card.get("pause_state") == tk.NORMAL:
            self._pause_one(serial)

    def _stop_row_device(self, serial):
        card = self.device_cards.get(serial)
        if card and card.get("stop_state") == tk.NORMAL:
            self._stop_one(serial)

    def _update_device_row(self, serial):
        card = self.device_cards.get(serial)
        if not card:
            return
        is_running = bool(card.get("running"))
        ld_status = "Đang chạy" if is_running else "Tắt"
        index_text = "" if card.get("index") is None else str(card.get("index"))
        row_bg = "#f8f9fa" if list(self.device_cards).index(serial) % 2 else "#ffffff"
        widgets = card.get("widgets", {})

        def _safe_config(w, **kwargs):
            if not w or not hasattr(w, "winfo_exists"):
                return
            try:
                if not w.winfo_exists():
                    return
            except Exception:
                return

            diff = {}
            for k, v in kwargs.items():
                try:
                    cur = w.cget(k)
                    if k == "font" and isinstance(v, (tuple, list)):
                        family = v[0]
                        size = str(v[1])
                        weight = v[2] if len(v) > 2 else ""
                        if family in cur and size in cur and (not weight or weight in cur):
                            continue
                    if cur != v:
                        diff[k] = v
                except Exception:
                    diff[k] = v
            if diff:
                try:
                    w.config(**diff)
                except Exception:
                    pass

        try:
            if card.get("row") and card["row"].winfo_exists():
                _safe_config(card["row"], bg=row_bg)
        except Exception:
            pass

        _safe_config(widgets.get("index"), text=index_text, bg=row_bg, fg="#57606f", font=("Arial", 9))
        _safe_config(widgets.get("name"), text=card.get("name", ""), bg=row_bg, fg="#2c3e50", font=("Arial", 8))
        
        ld_fg = "#27ae60" if is_running else "#95a5a6"
        ld_font = ("Arial", 8, "bold") if is_running else ("Arial", 8)
        _safe_config(widgets.get("ld_status"), text=ld_status, bg=row_bg, fg=ld_fg, font=ld_font)

        status_text = card.get("status", "")
        stats_text = format_daily_counts(serial)
        full_status = f"{status_text}\n{stats_text}"
        _safe_config(widgets.get("job_status"), text=full_status, bg=row_bg, fg="#2f3542", font=("Arial", 9), justify=tk.LEFT)

        action_state = [
            ("btn_ld", card.get("ld_start_state", tk.DISABLED), "⚡", "#2980b9"),
            ("btn_run", card.get("start_state", tk.DISABLED), "▶", "#27ae60"),
            ("btn_pause", card.get("pause_state", tk.DISABLED), "⏸", "#f39c12"),
            ("btn_stop", card.get("stop_state", tk.DISABLED), "■", "#c0392b"),
        ]
        for key, state, text, color in action_state:
            enabled = state == tk.NORMAL
            _safe_config(widgets.get(key),
                text=text if enabled else "",
                bg=row_bg,
                fg=color,
                cursor="hand2" if enabled else "",
            )

        self._update_device_summary_label()

    def _update_device_summary_label(self):
        if not hasattr(self, "lbl_device_summary") or not self.lbl_device_summary.winfo_exists():
            return
        total = len(self.device_cards)
        running = sum(1 for c in self.device_cards.values() if c.get("running"))
        auto_running = sum(1 for c in self.device_cards.values() if c.get("thread") and c.get("thread").is_alive() and not c.get("is_paused"))
        auto_paused = sum(1 for c in self.device_cards.values() if c.get("thread") and c.get("thread").is_alive() and c.get("is_paused"))

        parts = [f"Tổng: {total} LD"]
        if running > 0:
            parts.append(f"🟢 Mở: {running}")
        else:
            parts.append("Mở: 0")
        if auto_running > 0:
            parts.append(f"⚡ Auto: {auto_running}")
        if auto_paused > 0:
            parts.append(f"⏸ Tạm dừng: {auto_paused}")

        new_text = "   |   ".join(parts)
        if self.lbl_device_summary.cget("text") != new_text:
            self.lbl_device_summary.config(text=new_text)

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
        def _apply():
            card = self.device_cards.get(serial)
            if not card:
                return
            if widget_key == "btn_start" and "state" in kwargs:
                card["start_state"] = kwargs["state"]
            elif widget_key == "btn_pause" and "state" in kwargs:
                card["pause_state"] = kwargs["state"]
            elif widget_key == "btn_stop" and "state" in kwargs:
                card["stop_state"] = kwargs["state"]
            elif widget_key == "btn_ld_start" and "state" in kwargs:
                card["ld_start_state"] = kwargs["state"]
            self._update_device_row(serial)
            self._refresh_device_action_buttons()
        self._ui_safe(_apply)

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
        """Chạy auto cho 1 nick (nếu đang tạm dừng thì tiếp tục, chưa chạy thì bắt đầu)."""
        card = self.device_cards.get(serial)
        if not card:
            return
        if card.get("thread") and card["thread"].is_alive():
            if card.get("is_paused"):
                self._resume_one(serial)
            return

        cfg = cfg or self._load_config()
        if not cfg:
            return
        settings, tasks, ban_do = cfg

        # Đang chạy rồi thì bỏ qua
        if not card.get("running", True):
            self._set_card_status(serial, "Chưa mở LD", "#7f8c8d")
            return
        if card["thread"] and card["thread"].is_alive():
            return

        config_name = self.config_var.get()
        self._reset_runtime_flags_for_start(serial)

        stop_ev = threading.Event()
        pause_ev = threading.Event()
        card["stop_event"] = stop_ev
        card["pause_event"] = pause_ev
        card["is_paused"] = False
        card["btn_start"].config(state=tk.DISABLED)
        card["btn_pause"].config(state=tk.NORMAL)
        card["btn_stop"].config(state=tk.NORMAL)
        self._set_card_status(serial, f"Đang chạy: {config_name}", "#27ae60")
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
                    set_utils_debug_mode(True)
                    set_ban_do_debug_mode(True)
                    set_trong_cay_debug_mode(True)
                    set_thu_hoach_debug_mode(True)
                    set_san_xuat_debug_mode(True)
                    set_sxcam_debug_mode(True)

                adb_inst = ADBController(serial=serial)

                # Setup thread với device_name → tất cả log tự động có [tên nick]
                def thread_status_cb(msg, color="#e67e22"):
                    self._set_card_status(serial, f"{config_name} | {msg}", color)

                setup_thread(adb_inst, stop_event=stop_ev, pause_event=pause_ev, device_name=dev_name, status_callback=thread_status_cb)

                # Đồng bộ cấu hình AI toàn cục từ Tab Cấu Hình Chung
                global_config.GEMINI_API_KEY = self.gemini_api_key_var.get().strip()
                global_config.ENABLE_AI_RECOVERY = self.bat_ai_recovery_var.get()
                global_config.ENABLE_YOLO = self.bat_yolo_var.get()
                global_config.YOLO_MODEL_PATH = self.yolo_model_path_var.get().strip()

                self._log(f"{dev_label} Kết nối thành công | Config: {config_name}")

                tc_tasks = [t for t in tasks if
                            (t.get("type") == "TC" and settings.get("bat_trong_cay")) or
                            (t.get("type") == "MAY" and settings.get("bat_may"))]

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
                    loop_start_time = time.time()
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
                            else:
                                self._set_card_status(serial, f"{config_name} | Chưa có rương", "#7f8c8d")

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
                            lbl_loop = f" ({loop_i+1}/{loop_tc_may})" if loop_tc_may > 1 else ""
                            self._log(f"{dev_label} [{config_name}] TC+MAY {loop_i+1}/{loop_tc_may}")
                            self._set_card_status(serial, f"{config_name} | Trồng cây & Máy{lbl_loop}...", "#e67e22")
                            main_tc(tc_tasks, adb_instance=adb_inst, stop_event=stop_ev,
                                    global_threshold=settings.get("threshold"), is_sua_may= (loop_i == loop_tc_may-1))
                            end_time_item = time.time()
                            elapsed = end_time_item - start_time_item
                            self._log(f"{dev_label} [{config_name}] TC+MAY {loop_i+1}/{loop_tc_may} hoàn thành trong {elapsed:.1f}s")
                            record_loop_run(
                                serial,
                                loop_index=loop_i + 1,
                                duration=elapsed,
                                task="tc_may",
                                note=f"[{config_name}] Lặp #{tong_i} - TC+MAY {loop_i+1}/{loop_tc_may}",
                                update_summary=(loop_tc_may > 1)
                            )
                            self._ui_safe(lambda s=serial: self._update_device_row(s))
                        end_time = time.time()
                        elapsed = end_time - start_time
                        self._log(f"{dev_label} [{config_name}] TC+MAY x{loop_tc_may} hoàn thành trong {elapsed:.1f}s")
                        self._set_card_status(serial, f"{config_name} | Đã xong TC+MAY", "#27ae60")
                        
                    if stop_ev.is_set():
                        break

                    if settings.get("bat_ban_vp") and ban_do.get("data"):
                        self._log(f"{dev_label} [{config_name}] Bán vật phẩm")
                        self._set_card_status(serial, f"{config_name} | Bán VP...", "#e67e22")
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

                    # Ghi nhận tổng thời gian vòng lặp vào CSV thống kê
                    loop_total_elapsed = time.time() - loop_start_time
                    record_loop_run(
                        serial,
                        loop_index=tong_i,
                        duration=loop_total_elapsed,
                        task="vong_lap",
                        note=f"[{config_name}] Vòng lặp #{tong_i} ({loop_total_elapsed:.1f}s)",
                        update_summary=(loop_tc_may <= 1 or not tc_tasks)
                    )
                    self._ui_safe(lambda s=serial: self._update_device_row(s))
                    self._log(f"{dev_label} [{config_name}] Vòng lặp #{tong_i} xong trong {loop_total_elapsed:.1f}s (Tốc độ: {loop_total_elapsed:.1f}s/vòng)")

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
                card["is_paused"] = False
                self._ui_safe(lambda: self._config_current_card(serial, "btn_start", state=tk.NORMAL))
                self._ui_safe(lambda: self._config_current_card(serial, "btn_pause", state=tk.DISABLED))
                self._ui_safe(lambda: self._config_current_card(serial, "btn_stop", state=tk.DISABLED))

        t = threading.Thread(target=run, daemon=True)
        card["thread"] = t
        t.start()

    def _pause_one(self, serial):
        """Tạm dừng auto cho 1 nick mà không hủy thread."""
        card = self.device_cards.get(serial)
        if not card or not card.get("thread") or not card["thread"].is_alive():
            return
        if card.get("is_paused"):
            return
        pause_ev = card.get("pause_event")
        if pause_ev:
            pause_ev.set()
        card["is_paused"] = True
        card["start_state"] = tk.NORMAL
        card["pause_state"] = tk.DISABLED
        card["stop_state"] = tk.NORMAL
        config_name = self.config_var.get()
        self._set_card_status(serial, f"{config_name} | Tạm dừng ⏸", "#f39c12")
        self._log(f"[{card['name']}] Đã tạm dừng auto.")
        self._update_device_row(serial)

    def _resume_one(self, serial):
        """Tiếp tục auto từ vị trí tạm dừng."""
        card = self.device_cards.get(serial)
        if not card:
            return
        if not card.get("thread") or not card["thread"].is_alive():
            card["is_paused"] = False
            self._start_one(serial)
            return
        pause_ev = card.get("pause_event")
        if pause_ev:
            pause_ev.clear()
        card["is_paused"] = False
        card["start_state"] = tk.DISABLED
        card["pause_state"] = tk.NORMAL
        card["stop_state"] = tk.NORMAL
        config_name = self.config_var.get()
        self._set_card_status(serial, f"{config_name} | Tiếp tục chạy ▶", "#27ae60")
        self._log(f"[{card['name']}] Tiếp tục chạy auto.")
        self._update_device_row(serial)

    def _pause_all(self):
        """Tạm dừng tất cả các nick đang chạy."""
        count = 0
        for serial, card in list(self.device_cards.items()):
            if card.get("thread") and card["thread"].is_alive() and not card.get("is_paused"):
                self._pause_one(serial)
                count += 1
        if count:
            self.status_label.config(text=f"Đã tạm dừng {count} LDPlayer", bg="#f39c12")
        else:
            self.status_label.config(text="Không có LDPlayer nào đang chạy để tạm dừng")

    def _stop_one(self, serial):
        """Dừng 1 nick."""
        card = self.device_cards.get(serial)
        if not card:
            return
        pause_ev = card.get("pause_event")
        if pause_ev:
            pause_ev.clear()
        card["is_paused"] = False
        if card.get("stop_event"):
            card["stop_event"].set()
            self._log(f"[{card['name']}] Đang dừng...")
            card["pause_state"] = tk.DISABLED
            card["stop_state"] = tk.DISABLED
            self._update_device_row(serial)

    def _start_all(self):
        """Chạy tất cả nick (nếu đang tạm dừng thì tiếp tục, nếu chưa chạy thì bắt đầu)."""
        if getattr(self, "_start_all_queue_running", False):
            self.status_label.config(text="Đang xử lý chạy tất cả, vui lòng đợi...")
            return

        cfg = self._load_config()
        if not cfg:
            return

        resumed_count = 0
        for serial, card in list(self.device_cards.items()):
            if card.get("thread") and card["thread"].is_alive() and card.get("is_paused"):
                self._resume_one(serial)
                resumed_count += 1

        targets = []
        skipped_not_running = 0
        for serial, card in list(self.device_cards.items()):
            if card.get("thread") and card["thread"].is_alive():
                continue
            if not card.get("running", True):
                skipped_not_running += 1
                self._set_card_status(serial, "Chưa mở LD", "#7f8c8d")
                continue
            targets.append(serial)

        if not targets and not resumed_count:
            self.status_label.config(text="Không có LDPlayer nào sẵn sàng để chạy")
            return

        if not targets:
            self.status_label.config(text=f"Đã tiếp tục {resumed_count} LDPlayer đang tạm dừng")
            return

        self.status_label.config(text=f"Đang xếp lịch chạy {len(targets)} LDPlayer")
        self._start_all_queue_running = True

        def start_next(pos=0):
            if not getattr(self, "_start_all_queue_running", False):
                self.status_label.config(text="Đã hủy xếp lịch chạy tất cả")
                return
            if pos >= len(targets):
                self._start_all_queue_running = False
                msg = f"Đã chạy {len(targets)} tác vụ"
                if resumed_count:
                    msg += f" | Tiếp tục {resumed_count} LD"
                if skipped_not_running:
                    msg += f" | Bỏ qua {skipped_not_running} LD chưa mở"
                self.status_label.config(text=msg)
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
        from core.trong_cay import set_debug_mode as trong_cay_debug
        from core.thu_hoach import set_debug_mode as thu_hoach_debug
        from core.san_xuat import set_debug_mode as san_xuat_debug
        from core.sxcam import set_debug_mode as sxcam_debug
        ban_do_debug(enabled)
        utils_debug(enabled)
        trong_cay_debug(enabled)
        thu_hoach_debug(enabled)
        san_xuat_debug(enabled)
        sxcam_debug(enabled)
        self._log(f"Gỡ lỗi: {'Bật' if enabled else 'Tắt'}")

    def _open_debug_folder(self):
        def _worker():
            debug_dir = os.path.abspath("debug")
            os.makedirs(debug_dir, exist_ok=True)
            try:
                from utils.utils import cleanup_debug_files
                cleanup_debug_files(debug_dir)
            except Exception:
                pass
            try:
                subprocess.Popen(f'explorer.exe "{debug_dir}"')
            except Exception:
                try:
                    os.startfile(debug_dir)
                except Exception:
                    pass
        threading.Thread(target=_worker, daemon=True).start()

    def _clear_debug_folder(self):
        debug_dir = os.path.abspath("debug")
        if not os.path.exists(debug_dir):
            messagebox.showinfo("Thông báo", "Thư mục debug hiện đang trống!")
            return
        if messagebox.askyesno("Xác nhận", "Bạn có chắc muốn xóa toàn bộ ảnh trong thư mục debug để giải phóng dung lượng?"):
            def _worker():
                try:
                    deleted = 0
                    for root, _, files in os.walk(debug_dir):
                        for f in files:
                            ext = os.path.splitext(f)[1].lower()
                            if ext in ('.png', '.jpg', '.jpeg'):
                                try:
                                    os.remove(os.path.join(root, f))
                                    deleted += 1
                                except OSError:
                                    pass
                    self._log(f"Đã dọn dẹp {deleted} ảnh debug.")
                    self._ui_safe(lambda: messagebox.showinfo("Thành công", f"Đã xóa {deleted} ảnh debug để giải phóng bộ nhớ!"))
                except Exception as e:
                    self._log(f"Lỗi khi xóa debug: {e}")
            threading.Thread(target=_worker, daemon=True).start()

    def _open_daily_stats_folder(self):
        folder = os.path.abspath("data/daily_stats")
        os.makedirs(folder, exist_ok=True)
        try:
            subprocess.Popen(f'explorer.exe "{folder}"')
        except Exception:
            pass

    def _open_daily_stats_csv(self):
        csv_path = os.path.abspath(get_today_stats_path())
        if not os.path.exists(csv_path):
            from utils.daily_stats import _write_rows
            _write_rows(csv_path, [])

        self.status_label.config(text=f"Đang mở CSV: {os.path.basename(csv_path)}...", bg="#1565c0")
        self._log(f"Đang mở file thống kê: {csv_path}")

        def _worker():
            try:
                # Mở bằng ứng dụng mặc định trong process riêng biệt qua cmd start
                # Tuyệt đối không gọi os.startfile trực tiếp trên main thread vì DDE của Excel sẽ khóa cứng giao diện
                subprocess.Popen(f'cmd /c start "" "{csv_path}"', shell=True)
            except Exception:
                try:
                    subprocess.Popen(f'explorer.exe /select,"{csv_path}"')
                except Exception as e:
                    self._ui_safe(lambda: messagebox.showerror("Mở thống kê", f"Không thể mở file CSV:\n{e}"))

        threading.Thread(target=_worker, daemon=True).start()

    # ----------------------------------------------------------------
