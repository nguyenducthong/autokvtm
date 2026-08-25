import csv
import glob
import json
import logging
import os
import time
from datetime import datetime

import config
from config import CONFIG_LOAI_KHO, INDEX_NHA_KHO_MAC_DINH
from core.adb import ADBController
from core.image import ImageProcessor
from core.ban_do import _read_stock_number_near_item, ve_nha_neu_can
from utils.utils import setup_thread


logger = logging.getLogger(__name__)
img = ImageProcessor()

OUTPUT_DIR = os.path.join("data", "kho_thanh_pham")
ITEM_REGION = (10, 213, 410, 383)
MAX_SCAN_PAGES = 8
NO_NEW_PAGE_LIMIT = 2


def _should_stop(stop_event=None):
    return stop_event is not None and stop_event.is_set()


def _sleep(seconds, stop_event=None):
    if stop_event is not None:
        stop_event.wait(seconds)
    else:
        time.sleep(seconds)


def _find_on_screen(screen, template_path, threshold=0.82, color_threshold=0.6, region=None):
    if screen is None:
        return None
    return img.find_template_color(
        template_path=template_path,
        threshold=threshold,
        color_threshold=color_threshold,
        screen_img=screen,
        region=region,
    )


def _tap_template(adb, template_path, threshold=0.82, color_threshold=0.6, timeout=3,
                  stop_event=None):
    end = time.time() + timeout
    while time.time() < end:
        if _should_stop(stop_event):
            return False
        screen = adb.screenshot_full()
        pos = _find_on_screen(screen, template_path, threshold=threshold,
                              color_threshold=color_threshold)
        if pos:
            adb.tap(*pos)
            _sleep(0.7, stop_event)
            return True
        _sleep(0.5, stop_event)
    return False


def _kho_thanh_pham_info():
    return next((kho for kho in CONFIG_LOAI_KHO if kho.get("code") == "KTP"), None)


def _open_kho_thanh_pham(adb, stop_event=None):
    """Ve tang 0, tap nha, mo tab kho thanh pham."""
    if _should_stop(stop_event):
        return False

    if not ve_nha_neu_can(adb):
        logger.warning("[KHO TP] Khong ve duoc tang 0")
        return False
    if _should_stop(stop_event):
        return False

    adb.tap(*INDEX_NHA_KHO_MAC_DINH)
    _sleep(1.0, stop_event)
    kho_info = _kho_thanh_pham_info()
    if not kho_info:
        logger.error("[KHO TP] Khong co config kho thanh pham")
        return False

    x, y = kho_info.get("position", (361, 353))
    adb.tap(x, y)
    _sleep(1.0, stop_event)

    screen = adb.screenshot_full()
    selected = _find_on_screen(screen, kho_info["path_warehouse_select"],
                               threshold=0.7, color_threshold=0.5)
    not_selected = _find_on_screen(screen, kho_info["path_warehouse_not_select"],
                                   threshold=0.7, color_threshold=0.5)
    if selected:
        return True
    if not_selected:
        adb.tap(*not_selected)
        _sleep(0.8, stop_event)
        return True
    return True


def load_danh_sach_quet_kho():
    """Load data/danh_sach_quet_kho.json -> (templates_mapping dict {display_name: path}, ordered_display_names list)."""
    import sys
    json_path = os.path.join("data", "danh_sach_quet_kho.json")
    if not os.path.exists(json_path):
        return {}, []

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error("[KHO TP] Lỗi đọc file danh_sach_quet_kho.json: %s", e)
        return {}, []

    base_dir = os.path.abspath('.')
    is_frozen = getattr(sys, 'frozen', False)
    mei_dir = getattr(sys, '_MEIPASS', base_dir) if is_frozen else base_dir

    templates_mapping = {}
    ordered_items = []

    for display_name, img_name in data.items():
        ordered_items.append(display_name)
        p1 = os.path.join(base_dir, "assets", "items", img_name)
        if os.path.exists(p1):
            templates_mapping[display_name] = p1
            continue
        if is_frozen:
            p2 = os.path.join(mei_dir, "assets", "items", img_name)
            if os.path.exists(p2):
                templates_mapping[display_name] = p2
                continue
        logger.warning("[KHO TP] Không tìm thấy file ảnh '%s' cho '%s'", img_name, display_name)

    return templates_mapping, ordered_items


