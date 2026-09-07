import os
import logging
import zipfile
from datetime import date


class DeviceNameFilter(logging.Filter):
    """Tự động thêm [device_name] vào mọi log message từ mọi module."""
    def filter(self, record):
        from utils.utils import get_device_name
        name = get_device_name()
        record.device = f"[{name}]" if name else "[main]"
        return True


class DailySizeZipFileHandler(logging.FileHandler):
    """Write to one active log file, then zip old chunks by date and size."""

    def __init__(self, filename, max_bytes=10 * 1024 * 1024, encoding=None):
        super().__init__(filename, mode="a", encoding=encoding, delay=True)
        self.max_bytes = max_bytes
        if os.path.exists(filename) and os.path.getsize(filename) > 0:
            self.current_date = date.fromtimestamp(os.path.getmtime(filename)).isoformat()
        else:
            self.current_date = date.today().isoformat()
        self.archive_dir = os.path.join(os.path.dirname(os.path.abspath(filename)), "archive")
        os.makedirs(self.archive_dir, exist_ok=True)

    def emit(self, record):
        try:
            if self._should_rollover():
                self._rollover()
            super().emit(record)
            if self._should_rollover(size_only=True):
                self._rollover()
        except Exception:
            self.handleError(record)

    def _should_rollover(self, size_only=False):
        if not os.path.exists(self.baseFilename):
            return False

        if os.path.getsize(self.baseFilename) <= 0:
            if not size_only:
                self.current_date = date.today().isoformat()
            return False

        if os.path.getsize(self.baseFilename) >= self.max_bytes:
            return True

        if not size_only and date.today().isoformat() != self.current_date:
            return True

        return False

    def _next_archive_paths(self, archive_date):
        idx = 1
        while True:
            stem = f"auto_config_{archive_date}_{idx:03d}"
            zip_path = os.path.join(self.archive_dir, f"{stem}.zip")
            log_name = f"{stem}.log"
            if not os.path.exists(zip_path):
                return zip_path, log_name
            idx += 1

    def _rollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None

        if not os.path.exists(self.baseFilename) or os.path.getsize(self.baseFilename) <= 0:
            self.current_date = date.today().isoformat()
            return

        archive_date = self.current_date
        zip_path, log_name = self._next_archive_paths(archive_date)
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(self.baseFilename, arcname=log_name)
        os.remove(self.baseFilename)
        self.current_date = date.today().isoformat()
