import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from core.adb import ADBController
from core.image import ImageProcessor
from config import DEVICE_SERIAL, INDEX_HANG, INDEX_XUONG_NHA_MAC_DINH, TAB_LEN_2_HANG, INDEX_THOAT_SAN_XUAT_MAC_DINH
import time
import logging
import threading
from enum import Enum, auto

THRESHOLD = 0.85                  # Độ chính xác tìm kiếm
logger = logging.getLogger(__name__)

img = ImageProcessor()
# Per-thread state: adb, stop_event, screen cache, player state
_ctx = threading.local()


# ================================================================
# Per-LDPlayer State Machine — theo dõi trạng thái hiện tại
# ================================================================
class PlayerState(Enum):
    """Trạng thái hiện tại của mỗi LDPlayer (thread-local)."""
    UNKNOWN = auto()        # Chưa xác định
    # --- Vị trí tầng ---
    TANG_0 = auto()         # Ở nhà (hàng 0)
    TANG_1 = auto()         # Tầng 1 (hàng 1-2)
    TANG_2 = auto()         # Tầng 2 (hàng 3)
    TANG_3 = auto()         # Tầng 3 (hàng 4)
    TANG_4 = auto()         # Tầng 4 (hàng 5)
    DANG_SCROLL = auto()    # Đang cuộn lên/xuống
    # --- Trồng cây ---
    TRONG_CAY = auto()      # Đang trồng cây
    THU_HOACH = auto()      # Đang thu hoạch
    TIM_CAY = auto()        # Đang tìm cây để gieo
    # --- Sản xuất ---
    MO_MAY = auto()         # Đang mở máy sản xuất
    SAN_XUAT = auto()       # Đang kéo VP vào máy
    SUA_MAY = auto()        # Đang sửa máy
    # --- Bán hàng ---
    CUA_HANG = auto()       # Đang ở cửa hàng
    NHAT_VANG = auto()      # Đang nhặt vàng
    TIM_O_BAN = auto()      # Đang tìm ô trống
    MO_KHO = auto()         # Đang mở kho thành phẩm
    CHON_VP = auto()        # Đang chọn vật phẩm
    DAT_BAN = auto()        # Đang đặt bán
    # --- Lỗi ---
    ERROR = auto()          # Gặp lỗi, cần recovery


def set_state(state: PlayerState):
    """Set trạng thái hiện tại cho thread (LDPlayer) này."""
    old = getattr(_ctx, 'state', PlayerState.UNKNOWN)
    _ctx.state = state
    dev = getattr(_ctx, 'device_name', '?')
    if old != state:
        logger.debug(f"[STATE] {dev}: {old.name} → {state.name}")


def get_state() -> PlayerState:
    """Lấy trạng thái hiện tại của thread (LDPlayer) này."""
    return getattr(_ctx, 'state', PlayerState.UNKNOWN)


def get_state_name() -> str:
    """Lấy tên trạng thái (để hiển thị GUI/log)."""
    return get_state().name


def _row_to_state(row) -> PlayerState:
    """Chuyển số hàng thành PlayerState tầng tương ứng."""
    mapping = {
        0: PlayerState.TANG_0,
        1: PlayerState.TANG_1,
        2: PlayerState.TANG_1,
        3: PlayerState.TANG_2,
        4: PlayerState.TANG_3,
        5: PlayerState.TANG_4,
    }
    return mapping.get(row, PlayerState.UNKNOWN)


def _get_adb():
    """Lấy ADB instance của thread hiện tại."""
    return getattr(_ctx, 'adb', None)


def _get_stop_event():
    """Lấy stop_event của thread hiện tại."""
    return getattr(_ctx, 'stop_event', None)


def setup_thread(adb_instance, stop_event=None, device_name=None):
    """Gọi đầu mỗi thread để set ADB + stop_event + tên thiết bị + state cho thread đó."""
    _ctx.adb = adb_instance
    _ctx.stop_event = stop_event
    _ctx._last_screen = None
    _ctx.device_name = device_name
    _ctx.state = PlayerState.UNKNOWN


def get_device_name():
    """Lấy tên thiết bị của thread hiện tại."""
    return getattr(_ctx, 'device_name', None)


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


def init_adb(serial=None, adb: ADBController=None):
    """Khởi tạo ADB controller và gán vào thread hiện tại."""
    if adb is not None:
        _ctx.adb = adb
        return adb
    if serial is None:
        serial = DEVICE_SERIAL
    new_adb = ADBController(serial=serial)
    _ctx.adb = new_adb
    return new_adb


