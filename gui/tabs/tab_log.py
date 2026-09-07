import os
import sys
import logging
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess

from gui.constants import GUI_LOG_MAX_LINES

logger = logging.getLogger(__name__)


class LogTabMixin:
    """Tab 7: Xem nhật ký hoạt động thời gian thực và thống kê Gemini AI."""
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
                    subprocess.Popen(f'cmd /c start "" "{os.path.abspath(target_csv)}"', shell=True)
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
            subprocess.Popen(['notepad.exe', log_path])
        else:
            messagebox.showinfo("Thông báo", "Chưa có tệp nhật ký!")

    # ----------------------------------------------------------------
