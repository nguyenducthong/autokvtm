"""
Ban do - Bán vật phẩm tại cửa hàng
Flow: Kiểm tra vị trí → về nhà nếu cần → mở cửa hàng → tìm ô trống (kéo trái nếu cần)
      → click → chọn kho → tìm VP → đặt bán (bật/tắt QC)
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from .adb import ADBController
from .image import ImageProcessor
from config import INDEX_CUA_HANG_MAC_DINH
from utils.utils import (
    _detect_current_row, xuong_nha, xuong_may,
    set_state, get_state, PlayerState
)
import time
import logging
import cv2
import random
from datetime import datetime

logger = logging.getLogger(__name__)
img = ImageProcessor()
MAX_ATTEMPTS = 3
THRESHOLD = 0.85
CLICK_DELAY = 1.0

# Debug mode — bật để lưu screenshot + kết quả match vào debug/ban_do/
DEBUG_MODE = False
DEBUG_DIR = "debug/ban_do"

# Per-thread state cho ban_do
import threading as _threading
_bd_ctx = _threading.local()

def set_debug_mode(enabled: bool):
    global DEBUG_MODE
    DEBUG_MODE = enabled
    if enabled:
        os.makedirs(DEBUG_DIR, exist_ok=True)
        logger.info(f"[DEBUG] Ban do debug mode ON — lưu ảnh tại {DEBUG_DIR}/")

def _set_stop_event(event):
    """Set stop_event cho thread hiện tại (thread-local, an toàn multi-nick)."""
    _bd_ctx.stop_event = event

def _get_stop_event():
    return getattr(_bd_ctx, 'stop_event', None)

def _should_stop():
    ev = _get_stop_event()
    return ev is not None and ev.is_set()

def _sleep(seconds):
    """Sleep có thể bị interrupt bởi stop_event."""
    ev = _get_stop_event()
    if ev is not None:
        ev.wait(seconds)
    else:
        time.sleep(seconds)


# ================================================================
# HELPER: Screenshot + tìm ảnh + Debug
# ================================================================
def _save_debug_screenshot(screen, template_path, pos, step_name):
    """Lưu screenshot debug với khung match (nếu tìm thấy)."""
    if not DEBUG_MODE or screen is None:
        return
    try:
        os.makedirs(DEBUG_DIR, exist_ok=True)
        ts = datetime.now().strftime("%H%M%S_%f")[:-3]
        tpl_name = os.path.basename(template_path).replace(".png", "")
        status = "FOUND" if pos else "NOT_FOUND"
        filename = f"{ts}_{step_name}_{tpl_name}_{status}.png"
        save_path = os.path.join(DEBUG_DIR, filename)

        debug_img = screen.copy()

        if pos:
            # Vẽ khung xanh lá quanh vị trí tìm thấy
            template = cv2.imread(str(template_path), cv2.IMREAD_UNCHANGED)
            if template is not None:
                th, tw = template.shape[:2]
                cx, cy = pos
                cv2.rectangle(debug_img,
                              (cx - tw // 2, cy - th // 2),
                              (cx + tw // 2, cy + th // 2),
                              (0, 255, 0), 2)
                cv2.putText(debug_img, f"FOUND ({cx},{cy})",
                            (cx - tw // 2, cy - th // 2 - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        else:
            # Vẽ chữ đỏ NOT FOUND
            cv2.putText(debug_img, f"NOT FOUND: {tpl_name}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        # Ghi tên step + thời gian
        cv2.putText(debug_img, f"[{step_name}] {ts}",
                    (10, debug_img.shape[0] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

        cv2.imwrite(save_path, debug_img)
        logger.debug(f"[DEBUG] Saved: {save_path}")
    except Exception as e:
        logger.debug(f"[DEBUG] Lỗi lưu debug: {e}")


def _find(adb, template_path, threshold=THRESHOLD, color_threshold=0.6, step_name="find"):
    """Chụp màn hình rồi tìm template, trả về (x,y) hoặc None."""
    screen = adb.screenshot_full()
    if screen is None:
        return None, None
    pos = img.find_template_color(template_path=template_path, threshold=threshold,
                                  color_threshold=color_threshold, screen_img=screen)
    _save_debug_screenshot(screen, template_path, pos, step_name)
    return pos, screen


def _find_on_screen(screen, template_path, threshold=THRESHOLD, color_threshold=0.6,
                    step_name="find_cached"):
    """Tìm template trên screen đã chụp sẵn."""
    if screen is None:
        return None
    pos = img.find_template_color(template_path=template_path, threshold=threshold,
                                  color_threshold=color_threshold, screen_img=screen)
    _save_debug_screenshot(screen, template_path, pos, step_name)
    return pos


def _find_match(adb, template_path, threshold=THRESHOLD):
    """Dùng _match_one (grayscale) cho các nút cố định."""
    screen = adb.screenshot_full()
    if screen is None:
        return None
    return img._match_one(template_path=template_path, threshold=threshold, screen_img=screen)


# ================================================================
# HELPER: Đóng popup bằng nút X (an toàn hơn press_key Back)
# ================================================================
NUT_X_PATH = "assets/items/nut_x.png"


def _dong_popup(adb):
    """Đóng popup/dialog bằng cách tìm và bấm nút X.
    An toàn hơn press_key(4) vì Back có thể thoát game."""
    pos, _ = _find(adb, NUT_X_PATH, threshold=0.85, step_name="dong_popup_x")
    if pos:
        x, y = pos
        _btn_cache["nut_x"] = pos  # Cache lại
        logger.info(f"Bấm nút X đóng popup tại ({x}, {y})")
        adb.tap(x, y, 0.1)
        _sleep(0.5)
        return True

    # # Không tìm thấy X → thử cache
    # if "nut_x" in _btn_cache:
    #     x, y = _btn_cache["nut_x"]
    #     logger.info(f"Bấm nút X (cache) tại ({x}, {y})")
    #     adb.tap(x, y, 0.1)
    #     _sleep(0.5)
    #     return True

    logger.warning("Không tìm thấy nút X")
    return False


# ================================================================
# STEP 0: Kiểm tra vị trí hiện tại → về nhà nếu cần
# ================================================================
def ve_nha_neu_can(adb):
    """Kiểm tra đang ở hàng nào.
    - Nếu đang ở hàng > 0 (trên máy) → xuống nhà (hàng 0) trước.
    - Nếu đang ở hàng 0 hoặc không nhận diện được → bỏ qua.
    Return True nếu đã ở hàng 0 hoặc về được."""
    if _should_stop():
        return False

    current_row = _detect_current_row(take_screenshot=True)
    if current_row is None:
        logger.info("Không nhận diện được hàng, thử tiếp...")
        return True  # Không chắc ở đâu, cứ tiếp tục

    if current_row == 0:
        logger.info("Đang ở hàng 0 (nhà), OK")
        set_state(PlayerState.TANG_0)
        return True
    logger.info(f"Đang ở hàng {current_row}, cần về nhà trước...")
    if current_row == 1 or current_row == 2:
        xuong_may()
    else:
        xuong_nha()
    _sleep(0.5)

    # Verify
    verify_row = _detect_current_row(take_screenshot=True)
    if verify_row is not None and verify_row == 0:
        logger.info("Đã về nhà thành công")
        return True

    # Nếu chưa về được, thử lại 1 lần
    logger.warning(f"Chưa về nhà (đang hàng {verify_row}), thử lại...")
    xuong_nha()
    _sleep(0.5)
    return True


# ================================================================
# STEP 1: Check đang ở cửa hàng → mở nếu chưa
# ================================================================
def check_cua_hang(adb):
    """Kiểm tra đang ở cửa hàng bằng quay_hang_on.png.
    Nếu chưa ở → về nhà → mở cửa hàng.
    Return True nếu OK."""
    if _should_stop():
        return False

    # Kiểm tra đã ở cửa hàng chưa
    pos, _ = _find(adb, "assets/items/quay_hang_on.png", step_name="check_cua_hang")
    if pos:
        logger.info("Đã ở cửa hàng")
        set_state(PlayerState.CUA_HANG)
        return True

    # Chưa ở cửa hàng → về nhà trước
    logger.info("Chưa ở cửa hàng, kiểm tra vị trí...")
    ve_nha_neu_can(adb)

    if _should_stop():
        return False

    # Đóng popup nếu có
    _dong_popup(adb)

    # Tap vào vị trí cửa hàng mặc định
    x, y = INDEX_CUA_HANG_MAC_DINH
    adb.tap(x, y)
    _sleep(CLICK_DELAY)

    # Kiểm tra lại
    pos, _ = _find(adb, "assets/items/quay_hang_on.png", step_name="check_cua_hang_retry1")
    if pos:
        logger.info("Đã mở cửa hàng thành công")
        set_state(PlayerState.CUA_HANG)
        return True

    # Retry: đóng popup rồi tap lại
    logger.warning("Lần 1 không mở được, thử lại...")
    _dong_popup(adb)
    adb.tap(x, y)
    _sleep(CLICK_DELAY)

    pos, _ = _find(adb, "assets/items/quay_hang_on.png", step_name="check_cua_hang_retry2")
    if pos:
        logger.info("Đã mở cửa hàng thành công (retry)")
        set_state(PlayerState.CUA_HANG)
        return True

    logger.warning("Không mở được cửa hàng!")
    set_state(PlayerState.ERROR)
    return False


# ================================================================
# STEP 2: Tìm ô trống hoặc ô vàng để click (kéo trái nếu cần)
# ================================================================
# Quầy hàng: 20 ô tổng cộng, 8 ô hiển thị / màn hình
# Cần kéo (swipe) trong khung quầy để xem thêm ô
SWIPE_LEFT_MAX = 3   # 8 ô/màn → 3 màn = 24 ô > 20, nên 3 lần kéo đủ
QUAY_HANG_Y = 430    # Tọa độ y vùng quầy hàng (giữa các ô)
SWIPE_START_X = 400# Kéo từ bên phải
SWIPE_END_X = 200    # Kéo sang trái (~550px ≈ ~5-6 ô)
SWIPE_DURATION = 700 # ms — kéo vừa tay, không quá nhanh


def _nhat_vang(adb, screen):
    """Nhặt tất cả ô vàng trên màn hình hiện tại.
    Return screen mới sau khi nhặt xong."""
    set_state(PlayerState.NHAT_VANG)
    while True:
        if _should_stop():
            return screen
        pos = _find_on_screen(screen, "assets/items/vang3.png", threshold=0.9,
                              step_name="tim_o_vang")
        if not pos:
            break
        x, y = pos
        logger.info(f"Tìm thấy ô vàng tại ({x}, {y}) → tap thu hoạch")
        adb.tap(x, y, 0.1)
        _sleep(0.8)
        screen = adb.screenshot_full()
        if screen is None:
            break
    return screen


def _keo_quay_hang_sang_trai(adb):
    """Kéo (swipe) trong khung quầy hàng sang trái để xem thêm ô.
    Dùng swipe thay vì nút — kéo từ phải sang trái tại vùng y quầy hàng."""
    adb.swipe(SWIPE_START_X, QUAY_HANG_Y, SWIPE_END_X, QUAY_HANG_Y, SWIPE_DURATION)
    logger.info(f"Kéo quầy hàng sang trái: ({SWIPE_START_X},{QUAY_HANG_Y}) → ({SWIPE_END_X},{QUAY_HANG_Y})")


def tim_o_ban(adb, max_swipe=SWIPE_LEFT_MAX):
    """Tìm ô trống hoặc ô vàng trên quầy hàng.
    Ưu tiên: nhặt vàng → tìm ô trống.
    Nếu không tìm thấy → kéo (swipe) trong khung quầy sang trái,
    tối đa max_swipe lần (20 ô / 8 ô mỗi màn = ~3 lần kéo).
    Return (x,y) hoặc None."""
    set_state(PlayerState.TIM_O_BAN)
    if _should_stop():
        return None

    for swipe_i in range(max_swipe + 1):  # 0 = trang hiện tại, 1..max = sau kéo
        if _should_stop():
            return None

        screen = adb.screenshot_full()
        if screen is None:
            return None

        # Nhặt hết vàng trước
        screen = _nhat_vang(adb, screen)

        # Tìm ô trống
        pos_trong = _find_on_screen(screen, "assets/items/o_trong.png", threshold=0.9,
                                    step_name=f"tim_o_trong_swipe{swipe_i}")
        if pos_trong:
            logger.info(f"Tìm thấy ô trống tại {pos_trong} (sau {swipe_i} lần kéo)")
            return pos_trong

        # Không tìm thấy ô trống → kéo trong khung quầy sang trái
        if swipe_i < max_swipe:
            logger.info(f"Không tìm thấy ô trống, kéo quầy sang trái ({swipe_i+1}/{max_swipe})...")
            _keo_quay_hang_sang_trai(adb)
            _sleep(0.8)

    logger.warning(f"Không tìm thấy ô trống sau {max_swipe} lần kéo (đã xem hết 20 ô)")
    return None


# ================================================================
# STEP 3: Chọn kho (có retry + debug)
# ================================================================
def chon_kho(adb, path_kho_selected, path_kho_not_selected, max_retry=3):
    """Tìm và chọn kho. Retry nếu chụp quá sớm chưa kịp load UI.
    Return True/False."""
    set_state(PlayerState.MO_KHO)
    if _should_stop():
        return False

    for attempt in range(max_retry):
        if _should_stop():
            return False

        # Đợi UI load — tăng dần delay mỗi lần retry
        wait_time = CLICK_DELAY + (attempt * 0.5)
        _sleep(wait_time)

        screen = adb.screenshot_full()
        if screen is None:
            continue

        # Kho đã được chọn?
        pos = _find_on_screen(screen, path_kho_selected, threshold=0.7,
                              step_name=f"chon_kho_selected_try{attempt+1}")
        if pos:
            logger.info(f"Kho đã được chọn sẵn tại {pos} (lần {attempt+1})")
            return True

        # Kho chưa chọn → click vào
        pos = _find_on_screen(screen, path_kho_not_selected, threshold=0.7,
                              step_name=f"chon_kho_not_sel_try{attempt+1}")
        if pos:
            x, y = pos
            logger.info(f"Chọn kho tại ({x}, {y}) (lần {attempt+1})")
            adb.tap(x, y, 0.1)
            _sleep(0.5)
            return True

        logger.warning(f"Không tìm thấy kho lần {attempt+1}/{max_retry}, "
                       f"đợi thêm rồi chụp lại...")

    logger.error(f"Không tìm thấy kho sau {max_retry} lần thử!")
    return False


# ================================================================
# STEP 4: Tìm vật phẩm trong kho (fallback qua SP tiếp theo)
# ================================================================
def _normalize_vp_list(vp_list, default_threshold=THRESHOLD, default_color=0.6):
    """Chuẩn hóa vp_list thành list of dict.
    Input có thể là:
      - ["path1.png", "path2.png"]  (legacy, dùng default)
      - [{"path": "path1.png", "threshold": 0.85, "color_threshold": 0.7}, ...]
    Return: [{"path", "threshold", "color_threshold"}, ...]"""
    result = []
    for item in vp_list:
        if isinstance(item, str):
            result.append({
                "path": item,
                "threshold": default_threshold,
                "color_threshold": default_color
            })
        elif isinstance(item, dict):
            result.append({
                "path": item["path"],
                "threshold": item.get("threshold", default_threshold),
                "color_threshold": item.get("color_threshold", default_color)
            })
    return result


def tim_vat_pham(adb, path_vp, threshold=THRESHOLD, color_threshold=0.6):
    """Tìm vật phẩm trong kho bằng find_template_color.
    Return (x,y) hoặc None."""
    if _should_stop():
        return None
    _sleep(0.5)
    pos, _ = _find(adb, path_vp, threshold=threshold, color_threshold=color_threshold,
                   step_name="tim_vat_pham")
    if pos:
        logger.info(f"Tìm thấy VP '{path_vp}' tại {pos}")
        return pos

    logger.warning(f"Không tìm thấy VP: {path_vp}")
    return None


def tim_vat_pham_fallback(adb, vp_list, threshold=THRESHOLD, color_threshold=0.6):
    """Random thứ tự SP mỗi lần đặt. SP không thấy → thử SP kế tiếp.
    vp_list: list of str hoặc list of dict {"path", "threshold", "color_threshold"}
    Chụp 1 screenshot, tìm tất cả SP trên cùng ảnh đó.
    Return (path_vp, (x,y)) hoặc (None, None)."""
    if _should_stop():
        return None, None
    _sleep(0.5)
    screen = adb.screenshot_full()
    if screen is None:
        return None, None

    # Chuẩn hóa
    normalized = _normalize_vp_list(vp_list, threshold, color_threshold)

    # Random thứ tự mỗi lần → bán đều các SP
    shuffled = list(normalized)
    random.shuffle(shuffled)
    names = [os.path.basename(v["path"]).replace('.png', '') for v in shuffled]
    logger.info(f"Thử SP theo thứ tự: {names}")

    for vp_info in shuffled:
        if _should_stop():
            return None, None
        vp_path = vp_info["path"]
        name = os.path.basename(vp_path).replace('.png', '')
        pos = _find_on_screen(screen, vp_path, threshold=vp_info["threshold"],
                              color_threshold=vp_info["color_threshold"],
                              step_name=f"tim_vp_{name}")
        if pos:
            logger.info(f"Chọn VP '{name}' tại {pos} (t={vp_info['threshold']}, c={vp_info['color_threshold']})")
            return vp_path, pos
        logger.info(f"VP '{name}' không thấy (t={vp_info['threshold']}, c={vp_info['color_threshold']}), thử SP tiếp...")

    logger.warning(f"Tất cả {len(vp_list)} SP đều không thấy!")
    return None, None


# ================================================================
# STEP 5: Đặt bán + xử lý QC + xé kim cương (có cache nút)
# ================================================================

# Cache vị trí nút cố định — tìm 1 lần, dùng lại các lần sau
# Reset mỗi khi gọi main_ban_hang (session mới)
_btn_cache = {}


def _reset_btn_cache():
    """Reset cache nút khi bắt đầu session bán hàng mới."""
    global _btn_cache
    _btn_cache = {}
    logger.info("Reset cache vị trí nút")


def _find_btn(adb, screen, template_path, cache_key, threshold=0.9, step_name="btn"):
    """Tìm nút — dùng cache nếu đã tìm được trước đó.
    Nút cố định (QC, +, đặt bán) không đổi vị trí giữa các lần đặt.
    Return (x, y) hoặc None."""
    # Có cache → dùng luôn, không cần screenshot
    if cache_key in _btn_cache:
        pos = _btn_cache[cache_key]
        logger.debug(f"[CACHE] Dùng cache {cache_key}: {pos}")
        return pos

    # Chưa cache → tìm bằng template matching
    pos = _find_on_screen(screen, template_path, threshold=threshold,
                          step_name=step_name)
    if pos:
        _btn_cache[cache_key] = pos
        logger.info(f"[CACHE] Lưu {cache_key}: {pos}")
    return pos


def dat_ban(adb, bat_qc=True, xoa_kc=False):
    """Sau khi chọn VP, xử lý popup đặt bán:
    - Bật/tắt QC
    - Xé kim cương nếu cần
    - Bấm nút đặt bán
    Nút +, QC, đặt bán có vị trí cố định → cache lại sau lần đầu."""
    if _should_stop():
        return False
    _sleep(CLICK_DELAY)
    screen = adb.screenshot_full()
    if screen is None:
        return False

    # Bật/tắt quảng cáo
    pos_qc = _find_btn(adb, screen, "assets/items/cua_hang_qc.png",
                        "qc", threshold=0.9, step_name="dat_ban_qc")
    if pos_qc:
        if not bat_qc:
            x, y = pos_qc
            logger.info(f"Tắt quảng cáo tại ({x}, {y})")
            adb.tap(x, y, 0.1)
            _sleep(0.3)

    # Tăng số lượng (bấm nút +)
    pos_cong = _find_btn(adb, screen, "assets/items/cong.png",
                          "cong", threshold=0.9, step_name="dat_ban_cong")
    if pos_cong:
        x, y = pos_cong
        logger.info(f"Bấm + tăng số lượng tại ({x}, {y})")
        adb.taps(x, y, 8, 0.01)
        _sleep(0.3)
        # Nút + thứ 2 (giá bán) — cũng cache riêng
        screen = adb.screenshot_full()
        pos_cong2 = _find_btn(adb, screen, "assets/items/cong.png",
                               "cong2", threshold=0.9, step_name="dat_ban_cong2")
        if pos_cong2:
            x2, y2 = pos_cong2
            adb.taps(x2, y2, 8, 0.01)
            _sleep(0.3)

    # Xé kim cương nếu config bật
    if xoa_kc:
        screen = adb.screenshot_full()
        pos_kc = _find_btn(adb, screen, "assets/items/xoa_vp_kc.png",
                            "xe_kc", threshold=0.85, step_name="dat_ban_xe_kc")
        if pos_kc:
            x, y = pos_kc
            logger.info(f"Xé kim cương tại ({x}, {y})")
            adb.tap(x, y, 0.1)
            _sleep(0.5)

    # Bấm "Đặt bán"
    pos_ban = _find_btn(adb, screen, "assets/items/dat_ban.png",
                         "dat_ban", threshold=0.9, step_name="dat_ban_nut")
    if pos_ban:
        x, y = pos_ban
        logger.info(f"Đặt bán tại ({x}, {y})")
        adb.tap(x, y, 0.1)
        _sleep(CLICK_DELAY)
        return True

    # Cache miss cho đặt bán → chụp lại thử 1 lần
    screen = adb.screenshot_full()
    pos_ban = _find_on_screen(screen, "assets/items/dat_ban.png", threshold=0.9,
                              step_name="dat_ban_nut_retry")
    if pos_ban:
        _btn_cache["dat_ban"] = pos_ban
        x, y = pos_ban
        logger.info(f"Đặt bán tại ({x}, {y}) (retry)")
        adb.tap(x, y, 0.1)
        _sleep(CLICK_DELAY)
        return True

    logger.warning("Không tìm thấy nút đặt bán!")
    return False


# ================================================================
# STEP 4+5 kết hợp: Tìm VP + đặt bán, thử SP khác nếu fail
# ================================================================
def _thu_dat_ban_voi_fallback(adb, vp_list, path_kho_selected, path_kho_not_selected,
                               threshold, color_threshold, bat_qc, xoa_kc):
    """Tìm SP theo thứ tự random → click → đặt bán.
    vp_list: list of str (path) hoặc list of dict {"path", "threshold", "color_threshold"}
    Nếu SP đó không đặt được (hết hàng) → back ra kho → thử SP khác.
    Return True nếu đặt thành công, False nếu tất cả SP đều fail."""
    if _should_stop():
        return False

    # Chuẩn hóa vp_list thành list of dict
    normalized = _normalize_vp_list(vp_list, threshold, color_threshold)

    # Random thứ tự SP
    shuffled = list(normalized)
    random.shuffle(shuffled)
    tried = []  # SP đã thử rồi (fail)

    for vp_info in shuffled:
        if _should_stop():
            return False

        vp_path = vp_info["path"]
        vp_threshold = vp_info["threshold"]
        vp_color = vp_info["color_threshold"]
        name = os.path.basename(vp_path).replace('.png', '')

        # Nếu không phải lần đầu, cần quay lại màn chọn kho
        if tried:
            logger.info(f"Thử SP khác: {name} (đã thử {len(tried)} SP)")

        tried.append(name)

        # Tìm VP trên screen kho
        set_state(PlayerState.CHON_VP)
        _sleep(0.3)
        pos_vp, _ = _find(adb, vp_path, threshold=vp_threshold,
                          color_threshold=vp_color,
                          step_name=f"tim_vp_{name}")
        if not pos_vp:
            logger.info(f"SP '{name}' không thấy trong kho (t={vp_threshold}, c={vp_color}), thử SP tiếp...")
            continue

        # Click chọn VP
        vx, vy = pos_vp
        adb.tap(vx, vy, 0.1)
        _sleep(0.5)

        # Thử đặt bán
        set_state(PlayerState.DAT_BAN)
        ok = dat_ban(adb, bat_qc=bat_qc, xoa_kc=xoa_kc)
        if ok:
            logger.info(f"Đặt bán '{name}' thành công!")
            set_state(PlayerState.CUA_HANG)
            return True

        # Đặt bán fail (SP hết hoặc lỗi) → đóng popup về màn kho
        logger.info(f"SP '{name}' đặt bán fail, đóng popup thử SP khác...")
        _dong_popup(adb)

    logger.warning(f"Đã thử {len(tried)} SP đều fail: {tried}")
    # Đóng popup kho nếu còn mở, về nhà reset trạng thái
    _xu_ly_sau_dat_ban(adb)
    return False

# ================================================================
# (Nếu cần) STEP 6: Xử lý sau khi đặt bán (đóng popup cần thiết, đóng cửa hàng nếu cửa hàng đang mở)
# ================================================================
def _xu_ly_sau_dat_ban(adb):
    """Sau khi đặt bán, đảm bảo đóng popup về cửa hàng nếu còn mở.
    Nếu đang ở cửa hàng → về nhà luôn để reset trạng thái."""
    if _should_stop():
        return

    # Đóng popup về cửa hàng nếu còn mở
    _dong_popup(adb)

    # Kiểm tra nếu vẫn đang ở cửa hàng → về nhà luôn
    pos, _ = _find(adb, "assets/items/quay_hang_on.png", step_name="post_ban_check_cua_hang")
    if pos:
        logger.info("Vẫn đang ở cửa hàng sau khi đặt bán, về nhà để reset trạng thái...")
        # Tap vào vị trí cửa hàng mặc định
        x, y = INDEX_CUA_HANG_MAC_DINH
        adb.tap(x, y)
    else:
        logger.info("Đã thoát cửa hàng sau khi đặt bán, OK")                                               

def _xu_ly_dat_qc(adb, data_vps, threshold, color_threshold):
    """Nếu config có bật QC nhưng chưa đặt được QC nào, thử tìm 1 VP bất kỳ để bật QC.
    Tìm trên screen kho, nếu thấy VP đã đặt bán rồi (có thể dựa vào màu sắc) → click vào để bật QC."""
    if _should_stop():
        return False
    _sleep(0.5)
    screen = adb.screenshot_full()
    if screen is None:
        return False

    # Tìm VP đã đặt bán (có thể dựa vào màu sắc khác so với VP chưa đặt)
    for vp_info in data_vps:
        vp_path = vp_info["path"]
        vp_threshold = vp_info.get("threshold", threshold)
        vp_color = vp_info.get("color_threshold", color_threshold)
        name = os.path.basename(vp_path).replace('.png', '')
        pos = _find_on_screen(screen, vp_path, threshold=vp_threshold,
                              color_threshold=vp_color,
                              step_name=f"tim_vp_dat_qc_{name}")
        if pos:
            x, y = pos
            logger.info(f"Tìm thấy VP '{name}' đã đặt bán tại {pos}, click để bật QC")
            adb.tap(x, y, 0.1)
            _sleep(0.3)
            return True

    logger.warning("Không tìm thấy VP nào đã đặt bán để bật QC!")
    return False

def _xu_ly_xe_kc(adb , data_vps, threshold, color_threshold):
    """Nếu config có bật xé kim cương nhưng chưa xé được, thử tìm 1 VP bất kỳ để click vào nút xé KC.
    Tìm trên screen kho, nếu thấy VP đã đặt bán rồi (có thể dựa vào màu sắc) 
    Tìm bút xé KC → click vào để xé KC -> xác nhận -> return True."""

    if _should_stop():
        return False
    _sleep(0.5)
    screen = adb.screenshot_full()
    if screen is None:
        return False

    # Tìm VP đã đặt bán (có thể dựa vào màu sắc khác so với VP chưa đặt)
    for vp_info in data_vps:
        vp_path = vp_info["path"]
        vp_threshold = vp_info.get("threshold", threshold)
        vp_color = vp_info.get("color_threshold", color_threshold)
        name = os.path.basename(vp_path).replace('.png', '')
        pos = _find_on_screen(screen, vp_path, threshold=vp_threshold,
                              color_threshold=vp_color,
                              step_name=f"tim_vp_xe_kc_{name}")
        if pos:
            x, y = pos
            logger.info(f"Tìm thấy VP '{name}' đã đặt bán tại {pos}, click để bật xé KC")
            adb.tap(x, y, 0.1)

            pos_kc = _find_on_screen(screen, "assets/items/xoa_vp_kc.png", threshold=0.85,
                            step_name="xe_kc_after_click_vp")
            if pos_kc:
                x_kc, y_kc = pos_kc
                logger.info(f"Tìm thấy nút xé KC tại ({x_kc}, {y_kc}), click để xé")
                adb.tap(x_kc, y_kc, 0.1)

                pos_dong_y = _find_on_screen(screen, "assets/items/dong_y.png", threshold=0.85,
                            step_name="xe_kc_xac_nhan")
                if pos_dong_y:
                    x_dy, y_dy = pos_dong_y
                    logger.info(f"Tìm thấy nút Đồng ý tại ({x_dy}, {y_dy}), click để xác nhận xé KC")
                    adb.tap(x_dy, y_dy, 0.1)
                    _sleep(0.3)
                    return True

    logger.warning("Không tìm thấy VP nào đã đặt bán để bật xé KC!")
    return False
# ================================================================
# MAIN: Hàm chính chạy theo config
# ================================================================
def main_ban_hang(adb: ADBController, config: dict, stop_event=None):
    """
    Hàm bán hàng theo config từ GUI.

    config = {
        "loai_kho": "KTP",           # code kho (KSK, KNS, KTP)
        "so_lan_dat_vp": 4,          # số lần đặt VP (mỗi lần = 1 ô)
        "data": ["kho_tra_hoa_hong.png", "kho_vai_vang.png"],  # danh sách VP
        "xoa_kc": True,              # xé kim cương
        "dat_quang_cao": True         # bật/tắt QC
    }

    Flow mỗi lần:
      0. Kiểm tra vị trí → nếu đang ở máy/hàng → về nhà (hàng 0)
      1. Mở cửa hàng (quay_hang_on.png)
      2. Tìm ô trống/vàng → kéo trái nếu không thấy → click
      3. Chọn kho → tìm VP (SP1 hết → thử SP2 → SP3...) → đặt bán
      * Nút +, QC, đặt bán cache vị trí sau lần đầu → nhanh hơn
    """
    if stop_event:
        _set_stop_event(stop_event)

    # Reset cache nút mỗi session
    _reset_btn_cache()

    # Bật debug mode nếu config yêu cầu
    if config.get("debug", False):
        set_debug_mode(True)

    from config import CONFIG_LOAI_KHO

    so_lan = config.get("so_lan_dat_vp", 4)
    loai_kho = config.get("loai_kho", "KTP")
    data_vp = config.get("data", [])
    xoa_kc = config.get("xoa_kc", False)
    bat_qc = config.get("dat_quang_cao", True)
    cfg_threshold = config.get("threshold") or THRESHOLD
    cfg_color_threshold = config.get("color_threshold", 0.6)
    # is_dat_qc check đã đặt pc chưa (trong trường hợp có qc = true) 
    is_dat_qc = False  
    # Parse data nếu là string (legacy)
    if isinstance(data_vp, str):
        data_vp = [vp.strip() for vp in data_vp.split(",") if vp.strip()]

    if not data_vp:
        logger.error("Danh sách vật phẩm trống!")
        return

    # Tìm config kho
    kho_info = next((kho for kho in CONFIG_LOAI_KHO if kho["code"] == loai_kho), None)
    if not kho_info:
        logger.error(f"Loại kho không hợp lệ: {loai_kho}")
        return

    path_kho_selected = kho_info["path_warehouse_select"]
    path_kho_not_selected = kho_info["path_warehouse_not_select"]

    logger.info(f"=== BÁN HÀNG: kho={loai_kho}, ô={so_lan}, VP={data_vp}, "
                f"QC={bat_qc}, xé KC={xoa_kc}, threshold={cfg_threshold}, color={cfg_color_threshold} ===")

    for lan in range(so_lan):
        if _should_stop():
            logger.info("Dừng bán hàng theo yêu cầu")
            return

        logger.info(f"--- Đặt ô {lan + 1}/{so_lan} ---")

        # Step 1: Check/mở cửa hàng
        if not check_cua_hang(adb):
            logger.error("Không vào được cửa hàng, bỏ qua lần này")
            continue

        if xoa_kc:
            _xu_ly_xe_kc(adb, data_vp, cfg_threshold, cfg_color_threshold)

        # Step 2: Tìm ô trống (có kéo trái nếu cần)
        pos = tim_o_ban(adb)
        if not pos:
            logger.warning("Hết ô trống, dừng bán")
            break

        # Click vào ô trống
        x, y = pos
        adb.tap(x, y)
        _sleep(CLICK_DELAY)

        # Step 3: Chọn kho
        if not chon_kho(adb, path_kho_selected, path_kho_not_selected):
            logger.warning("Không chọn được kho, bỏ qua ô này")
            continue

        # Step 4+5: Tìm VP → đặt bán. Nếu SP hết → thử SP khác trong cùng ô
        da_ban = _thu_dat_ban_voi_fallback(
            adb, data_vp, path_kho_selected, path_kho_not_selected,
            cfg_threshold, cfg_color_threshold, bat_qc, xoa_kc
        )
        if not da_ban:
            logger.warning("Không đặt được SP nào cho ô này")
        else:
            is_dat_qc = True # Đã đặt được SP, coi như đã đăt qc
        _sleep(0.3)
    if is_dat_qc == False and bat_qc:
        # chon 1 vp bất kỳ để bật qc, tìm danh sách vp để tìm vp đã đặt qc rồi bật qc
        _xu_ly_dat_qc(adb, data_vp, cfg_threshold, cfg_color_threshold)
            
    _xu_ly_sau_dat_ban(adb)
    logger.info("=== Hoàn thành bán hàng ===")