def list_kho_thanh_pham_templates():
    import sys
    excluded = {
        "core_kho_event.png",
        "core_kho_event_0.png",
        "core_kho_nong_san.png",
        "core_kho_nong_san_0.png",
        "core_kho_thanh_pham.png",
        "core_kho_thanh_pham_0.png",
        "core_kho_vat_dung.png",
    }
    
    base_dir = os.path.abspath('.')
    is_frozen = getattr(sys, 'frozen', False)
    
    search_pattern = os.path.join(base_dir, "assets", "items", "kho_*.png")
    paths = glob.glob(search_pattern)
    
    if not paths and is_frozen:
        mei_dir = getattr(sys, '_MEIPASS', base_dir)
        search_pattern_mei = os.path.join(mei_dir, "assets", "items", "kho_*.png")
        paths = glob.glob(search_pattern_mei)

    filtered_paths = []
    for path in paths:
        name = os.path.basename(path)
        if name in excluded or name.endswith("_0.png"):
            continue
        filtered_paths.append(path)
    return sorted(filtered_paths, key=lambda p: os.path.basename(p))


def _scan_visible_page(adb, templates, threshold=0.82, color_threshold=0.6):
    screen = adb.screenshot_full()
    results = {}
    if screen is None:
        return results

    if isinstance(templates, dict):
        items_to_scan = templates.items()
    elif isinstance(templates, list) and templates and isinstance(templates[0], tuple):
        items_to_scan = templates
    else:
        items_to_scan = [(os.path.splitext(os.path.basename(p))[0], p) for p in templates]

    for item_name, template_path in items_to_scan:
        pos = _find_on_screen(
            screen,
            template_path,
            threshold=threshold,
            color_threshold=color_threshold,
            region=ITEM_REGION,
        )
        if not pos:
            continue
        stock = _read_stock_number_near_item(screen, pos)
        if stock is None:
            logger.info("[KHO TP] Thấy %s tại %s nhưng chưa đọc được số", item_name, pos)
            continue
        results[item_name] = stock
        logger.info("[KHO TP] %s=%s", item_name, stock)
    return results


def _scan_visible_page_gemini(adb, ordered_items, api_key=None, model_name=None, device_name=None):
    """Gửi ảnh chụp màn hình bảng kho cho Gemini AI VLM để đọc tên vật phẩm và số lượng tương ứng."""
    api_key = api_key or getattr(config, "GEMINI_API_KEY", "")
    if not api_key:
        logger.warning("[KHO TP GEMINI] Thiếu Gemini API Key trong config")
        return {}

    screen = adb.screenshot_full()
    if screen is None:
        return {}

    try:
        import cv2
        import base64
        import requests
        from core.ai_recovery import log_gemini_request

        h, w = screen.shape[:2]
        crop_y1, crop_y2 = max(0, int(h * 0.25)), min(h, int(h * 0.95))
        crop_img = screen[crop_y1:crop_y2, :]

        success, encoded_img = cv2.imencode(".jpg", crop_img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not success:
            return {}
        image_b64 = base64.b64encode(encoded_img.tobytes()).decode("utf-8")

        target_str = ", ".join(ordered_items[:45])
        prompt = (
            "Đây là ảnh chụp phần giao diện Kho Thành Phẩm của game Khu Vườn Trên Mây.\n"
            "Mỗi ô vật phẩm hiển thị hình ảnh sản phẩm và con số ghi số lượng nằm ở góc sản phẩm.\n"
            f"Danh sách các vật phẩm cần kiểm tra (tiếng Việt): [{target_str}].\n\n"
            "Hãy nhìn thật kỹ từng ô vật phẩm đang xuất hiện trên màn hình và đọc chính xác số lượng tương ứng.\n"
            "Trả về duy nhất định dạng JSON chuẩn (không chứa các ký tự ```json):\n"
            "{\n"
            '  "items": [\n'
            '    {"name": "tên vật phẩm chuẩn trong danh sách", "quantity": số_lượng_chính_xác_đọc_được}\n'
            '  ]\n'
            "}"
        )

        model_str = model_name or getattr(config, "GEMINI_MODEL", "gemini-3.5-flash-lite") or "gemini-3.5-flash-lite"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_str}:generateContent?key={api_key}"
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
                "temperature": 0.1
            }
        }

        response = requests.post(url, headers=headers, json=payload, timeout=25)
        if response.status_code == 200:
            res_json = response.json()
            resp_text = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
            data = json.loads(resp_text)
            parsed_results = {}
            for item in data.get("items", []):
                name = item.get("name")
                qty = item.get("quantity")
                if name and isinstance(qty, (int, float)):
                    parsed_results[name] = int(qty)
                    logger.info("[KHO TP GEMINI] %s = %s", name, qty)
            log_gemini_request(device_name or "main", 0, "SUCCESS", 200, reason="Quét kho Gemini", raw_response=resp_text, model=model_str)
            return parsed_results
        else:
            logger.error("[KHO TP GEMINI] Error HTTP %s: %s", response.status_code, response.text)
            log_gemini_request(device_name or "main", 0, "ERROR", response.status_code, reason=f"HTTP {response.status_code}", model=model_str)
    except Exception as e:
        logger.error("[KHO TP GEMINI] Exception: %s", e)

    return {}


