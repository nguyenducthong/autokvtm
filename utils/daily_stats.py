import csv
import os
import threading
from datetime import datetime


STATS_DIR = os.path.join("data", "daily_stats")
TASK_LABELS = {
    "ban_do": "Bán",
    "giao_tom": "Tôm",
    "mo_ruong": "Rương",
    "giao_cu": "Cú",
    "sang_ban_be": "Bạn bè",
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
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _write_rows(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fieldnames = ["date", "device", "task", "count", "updated_at"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def record_daily_stat(adb_or_serial, task, amount=1, date=None):
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
                found = True
                break
        if not found:
            rows.append({
                "date": date,
                "device": serial,
                "task": task,
                "count": str(int(amount)),
                "updated_at": _now(),
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


def format_daily_counts(serial=None, date=None):
    counts = get_daily_counts(serial=serial, date=date)
    return (
        f"Bán {counts['ban_do']} | "
        f"Tôm {counts['giao_tom']} | "
        f"Rương {counts['mo_ruong']} | "
        f"Cú {counts['giao_cu']} | "
        f"Bạn {counts['sang_ban_be']}"
    )


def get_today_stats_path():
    return _stats_path(_today())
