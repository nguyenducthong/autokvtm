import os
import sys
import json
import ssl
import logging
import threading
import urllib.request
import webbrowser
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
from config import CURRENT_VERSION, GITHUB_API_URL, GITHUB_RELEASES_URL

logger = logging.getLogger(__name__)


def parse_version(v):
    """Phân tích chuỗi phiên bản (ví dụ 'v1.0.23' hoặc '1.0.23') thành danh sách số nguyên."""
    if not v:
        return [0]
    v = str(v).lstrip('vV').strip()
    try:
        parts = [int(x) for x in v.split('.') if x.isdigit()]
        return parts if parts else [0]
    except Exception:
        return [0]


def format_release_date(date_str):
    """Định dạng chuỗi ngày phát hành ISO (2026-09-07T13:33:59Z) thành ngày giờ dễ đọc."""
    if not date_str:
        return "Không rõ"
    try:
        parts = date_str.split("T")
        date_part = parts[0]
        time_part = parts[1].replace("Z", "")[:5] if len(parts) > 1 else ""
        y, m, d = date_part.split("-")
        return f"{d}/{m}/{y} {time_part}".strip()
    except Exception:
        return date_str


def format_file_size(size_bytes):
    """Chuyển đổi kích thước file từ byte sang định dạng MB/KB."""
    if not size_bytes:
        return ""
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


