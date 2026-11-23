"""Менеджер self-hosted runner'а на локальном компьютере.

Скачивание, распаковка, регистрация (config.cmd), служба Windows
(svc.cmd), удаление. Все операции — через subprocess, с логами.
"""
from __future__ import annotations
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional

from .config import get_runner_dir

LogFn = Callable[[str], None]


def detect_runner_asset() -> str:
    """Определить имя ассета runner'а для текущей ОС/архитектуры."""
    system = platform.system().lower()
    machine = platform.machine().lower()
    arch = "x64" if machine in ("amd64", "x86_64") else "arm64" if "arm" in machine else "x64"
    if system == "windows":
        return f"actions-runner-win-{arch}.zip"
    if system == "linux":
        return f"actions-runner-linux-{arch}.tar.gz"
    if system == "darwin":
        return f"actions-runner-osx-{arch}.tar.gz"
    return f"actions-runner-win-{arch}.zip"


def is_runner_installed(runner_dir: Optional[Path] = None) -> bool:
    d = runner_dir or get_runner_dir()
    return (d / "config.cmd").exists() or (d / "run.cmd").exists() or (d / "run.sh").exists()


def get_runner_status(runner_dir: Optional[Path] = None) -> dict:
    """Статус локального runner'а: установлен, конфиг, служба."""
    d = runner_dir or get_runner_dir()
    info = {
        "dir": str(d),
        "installed": is_runner_installed(d),
        "config_exists": (d / ".runner").exists(),
        "service_installed": False,
        "service_running": False,
        "runner_name": "",
        "labels": "",
    }
    # .runner — JSON с именем и метками
    runner_file = d / ".runner"
    if runner_file.exists():
        try:
            data = json.loads(runner_file.read_text(encoding="utf-8"))
            info["runner_name"] = data.get("agentName", "")
            info["labels"] = ",".join(data.get("agentLabels", []))
        except Exception:
            pass
    # Служба Windows
    if sys.platform == "win32":
        try:
            out = subprocess.run(
                ["sc", "query", "actions.runner"],
                capture_output=True, text=True, timeout=10,
            )
            info["service_installed"] = "actions.runner" in out.stdout
            info["service_running"] = "RUNNING" in out.stdout
        except Exception:
            pass
        # Альтернативное имя службы: actions.runner.<user>-<host>
        if not info["service_installed"]:
            try:
                out = subprocess.run(
                    ["sc", "query", "type=", "service"],
                    capture_output=True, text=True, timeout=10,
                )
                for line in out.stdout.splitlines():
                    if "actions.runner" in line.lower():
                        info["service_installed"] = True
                        break
            except Exception:
                pass
    return info


class RunnerManager:
    """Управление жизненным циклом runner'а."""

    def __init__(self, runner_dir: Optional[Path] = None, log: Optional[LogFn] = None):
        self.dir = runner_dir or get_runner_dir()
        self.log = log or (lambda m: print(m))

    # ── Скачивание ──────────────────────────────────────────────────────────

    def download(self, url: str, dest: Optional[Path] = None,
                 progress: Optional[Callable[[int, int], None]] = None) -> Path:
        dest = dest or (self.dir.parent / "runner-download" / Path(url).name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        self.log(f"Скачивание: {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "SHR/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as f:
            total = int(resp.headers.get("Content-Length", 0))
            done = 0
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
        self.log(f"Скачано: {dest} ({dest.stat().st_size} байт)")
        return dest

    def extract(self, archive: Path) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.log(f"Распаковка в {self.dir}")
        if archive.suffix == ".zip":
            with zipfile.ZipFile(archive) as z:
                z.extractall(self.dir)
        else:
            with tarfile.open(archive, "r:gz") as t:
                t.extractall(self.dir)
        self.log("Распаковка завершена")

    # ── Регистрация / удаление ─────────────────────────────────────────────

    def _run_cmd(self, args: list[str], cwd: Optional[Path] = None,
                 timeout: int = 120) -> tuple[int, str]:
        cmd = [str(self.dir / "config.cmd")] + args if sys.platform == "win32" else \
              [str(self.dir / "config.sh")] + args
        self.log(f"$ {' '.join(cmd)}")
        proc = subprocess.run(cmd, cwd=str(cwd or self.dir),
                              capture_output=True, text=True, timeout=timeout)
        out = (proc.stdout or "") + (proc.stderr or "")
        self.log(out[-2000:])
        return proc.returncode, out

    def configure(self, token: str, name: str, labels: str = "",
                  work_folder: str = "_work", url: str = "https://github.com",
                  no_service: bool = False, run_as_service: bool = True) -> tuple[int, str]:
        """Регистрация runner'а: config.cmd --token ... --name ... --labels ..."""
        args = ["--token", token, "--name", name, "--url", url,
                "--work", work_folder, "--unattended"]
        if labels:
            args += ["--labels", labels]
        if run_as_service and sys.platform == "win32":
            args += ["--runasservice"]
        elif no_service:
            args += ["--no-service"]
        return self._run_cmd(args)

    def remove_config(self) -> tuple[int, str]:
        """Снять регистрацию: config.cmd remove."""
        return self._run_cmd(["remove", "--unattended"])

    # ── Служба Windows ─────────────────────────────────────────────────────

    def _svc(self, action: str) -> tuple[int, str]:
        svc = str(self.dir / "svc.cmd")
        self.log(f"$ svc.cmd {action}")
        proc = subprocess.run([svc, action], cwd=str(self.dir),
                              capture_output=True, text=True, timeout=60)
        out = (proc.stdout or "") + (proc.stderr or "")
        self.log(out[-2000:])
        return proc.returncode, out

    def service_install(self) -> tuple[int, str]:
        return self._svc("install")

    def service_start(self) -> tuple[int, str]:
        return self._svc("start")

    def service_stop(self) -> tuple[int, str]:
        return self._svc("stop")

    def service_uninstall(self) -> tuple[int, str]:
        return self._svc("uninstall")

    def service_restart(self) -> tuple[int, str]:
        self.service_stop()
        time.sleep(2)
        return self.service_start()

    # ── Запуск вручную (без службы) ────────────────────────────────────────

    def run_foreground(self, log: Optional[LogFn] = None) -> int:
        """Запустить runner в foreground (блокирующий вызов)."""
        log = log or self.log
        if sys.platform == "win32":
            cmd = [str(self.dir / "run.cmd")]
        else:
            cmd = [str(self.dir / "run.sh")]
        log(f"Запуск: {' '.join(cmd)}")
        proc = subprocess.Popen(cmd, cwd=str(self.dir),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1)
        assert proc.stdout is not None
        for line in proc.stdout:
            log(line.rstrip())
        return proc.wait()

    # ── Утилиты ────────────────────────────────────────────────────────────

    def sha256(self, path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def cleanup_download(self, archive: Path) -> None:
        try:
            archive.unlink()
        except Exception:
            pass
