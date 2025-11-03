from core.actions import main_loop
from core.ban_do import tim_cua_hang, dat_vp, select_kho2, nhat_vang,keo_cua_hang_sang_phai,len_may, lua_chon_vp
from core.thu_hoach import thuhoach
from config import WAREHOUSE_ITEM_KSK
import time
def hien_thi_menu_kho():
    print("\n" + "="*60)
    print("   CHỌN VẬT PHẨM ĐẶT VÀO KHO SỰ KIỆN (KSK)")
    print("="*60)
    for idx, item in enumerate(WAREHOUSE_ITEM_KSK, 1):
        print(f"  [{idx}] {item['name']}")
    print(f"  [0] Quay lại menu chính")
    print("-"*60)
def chon_va_dat_vp():
    while True:
        hien_thi_menu_kho()
        try:
            choice = input("Chọn vật phẩm (0 để quay lại): ").strip()
            if choice == "0":
                return
            idx = int(choice) - 1
            if 0 <= idx < len(WAREHOUSE_ITEM_KSK):
                item = WAREHOUSE_ITEM_KSK[idx]
                print(f"\nĐang đặt: {item['name']}...")
                try:
                    dat_vp(
                        item["path_warehouse_not_select"],
                        item["path_warehouse_select"],
                        item["path"],
                        10  # số lần đặt (có thể thêm menu chọn số lần sau)
                    )
                    print(f"Đã đặt xong: {item['name']}")
                except Exception as e:
                    print(f"Lỗi khi đặt {item['name']}: {e}")
                time.sleep(1)
            else:
                print("Lựa chọn không hợp lệ!")
        except ValueError:
            print("Vui lòng nhập số!")
        except KeyboardInterrupt:
            print("\nĐã hủy!")
            return

# === MENU CHÍNH ===
MENU_OPTIONS = {
    "1": ("Đặt vật phẩm vào kho sự kiện (KSK)", chon_va_dat_vp),
    # "2": ("Thu hoạch cây", lambda: print("Chưa triển khai")),
    "0": ("Thoát", lambda: exit(0))
}

def hien_thi_menu_chinh():
    print("\n" + "="*50)
    print("   AUTO KHU VƯỜN TRÊN MÂY – MENU CHÍNH")
    print("="*50)
    for key, (mo_ta, _) in MENU_OPTIONS.items():
        if key != "0":
            print(f"  [{key}] {mo_ta}")
    print(f"  [0] Thoát")
    print("-"*50)

def main():
    print("AUTO KHU VƯỜN TRÊN MÂY – KHỞI ĐỘNG!")
    while True:
        try:
            hien_thi_menu_chinh()
            choice = input("Nhập lựa chọn: ").strip()
            if choice in MENU_OPTIONS:
                ac, func = MENU_OPTIONS[choice]
                if choice == "0":
                    print("Tạm biệt!")
                    break
                print(f"\nChạy: {ac}")
                func()
            else:
                print("Lựa chọn không hợp lệ!")
            time.sleep(1)
        except KeyboardInterrupt:
            print("\nĐã dừng bởi người dùng!")
            break




if __name__ == "__main__":
    print("AUTO KHU VƯỜN TRÊN MÂY – KHỞI ĐỘNG!")
    main()
    # try:
    #     dat_vp("assets/items/kho_thanh_pham_0.png","assets/items/kho_thanh_pham.png", "assets/items/kho_tinh_dau_tao.png", 1)
    #     # lua_chon_vp("assets/items/kho_tinh_dau_tao.png")
    # except Exception as e:
    #     print(f"LỖI: {e}")