"""
Module core/san_xuat.py
Xử lý chuyên biệt cho Máy Sản Xuất trong Khu Vườn Trên Mây:
- Mở máy tại hàng tương ứng.
- Tìm vị trí nguyên liệu trên khay (hỗ trợ chuyển trang nếu cần).
- Kéo thả nguyên liệu vào ô sản xuất (chống hụt, chống văng, giữ tại ô trước khi nhả tay).
- Quản lý vòng lặp sản xuất số lượng N (vd: 4 cái) với nhịp nghỉ vàng.
- Tự động phát hiện hết nguyên liệu (nút X kim cương) và đóng máy.
- Tự động sửa máy nếu được cấu hình.
"""

import os
import sys
import time
import logging
from typing import Tuple, List, Optional

from .adb import ADBController
from .image import ImageProcessor
from utils.utils import (
    find_image_v2, _should_stop, _sleep, _get_adb,
    set_state, PlayerState
)
from config import (
    INDEX_MAY, INDEX_SAN_XUAT_MAC_DINH,
    INDEX_NEXT_SAN_XUAT_MAC_DINH, INDEX_SUA_MAY_MAC_DINH,
    INDEX_THOAT_SAN_XUAT_MAC_DINH,
    TIME_SLEEP_SAN_XUAT as TIME_SLEEP,
    TIME_SLEEP_SHORT_SAN_XUAT as TIME_SLEEP_SHORT
)

logger = logging.getLogger(__name__)
img = ImageProcessor()
THRESHOLD = 0.85


def keo_vat_pham(adb: ADBController, start_pos: Tuple[int, int], end_pos: Tuple[int, int],
                 hold_start_ms: int = 48, hold_end_ms: int = 40, duration_ms: int = 72) -> bool:
    """
    Kéo thả 1 vật phẩm từ start_pos (icon nguyên liệu) vào end_pos (ô sản xuất):
    - Tối ưu siêu tốc (nhanh hơn 20%): hold_start: 48ms, lướt 72ms (3 bước), hold_end: 40ms.
    - Gửi trực tiếp chuỗi sendevent qua shell (;), loại bỏ hoàn toàn độ trễ ghi file flash.
    - Tổng thời gian kéo chỉ ~160ms, cực kỳ nhanh, dứt khoát và bám dính tốt.
    """
    try:
        event = adb.get_touch_device_event()

        num_steps = max(3, int(duration_ms / 25))
        step_delay_us = int((duration_ms * 1000) / num_steps)

        sys_start = adb.px_to_system(start_pos[0], start_pos[1])
        sys_end = adb.px_to_system(end_pos[0], end_pos[1])

        move_points = []
        for s in range(1, num_steps + 1):
            t = s / float(num_steps)
            mx = int(sys_start[0] + (sys_end[0] - sys_start[0]) * t)
            my = int(sys_start[1] + (sys_end[1] - sys_start[1]) * t)
            move_points.append((mx, my))

        cmds = []
        # 1. Chạm xuống tại điểm bắt đầu (Slot 0)
        cmds.append(f"sendevent {event} 3 47 0")
        cmds.append(f"sendevent {event} 3 57 0")
        cmds.append(f"sendevent {event} 1 330 1")
        cmds.append(f"sendevent {event} 3 53 {sys_start[0]}")
        cmds.append(f"sendevent {event} 3 54 {sys_start[1]}")
        cmds.append(f"sendevent {event} 0 0 0")

        # 2. Giữ ở điểm đầu để game nhấc dính icon (60ms)
        if hold_start_ms > 0:
            cmds.append(f"usleep {int(hold_start_ms * 1000)}")

        # 3. Kéo mượt qua các điểm trung gian (90ms)
        for mx, my in move_points:
            cmds.append(f"sendevent {event} 3 53 {mx}")
            cmds.append(f"sendevent {event} 3 54 {my}")
            cmds.append(f"sendevent {event} 0 0 0")
            cmds.append(f"usleep {step_delay_us}")

        # 4. Giữ tại ô sản xuất để kích hoạt vùng nhận đồ (50ms)
        if hold_end_ms > 0:
            cmds.append(f"usleep {int(hold_end_ms * 1000)}")

        # 5. Nhả tay thả vật phẩm vào ô
        cmds.append(f"sendevent {event} 1 330 0")
        cmds.append(f"sendevent {event} 3 57 4294967295")
        cmds.append(f"sendevent {event} 0 0 0")

        # Thực thi thẳng qua shell (;), cực nhanh không tốn I/O đĩa
        adb.device.shell(";".join(cmds))
        logger.info(f"[SAN_XUAT] Kéo nhanh ({start_pos} -> {end_pos}) thành công")
        return True
    except Exception as e:
        logger.warning(f"[SAN_XUAT] Lỗi khi kéo vật phẩm: {e}")
        return False


def tim_vp(template_path: str, count: int = 1, threshold: float = THRESHOLD, region=None):
    """Tìm vật phẩm sản xuất trên khay. Tối ưu: 1 screenshot cho cả VP + nút chuyển trang."""
    adb = _get_adb()
    if _should_stop():
        return None
    if count > 5:
        logger.info(f"[SAN_XUAT] Đã thử tìm VP {count} lần, dừng")
        return None

    screen = adb.screenshot_full()
    if screen is None:
        return None

    pos = img.find_template_color(template_path, threshold=threshold, screen_img=screen, region=region)
    if pos:
        logger.info(f"[SAN_XUAT] Tìm được {template_path} tại {pos}")
        return pos

    logger.info(f"[SAN_XUAT] Không tìm được {template_path} lần {count}, bấm chuyển trang")
    (x, y) = INDEX_NEXT_SAN_XUAT_MAC_DINH
    adb.tap(x, y)
    _sleep(TIME_SLEEP_SHORT)
    return tim_vp(template_path, count + 1, threshold=threshold, region=region)