class UpdaterMixin:
    """Mixin xử lý kiểm tra, quản lý danh sách phiên bản, cập nhật và hạ cấp."""

    def check_update_action(self, silent=False):
        """Khởi chạy kiểm tra cập nhật ngầm hoặc mở giao diện chọn phiên bản."""
        if silent:
            threading.Thread(
                target=self._check_for_updates_thread,
                args=(True,),
                daemon=True
            ).start()
        else:
            self.open_version_manager()

    def open_version_manager(self):
        """Mở cửa sổ quản lý phiên bản, cho phép xem, cập nhật hoặc cài đặt các phiên bản cũ."""
        if hasattr(self, '_version_manager_win') and self._version_manager_win and self._version_manager_win.winfo_exists():
            self._version_manager_win.lift()
            self._version_manager_win.focus_force()
            return

        win = tk.Toplevel(self.root)
        self._version_manager_win = win
        win.title("Quản lý phiên bản & Cập nhật - AutoKVTM")
        win.geometry("680x590")
        win.minsize(600, 520)
        win.configure(bg="#f4f6f9")

        # Căn giữa màn hình
        win.update_idletasks()
        rx = self.root.winfo_x()
        ry = self.root.winfo_y()
        rw = self.root.winfo_width()
        rh = self.root.winfo_height()
        w = 680
        h = 590
        x = max(0, rx + (rw - w) // 2)
        y = max(0, ry + (rh - h) // 2)
        win.geometry(f"{w}x{h}+{x}+{y}")
        win.transient(self.root)

        # Header Banner
        header = tk.Frame(win, bg="#2c3e50", height=65)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        h_left = tk.Frame(header, bg="#2c3e50")
        h_left.pack(side=tk.LEFT, padx=16, pady=8)
        tk.Label(
            h_left, text="QUẢN LÝ PHIÊN BẢN & CẬP NHẬT",
            font=("Arial", 12, "bold"), fg="#ecf0f1", bg="#2c3e50"
        ).pack(anchor="w")
        tk.Label(
            h_left, text="Bạn có thể nâng cấp lên bản mới hoặc cài đặt lại các phiên bản cũ",
            font=("Arial", 9), fg="#bdc3c7", bg="#2c3e50"
        ).pack(anchor="w", pady=(2, 0))

        h_right = tk.Frame(header, bg="#2c3e50")
        h_right.pack(side=tk.RIGHT, padx=16)
        curr_badge = tk.Label(
            h_right, text=f"Đang dùng: v{CURRENT_VERSION}",
            font=("Arial", 9, "bold"), fg="white", bg="#27ae60",
            padx=10, pady=5, relief=tk.FLAT
        )
        curr_badge.pack()

        # Status Bar
        status_bar = tk.Frame(win, bg="#e8ecf1", padx=14, pady=6)
        status_bar.pack(fill=tk.X)

        status_lbl = tk.Label(
            status_bar, text="🔄 Đang kết nối và tải danh sách phiên bản từ GitHub...",
            font=("Arial", 9), fg="#34495e", bg="#e8ecf1"
        )
        status_lbl.pack(side=tk.LEFT)

        btn_refresh = tk.Button(
            status_bar, text="🔄 Làm mới", font=("Arial", 8, "bold"),
            bg="#ffffff", fg="#2c3e50", activebackground="#dfe6e9",
            relief=tk.GROOVE, cursor="hand2", padx=8, pady=1
        )
        btn_refresh.pack(side=tk.RIGHT)

        # Main Body
        main_body = tk.Frame(win, bg="#f4f6f9", padx=16, pady=10)
        main_body.pack(fill=tk.BOTH, expand=True)

        # 1. Khung chọn phiên bản
        sel_frame = tk.LabelFrame(
            main_body, text=" Chọn phiên bản ",
            font=("Arial", 10, "bold"), bg="#ffffff", fg="#2c3e50", padx=12, pady=8
        )
        sel_frame.pack(fill=tk.X, pady=(0, 8))

        combo_row = tk.Frame(sel_frame, bg="#ffffff")
        combo_row.pack(fill=tk.X)

        tk.Label(
            combo_row, text="Phiên bản phát hành:",
            font=("Arial", 9, "bold"), bg="#ffffff", fg="#34495e"
        ).pack(side=tk.LEFT, padx=(0, 8))

        version_var = tk.StringVar()
        version_combo = ttk.Combobox(
            combo_row, textvariable=version_var, state="disabled",
            font=("Arial", 9), width=50
        )
        version_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        quick_btn_frame = tk.Frame(sel_frame, bg="#ffffff")
        quick_btn_frame.pack(fill=tk.X, pady=(6, 2))

        lbl_hint = tk.Label(
            quick_btn_frame,
            text="💡 Chọn phiên bản trong danh sách trên, hoặc chọn nhanh:",
            font=("Arial", 8, "italic"), bg="#ffffff", fg="#7f8c8d"
        )
        lbl_hint.pack(side=tk.LEFT)

        btn_select_prev = tk.Button(
            quick_btn_frame, text="⏪ Chọn bản cũ gần nhất", font=("Arial", 8, "bold"),
            bg="#f39c12", fg="white", activebackground="#e67e22", activeforeground="white",
            relief=tk.RAISED, cursor="hand2", padx=8, pady=1, state=tk.DISABLED
        )
        btn_select_prev.pack(side=tk.RIGHT, padx=(4, 0))

        btn_select_latest = tk.Button(
            quick_btn_frame, text="🚀 Chọn bản mới nhất", font=("Arial", 8, "bold"),
            bg="#27ae60", fg="white", activebackground="#2ecc71", activeforeground="white",
            relief=tk.RAISED, cursor="hand2", padx=8, pady=1, state=tk.DISABLED
        )
        btn_select_latest.pack(side=tk.RIGHT)

        # 2. Khung chi tiết phiên bản
        detail_frame = tk.LabelFrame(
            main_body, text=" Thông tin phiên bản đã chọn ",
            font=("Arial", 10, "bold"), bg="#ffffff", fg="#2c3e50", padx=12, pady=8
        )
        detail_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        meta_row1 = tk.Frame(detail_frame, bg="#ffffff")
        meta_row1.pack(fill=tk.X, pady=(2, 4))
        lbl_meta_tag = tk.Label(meta_row1, text="Phiên bản: Đang tải...", font=("Arial", 9, "bold"), bg="#ffffff", fg="#2c3e50")
        lbl_meta_tag.pack(side=tk.LEFT)
        lbl_meta_date = tk.Label(meta_row1, text="Ngày phát hành: --", font=("Arial", 9), bg="#ffffff", fg="#7f8c8d")
        lbl_meta_date.pack(side=tk.RIGHT)

        meta_row2 = tk.Frame(detail_frame, bg="#ffffff")
        meta_row2.pack(fill=tk.X, pady=(2, 6))
        lbl_meta_asset = tk.Label(meta_row2, text="File cài đặt: Đang kiểm tra...", font=("Arial", 9), bg="#ffffff", fg="#2980b9")
        lbl_meta_asset.pack(side=tk.LEFT)

        btn_card_action = tk.Button(
            meta_row2, text="", command=lambda: on_click_install(),
            font=("Arial", 9, "bold"), fg="white", relief=tk.RAISED,
            cursor="hand2", padx=12, pady=3, state=tk.DISABLED
        )
        btn_card_action.pack(side=tk.RIGHT)

        tk.Label(
            detail_frame, text="Nội dung cập nhật (Release Notes):",
            font=("Arial", 9, "bold"), bg="#ffffff", fg="#34495e", anchor="w"
        ).pack(fill=tk.X, pady=(4, 2))

        cl_frame = tk.Frame(detail_frame, bg="#ffffff")
        cl_frame.pack(fill=tk.BOTH, expand=True)
        changelog_text = tk.Text(
            cl_frame, font=("Segoe UI", 9), bg="#fafbfc", fg="#2c3e50",
            wrap=tk.WORD, bd=1, relief=tk.SOLID
        )
        cl_scroll = ttk.Scrollbar(cl_frame, orient=tk.VERTICAL, command=changelog_text.yview)
        changelog_text.configure(yscrollcommand=cl_scroll.set)
        cl_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        changelog_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Bottom Bar
        bottom_bar = tk.Frame(win, bg="#ecf0f1", padx=16, pady=10)
        bottom_bar.pack(fill=tk.X, side=tk.BOTTOM)

        btn_web = tk.Button(
            bottom_bar, text="🌐 Mở trên GitHub", font=("Arial", 9),
            bg="#ffffff", fg="#2c3e50", relief=tk.GROOVE, cursor="hand2", padx=10, pady=4
        )
        btn_web.pack(side=tk.LEFT)

        btn_close = tk.Button(
            bottom_bar, text="Đóng", font=("Arial", 9),
            bg="#95a5a6", fg="white", relief=tk.FLAT, cursor="hand2", padx=14, pady=4,
            command=win.destroy
        )
        btn_close.pack(side=tk.RIGHT, padx=(8, 0))

        btn_action = tk.Button(
            bottom_bar, text="Cài đặt phiên bản này", font=("Arial", 10, "bold"),
            bg="#bdc3c7", fg="white", relief=tk.FLAT, cursor="hand2", padx=16, pady=4,
            command=lambda: on_click_install(),
            state=tk.DISABLED
        )
        btn_action.pack(side=tk.RIGHT)

        # Lưu trữ danh sách releases và release đang được chọn
        releases_cache = []
        selected_release_obj = [None]

        def get_current_selected_release():
            # 1. Ưu tiên kiểm tra chuỗi tag hiển thị trong Combobox
            curr_text = version_var.get().strip()
            if curr_text and releases_cache:
                tag_prefix = curr_text.split()[0].strip()
                for rel in releases_cache:
                    if rel.get("tag_name", "").strip() == tag_prefix:
                        return rel
            # 2. Kiểm tra theo index combobox.current()
            idx = version_combo.current()
            if 0 <= idx < len(releases_cache):
                return releases_cache[idx]
            # 3. Release object đã được chọn lưu trong view
            if selected_release_obj[0] is not None:
                return selected_release_obj[0]
            if releases_cache:
                return releases_cache[0]
            return None

        def update_detail_view(release_data):
            if not release_data:
                return
            selected_release_obj[0] = release_data
            tag = release_data.get("tag_name", "").strip()
            clean_ver = tag.lstrip("vV")
            pub_date = format_release_date(release_data.get("published_at"))
            html_url = release_data.get("html_url", "https://github.com/nguyenducthong/autokvtm/releases")
            body = release_data.get("body") or "Không có ghi chú thay đổi nào cho phiên bản này."

            lbl_meta_tag.config(text=f"Phiên bản: {tag}")
            lbl_meta_date.config(text=f"Ngày phát hành: {pub_date}")

            # Tìm gói cài đặt (.zip cho thư mục hoặc .exe độc lập)
            exe_asset = None
            for asset in release_data.get("assets", []):
                aname = asset.get("name", "").lower()
                if aname.endswith(".zip"):
                    exe_asset = asset
                    break
            if not exe_asset:
                for asset in release_data.get("assets", []):
                    aname = asset.get("name", "").lower()
                    if aname.endswith(".exe"):
                        exe_asset = asset
                        break

            if exe_asset:
                size_str = format_file_size(exe_asset.get("size", 0))
                lbl_meta_asset.config(
                    text=f"Gói cài đặt: {exe_asset['name']} ({size_str})",
                    fg="#2980b9"
                )
            else:
                lbl_meta_asset.config(
                    text="Gói cài đặt: Không tìm thấy file .zip hoặc .exe trong bản phát hành này",
                    fg="#e74c3c"
                )

            # Phân loại so sánh phiên bản
            parsed_target = parse_version(clean_ver)
            parsed_current = parse_version(CURRENT_VERSION)

            if parsed_target > parsed_current:
                if exe_asset:
                    btn_card_action.config(
                        state=tk.NORMAL,
                        text=f"🚀 Bấm để Nâng cấp lên {tag}",
                        bg="#27ae60",
                        fg="white",
                        activebackground="#2ecc71",
                        activeforeground="white"
                    )
                    btn_action.config(
                        state=tk.NORMAL,
                        text=f"🚀 Nâng cấp lên {tag}",
                        bg="#27ae60",
                        fg="white",
                        activebackground="#2ecc71",
                        activeforeground="white"
                    )
            elif parsed_target == parsed_current:
                if exe_asset:
                    btn_card_action.config(
                        state=tk.NORMAL,
                        text=f"🔄 Bấm để Cài đặt lại {tag}",
                        bg="#2980b9",
                        fg="white",
                        activebackground="#3498db",
                        activeforeground="white"
                    )
                    btn_action.config(
                        state=tk.NORMAL,
                        text=f"🔄 Cài đặt lại {tag}",
                        bg="#2980b9",
                        fg="white",
                        activebackground="#3498db",
                        activeforeground="white"
                    )
            else:
                if exe_asset:
                    btn_card_action.config(
                        state=tk.NORMAL,
                        text=f"⏪ Bấm để Hạ cấp về {tag}",
                        bg="#d35400",
                        fg="white",
                        activebackground="#e67e22",
                        activeforeground="white"
                    )
                    btn_action.config(
                        state=tk.NORMAL,
                        text=f"⏪ Bấm để Hạ cấp về {tag}",
                        bg="#d35400",
                        fg="white",
                        activebackground="#e67e22",
                        activeforeground="white"
                    )

            if not exe_asset:
                btn_card_action.config(
                    state=tk.DISABLED,
                    text="Không có .exe để cài đặt",
                    bg="#bdc3c7",
                    fg="#7f8c8d"
                )
                btn_action.config(
                    state=tk.DISABLED,
                    text="Không có file .exe để cài đặt",
                    bg="#bdc3c7",
                    fg="#7f8c8d"
                )

            # Changelog
            changelog_text.config(state=tk.NORMAL)
            changelog_text.delete("1.0", tk.END)
            changelog_text.insert(tk.END, body)
            changelog_text.config(state=tk.DISABLED)

            btn_web.config(command=lambda: webbrowser.open(html_url))

        def on_select_version(event=None):
            r = get_current_selected_release()
            if r:
                update_detail_view(r)

        version_combo.bind("<<ComboboxSelected>>", on_select_version)
        version_combo.bind("<Return>", on_select_version)
        version_combo.bind("<FocusOut>", on_select_version)

        def select_prev_release():
            if not releases_cache:
                return
            parsed_cur = parse_version(CURRENT_VERSION)
            for i, rel in enumerate(releases_cache):
                c_v = rel.get("tag_name", "").lstrip("vV")
                if parse_version(c_v) < parsed_cur:
                    version_combo.current(i)
                    update_detail_view(rel)
                    return
            messagebox.showinfo("Thông báo", "Không tìm thấy phiên bản cũ hơn phiên bản hiện tại.", parent=win)

        def select_latest_release():
            if not releases_cache:
                return
            version_combo.current(0)
            update_detail_view(releases_cache[0])

        btn_select_prev.config(command=select_prev_release)
        btn_select_latest.config(command=select_latest_release)

        def on_click_install():
            r = get_current_selected_release()
            if not r:
                messagebox.showwarning("Thông báo", "Vui lòng chọn một phiên bản từ danh sách trước khi cài đặt.", parent=win)
                return

            tag = r.get("tag_name", "").strip()
            clean_ver = tag.lstrip("vV")
            changelog = r.get("body") or ""

            exe_asset = None
            for asset in r.get("assets", []):
                aname = asset.get("name", "").lower()
                if aname.endswith(".zip"):
                    exe_asset = asset
                    break
            if not exe_asset:
                for asset in r.get("assets", []):
                    aname = asset.get("name", "").lower()
                    if aname.endswith(".exe"):
                        exe_asset = asset
                        break

            if not exe_asset:
                if messagebox.askyesno(
                    "Không có gói cài đặt",
                    f"Bản phát hành {tag} không có gói cài đặt (.zip hoặc .exe) đính kèm.\n\n"
                    f"Bạn có muốn mở trang GitHub để tải thủ công không?",
                    parent=win
                ):
                    webbrowser.open(r.get("html_url", "https://github.com/nguyenducthong/autokvtm/releases"))
                return

            download_url = exe_asset.get("browser_download_url")
            parsed_target = parse_version(clean_ver)
            parsed_current = parse_version(CURRENT_VERSION)

            if parsed_target < parsed_current:
                confirm = messagebox.askyesno(
                    "Xác nhận hạ cấp phiên bản",
                    f"Bạn đang chọn cài đặt phiên bản CŨ HƠN: {tag}\n"
                    f"(Phiên bản đang chạy hiện tại: v{CURRENT_VERSION})\n\n"
                    f"Hệ thống sẽ tải file cài đặt {exe_asset['name']} và tự động thay thế để hạ cấp về {tag}.\n\n"
                    f"Bạn có chắc chắn muốn hạ cấp không?",
                    parent=win
                )
            elif parsed_target > parsed_current:
                confirm = messagebox.askyesno(
                    "Xác nhận nâng cấp phiên bản",
                    f"Bạn có muốn tải và nâng cấp lên phiên bản mới {tag} không?",
                    parent=win
                )
            else:
                confirm = messagebox.askyesno(
                    "Xác nhận cài đặt lại",
                    f"Bạn có muốn tải và cài đặt lại phiên bản {tag} không?",
                    parent=win
                )

            if not confirm:
                return

            # Đóng cửa sổ quản lý phiên bản và tiến hành tải
            win.destroy()
            self._download_update(download_url, latest_version=tag, changelog=changelog, silent=False)

        def fetch_releases():
            status_lbl.config(text="🔄 Đang kết nối và tải danh sách phiên bản từ GitHub...", fg="#34495e")
            btn_refresh.config(state=tk.DISABLED)
            btn_select_prev.config(state=tk.DISABLED)
            btn_select_latest.config(state=tk.DISABLED)
            version_combo.config(state="disabled")

            def task():
                try:
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE

                    req = urllib.request.Request(
                        GITHUB_RELEASES_URL,
                        headers={"User-Agent": "AutoKVTM-Updater"}
                    )
                    with urllib.request.urlopen(req, timeout=12, context=ctx) as response:
                        raw_data = json.loads(response.read().decode("utf-8"))

                    if not isinstance(raw_data, list):
                        raise ValueError("Dữ liệu trả về từ GitHub không hợp lệ.")

                    def on_success():
                        if not win.winfo_exists():
                            return
                        nonlocal releases_cache
                        releases_cache = raw_data
                        btn_refresh.config(state=tk.NORMAL)
                        btn_select_prev.config(state=tk.NORMAL)
                        btn_select_latest.config(state=tk.NORMAL)

                        if not releases_cache:
                            status_lbl.config(text="⚠️ Chưa tìm thấy bản phát hành nào trên GitHub.", fg="#e67e22")
                            return

                        status_lbl.config(
                            text=f"✅ Đã tìm thấy {len(releases_cache)} phiên bản phát hành trên GitHub.",
                            fg="#27ae60"
                        )

                        combo_items = []
                        current_idx = 0
                        parsed_cur = parse_version(CURRENT_VERSION)

                        for i, rel in enumerate(releases_cache):
                            t = rel.get("tag_name", "").strip()
                            c_v = t.lstrip("vV")
                            p_date = format_release_date(rel.get("published_at"))
                            p_v = parse_version(c_v)

                            if p_v == parsed_cur:
                                label = f"{t}  ★ [Đang dùng] ({p_date})"
                                current_idx = i
                            elif p_v > parsed_cur:
                                label = f"{t}  🚀 [Bản mới hơn] ({p_date})"
                            else:
                                label = f"{t}  ⏪ [Bản cũ] ({p_date})"

                            has_exe = any(a.get("name", "").endswith(".exe") for a in rel.get("assets", []))
                            if not has_exe:
                                label += " (Không có .exe)"

                            combo_items.append(label)

                        version_combo['values'] = combo_items
                        version_combo.config(state="readonly")
                        version_combo.current(current_idx)
                        update_detail_view(releases_cache[current_idx])

                    try:
                        win.after(0, on_success)
                    except Exception:
                        self.root.after(0, on_success)

                except Exception as err:
                    def on_error():
                        if not win.winfo_exists():
                            return
                        btn_refresh.config(state=tk.NORMAL)
                        btn_select_prev.config(state=tk.DISABLED)
                        btn_select_latest.config(state=tk.DISABLED)
                        status_lbl.config(text=f"❌ Lỗi tải phiên bản: {err}", fg="#e74c3c")
                        messagebox.showwarning(
                            "Không thể tải danh sách phiên bản",
                            f"Không thể kết nối tới GitHub Releases:\n{err}\n\n"
                            f"Vui lòng kiểm tra kết nối mạng hoặc thử lại sau.",
                            parent=win
                        )
                    try:
                        win.after(0, on_error)
                    except Exception:
                        self.root.after(0, on_error)

            threading.Thread(target=task, daemon=True).start()

        btn_refresh.config(command=fetch_releases)

        # Tự động tải danh sách lần đầu khi mở dialog
        fetch_releases()

    def _check_for_updates_thread(self, silent):
        """Kiểm tra xem có bản cập nhật mới nhất không (dùng khi chạy kiểm tra ngầm)."""
        try:
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
            latest_version = latest_tag[1:] if latest_tag.lower().startswith('v') else latest_tag
            changelog = data.get("body") or "Không có thông tin thay đổi."
            html_url = data.get("html_url", "https://github.com/nguyenducthong/autokvtm/releases")

            download_url = None
            for asset in data.get("assets", []):
                if asset.get("name", "").endswith(".exe"):
                    download_url = asset.get("browser_download_url")
                    break

            if parse_version(latest_version) > parse_version(CURRENT_VERSION):
                if silent:
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
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Lỗi kiểm tra cập nhật",
                        f"Không thể kết nối đến máy chủ GitHub để kiểm tra cập nhật:\n{e}"
                    )
                )

    def _prompt_update(self, latest_version, download_url, html_url, changelog):
        msg = f"Đã có phiên bản mới: {latest_version}\n" \
              f"(Phiên bản hiện tại: {CURRENT_VERSION})\n\n" \
              f"Nội dung cập nhật:\n{changelog}\n\n" \
              f"Bạn có muốn cập nhật ngay bây giờ không?"

        if messagebox.askyesno("Tìm thấy bản cập nhật mới", msg):
            if not getattr(sys, 'frozen', False):
                messagebox.showinfo(
                    "Thông báo",
                    "Bạn đang chạy ứng dụng từ mã nguồn (source code).\n"
                    "Hệ thống sẽ mở trình duyệt để bạn tải file hoặc git pull bản mới nhất.",
                    parent=self.root
                )
                webbrowser.open(html_url)
            else:
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

        if not silent:
            progress_win.grab_set()

        # Căn giữa cửa sổ con theo cửa sổ chính
        x = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 140) // 2
        progress_win.geometry(f"+{x}+{y}")

        if silent:
            lbl = tk.Label(progress_win, text="Đang tải bản cập nhật mới trong nền...\n(Bạn vẫn có thể tương tác với ứng dụng chính bình thường)", font=("Arial", 10), justify=tk.CENTER)
        else:
            ver_text = f" {latest_version}" if latest_version else ""
            lbl = tk.Label(progress_win, text=f"Đang tải về phiên bản{ver_text}, vui lòng đợi...", font=("Arial", 10))
        lbl.pack(pady=15)

        progress = ttk.Progressbar(progress_win, orient=tk.HORIZONTAL, length=320, mode='determinate')
        progress.pack(pady=5)

        def _download_thread():
            try:
                is_frozen = getattr(sys, 'frozen', False)
                current_exe = sys.executable if is_frozen else os.path.abspath(sys.argv[0])
                dir_name = os.path.dirname(current_exe)
                filename = os.path.basename(current_exe)

                is_zip = download_url.lower().split("?")[0].endswith(".zip")
                if is_zip:
                    new_exe_name = "update_package.zip"
                elif is_frozen:
                    base, ext = os.path.splitext(filename)
                    new_exe_name = f"{base}_new{ext}"
                else:
                    new_exe_name = "gui_auto_config_new.exe"

                new_exe_path = os.path.join(dir_name, new_exe_name)

                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE

                # Kiểm tra & thử tải qua Mirror Proxy trước
                urls_to_try = [download_url]
                if "github.com" in download_url:
                    proxy_url = f"https://mirror.ghproxy.com/{download_url}"
                    urls_to_try = [proxy_url, download_url]
                    logger.info(f"[UPDATER] Thử tải qua mirror: {proxy_url}")
                else:
                    logger.info(f"[UPDATER] Tải trực tiếp: {download_url}")

                response = None
                for idx, url in enumerate(urls_to_try):
                    try:
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

                progress_win.after(0, progress_win.destroy)

                if not is_frozen:
                    def prompt_source_complete():
                        messagebox.showinfo(
                            "Đã tải xong",
                            f"Đã tải bản phát hành ({latest_version}) thành công!\n\n"
                            f"Đường dẫn file: {new_exe_name}\n"
                            f"(Do chạy từ mã nguồn .py nên ứng dụng không tự khởi động lại)",
                            parent=self.root
                        )
                    self.root.after(0, prompt_source_complete)
                    return

                if silent:
                    def prompt_apply():
                        msg = f"Đã tự động tải xong bản cập nhật mới ({latest_version}) trong nền.\n\n" \
                              f"Nội dung thay đổi:\n{changelog}\n\n" \
                              f"Bạn có muốn khởi động lại phần mềm để áp dụng ngay bây giờ không?"
                        if messagebox.askyesno("Đã tải xong bản cập nhật", msg, parent=self.root):
                            self._apply_update_windows(current_exe, new_exe_path)
                    self.root.after(0, prompt_apply)
                else:
                    self.root.after(100, lambda: self._apply_update_windows(current_exe, new_exe_path))

            except Exception as e:
                logger.error(f"Lỗi tải file cập nhật: {e}")
                progress_win.after(0, progress_win.destroy)
                if not silent:
                    self.root.after(0, lambda: messagebox.showerror(
                        "Lỗi tải xuống",
                        f"Có lỗi xảy ra khi đang tải cập nhật:\n{e}"
                    ))

        threading.Thread(target=_download_thread, daemon=True).start()

    def _apply_update_windows(self, current_exe, new_exe_path):
        try:
            dir_name = os.path.dirname(current_exe)
            current_exe_name = os.path.basename(current_exe)
            new_exe_name = os.path.basename(new_exe_path)
            bat_path = os.path.join(dir_name, "updater.bat")
            ps1_path = os.path.join(dir_name, "apply_update.ps1")

            # Tạo kịch bản PowerShell bảo vệ configs và assets tuyệt đối
            ps1_content = f"""$ErrorActionPreference = "SilentlyContinue"

# 1. Tu dong sao luu thu muc configs truoc khi cap nhat
if (Test-Path "configs") {{
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $bkDir = "backup_configs\\backup_$timestamp"
    New-Item -ItemType Directory -Path $bkDir -Force | Out-Null
    Copy-Item "configs\\*" -Destination $bkDir -Recurse -Force
}}

$zip = "{new_exe_name}"
if ($zip -like "*.zip" -and (Test-Path $zip)) {{
    $tempDir = "_update_temp"
    if (Test-Path $tempDir) {{
        Remove-Item $tempDir -Recurse -Force
    }}

    # Giai nen goi cap nhat vao thu muc tam
    Expand-Archive -Path $zip -DestinationPath $tempDir -Force

    # Truong hop goi zip duoc dong goi boc trong thu muc con
    $src = $tempDir
    if (Test-Path "$tempDir\\autokvtm_pro\\autokvtm_pro.exe") {{
        $src = "$tempDir\\autokvtm_pro"
    }}

    # Cap nhat file thuc thi chinh
    if (Test-Path "$src\\{current_exe_name}") {{
        Copy-Item "$src\\{current_exe_name}" -Destination ".\\{current_exe_name}" -Force
    }}

    # Cap nhat toan bo nhan code va thu vien he thong (_internal)
    if (Test-Path "$src\\_internal") {{
        Copy-Item "$src\\_internal\\*" -Destination ".\\_internal" -Recurse -Force
    }}

    # Cap nhat tools (tesseract) neu co
    if (Test-Path "$src\\tools") {{
        Copy-Item "$src\\tools\\*" -Destination ".\\tools" -Recurse -Force
    }}

    # BAO VE ASSETS: Chi bo sung anh moi, TUYET DOI KHONG ghi de anh cu cua nguoi dung
    if (Test-Path "$src\\assets") {{
        $baseSrc = (Resolve-Path "$src\\assets").Path
        Get-ChildItem -Path "$src\\assets" -Recurse | ForEach-Object {{
            if (-not $_.PSIsContainer) {{
                $rel = $_.FullName.Substring($baseSrc.Length + 1)
                $dst = Join-Path "assets" $rel
                if (-not (Test-Path $dst)) {{
                    $parent = Split-Path $dst -Parent
                    if (-not (Test-Path $parent)) {{ New-Item -ItemType Directory -Path $parent -Force | Out-Null }}
                    Copy-Item $_.FullName -Destination $dst -Force
                }}
            }}
        }}
    }}

    # BAO VE CONFIGS: Chi bo sung file config moi tinh, TUYET DOI KHONG ghi de file da co
    if (Test-Path "$src\\configs") {{
        $baseSrcCfg = (Resolve-Path "$src\\configs").Path
        Get-ChildItem -Path "$src\\configs" -Recurse | ForEach-Object {{
            if (-not $_.PSIsContainer) {{
                $rel = $_.FullName.Substring($baseSrcCfg.Length + 1)
                $dst = Join-Path "configs" $rel
                if (-not (Test-Path $dst)) {{
                    $parent = Split-Path $dst -Parent
                    if (-not (Test-Path $parent)) {{ New-Item -ItemType Directory -Path $parent -Force | Out-Null }}
                    Copy-Item $_.FullName -Destination $dst -Force
                }}
            }}
        }}
    }}

    # Don dep file tam
    Remove-Item $tempDir -Recurse -Force
    Remove-Item $zip -Force
}} elseif (Test-Path "{new_exe_name}") {{
    # Truong hop ha cap ve ban .exe don le cu
    Copy-Item "{new_exe_name}" -Destination "{current_exe_name}" -Force
    Remove-Item "{new_exe_name}" -Force
}}
"""
            with open(ps1_path, "w", encoding="utf-8") as f:
                f.write(ps1_content)

            bat_content = f"""@echo off
set _MEIPASS=
set _MEIPASS2=
set _PYI_ARCHIVE_FILE=
set _PYI_APPLICATION_HOME_DIR=
set _PYI_PARENT_PROCESS_LEVEL=
set _PYI_SPLASH_IPC=
set PYINSTALLER_PARENT_PID=
set PYINSTALLER_STRICT_UNPACK_MODE=
set PYTHONHOME=
set PYTHONPATH=
timeout /t 1 /nobreak >nul
:loop
taskkill /f /im "{current_exe_name}" >nul 2>&1
timeout /t 1 /nobreak >nul
powershell -ExecutionPolicy Bypass -File "apply_update.ps1"
start "" "{current_exe_name}"
timeout /t 1 /nobreak >nul
del "apply_update.ps1" >nul 2>&1
del "%~f0" >nul 2>&1
"""
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write(bat_content)

            clean_env = {
                k: v for k, v in os.environ.items()
                if not (k.startswith('_PYI') or k.startswith('PYI') or 'MEI' in k or k in ('PYTHONHOME', 'PYTHONPATH'))
            }

            flags = 0
            if hasattr(subprocess, 'CREATE_NEW_PROCESS_GROUP'):
                flags |= subprocess.CREATE_NEW_PROCESS_GROUP
            if hasattr(subprocess, 'DETACHED_PROCESS'):
                flags |= subprocess.DETACHED_PROCESS

            subprocess.Popen(["cmd.exe", "/c", bat_path], cwd=dir_name, env=clean_env, creationflags=flags)
            sys.exit(0)
        except Exception as e:
            logger.error(f"Lỗi khởi động updater.bat: {e}")
            messagebox.showerror(
                "Lỗi cập nhật",
                f"Không thể áp dụng bản cập nhật tự động:\n{e}"
            )
