# DEVICE_SERIAL sẽ được chọn từ GUI mỗi khi chạy
# Không có giá trị mặc định - người dùng phải chọn thiết bị
DEVICE_SERIAL = None  # Sẽ được set khi chọn thiết bị trong GUI
GARDEN_REGION = (100, 380, 880, 1100)
REGION_PRESETS = {
    "Toàn màn": None,
    "Cây và gieo": [108, 435, 578, 362],
    "Máy sản xuất": [110, 211, 510, 560],
    "Mây": [630,571,51,225],
    "Quầy hàng": [12, 216, 682, 374]
}
REGION_FROM_CROP = "Vung crop hien tai"
SIZE = 800
SWIPE_DURATION = 1000  # Tốc độ kéo (ms)
PLANTS = [
    {
        "name": "hong",
        "ripe": "assets/items/cay/ripe/hong.png",
        "seed": "assets/items/cay/seed/hong.png",
        "priority": 1  # Ưu tiên cao
    },
    {
        "name": "tao",
        "ripe": "assets/items/cay/ripe/tao.png",
        "seed": "assets/items/cay/seed/tao.png",
        "priority": 2
    },
    {
        "name": "bong",
        "ripe": "assets/items/cay/ripe/bong.png",
        "seed": "assets/items/cay/seed/bong.png",
        "priority": 3
    },
    {
        "name": "tuyet",
        "ripe": "assets/items/cay/ripe/tuyet.png",
        "seed": "assets/items/cay/seed/tuyet.png",
        "priority": 3
    }
    # Thêm cây mới chỉ cần copy 1 dòng
]
# Map Kho
WAREHOUSE_ITEM_KSK = [
    {
        "code": "KSK_KEM",
        "name": "Kem",
        "path": "assets/items/vpsk_kem.png", #đường dẫn kho khi chưa chọn
        "path_warehouse_not_select": "assets/items/kho_event_0.png", #đường dẫn kho khi chưa chọn
        "path_warehouse_select": "assets/items/kho_event.png" #đường dẫn kho khi đã chọn
    },
    {
        "code": "KSK_KINH",
        "name": "Kính",
        "path": "assets/items/vpsk_kinh.png", #đường dẫn kho khi chưa chọn
        "path_warehouse_not_select": "assets/items/kho_event_0.png", #đường dẫn kho khi chưa chọn
        "path_warehouse_select": "assets/items/kho_event.png" #đường dẫn kho khi đã chọn
    },
    {
        "code": "KSK_DUA",
        "name": "Dừa",
        "path": "assets/items/vpsk_dua.png", #đường dẫn kho khi chưa chọn
        "path_warehouse_not_select": "assets/items/kho_event_0.png", #đường dẫn kho khi chưa chọn
        "path_warehouse_select": "assets/items/kho_event.png" #đường dẫn kho khi đã chọn
    },
    {
        "code": "KSK_BO",
        "name": "Bò",
        "path": "assets/items/vpsk_bo.png", #đường dẫn kho khi chưa chọn
        "path_warehouse_not_select": "assets/items/kho_event_0.png", #đường dẫn kho khi chưa chọn
        "path_warehouse_select": "assets/items/kho_event.png" #đường dẫn kho khi đã chọn
    },
    {
        "code": "KSK_CUU",
        "name": "Cừu",
        "path": "assets/items/vpsk_cuu.png", #đường dẫn kho khi chưa chọn
        "path_warehouse_not_select": "assets/items/kho_event_0.png", #đường dẫn kho khi chưa chọn
        "path_warehouse_select": "assets/items/kho_event.png" #đường dẫn kho khi đã chọn
    },
    {
        "code": "KSK_GA",
        "name": "Gà",
        "path": "assets/items/vpsk_ga.png", #đường dẫn kho khi chưa chọn
        "path_warehouse_not_select": "assets/items/kho_event_0.png", #đường dẫn kho khi chưa chọn
        "path_warehouse_select": "assets/items/kho_event.png" #đường dẫn kho khi đã chọn
    },
    {
        "code": "KSK_HEO",
        "name": "Heo",
        "path": "assets/items/vpsk_heo.png", #đường dẫn kho khi chưa chọn
        "path_warehouse_not_select": "assets/items/kho_event_0.png", #đường dẫn kho khi chưa chọn
        "path_warehouse_select": "assets/items/kho_event.png" #đường dẫn kho khi đã chọn
    }
]

