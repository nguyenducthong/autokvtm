import os
import sys
import time
import shutil
import subprocess
import logging
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk

from core.image import get_resource_path
from gui.constants import BASE_DIR

logger = logging.getLogger(__name__)


class CoreImagesTabMixin:
    """Tab 6: Quản lý và thay thế các hình ảnh cốt lõi (Core) của game."""
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

