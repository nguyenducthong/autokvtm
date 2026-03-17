"""
Simple GUI to compare template images against a search image
and visualize match locations.
"""

import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import cv2
import numpy as np


class TemplateMatchGUI:
    def __init__(self, parent=None):
        self.root = tk.Toplevel(parent) if parent else tk.Tk()
        self.root.title("Template Compare")
        self.root.geometry("1200x800")

        self.template1_path = None
        self.template2_path = None
        self.search_path = None

        self.search_image = None  # BGR
        self.display_image = None  # PIL
        self.photo_image = None
        self.template1_photo = None
        self.template2_photo = None

        self._build_ui()

    def _build_ui(self):
        toolbar = tk.Frame(self.root, bg="#34495e", height=45)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)

        tk.Label(
            toolbar,
            text="Template Compare",
            fg="white",
            bg="#34495e",
            font=("Arial", 11, "bold"),
            padx=10
        ).pack(side=tk.LEFT)

        tk.Button(
            toolbar,
            text="Open Search Image",
            command=self.load_search_image,
            bg="#3498db",
            fg="white",
            relief=tk.FLAT,
            padx=10,
            cursor="hand2"
        ).pack(side=tk.RIGHT, padx=5, pady=6)

        content = tk.Frame(self.root)
        content.pack(fill=tk.BOTH, expand=True)

        # Left: image viewer
        left = tk.Frame(content, bg="#2c3e50")
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(
            left,
            text="Search Image (result will be drawn here)",
            bg="#2c3e50",
            fg="white",
            font=("Arial", 10, "bold"),
            pady=6
        ).pack()

        canvas_frame = tk.Frame(left)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        h_scroll = tk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        v_scroll = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas = tk.Canvas(
            canvas_frame,
            bg="#34495e",
            xscrollcommand=h_scroll.set,
            yscrollcommand=v_scroll.set
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        h_scroll.config(command=self.canvas.xview)
        v_scroll.config(command=self.canvas.yview)

        # Right: controls and template previews
        right = tk.Frame(content, bg="#ecf0f1", width=320)
        right.pack(side=tk.RIGHT, fill=tk.Y)
        right.pack_propagate(False)

        tpl_frame = tk.LabelFrame(
            right,
            text="Templates",
            font=("Arial", 10, "bold"),
            bg="#ecf0f1",
            padx=10,
            pady=10
        )
        tpl_frame.pack(fill=tk.X, padx=10, pady=10)

        # Template 1
        tk.Label(tpl_frame, text="Template 1:", bg="#ecf0f1").pack(anchor=tk.W)
        tk.Button(
            tpl_frame,
            text="Open Template 1",
            command=lambda: self.load_template(1),
            bg="#27ae60",
            fg="white",
            relief=tk.FLAT,
            cursor="hand2"
        ).pack(fill=tk.X, pady=(4, 6))
        self.template1_label = tk.Label(tpl_frame, bg="white", relief=tk.SUNKEN, bd=1)
        self.template1_label.pack(fill=tk.X)

        # Template 2
        tk.Label(tpl_frame, text="Template 2:", bg="#ecf0f1").pack(anchor=tk.W, pady=(10, 0))
        tk.Button(
            tpl_frame,
            text="Open Template 2",
            command=lambda: self.load_template(2),
            bg="#e67e22",
            fg="white",
            relief=tk.FLAT,
            cursor="hand2"
        ).pack(fill=tk.X, pady=(4, 6))
        self.template2_label = tk.Label(tpl_frame, bg="white", relief=tk.SUNKEN, bd=1)
        self.template2_label.pack(fill=tk.X)

        control_frame = tk.LabelFrame(
            right,
            text="Compare",
            font=("Arial", 10, "bold"),
            bg="#ecf0f1",
            padx=10,
            pady=10
        )
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(control_frame, text="Threshold (0-1):", bg="#ecf0f1").pack(anchor=tk.W)
        self.threshold_entry = tk.Entry(control_frame)
        self.threshold_entry.pack(fill=tk.X, pady=4)
        self.threshold_entry.insert(0, "0.80")

        tk.Button(
            control_frame,
            text="Compare",
            command=self.compare_templates,
            bg="#3498db",
            fg="white",
            relief=tk.FLAT,
            cursor="hand2"
        ).pack(fill=tk.X, pady=(6, 2))

        tk.Button(
            control_frame,
            text="Clear Result",
            command=self.reset_view,
            bg="#95a5a6",
            fg="white",
            relief=tk.FLAT,
            cursor="hand2"
        ).pack(fill=tk.X, pady=2)

        self.result_text = tk.Text(
            right,
            height=10,
            wrap=tk.WORD,
            bg="white"
        )
        self.result_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self._set_result("No image loaded.")

    def _set_result(self, text):
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(1.0, text)

    def load_search_image(self):
        path = filedialog.askopenfilename(
            title="Open Search Image",
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp"), ("All files", "*.*")]
        )
        if not path:
            return
        img = cv2.imread(path)
        if img is None:
            messagebox.showerror("Error", "Failed to load image.")
            return
        self.search_path = path
        self.search_image = img
        self._display_search_image(img)
        h, w = img.shape[:2]
        self._set_result(f"Search image loaded: {w}x{h}\n{path}")

    def load_template(self, idx: int):
        path = filedialog.askopenfilename(
            title=f"Open Template {idx}",
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp"), ("All files", "*.*")]
        )
        if not path:
            return
        img = cv2.imread(path)
        if img is None:
            messagebox.showerror("Error", "Failed to load template.")
            return
        preview = self._make_preview(img, max_size=180)
        if idx == 1:
            self.template1_path = path
            self.template1_photo = ImageTk.PhotoImage(preview)
            self.template1_label.config(image=self.template1_photo)
        else:
            self.template2_path = path
            self.template2_photo = ImageTk.PhotoImage(preview)
            self.template2_label.config(image=self.template2_photo)

    def _make_preview(self, img_bgr, max_size=200):
        rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        w, h = pil_img.size
        scale = min(max_size / max(w, h), 1.0)
        new_w, new_h = int(w * scale), int(h * scale)
        if new_w < 1:
            new_w = 1
        if new_h < 1:
            new_h = 1
        return pil_img.resize((new_w, new_h), Image.LANCZOS)

    def _display_search_image(self, img_bgr):
        rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        self.display_image = pil_img
        self.photo_image = ImageTk.PhotoImage(pil_img)
        self.canvas.delete("all")
        self.canvas.config(scrollregion=(0, 0, pil_img.width, pil_img.height))
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo_image)

    def reset_view(self):
        if self.search_image is None:
            return
        self._display_search_image(self.search_image)
        self._set_result("Result cleared.")

    def compare_templates(self):
        if self.search_image is None:
            messagebox.showwarning("Missing", "Please load a search image first.")
            return

        t1 = self.template1_path
        t2 = self.template2_path
        if not t1 and not t2:
            messagebox.showwarning("Missing", "Please load at least one template.")
            return

        try:
            threshold = float(self.threshold_entry.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Threshold must be a number between 0 and 1.")
            return

        if threshold <= 0 or threshold > 1:
            messagebox.showerror("Error", "Threshold must be in (0, 1].")
            return

        screen = self.search_image.copy()
        gray_screen = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)

        results = []

        if t1:
            res = self._match_one(gray_screen, screen, t1, color=(0, 255, 0), label="T1", threshold=threshold)
            if res:
                results.append(res)

        if t2:
            res = self._match_one(gray_screen, screen, t2, color=(0, 0, 255), label="T2", threshold=threshold)
            if res:
                results.append(res)

        if not results:
            self._set_result("No match found above threshold.")
            self._display_search_image(self.search_image)
            return

        for item in results:
            x, y, w, h, score, color, label = item
            cv2.rectangle(screen, (x, y), (x + w, y + h), color, 2)
            cv2.putText(
                screen,
                f"{label}:{score:.2f}",
                (x, max(10, y - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2
            )

        self._display_search_image(screen)
        msg_lines = ["Match result:"]
        for item in results:
            x, y, w, h, score, _color, label = item
            msg_lines.append(f"{label} at ({x},{y}) size {w}x{h} score {score:.3f}")
        self._set_result("\n".join(msg_lines))

    def _match_one(self, gray_screen, screen_bgr, template_path, color, label, threshold):
        template = cv2.imread(template_path, cv2.IMREAD_UNCHANGED)
        if template is None:
            return None
        if template.ndim == 3 and template.shape[2] == 4:
            tpl_bgr = template[:, :, :3]
            tpl_alpha = template[:, :, 3]
            tpl_mask = (tpl_alpha > 10).astype("uint8")
        else:
            tpl_bgr = template
            tpl_mask = None
        h, w = tpl_bgr.shape[:2]
        if h > gray_screen.shape[0] or w > gray_screen.shape[1]:
            return None

        gray_tpl = cv2.cvtColor(tpl_bgr, cv2.COLOR_BGR2GRAY)
        result = cv2.matchTemplate(gray_screen, gray_tpl, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)
        if locations[0].size == 0:
            return None

        # Sort candidates by score desc (limit for speed)
        candidates = []
        for pt in zip(*locations[::-1]):
            score = float(result[pt[1], pt[0]])
            candidates.append((score, pt[0], pt[1]))
        candidates.sort(reverse=True, key=lambda x: x[0])
        candidates = candidates[:120]

        for score, x, y in candidates:
            region = screen_bgr[y:y + h, x:x + w]
            if region.shape[0] != h or region.shape[1] != w:
                continue
            if self._color_pass(tpl_bgr, region, tpl_mask):
                return (x, y, w, h, score, color, label)
        return None

    def _color_pass(self, tpl_bgr, region_bgr, tpl_mask=None):
        # HSV dominant hue + saturation check to reject wrong colors
        tpl_hsv = cv2.cvtColor(tpl_bgr, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([tpl_hsv], [0], tpl_mask, [18], [0, 180])
        dominant_idx = int(np.argmax(hist))
        tpl_hue = (dominant_idx + 0.5) * (180.0 / 18.0)

        tpl_sat = tpl_hsv[:, :, 1]
        if tpl_mask is not None:
            sat_vals = tpl_sat[tpl_mask.astype(bool)]
        else:
            sat_vals = tpl_sat.flatten()
        tpl_sat_med = float(np.median(sat_vals)) if sat_vals.size > 0 else 0.0

        reg_hsv = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2HSV)
        reg_hist = cv2.calcHist([reg_hsv], [0], None, [18], [0, 180])
        reg_idx = int(np.argmax(reg_hist))
        reg_hue = (reg_idx + 0.5) * (180.0 / 18.0)
        reg_sat_med = float(np.median(reg_hsv[:, :, 1].flatten()))

        hue_diff = abs(tpl_hue - reg_hue)
        hue_diff = min(hue_diff, 180 - hue_diff)
        sat_ratio = (reg_sat_med + 1.0) / (tpl_sat_med + 1.0)

        if tpl_sat_med > 20:
            if hue_diff > 12:
                return False
            if not (0.85 <= sat_ratio <= 1.35):
                return False
            return True

        # Low saturation: fallback to mean color distance
        tpl_mean = np.mean(tpl_bgr.astype(np.float32), axis=(0, 1))
        reg_mean = np.mean(region_bgr.astype(np.float32), axis=(0, 1))
        color_dist = float(np.sqrt(np.sum((tpl_mean - reg_mean) ** 2)))
        return color_dist <= 80

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = TemplateMatchGUI()
    app.run()