def sua_may(threshold: float = THRESHOLD):
    """Xử lý sửa máy khi máy sản xuất bị hỏng."""
    adb = _get_adb()
    set_state(PlayerState.SUA_MAY)
    pos_sua = find_image_v2("assets/items/core_sua_may.png", True, threshold=threshold, max_retry=0)
    if pos_sua:
        x_sua, y_sua = pos_sua
        adb.tap(x_sua, y_sua)
        _sleep(TIME_SLEEP_SHORT)
        if INDEX_SUA_MAY_MAC_DINH is not None:
            (x_vang, y_vang) = INDEX_SUA_MAY_MAC_DINH
            adb.tap(x_vang, y_vang)
            _sleep(TIME_SLEEP_SHORT)
            logger.info("[SAN_XUAT] Sửa máy thành công")
        else:    
            pos_vang = find_image_v2("assets/items/core_sua_may_vang.png", True, threshold=threshold, max_retry=0)
            if pos_vang:
                x_vang, y_vang = pos_vang
                adb.tap(x_vang, y_vang)
                _sleep(TIME_SLEEP_SHORT)
                logger.info("[SAN_XUAT] Sửa máy thành công")
            else:
                logger.info("[SAN_XUAT] Không tìm thấy nút sửa máy vàng")

    (x, y) = INDEX_THOAT_SAN_XUAT_MAC_DINH
    adb.tap_fast(x, y, 2)


def xu_ly_may(config_may: dict, threshold: float = THRESHOLD, is_sua_may: bool = False) -> bool:
    """
    Xử lý mở máy sản xuất và kéo vật phẩm vào ô.
    Hỗ trợ sản xuất số lượng N (vd: 4 cái) với nhịp nghỉ chuẩn xác, không bị hụt ở cái thứ 4.
    """
    adb = _get_adb()
    row = str(config_may['row'])
    data = config_may.get('data', [])
    region = config_may.get('region')

    if row not in INDEX_MAY:
        logger.error(f"[SAN_XUAT] Không tìm thấy INDEX_MAY cho row {row}")
        return False

    x_may, y_may = INDEX_MAY[row]
    logger.info(f"[SAN_XUAT] Xử lý máy hàng {row} tại ({x_may}, {y_may})")

    max_tap = 3
    for i in range(max_tap):
        if _should_stop():
            return False

        adb.tap_sendevent_fast(x_may, y_may, 10)
        _sleep(TIME_SLEEP_SHORT)

        screen = adb.screenshot_full()
        if screen is None:
            continue

        pos_slot = img.find_template_color("assets/items/core_sanxuat_vp.png", threshold=threshold, screen_img=screen)
        if pos_slot:
            logger.info(f"[SAN_XUAT] Máy rảnh sau {i+1} lần tap")
            break

        pos_next_sx = img.find_template_color("assets/items/core_next_sanxuat.png", threshold=threshold, screen_img=screen)
        if pos_next_sx:
            logger.info(f"[SAN_XUAT] Tìm thấy next_sanxuat sau {i+1} lần tap")
            break

    # Mặc định ô sản xuất
    pos_slot = INDEX_SAN_XUAT_MAC_DINH

    for item_data in data:
        if _should_stop():
            return False

        path_item = item_data['path_item']
        total = item_data.get('total', 1)

        set_state(PlayerState.SAN_XUAT)
        logger.info(f"[SAN_XUAT] Bắt đầu sản xuất {total} x {path_item}")

        pos_item = tim_vp(path_item, threshold=threshold, region=region)
        if not pos_item:
            logger.warning(f"[SAN_XUAT] Không tìm thấy vật phẩm {path_item}")
            break

        x_item, y_item = pos_item
        x_slot, y_slot = pos_slot

        # Vòng lặp kéo N vật phẩm vào ô sản xuất
        for item_idx in range(total):
            if _should_stop():
                return False

            logger.info(f"[SAN_XUAT] Kéo cái thứ {item_idx + 1}/{total}...")
            keo_vat_pham(adb, (x_item, y_item), (x_slot, y_slot),
                         hold_start_ms=48, hold_end_ms=40, duration_ms=72)

            # Nghỉ giữa các lượt kéo (TIME_SLEEP_SAN_XUAT từ config)
            _sleep(TIME_SLEEP)

        # Kiểm tra popup hết nguyên liệu (nút X) 1 lần sau khi kéo xong danh sách
        screen = adb.screenshot_full()
        if screen is not None:
            pos_nut_x = img.find_template_color("assets/items/core_nut_x.png",
                                                threshold=threshold, screen_img=screen)
            if pos_nut_x:
                logger.info("[SAN_XUAT] Phát hiện popup hết nguyên liệu, đóng popup")
                x_x, y_x = pos_nut_x
                adb.tap(x_x, y_x)
                _sleep(TIME_SLEEP_SHORT)
                break

    if is_sua_may:
        sua_may(threshold=threshold)
    else:
        (x, y) = INDEX_THOAT_SAN_XUAT_MAC_DINH
        adb.tap_fast(x, y, 2)

    logger.info(f"[SAN_XUAT] Hoàn thành xử lý máy hàng {row}")
    _sleep(TIME_SLEEP_SHORT)
    return True