def tim_may(template_path, config_row, count=1):
    """(Legacy) Giữ lại để tương thích ngược. Gọi tim_may_v2."""
    return tim_may_v2(template_path, config_row)


def _row_to_level(row):
    """Chuyển số hàng (row) thành tầng scroll (level).

    Hàng 0 là nhà (dưới cùng) → level 0
    Hàng 1, 2 cùng 1 khung hình → level 1  (1 scroll từ nhà)
    Hàng 3 → level 2  (2 scroll từ nhà)
    Hàng 4 → level 3  (3 scroll từ nhà)
    Hàng N (N >= 3) → level N - 1

    VD:
      row 0 → level 0  (nhà)
      row 1 → level 1  (1 scroll lên)
      row 2 → level 1  (cùng khung với row 1)
      row 3 → level 2  (2 scroll lên)
      row 4 → level 3  (3 scroll lên)
      row 5 → level 4
    """
    if row == 0:
        return 0
    if row <= 2:
        return 1
    return row - 1


def _detect_current_row(take_screenshot=True, threshold=None):
    """Chụp màn hình và nhận diện đang ở hàng nào (0-10).
    Tối ưu: chụp 1 screenshot, tìm 11 số trên cùng ảnh.
    Nếu lần 1 không thấy (bóng/lag) → chụp lại lần 2.
    Tối đa 2 screenshot thay vì 22."""
    th = threshold or THRESHOLD
    adb = _get_adb()
    if not adb:
        return None

    for attempt in range(2):
        # Lần 1: chụp mới (hoặc dùng cache nếu take_screenshot=False)
        if attempt == 0 and not take_screenshot:
            screen = getattr(_ctx, '_last_screen', None)
            if screen is None:
                screen = adb.screenshot_full()
        else:
            adb.tap(*INDEX_THOAT_SAN_XUAT_MAC_DINH)
            if attempt > 0:
                _sleep(0.3)
                logger.info("Lần 1 không nhận diện được hàng, chụp lại...")
            screen = adb.screenshot_full()

        if screen is None:
            continue

        _ctx._last_screen = screen

        # Tìm 11 số trên cùng 1 ảnh (không retry từng số)
        for i in range(0, 11):
            may_i = f"assets/items/num/{i}.png"
            pos = img.find_template_color(may_i, threshold=th, screen_img=screen)
            if pos:
                logger.info(f"Nhận diện hàng hiện tại: {i} (lần {attempt+1})")
                set_state(_row_to_state(i))
                return i

    return None


