import csv
import os
import threading
from datetime import datetime


STATS_DIR = os.path.join("data", "daily_stats")
TASK_LABELS = {
    "so_luot": "Lượt",
    "ban_do": "Bán",
    "giao_tom": "Tôm",
    "mo_ruong": "Rương",
    "giao_cu": "Cú",
}
_lock = threading.Lock()


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _stats_path(date=None):
    date = date or _today()
    return os.path.join(STATS_DIR, f"{date}.csv")


def _empty_counts():
    return {task: 0 for task in TASK_LABELS}


def _read_rows(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _write_rows(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fieldnames = ["date", "device", "task", "count", "duration_s", "updated_at", "details"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            row_dict = {
                "date": r.get("date", ""),
                "device": r.get("device", ""),
                "task": r.get("task", ""),
                "count": r.get("count", ""),
                "duration_s": r.get("duration_s", ""),
                "updated_at": r.get("updated_at", ""),
                "details": r.get("details", ""),
            }
            writer.writerow(row_dict)


def record_daily_stat(adb_or_serial, task, amount=1, date=None, duration=None, details=None):
    """Increment a per-device daily task counter and persist it to CSV."""
    if task not in TASK_LABELS:
        return
    serial = getattr(adb_or_serial, "serial", None) or str(adb_or_serial or "unknown")
    date = date or _today()
    path = _stats_path(date)
    with _lock:
        rows = _read_rows(path)
        found = False
        for row in rows:
            if row.get("date") == date and row.get("device") == serial and row.get("task") == task:
                try:
                    current = int(row.get("count", 0))
                except (TypeError, ValueError):
                    current = 0
                row["count"] = str(current + int(amount))
                row["updated_at"] = _now()
                if duration is not None:
                    row["duration_s"] = str(round(float(duration), 1))
                if details is not None:
                    row["details"] = str(details)
                found = True
                break
        if not found:
            row_entry = {
                "date": date,
                "device": serial,
                "task": task,
                "count": str(int(amount)),
                "duration_s": str(round(float(duration), 1)) if duration is not None else "",
                "updated_at": _now(),
                "details": str(details) if details is not None else "",
            }
            rows.append(row_entry)
        _write_rows(path, rows)


def record_loop_run(adb_or_serial, loop_index=1, duration=0.0, task="tc_may", note="", date=None, update_summary=True):
    """Ghi lại 1 lượt chạy cụ thể (kèm thời gian chạy tính bằng giây) vào CSV,
    đồng thời cập nhật dòng tổng kết số lượt chạy (so_luot) nếu update_summary=True.
    """
    serial = getattr(adb_or_serial, "serial", None) or str(adb_or_serial or "unknown")
    date = date or _today()
    path = _stats_path(date)
    duration_val = round(float(duration), 1)

    with _lock:
        rows = _read_rows(path)

        # 1. Cập nhật hoặc tạo dòng tổng kết 'so_luot' cho thiết bị này
        if update_summary:
            # Tính toán tốc độ trung bình từ các lượt trước đó
            durations = []
            for r in rows:
                if r.get("date") == date and r.get("device") == serial and r.get("task") in ("tc_may", "vong_lap"):
                    try:
                        durations.append(float(r.get("duration_s", 0)))
                    except (ValueError, TypeError):
                        pass
            durations.append(duration_val)
            avg_speed = round(sum(durations) / len(durations), 1) if durations else duration_val

            found_summary = False
            for row in rows:
                if row.get("date") == date and row.get("device") == serial and row.get("task") == "so_luot":
                    try:
                        current_count = int(row.get("count", 0))
                    except (TypeError, ValueError):
                        current_count = 0
                    new_count = current_count + 1
                    row["count"] = str(new_count)
                    row["duration_s"] = str(duration_val)
                    row["updated_at"] = _now()
                    row["details"] = f"Tổng {new_count} lượt | Vừa xong: {duration_val}s | TB: {avg_speed}s/lượt"
                    found_summary = True
                    break

            if not found_summary:
                rows.insert(0, {
                    "date": date,
                    "device": serial,
                    "task": "so_luot",
                    "count": "1",
                    "duration_s": str(duration_val),
                    "updated_at": _now(),
                    "details": f"Tổng 1 lượt | Vừa xong: {duration_val}s | TB: {avg_speed}s/lượt",
                })

        # 2. Thêm dòng nhật ký chi tiết cho lượt chạy này
        detail_msg = note or f"Lượt {loop_index} ({task}) hoàn thành trong {duration_val}s"
        rows.append({
            "date": date,
            "device": serial,
            "task": task,
            "count": str(loop_index),
            "duration_s": str(duration_val),
            "updated_at": _now(),
            "details": detail_msg,
        })

        _write_rows(path, rows)


def get_daily_counts(serial=None, date=None):
    """Return today's counts. If serial is provided, returns counts for that device."""
    date = date or _today()
    path = _stats_path(date)
    counts = _empty_counts()
    with _lock:
        rows = _read_rows(path)
    for row in rows:
        if row.get("date") != date:
            continue
        if serial is not None and row.get("device") != serial:
            continue
        task = row.get("task")
        if task not in counts:
            continue
        try:
            counts[task] += int(row.get("count", 0))
        except (TypeError, ValueError):
            pass
    return counts


def get_daily_summary(serial=None, date=None):
    """Lấy số liệu thống kê kèm thông tin thời gian/tốc độ của thiết bị."""
    date = date or _today()
    path = _stats_path(date)
    counts = _empty_counts()
    last_duration = None
    with _lock:
        rows = _read_rows(path)
    for row in rows:
        if row.get("date") != date:
            continue
        if serial is not None and row.get("device") != serial:
            continue
        task = row.get("task")
        if task in counts:
            try:
                counts[task] += int(row.get("count", 0))
            except (TypeError, ValueError):
                pass
        if task == "so_luot" and row.get("duration_s"):
            try:
                last_duration = float(row.get("duration_s"))
            except (TypeError, ValueError):
                pass
    return counts, last_duration


def format_daily_counts(serial=None, date=None):
    counts, last_dur = get_daily_summary(serial=serial, date=date)
    parts = []
    if counts.get("so_luot", 0) > 0:
        if last_dur is not None:
            parts.append(f"Lượt {counts['so_luot']} ({last_dur}s)")
        else:
            parts.append(f"Lượt {counts['so_luot']}")
    parts.extend([
        f"Bán {counts['ban_do']}",
        f"Tôm {counts['giao_tom']}",
        f"Rương {counts['mo_ruong']}",
        f"Cú {counts['giao_cu']}",
    ])
    return " | ".join(parts)


def get_today_stats_path():
    return _stats_path(_today())