CONFIG_TEMP_TC = [
    {
        "id" : 1,  # thu tu chay
        "row": 1, # hàng thứ mấy
        "type": "TC",
        "indexs": ["1.1", "1.2", "1.3", "1.4", "1.5", "1.6",
                   "2.1", "2.2", "2.3", "2.4", "2.5", "2.6",
                   "3.1", "3.2", "3.3", "3.4", "3.5", "3.6"],  # các giá trị ô sẽ đặt cây
        "path_row": "assets/items/num/1.png", # Hình ảnh để tìm đến mây
        "path_item": "assets/items/cay_tao.png", # Hình ảnh để trồng cây
        "path_item_default": "assets/items/cay_hong.png" # Hình ảnh mặc định để trồng cây nếu không tìm thấy path_item
    },
    {
        "id" : 1,
        "row": 4,
        "type": "TC",
        "indexs": ["2.1", "2.2", "2.3", "2.4", "2.5", "2.6"],
        "path_row": "assets/items/num/4.png",
        "path_item": "assets/items/cay_bong.png",
        "path_item_default": "assets/items/cay_hong.png"
    },
    {
        "id" : 1,
        "row": 5,
        "type": "TC",
        "indexs": ["2.1", "2.2", "2.3", "2.4", "2.5", "2.6",
                   "3.1", "3.2", "3.3", "3.4", "3.5", "3.6",
                   "4.1", "4.2", "4.3", "4.4"],
        "path_row": "assets/items/num/5.png",
        "path_item": "assets/items/cay_tuyet.png",
        "path_item_default": "assets/items/cay_hong.png"
    },
    {
        "id" : 1,
        "row": 8,
        "type": "TC",
        "path_row": "assets/items/num/8.png",
        "indexs": ["2.1", "2.2", "2.3", "2.4", "2.5", "2.6",
                   "3.1", "3.2", "3.3", "3.4", "3.5", "3.6"],
        "path_item": "assets/items/cay_hong.png",
        "path_item_default": "assets/items/cay_hong.png"
    },

    {
        "id" : 1,  # thu tu chay
        "row": 1,
        "type": "TC",
        "indexs": ["1.1", "1.2", "1.3", "1.4", "1.5", "1.6",
                   "2.1", "2.2", "2.3", "2.4", "2.5", "2.6",
                   "3.1", "3.2", "3.3", "3.4", "3.5", "3.6"],
        "path_row": "assets/items/num/1.png",
        "path_item": "assets/items/cay_tao.png",
        "path_item_default": "assets/items/cay_hong.png"
    },
    {
        "id" : 1,
        "row": 4,
        "type": "TC",
        "indexs": ["2.1", "2.2", "2.3", "2.4", "2.5", "2.6"],
        "path_row": "assets/items/num/4.png",
        "path_item": "assets/items/cay_bong.png",
        "path_item_default": "assets/items/cay_hong.png"
    },
    {
        "id" : 1,
        "row": 5,
        "type": "TC",
        "indexs": ["2.1", "2.2", "2.3", "2.4", "2.5", "2.6",
                   "3.1", "3.2", "3.3", "3.4", "3.5", "3.6",
                   "4.1", "4.2", "4.3", "4.4"],
        "path_row": "assets/items/num/5.png",
        "path_item": "assets/items/cay_tuyet.png",
        "path_item_default": "assets/items/cay_hong.png"
    },
    {
        "id" : 1,
        "row": 8,
        "type": "TC",
        "path_row": "assets/items/num/8.png",
        "indexs": ["2.1", "2.2", "2.3", "2.4", "2.5", "2.6",
                   "3.1", "3.2", "3.3", "3.4", "3.5", "3.6"],
        "path_item": "assets/items/cay_hong.png",
        "path_item_default": "assets/items/cay_hong.png"
    },

    {
        "id" : 2,
        "row": 1,
        "type": "MAY",
        "path_row": "assets/items/num/1.png",
        "data": [
            {
                "path_item": "assets/items/hong_say.png",
                "total":  8
            }
        ]
    },
    {
        "id" : 2,
        "row": 2,
        "type": "MAY",
        "path_row": "assets/items/num/2.png",
        "data": [
            {
                "path_item": "assets/items/nuoc_tao.png",
                "total":  4
            },
            {
                "path_item": "assets/items/nuoc_tuyet.png",
                "total":  4
            }
        ]
    },
    {
        "id" : 2,
        "row": 3,
        "type": "MAY",
        "path_row": "assets/items/num/3.png",
        "data": [
            {
                "path_item": "assets/items/vai_vang.png",
                "total":  4
            }
        ]
    },
    {
        "id" : 2,
        "row": 5,
        "type": "MAY",
        "path_row": "assets/items/num/5.png",
        "data": [
            {
                "path_item": "assets/items/tinh_dau_tao.png",
                "total":  4
            }
        ]
    }
    ,
    {
        "id" : 2,
        "row": 6,
        "type": "MAY",
        "path_row": "assets/items/num/6.png",
        "data": [
            {
                "path_item": "assets/items/tra_hoa_hong.png",
                "total":  4
            }
        ]
    }

]

