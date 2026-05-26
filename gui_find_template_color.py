"""
GUI to test and visualize the find_template_color function.
Loads a screen image + template, runs find_template_color, and shows results.
"""

import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import cv2
import numpy as np
import os
import logging

from core.image import ImageProcessor

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class FindTemplateColorGUI:
    def __init__(self, parent=None):
        self.root = tk.Toplevel(parent) if parent else tk.Tk()
        self.root.title("Test find_template_color")
        self.root.geometry("1300x850")

        self.processor = ImageProcessor()

        self.screen_path = None
        self.screen_img = None  # BGR numpy
        self.template_path = None

        self.photo_image = None
        self.template_photo = None

        self._build_ui()

    def _build_ui(self):
        # Toolbar
        toolbar = tk.Frame(self.root, bg="#2c3e50", height=45)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)

        tk.Label(
            toolbar, text="Test find_template_color",
            fg="white", bg="#2c3e50", font=("Arial", 12, "bold"), padx=10
        ).pack(side=tk.LEFT)

        content = tk.Frame(self.root)
        content.pack(fill=tk.BOTH, expand=True)

        # Left: canvas
        left = tk.Frame(content, bg="#34495e")
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(left, text="Screen Image", bg="#34495e", fg="white",
                 font=("Arial", 10, "bold"), pady=4).pack()

        canvas_frame = tk.Frame(left)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        h_scroll = tk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        v_scroll = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas = tk.Canvas(
            canvas_frame, bg="#1e272e",
            xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        h_scroll.config(command=self.canvas.xview)
        v_scroll.config(command=self.canvas.yview)

        # Mouse coordinates
        self.coord_label = tk.Label(left, text="Mouse: (-, -)", bg="#34495e",
                                    fg="#bdc3c7", font=("Consolas", 9))
        self.coord_label.pack(anchor=tk.W, padx=8)
        self.canvas.bind("<Motion>", self._on_mouse_move)

        # Right: controls
        right = tk.Frame(content, bg="#ecf0f1", width=340)
        right.pack(side=tk.RIGHT, fill=tk.Y)
        right.pack_propagate(False)

        # Screen image
        screen_frame = tk.LabelFrame(right, text="Screen Image", bg="#ecf0f1",
                                     font=("Arial", 10, "bold"), padx=8, pady=8)
        screen_frame.pack(fill=tk.X, padx=8, pady=(8, 4))

        tk.Button(screen_frame, text="Load Screen Image",
                  command=self._load_screen, bg="#3498db", fg="white",
                  relief=tk.FLAT, cursor="hand2").pack(fill=tk.X)
        self.screen_info = tk.Label(screen_frame, text="No image loaded",
                                    bg="#ecf0f1", fg="#7f8c8d", wraplength=300,
                                    justify=tk.LEFT)
        self.screen_info.pack(anchor=tk.W, pady=(4, 0))

        # Template
        tpl_frame = tk.LabelFrame(right, text="Template", bg="#ecf0f1",
                                  font=("Arial", 10, "bold"), padx=8, pady=8)
        tpl_frame.pack(fill=tk.X, padx=8, pady=4)

        tk.Button(tpl_frame, text="Load Template",
                  command=self._load_template, bg="#27ae60", fg="white",
                  relief=tk.FLAT, cursor="hand2").pack(fill=tk.X)
        self.template_label = tk.Label(tpl_frame, bg="white", relief=tk.SUNKEN, bd=1)
        self.template_label.pack(fill=tk.X, pady=(6, 0))
        self.tpl_info = tk.Label(tpl_frame, text="No template loaded",
                                 bg="#ecf0f1", fg="#7f8c8d", wraplength=300,
                                 justify=tk.LEFT)
        self.tpl_info.pack(anchor=tk.W, pady=(4, 0))

        # Parameters
        param_frame = tk.LabelFrame(right, text="Parameters", bg="#ecf0f1",
                                    font=("Arial", 10, "bold"), padx=8, pady=8)
        param_frame.pack(fill=tk.X, padx=8, pady=4)

        tk.Label(param_frame, text="threshold (shape):", bg="#ecf0f1").pack(anchor=tk.W)
        self.threshold_entry = tk.Entry(param_frame)
        self.threshold_entry.pack(fill=tk.X, pady=(2, 6))
        self.threshold_entry.insert(0, "0.75")

        tk.Label(param_frame, text="color_threshold:", bg="#ecf0f1").pack(anchor=tk.W)
        self.color_threshold_entry = tk.Entry(param_frame)
        self.color_threshold_entry.pack(fill=tk.X, pady=(2, 6))
        self.color_threshold_entry.insert(0, "0.6")

        # Run button
        tk.Button(param_frame, text="Run find_template_color",
                  command=self._run_find, bg="#e74c3c", fg="white",
                  font=("Arial", 10, "bold"), relief=tk.FLAT,
                  cursor="hand2", pady=4).pack(fill=tk.X, pady=(6, 2))

        tk.Button(param_frame, text="Clear Result",
                  command=self._clear_result, bg="#95a5a6", fg="white",
                  relief=tk.FLAT, cursor="hand2").pack(fill=tk.X, pady=2)

        # Results
        result_frame = tk.LabelFrame(right, text="Result", bg="#ecf0f1",
                                     font=("Arial", 10, "bold"), padx=8, pady=8)
        result_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 8))

        self.result_text = tk.Text(result_frame, height=12, wrap=tk.WORD,
                                   bg="white", font=("Consolas", 9))
        self.result_text.pack(fill=tk.BOTH, expand=True)
        self._set_result("Ready. Load screen image and template to start.")

    def _set_result(self, text):
        self.result_text.delete("1.0", tk.END)
        self.result_text.insert("1.0", text)

    def _on_mouse_move(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        self.coord_label.config(text=f"Mouse: ({int(cx)}, {int(cy)})")

    def _load_screen(self):
        path = filedialog.askopenfilename(
            title="Open Screen Image",
            initialdir="assets/screenshots",
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp"), ("All", "*.*")]
        )
        if not path:
            return
        img = cv2.imread(path)
        if img is None:
            messagebox.showerror("Error", f"Cannot load: {path}")
            return
        self.screen_path = path
        self.screen_img = img
        self._display_screen(img)
        h, w = img.shape[:2]
        name = os.path.basename(path)
        self.screen_info.config(text=f"{name}\n{w}x{h}")
        self._set_result(f"Screen loaded: {name} ({w}x{h})")

    def _load_template(self):
        path = filedialog.askopenfilename(
            title="Open Template",
            initialdir="assets/items",
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp"), ("All", "*.*")]
        )
        if not path:
            return
        img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if img is None:
            messagebox.showerror("Error", f"Cannot load: {path}")
            return
        self.template_path = path

        # Preview
        if img.ndim == 3 and img.shape[2] == 4:
            display = img[:, :, :3]
        else:
            display = img
        preview = self._make_preview(display, 200)
        self.template_photo = ImageTk.PhotoImage(preview)
        self.template_label.config(image=self.template_photo)

        h, w = img.shape[:2]
        ch = img.shape[2] if img.ndim == 3 else 1
        name = os.path.basename(path)
        alpha_info = " (has alpha)" if ch == 4 else ""
        self.tpl_info.config(text=f"{name}\n{w}x{h}{alpha_info}")

    def _make_preview(self, img_bgr, max_size=200):
        rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        w, h = pil_img.size
        scale = min(max_size / max(w, h), 1.0)
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        return pil_img.resize((nw, nh), Image.LANCZOS)

    def _display_screen(self, img_bgr):
        rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        self.photo_image = ImageTk.PhotoImage(pil_img)
        self.canvas.delete("all")
        self.canvas.config(scrollregion=(0, 0, pil_img.width, pil_img.height))
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo_image)

    def _clear_result(self):
        if self.screen_img is not None:
            self._display_screen(self.screen_img)
        self._set_result("Result cleared.")

    def _run_find(self):
        if self.screen_img is None:
            messagebox.showwarning("Missing", "Load a screen image first.")
            return
        if self.template_path is None:
            messagebox.showwarning("Missing", "Load a template first.")
            return

        try:
            threshold = float(self.threshold_entry.get().strip())
            color_threshold = float(self.color_threshold_entry.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Threshold values must be numbers.")
            return

        if not (0 < threshold <= 1) or not (0 < color_threshold <= 1):
            messagebox.showerror("Error", "Thresholds must be in (0, 1].")
            return

        tpl_name = os.path.basename(self.template_path)
        self._set_result(f"Running find_template_color...\n"
                         f"Template: {tpl_name}\n"
                         f"threshold={threshold}, color_threshold={color_threshold}\n")

        # Run the actual function
        result = self.processor.find_template_color(
            template_path=self.template_path,
            threshold=threshold,
            color_threshold=color_threshold,
            screen_img=self.screen_img
        )

        # Also get detailed candidate info by running the matching manually
        details = self._get_detailed_results(threshold, color_threshold)

        # Draw result on screen
        screen_draw = self.screen_img.copy()
        template = cv2.imread(self.template_path, cv2.IMREAD_UNCHANGED)
        if template.ndim == 3 and template.shape[2] == 4:
            th, tw = template[:, :, :3].shape[:2]
        else:
            th, tw = template.shape[:2]

        lines = [f"Template: {tpl_name}",
                 f"threshold={threshold}, color_threshold={color_threshold}",
                 ""]

        if result is not None:
            cx, cy = result
            x = cx - tw // 2
            y = cy - th // 2

            # Draw green rectangle at match
            cv2.rectangle(screen_draw, (x, y), (x + tw, y + th), (0, 255, 0), 2)
            # Draw crosshair at center
            cv2.drawMarker(screen_draw, (cx, cy), (0, 0, 255), cv2.MARKER_CROSS, 20, 2)
            # Label
            cv2.putText(screen_draw, f"FOUND ({cx},{cy})",
                        (x, max(15, y - 8)), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (0, 255, 0), 2)

            lines.append(f"FOUND at ({cx}, {cy})")
            lines.append(f"Bounding box: ({x},{y}) -> ({x+tw},{y+th})")
        else:
            lines.append("NOT FOUND")

        lines.append("")
        lines.append("--- Candidates ---")

        # Draw all candidates
        if details:
            for i, (dx, dy, shape_s, color_s, combined_s, passed) in enumerate(details):
                color = (0, 255, 0) if passed else (0, 0, 255)
                cv2.rectangle(screen_draw, (dx, dy), (dx + tw, dy + th), color, 1)
                label = f"#{i+1} s={shape_s:.2f} c={color_s:.2f}"
                cv2.putText(screen_draw, label, (dx, max(12, dy - 4)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

                status = "PASS" if passed else "REJECT"
                lines.append(
                    f"#{i+1} ({dx},{dy}): shape={shape_s:.3f} "
                    f"color={color_s:.3f} combined={combined_s:.3f} [{status}]"
                )
        else:
            lines.append("No candidates found (no shape match above threshold)")

        self._display_screen(screen_draw)
        self._set_result("\n".join(lines))

    def _get_detailed_results(self, threshold, color_threshold):
        """Re-run the matching logic to get per-candidate details for display."""
        template = cv2.imread(str(self.template_path), cv2.IMREAD_UNCHANGED)
        if template is None:
            return []

        alpha_mask = None
        if template.ndim == 3 and template.shape[2] == 4:
            alpha_mask = template[:, :, 3]
            alpha_mask = (alpha_mask > 10).astype(np.uint8) * 255
            template_bgr = template[:, :, :3]
        else:
            template_bgr = template

        th, tw = template_bgr.shape[:2]
        screen = self.screen_img

        if th > screen.shape[0] or tw > screen.shape[1]:
            return []

        result = cv2.matchTemplate(screen, template_bgr, cv2.TM_CCOEFF_NORMED)

        locations = np.where(result >= threshold)
        candidates = []
        used = []

        for pt in zip(*locations[::-1]):
            is_dup = False
            for u in used:
                if abs(pt[0] - u[0]) < tw // 2 and abs(pt[1] - u[1]) < th // 2:
                    is_dup = True
                    break
            if not is_dup:
                score = float(result[pt[1], pt[0]])
                candidates.append((pt[0], pt[1], score))
                used.append(pt)

        if not candidates:
            return []

        tpl_hsv = cv2.cvtColor(template_bgr, cv2.COLOR_BGR2HSV)
        h_bins, s_bins = 30, 32
        hist_ranges = [0, 180, 0, 256]
        tpl_hist = cv2.calcHist([tpl_hsv], [0, 1], alpha_mask, [h_bins, s_bins], hist_ranges)
        cv2.normalize(tpl_hist, tpl_hist, 0, 1, cv2.NORM_MINMAX)

        details = []
        for (x, y, shape_score) in candidates:
            region = screen[y:y+th, x:x+tw]
            if region.shape[0] != th or region.shape[1] != tw:
                continue

            reg_hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
            reg_hist = cv2.calcHist([reg_hsv], [0, 1], alpha_mask, [h_bins, s_bins], hist_ranges)
            cv2.normalize(reg_hist, reg_hist, 0, 1, cv2.NORM_MINMAX)

            color_score = cv2.compareHist(tpl_hist, reg_hist, cv2.HISTCMP_CORREL)
            combined = 0.4 * shape_score + 0.6 * color_score
            passed = color_score >= color_threshold

            details.append((x, y, shape_score, color_score, combined, passed))

        details.sort(key=lambda d: (0.4 * d[2] + 0.6 * d[3]), reverse=True)
        return details

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = FindTemplateColorGUI()
    app.run()