def scan_kho_thanh_pham(adb: ADBController, device_name=None, stop_event=None,
                        templates=None, use_gemini=False, api_key=None):
    """Open KTP and scan stock. Returns {item_name: count}."""
    setup_thread(adb, stop_event, device_name=device_name)
    
    custom_mapping, ordered_items = load_danh_sach_quet_kho()
    if custom_mapping:
        scan_items = custom_mapping
    else:
        scan_items = templates or list_kho_thanh_pham_templates()

    if not _open_kho_thanh_pham(adb, stop_event=stop_event):
        return {}

    results = {}
    no_new_pages = 0
    for page in range(MAX_SCAN_PAGES):
        if _should_stop(stop_event):
            break

        page_results = {}
        if use_gemini:
            logger.info("[KHO TP] Đang quét trang %s bằng Gemini AI...", page + 1)
            page_results = _scan_visible_page_gemini(adb, ordered_items or list(custom_mapping.keys()), api_key=api_key, device_name=device_name)

        if not page_results:
            logger.info("[KHO TP] Đang quét trang %s bằng OpenCV Offline...", page + 1)
            page_results = _scan_visible_page(adb, scan_items)

        before = len(results)
        for k, v in page_results.items():
            if k not in results:
                results[k] = v
        new_count = len(results) - before
        logger.info("[KHO TP] Page %s: %s item mới", page + 1, new_count)

        if new_count <= 0:
            no_new_pages += 1
            if no_new_pages >= NO_NEW_PAGE_LIMIT:
                break
        else:
            no_new_pages = 0

        adb.swipe(175, 545, 175, 495, duration=500)
        _sleep(0.1, stop_event)

    return results


def export_kho_thanh_pham_csv(results_by_device, output_path=None):
    """Export matrix CSV: item, device display names..."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if output_path is None:
        output_path = get_today_kho_thanh_pham_csv_path()

    devices = list(results_by_device.keys())
    
    custom_mapping, ordered_items = load_danh_sach_quet_kho()
    if ordered_items:
        all_items = ordered_items
    else:
        all_items = sorted({
            item
            for result in results_by_device.values()
            for item in result.keys()
        })

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["item"] + devices)
        for item in all_items:
            writer.writerow([item] + [
                results_by_device.get(device, {}).get(item, 0)
                for device in devices
            ])

    return output_path


def get_today_kho_thanh_pham_csv_path():
    date_text = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(OUTPUT_DIR, f"kho_thanh_pham_{date_text}.csv")

