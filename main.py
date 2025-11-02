from core.actions import main_loop
from core.ban_do import tim_cua_hang, dat_vp, select_kho2, nhat_vang,keo_cua_hang_sang_phai,len_may, lua_chon_vp
from core.thu_hoach import thuhoach
if __name__ == "__main__":
    print("AUTO KHU VƯỜN TRÊN MÂY – KHỞI ĐỘNG!")
    try:
        dat_vp("assets/items/kho_thanh_pham_0.png","assets/items/kho_thanh_pham.png", "assets/items/kho_tinh_dau_tao.png", 1)
        # lua_chon_vp("assets/items/kho_tinh_dau_tao.png")
    except Exception as e:
        print(f"LỖI: {e}")