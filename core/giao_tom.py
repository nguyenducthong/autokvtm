import logging
import os
import re
import time

import cv2
import numpy as np
import pytesseract

from config import (
    INDEX_THOAT_SAN_XUAT_MAC_DINH,
    INDEX_TOM_KHO,
    INDEX_TOM_MAC_DINH,
    INDEX_TOM_O_MUA,
    REGION_TOM_O_MUA,
)
from core.image import ImageProcessor
from utils.daily_stats import record_daily_stat
from utils.utils import tim_may_v2, xuong_nha

logger = logging.getLogger(__name__)
img = ImageProcessor()

TOM_TEMPLATE = "assets/items/tom.png"
TIM_HANG_TEMPLATE = "assets/items/tim_hang.png"
TOM_THAY_HANG_TEMPLATE = "assets/items/tom_thay_hang.png"
QUAY_ITEMS_TOM_TEMPLATE = "assets/items/quay_items_tom.png"
NOT_BUY_TOM_TEMPLATE = "assets/items/not_buy_tom.png"
KHONG_MUA_DAU_TEMPLATE = "assets/items/khong_mua_dau.png"
DAY_DI_MA_TEMPLATE = "assets/items/day_di_ma.png"

TOM_ROW_0_REGION = (82, 708, 205, 89)
TOM_KHO_REGION = (7, 259, 469, 450)
TOM_MUA_REGION = REGION_TOM_O_MUA
TOM_FIND_TIMEOUT = 30


def _sleep(seconds, stop_event=None):
    if stop_event is not None:
        stop_event.wait(seconds)
    else:
        time.sleep(seconds)


def _should_stop(stop_event=None):
    return stop_event is not None and stop_event.is_set()


def _normalize_template_path(path: str) -> str:
    if not path:
        return ""
    if os.path.isabs(path) or path.startswith("assets/"):
        return path
    return os.path.join("assets/items", path)


def _tim_anh(adb, template_path: str, threshold: float = 0.82, region=None):
    template_path = _normalize_template_path(template_path)
    if not template_path or not os.path.exists(template_path):
        logger.warning("[GIAO TÔM] Thiếu ảnh mẫu: %s", template_path)
        return None
    screen = adb.screenshot_full()
    if screen is None:
        return None
    return img.find_template_color(
        template_path=template_path,
        threshold=threshold,
        screen_img=screen,
        region=region,
    )


def _doi_anh(adb, template_path: str, timeout: int = TOM_FIND_TIMEOUT,
             interval: float = 1.0, threshold: float = 0.82,
             stop_event=None, region=None):
    end_time = time.time() + timeout
    while time.time() < end_time:
        if _should_stop(stop_event):
            return None
        pos = _tim_anh(adb, template_path, threshold=threshold, region=region)
        if pos:
            return pos
        _sleep(interval, stop_event)
    return None


def _tap_neu_thay(adb, template_path: str, timeout: int = 8,
                  stop_event=None, region=None) -> bool:
    pos = _doi_anh(adb, template_path, timeout=timeout, interval=1,
                   stop_event=stop_event, region=region)
    if not pos:
        return False
    adb.tap(*pos)
    _sleep(1.0, stop_event)
    return True


def _ve_tang_0(stop_event=None):
    if _should_stop(stop_event):
        return False
    ok = tim_may_v2("assets/items/num/0.png", 0)
    if not ok:
        logger.warning("[GIAO TÔM] tim_may_v2 về tầng 0 thất bại, chuyển sang xuong_nha")
        xuong_nha()
    return True


def _tim_vp_trong_kho(adb, vp_path: str, stop_event=None):
    for lan_keo in range(12):
        if _should_stop(stop_event):
            return None
        pos = _tim_anh(adb, vp_path, threshold=0.82, region=TOM_KHO_REGION)
        if pos:
            logger.info("[GIAO TÔM] Tìm thấy vật phẩm ở kho sau %s lần kéo", lan_keo)
            return pos
        adb.swipe(240, 500, 249, 360, 500)
        _sleep(0.8, stop_event)
    return None


def _doi_trang_thai_sau_khi_tap_tom(adb, timeout=6, stop_event=None):
    end_time = time.time() + timeout
    while time.time() < end_time:
        if _should_stop(stop_event):
            return None, None
        if _tim_anh(adb, DAY_DI_MA_TEMPLATE, threshold=0.82):
            return "day_di_ma", None
        pos_tim_hang = _tim_anh(adb, TIM_HANG_TEMPLATE, threshold=0.82)
        if pos_tim_hang:
            return "tim_hang", pos_tim_hang
        if _tim_anh(adb, KHONG_MUA_DAU_TEMPLATE, threshold=0.82):
            return "khong_mua_dau", None
        _sleep(0.5, stop_event)
    return None, None