def tim_may_v2(template_path, config_row, max_retry=2):
    """Tìm và di chuyển đến hàng config_row.

    Logic scroll theo tầng (level):
      - Máy 1, 2 cùng khung hình → level 0 (không cần scroll)
      - Máy 3 → level 1 (1 scroll từ nhà)
      - Máy 4 → level 2 (2 scroll từ nhà)
      - Máy N (N>=3) → level N-2

    Scroll = chênh lệch level, KHÔNG phải chênh lệch row.
    VD: đang ở máy 1 (level 0), cần đến máy 3 (level 1) → 1 scroll
        đang ở máy 1 (level 0), cần đến máy 4 (level 2) → 2 scroll
        đang ở máy 2 (level 0), cần đến máy 3 (level 1) → 1 scroll
        đang ở máy 3 (level 1), cần đến máy 1 (level 0) → 1 scroll xuống
    """
    if _should_stop():
        return False

    # === BƯỚC 1: Nhận diện hàng hiện tại (có retry) ===
    current_row = _detect_current_row(take_screenshot=True)

    if current_row is None:
        logger.warning("Không nhận diện được hàng, chụp lại...")
        _sleep(0.5)
        current_row = _detect_current_row(take_screenshot=True)

    if current_row is None:
        # Nếu không nhận diện được hàng, có thể màn hình bị kẹt bởi popup/quảng cáo. Thử dùng AI gỡ kẹt.
        import config
        if getattr(config, "ENABLE_AI_RECOVERY", False) and getattr(config, "GEMINI_API_KEY", "").strip():
            try:
                logger.warning("[AI_RECOVERY] Nghi ngờ màn hình bị kẹt popup/quảng cáo. Đang gọi Gemini VLM để giải cứu...")
                from core.ai_recovery import AIRecovery
                ai_rec = AIRecovery()
                screen = adb.screenshot_full()
                rec_data = ai_rec.analyze_and_recover(screen)
                if rec_data and rec_data.get("is_stuck") and rec_data.get("action") == "click" and rec_data.get("original_coords"):
                    orig_x, orig_y = rec_data["original_coords"]
                    logger.info(f"[AI_RECOVERY] Phát hiện kẹt: '{rec_data['reason']}'. Click đóng tại ({orig_x}, {orig_y})")
                    adb.tap(orig_x, orig_y)
                    _sleep(1.5)
                    # Chụp và thử nhận diện lại hàng
                    current_row = _detect_current_row(take_screenshot=True)
            except Exception as ai_err:
                logger.error(f"[AI_RECOVERY] Gặp lỗi khi gọi AI gỡ kẹt: {ai_err}")

    if current_row is None:
        logger.error("Không thể nhận diện hàng hiện tại sau 2 lần chụp")
        return False

    # === BƯỚC 2: Tính level hiện tại và level đích ===
    current_level = _row_to_level(current_row)
    target_level = _row_to_level(config_row)

    logger.info(f"Hàng hiện tại: {current_row} (level {current_level}), "
                f"cần đến: {config_row} (level {target_level})")

    # Cùng level → không cần scroll (VD: đang ở máy 1, cần máy 2)
    if current_level == target_level:
        logger.info(f"Máy {current_row} và {config_row} cùng khung hình, không cần scroll")
        return True

    if _should_stop():
        return False

    # === BƯỚC 3: Scroll theo chênh lệch level ===
    level_diff = target_level - current_level  # dương = lên, âm = xuống
    abs_diff = abs(level_diff)

    # nếu xuống nhà >= 3 level → ưu tiên về nhà trước rồi scroll lên, tránh lỗi nhận diện hàng do bóng/lag khi scroll nhiều
    if level_diff < 0 and abs_diff >= 3:
        logger.info(f"Khoảng cách xa ({abs_diff} level), về nhà trước")
        xuong_nha()
        if _should_stop():
            return False
        # Từ nhà (level 0), scroll lên đến target_level
        if target_level > 0:
            logger.info(f"Từ nhà, scroll lên {target_level} lần")
            len_may(target_level)
    elif level_diff > 0:
        logger.info(f"Scroll lên {abs_diff} lần (level {current_level} → {target_level})")
        len_may(abs_diff)
    else:
        logger.info(f"Scroll xuống {abs_diff} lần (level {current_level} → {target_level})")
        xuong_may(abs_diff)

    if _should_stop():
        return False

    # === BƯỚC 4: Verify — chụp lại kiểm tra ===
    _sleep(0.5)
    for retry in range(max_retry):
        if _should_stop():
            return False
        verify_row = _detect_current_row(take_screenshot=True)

        if verify_row is None:
            logger.warning(f"Verify lần {retry+1}: không nhận diện được hàng, thử lại...")
            _sleep(0.5)
            continue

        verify_level = _row_to_level(verify_row)
        if verify_level == target_level:
            logger.info(f"Verify OK: đang ở hàng {verify_row} (level {verify_level}), "
                        f"cùng khung với máy {config_row}")
            return True

        # Chưa đúng level → micro-adjust theo level
        micro = target_level - verify_level
        logger.warning(f"Verify lần {retry+1}: hàng {verify_row} (level {verify_level}), "
                       f"cần level {target_level}, adjust {micro}")
        if micro > 0:
            len_may(abs(micro))
        else:
            xuong_may(abs(micro))
        _sleep(0.5)

    # Kiểm tra lần cuối
    final_row = _detect_current_row(take_screenshot=True)
    if final_row is not None and _row_to_level(final_row) == target_level:
        logger.info(f"Verify cuối cùng OK: hàng {final_row} (level {target_level})")
        return True

    logger.error(f"Không thể đến máy {config_row} (đang ở hàng {final_row})")
    return False


def lay_toa_do_tu_indexs(indexs_list):
    return [INDEX_HANG[idx] for idx in indexs_list if idx in INDEX_HANG]


def _len_1_may(duration: int=50):
    adb = _get_adb()
    adb.drag_smooth([(70, 450), (70, 500)], total_duration_ms=duration)


