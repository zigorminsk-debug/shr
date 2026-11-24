"""Главное окно SHR: вкладки Дашборд / Runner / Репозитории / Actions / Issues / Секреты / Запросы / Логи / Настройки."""
from __future__ import annotations
import json
import socket
import threading
import tkinter as tk
from tkinter import filedialog, ttk
from pathlib import Path
from typing import TYPE_CHECKING

from .. import git_ops, system_info
from ..approval_queue import ApprovalRequest, RequestStatus
from ..config import save_config
from ..runner_manager import RunnerManager, detect_runner_asset, get_runner_status, is_runner_installed
from .widgets import LogView, StatusCard, ask_text, confirm, open_url, show_error, show_info

if TYPE_CHECKING:
    from ..app import SHRApp


class MainWindow:
    def __init__(self, root: tk.Tk, app: "SHRApp"):
        self.root = root
        self.app = app
        self._build_topbar()
        self._build_notebook()
        self._build_statusbar()
        self._refresh_loop()
        self._refresh_dashboard()
        self.app.log("GUI инициализирован")

    # ── Верхняя панель ─────────────────────────────────────────────────────

    def _build_topbar(self) -> None:
        bar = ttk.Frame(self.root, padding=6)
        bar.pack(side="top", fill="x")
        ttk.Label(bar, text="SHR", font=("Segoe UI", 16, "bold")).pack(side="left")
        ttk.Label(bar, text="Self-Hosted Runner GUI", font=("Segoe UI", 10)).pack(side="left", padx=(4, 0))
        self.conn_label = ttk.Label(bar, text="● Не подключено", foreground="red")
        self.conn_label.pack(side="left", padx=16)
        self.pending_label = ttk.Label(bar, text="Запросов: 0")
        self.pending_label.pack(side="right")
        ttk.Button(bar, text="Проверить подключение", command=self._test_connection).pack(side="right", padx=4)
        ttk.Button(bar, text="Открыть GitHub", command=lambda: open_url("https://github.com")).pack(side="right", padx=4)

    def show_token_warning(self) -> None:
        show_error(self.root, "Нет токена",
                   "Сначала укажите Personal Access Token во вкладке «Настройки».\n"
                   "Создать PAT: GitHub → Settings → Developer settings → Personal access tokens.")

    def _test_connection(self) -> None:
        def cb(result, error):
            if error:
                self.conn_label.configure(text="● Ошибка", foreground="red")
                show_error(self.root, "Подключение", f"Ошибка: {error}")
            else:
                login = result.get("login", "?") if isinstance(result, dict) else "?"
                self.conn_label.configure(text=f"● Подключено как {login}", foreground="green")
                show_info(self.root, "Подключение", f"Успешно! Вы вошли как {login}")
        self.app.api_request("Проверка подключения (GET /user)", "GET", "/user",
                             "Проверка токена и прав доступа", is_safe=True, on_complete=cb)

    # ── Вкладки ────────────────────────────────────────────────────────────

    def _build_notebook(self) -> None:
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(side="top", fill="both", expand=True, padx=6, pady=4)
        self.tab_dashboard = ttk.Frame(self.notebook)
        self.tab_runner = ttk.Frame(self.notebook)
        self.tab_repos = ttk.Frame(self.notebook)
        self.tab_actions = ttk.Frame(self.notebook)
        self.tab_issues = ttk.Frame(self.notebook)
        self.tab_secrets = ttk.Frame(self.notebook)
        self.tab_requests = ttk.Frame(self.notebook)
        self.tab_logs = ttk.Frame(self.notebook)
        self.tab_settings = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_dashboard, text="Дашборд")
        self.notebook.add(self.tab_runner, text="Runner")
        self.notebook.add(self.tab_repos, text="Репозитории")
        self.notebook.add(self.tab_actions, text="Actions")
        self.notebook.add(self.tab_issues, text="Issues / PR")
        self.notebook.add(self.tab_secrets, text="Секреты")
        self.notebook.add(self.tab_requests, text="Запросы ⏳")
        self.notebook.add(self.tab_logs, text="Логи")
        self.notebook.add(self.tab_settings, text="Настройки")
        self._build_dashboard()
        self._build_runner()
        self._build_repos()
        self._build_actions()
        self._build_issues()
        self._build_secrets()
        self._build_requests()
        self._build_logs()
        self._build_settings()

    def _build_statusbar(self) -> None:
        self.statusbar = ttk.Label(self.root, text="Готово", anchor="w", padding=4)
        self.statusbar.pack(side="bottom", fill="x")

    # ── Дашборд ────────────────────────────────────────────────────────────

    def _build_dashboard(self) -> None:
        f = self.tab_dashboard
        cards = ttk.Frame(f)
        cards.pack(fill="x", padx=8, pady=8)
        self.card_token = StatusCard(cards, "Токен GitHub")
        self.card_token.pack(side="left", fill="both", expand=True, padx=4)
        self.card_runner = StatusCard(cards, "Локальный runner")
        self.card_runner.pack(side="left", fill="both", expand=True, padx=4)
        self.card_system = StatusCard(cards, "Система")
        self.card_system.pack(side="left", fill="both", expand=True, padx=4)
        self.card_rate = StatusCard(cards, "Rate limit")
        self.card_rate.pack(side="left", fill="both", expand=True, padx=4)

        quick = ttk.LabelFrame(f, text="Быстрые действия", padding=8)
        quick.pack(fill="x", padx=8, pady=4)
        ttk.Button(quick, text="Обновить статус", command=self._refresh_dashboard).pack(side="left", padx=4)
        ttk.Button(quick, text="Список runner'ов (repo)", command=self._dash_list_runners).pack(side="left", padx=4)
        ttk.Button(quick, text="Rate limit", command=self._dash_rate_limit).pack(side="left", padx=4)
        ttk.Button(quick, text="Открыть папку runner'а", command=self._dash_open_runner_dir).pack(side="left", padx=4)

        self.dash_log = LogView(f, height=14)
        self.dash_log.pack(fill="both", expand=True, padx=8, pady=8)

    def _refresh_dashboard(self) -> None:
        token_masked = self.app.get_token_masked()
        has = bool(self.app.github.token)
        self.card_token.set("Задан" if has else "Не задан", token_masked)
        st = get_runner_status()
        self.card_runner.set("Установлен" if st["installed"] else "Не установлен",
                             f"{st['runner_name'] or st['dir']}")
        info = system_info.collect()
        self.card_system.set(info["hostname"], f"{info['os']} · {info['arch']}")
        rl = self.app.github.rate_limit_remaining
        self.card_rate.set(str(rl) if rl is not None else "—", "осталось запросов")
        self.dash_log.append(f"Статус обновлён: {info['hostname']}, runner={'да' if st['installed'] else 'нет'}")

    def _dash_list_runners(self) -> None:
        owner = self.app.config.default_owner
        repo = self.app.config.default_repo
        if not owner or not repo:
            show_error(self.root, "Не задано", "Укажите владельца и репозиторий в Настройках.")
            return
        def cb(result, error):
            if error:
                self.dash_log.append(f"✗ {error}")
            else:
                self.dash_log.append(f"Runner'ов: {len(result)}")
                for r in result:
                    self.dash_log.append(f"  • {r.get('name')} — {'online' if r.get('status')=='online' else 'offline'} "
                                         f"(id={r.get('id')}, labels={r.get('labels')})")
        self.app.api_request(f"Список runner'ов {owner}/{repo}", "GET",
                             f"/repos/{owner}/{repo}/actions/runners",
                             "Получить список self-hosted runner'ов репозитория",
                             is_safe=True, on_complete=cb)

    def _dash_rate_limit(self) -> None:
        def cb(result, error):
            if error:
                self.dash_log.append(f"✗ {error}")
            else:
                core = result.get("resources", {}).get("core", {}) if isinstance(result, dict) else {}
                self.dash_log.append(f"Rate limit: {core.get('remaining')}/{core.get('limit')} "
                                     f"(сброс через {core.get('reset')})")
        self.app.api_request("Rate limit (GET /rate_limit)", "GET", "/rate_limit",
                             "Проверить лимит запросов API", is_safe=True, on_complete=cb)

    def _dash_open_runner_dir(self) -> None:
        d = self.app.config.resolved_runner_dir()
        d.mkdir(parents=True, exist_ok=True)
        import os
        os.startfile(str(d)) if hasattr(os, "startfile") else open_url(d.as_uri())

    # ── Runner ─────────────────────────────────────────────────────────────

    def _build_runner(self) -> None:
        f = self.tab_runner
        top = ttk.Frame(f)
        top.pack(fill="x", padx=8, pady=8)
        self.runner_status_label = ttk.Label(top, text="Статус: …", font=("Segoe UI", 10, "bold"))
        self.runner_status_label.pack(side="left")
        ttk.Button(top, text="Обновить", command=self._refresh_runner_status).pack(side="right")

        # Установка
        install = ttk.LabelFrame(f, text="1. Скачать и установить runner", padding=8)
        install.pack(fill="x", padx=8, pady=4)
        ttk.Button(install, text="Скачать runner (latest)", command=self._runner_download).pack(side="left", padx=4)
        ttk.Button(install, text="Скачать по URL…", command=self._runner_download_custom).pack(side="left", padx=4)
        self.runner_progress = ttk.Progressbar(install, mode="determinate", length=200)
        self.runner_progress.pack(side="left", padx=8)

        # Регистрация
        reg = ttk.LabelFrame(f, text="2. Зарегистрировать (нужен токен регистрации от GitHub)", padding=8)
        reg.pack(fill="x", padx=8, pady=4)
        ttk.Button(reg, text="Получить токен регистрации (repo)", command=self._runner_get_token_repo).pack(side="left", padx=4)
        ttk.Button(reg, text="Получить токен регистрации (org)", command=self._runner_get_token_org).pack(side="left", padx=4)
        ttk.Button(reg, text="JIT-токен (эфемерный)", command=self._runner_get_jit).pack(side="left", padx=4)
        ttk.Button(reg, text="Зарегистрировать локально…", command=self._runner_configure_dialog).pack(side="left", padx=4)

        # Служба
        svc = ttk.LabelFrame(f, text="3. Служба Windows (svc.cmd)", padding=8)
        svc.pack(fill="x", padx=8, pady=4)
        ttk.Button(svc, text="Установить службу", command=lambda: self._runner_svc("install")).pack(side="left", padx=4)
        ttk.Button(svc, text="Запустить", command=lambda: self._runner_svc("start")).pack(side="left", padx=4)
        ttk.Button(svc, text="Остановить", command=lambda: self._runner_svc("stop")).pack(side="left", padx=4)
        ttk.Button(svc, text="Перезапустить", command=lambda: self._runner_svc("restart")).pack(side="left", padx=4)
        ttk.Button(svc, text="Удалить службу", command=lambda: self._runner_svc("uninstall")).pack(side="left", padx=4)
        ttk.Button(svc, text="Запуск вручную (foreground)", command=self._runner_run_foreground).pack(side="left", padx=4)

        # Удаление
        rem = ttk.LabelFrame(f, text="4. Удаление", padding=8)
        rem.pack(fill="x", padx=8, pady=4)
        ttk.Button(rem, text="Снять регистрацию (config remove)", command=self._runner_remove_config).pack(side="left", padx=4)
        ttk.Button(rem, text="Удалить runner с GitHub (по ID)…", command=self._runner_remove_remote).pack(side="left", padx=4)

        self.runner_log = LogView(f, height=12)
        self.runner_log.pack(fill="both", expand=True, padx=8, pady=8)
        self._refresh_runner_status()

    def _refresh_runner_status(self) -> None:
        st = get_runner_status()
        txt = (f"Установлен: {'да' if st['installed'] else 'нет'} · "
               f"Имя: {st['runner_name'] or '—'} · Метки: {st['labels'] or '—'} · "
               f"Служба: {'запущена' if st['service_running'] else 'установлена' if st['service_installed'] else 'нет'}")
        self.runner_status_label.configure(text=txt)
        self.runner_log.append(txt)

    def _runner_download(self) -> None:
        def cb(result, error):
            if error:
                self.runner_log.append(f"✗ {error}")
                return
            asset_name = detect_runner_asset()
            url = ""
            for a in result.get("assets", []):
                if a.get("name") == asset_name:
                    url = a.get("browser_download_url", "")
                    break
            if not url:
                self.runner_log.append(f"✗ Ассет {asset_name} не найден в релизе {result.get('tag_name')}")
                return
            self.runner_log.append(f"Релиз {result.get('tag_name')}, ассет {asset_name}")
            self._do_download(url)
        self.app.api_request("Получить latest runner release", "GET",
                             "/repos/actions/runner/releases/latest",
                             "Узнать URL скачивания actions/runner", is_safe=True, on_complete=cb)

    def _runner_download_custom(self) -> None:
        url = ask_text(self.root, "URL runner'а", "URL ZIP/TAR.GZ архива actions/runner:")
        if url:
            self._do_download(url)

    def _do_download(self, url: str) -> None:
        mgr = RunnerManager(log=self.runner_log.append)
        def worker():
            try:
                def prog(done, total):
                    if total:
                        self.runner_progress["value"] = done / total * 100
                archive = mgr.download(url, progress=prog)
                mgr.extract(archive)
                self.runner_log.append("✓ Runner скачан и распакован")
                self.root.after(0, self._refresh_runner_status)
            except Exception as e:
                self.runner_log.append(f"✗ Ошибка скачивания: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def _runner_get_token_repo(self) -> None:
        owner, repo = self.app.config.default_owner, self.app.config.default_repo
        if not owner or not repo:
            show_error(self.root, "Не задано", "Укажите owner/repo в Настройках.")
            return
        def cb(result, error):
            if error:
                self.runner_log.append(f"✗ {error}")
            else:
                token = result.get("token", "")
                self.runner_log.append(f"✓ Токен регистрации (repo): {token[:8]}… (действителен ~1 час)")
                show_info(self.root, "Токен регистрации",
                          f"Токен получен:\n{token}\n\nТеперь нажмите «Зарегистрировать локально…» и вставьте его.")
        self.app.api_request(f"Токен регистрации {owner}/{repo}", "POST",
                             f"/repos/{owner}/{repo}/actions/runners/registration-token",
                             "Создать токен регистрации runner'а для репозитория",
                             is_destructive=False, on_complete=cb)

    def _runner_get_token_org(self) -> None:
        org = ask_text(self.root, "Организация", "Имя организации (org):", self.app.config.default_owner)
        if not org:
            return
        def cb(result, error):
            if error:
                self.runner_log.append(f"✗ {error}")
            else:
                token = result.get("token", "")
                self.runner_log.append(f"✓ Токен регистрации (org {org}): {token[:8]}…")
                show_info(self.root, "Токен регистрации", f"Токен:\n{token}")
        self.app.api_request(f"Токен регистрации org {org}", "POST",
                             f"/orgs/{org}/actions/runners/registration-token",
                             "Создать токен регистрации runner'а для организации",
                             on_complete=cb)

    def _runner_get_jit(self) -> None:
        owner, repo = self.app.config.default_owner, self.app.config.default_repo
        if not owner or not repo:
            show_error(self.root, "Не задано", "Укажите owner/repo в Настройках.")
            return
        labels = [l.strip() for l in self.app.config.runner_labels.split(",") if l.strip()]
        def cb(result, error):
            if error:
                self.runner_log.append(f"✗ {error}")
            else:
                self.runner_log.append(f"✓ JIT-конфиг: {json.dumps(result)[:300]}")
                show_info(self.root, "JIT-токен", json.dumps(result, indent=2, ensure_ascii=False))
        self.app.api_request(f"JIT-токен {owner}/{repo}", "POST",
                             f"/repos/{owner}/{repo}/actions/runners/generate-jitconfig",
                             f"Сгенерировать JIT-конфиг для эфемерного runner'а, метки: {labels}",
                             payload={"name": "", "labels": labels}, on_complete=cb)

    def _runner_configure_dialog(self) -> None:
        token = ask_text(self.root, "Регистрация runner'а", "Вставьте токен регистрации:")
        if not token:
            return
        name = ask_text(self.root, "Имя runner'а", "Имя runner'а:", socket.gethostname())
        if name is None:
            return
        labels = ask_text(self.root, "Метки", "Метки (через запятую):", self.app.config.runner_labels)
        if labels is None:
            return
        mgr = RunnerManager(log=self.runner_log.append)
        def worker():
            try:
                code, out = mgr.configure(token, name, labels)
                self.runner_log.append(f"config.cmd завершён с кодом {code}")
                self.root.after(0, self._refresh_runner_status)
            except Exception as e:
                self.runner_log.append(f"✗ {e}")
        threading.Thread(target=worker, daemon=True).start()

    def _runner_svc(self, action: str) -> None:
        if not confirm(self.root, "Служба runner'а",
                       f"Выполнить svc.cmd {action}?\n(может потребоваться запуск от администратора)"):
            return
        mgr = RunnerManager(log=self.runner_log.append)
        def worker():
            try:
                if action == "install":
                    mgr.service_install()
                elif action == "start":
                    mgr.service_start()
                elif action == "stop":
                    mgr.service_stop()
                elif action == "uninstall":
                    mgr.service_uninstall()
                elif action == "restart":
                    mgr.service_restart()
                self.root.after(0, self._refresh_runner_status)
            except Exception as e:
                self.runner_log.append(f"✗ {e}")
        threading.Thread(target=worker, daemon=True).start()

    def _runner_run_foreground(self) -> None:
        mgr = RunnerManager(log=self.runner_log.append)
        def worker():
            try:
                mgr.run_foreground()
            except Exception as e:
                self.runner_log.append(f"✗ {e}")
        threading.Thread(target=worker, daemon=True).start()
        self.runner_log.append("Runner запущен в foreground (смотрите лог)")

    def _runner_remove_config(self) -> None:
        if not confirm(self.root, "Снятие регистрации", "Выполнить config.cmd remove?"):
            return
        mgr = RunnerManager(log=self.runner_log.append)
        def worker():
            try:
                mgr.remove_config()
                self.root.after(0, self._refresh_runner_status)
            except Exception as e:
                self.runner_log.append(f"✗ {e}")
        threading.Thread(target=worker, daemon=True).start()

    def _runner_remove_remote(self) -> None:
        owner, repo = self.app.config.default_owner, self.app.config.default_repo
        rid = ask_text(self.root, "Удалить runner", "ID runner'а на GitHub:")
        if not rid:
            return
        if not confirm(self.root, "Удаление", f"Удалить runner #{rid} из {owner}/{repo}?\nЭто действие нельзя отменить."):
            return
        def cb(result, error):
            self.runner_log.append("✓ Runner удалён с GitHub" if not error else f"✗ {error}")
        self.app.api_request(f"Удалить runner #{rid}", "DELETE",
                             f"/repos/{owner}/{repo}/actions/runners/{rid}",
                             "Удалить self-hosted runner с GitHub (деструктивно)",
                             is_destructive=True, on_complete=cb)

    # ── Репозитории ────────────────────────────────────────────────────────

    def _build_repos(self) -> None:
        f = self.tab_repos
        top = ttk.Frame(f)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Button(top, text="Мои репозитории", command=self._repos_list_mine).pack(side="left", padx=4)
        ttk.Button(top, text="Репозитории владельца…", command=self._repos_list_owner).pack(side="left", padx=4)
        ttk.Button(top, text="Создать репозиторий…", command=self._repos_create).pack(side="left", padx=4)
        ttk.Button(top, text="Клонировать (git)…", command=self._repos_clone).pack(side="left", padx=4)
        self.repos_tree = ttk.Treeview(f, columns=("name", "lang", "stars", "updated"), show="headings")
        self.repos_tree.heading("name", text="Репозиторий")
        self.repos_tree.heading("lang", text="Язык")
        self.repos_tree.heading("stars", text="★")
        self.repos_tree.heading("updated", text="Обновлён")
        self.repos_tree.pack(fill="both", expand=True, padx=8, pady=4)
        self.repos_log = LogView(f, height=6)
        self.repos_log.pack(fill="x", padx=8, pady=4)

    def _repos_fill(self, repos: list) -> None:
        for item in self.repos_tree.get_children():
            self.repos_tree.delete(item)
        for r in repos:
            self.repos_tree.insert("", "end", values=(
                r.get("full_name", ""), r.get("language") or "—",
                r.get("stargazers_count", 0), (r.get("updated_at") or "")[:10]))

    def _repos_list_mine(self) -> None:
        def cb(result, error):
            if error:
                self.repos_log.append(f"✗ {error}")
            else:
                self._repos_fill(result)
                self.repos_log.append(f"Найдено: {len(result)}")
        self.app.api_request("Список моих репозиториев", "GET", "/user/repos",
                             "Получить репозитории текущего пользователя",
                             params={"affiliation": "owner", "per_page": 100},
                             is_safe=True, on_complete=cb)

    def _repos_list_owner(self) -> None:
        owner = ask_text(self.root, "Владелец", "Владелец (user/org):", self.app.config.default_owner)
        if not owner:
            return
        def cb(result, error):
            if error:
                self.repos_log.append(f"✗ {error}")
            else:
                self._repos_fill(result)
                self.repos_log.append(f"Найдено: {len(result)}")
        self.app.api_request(f"Репозитории {owner}", "GET", f"/users/{owner}/repos",
                             f"Получить репозитории {owner}", is_safe=True, on_complete=cb)

    def _repos_create(self) -> None:
        name = ask_text(self.root, "Создать репозиторий", "Имя репозитория:")
        if not name:
            return
        private = confirm(self.root, "Приватность", "Сделать репозиторий приватным?\nДа = приватный, Нет = публичный")
        def cb(result, error):
            if error:
                self.repos_log.append(f"✗ {error}")
            else:
                self.repos_log.append(f"✓ Создан: {result.get('full_name')}")
        self.app.api_request(f"Создать репозиторий {name}", "POST", "/user/repos",
                             f"Создать репозиторий {name} ({'private' if private else 'public'})",
                             payload={"name": name, "private": private, "auto_init": True},
                             on_complete=cb)

    def _repos_clone(self) -> None:
        url = ask_text(self.root, "Клонировать", "URL репозитория (https):")
        if not url:
            return
        dest = filedialog.askdirectory(title="Папка для клонирования")
        if not dest:
            return
        def worker():
            code, out = git_ops.clone(url, Path(dest) / Path(url).stem.replace(".git", ""))
            self.repos_log.append(out[-1500:])
            self.repos_log.append(f"clone завершён с кодом {code}")
        threading.Thread(target=worker, daemon=True).start()

    # ── Actions ────────────────────────────────────────────────────────────

    def _build_actions(self) -> None:
        f = self.tab_actions
        top = ttk.Frame(f)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Button(top, text="Workflows", command=self._actions_list_workflows).pack(side="left", padx=4)
        ttk.Button(top, text="Запуски (runs)", command=self._actions_list_runs).pack(side="left", padx=4)
        ttk.Button(top, text="Запустить workflow…", command=self._actions_trigger).pack(side="left", padx=4)
        ttk.Button(top, text="Отменить последний запуск", command=self._actions_cancel_last).pack(side="left", padx=4)
        ttk.Button(top, text="Перезапустить failed jobs", command=self._actions_rerun_last).pack(side="left", padx=4)
        self.actions_tree = ttk.Treeview(f, columns=("name", "status", "conclusion", "branch", "created"), show="headings")
        for col, title in [("name", "Workflow"), ("status", "Статус"), ("conclusion", "Вывод"),
                           ("branch", "Ветка"), ("created", "Создан")]:
            self.actions_tree.heading(col, text=title)
        self.actions_tree.pack(fill="both", expand=True, padx=8, pady=4)
        self.actions_log = LogView(f, height=6)
        self.actions_log.pack(fill="x", padx=8, pady=4)

    def _actions_owner_repo(self) -> tuple[str, str] | None:
        owner, repo = self.app.config.default_owner, self.app.config.default_repo
        if not owner or not repo:
            show_error(self.root, "Не задано", "Укажите owner/repo в Настройках.")
            return None
        return owner, repo

    def _actions_list_workflows(self) -> None:
        orr = self._actions_owner_repo()
        if not orr:
            return
        owner, repo = orr
        def cb(result, error):
            if error:
                self.actions_log.append(f"✗ {error}")
            else:
                for item in self.actions_tree.get_children():
                    self.actions_tree.delete(item)
                for w in result:
                    self.actions_tree.insert("", "end", values=(
                        w.get("name", ""), w.get("state", ""), "—", "—", "—"))
                self.actions_log.append(f"Workflows: {len(result)}")
        self.app.api_request(f"Workflows {owner}/{repo}", "GET",
                             f"/repos/{owner}/{repo}/actions/workflows",
                             "Список workflow-файлов", is_safe=True, on_complete=cb)

    def _actions_list_runs(self) -> None:
        orr = self._actions_owner_repo()
        if not orr:
            return
        owner, repo = orr
        def cb(result, error):
            if error:
                self.actions_log.append(f"✗ {error}")
            else:
                for item in self.actions_tree.get_children():
                    self.actions_tree.delete(item)
                for r in result:
                    self.actions_tree.insert("", "end", values=(
                        r.get("name", ""), r.get("status", ""), r.get("conclusion") or "—",
                        r.get("head_branch", ""), (r.get("created_at") or "")[:16]))
                self.actions_log.append(f"Запусков: {len(result)}")
        self.app.api_request(f"Запуски {owner}/{repo}", "GET",
                             f"/repos/{owner}/{repo}/actions/runs",
                             "Список запусков Actions", params={"per_page": 30},
                             is_safe=True, on_complete=cb)

    def _actions_trigger(self) -> None:
        orr = self._actions_owner_repo()
        if not orr:
            return
        owner, repo = orr
        wf = ask_text(self.root, "Запуск workflow", "ID или имя workflow-файла (например, build.yml):")
        if not wf:
            return
        ref = ask_text(self.root, "Ветка", "Ветка (ref):", "main") or "main"
        def cb(result, error):
            self.actions_log.append("✓ Workflow запущен" if not error else f"✗ {error}")
        self.app.api_request(f"Запуск workflow {wf}", "POST",
                             f"/repos/{owner}/{repo}/actions/workflows/{wf}/dispatches",
                             f"Запустить workflow {wf} на ветке {ref}",
                             payload={"ref": ref}, on_complete=cb)

    def _actions_cancel_last(self) -> None:
        orr = self._actions_owner_repo()
        if not orr:
            return
        owner, repo = orr
        def cb_runs(result, error):
            if error or not result:
                self.actions_log.append(f"✗ {error or 'нет запусков'}")
                return
            run_id = result[0].get("id")
            def cb2(r2, e2):
                self.actions_log.append("✓ Запуск отменён" if not e2 else f"✗ {e2}")
            self.app.api_request(f"Отмена запуска #{run_id}", "POST",
                                 f"/repos/{owner}/{repo}/actions/runs/{run_id}/cancel",
                                 "Отменить запущенный workflow", on_complete=cb2)
        self.app.api_request(f"Последний запуск {owner}/{repo}", "GET",
                             f"/repos/{owner}/{repo}/actions/runs",
                             "Найти последний запуск для отмены", params={"per_page": 1},
                             is_safe=True, on_complete=cb_runs)

    def _actions_rerun_last(self) -> None:
        orr = self._actions_owner_repo()
        if not orr:
            return
        owner, repo = orr
        def cb_runs(result, error):
            if error or not result:
                self.actions_log.append(f"✗ {error or 'нет запусков'}")
                return
            run_id = result[0].get("id")
            def cb2(r2, e2):
                self.actions_log.append("✓ Failed jobs перезапущены" if not e2 else f"✗ {e2}")
            self.app.api_request(f"Перезапуск failed #{run_id}", "POST",
                                 f"/repos/{owner}/{repo}/actions/runs/{run_id}/rerun-failed-jobs",
                                 "Перезапустить упавшие jobs", on_complete=cb2)
        self.app.api_request(f"Последний запуск {owner}/{repo}", "GET",
                             f"/repos/{owner}/{repo}/actions/runs",
                             "Найти последний запуск", params={"per_page": 1},
                             is_safe=True, on_complete=cb_runs)

    # ── Issues / PR ────────────────────────────────────────────────────────

    def _build_issues(self) -> None:
        f = self.tab_issues
        top = ttk.Frame(f)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Button(top, text="Issues (open)", command=self._issues_list).pack(side="left", padx=4)
        ttk.Button(top, text="PR (open)", command=self._prs_list).pack(side="left", padx=4)
        ttk.Button(top, text="Создать issue…", command=self._issue_create).pack(side="left", padx=4)
        self.issues_tree = ttk.Treeview(f, columns=("num", "title", "user", "created"), show="headings")
        for col, title in [("num", "#"), ("title", "Заголовок"), ("user", "Автор"), ("created", "Создан")]:
            self.issues_tree.heading(col, text=title)
        self.issues_tree.pack(fill="both", expand=True, padx=8, pady=4)
        self.issues_log = LogView(f, height=6)
        self.issues_log.pack(fill="x", padx=8, pady=4)

    def _issues_list(self) -> None:
        orr = self._actions_owner_repo()
        if not orr:
            return
        owner, repo = orr
        def cb(result, error):
            if error:
                self.issues_log.append(f"✗ {error}")
            else:
                for item in self.issues_tree.get_children():
                    self.issues_tree.delete(item)
                for it in result:
                    self.issues_tree.insert("", "end", values=(
                        it.get("number"), it.get("title", "")[:60],
                        it.get("user", {}).get("login", ""), (it.get("created_at") or "")[:10]))
                self.issues_log.append(f"Issues: {len(result)}")
        self.app.api_request(f"Issues {owner}/{repo}", "GET",
                             f"/repos/{owner}/{repo}/issues",
                             "Открытые issues", params={"state": "open", "per_page": 50},
                             is_safe=True, on_complete=cb)

    def _prs_list(self) -> None:
        orr = self._actions_owner_repo()
        if not orr:
            return
        owner, repo = orr
        def cb(result, error):
            if error:
                self.issues_log.append(f"✗ {error}")
            else:
                for item in self.issues_tree.get_children():
                    self.issues_tree.delete(item)
                for it in result:
                    self.issues_tree.insert("", "end", values=(
                        it.get("number"), it.get("title", "")[:60],
                        it.get("user", {}).get("login", ""), (it.get("created_at") or "")[:10]))
                self.issues_log.append(f"PR: {len(result)}")
        self.app.api_request(f"PR {owner}/{repo}", "GET",
                             f"/repos/{owner}/{repo}/pulls",
                             "Открытые pull requests", params={"state": "open", "per_page": 50},
                             is_safe=True, on_complete=cb)

    def _issue_create(self) -> None:
        orr = self._actions_owner_repo()
        if not orr:
            return
        owner, repo = orr
        title = ask_text(self.root, "Новый issue", "Заголовок:")
        if not title:
            return
        body = ask_text(self.root, "Описание", "Описание (может быть пустым):", "")
        def cb(result, error):
            self.issues_log.append(f"✓ Issue #{result.get('number')}" if not error else f"✗ {error}")
        self.app.api_request(f"Создать issue: {title[:40]}", "POST",
                             f"/repos/{owner}/{repo}/issues",
                             "Создать новый issue", payload={"title": title, "body": body or ""},
                             on_complete=cb)

    # ── Секреты ────────────────────────────────────────────────────────────

    def _build_secrets(self) -> None:
        f = self.tab_secrets
        top = ttk.Frame(f)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Button(top, text="Список секретов", command=self._secrets_list).pack(side="left", padx=4)
        ttk.Button(top, text="Добавить секрет…", command=self._secret_add).pack(side="left", padx=4)
        self.secrets_tree = ttk.Treeview(f, columns=("name", "updated"), show="headings")
        self.secrets_tree.heading("name", text="Имя секрета")
        self.secrets_tree.heading("updated", text="Обновлён")
        self.secrets_tree.pack(fill="both", expand=True, padx=8, pady=4)
        self.secrets_log = LogView(f, height=6)
        self.secrets_log.pack(fill="x", padx=8, pady=4)

    def _secrets_list(self) -> None:
        orr = self._actions_owner_repo()
        if not orr:
            return
        owner, repo = orr
        def cb(result, error):
            if error:
                self.secrets_log.append(f"✗ {error}")
            else:
                for item in self.secrets_tree.get_children():
                    self.secrets_tree.delete(item)
                for s in result:
                    self.secrets_tree.insert("", "end", values=(s.get("name", ""), (s.get("updated_at") or "")[:16]))
                self.secrets_log.append(f"Секретов: {len(result)}")
        self.app.api_request(f"Секреты {owner}/{repo}", "GET",
                             f"/repos/{owner}/{repo}/actions/secrets",
                             "Список секретов репозитория", is_safe=True, on_complete=cb)

    def _secret_add(self) -> None:
        orr = self._actions_owner_repo()
        if not orr:
            return
        owner, repo = orr
        name = ask_text(self.root, "Секрет", "Имя секрета (например, DEPLOY_KEY):")
        if not name:
            return
        value = ask_text(self.root, "Значение", "Значение секрета:")
        if value is None:
            return
        def cb_key(key_result, key_error):
            if key_error:
                self.secrets_log.append(f"✗ {key_error}")
                return
            key_id = key_result.get("key_id")
            key_b64 = key_result.get("key")
            try:
                encrypted = self.app.github.encrypt_secret(key_b64, value)
            except Exception as e:
                self.secrets_log.append(f"✗ Шифрование: {e}")
                return
            def cb_put(r2, e2):
                self.secrets_log.append(f"✓ Секрет {name} сохранён" if not e2 else f"✗ {e2}")
            self.app.api_request(f"Сохранить секрет {name}", "PUT",
                                 f"/repos/{owner}/{repo}/actions/secrets/{name}",
                                 "Записать секрет репозитория (зашифрован NaCl)",
                                 payload={"encrypted_value": encrypted, "key_id": key_id},
                                 on_complete=cb_put)
        self.app.api_request("Публичный ключ секретов", "GET",
                             f"/repos/{owner}/{repo}/actions/secrets/public-key",
                             "Получить публичный ключ для шифрования секрета",
                             is_safe=True, on_complete=cb_key)

    # ── Запросы (очередь) ─────────────────────────────────────────────────

    def _build_requests(self) -> None:
        f = self.tab_requests
        top = ttk.Frame(f)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Button(top, text="Разрешить выбранный", command=self._req_approve_selected).pack(side="left", padx=4)
        ttk.Button(top, text="Отклонить выбранный", command=self._req_reject_selected).pack(side="left", padx=4)
        ttk.Button(top, text="Разрешить все безопасные", command=self._req_approve_safe).pack(side="left", padx=4)
        ttk.Button(top, text="Отклонить все ожидающие", command=self._req_reject_all).pack(side="left", padx=4)
        ttk.Button(top, text="Очистить завершённые", command=self._req_clear).pack(side="left", padx=4)
        ttk.Button(top, text="Обновить", command=self._req_refresh).pack(side="left", padx=4)
        self.req_tree = ttk.Treeview(f, columns=("id", "title", "method", "status", "age"), show="headings")
        for col, title in [("id", "ID"), ("title", "Операция"), ("method", "Метод"),
                           ("status", "Статус"), ("age", "Возраст")]:
            self.req_tree.heading(col, text=title)
        self.req_tree.pack(fill="both", expand=True, padx=8, pady=4)
        detail = ttk.LabelFrame(f, text="Детали выбранного запроса", padding=6)
        detail.pack(fill="x", padx=8, pady=4)
        self.req_detail = tk.Text(detail, height=5, wrap="word", font=("Consolas", 9))
        self.req_detail.pack(fill="x")
        self.req_tree.bind("<<TreeviewSelect>>", self._req_show_detail)
        self._req_refresh()

    def _req_refresh(self) -> None:
        for item in self.req_tree.get_children():
            self.req_tree.delete(item)
        for req in self.app.approval_queue.list_all():
            self.req_tree.insert("", "end", iid=req.id, values=(
                req.id[:8], req.title[:60], req.method, req.status.value,
                f"{req.age_seconds:.0f}с"))
        self.pending_label.configure(text=f"Запросов: {self.app.approval_queue.pending_count()} ожидают")

    def _req_selected_id(self) -> str | None:
        sel = self.req_tree.selection()
        return sel[0] if sel else None

    def _req_approve_selected(self) -> None:
        rid = self._req_selected_id()
        if rid and self.app.approval_queue.approve(rid):
            self.app.log(f"✓ Запрос разрешён: {rid[:8]}")
        self._req_refresh()

    def _req_reject_selected(self) -> None:
        rid = self._req_selected_id()
        if rid and self.app.approval_queue.reject(rid):
            self.app.log(f"✗ Запрос отклонён: {rid[:8]}")
        self._req_refresh()

    def _req_approve_safe(self) -> None:
        n = self.app.approval_queue.approve_all_safe()
        self.app.log(f"✓ Разрешено безопасных: {n}")
        self._req_refresh()

    def _req_reject_all(self) -> None:
        n = self.app.approval_queue.reject_all()
        self.app.log(f"✗ Отклонено: {n}")
        self._req_refresh()

    def _req_clear(self) -> None:
        n = self.app.approval_queue.clear_finished()
        self.app.log(f"Очищено завершённых: {n}")
        self._req_refresh()

    def _req_show_detail(self, event=None) -> None:
        rid = self._req_selected_id()
        if not rid:
            return
        req = self.app.approval_queue.get(rid)
        if not req:
            return
        self.req_detail.configure(state="normal")
        self.req_detail.delete("1.0", "end")
        text = (f"Заголовок: {req.title}\nМетод: {req.method}\nURL: {req.url}\n"
                f"Описание: {req.description}\nСтатус: {req.status.value}\n"
                f"Безопасный: {req.is_safe} · Деструктивный: {req.is_destructive}\n"
                f"Payload: {json.dumps(req.payload, ensure_ascii=False) if req.payload else '—'}\n")
        if req.error:
            text += f"Ошибка: {req.error}\n"
        if req.result is not None:
            text += f"Результат: {json.dumps(req.result, ensure_ascii=False)[:2000]}\n"
        self.req_detail.insert("end", text)
        self.req_detail.configure(state="disabled")

    # ── Логи ───────────────────────────────────────────────────────────────

    def _build_logs(self) -> None:
        f = self.tab_logs
        top = ttk.Frame(f)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Button(top, text="Очистить", command=lambda: self.main_log.clear()).pack(side="left", padx=4)
        ttk.Button(top, text="Открыть файл лога", command=self._open_log_file).pack(side="left", padx=4)
        self.main_log = LogView(f, height=20)
        self.main_log.pack(fill="both", expand=True, padx=8, pady=8)

    def _open_log_file(self) -> None:
        from ..config import get_log_path
        p = get_log_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch(exist_ok=True)
        import os
        if hasattr(os, "startfile"):
            os.startfile(str(p))
        else:
            open_url(p.as_uri())

    # ── Настройки ──────────────────────────────────────────────────────────

    def _build_settings(self) -> None:
        f = self.tab_settings
        form = ttk.LabelFrame(f, text="GitHub", padding=10)
        form.pack(fill="x", padx=8, pady=8)
        ttk.Label(form, text="Personal Access Token (PAT):").grid(row=0, column=0, sticky="w", pady=2)
        self.token_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.token_var, width=60, show="•").grid(row=0, column=1, padx=4)
        ttk.Button(form, text="Сохранить токен", command=self._settings_save_token).grid(row=0, column=2, padx=4)
        ttk.Label(form, text="Токен хранится зашифрованным (DPAPI) в %APPDATA%\\SHR\\token.dat").grid(row=1, column=0, columnspan=3, sticky="w")

        repo_form = ttk.LabelFrame(f, text="Репозиторий по умолчанию", padding=10)
        repo_form.pack(fill="x", padx=8, pady=4)
        ttk.Label(repo_form, text="Владелец (owner):").grid(row=0, column=0, sticky="w", pady=2)
        self.owner_var = tk.StringVar(value=self.app.config.default_owner)
        ttk.Entry(repo_form, textvariable=self.owner_var, width=30).grid(row=0, column=1, padx=4)
        ttk.Label(repo_form, text="Репозиторий:").grid(row=1, column=0, sticky="w", pady=2)
        self.repo_var = tk.StringVar(value=self.app.config.default_repo)
        ttk.Entry(repo_form, textvariable=self.repo_var, width=30).grid(row=1, column=1, padx=4)

        runner_form = ttk.LabelFrame(f, text="Runner", padding=10)
        runner_form.pack(fill="x", padx=8, pady=4)
        ttk.Label(runner_form, text="Имя runner'а:").grid(row=0, column=0, sticky="w", pady=2)
        self.runner_name_var = tk.StringVar(value=self.app.config.runner_name or socket.gethostname())
        ttk.Entry(runner_form, textvariable=self.runner_name_var, width=30).grid(row=0, column=1, padx=4)
        ttk.Label(runner_form, text="Метки:").grid(row=1, column=0, sticky="w", pady=2)
        self.runner_labels_var = tk.StringVar(value=self.app.config.runner_labels)
        ttk.Entry(runner_form, textvariable=self.runner_labels_var, width=30).grid(row=1, column=1, padx=4)
        ttk.Label(runner_form, text="Папка runner'а:").grid(row=2, column=0, sticky="w", pady=2)
        self.runner_dir_var = tk.StringVar(value=self.app.config.runner_dir)
        ttk.Entry(runner_form, textvariable=self.runner_dir_var, width=30).grid(row=2, column=1, padx=4)
        ttk.Button(runner_form, text="Обзор…", command=self._settings_browse_runner_dir).grid(row=2, column=2, padx=4)

        safety = ttk.LabelFrame(f, text="Безопасность запросов", padding=10)
        safety.pack(fill="x", padx=8, pady=4)
        self.auto_get_var = tk.BooleanVar(value=self.app.config.auto_approve_get)
        ttk.Checkbutton(safety, text="Авто-разрешать безопасные GET-запросы (чтение)",
                        variable=self.auto_get_var).pack(anchor="w")
        self.auto_safe_var = tk.BooleanVar(value=self.app.config.auto_approve_safe)
        ttk.Checkbutton(safety, text="Авто-разрешать все не-деструктивные запросы",
                        variable=self.auto_safe_var).pack(anchor="w")
        ttk.Label(safety, text="По умолчанию ВСЕ запросы требуют подтверждения во вкладке «Запросы».",
                  foreground="gray").pack(anchor="w")

        ttk.Button(f, text="Сохранить настройки", command=self._settings_save).pack(padx=8, pady=8)
        self.settings_log = LogView(f, height=5)
        self.settings_log.pack(fill="x", padx=8, pady=4)

    def _settings_browse_runner_dir(self) -> None:
        d = filedialog.askdirectory(title="Папка runner'а")
        if d:
            self.runner_dir_var.set(d)

    def _settings_save_token(self) -> None:
        token = self.token_var.get().strip()
        if not token:
            show_error(self.root, "Токен", "Введите токен.")
            return
        self.app.set_token(token)
        self.token_var.set("")
        self.settings_log.append("✓ Токен сохранён")
        self._refresh_dashboard()

    def _settings_save(self) -> None:
        cfg = self.app.config
        cfg.default_owner = self.owner_var.get().strip()
        cfg.default_repo = self.repo_var.get().strip()
        cfg.runner_name = self.runner_name_var.get().strip()
        cfg.runner_labels = self.runner_labels_var.get().strip()
        cfg.runner_dir = self.runner_dir_var.get().strip()
        cfg.auto_approve_get = self.auto_get_var.get()
        cfg.auto_approve_safe = self.auto_safe_var.get()
        save_config(cfg)
        self.app.refresh_auto_approve()
        self.settings_log.append("✓ Настройки сохранены")
        self.app.log("Настройки сохранены")

    # ── Цикл обновления ────────────────────────────────────────────────────

    def _refresh_loop(self) -> None:
        for msg in self.app.drain_logs():
            self.main_log.append(msg) if hasattr(self, "main_log") else None
            if hasattr(self, "dash_log"):
                self.dash_log.append(msg)
            self.statusbar.configure(text=msg)
        # Авто-обновление вкладки запросов, если видна
        try:
            current = self.notebook.select()
            if current == str(self.tab_requests):
                self._req_refresh()
        except Exception:
            pass
        self.root.after(500, self._refresh_loop)
