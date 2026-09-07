import os
import sys
import glob as glob_mod
from config import (
    get_configs_dir,
    CONFIG_LOAI_KHO,
    REGION_PRESETS,
    REGION_FROM_CROP,
    CURRENT_VERSION,
    GITHUB_API_URL,
    GITHUB_RELEASES_URL,
)

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONFIG_DIR = get_configs_dir()
SELECTED_DEVICE_FILE = os.path.join(BASE_DIR, "selected_device.json")
ITEMS_DIR = os.path.join(BASE_DIR, "assets", "items")
GUI_LOG_MAX_LINES = 1000

DEFAULT_SETTINGS = {
    "loop_tong_mode": "count",
    "loop_tong": 1,
    "loop": 1,
    "threshold": 0.85,
    "bat_trong_cay": True,
    "bat_may": True,
    "bat_ban_vp": False,
    "bat_thu_hoach": True,
    "bat_mo_ruong": False,
    "bat_giao_cu": False,
    "bat_giao_tom": False,
    "bat_sxcam": False,
    "bat_sang_ban_be": False,
    "bat_cap_nhat_khoi_dong": False,
    "bat_khoi_dong_lai_ld": False,
    "thoi_gian_khoi_dong_lai": 5.0,
    "bat_ai_recovery": False,
    "gemini_api_key": "",
    "bat_yolo": False,
    "yolo_model_path": "configs/kvtm_yolo.onnx"
}

DEFAULT_BAN_DO = {
    "loai_kho": "KTP",
    "so_lan_dat_vp": 4,
    "data": [],
    "xoa_kc": True,
    "dat_quang_cao": True,
    "check_stock": False,
    "qc_templates": [],
    "xoa_kc_templates": [],
    "dsvp_bo_qua": [],
    "tom_vp": "",
    "tom_kho": "KTP",
    "threshold": 0.85,
    "color_threshold": 0.6
}


def scan_all_templates():
    """Scan all *.png in assets/items/"""
    files = glob_mod.glob(os.path.join(ITEMS_DIR, "*.png"))
    return sorted([os.path.basename(f) for f in files])


def scan_kho_templates():
    """Scan assets/items/kho_*.png"""
    files = glob_mod.glob(os.path.join(ITEMS_DIR, "*.png"))
    return sorted([os.path.basename(f) for f in files])


def normalize_region(region):
    """Return region as [x, y, w, h] or None."""
    if region in (None, "", []):
        return None
    if isinstance(region, str):
        parts = [p.strip() for p in region.replace(";", ",").split(",")]
    elif isinstance(region, (list, tuple)):
        parts = list(region)
    else:
        return None
    if len(parts) != 4:
        return None
    try:
        x, y, w, h = [int(float(p)) for p in parts]
    except (TypeError, ValueError):
        return None
    if w <= 0 or h <= 0:
        return None
    return [x, y, w, h]


def format_region(region):
    region = normalize_region(region)
    return "" if region is None else ",".join(str(v) for v in region)


def scan_row_templates():
    """Scan assets/items/num/*.png"""
    files = glob_mod.glob(os.path.join(ITEMS_DIR, "num", "*.png"))
    results = []
    for f in files:
        name = os.path.basename(f)
        if name.replace(".png", "").isdigit():
            results.append(name)
    return sorted(results, key=lambda x: int(x.replace(".png", "")))
