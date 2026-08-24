"""
Module Recipe Builder - Tự động tính toán chuỗi sản xuất và phân bổ ô trồng cây trong KVTM.
"""

import os
from typing import Dict, List, Tuple, Any

# Danh mục định nghĩa cây trồng nguyên liệu gốc
CROPS = {
    "hong": {"name": "Hoa Hồng", "path": "assets/items/cay_hong.png"},
    "tao": {"name": "Táo", "path": "assets/items/cay_tao.png"},
    "bong": {"name": "Bông", "path": "assets/items/cay_bong.png"},
    "tuyet": {"name": "Tuyết", "path": "assets/items/cay_tuyet.png"},
    "dua": {"name": "Dừa", "path": "assets/items/cay_dua.png"},
    "chanh": {"name": "Chanh", "path": "assets/items/cay_chanh.png"},
    "cuc": {"name": "Hoa Cúc", "path": "assets/items/cay_cuc.png"},
    "lai": {"name": "Hoa Lài", "path": "assets/items/cay_lai.png"},
    "mit": {"name": "Mít", "path": "assets/items/cay_mit.png"},
    "nho": {"name": "Nho", "path": "assets/items/cay_nho.png"},
    "thom": {"name": "Thơm (Dứa)", "path": "assets/items/cay_thom.png"},
    "tra": {"name": "Trà", "path": "assets/items/cay_tra.png"},
    "xoai": {"name": "Xoài", "path": "assets/items/cay_xoai.png"},
    "bi": {"name": "Bí", "path": "assets/items/cay_bi.png"},
    "oai_huong": {"name": "Oải Hương", "path": "assets/items/oai_huong.png"},
    "dua_hau": {"name": "Dưa Hấu", "path": "assets/items/dua_hau.png"}
}

