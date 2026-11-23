# Архитектура SHR

## Компоненты

### ApprovalQueue (approval_queue.py)
Потокобезопасная очередь. Состояния запроса: PENDING → APPROVED → EXECUTING → DONE/FAILED, либо REJECTED/EXPIRED. Слушатели уведомляются об изменениях. TTL 300с для PENDING.

### RequestExecutor (app.py)
Фоновый поток (daemon). Цикл: `next_approved()` → `github.request()` → `complete()`. Ошибки `GitHubAPIError` превращаются в FAILED с сообщением.

### GitHubClient (github_client.py)
`requests.Session` с заголовками `Authorization: Bearer`, `Accept: application/vnd.github+json`. Методы: `request/get/post/put/patch/delete`, `get_all_pages` (пагинация), удобные обёртки (runners, workflows, issues, secrets, releases). Rate limit парсится из заголовков.

### SecureStore (secure_store.py)
Windows DPAPI через `ctypes.windll.crypt32.CryptProtectData/CryptUnprotectData`. Fallback для dev — XOR+base64. Файл `%APPDATA%\SHR\token.dat` (JSON: method + base64).

### RunnerManager (runner_manager.py)
- `detect_runner_asset()` — выбор ассета по `platform.system/machine`.
- `download()` — потоковое скачивание с прогрессом.
- `extract()` — ZIP/TAR.GZ.
- `configure()` — `config.cmd --token --name --labels --runasservice --unattended`.
- `service_*()` — `svc.cmd install/start/stop/uninstall`.
- `get_runner_status()` — `.runner` JSON + `sc query`.

### GUI (ui/main_window.py)
tkinter + ttk. Notebook с 9 вкладками. Обновление логов каждые 500мс через `after()`. Все кнопки создают запросы через `app.api_request()`.

## Поток данных

```
Кнопка GUI → api_request() → ApprovalQueue.submit() → [пользователь подтверждает]
→ RequestExecutor → GitHubClient.request() → callback(result, error) → GUI обновляется
```

## Зависимости

`requests`, `PyNaCl` (шифрование секретов), `psutil` (системная информация), `Pillow`/`pystray` (иконки/трей, задел), `PyInstaller` (сборка EXE).

## Тесты

`tests/test_approval_queue.py`, `test_github_client.py` (responses), `test_secure_store.py`, `test_runner_manager.py`. Запуск: `python -m pytest tests/ -v`.
