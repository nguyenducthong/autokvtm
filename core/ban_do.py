"""
Ban do - Bán vật phẩm tại cửa hàng
Flow: Kiểm tra vị trí → về nhà nếu cần → mở cửa hàng → tìm ô trống (kéo trái nếu cần)
      → click → chọn kho → tìm VP → đặt bán (bật/tắt QC)
"""
import sys
import os
import json
import re
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from .adb import ADBController
from .image import ImageProcessor, get_resource_path
from config import INDEX_CONG_1, INDEX_CUA_HANG_MAC_DINH, INDEX_TAT_QC,INDEX_DAT_BAN
from utils.utils import (
    _detect_current_row, xuong_nha, xuong_may,
    set_state, get_state, PlayerState
)
from utils.daily_stats import record_daily_stat
import time
import logging
import cv2
import random
from datetime import datetime
try:
    import pytesseract
except Exception:
    pytesseract = None

logger = logging.getLogger(__name__)
img = ImageProcessor()
MAX_ATTEMPTS = 3
THRESHOLD = 0.85
CLICK_DELAY = 1.0

# Debug mode — bật để lưu screenshot + kết quả match vào debug/ban_do/
DEBUG_MODE = False
DEBUG_DIR = "debug/ban_do"
STOCK_STATE_FILE = os.path.join("data", "ban_do_stock_state.json")
STOCK_NUMBER_OFFSET = (5, 5, 60, 40)
STOCK_NUMBER_OFFSETS = [
    STOCK_NUMBER_OFFSET,
    (25, 0, 75, 45),
    (-10, 0, 90, 45),
    (0, -8, 80, 55),
]
STOCK_DIGIT_THRESHOLD = 0.62
STOCK_PLAN_REPEAT_PENALTY = 0.25
_stock_ocr_available = None


def _normalize_template_path(template_path):
    if not template_path:
        return template_path
    if os.path.isabs(template_path):
        return template_path
    if template_path.startswith("assets/"):
        return template_path
    return os.path.join("assets/items", template_path)

# Per-thread state cho ban_do
import threading as _threading
_bd_ctx = _threading.local()
_stock_lock = _threading.Lock()

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


def _find(adb, template_path, threshold=THRESHOLD, color_threshold=0.6, step_name="find",
          region=None):
    """Chụp màn hình rồi tìm template, trả về (x,y) hoặc None."""
    screen = adb.screenshot_full()
    if screen is None:
        return None, None
    pos = img.find_template_color(template_path=template_path, threshold=threshold,
                                  color_threshold=color_threshold, screen_img=screen,
                                  region=region)
    _save_debug_screenshot(screen, template_path, pos, step_name)
    return pos, screen