# Danh mục sản phẩm theo máy và công thức
# Mỗi sản phẩm có:
# - name: Tên hiển thị
# - machine_row: Hàng/máy sản xuất (1-10)
# - path_item: File ảnh sản phẩm
# - intermediate: Danh sách các bước máy trung gian cần chế biến trước (nếu có)
# - raw_crops: Số lượng cây trồng thô cần cho 1 đơn vị sản phẩm
RECIPES: Dict[str, Dict[str, Any]] = {
    # --- MÁY 1: BỌ SẤY (Tầng 1) ---
    "hong_say": {
        "name": "Hồng sấy (Máy 1)",
        "machine_row": 1,
        "path_item": "assets/items/hong_say.png",
        "intermediate": [],
        "raw_crops": {"hong": 3}
    },
    "tao_say": {
        "name": "Táo sấy (Máy 1)",
        "machine_row": 1,
        "path_item": "assets/items/tao_say.png",
        "intermediate": [],
        "raw_crops": {"tao": 3}
    },
    "cuc_say": {
        "name": "Cúc sấy (Máy 1)",
        "machine_row": 1,
        "path_item": "assets/items/cuc_say.png",
        "intermediate": [],
        "raw_crops": {"cuc": 3}
    },
    "dua_say": {
        "name": "Dừa sấy (Máy 1)",
        "machine_row": 1,
        "path_item": "assets/items/dua_say.png",
        "intermediate": [],
        "raw_crops": {"dua": 3}
    },
    "oai_huong_say": {
        "name": "Oải hương sấy (Máy 1)",
        "machine_row": 1,
        "path_item": "assets/items/oai_huong_say.png",
        "intermediate": [],
        "raw_crops": {"oai_huong": 3}
    },
    "tra_say": {
        "name": "Trà sấy (Máy 1)",
        "machine_row": 1,
        "path_item": "assets/items/tra_say.png",
        "intermediate": [],
        "raw_crops": {"tra": 3}
    },

    # --- MÁY 2: BỌ NƯỚC ÉP (Tầng 2) ---
    "nuoc_tao": {
        "name": "Nước táo (Máy 2)",
        "machine_row": 2,
        "path_item": "assets/items/nuoc_tao.png",
        "intermediate": [],
        "raw_crops": {"tao": 4}
    },
    "nuoc_tuyet": {
        "name": "Nước tinh khiết (Máy 2)",
        "machine_row": 2,
        "path_item": "assets/items/nuoc_tuyet.png",
        "intermediate": [],
        "raw_crops": {"tuyet": 4}
    },
    "nuoc_chanh": {
        "name": "Nước chanh (Máy 2)",
        "machine_row": 2,
        "path_item": "assets/items/nuoc_chanh.png",
        "intermediate": [],
        "raw_crops": {"chanh": 4}
    },
    "nuoc_dua": {
        "name": "Nước dừa (Máy 2)",
        "machine_row": 2,
        "path_item": "assets/items/nuoc_dua.png",
        "intermediate": [],
        "raw_crops": {"dua": 4}
    },
    "nuoc_dua_hau": {
        "name": "Nước dưa hấu (Máy 2)",
        "machine_row": 2,
        "path_item": "assets/items/nuoc_dua_hau.png",
        "intermediate": [],
        "raw_crops": {"dua_hau": 4}
    },
    "nuoc_mit": {
        "name": "Sinh tố mít (Máy 2)",
        "machine_row": 2,
        "path_item": "assets/items/nuoc_mit.png",
        "intermediate": [],
        "raw_crops": {"mit": 4}
    },

    # --- MÁY 3: BỌ DỆT VẢI (Tầng 3) ---
    "vai_do": {
        "name": "Vải đỏ (Máy 3)",
        "machine_row": 3,
        "path_item": "assets/items/vai_do.png",
        "intermediate": [
            {"machine_row": 1, "path_item": "assets/items/hong_say.png", "mult": 1}
        ],
        "raw_crops": {"bong": 3, "hong": 3}
    },
    "vai_vang": {
        "name": "Vải vàng (Máy 3)",
        "machine_row": 3,
        "path_item": "assets/items/vai_vang.png",
        "intermediate": [
            {"machine_row": 2, "path_item": "assets/items/nuoc_tao.png", "mult": 1}
        ],
        "raw_crops": {"bong": 3, "tao": 4}
    },
    "vai_tim": {
        "name": "Vải tím (Máy 3)",
        "machine_row": 3,
        "path_item": "assets/items/vai_tim.png",
        "intermediate": [
            {"machine_row": 1, "path_item": "assets/items/oai_huong_say.png", "mult": 1}
        ],
        "raw_crops": {"bong": 3, "oai_huong": 3}
    },
    "vai_xanh": {
        "name": "Vải xanh lá (Máy 3)",
        "machine_row": 3,
        "path_item": "assets/items/vai_xanh.png",
        "intermediate": [
            {"machine_row": 2, "path_item": "assets/items/nuoc_chanh.png", "mult": 1}
        ],
        "raw_crops": {"bong": 3, "chanh": 4}
    },

    # --- MÁY 5: BỌ TINH DẦU (Tầng 5) ---
    "tinh_dau_hh": {
        "name": "Tinh dầu hoa hồng (Máy 5)",
        "machine_row": 5,
        "path_item": "assets/items/tinh_dau_hh.png",
        "intermediate": [],
        "raw_crops": {"tuyet": 4, "hong": 5}
    },
    "tinh_dau_tao": {
        "name": "Tinh dầu táo (Máy 5)",
        "machine_row": 5,
        "path_item": "assets/items/tinh_dau_tao.png",
        "intermediate": [],
        "raw_crops": {"tuyet": 4, "tao": 5}
    },
    "tinh_dau_oai": {
        "name": "Tinh dầu oải hương (Máy 5)",
        "machine_row": 5,
        "path_item": "assets/items/tinh_dau_oai.png",
        "intermediate": [],
        "raw_crops": {"tuyet": 4, "oai_huong": 5}
    },
    "tinh_dau_chanh": {
        "name": "Tinh dầu chanh (Máy 5)",
        "machine_row": 5,
        "path_item": "assets/items/tinh_dau_chanh.png",
        "intermediate": [],
        "raw_crops": {"tuyet": 4, "chanh": 5}
    },
    "tinh_dau_dua": {
        "name": "Tinh dầu dừa (Máy 5)",
        "machine_row": 5,
        "path_item": "assets/items/tinh_dau_dua.png",
        "intermediate": [],
        "raw_crops": {"tuyet": 4, "dua": 5}
    },

    # --- MÁY 6: BỌ PHA TRÀ (Tầng 6) ---
    "tra_hoa_hong": {
        "name": "Trà hoa hồng (Máy 6)",
        "machine_row": 6,
        "path_item": "assets/items/tra_hoa_hong.png",
        "intermediate": [
            {"machine_row": 2, "path_item": "assets/items/nuoc_tuyet.png", "mult": 1},
            {"machine_row": 1, "path_item": "assets/items/hong_say.png", "mult": 2}
        ],
        "raw_crops": {"tuyet": 4, "hong": 6}
    },
    "tra_da": {
        "name": "Trà đá (Máy 6)",
        "machine_row": 6,
        "path_item": "assets/items/tra_da.png",
        "intermediate": [
            {"machine_row": 1, "path_item": "assets/items/tra_say.png", "mult": 1}
        ],
        "raw_crops": {"tuyet": 4, "tra": 3}
    },
    "tra_tao": {
        "name": "Trà táo (Máy 6)",
        "machine_row": 6,
        "path_item": "assets/items/tra_tao.png",
        "intermediate": [
            {"machine_row": 2, "path_item": "assets/items/nuoc_tao.png", "mult": 1}
        ],
        "raw_crops": {"tuyet": 4, "tao": 4}
    },
    "tra_chanh": {
        "name": "Trà chanh (Máy 6)",
        "machine_row": 6,
        "path_item": "assets/items/tra_chanh.png",
        "intermediate": [
            {"machine_row": 2, "path_item": "assets/items/nuoc_chanh.png", "mult": 1},
            {"machine_row": 1, "path_item": "assets/items/tra_say.png", "mult": 1}
        ],
        "raw_crops": {"chanh": 4, "tra": 3}
    },
    "tra_cuc": {
        "name": "Trà cúc (Máy 6)",
        "machine_row": 6,
        "path_item": "assets/items/tra_cuc.png",
        "intermediate": [
            {"machine_row": 2, "path_item": "assets/items/nuoc_tuyet.png", "mult": 1},
            {"machine_row": 1, "path_item": "assets/items/cuc_say.png", "mult": 2}
        ],
        "raw_crops": {"tuyet": 4, "cuc": 6}
    },

    # --- MÁY 8: BỌ NƯỚC HOA (Tầng 8) ---
    "nuoc_hoa_tao": {
        "name": "Nước hoa táo (Máy 8)",
        "machine_row": 8,
        "path_item": "assets/items/nuoc_hoa_tao.png",
        "intermediate": [
            {"machine_row": 2, "path_item": "assets/items/nuoc_tuyet.png", "mult": 1},
            {"machine_row": 5, "path_item": "assets/items/tinh_dau_tao.png", "mult": 1}
        ],
        "raw_crops": {"tuyet": 8, "tao": 5}
    },
    "nuoc_hoa_hong": {
        "name": "Nước hoa hồng (Máy 8)",
        "machine_row": 8,
        "path_item": "assets/items/nuoc_hoa_hong.png",
        "intermediate": [
            {"machine_row": 2, "path_item": "assets/items/nuoc_tuyet.png", "mult": 1},
            {"machine_row": 5, "path_item": "assets/items/tinh_dau_hh.png", "mult": 1}
        ],
        "raw_crops": {"tuyet": 8, "hong": 5}
    },
    "nuoc_hoa_oai": {
        "name": "Nước hoa oải hương (Máy 8)",
        "machine_row": 8,
        "path_item": "assets/items/nuoc_hoa_oai.png",
        "intermediate": [
            {"machine_row": 2, "path_item": "assets/items/nuoc_tuyet.png", "mult": 1},
            {"machine_row": 5, "path_item": "assets/items/tinh_dau_oai.png", "mult": 1}
        ],
        "raw_crops": {"tuyet": 8, "oai_huong": 5}
    },
    "nuoc_hoa_chanh": {
        "name": "Nước hoa chanh (Máy 8)",
        "machine_row": 8,
        "path_item": "assets/items/nuoc_hoa_chanh.png",
        "intermediate": [
            {"machine_row": 2, "path_item": "assets/items/nuoc_tuyet.png", "mult": 1},
            {"machine_row": 5, "path_item": "assets/items/tinh_dau_chanh.png", "mult": 1}
        ],
        "raw_crops": {"tuyet": 8, "chanh": 5}
    },

    # --- MÁY 9: BỌ MAY TÚI (Tầng 9) ---
    "tui_hong": {
        "name": "Túi hồng (Máy 9)",
        "machine_row": 9,
        "path_item": "assets/items/tui_hong.png",
        "intermediate": [
            {"machine_row": 1, "path_item": "assets/items/hong_say.png", "mult": 1},
            {"machine_row": 3, "path_item": "assets/items/vai_do.png", "mult": 1},
            {"machine_row": 5, "path_item": "assets/items/tinh_dau_hh.png", "mult": 1}
        ],
        "raw_crops": {"bong": 3, "hong": 8, "tuyet": 4}
    },
    "tui_tao": {
        "name": "Túi táo (Máy 9)",
        "machine_row": 9,
        "path_item": "assets/items/tui_tao.png",
        "intermediate": [
            {"machine_row": 2, "path_item": "assets/items/nuoc_tao.png", "mult": 1},
            {"machine_row": 3, "path_item": "assets/items/vai_vang.png", "mult": 1},
            {"machine_row": 5, "path_item": "assets/items/tinh_dau_tao.png", "mult": 1}
        ],
        "raw_crops": {"bong": 3, "tao": 9, "tuyet": 4}
    },
    "tui_oai": {
        "name": "Túi oải hương (Máy 9)",
        "machine_row": 9,
        "path_item": "assets/items/tui_oai.png",
        "intermediate": [
            {"machine_row": 1, "path_item": "assets/items/oai_huong_say.png", "mult": 1},
            {"machine_row": 3, "path_item": "assets/items/vai_tim.png", "mult": 1},
            {"machine_row": 5, "path_item": "assets/items/tinh_dau_oai.png", "mult": 1}
        ],
        "raw_crops": {"bong": 3, "oai_huong": 8, "tuyet": 4}
    },
    "tui_chanh": {
        "name": "Túi chanh (Máy 9)",
        "machine_row": 9,
        "path_item": "assets/items/tui_chanh.png",
        "intermediate": [
            {"machine_row": 2, "path_item": "assets/items/nuoc_chanh.png", "mult": 1},
            {"machine_row": 3, "path_item": "assets/items/vai_xanh.png", "mult": 1},
            {"machine_row": 5, "path_item": "assets/items/tinh_dau_chanh.png", "mult": 1}
        ],
        "raw_crops": {"bong": 3, "chanh": 9, "tuyet": 4}
    }
}


