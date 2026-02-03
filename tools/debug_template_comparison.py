"""
So sánh 2 template để hiểu tại sao matching score cao
"""
import cv2
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Template 1: hong_say (đỏ)
template1_path = ROOT / 'assets' / 'items' / 'hong_say.png'

# Template 2: oai_huong_say (vàng) - nếu có
template2_options = [
    ROOT / 'assets' / 'items' / 'oai_huong_say.png',
    ROOT / 'assets' / 'items' / 'oai_say.png',
    ROOT / 'assets' / 'items' / 'dua_say.png',
]

print("=" * 80)
print("TEMPLATE COMPARISON: hong_say vs others")
print("=" * 80)

tpl1 = cv2.imread(str(template1_path))
print(f"\n📌 Template 1: {template1_path.name}")
print(f"   Size: {tpl1.shape}")
print(f"   Mean BGR: {tpl1.mean(axis=(0,1))}")

# Grayscale analysis
gray1 = cv2.cvtColor(tpl1, cv2.COLOR_BGR2GRAY)
hist1 = cv2.calcHist([gray1], [0], None, [256], [0, 256])

print(f"   Grayscale histogram (peaks):")
top_5_indices = np.argsort(hist1.flatten())[-5:][::-1]
for idx in top_5_indices:
    print(f"      Value {idx}: {hist1[idx, 0]:.0f}")

# Edge detection
edges1 = cv2.Canny(gray1, 50, 150)
edge_count1 = np.count_nonzero(edges1)
print(f"   Edge count (Canny): {edge_count1}")

# HSV analysis
hsv1 = cv2.cvtColor(tpl1, cv2.COLOR_BGR2HSV)
hue_hist = cv2.calcHist([hsv1], [0], None, [18], [0, 180])
dom_idx = int(np.argmax(hue_hist))
dom_hue = (dom_idx + 0.5) * (180.0 / 18.0)
sat = np.median(hsv1[:, :, 1])
print(f"   HSV: Dominant Hue={dom_hue:.1f}°, Median Saturation={sat:.0f}")

print("\n" + "-" * 80)

for template2_path in template2_options:
    if not template2_path.exists():
        continue
    
    tpl2 = cv2.imread(str(template2_path))
    print(f"\n📌 Template 2: {template2_path.name}")
    print(f"   Size: {tpl2.shape}")
    print(f"   Mean BGR: {tpl2.mean(axis=(0,1))}")
    
    # Grayscale comparison
    gray2 = cv2.cvtColor(tpl2, cv2.COLOR_BGR2GRAY)
    
    # ===== MATCHING TESTS =====
    print("\n   🔍 MATCHING TESTS:")
    
    # 1. Grayscale matching
    if gray1.shape == gray2.shape:
        score_gray = cv2.matchTemplate(gray1, gray2, cv2.TM_CCOEFF_NORMED)
        if score_gray.size > 0:
            match_gray = score_gray.max()
            print(f"      Grayscale match (same size): {match_gray:.3f}")
    else:
        print(f"      Grayscale match: Different sizes ({gray1.shape} vs {gray2.shape})")
    
    # 2. Edge matching
    edges2 = cv2.Canny(gray2, 50, 150)
    if edges1.shape == edges2.shape:
        score_edge = cv2.matchTemplate(edges1, edges2, cv2.TM_CCOEFF_NORMED)
        if score_edge.size > 0:
            match_edge = score_edge.max()
            print(f"      Edge match (same size): {match_edge:.3f}")
    else:
        print(f"      Edge match: Different sizes")
    
    # Edge statistics
    edge_count2 = np.count_nonzero(edges2)
    print(f"      Edge count (Canny): {edge_count2}")
    
    # HSV analysis
    hsv2 = cv2.cvtColor(tpl2, cv2.COLOR_BGR2HSV)
    hue_hist2 = cv2.calcHist([hsv2], [0], None, [18], [0, 180])
    dom_idx2 = int(np.argmax(hue_hist2))
    dom_hue2 = (dom_idx2 + 0.5) * (180.0 / 18.0)
    sat2 = np.median(hsv2[:, :, 1])
    print(f"      HSV: Dominant Hue={dom_hue2:.1f}°, Median Saturation={sat2:.0f}")
    
    # Hue difference
    hue_diff = abs(dom_hue - dom_hue2)
    hue_diff = min(hue_diff, 180 - hue_diff)
    sat_ratio = (sat2 + 1.0) / (sat + 1.0)
    print(f"      Color diff: hue_diff={hue_diff:.1f}°, sat_ratio={sat_ratio:.2f}")
    
    print(f"\n   ✅ Match: {'PASS' if hue_diff <= 12 and 0.7 <= sat_ratio <= 1.4 else 'FAIL'}")
    print("-" * 80)

print("\n💡 Kết luận:")
print("   - Nếu 2 template có size khác nhau → không thể so sánh trực tiếp")
print("   - Grayscale matching cao = hình dáng/cạnh giống nhau, không phân biệt màu")
print("   - Color check (hue_diff) sẽ lọc các false positive")