def _find_on_screen(screen, template_path, threshold=THRESHOLD, color_threshold=0.6,
                    step_name="find_cached", region=None):
    """Tìm template trên screen đã chụp sẵn (hỗ trợ YOLO AI trước, dự phòng OpenCV)."""
    if screen is None:
        return None

    # 1. Thử tìm bằng YOLO (nếu bật)
    import config
    if getattr(config, "ENABLE_YOLO", False):
        try:
            from core.yolo_detector import YOLODetector
            detector = YOLODetector()
            if detector.is_available():
                detections = detector.detect(screen)
                classes = detector.classes
                
                # Trích xuất tên file không chứa đường dẫn và đuôi mở rộng
                base = os.path.basename(template_path).replace(".png", "")
                
                # Quy tắc ánh xạ thông minh từ template_path sang class YOLO
                target_class = None
                if base in classes:
                    target_class = base
                else:
                    normalized = base.replace("core_", "").replace("kho_", "").replace("cay_", "")
                    # Xử lý các nhãn đặc biệt
                    if "vang" in normalized:
                        for c in ("o_vang", "o_ban_vang", "vang"):
                            if c in classes:
                                target_class = c
                                break
                    elif "trong" in normalized:
                        for c in ("o_trong", "o_ban_trong", "trong"):
                            if c in classes:
                                target_class = c
                                break
                    else:
                        # Tìm fuzzy match tên nhãn lớp
                        for c in classes:
                            if c in base or base in c or c in normalized or normalized in c:
                                target_class = c
                                break
                
                if target_class:
                    pos_yolo = None
                    for d in detections:
                        if d["class"] == target_class:
                            pos_yolo = d["center"]
                            # Kiểm tra giới hạn vùng chụp (region) nếu có
                            if region:
                                rx, ry, rw, rh = region
                                cx, cy = pos_yolo
                                if not (rx <= cx <= rx + rw and ry <= cy <= ry + rh):
                                    continue
                            break
                    if pos_yolo:
                        logger.info(f"[YOLO] Tìm thấy '{target_class}' (từ {base}) tại {pos_yolo}")
                        _save_debug_screenshot(screen, template_path, pos_yolo, f"yolo_{step_name}")
                        return pos_yolo
        except Exception as e:
            logger.warning(f"[BAN_DO_YOLO] Lỗi nhận diện bằng YOLO cho {template_path}: {e}")

    # 2. Dự phòng: OpenCV Template Matching
    pos = img.find_template_color(template_path=template_path, threshold=threshold,
                                  color_threshold=color_threshold, screen_img=screen,
                                  region=region)
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
NUT_X_PATH = "assets/items/core_nut_x.png"


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
    pos, _ = _find(adb, "assets/items/core_quay_hang_on.png", step_name="check_cua_hang")
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
    pos, _ = _find(adb, "assets/items/core_quay_hang_on.png", step_name="check_cua_hang_retry1")
    if pos:
        logger.info("Đã mở cửa hàng thành công")
        set_state(PlayerState.CUA_HANG)
        return True

    # Retry: đóng popup rồi tap lại
    logger.warning("Lần 1 không mở được, thử lại...")
    _dong_popup(adb)
    adb.tap(x, y)
    _sleep(CLICK_DELAY)

    pos, _ = _find(adb, "assets/items/core_quay_hang_on.png", step_name="check_cua_hang_retry2")
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
        pos = _find_on_screen(screen, "assets/items/core_vang3.png", threshold=0.9,
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
    _sleep(CLICK_DELAY)

    for swipe_i in range(max_swipe + 1):  # 0 = trang hiện tại, 1..max = sau kéo
        if _should_stop():
            return None

        screen = adb.screenshot_full()
        if screen is None:
            return None

        # Tim o vang truoc; co o vang thi tra toa do luon (tự động dùng YOLO nếu bật)
        pos_vang = _find_on_screen(screen, "assets/items/core_vang3.png", threshold=0.9,
                                   step_name=f"tim_o_vang_swipe{swipe_i}")
        if pos_vang:
            logger.info(f"Tìm thấy ô vàng tại {pos_vang} (sau {swipe_i} lần kéo)")
            return pos_vang

        # Tìm ô trống (tự động dùng YOLO nếu bật)
        pos_trong = _find_on_screen(screen, "assets/items/core_o_trong.png", threshold=0.9,
                                    step_name=f"tim_o_trong_swipe{swipe_i}")
        if pos_trong:
            logger.info(f"Tìm thấy ô trống tại {pos_trong} (sau {swipe_i} lần kéo)")
            return pos_trong

        # Không tìm thấy ô trống → kéo trong khung quầy sang trái
        if swipe_i < max_swipe:
            logger.info(f"Không tìm thấy ô trống, kéo quầy sang trái ({swipe_i+1}/{max_swipe})...")
            _keo_quay_hang_sang_trai(adb)
            _sleep(CLICK_DELAY)

    logger.warning(f"Không tìm thấy ô trống sau {max_swipe} lần kéo (đã xem hết 20 ô)")
    return None


# ================================================================
# STEP 3: Chọn kho (có retry + debug)
# ================================================================
def chon_kho(adb, path_kho_selected, path_kho_not_selected, max_retry=3, position=None):
    """Tìm và chọn kho. Retry nếu chụp quá sớm chưa kịp load UI.
    Return True/False."""
    set_state(PlayerState.MO_KHO)
    if _should_stop():
        return False

    if position:
        try:
            x, y = position
            logger.info(f"Chon kho bang toa do co dinh: ({x}, {y})")
            _sleep(0.2)
            adb.tap(int(x), int(y), 0.1)
            _sleep(0.3)
            return True
        except (TypeError, ValueError) as e:
            logger.warning(f"Toa do kho khong hop le {position}: {e}. Fallback tim anh.")

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
def _normalize_vp_list(vp_list, default_threshold=THRESHOLD, default_color=0.6,
                       default_region=None):
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
                "color_threshold": default_color,
                "region": default_region
            })
        elif isinstance(item, dict):
            result.append({
                "path": item["path"],
                "threshold": item.get("threshold", default_threshold),
                "color_threshold": item.get("color_threshold", default_color),
                "region": item.get("region", default_region)
            })
    return result


def _stock_device_key(adb):
    return getattr(adb, "serial", None) or "default"


def _stock_item_key(path_vp):
    return _normalize_template_path(path_vp)


