import ctypes
import logging
import os
import subprocess
import time
from dataclasses import dataclass
import psutil
from service.core.config import settings

log = logging.getLogger(__name__)


@dataclass
class IdleConfig:
    scan_idle_only: bool
    idle_minutes: int
    cpu_limit: int
    gpu_limit: int
    io_limit: int


class DiskIOMonitor:
    def __init__(self):
        self._last = psutil.disk_io_counters()
        self._last_time = time.time()

    def mb_per_s(self) -> float:
        now = time.time()
        cur = psutil.disk_io_counters()
        dt = max(now - self._last_time, 0.001)
        read_mb = (cur.read_bytes - self._last.read_bytes) / 1024 / 1024 / dt
        write_mb = (cur.write_bytes - self._last.write_bytes) / 1024 / 1024 / dt
        self._last = cur
        self._last_time = now
        return max(0.0, read_mb + write_mb)


def get_idle_seconds() -> float:
    if os.name != "nt":
        return 0.0
    try:
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)) == 0:
            return 0.0
        millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
        return millis / 1000.0
    except Exception:
        return 0.0


def get_gpu_percent() -> int:
    try:
        output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        values = []
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                values.append(int(line))
            except ValueError:
                continue
        return max(values) if values else 0
    except Exception:
        return 0


class IdleController:
    def __init__(self, cfg: IdleConfig):
        self.cfg = cfg
        self._disk = DiskIOMonitor()

    @classmethod
    def from_settings(cls) -> "IdleController":
        cfg = IdleConfig(
            scan_idle_only=settings.scan.scan_idle_only,
            idle_minutes=settings.scan.idle_minutes,
            cpu_limit=settings.scan.cpu_limit,
            gpu_limit=settings.scan.gpu_limit,
            io_limit=settings.scan.io_limit,
        )
        return cls(cfg)

    def is_idle(self) -> bool:
        if self.cfg.scan_idle_only:
            idle_sec = get_idle_seconds()
            if idle_sec < self.cfg.idle_minutes * 60:
                return False
        cpu = psutil.cpu_percent(interval=0.1)
        gpu = get_gpu_percent()
        io = self._disk.mb_per_s()
        return cpu < self.cfg.cpu_limit and gpu < self.cfg.gpu_limit and io < self.cfg.io_limit

    def wait_for_idle(self, stop_event=None, check_interval: float = 2.0) -> bool:
        while True:
            if stop_event and stop_event.is_set():
                return False
            if self.is_idle():
                return True
            time.sleep(check_interval)