def len_2_may(count: int=1, duration: int=70, sleep: float=0.5):
    adb = _get_adb()
    set_state(PlayerState.DANG_SCROLL)
    for _ in range(count):
        if _should_stop():
            return
        adb.tap(*TAB_LEN_2_HANG)
        _sleep(sleep)

def len_may(count: int=1, duration: int=50, sleep: float=0.5): 
    set_state(PlayerState.DANG_SCROLL)
    len_2_count = count // 2
    len_1_count = count % 2

    if len_2_count:
        len_2_may(len_2_count, sleep=sleep)

    for _ in range(len_1_count):
        if _should_stop():
            return
        _len_1_may(duration=duration)
        _sleep(sleep)

def xuong_may(count: int=1, duration: int=50, sleep: float=0.5):
    adb = _get_adb()
    set_state(PlayerState.DANG_SCROLL)
    for _ in range(count):
        if _should_stop():
            return
        adb.drag_smooth([(70, 500), (70, 450)], total_duration_ms=duration)
        _sleep(sleep)


def xuong_nha(duration: int=50, sleep: float=0.7, threshold=None):
    adb = _get_adb()
    set_state(PlayerState.DANG_SCROLL)
    th = threshold or THRESHOLD
    adb.scroll_up(450, 500, 70, duration)
    adb.scroll_down(500, 450, 70, duration)
    _sleep(sleep)
    pos = find_image_v2("assets/items/core_check_xuong_1.png", True, threshold=th)
    if (pos):
        logger.info("Tìm được xuống nhà")
        (x, y) = pos
        adb.tap(x, y)
        _sleep(sleep)
    else:
        logger.info("Không tìm được tab mặc định")
        (x, y) = INDEX_XUONG_NHA_MAC_DINH
        adb.tap(x, y)
        _sleep(sleep)
    set_state(PlayerState.TANG_0)


def find_image(template_path, screen, screen_img=None, region=None):
    """Tìm template trong screen (grayscale match)."""
    use_screen = _get_screen(screen, screen_img)
    if use_screen is None:
        logger.warning("Không có ảnh màn hình để tìm template: %s", template_path)
        return None
    return img._match_one(template_path=template_path, threshold=THRESHOLD, screen_img=use_screen, region=region)


# Debug mode cho utils (trong_cay, v.v.)
_debug_mode = False
_DEBUG_DIR = "debug/utils"

def set_debug_mode(enabled: bool):
    global _debug_mode
    _debug_mode = enabled
    if enabled:
        os.makedirs(_DEBUG_DIR, exist_ok=True)
        logger.info(f"[DEBUG] Utils debug mode ON — lưu ảnh tại {_DEBUG_DIR}/")


