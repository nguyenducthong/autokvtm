from core.actions import main_loop
from core.ban_do import tim_cua_hang, dat_vp, select_kho2, nhat_vang,keo_cua_hang_sang_phai,len_may 
from core.thu_hoach import thuhoach
if __name__ == "__main__":
    print("AUTO KHU VƯỜN TRÊN MÂY – KHỞI ĐỘNG!")
    try:
        thuhoach()
    except Exception as e:
        print(f"LỖI: {e}")