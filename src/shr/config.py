"""Конфигурация приложения SHR."""
from __future__ import annotations
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path


def get_app_dir() -> Path:
    """Папка данных приложения: %APPDATA%\\SHR на Windows, ~/.shr на Linux."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return Path(base) / "SHR"
    return Path.home() / ".shr"


def get_config_path() -> Path:
    return get_app_dir() / "config.json"


def get_log_path() -> Path:
    return get_app_dir() / "shr.log"


def get_runner_dir() -> Path:
    """Папка установки runner'а по умолчанию."""
    if sys.platform == "win32":
        return Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "GitHub Runner"
    return Path.home() / "actions-runner"


@dataclass
class AppConfig:
    """Настройки приложения."""
    github_token: str = ""          # PAT (хранится зашифрованным отдельно)
    default_owner: str = ""         # владелец по умолчанию (user/org)
    default_repo: str = ""          # репозиторий по умолчанию
    runner_name: str = ""           # имя runner'а (по умолчанию hostname)
    runner_labels: str = "self-hosted,windows,x64"
    runner_work_folder: str = "_work"
    runner_dir: str = ""            # путь к runner'у, пусто = по умолчанию
    auto_approve_get: bool = False  # авто-разрешать безопасные GET-запросы
    auto_approve_safe: bool = False # авто-разрешать безопасные операции
    confirm_destructive: bool = True  # дополнительное подтверждение для DELETE
    check_updates: bool = True
    minimize_to_tray: bool = True
    start_with_windows: bool = False
    log_level: str = "INFO"
    api_base: str = "https://api.github.com"

    def resolved_runner_dir(self) -> Path:
        if self.runner_dir:
            return Path(self.runner_dir)
        return get_runner_dir()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        known = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


def load_config() -> AppConfig:
    path = get_config_path()
    if not path.exists():
        return AppConfig()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return AppConfig.from_dict(data)
    except Exception:
        return AppConfig()


def save_config(cfg: AppConfig) -> None:
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Токен не сохраняем в открытом виде в config.json — он в secure store
    data = cfg.to_dict()
    data["github_token"] = ""
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
