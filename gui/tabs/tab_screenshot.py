import os
import sys
import time
import json
import logging
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk

import cv2
from core.adb_helper import get_adb_helper
from core.adb import ADBController
from gui.constants import BASE_DIR, REGION_FROM_CROP

logger = logging.getLogger(__name__)


class ScreenshotTabMixin:
    """Tab 4: Chụp ảnh màn hình LDPlayer, cắt vùng và kiểm tra nhận diện AI (YOLO/Gemini)."""
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
    def _ss_refresh_devices(self, silent=True):
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
            if not silent and isinstance(e, (FileNotFoundError, OSError)):
                if messagebox.askyesno(
                    "Lỗi ADB",
                    "Không tìm thấy ADB!\n\nBạn có muốn chọn thư mục LDPlayer thủ công không?",
                    parent=self.root
                ):
                    if self._choose_adb_path():
                        self._ss_refresh_devices(silent=False)

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