CONFIG_LOAI_KHO = [
    {
        "code": "KSK",
        "name": "Kho Su Kien",
        "path_warehouse_not_select": "assets/items/kho_event_0.png",
        "path_warehouse_select": "assets/items/kho_event.png",
        "position": (361, 530)
    },
    {
        "code": "KNS",
        "name": "Kho Nong San",
        "path_warehouse_not_select": "assets/items/kho_nong_san_0.png",
        "path_warehouse_select": "assets/items/kho_nong_san.png",
        "position": (361, 296)
    },
    {
        "code": "KTP",
        "name": "Kho Thanh Pham",
        "path_warehouse_not_select": "assets/items/kho_thanh_pham_0.png",
        "path_warehouse_select": "assets/items/kho_thanh_pham.png",
        "position": (361, 353)
    }
]

CONFIG_BAN_DO = {
    "loai_kho": "KTP", # loại kho: KSK, KNS, KTP
    "so_lan_dat_vp": 4, # số lần đặt vật phẩm vào kho mỗi lần chạy
    "data": "assets/items/kho_tra_hoa_hong.png, assets/items/kho_tinh_dau_tao.png, assets/items/kho_vai_vang.png",
    "xoa_kc": True, # có xóa kho không
    "dat_quang_cao": True, # có đặt quảng cáo không
    # New: lists of templates (thứ tự sẽ được thử từng cái)
    "qc_templates": ["assets/items/cua_hang_qc.png"],
    "xoa_kc_templates": ["assets/items/xoa_vp_kc.png"]
}

INDEX_HANG = {
    # vi_tri : (x,y)
    "1.1": (311,749),
    "1.2": (371,749),
    "1.3": (431,749),
    "1.4": (490,749),
    "1.5": (550,749),
    "1.6": (650,749),

    "2.1": (311,571),
    "2.2": (371,571),
    "2.3": (431,571),
    "2.4": (490,571),
    "2.5": (550,571),
    "2.6": (650,571),

    "3.1": (311,391),
    "3.2": (371,391),
    "3.3": (431,391),
    "3.4": (490,391),
    "3.5": (550,391),
    "3.6": (650,391),

    "4.1": (311,220),
    "4.2": (371,220),
    "4.3": (431,220),
    "4.4": (490,220),
    "4.5": (550,220),
    "4.6": (650,220)
}

INDEX_MAY = {
    "1": (210, 720),
    "2": (210, 550),
    "3": (210, 550),
    "4": (210, 550),
    "5": (210, 550),
    "6": (210, 550),
    "7": (210, 550),
    "8": (210, 550),
    "9": (210, 550),
    "10": (210, 550)
}

INDEX_XUONG_NHA_MAC_DINH = (402, 784)
INDEX_SAN_XUAT_MAC_DINH = (319, 576)
INDEX_THOAT_SAN_XUAT_MAC_DINH = (735, 420)
INDEX_NEXT_SAN_XUAT_MAC_DINH = (514, 511)
INDEX_CUA_HANG_MAC_DINH = (513, 690)
INDEX_SUA_MAY_MAC_DINH = (577, 475)