def _save_debug(screen, template_path, pos, step_name="find"):
    """Lưu screenshot debug nếu debug mode bật."""
    if not _debug_mode or screen is None:
        return
    try:
        import cv2
        from datetime import datetime
        os.makedirs(_DEBUG_DIR, exist_ok=True)
        ts = datetime.now().strftime("%H%M%S_%f")[:-3]
        tpl_name = os.path.basename(template_path).replace(".png", "")
        status = "FOUND" if pos else "NOT_FOUND"
        filename = f"{ts}_{step_name}_{tpl_name}_{status}.png"
        save_path = os.path.join(_DEBUG_DIR, filename)

        debug_img = screen.copy()
        if pos:
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
            cv2.putText(debug_img, f"NOT FOUND: {tpl_name}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        cv2.imwrite(save_path, debug_img)
        logger.debug(f"[DEBUG] Saved: {save_path}")
    except Exception as e:
        logger.debug(f"[DEBUG] Lỗi lưu debug: {e}")


def _get_screen(screen_flag, screen_img=None):
    """Lấy screenshot: chụp mới hoặc dùng cache. Trả về numpy array."""
    if screen_img is not None:
        return screen_img

    adb = _get_adb()
    if not hasattr(_ctx, '_last_screen'):
        _ctx._last_screen = None

    if screen_flag:
        if adb is None:
            init_adb()
            adb = _get_adb()
        _ctx._last_screen = adb.screenshot_full()
    else:
        if _ctx._last_screen is None:
            if adb is None:
                init_adb()
                adb = _get_adb()
            _ctx._last_screen = adb.screenshot_full()

    return _ctx._last_screen


def find_image_v2(template_path, screen, screen_img=None, threshold=THRESHOLD,
                  retry=0, max_retry=1, step_name=None, region=None):
    """Tìm template trong screen (color match).

    Cải tiến:
    - Nếu không tìm thấy + retry < max_retry → chụp lại 1 lần nữa
    - Lưu debug screenshot nếu debug mode bật
    - Log chi tiết hơn
    """
    tpl_name = os.path.basename(template_path).replace(".png", "")
    _step = step_name or tpl_name

    use_screen = _get_screen(screen, screen_img)
    if use_screen is None:
        logger.warning("Không có ảnh màn hình để tìm template: %s", template_path)
        return None

    pos = img.find_template_color(template_path=template_path, threshold=threshold,
                                  screen_img=use_screen, region=region)

    # Lưu debug
    _save_debug(use_screen, template_path, pos, _step)

    if pos:
        return pos

    # Retry: chụp mới rồi tìm lại
    if retry < max_retry:
        logger.info(f"[RETRY] {tpl_name} không thấy, chụp lại (retry {retry+1}/{max_retry})")
        _sleep(0.3)
        return find_image_v2(template_path, True, screen_img=None, threshold=threshold,
                             retry=retry + 1, max_retry=max_retry,
                             step_name=f"{_step}_retry{retry+1}", region=region)

    return None


def clear_screen_cache():
    """Xóa cache screenshot để giải phóng memory."""
    if hasattr(_ctx, '_last_screen'):
        _ctx._last_screen = None


# ================================================================
# Error Recovery dựa trên state
# ================================================================
def recover_from_state():
    """Thử khôi phục dựa trên trạng thái hiện tại.
    Gọi khi gặp lỗi — hàm sẽ cố gắng đưa player về trạng thái an toàn.
    Return True nếu recovery thành công."""
    state = get_state()
    adb = _get_adb()
    if not adb:
        return False

    dev = getattr(_ctx, 'device_name', '?')
    logger.info(f"[RECOVERY] {dev}: Đang ở state {state.name}, thử phục hồi...")

    if state == PlayerState.UNKNOWN:
        # Chưa biết ở đâu → detect row
        row = _detect_current_row(take_screenshot=True)
        if row is not None:
            logger.info(f"[RECOVERY] Phát hiện đang ở hàng {row}")
            return True
        logger.warning("[RECOVERY] Không nhận diện được vị trí")
        return False

    elif state in (PlayerState.CUA_HANG, PlayerState.NHAT_VANG,
                   PlayerState.TIM_O_BAN, PlayerState.MO_KHO,
                   PlayerState.CHON_VP, PlayerState.DAT_BAN):
        # Đang trong flow bán hàng → thử đóng popup bằng nút X
        logger.info(f"[RECOVERY] Đang trong flow bán hàng ({state.name}), thử đóng popup...")
        pos = find_image_v2("assets/items/core_nut_x.png", True, threshold=0.85)
        if pos:
            x, y = pos
            adb.tap(x, y)
            _sleep(0.5)
            set_state(PlayerState.CUA_HANG)
            return True
        # Không thấy nút X → có thể đã ở cửa hàng rồi
        set_state(PlayerState.CUA_HANG)
        return True

    elif state in (PlayerState.TRONG_CAY, PlayerState.THU_HOACH, PlayerState.TIM_CAY):
        # Đang trồng/thu hoạch → chỉ cần tap lại cánh đồng
        logger.info(f"[RECOVERY] Đang trong flow trồng cây ({state.name})")
        return True

    elif state in (PlayerState.MO_MAY, PlayerState.SAN_XUAT, PlayerState.SUA_MAY):
        # Đang sản xuất → thử đóng máy
        logger.info(f"[RECOVERY] Đang trong flow sản xuất ({state.name}), thử đóng popup...")
        pos = find_image_v2("assets/items/core_nut_x.png", True, threshold=0.85)
        if pos:
            x, y = pos
            adb.tap(x, y)
            _sleep(0.5)
        return True

    elif state in (PlayerState.DANG_SCROLL,):
        # Đang scroll → đợi xong, detect lại
        _sleep(1)
        _detect_current_row(take_screenshot=True)
        return True

    elif state == PlayerState.ERROR:
        # Đã error trước đó → về nhà cho an toàn
        logger.info("[RECOVERY] State ERROR → về nhà...")
        xuong_nha()
        return True

    # State khác (TANG_x) → không cần recovery đặc biệt
    return True