def get_available_products() -> List[Tuple[str, str]]:
    """Trả về danh sách (key, tên hiển thị) của tất cả sản phẩm có công thức."""
    return [(k, v["name"]) for k, v in RECIPES.items()]


def calculate_requirements(product_key: str, quantity: int = 4) -> Dict[str, Any]:
    """Tính toán toàn bộ nguyên liệu cây trồng và các bước máy trung gian."""
    if product_key not in RECIPES:
        raise ValueError(f"Không tìm thấy công thức cho: {product_key}")

    recipe = RECIPES[product_key]
    raw_crops = {}
    for crop_key, crop_count in recipe["raw_crops"].items():
        raw_crops[crop_key] = crop_count * quantity

    # Các máy trung gian
    intermediates = []
    for step in recipe.get("intermediate", []):
        intermediates.append({
            "machine_row": step["machine_row"],
            "path_row": f"assets/items/num/{step['machine_row']}.png",
            "path_item": step["path_item"],
            "total": step["mult"] * quantity
        })

    # Máy đích cuối cùng
    final_machine = {
        "machine_row": recipe["machine_row"],
        "path_row": f"assets/items/num/{recipe['machine_row']}.png",
        "path_item": recipe["path_item"],
        "total": quantity
    }

    return {
        "product_name": recipe["name"],
        "quantity": quantity,
        "raw_crops": raw_crops,
        "intermediate_machines": intermediates,
        "final_machine": final_machine
    }