def _tim_tat_ca_vi_tri(adb, template_path: str, threshold: float = 0.78, region=None):
    template_path = _normalize_template_path(template_path)
    if not template_path or not os.path.exists(template_path):
        logger.warning("[GIAO TÔM] Thiếu ảnh mẫu: %s", template_path)
        return []

    screen = adb.screenshot_full()
    if screen is None:
        return []

    template = cv2.imread(template_path, cv2.IMREAD_UNCHANGED)
    if template is None:
        return []
    if template.ndim == 3 and template.shape[2] == 4:
        template = template[:, :, :3]

    rx, ry = 0, 0
    if region is not None:
        rx, ry, rw, rh = region
        h_max, w_max = screen.shape[:2]
        rx = max(0, min(rx, w_max - 1))
        ry = max(0, min(ry, h_max - 1))
        rw = max(1, min(rw, w_max - rx))
        rh = max(1, min(rh, h_max - ry))
        screen = screen[ry:ry + rh, rx:rx + rw]

    th, tw = template.shape[:2]
    if th > screen.shape[0] or tw > screen.shape[1]:
        return []

    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    locations = np.where(result >= threshold)
    candidates = []
    for pt in zip(*locations[::-1]):
        score = float(result[pt[1], pt[0]])
        candidates.append((score, pt[0], pt[1]))
    candidates.sort(reverse=True, key=lambda x: x[0])

    used = []
    points = []
    for score, x, y in candidates:
        if any(abs(x - ux) < tw // 2 and abs(y - uy) < th // 2 for ux, uy in used):
            continue
        used.append((x, y))
        points.append((x + rx + tw // 2, y + ry + th // 2, score))
    points.sort(key=lambda p: p[0])
    return points


def _chon_quay_item_ben_phai_nhat(adb, stop_event=None):
    if _should_stop(stop_event):
        return None
    points = _tim_tat_ca_vi_tri(
        adb,
        QUAY_ITEMS_TOM_TEMPLATE,
        threshold=0.6,
        region=TOM_MUA_REGION,
    )
    if not points:
        logger.info("[GIAO TÔM] Không tìm thấy quay_items_tom.png để fallback")
        return None
    x, y, score = points[-1]
    logger.info("[GIAO TÔM] Fallback chọn item bên phải nhất: (%s,%s) score=%.3f", x, y, score)
    return int(x), int(y)


def _chon_o_mua_lon_nhat(vi_tri_vp=None):
    options = []
    for idx, item in enumerate(INDEX_TOM_O_MUA):
        tap = item.get("tap") if isinstance(item, dict) else None
        quantity = item.get("quantity", item.get("qty", 0)) if isinstance(item, dict) else 0
        gold = item.get("gold", 0) if isinstance(item, dict) else 0
        name = item.get("name", f"Ô {idx + 1}") if isinstance(item, dict) else f"Ô {idx + 1}"
        options.append((quantity, gold, idx, tap, name))
    if not options:
        return None

    quantity, gold, idx, tap, name = max(options, key=lambda x: (x[0], x[1]))
    if vi_tri_vp:
        if idx >= len(vi_tri_vp):
            idx = len(vi_tri_vp) - 1
        x, y, score = vi_tri_vp[idx]
        return quantity, gold, (int(x), int(y)), name, score

    if tap and tuple(tap) != (0, 0):
        return quantity, gold, tuple(tap), name, None
    return None


def _cac_o_mua_bang_template(vi_tri_vp=None):
    candidates = []
    for idx, item in enumerate(INDEX_TOM_O_MUA):
        if not isinstance(item, dict):
            continue
        quantity = item.get("quantity", item.get("qty", 0)) or 0
        gold = item.get("gold", 0) or 0
        name = item.get("name", f"Ô {idx + 1}")
        tap = item.get("tap")
        score = None

        if vi_tri_vp and idx < len(vi_tri_vp):
            x, y, score = vi_tri_vp[idx]
            tap_pos = (int(x), int(y))
        elif tap and tuple(tap) != (0, 0):
            tap_pos = tuple(tap)
        else:
            continue

        candidates.append({
            "quantity": int(quantity),
            "gold": int(gold),
            "tap_pos": tap_pos,
            "name": name,
            "source": "template",
            "raw": name,
            "score": score,
        })
    return candidates


def _doc_cac_o_mua_bang_ocr(adb, region=TOM_MUA_REGION):
    try:
        pytesseract.get_tesseract_version()
    except Exception as e:
        logger.warning("[GIAO TÔM] Không dùng OCR vì chưa cài Tesseract: %s", e)
        return []

    screen = adb.screenshot_full()
    if screen is None:
        return []

    rx, ry, rw, rh = region
    h_max, w_max = screen.shape[:2]
    rx = max(0, min(rx, w_max - 1))
    ry = max(0, min(ry, h_max - 1))
    rw = max(1, min(rw, w_max - rx))
    rh = max(1, min(rh, h_max - ry))
    crop = screen[ry:ry + rh, rx:rx + rw]

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    candidates = []
    config = "--psm 6 -c tessedit_char_whitelist=xX0123456789"
    for ocr_img in (binary, cv2.bitwise_not(binary)):
        try:
            data = pytesseract.image_to_data(ocr_img, config=config, output_type=pytesseract.Output.DICT)
        except Exception as e:
            logger.warning("[GIAO TÔM] OCR lỗi, chuyển sang fallback ảnh: %s", e)
            return []
        count = len(data.get("text", []))
        for i in range(count):
            raw = (data["text"][i] or "").strip()
            if not raw:
                continue
            text = raw.replace(" ", "")
            match = re.search(r"[xX](\d+)", text)
            x = data["left"][i]
            y = data["top"][i]
            w = data["width"][i]
            h = data["height"][i]
            if not match and i + 1 < count and text.lower() == "x":
                next_text = (data["text"][i + 1] or "").strip()
                if next_text.isdigit():
                    match = re.match(r"(\d+)", next_text)
                    x2 = data["left"][i + 1]
                    y2 = data["top"][i + 1]
                    w2 = data["width"][i + 1]
                    h2 = data["height"][i + 1]
                    left = min(x, x2)
                    top = min(y, y2)
                    right = max(x + w, x2 + w2)
                    bottom = max(y + h, y2 + h2)
                    x, y, w, h = left, top, right - left, bottom - top
            if not match:
                continue

            quantity = int(match.group(1))
            cx = rx + int((x + w / 2) / 3)
            cy = ry + int((y + h / 2) / 3)
            candidates.append({
                "quantity": quantity,
                "gold": 0,
                "tap_pos": (cx, cy),
                "name": f"OCR x{quantity}",
                "source": "ocr",
                "raw": raw,
                "score": None,
            })

    if not candidates:
        logger.info("[GIAO TÔM] OCR không đọc được số lượng x... trong vùng %s", region)
        return []

    logger.info("[GIAO TÔM] OCR đọc được %s ô mua: %s", len(candidates),
                [(c["quantity"], c["tap_pos"], c["raw"]) for c in candidates])
    return candidates


def _doc_o_mua_lon_nhat_bang_ocr(adb, region=TOM_MUA_REGION):
    candidates = _doc_cac_o_mua_bang_ocr(adb, region=region)
    if not candidates:
        return None

    best = max(candidates, key=lambda item: item["quantity"])
    logger.info("[GIAO TÔM] OCR đọc ô lớn nhất: %s tại (%s,%s), text=%s",
                best["quantity"], best["tap_pos"][0], best["tap_pos"][1], best["raw"])
    return best["quantity"], best["tap_pos"], best["raw"]


def _mua_o_lon_nhat(adb, vp_path: str, stop_event=None):
    candidates = []
    ocr_candidates = _doc_cac_o_mua_bang_ocr(adb, region=TOM_MUA_REGION)
    candidates.extend(ocr_candidates)

    vi_tri_vp = _tim_tat_ca_vi_tri(adb, vp_path, threshold=0.78, region=TOM_MUA_REGION)
    template_candidates = _cac_o_mua_bang_template(vi_tri_vp=vi_tri_vp)
    candidates.extend(template_candidates)

    logger.info("[GIAO TÔM] Tìm thấy %s ô mua theo ảnh vật phẩm, %s ô OCR, %s ô template",
                len(vi_tri_vp), len(ocr_candidates), len(template_candidates))

    if not candidates:
        fallback_tap = _chon_quay_item_ben_phai_nhat(adb, stop_event=stop_event)
        if fallback_tap:
            logger.info("[GIAO TÔM] Không có số lượng, fallback mua item bên phải nhất: %s", fallback_tap)
            adb.tap(*fallback_tap)
            _sleep(1.0, stop_event)
            return True
        logger.warning("[GIAO TÔM] Chưa tìm được vị trí ô mua bằng OCR/template")
        return True

    best = max(candidates, key=lambda item: (item["quantity"], item.get("gold", 0)))
    score = best.get("score")
    logger.info("[GIAO TÔM] Mua ô lớn nhất: %s source=%s x%s gold=%s vị trí=%s score=%s raw=%s",
                best["name"], best["source"], best["quantity"], best.get("gold", 0),
                best["tap_pos"], f"{score:.3f}" if score is not None else "n/a",
                best.get("raw", ""))
    tap_pos = best["tap_pos"]
    adb.tap(*tap_pos)
    _sleep(1.0, stop_event)
    return True


def _doi_tim_hang_va_mua(adb, vp_path: str, stop_event=None):
    logger.info("[GIAO TÔM] Đợi tìm thấy hàng")
    _sleep(35, stop_event)
    adb.tap(*INDEX_TOM_MAC_DINH)
    _sleep(1.0, stop_event)
    return _mua_o_lon_nhat(adb, vp_path, stop_event=stop_event)


def _chon_vat_pham_va_tim_hang(adb, vp_path: str, kho: str, stop_event=None):
    kho_pos = INDEX_TOM_KHO.get(kho, INDEX_TOM_KHO.get("KTP"))
    if not kho_pos:
        logger.warning("[GIAO TÔM] Chưa cấu hình vị trí kho cho %s", kho)
        return False
    logger.info("[GIAO TÔM] Vào kho %s", kho)
    adb.tap(*kho_pos)
    _sleep(1.0, stop_event)

    pos_vp = _tim_vp_trong_kho(adb, vp_path, stop_event=stop_event)
    if not pos_vp:
        logger.info("[GIAO TÔM] Không tìm thấy vật phẩm: %s", vp_path)
        adb.tap(*INDEX_THOAT_SAN_XUAT_MAC_DINH)
        return False
    adb.tap(*pos_vp)
    _sleep(1.0, stop_event)

    if not _tap_neu_thay(adb, TIM_HANG_TEMPLATE, timeout=8, stop_event=stop_event):
        logger.info("[GIAO TÔM] Không thấy nút tim_hang.png")
        adb.tap(*INDEX_THOAT_SAN_XUAT_MAC_DINH)
        return False
    return True


def giao_tom(adb, vp_path: str, kho: str = "KTP", stop_event=None) -> bool:
    """Xử lý giao tôm."""
    vp_path = _normalize_template_path(vp_path)
    if _should_stop(stop_event):
        return False
    if not vp_path:
        logger.info("[GIAO TÔM] Chưa cấu hình vật phẩm cần lấy")
        return False

    _ve_tang_0(stop_event=stop_event)
    if _should_stop(stop_event):
        return False
    if _tim_anh(adb, NOT_BUY_TOM_TEMPLATE, threshold=0.82):
        logger.info("[GIAO TÔM] Thấy not_buy_tom.png, bỏ qua giao tôm")
        return False

    logger.info("[GIAO TÔM] Tap tôm")
    adb.tap(*INDEX_TOM_MAC_DINH)
    _sleep(1.0, stop_event)

    trang_thai_tom, pos_tim_hang = _doi_trang_thai_sau_khi_tap_tom(adb, timeout=6, stop_event=stop_event)
    if trang_thai_tom == "day_di_ma":
        logger.info("[GIAO TÔM] Thấy day_di_ma.png, kết thúc giao tôm")
        return False

    if trang_thai_tom == "khong_mua_dau":
        logger.info("[GIAO TÔM] Đã có khong_mua_dau.png, đi thẳng bước mua hàng")
        ok = _mua_o_lon_nhat(adb, vp_path, stop_event=stop_event)
        if ok:
            record_daily_stat(adb, "giao_tom")
        return ok

    if trang_thai_tom == "tim_hang":
        logger.info("[GIAO TÔM] Thấy tim_hang.png, chọn vật phẩm để mua")
    else:
        logger.info("[GIAO TÔM] Chưa rõ trạng thái sau khi tap tôm, thử chọn vật phẩm")

    if not _chon_vat_pham_va_tim_hang(adb, vp_path, kho, stop_event=stop_event):
        return False
    ok = _doi_tim_hang_va_mua(adb, vp_path, stop_event=stop_event)
    if ok:
        record_daily_stat(adb, "giao_tom")
    return ok
