import cv2
import numpy as np
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCREENSHOTS_DIR = ROOT / 'assets' / 'screenshots'
DEBUG_DIR = ROOT / 'debug' / 'ab_tests'
TEMPLATES = [
    ROOT / 'assets' / 'items' / 'num' / '1.png',
    ROOT / 'assets' / 'items' / 'thu_hoach.png',
    ROOT / 'assets' / 'items' / 'check_xuong_1.png',
    ROOT / 'assets' / 'items' / 'hong_say.png',
    ROOT / 'assets' / 'items' / 'cay' / 'ripe' / 'tao.png',
]
THRESHOLD = 0.8

os.makedirs(DEBUG_DIR, exist_ok=True)


def old_match(screen, template_path):
    template = cv2.imread(str(template_path))
    if template is None:
        return None, None
    if template.shape[0] > screen.shape[0] or template.shape[1] > screen.shape[1]:
        return None, None
    res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    minv, maxv, minloc, maxloc = cv2.minMaxLoc(res)
    h, w = template.shape[:2]
    center = (maxloc[0] + w // 2, maxloc[1] + h // 2)
    return maxv, center


def verify_color(screen, template_path, region, hue_threshold=12, sat_ratio_range=(0.7, 1.4)):
    """Verify if region matches template color characteristics"""
    template = cv2.imread(str(template_path), cv2.IMREAD_UNCHANGED)
    if template is None:
        return True, {}
    
    # Extract template color info
    if template.ndim == 3 and template.shape[2] == 4:
        alpha = template[:, :, 3]
        tpl_mask = (alpha > 10).astype('uint8')
        tpl_bgr = template[:, :, :3]
    else:
        tpl_mask = None
        tpl_bgr = template
    
    tpl_hsv = cv2.cvtColor(tpl_bgr, cv2.COLOR_BGR2HSV)
    
    # Compute dominant hue (18 bins -> 10 degree bins)
    hist = cv2.calcHist([tpl_hsv], [0], tpl_mask, [18], [0, 180])
    dominant_idx = int(np.argmax(hist))
    dominant_hue = (dominant_idx + 0.5) * (180.0 / 18.0)
    
    # Median saturation
    tpl_sat = tpl_hsv[:, :, 1]
    if tpl_mask is not None:
        sat_vals = tpl_sat[tpl_mask.astype(bool)]
    else:
        sat_vals = tpl_sat.flatten()
    mean_s = float(np.median(sat_vals)) if sat_vals.size > 0 else 0.0
    
    # Skip color check if template is not saturated enough
    if mean_s <= 35:
        return True, {'skip': 'low_saturation', 'tpl_sat': mean_s}
    
    # Check region color
    reg_hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    reg_hist = cv2.calcHist([reg_hsv], [0], None, [18], [0, 180])
    reg_idx = int(np.argmax(reg_hist))
    reg_hue = (reg_idx + 0.5) * (180.0 / 18.0)
    reg_sat = float(np.median(reg_hsv[:, :, 1].flatten()))
    
    # Circular hue difference
    hue_diff = abs(dominant_hue - reg_hue)
    hue_diff = min(hue_diff, 180 - hue_diff)
    
    sat_ratio = (reg_sat + 1.0) / (mean_s + 1.0)
    
    info = {
        'tpl_hue': round(dominant_hue, 2),
        'tpl_sat': round(mean_s, 2),
        'reg_hue': round(reg_hue, 2),
        'reg_sat': round(reg_sat, 2),
        'hue_diff': round(hue_diff, 2),
        'sat_ratio': round(sat_ratio, 2)
    }
    
    passed = hue_diff <= hue_threshold and sat_ratio_range[0] <= sat_ratio <= sat_ratio_range[1]
    return passed, info


def new_match(screen, template_path):
    template = cv2.imread(str(template_path), cv2.IMREAD_UNCHANGED)
    if template is None:
        return None, None, None, {}
    if template.ndim == 3 and template.shape[2] == 4:
        template_rgb = template[:, :, :3]
    else:
        template_rgb = template
    th, tw = template_rgb.shape[:2]
    if th > screen.shape[0] or tw > screen.shape[1]:
        return None, None, None, {}

    gray_screen = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
    gray_template = cv2.cvtColor(template_rgb, cv2.COLOR_BGR2GRAY)
    gray_template = cv2.equalizeHist(gray_template)
    res_gray = cv2.matchTemplate(gray_screen, gray_template, cv2.TM_CCOEFF_NORMED)
    min_g, max_g, min_loc_g, max_loc_g = cv2.minMaxLoc(res_gray)

    edges_screen = cv2.Canny(gray_screen, 50, 150)
    edges_template = cv2.Canny(gray_template, 50, 150)
    res_edge = cv2.matchTemplate(edges_screen, edges_template, cv2.TM_CCOEFF_NORMED)
    min_e, max_e, min_loc_e, max_loc_e = cv2.minMaxLoc(res_edge)

    # Choose best match
    if max_g >= max_e:
        best_score, best_loc, best_method = max_g, max_loc_g, 'gray'
    else:
        best_score, best_loc, best_method = max_e, max_loc_e, 'edge'
    
    # Extract matched region for color verification
    x0 = int(max(best_loc[0], 0))
    y0 = int(max(best_loc[1], 0))
    x1 = int(min(best_loc[0] + tw, screen.shape[1]))
    y1 = int(min(best_loc[1] + th, screen.shape[0]))
    region = screen[y0:y1, x0:x1]
    
    if region.size == 0 or region.shape[0] == 0 or region.shape[1] == 0:
        return None, None, None, {}
    
    # Verify color match
    color_ok, color_info = verify_color(screen, template_path, region)
    
    if not color_ok:
        return best_score, (best_loc[0] + tw//2, best_loc[1] + th//2), f'{best_method}+colorReject', color_info
    
    return best_score, (best_loc[0] + tw//2, best_loc[1] + th//2), best_method, color_info


def draw_and_save(screen, center, template_path, out_path, label):
    out = screen.copy()
    template = cv2.imread(str(template_path), cv2.IMREAD_UNCHANGED)
    if template is None:
        return
    h, w = template.shape[:2]
    if center:
        cx, cy = center
        tl = (int(cx - w//2), int(cy - h//2))
        br = (int(cx + w//2), int(cy + h//2))
        cv2.rectangle(out, tl, br, (0,255,0), 2)
        cv2.putText(out, label, (tl[0], max(tl[1]-10,10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)
    cv2.imwrite(str(out_path), out)


summary_lines = ["screenshot,template,old_score,old_center,new_score,new_center,new_method,color_info"]

screens = list(SCREENSHOTS_DIR.glob('*.png'))
if not screens:
    print("No screenshots found in assets/screenshots/")

for s in screens:
    screen = cv2.imread(str(s))
    for t in TEMPLATES:
        old_score, old_center = old_match(screen, t)
        new_score, new_center, new_method, color_info = new_match(screen, t)

        # Save debug images
        base = f"{s.stem}__{t.stem}"
        out_old = DEBUG_DIR / f"{base}_old.png"
        out_new = DEBUG_DIR / f"{base}_new.png"
        draw_and_save(screen, old_center, t, out_old, f"old:{old_score:.3f}" if old_score is not None else "old:None")
        if new_score is not None:
            label = f"new:{new_score:.3f}/{new_method}"
            if color_info:
                label += f" [hue_d={color_info.get('hue_diff','?')} sat_r={color_info.get('sat_ratio','?')}]"
            draw_and_save(screen, new_center, t, out_new, label)
        else:
            draw_and_save(screen, None, t, out_new, "new:None")
        
        # Log to summary
        color_str = str(color_info) if color_info else ""
        new_score_str = f"{new_score:.3f}" if new_score is not None else "None"
        old_score_str = f"{old_score:.3f}" if old_score is not None else "None"
        summary_lines.append(f"{s.name},{t.name},{old_score_str},{old_center},{new_score_str},{new_center},{new_method},{color_str}")

# write summary
with open(DEBUG_DIR / 'summary.csv', 'w', encoding='utf-8') as f:
    f.write('\n'.join(summary_lines))

print("A/B test complete. Results in debug/ab_tests/")
