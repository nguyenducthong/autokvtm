import csv
import glob
import logging
import os
import time
from datetime import datetime

from config import CONFIG_LOAI_KHO, INDEX_NHA_KHO_MAC_DINH
from core.adb import ADBController
from core.image import ImageProcessor
from core.ban_do import _read_stock_number_near_item, ve_nha_neu_can
from utils.utils import setup_thread


logger = logging.getLogger(__name__)
img = ImageProcessor()

OUTPUT_DIR = os.path.join("data", "kho_thanh_pham")
ITEM_REGION = (35, 213, 389, 383)
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


def list_kho_thanh_pham_templates():
    excluded = {
        "kho_event.png",
        "kho_event_0.png",
        "kho_nong_san.png",
        "kho_nong_san_0.png",
        "kho_thanh_pham.png",
        "kho_thanh_pham_0.png",
        "kho_vat_dung.png",
    }
    paths = []
    for path in glob.glob(os.path.join("assets", "items", "kho_*.png")):
        name = os.path.basename(path)
        if name in excluded or name.endswith("_0.png"):
            continue
        paths.append(path)
    return sorted(paths, key=lambda p: os.path.basename(p))


def _scan_visible_page(adb, templates, threshold=0.82, color_threshold=0.6):
    screen = adb.screenshot_full()
    results = {}
    if screen is None:
        return results

    for template_path in templates:
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
            logger.info("[KHO TP] Thay %s tai %s nhung chua doc duoc so",
                        os.path.basename(template_path), pos)
            continue
        item_name = os.path.splitext(os.path.basename(template_path))[0]
        results[item_name] = stock
        logger.info("[KHO TP] %s=%s", item_name, stock)
    return results


def scan_kho_thanh_pham(adb: ADBController, device_name=None, stop_event=None,
                        templates=None):
    """Open KTP and scan stock. Returns {item_name: count}."""
    setup_thread(adb, stop_event, device_name=device_name)
    templates = templates or list_kho_thanh_pham_templates()
    if not _open_kho_thanh_pham(adb, stop_event=stop_event):
        return {}

    results = {}
    no_new_pages = 0
    for page in range(MAX_SCAN_PAGES):
        if _should_stop(stop_event):
            break
        page_results = _scan_visible_page(adb, templates)
        before = len(results)
        results.update(page_results)
        new_count = len(results) - before
        logger.info("[KHO TP] Page %s: %s item moi", page + 1, new_count)

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
                results_by_device.get(device, {}).get(item, "")
                for device in devices
            ])

    return output_path


def get_today_kho_thanh_pham_csv_path():
    date_text = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(OUTPUT_DIR, f"kho_thanh_pham_{date_text}.csv")