def _load_stock_state():
    try:
        if not os.path.exists(STOCK_STATE_FILE):
            return {}
        with open(STOCK_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning(f"Khong doc duoc stock state: {e}")
        return {}


def _save_stock_state(state):
    try:
        os.makedirs(os.path.dirname(STOCK_STATE_FILE), exist_ok=True)
        with open(STOCK_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Khong luu duoc stock state: {e}")


def _read_stock_map(adb):
    device_key = _stock_device_key(adb)
    with _stock_lock:
        state = _load_stock_state()
    device_state = state.get(device_key, {})
    stock_map = {}
    if not isinstance(device_state, dict):
        return stock_map
    for path_vp, info in device_state.items():
        if isinstance(info, dict) and isinstance(info.get("stock"), int):
            stock_map[path_vp] = info["stock"]
    return stock_map


def _digit_template_paths():
    paths = []
    stock_num_dir = os.path.join("assets", "items", "stock_num")
    for digit in range(10):
        path = os.path.join(stock_num_dir, f"{digit}.png")
        resolved = get_resource_path(path)
        if os.path.exists(resolved):
            paths.append((str(digit), path))
    if paths:
        x_path = os.path.join(stock_num_dir, "x.png")
        resolved_x = get_resource_path(x_path)
        if os.path.exists(resolved_x):
            paths.append(("x", x_path))
        return paths

    for digit in range(10):
        path = os.path.join("assets", "items", "num", f"{digit}.png")
        resolved = get_resource_path(path)
        if os.path.exists(resolved):
            paths.append((str(digit), path))
    return paths


def _find_digit_candidates(screen, region, threshold=STOCK_DIGIT_THRESHOLD):
    if screen is None or region is None:
        return []

    rx, ry, rw, rh = region
    h_max, w_max = screen.shape[:2]
    rx = max(0, min(int(rx), w_max - 1))
    ry = max(0, min(int(ry), h_max - 1))
    rw = max(1, min(int(rw), w_max - rx))
    rh = max(1, min(int(rh), h_max - ry))
    crop = screen[ry:ry+rh, rx:rx+rw]
    if crop.size == 0:
        return []

    crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    candidates = []
    for digit, template_path in _digit_template_paths():
        template = cv2.imread(template_path, cv2.IMREAD_UNCHANGED)
        if template is None:
            continue
        if template.ndim == 3 and template.shape[2] == 4:
            template = template[:, :, :3]
        tpl_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY) if template.ndim == 3 else template
        th, tw = tpl_gray.shape[:2]
        if th > crop_gray.shape[0] or tw > crop_gray.shape[1]:
            continue

        result = cv2.matchTemplate(crop_gray, tpl_gray, cv2.TM_CCOEFF_NORMED)
        locations = zip(*cv2.threshold(result, threshold, 1.0, cv2.THRESH_TOZERO)[1].nonzero()[::-1])
        for x, y in locations:
            score = float(result[y, x])
            candidates.append({
                "digit": digit,
                "x": rx + int(x),
                "y": ry + int(y),
                "w": tw,
                "h": th,
                "score": score
            })
    return candidates


def _dedupe_digit_candidates(candidates):
    selected = []
    for cand in sorted(candidates, key=lambda c: c["score"], reverse=True):
        duplicate = False
        for prev in selected:
            same_area = (
                abs(cand["x"] - prev["x"]) < max(4, cand["w"] // 2) and
                abs(cand["y"] - prev["y"]) < max(4, cand["h"] // 2)
            )
            if same_area:
                duplicate = True
                break
        if not duplicate:
            selected.append(cand)
    return sorted(selected, key=lambda c: c["x"])


def _is_stock_ocr_available():
    global _stock_ocr_available
    if _stock_ocr_available is not None:
        return _stock_ocr_available
    if pytesseract is None:
        _stock_ocr_available = False
        logger.warning("[STOCK] Khong dung OCR vi chua cai pytesseract")
        return False
    try:
        pytesseract.get_tesseract_version()
        _stock_ocr_available = True
    except Exception as e:
        _stock_ocr_available = False
        logger.warning("[STOCK] Khong dung OCR vi chua cai Tesseract: %s", e)
    return _stock_ocr_available


def _parse_stock_ocr_text(text, allow_plain_digits=False):
    if not text:
        return None
    compact = re.sub(r"\s+", "", str(text))
    match = re.search(r"[xX](\d{1,4})", compact)
    if match:
        return int(match.group(1))
    if allow_plain_digits:
        digits = re.findall(r"\d{1,4}", compact)
        if digits:
            return int("".join(digits[:2])[:4])
    return None


def _stock_ocr_images(crop):
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=5, fy=5, interpolation=cv2.INTER_CUBIC)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _, bright = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    # Bat ca chu trang va chu vang sang, bo nen vat pham nhieu mau.
    mask_white = cv2.inRange(hsv, (0, 0, 145), (180, 95, 255))
    mask_yellow = cv2.inRange(hsv, (15, 45, 130), (45, 255, 255))
    mask = cv2.bitwise_or(mask_white, mask_yellow)
    mask = cv2.resize(mask, None, fx=5, fy=5, interpolation=cv2.INTER_CUBIC)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, (3, 3))

    return (gray, otsu, cv2.bitwise_not(otsu), bright, mask, cv2.bitwise_not(mask))


def _read_stock_number_by_ocr(screen, region):
    if screen is None or region is None or not _is_stock_ocr_available():
        return None

    rx, ry, rw, rh = region
    h_max, w_max = screen.shape[:2]
    rx = max(0, min(int(rx), w_max - 1))
    ry = max(0, min(int(ry), h_max - 1))
    rw = max(1, min(int(rw), w_max - rx))
    rh = max(1, min(int(rh), h_max - ry))
    crop = screen[ry:ry + rh, rx:rx + rw]
    if crop.size == 0:
        return None

    results = []
    config = "--psm 7 -c tessedit_char_whitelist=xX0123456789"
    for ocr_img in _stock_ocr_images(crop):
        try:
            text = pytesseract.image_to_string(ocr_img, config=config)
        except Exception as e:
            logger.warning("[STOCK] OCR loi, dung fallback anh so: %s", e)
            return None
        number = _parse_stock_ocr_text(text, allow_plain_digits=False)
        if number is not None:
            results.append({
                "number": number,
                "score": 1.0,
                "digits": [],
                "region": (rx, ry, rw, rh),
                "source": "ocr",
                "raw": text.strip(),
            })
    if not results:
        return None
    best = max(results, key=lambda item: item["number"])
    logger.info(
        f"[STOCK] OCR doc so {best['number']} tai region=({rx}, {ry}, {rw}, {rh}) "
        f"text={best.get('raw', '')!r}"
    )
    return best


def _read_stock_number_by_template(screen, region):
    candidates = _find_digit_candidates(screen, region)
    digits = _dedupe_digit_candidates(candidates)
    if not digits:
        return None

    # Keep the most likely visual row. Stock digits usually sit on one line.
    rows = {}
    for cand in digits:
        bucket = int(round(cand["y"] / 10.0) * 10)
        rows.setdefault(bucket, []).append(cand)
    best_row = max(rows.values(), key=lambda row: (len(row), sum(c["score"] for c in row)))
    best_row = sorted(best_row, key=lambda c: c["x"])
    number_text = "".join(c["digit"] for c in best_row if c["digit"] != "x")
    try:
        number = int(number_text)
    except ValueError:
        return None
    avg_score = sum(c["score"] for c in best_row) / max(1, len(best_row))
    return {
        "number": number,
        "score": avg_score,
        "digits": best_row,
        "region": region,
        "source": "template",
    }


def _read_stock_number_from_region(screen, region):
    results = []
    ocr_result = _read_stock_number_by_ocr(screen, region)
    if ocr_result is not None:
        results.append(ocr_result)

    template_result = _read_stock_number_by_template(screen, region)
    if template_result is not None:
        results.append(template_result)

    if not results:
        return None

    best = max(results, key=lambda item: item["number"])
    logger.info(
        f"[STOCK] Chon so lon nhat {best['number']} tu "
        f"{[(r['source'], r['number']) for r in results]}"
    )
    return best


def _read_stock_number_near_item(screen, pos_vp, stock_offset=STOCK_NUMBER_OFFSET):
    if not pos_vp:
        return None
    x, y = pos_vp
    offsets = STOCK_NUMBER_OFFSETS if stock_offset == STOCK_NUMBER_OFFSET else [stock_offset]
    for ox, oy, ow, oh in offsets:
        region = (int(x + ox), int(y + oy), int(ow), int(oh))
        result = _read_stock_number_from_region(screen, region)
        if result is not None:
            if result.get("source") == "ocr":
                logger.info(
                    f"[STOCK] Doc so {result['number']} bang OCR tai region={result['region']} "
                    f"raw={result.get('raw', '')!r}"
                )
            else:
                logger.info(
                    f"[STOCK] Doc so {result['number']} bang template tai region={result['region']} "
                    f"digits={[(d['digit'], d['x'], d['y'], round(d['score'], 3)) for d in result['digits']]}"
                )
            return result["number"]
    return None


_HTTP_SESSION = None

def _get_http_session():
    global _HTTP_SESSION
    if _HTTP_SESSION is None:
        import requests
        _HTTP_SESSION = requests.Session()
    return _HTTP_SESSION


def _scan_stock_with_gemini(screen, vp_list, api_key):
    """
    Sử dụng Gemini VLM để đọc số lượng vật phẩm trong kho thành phẩm.
    """
    import base64
    import json
    
    # 1. Trích xuất danh sách tên vật phẩm từ vp_list
    item_map = {} # map name -> path
    for item in vp_list:
        path = item.get("path") if isinstance(item, dict) else item
        name = os.path.basename(path).replace(".png", "").replace("kho_", "").replace("core_", "")
        item_map[name] = path

    item_names = list(item_map.keys())
    
    # 2. Resize ảnh để gửi cho nhẹ (rộng 900px)
    h, w = screen.shape[:2]
    target_width = 900  # Tăng độ phân giải lên 900px để chữ số to rõ ràng hơn
    target_height = int(h * (target_width / w))
    resized = cv2.resize(screen, (target_width, target_height))
    # Nén JPEG chất lượng cao 95% để tránh nhiễu nén làm nhòe chữ số
    _, buffer = cv2.imencode('.jpg', resized, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    image_bytes = buffer.tobytes()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    
    # 3. Chuẩn bị prompt tiếng Anh ngắn để giảm token và tối ưu hóa thời gian suy luận
    prompt = (
        "Identify quantities of these items in the warehouse screen. "
        "Read numbers at the bottom-right corner of each item cell (e.g. x152 is 152). "
        f"Items to find: {', '.join(item_names)}. "
        "Output ONLY a valid JSON dictionary using double quotes for keys, format: {\"item_name\": quantity}. "
        "If not found, set its value to 0."
    )
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inlineData": {
                            "mimeType": "image/jpeg",
                            "data": image_b64
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.1,
            "maxOutputTokens": 150  # Giới hạn số token đầu ra để phản hồi nhanh nhất
        }
    }
    
    try:
        session = _get_http_session()
        response = session.post(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        res_json = response.json()
        resp_text = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
        
        # Parse JSON phản hồi (có dự phòng dùng ast.literal_eval nếu trả về nháy đơn hoặc markdown block)
        try:
            result = json.loads(resp_text)
        except Exception:
            import ast
            cleaned_text = resp_text.replace("```json", "").replace("```", "").strip()
            result = ast.literal_eval(cleaned_text)
            
        logger.info(f"[STOCK_AI] Phản hồi từ Gemini: {result}")
        
        # Ánh xạ kết quả ngược về path vật phẩm
        stock_result = {}
        for name, qty in result.items():
            matched_path = None
            for k, path in item_map.items():
                if k in name or name in k:
                    matched_path = path
                    break
            if matched_path:
                stock_result[matched_path] = int(qty)
                
        return stock_result
    except Exception as e:
        logger.error(f"[STOCK_AI] Lỗi khi gọi Gemini để đọc kho: {e}")
        return {}


def _scan_va_luu_stock_kho(adb, vp_list, threshold=THRESHOLD, color_threshold=0.6,
                           region=None):
    """Quet so luong cac VP dang cau hinh trong kho va luu JSON theo tung LDPlayer."""
    if _should_stop():
        return {}

    screen = adb.screenshot_full()
    if screen is None:
        return {}

    # Tạm tắt đọc stock bằng Gemini theo yêu cầu để tối ưu tốc độ bán
    if getattr(config, "ENABLE_GEMINI_STOCK", False) and gemini_key:
        try:
            ai_stock = _scan_stock_with_gemini(screen, vp_list, gemini_key)
            if ai_stock:
                logger.info(f"[STOCK_AI] Quét kho thành công bằng AI: {ai_stock}")
                
                # Đồng bộ lưu trữ JSON stock giống như cũ
                normalized = _normalize_vp_list(vp_list, threshold, color_threshold, region)
                scanned = {}
                now = datetime.now().isoformat(timespec="seconds")
                device_key = _stock_device_key(adb)
                
                for vp_info in normalized:
                    vp_path = vp_info["path"]
                    if vp_path in ai_stock:
                        item_key = _stock_item_key(vp_path)
                        pos = _find_on_screen(screen, vp_path, threshold=0.7, step_name="scan_stock_pos")
                        if pos:
                            scanned[item_key] = {
                                "stock": ai_stock[vp_path],
                                "last_scan": now,
                                "position": [int(pos[0]), int(pos[1])]
                            }
                if scanned:
                    with _stock_lock:
                        state = _load_stock_state()
                        device_state = state.get(device_key, {})
                        if not isinstance(device_state, dict):
                            device_state = {}
                        for item_key, info in scanned.items():
                            old = device_state.get(item_key, {})
                            sold_count = old.get("sold_count", 0) if isinstance(old, dict) else 0
                            info["sold_count"] = sold_count
                            device_state[item_key] = info
                        state[device_key] = device_state
                        _save_stock_state(state)
                return ai_stock
        except Exception as e:
            logger.warning(f"[STOCK_AI] Quét kho bằng Gemini lỗi, chuyển sang dùng OpenCV: {e}")

    # Fallback dự phòng: OpenCV Template Matching
    normalized = _normalize_vp_list(vp_list, threshold, color_threshold, region)
    scanned = {}
    now = datetime.now().isoformat(timespec="seconds")
    device_key = _stock_device_key(adb)

    for vp_info in normalized:
        if _should_stop():
            return scanned
        vp_path = vp_info["path"]
        item_key = _stock_item_key(vp_path)
        name = os.path.basename(vp_path).replace(".png", "")
        pos = _find_on_screen(
            screen, vp_path,
            threshold=vp_info["threshold"],
            color_threshold=vp_info["color_threshold"],
            step_name=f"scan_stock_{name}",
            region=vp_info.get("region")
        )
        if not pos:
            logger.info(f"[STOCK] Khong thay '{name}' khi quet kho")
            continue

        stock = _read_stock_number_near_item(screen, pos)
        if stock is None:
            logger.info(f"[STOCK] Thay '{name}' tai {pos} nhung chua doc duoc so luong")
            continue

        scanned[item_key] = {
            "stock": stock,
            "last_scan": now,
            "position": [int(pos[0]), int(pos[1])]
        }
        logger.info(f"[STOCK] {name}: {stock}")

    if scanned:
        with _stock_lock:
            state = _load_stock_state()
            device_state = state.get(device_key, {})
            if not isinstance(device_state, dict):
                device_state = {}
            for item_key, info in scanned.items():
                old = device_state.get(item_key, {})
                sold_count = old.get("sold_count", 0) if isinstance(old, dict) else 0
                info["sold_count"] = sold_count
                device_state[item_key] = info
            state[device_key] = device_state
            _save_stock_state(state)
        logger.info(f"[STOCK] Da luu {len(scanned)} SP vao {STOCK_STATE_FILE} cho {device_key}")

    return {path: info["stock"] for path, info in scanned.items()}


def _build_stock_sale_plan(vp_list, stock_map, total_slots, threshold=THRESHOLD,
                           color_threshold=0.6, region=None):
    """Tao danh sach VP can ban cho ca dot dua tren ton kho da quet mot lan."""
    if total_slots <= 0 or not stock_map:
        return []

    normalized = _normalize_vp_list(vp_list, threshold, color_threshold, region)
    candidates = []
    for idx, vp_info in enumerate(normalized):
        item_key = _stock_item_key(vp_info["path"])
        stock = int(stock_map.get(item_key, 0) or 0)
        if stock > 0:
            candidates.append({
                "idx": idx,
                "vp": dict(vp_info),
                "stock": stock,
                "key": item_key,
            })

    if not candidates:
        logger.warning("[STOCK] Khong co VP nao doc duoc ton kho de tao ke hoach ban")
        return []

    plan = []
    used_count = {item["key"]: 0 for item in candidates}
    for _ in range(total_slots):
        available = [item for item in candidates if used_count[item["key"]] < item["stock"]]
        if not available:
            break

        def score(item):
            used = used_count[item["key"]]
            repeat_penalty = (used + 1) ** STOCK_PLAN_REPEAT_PENALTY
            return (item["stock"] / repeat_penalty, item["stock"], -item["idx"])

        selected = max(available, key=score)
        used_count[selected["key"]] += 1
        plan.append(dict(selected["vp"]))

    order = [
        os.path.basename(item["path"]).replace(".png", "")
        for item in plan
    ]
    logger.info(f"[STOCK] Ke hoach ban {len(plan)}/{total_slots} lan: {order}")
    return plan


def _build_random_sale_plan(vp_list, total_slots):
    items = list(vp_list or [])
    if total_slots <= 0 or not items:
        return []
    random.shuffle(items)
    plan = [items[i % len(items)] for i in range(total_slots)]
    order = [
        os.path.basename((item.get("path") if isinstance(item, dict) else item)).replace(".png", "")
        for item in plan
    ]
    logger.info(f"[BAN DO] Ke hoach ban ngau nhien {len(plan)}/{total_slots} lan: {order}")
    return plan


def _mark_stock_sold(adb, path_vp):
    device_key = _stock_device_key(adb)
    item_key = _stock_item_key(path_vp)
    now = datetime.now().isoformat(timespec="seconds")
    with _stock_lock:
        state = _load_stock_state()
        device_state = state.get(device_key, {})
        if not isinstance(device_state, dict):
            device_state = {}
        info = device_state.get(item_key, {})
        if not isinstance(info, dict):
            info = {}
        info["sold_count"] = int(info.get("sold_count", 0)) + 1
        info["last_sold_at"] = now
        device_state[item_key] = info
        state[device_key] = device_state
        _save_stock_state(state)


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


def tim_vat_pham_fallback(adb, vp_list, threshold=THRESHOLD, color_threshold=0.6,
                          region=None):
    """Thử SP theo thứ tự cấu hình. SP không thấy → thử SP kế tiếp.
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
    normalized = _normalize_vp_list(vp_list, threshold, color_threshold, region)

    shuffled = list(normalized)
    names = [os.path.basename(v["path"]).replace('.png', '') for v in shuffled]
    logger.info(f"Thử SP theo thứ tự: {names}")

    for vp_info in shuffled:
        if _should_stop():
            return None, None
        vp_path = vp_info["path"]
        name = os.path.basename(vp_path).replace('.png', '')
        pos = _find_on_screen(screen, vp_path, threshold=vp_info["threshold"],
                              color_threshold=vp_info["color_threshold"],
                              step_name=f"tim_vp_{name}",
                              region=vp_info.get("region"))
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
    # _sleep(CLICK_DELAY)
    # screen = adb.screenshot_full()
    # if screen is None:
    #     return False

    # Bật/tắt quảng cáo
    # pos_qc = _find_btn(adb, screen, "assets/items/cua_hang_qc.png",
    #                     "qc", threshold=0.9, step_name="dat_ban_qc")
    # if pos_qc:
    #     if not bat_qc:
    #         x, y = pos_qc
    #         logger.info(f"Tắt quảng cáo tại ({x}, {y})")
    #         adb.tap(x, y, 0.1)
    #         _sleep(0.3)
    if not bat_qc:
        adb.tap(*INDEX_TAT_QC)
        _sleep(0.1)

    # Tăng số lượng (bấm nút +)
    # pos_cong = _find_btn(adb, screen, "assets/items/cong.png",
    #                       "cong", threshold=0.9, step_name="dat_ban_cong")
    # if pos_cong:
    #     x, y = pos_cong
    #     logger.info(f"Bấm + tăng số lượng tại ({x}, {y})")
    #     adb.tap_sendevent_fast(x, y, 10)
    #     _sleep(0.3)
    #     # Nút + thứ 2 (giá bán) — cũng cache riêng
    #     screen = adb.screenshot_full()
    #     pos_cong2 = _find_btn(adb, screen, "assets/items/cong.png",
    #                            "cong2", threshold=0.9, step_name="dat_ban_cong2")
    #     if pos_cong2:
    #         x2, y2 = pos_cong2
    #         adb.tap_sendevent_fast(x2, y2, 10)
    #         _sleep(0.3)
    adb.tap_sendevent_fast(*INDEX_CONG_1, 10)
    # Xé kim cương nếu config bật
    if xoa_kc:
        screen = adb.screenshot_full()
        pos_kc = _find_btn(adb, screen, "assets/items/core_xoa_vp_kc.png",
                            "xe_kc", threshold=0.85, step_name="dat_ban_xe_kc")
        if pos_kc:
            x, y = pos_kc
            logger.info(f"Xé kim cương tại ({x}, {y})")
            adb.tap(x, y, 0.1)
            _sleep(0.5)

    # Bấm "Đặt bán"
    # pos_ban = _find_btn(adb, screen, "assets/items/dat_ban.png",
    #                      "dat_ban", threshold=0.9, step_name="dat_ban_nut")
    # if pos_ban:
    #     x, y = pos_ban
    #     logger.info(f"Đặt bán tại ({x}, {y})")
    adb.tap(*INDEX_DAT_BAN, 0.1)
    _sleep(CLICK_DELAY)
    return True

    # Cache miss cho đặt bán → chụp lại thử 1 lần
    # screen = adb.screenshot_full()
    # pos_ban = _find_on_screen(screen, "assets/items/dat_ban.png", threshold=0.9,
    #                           step_name="dat_ban_nut_retry")
    # if pos_ban:
    #     _btn_cache["dat_ban"] = pos_ban
    #     x, y = pos_ban
    #     logger.info(f"Đặt bán tại ({x}, {y}) (retry)")
    #     adb.tap(x, y, 0.1)
    #     _sleep(CLICK_DELAY)
    #     return True

    # logger.warning("Không tìm thấy nút đặt bán!")
    # return False


# ================================================================
# STEP 4+5 kết hợp: Tìm VP + đặt bán, thử SP khác nếu fail
# ================================================================
def _thu_dat_ban_voi_fallback(adb, vp_list, path_kho_selected, path_kho_not_selected,
                               threshold, color_threshold, bat_qc, xoa_kc, region=None,
                               stock_map=None):
    """Tìm SP theo thứ tự cấu hình → click → đặt bán.
    vp_list: list of str (path) hoặc list of dict {"path", "threshold", "color_threshold"}
    Nếu SP đó không đặt được (hết hàng) → back ra kho → thử SP khác.
    Return True nếu đặt thành công, False nếu tất cả SP đều fail."""
    if _should_stop():
        return False
    logger.info(f"[STOCK] Thu SP voi danh sach: {vp_list}")
    # Chuẩn hóa vp_list thành list of dict
    normalized = _normalize_vp_list(vp_list, threshold, color_threshold, region)

    shuffled = list(normalized)
    tried = []  # SP đã thử rồi (fail)

    stock_map = _read_stock_map(adb) if stock_map is None else stock_map
    if stock_map:
        shuffled.sort(
            key=lambda vp: stock_map.get(_stock_item_key(vp["path"]), -1),
            reverse=True
        )
        order = [
            f"{os.path.basename(vp['path']).replace('.png', '')}:"
            f"{stock_map.get(_stock_item_key(vp['path']), '?')}"
            for vp in shuffled
        ]
        logger.info(f"[STOCK] Thu SP theo ton kho: {order}")
    logger.info(f"[STOCK] Thu SP theo thu tu: {shuffled}")
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
                          step_name=f"tim_vp_{name}",
                          region=vp_info.get("region"))
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
            _mark_stock_sold(adb, vp_path)
            record_daily_stat(adb, "ban_do")
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
    pos, _ = _find(adb, "assets/items/core_quay_hang_on.png", step_name="post_ban_check_cua_hang")
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

    # Tìm VP đã đặt bán (có thể dựa vào màu sắc khác so với VP chưa đặt)
    for vp_info in data_vps:
        name = os.path.basename(vp_info).replace('.png', '')
        pos, _ = _find(adb, vp_info, threshold=threshold,
                              color_threshold=color_threshold,
                              step_name=f"tim_vp_dat_qc_{name}")
        if pos:
            x, y = pos
            logger.info(f"Tìm thấy VP '{name}' đã đặt bán tại {pos}, click để bật QC")
            adb.tap(x, y, 0.1)
            _sleep(0.3)
            pos_qc, _ = _find(adb, "assets/items/core_dat_quang_cao.png", threshold=0.7,
                            step_name=f"dat_qc_vp_{name}")
            if pos_qc:
                x_qc, y_qc = pos_qc
                logger.info(f"Tìm thấy nút QC tại ({x_qc}, {y_qc}), click để bật QC")
                adb.tap(x_qc, y_qc, 0.1)
                return True
            else:
                logger.warning(f"Không tìm thấy nút QC sau khi click VP '{name}'!")
                # Thoát popup nếu có thể
                _dong_popup(adb)
    _sleep(0.3)
    logger.warning("Không tìm thấy VP nào đã đặt bán để bật QC!")
    return False

def _xu_ly_xe_kc(adb , data_vps, threshold, color_threshold):
    """Nếu config có bật xé kim cương nhưng chưa xé được, thử tìm 1 VP bất kỳ để click vào nút xé KC.
    Tìm trên screen kho, nếu thấy VP đã đặt bán rồi (có thể dựa vào màu sắc) 
    Tìm bút xé KC → click vào để xé KC -> xác nhận -> return True."""
    logger.info(f"[XÉ KC] Danh sach VP để tìm xé KC: {data_vps}")
    if _should_stop():
        return False
    _sleep(0.5)
    
    # Tìm VP đã đặt bán (có thể dựa vào màu sắc khác so với VP chưa đặt)
    for vp_info in data_vps:
        
        name = os.path.basename(vp_info).replace('.png', '')
        pos, _ = _find(adb, vp_info, threshold=threshold,
                              color_threshold=color_threshold,
                              step_name=f"tim_vp_xe_kc_{name}")
        if pos:
            x, y = pos
            logger.info(f"Tìm thấy VP '{name}' đã đặt bán tại {pos}, click để bật xé KC")
            adb.tap(x, y, 0.1)
            _sleep(0.3)
            pos_kc, _ = _find(adb, "assets/items/core_xoa_vp_kc.png", threshold=0.7,
                            step_name="xe_kc_after_click_vp")
            if pos_kc:
                x_kc, y_kc = pos_kc
                logger.info(f"Tìm thấy nút xé KC tại ({x_kc}, {y_kc}), click để xé")
                adb.tap(x_kc, y_kc, 0.1)
                _sleep(0.3)
                pos_dong_y, _ = _find(adb, "assets/items/core_dong_y.png", threshold=0.7,
                            step_name="xe_kc_xac_nhan")
                if pos_dong_y:
                    x_dy, y_dy = pos_dong_y
                    logger.info(f"Tìm thấy nút Đồng ý tại ({x_dy}, {y_dy}), click để xác nhận xé KC")
                    adb.tap(x_dy, y_dy, 0.1)
                    _sleep(0.3)
                    return True
            else:
                logger.warning(f"Không tìm thấy nút xé KC sau khi click VP '{name}'!")
                # Thoát popup nếu có thể
                _dong_popup(adb)
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
    # _reset_btn_cache()

    # Bật debug mode nếu config yêu cầu
    if config.get("debug", False):
        set_debug_mode(True)

    from config import CONFIG_LOAI_KHO

    so_lan = config.get("so_lan_dat_vp", 4)
    loai_kho = config.get("loai_kho", "KTP")
    data_vp = config.get("data", [])
    xoa_kc = config.get("xoa_kc", False)
    bat_qc = config.get("dat_quang_cao", True)
    check_stock = bool(config.get("check_stock", False))
    cfg_threshold = config.get("threshold") or THRESHOLD
    cfg_color_threshold = config.get("color_threshold", 0.6)
    cfg_region = config.get("region")
    qc_templates_cfg = config.get("qc_templates", [])
    xoa_kc_templates_cfg = config.get("xoa_kc_templates", [])
    qc_templates = [_normalize_template_path(t) for t in qc_templates_cfg if t]
    xoa_kc_templates = [_normalize_template_path(t) for t in xoa_kc_templates_cfg if t]
    logger.info(f"Danh sách template QC từ config: {qc_templates_cfg} và sau khi chuẩn hóa: {qc_templates}")
    logger.info(f"Danh sách template xé KC từ config: {xoa_kc_templates_cfg} và sau khi chuẩn hóa: {xoa_kc_templates}")
    is_dat_qc = False  

    if isinstance(data_vp, str):
        data_vp = [vp.strip() for vp in data_vp.split(",") if vp.strip()]

    if not data_vp:
        logger.error("Danh sách vật phẩm trống!")
        return
    can_check_stock = check_stock and len(data_vp) > 1
    if not check_stock:
        logger.info("[STOCK] Tat check stock, ban theo thu tu VP cau hinh")
    if not can_check_stock:
        logger.info("[STOCK] Bo qua check stock")

    # Tìm config kho
    kho_info = next((kho for kho in CONFIG_LOAI_KHO if kho["code"] == loai_kho), None)
    if not kho_info:
        logger.error(f"Loại kho không hợp lệ: {loai_kho}")
        return

    path_kho_selected = kho_info["path_warehouse_select"]
    path_kho_not_selected = kho_info["path_warehouse_not_select"]
    kho_position = kho_info.get("position")

    logger.info(f"=== BÁN HÀNG: kho={loai_kho}, ô={so_lan}, VP={data_vp}, "
                f"QC={bat_qc}, xé KC={xoa_kc}, threshold={cfg_threshold}, color={cfg_color_threshold} ===")

    sale_plan = None if can_check_stock else _build_random_sale_plan(data_vp, so_lan)
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
            xekc = _xu_ly_xe_kc(adb, xoa_kc_templates, cfg_threshold, cfg_color_threshold)
            if xekc:
                logger.info("Đã xé được kim cương cho lần này")

        # Step 2: Tìm ô trống (có kéo trái nếu cần)
        pos = tim_o_ban(adb)
        if not pos:
            logger.warning("Hết ô trống, dừng bán")
            break

        # Click vào ô trống (tối ưu tốc độ click)
        x, y = pos
        adb.taps(x, y, 2, 0.3)
        _sleep(0.3)

        # Step 3: Chọn kho
        if not chon_kho(adb, path_kho_selected, path_kho_not_selected, position=kho_position):
            logger.warning("Không chọn được kho, bỏ qua ô này")
            continue

        # Step 4+5: Tìm VP → đặt bán. Nếu SP hết → thử SP khác trong cùng ô
        if can_check_stock and sale_plan is None:
            stock_map = _scan_va_luu_stock_kho(
                adb, data_vp, cfg_threshold, cfg_color_threshold, region=cfg_region
            )
            sale_plan = _build_stock_sale_plan(
                data_vp, stock_map, so_lan, cfg_threshold, cfg_color_threshold, region=cfg_region
            )
            if not sale_plan:
                logger.warning("[STOCK] Khong tao duoc ke hoach ban, quay ve thu tu VP cau hinh")
                sale_plan = []

        if sale_plan:
            if lan >= len(sale_plan):
                logger.info("[BAN DO] Da ban het ke hoach, dung ban")
                break
            planned_item = sale_plan[lan]
            planned_path = planned_item.get("path") if isinstance(planned_item, dict) else planned_item
            remaining_items = []
            for item in data_vp:
                item_path = item.get("path") if isinstance(item, dict) else item
                if item_path != planned_path:
                    remaining_items.append(item)
            vp_list_lan = [planned_item] + remaining_items
        else:
            vp_list_lan = data_vp

        da_ban = _thu_dat_ban_voi_fallback(
            adb, vp_list_lan, path_kho_selected, path_kho_not_selected,
            cfg_threshold, cfg_color_threshold, bat_qc, xoa_kc, region=cfg_region,
            stock_map={}
        )
        if not da_ban:
            logger.warning("Không đặt được SP nào cho ô này")
        else:
            is_dat_qc = True # Đã đặt được SP, coi như đã đăt qc
        _sleep(0.3)
    if is_dat_qc == False and bat_qc:
        # chon 1 vp bất kỳ để bật qc, tìm danh sách vp để tìm vp đã đặt qc rồi bật qc
        _xu_ly_dat_qc(adb, qc_templates, cfg_threshold, cfg_color_threshold)
            
    _xu_ly_sau_dat_ban(adb)
    logger.info("=== Hoàn thành bán hàng ===")
