import os
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from config import CURRENT_VERSION
from gui.constants import BASE_DIR

try:
    import pyi_splash
except ImportError:
    pyi_splash = None


class DeviceButtonState:
    def __init__(self, owner, serial, state_key):
        self.owner = owner
        self.serial = serial
        self.state_key = state_key

    def config(self, **kwargs):
        if "state" in kwargs:
            new_state = kwargs["state"]
            def _apply():
                card = self.owner.device_cards.get(self.serial)
                if card:
                    card[self.state_key] = new_state
                    self.owner._update_device_row(self.serial)
                    self.owner._refresh_device_action_buttons()
            if hasattr(self.owner, "_ui_safe"):
                self.owner._ui_safe(_apply)
            else:
                _apply()


class TreeTooltip:
    def __init__(self, widget):
        self.widget = widget
        self.tip = None
        self.text = None
        self._after_id = None

    def show(self, text, x, y):
        self.cancel()
        if self.text == text and self.tip and self.tip.winfo_exists():
            return
        self.text = text
        # Chờ 250ms trước khi hiện tooltip để tránh nháy khi rê chuột lướt qua
        try:
            self._after_id = self.widget.after(250, lambda: self._create_tip(text, x, y))
        except Exception:
            pass

    def _create_tip(self, text, x, y):
        self.hide()
        self.text = text
        try:
            self.tip = tk.Toplevel(self.widget)
            self.tip.wm_overrideredirect(True)
            # Offset an toàn (+20, +25) để con trỏ chuột không chạm vào cửa sổ tooltip gây giật nháy
            self.tip.geometry(f"+{x + 20}+{y + 25}")
            self.tip.attributes("-topmost", True)
            label = tk.Label(self.tip, text=text, bg="#2c3e50", fg="white",
                             font=("Arial", 8), padx=6, pady=3, relief=tk.SOLID, bd=1)
            label.pack()
        except Exception:
            self.tip = None

    def cancel(self):
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def hide(self):
        self.cancel()
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


class SplashScreen:
    """Màn hình chờ (Loading / Splash Screen) xuất hiện khi ứng dụng khởi động."""

    def __init__(self, master):
        self.master = master
        self.window = tk.Toplevel(master)
        self.window.title("Khởi động Auto KVTM")
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.configure(bg="#1a1e24")

        # Kích thước và căn giữa màn hình
        w, h = 540, 290
        sx = self.window.winfo_screenwidth()
        sy = self.window.winfo_screenheight()
        x = (sx - w) // 2
        y = (sy - h) // 2
        self.window.geometry(f"{w}x{h}+{x}+{y}")

        # Đóng splash screen của PyInstaller nếu có
        try:
            if pyi_splash and hasattr(pyi_splash, "is_alive") and pyi_splash.is_alive():
                pyi_splash.close()
        except Exception:
            pass

        self._build_ui()

    def _build_ui(self):
        border_frame = tk.Frame(self.window, bg="#1a1e24", highlightbackground="#27ae60", highlightthickness=2)
        border_frame.pack(fill=tk.BOTH, expand=True)

        top_accent = tk.Frame(border_frame, bg="#27ae60", height=4)
        top_accent.pack(fill=tk.X, side=tk.TOP)

        content = tk.Frame(border_frame, bg="#1a1e24", padx=25, pady=18)
        content.pack(fill=tk.BOTH, expand=True)

        # Header: Icon + Title
        header_frame = tk.Frame(content, bg="#1a1e24")
        header_frame.pack(fill=tk.X, pady=(4, 10))

        # Icon
        self.icon_image = None
        icon_path = os.path.join(BASE_DIR, "assets", "icon", "app.ico")
        if os.path.exists(icon_path):
            try:
                pil_img = Image.open(icon_path).resize((64, 64), Image.Resampling.LANCZOS)
                self.icon_image = ImageTk.PhotoImage(pil_img)
                lbl_icon = tk.Label(header_frame, image=self.icon_image, bg="#1a1e24")
                lbl_icon.pack(side=tk.LEFT, padx=(0, 15))
            except Exception:
                pass

        text_frame = tk.Frame(header_frame, bg="#1a1e24")
        text_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        lbl_title = tk.Label(
            text_frame,
            text="AUTO KHU VƯỜN TRÊN MÂY",
            font=("Arial", 14, "bold"),
            fg="#ffffff",
            bg="#1a1e24",
            anchor="w"
        )
        lbl_title.pack(fill=tk.X)

        sub_frame = tk.Frame(text_frame, bg="#1a1e24")
        sub_frame.pack(fill=tk.X, pady=(3, 0))

        lbl_badge = tk.Label(
            sub_frame,
            text=f" v{CURRENT_VERSION} PRO ",
            font=("Arial", 8, "bold"),
            fg="#ffffff",
            bg="#27ae60",
            padx=4,
            pady=1
        )
        lbl_badge.pack(side=tk.LEFT, padx=(0, 8))

        lbl_desc = tk.Label(
            sub_frame,
            text="Hệ Thống Tự Động Hóa Nông Trại",
            font=("Arial", 9),
            fg="#95a5a6",
            bg="#1a1e24"
        )
        lbl_desc.pack(side=tk.LEFT)

        # Divider
        divider = tk.Frame(content, bg="#2c3e50", height=1)
        divider.pack(fill=tk.X, pady=(8, 12))

        # Status text & percentage frame
        status_frame = tk.Frame(content, bg="#1a1e24")
        status_frame.pack(fill=tk.X, pady=(0, 6))

        self.lbl_status = tk.Label(
            status_frame,
            text="Đang khởi tạo hệ thống...",
            font=("Arial", 9),
            fg="#ecf0f1",
            bg="#1a1e24",
            anchor="w"
        )
        self.lbl_status.pack(side=tk.LEFT)

        self.lbl_percent = tk.Label(
            status_frame,
            text="0%",
            font=("Arial", 9, "bold"),
            fg="#2ecc71",
            bg="#1a1e24"
        )
        self.lbl_percent.pack(side=tk.RIGHT)

        # Progress bar
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "Splash.Horizontal.TProgressbar",
            troughcolor="#2c3e50",
            background="#27ae60",
            bordercolor="#1a1e24",
            lightcolor="#2ecc71",
            darkcolor="#27ae60",
            thickness=8
        )

        self.progress = ttk.Progressbar(
            content,
            style="Splash.Horizontal.TProgressbar",
            mode="determinate",
            length=480
        )
        self.progress.pack(fill=tk.X, pady=(0, 10))
        self.progress["value"] = 0

        # Footer hint
        lbl_hint = tk.Label(
            content,
            text="Vui lòng chờ trong giây lát...",
            font=("Arial", 8, "italic"),
            fg="#7f8c8d",
            bg="#1a1e24"
        )
        lbl_hint.pack(side=tk.LEFT)

        self.window.update()

    def update_progress(self, percent: int, text: str):
        """Cập nhật tiến trình và thông báo trạng thái."""
        try:
            if not self.window.winfo_exists():
                return
            self.progress["value"] = percent
            self.lbl_percent.config(text=f"{percent}%")
            self.lbl_status.config(text=text)
            self.window.update()
        except Exception:
            pass

    def close(self):
        """Đóng màn hình chờ."""
        try:
            if self.window and self.window.winfo_exists():
                self.window.attributes("-topmost", False)
                self.window.destroy()
        except Exception:
            pass
        self.window = None
