"""Информация о системе (ОС, CPU, RAM, диск)."""
from __future__ import annotations
import platform
import shutil
import socket
import sys


def collect() -> dict:
    info = {
        "hostname": socket.gethostname(),
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "arch": platform.machine(),
        "python": sys.version.split()[0],
        "cpu": platform.processor() or "unknown",
    }
    try:
        import psutil
        info["cpu_count"] = psutil.cpu_count(logical=True)
        info["ram_total_gb"] = round(psutil.virtual_memory().total / (1024**3), 1)
        info["ram_used_gb"] = round(psutil.virtual_memory().used / (1024**3), 1)
        info["cpu_percent"] = psutil.cpu_percent(interval=0.5)
    except Exception:
        info["cpu_count"] = ""
        info["ram_total_gb"] = ""
    try:
        total, used, free = shutil.disk_usage("/")
        info["disk_total_gb"] = round(total / (1024**3), 1)
        info["disk_free_gb"] = round(free / (1024**3), 1)
    except Exception:
        pass
    return info