def generate_plant_tasks(raw_crops: Dict[str, int]) -> List[Dict[str, Any]]:
    """
    Phân bổ các cây cần trồng vào các cụm mây:
    - Cụm Row 1: Tầng 1..4 (Tối đa 24 ô: 1.1-1.6, 2.1-2.6, 3.1-3.6, 4.1-4.6)
    - Cụm Row 5: Tầng 5..7 (Tối đa 18 ô: 2.1-2.6, 3.1-3.6, 4.1-4.6)
    - Cụm Row 8: Tầng 8..10 (Tối đa 18 ô: 2.1-2.6, 3.1-3.6, 4.1-4.6)
    """
    # Khởi tạo danh sách các slot của từng cụm
    CLUSTERS = [
        {
            "row": 1,
            "path_row": "assets/items/num/1.png",
            "slots": [f"{r}.{c}" for r in range(1, 5) for c in range(1, 7)]  # 24 slots
        },
        {
            "row": 5,
            "path_row": "assets/items/num/5.png",
            "slots": [f"{r}.{c}" for r in range(2, 5) for c in range(1, 7)]  # 18 slots
        },
        {
            "row": 8,
            "path_row": "assets/items/num/8.png",
            "slots": [f"{r}.{c}" for r in range(2, 5) for c in range(1, 7)]  # 18 slots
        }
    ]

    tasks = []
    cluster_idx = 0
    slot_idx = 0

    for crop_key, needed_count in raw_crops.items():
        if needed_count <= 0:
            continue

        crop_info = CROPS.get(crop_key, {"name": crop_key, "path": f"assets/items/cay_{crop_key}.png"})
        path_item = crop_info["path"]
        remaining = needed_count

        while remaining > 0 and cluster_idx < len(CLUSTERS):
            curr_cluster = CLUSTERS[cluster_idx]
            available_slots = curr_cluster["slots"][slot_idx:]

            take_count = min(remaining, len(available_slots))
            allocated_slots = available_slots[:take_count]

            tasks.append({
                "id": 1,
                "row": curr_cluster["row"],
                "type": "TC",
                "path_row": curr_cluster["path_row"],
                "path_item": path_item,
                "path_item_default": "assets/items/cay_hong.png",
                "indexs": allocated_slots
            })

            remaining -= take_count
            slot_idx += take_count

            if slot_idx >= len(curr_cluster["slots"]):
                cluster_idx += 1
                slot_idx = 0

    return tasks


