DEVICE_SERIAL = "emulator-5554"
GARDEN_REGION = (100, 380, 880, 1100)

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
        "row": 1,
        "type": "TC",
        "indexs": ["1.1", "1.2", "1.3", "1.4", "1.5", "1.6",
                   "2.1", "2.2", "2.3", "2.4", "2.5", "2.6",
                   "3.1", "3.2", "3.3", "3.4", "3.5", "3.6"],
        "path_row": "assets/items/num/1.png",
        "path_item": "assets/items/cay_tao.png"
    },
    {
        "id" : 1,
        "row": 4,
        "type": "TC",
        "indexs": ["2.1", "2.2", "2.3", "2.4", "2.5", "2.6"],
        "path_row": "assets/items/num/4.png",
        "path_item": "assets/items/cay_bong.png"
    },
    {
        "id" : 1,
        "row": 5,
        "type": "TC",
        "indexs": ["2.1", "2.2", "2.3", "2.4", "2.5", "2.6",
                   "3.1", "3.2", "3.3", "3.4", "3.5", "3.6",
                   "4.1", "4.2", "4.3", "4.4"],
        "path_row": "assets/items/num/5.png",
        "path_item": "assets/items/cay_tuyet.png"
    },
    {
        "id" : 1,
        "row": 8,
        "type": "TC",
        "path_row": "assets/items/num/8.png",
        "indexs": ["2.1", "2.2", "2.3", "2.4", "2.5", "2.6",
                   "3.1", "3.2", "3.3", "3.4", "3.5", "3.6"],
        "path_item": "assets/items/cay_hong.png"
    },

    {
        "id" : 1,  # thu tu chay
        "row": 1,
        "type": "TC",
        "indexs": ["1.1", "1.2", "1.3", "1.4", "1.5", "1.6",
                   "2.1", "2.2", "2.3", "2.4", "2.5", "2.6",
                   "3.1", "3.2", "3.3", "3.4", "3.5", "3.6"],
        "path_row": "assets/items/num/1.png",
        "path_item": "assets/items/cay_tao.png"
    },
    {
        "id" : 1,
        "row": 4,
        "type": "TC",
        "indexs": ["2.1", "2.2", "2.3", "2.4", "2.5", "2.6"],
        "path_row": "assets/items/num/4.png",
        "path_item": "assets/items/cay_bong.png"
    },
    {
        "id" : 1,
        "row": 5,
        "type": "TC",
        "indexs": ["2.1", "2.2", "2.3", "2.4", "2.5", "2.6",
                   "3.1", "3.2", "3.3", "3.4", "3.5", "3.6",
                   "4.1", "4.2", "4.3", "4.4"],
        "path_row": "assets/items/num/5.png",
        "path_item": "assets/items/cay_tuyet.png"
    },
    {
        "id" : 1,
        "row": 8,
        "type": "TC",
        "path_row": "assets/items/num/8.png",
        "indexs": ["2.1", "2.2", "2.3", "2.4", "2.5", "2.6",
                   "3.1", "3.2", "3.3", "3.4", "3.5", "3.6"],
        "path_item": "assets/items/cay_hong.png"
    }
    # ,

    # {
    #     "id" : 2,
    #     "row": 1,
    #     "type": "MAY",
    #     "path_row": "assets/items/num/1.png",
    #     "data": [
    #         {
    #             "path_item": "assets/items/hong_say.png",
    #             "total":  8
    #         }
    #     ]
    # },
    # {
    #     "id" : 2,
    #     "row": 2,
    #     "type": "MAY",
    #     "path_row": "assets/items/num/2.png",
    #     "data": [
    #         {
    #             "path_item": "assets/items/nuoc_tao.png",
    #             "total":  4
    #         },
    #         {
    #             "path_item": "assets/items/nuoc_tuyet.png",
    #             "total":  4
    #         }
    #     ]
    # },
    # {
    #     "id" : 2,
    #     "row": 2,
    #     "type": "MAY",
    #     "path_row": "assets/items/num/2.png",
    #     "data": [
    #         {
    #             "path_item": "assets/items/nuoc_tao.png",
    #             "total":  4
    #         },
    #         {
    #             "path_item": "assets/items/nuoc_tuyet.png",
    #             "total":  4
    #         }
    #     ]
    # },
    # {
    #     "id" : 2,
    #     "row": 3,
    #     "type": "MAY",
    #     "path_row": "assets/items/num/3.png",
    #     "data": [
    #         {
    #             "path_item": "assets/items/vai_vang.png",
    #             "total":  4
    #         }
    #     ]
    # },
    # {
    #     "id" : 2,
    #     "row": 5,
    #     "type": "MAY",
    #     "path_row": "assets/items/num/5.png",
    #     "data": [
    #         {
    #             "path_item": "assets/items/tinh_dau_tao.png",
    #             "total":  4
    #         }
    #     ]
    # },
    # {
    #     "id" : 2,
    #     "row": 6,
    #     "type": "MAY",
    #     "path_row": "assets/items/num/6.png",
    #     "data": [
    #         {
    #             "path_item": "assets/items/nuoc_hoa_hong.png",
    #             "total":  4
    #         }
    #     ]
    # }

]


INDEX_HANG = {
    # vi_tri : (x,y)
    "1.1": (390,940),
    "1.2": (485,940),
    "1.3": (560,940),
    "1.4": (635,940),
    "1.5": (710,940),
    "1.6": (785,940),

    "2.1": (390,715),
    "2.2": (485,715),
    "2.3": (560,715),
    "2.4": (635,715),
    "2.5": (710,715),
    "2.6": (785,715),

    "3.1": (390,495),
    "3.2": (485,495),
    "3.3": (560,495),
    "3.4": (635,495),
    "3.5": (710,495),
    "3.6": (785,495),

    "4.1": (390,275),
    "4.2": (485,275),
    "4.3": (560,275),
    "4.4": (635,275),
    "4.5": (710,275),
    "4.6": (785,275)
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