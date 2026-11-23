"""Главное приложение SHR: GUI + очередь запросов + исполнитель."""
from __future__ import annotations
import logging
import queue as queue_module
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from .approval_queue import ApprovalQueue, ApprovalRequest, RequestStatus
from .config import AppConfig, get_log_path, load_config, save_config
from .github_client import GitHubAPIError, GitHubClient
from .secure_store import load_token, save_token

if TYPE_CHECKING:
    import tkinter as tk
    from .ui.main_window import MainWindow


class RequestExecutor(threading.Thread):
    """Фоновый исполнитель разрешённых запросов."""

    def __init__(self, app: "SHRApp"):
        super().__init__(daemon=True, name="RequestExecutor")
        self.app = app
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        while not self._stop.is_set():
            req = self.app.approval_queue.next_approved()
            if req is None:
                time.sleep(0.3)
                continue
            self.app.log(f"▶ Исполнение: {req.title} [{req.method} {req.url}]")
            try:
                result = self.app.github.request(
                    req.method, req.url, payload=req.payload,
                    params=req.params, headers=req.headers,
                )
                self.app.approval_queue.complete(req.id, result=result)
                self.app.log(f"✓ Готово: {req.title}")
            except GitHubAPIError as e:
                self.app.approval_queue.complete(req.id, error=str(e))
                self.app.log(f"✗ Ошибка: {req.title}: {e}")
            except Exception as e:
                self.app.approval_queue.complete(req.id, error=str(e))
                self.app.log(f"✗ Ошибка: {req.title}: {e}")


class SHRApp:
    """Контроллер приложения. Связывает GUI, API и очередь."""

    def __init__(self):
        self.config = load_config()
        self.github = GitHubClient(token=load_token(), api_base=self.config.api_base)
        self.approval_queue = ApprovalQueue(
            auto_approve_get=self.config.auto_approve_get,
            auto_approve_safe=self.config.auto_approve_safe,
        )
        self._log_queue: queue_module.Queue[str] = queue_module.Queue()
        self._setup_logging()
        self.executor = RequestExecutor(self)
        self.root: Optional[tk.Tk] = None
        self.main_window: Optional[MainWindow] = None

    # ── Логирование ────────────────────────────────────────────────────────

    def _setup_logging(self) -> None:
        log_path = get_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            level=getattr(logging, self.config.log_level.upper(), logging.INFO),
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[logging.FileHandler(log_path, encoding="utf-8"),
                      logging.StreamHandler()],
        )
        self.logger = logging.getLogger("shr")

    def log(self, msg: str) -> None:
        self.logger.info(msg)
        self._log_queue.put(msg)

    def drain_logs(self) -> list[str]:
        items = []
        while True:
            try:
                items.append(self._log_queue.get_nowait())
            except queue_module.Empty:
                break
        return items

    # ── Запросы к GitHub (все через очередь) ───────────────────────────────

    def api_request(self, title: str, method: str, url: str, description: str = "",
                    payload: Optional[dict] = None, params: Optional[dict] = None,
                    is_safe: bool = False, is_destructive: bool = False,
                    on_complete=None) -> ApprovalRequest:
        """Создать запрос в очереди. Исполнится только после подтверждения."""
        if not self.github.token:
            self.log("⚠ Токен не задан — запрос не создан. Укажите PAT в Настройках.")
            if self.main_window:
                self.main_window.show_token_warning()
            # Всё равно создаём запрос, но он будет отклонён при исполнении
        req = self.approval_queue.submit(
            title=title, method=method, url=url, description=description,
            payload=payload, params=params, is_safe=is_safe,
            is_destructive=is_destructive, on_complete=on_complete,
        )
        self.log(f"📋 Запрос создан: {req.title} (статус: {req.status.value})")
        return req

    # ── Токен ──────────────────────────────────────────────────────────────

    def set_token(self, token: str) -> None:
        save_token(token)
        self.github.set_token(token)
        self.config.github_token = ""  # не храним в открытом виде
        save_config(self.config)
        self.log("🔑 Токен GitHub сохранён (DPAPI)")

    def get_token_masked(self) -> str:
        t = load_token()
        if not t:
            return "(не задан)"
        return f"{t[:4]}…{t[-4:]} (длина {len(t)})"

    # ── Запуск GUI ─────────────────────────────────────────────────────────

    def run(self) -> None:
        import tkinter as tk
        from .ui.main_window import MainWindow
        self.executor.start()
        self.root = tk.Tk()
        self.root.title("SHR — Self-Hosted Runner GUI")
        self.root.geometry("1100x720")
        self.root.minsize(900, 600)
        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass
        self.main_window = MainWindow(self.root, self)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self) -> None:
        self.executor.stop()
        save_config(self.config)
        if self.root:
            self.root.destroy()

    def refresh_auto_approve(self) -> None:
        self.approval_queue.auto_approve_get = self.config.auto_approve_get
        self.approval_queue.auto_approve_safe = self.config.auto_approve_safe


def main() -> None:
    app = SHRApp()
    app.log("SHR запущен")
    app.run()


if __name__ == "__main__":
    main()