def generate_full_config(product_key: str, quantity: int = 4) -> List[Dict[str, Any]]:
    """
    Tạo toàn bộ danh sách Task (Trồng cây + Chế biến máy) cho 1 sản phẩm.
    """
    return generate_multi_product_config([{"key": product_key, "quantity": quantity}])


def calculate_multi_requirements(items_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Tính toán tổng hợp nguyên liệu cho danh sách nhiều sản phẩm cùng lúc.
    items_list: List of dict, e.g. [{"key": "nuoc_hoa_tao", "quantity": 4}, {"key": "vai_vang", "quantity": 4}]
    """
    total_raw_crops: Dict[str, int] = {}
    machine_dict: Dict[Tuple[int, str], int] = {}  # (machine_row, path_item) -> total quantity

    for item in items_list:
        p_key = item["key"]
        qty = item["quantity"]
        if p_key not in RECIPES or qty <= 0:
            continue
        reqs = calculate_requirements(p_key, qty)
        for crop, count in reqs["raw_crops"].items():
            total_raw_crops[crop] = total_raw_crops.get(crop, 0) + count

        all_m = reqs["intermediate_machines"] + [reqs["final_machine"]]
        for m in all_m:
            m_key = (m["machine_row"], m["path_item"])
            machine_dict[m_key] = machine_dict.get(m_key, 0) + m["total"]

    # Sort machine steps by row ascending
    sorted_machines = sorted(machine_dict.items(), key=lambda x: x[0][0])
    combined_machines = []
    for (m_row, p_item), total_q in sorted_machines:
        combined_machines.append({
            "machine_row": m_row,
            "path_row": f"assets/items/num/{m_row}.png",
            "path_item": p_item,
            "total": total_q
        })

    return {
        "items": items_list,
        "raw_crops": total_raw_crops,
        "machines": combined_machines
    }


def generate_multi_product_config(items_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Tạo toàn bộ danh sách Task (Trồng cây + Chạy máy) cho nhiều sản phẩm kết hợp.
    """
    multi_reqs = calculate_multi_requirements(items_list)
    tc_tasks = generate_plant_tasks(multi_reqs["raw_crops"])

    # Gom các máy trên cùng hàng (row) lại thành 1 task MAY với mảng data
    may_by_row: Dict[int, List[Dict[str, Any]]] = {}
    for m in multi_reqs["machines"]:
        r = m["machine_row"]
        if r not in may_by_row:
            may_by_row[r] = []
        may_by_row[r].append({
            "path_item": m["path_item"],
            "total": m["total"]
        })

    may_tasks = []
    for r in sorted(may_by_row.keys()):
        may_tasks.append({
            "id": 2,
            "row": r,
            "type": "MAY",
            "path_row": f"assets/items/num/{r}.png",
            "data": may_by_row[r]
        })

    return tc_tasks + may_tasks

