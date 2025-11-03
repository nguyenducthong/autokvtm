DEVICE_SERIAL = "emulator-5554"
GARDEN_REGION = (100, 380, 880, 1100)
NUM_ROWS = 2
ROW_HEIGHT = 300  # Khoảng cách giữa 2 hàng
ROW_START_POINTS = [
    (400, 1660),  # Hàng 1 - Vị trí 1.1 (trái)
    (400, 760),  # Hàng 2 - Vị trí 2.1 (trái)
]

# Kéo đến đâu?
ROW_END_X = 900  # Cạnh phải của vườn (cùng cho cả 2 hàng)
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