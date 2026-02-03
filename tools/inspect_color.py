import cv2
import numpy as np
import sys
from pathlib import Path

if len(sys.argv) < 5:
    print("Usage: python tools/inspect_color.py <template> <screenshot> <center_x> <center_y>")
    sys.exit(2)

tpl_path = Path(sys.argv[1])
shot_path = Path(sys.argv[2])
cx = int(sys.argv[3])
cy = int(sys.argv[4])

tpl = cv2.imread(str(tpl_path), cv2.IMREAD_UNCHANGED)
if tpl is None:
    print("Cannot read template", tpl_path)
    sys.exit(1)

if tpl.ndim == 3 and tpl.shape[2] == 4:
    alpha = tpl[:, :, 3]
    mask = (alpha > 10).astype('uint8')
    tpl_bgr = tpl[:, :, :3]
else:
    tpl_bgr = tpl if tpl.ndim==3 else cv2.cvtColor(tpl, cv2.COLOR_GRAY2BGR)
    mask = None

# template HSV
tpl_hsv = cv2.cvtColor(tpl_bgr, cv2.COLOR_BGR2HSV)
if mask is not None:
    hist = cv2.calcHist([tpl_hsv], [0], mask, [18], [0,180])
    sat_vals = tpl_hsv[:,:,1][mask.astype(bool)]
else:
    hist = cv2.calcHist([tpl_hsv], [0], None, [18], [0,180])
    sat_vals = tpl_hsv[:,:,1].flatten()

dom_idx = int(np.argmax(hist))
dom_hue = (dom_idx + 0.5) * (180.0/18.0)
med_sat = float(np.median(sat_vals)) if sat_vals.size>0 else 0.0
print(f"TEMPLATE {tpl_path.name}: dominant_hue={dom_hue:.2f}, median_sat={med_sat:.2f}, size={tpl_bgr.shape[:2]}")

# load screenshot and extract region
shot = cv2.imread(str(shot_path))
if shot is None:
    print("Cannot read screenshot", shot_path)
    sys.exit(1)

h, w = tpl_bgr.shape[:2]
x0 = max(0, cx - w//2)
y0 = max(0, cy - h//2)
x1 = min(shot.shape[1], x0 + w)
y1 = min(shot.shape[0], y0 + h)
region = shot[y0:y1, x0:x1]
if region.size == 0:
    print("Region empty")
    sys.exit(1)

reg_hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
reg_hist = cv2.calcHist([reg_hsv], [0], None, [18], [0,180])
reg_idx = int(np.argmax(reg_hist))
reg_hue = (reg_idx + 0.5) * (180.0/18.0)
reg_med_sat = float(np.median(reg_hsv[:,:,1].flatten()))
print(f"REGION at ({cx},{cy}) size={region.shape[:2]}: dominant_hue={reg_hue:.2f}, median_sat={reg_med_sat:.2f}")

# print simple checks
hue_diff = abs(dom_hue - reg_hue)
hue_diff = min(hue_diff, 180 - hue_diff)
sat_ratio = (reg_med_sat + 1.0) / (med_sat + 1.0)
print(f"hue_diff={hue_diff:.2f}, sat_ratio={sat_ratio:.2f}")

# save the region for inspection
out = Path('debug') / 'color_check' / f"inspect_{tpl_path.stem}_{cx}_{cy}.png"
out.parent.mkdir(parents=True, exist_ok=True)
cv2.imwrite(str(out), region)
print(f"Wrote region to {out}")
