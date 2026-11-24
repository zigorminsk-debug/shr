# SHR — Self-Hosted Runner GUI для Windows

**SHR** — Windows-приложение с графическим интерфейсом для подключения компьютера к GitHub через **self-hosted runner**. Приложение подключается к GitHub по **API-ключу (Personal Access Token)**, а **все операции выполняются только через очередь запросов с подтверждением пользователя**: ни один запрос к GitHub не отправится без вашего явного разрешения (кроме опциональных авто-разрешений для безопасного чтения).

Сборка запускается **на GitHub Actions сразу после внесения изменений** (push → `build.yml` → `SHR.exe`).

---

## Оглавление

1. [Что умеет SHR](#что-умеет-shr)
2. [Быстрый старт](#быстрый-старт)
3. [Как работает подтверждение запросов](#как-работает-подтверждение-запросов)
4. [Полный гайд: подключение runner'а](#полный-гайд-подключение-runnera)
5. [Все функции и возможности](#все-функции-и-возможности)
6. [Что можно автоматизировать](#что-можно-автоматизировать)
7. [Сборка через GitHub Actions](#сборка-через-github-actions)
8. [Безопасность](#безопасность)
9. [Архитектура](#архитектура)
10. [FAQ](#faq)

---

## Что умеет SHR

| Область | Возможности |
|---|---|
| **Подключение к GitHub** | PAT-токен (DPAPI-шифрование), проверка подключения, rate limit, авто-переподключение |
| **Self-hosted runner** | Скачивание latest runner'а, регистрация (repo/org/JIT), служба Windows, foreground-запуск, удаление |
| **Репозитории** | Список, создание, клонирование через git, просмотр |
| **GitHub Actions** | Workflows, запуски, trigger workflow_dispatch, отмена, перезапуск failed jobs |
| **Issues / PR** | Список, создание issue, просмотр PR |
| **Секреты** | Список, добавление (NaCl-шифрование по публичному ключу) |
| **Очередь запросов** | Подтверждение/отклонение каждой операции, авто-разрешение GET, история |
| **Логи** | Полный журнал в GUI + файл `%APPDATA%\SHR\shr.log` |
| **Система** | CPU/RAM/диск, hostname, статус службы |

---

## Быстрый старт

### Вариант А: скачать готовый EXE (рекомендуется)

1. Откройте вкладку **Actions** в этом репозитории на GitHub.
2. Выберите последний успешный запуск **Build SHR (Windows)**.
3. Скачайте артефакт `SHR-windows-<sha>` → распакуйте → запустите `SHR.exe`.
4. Или поставьте тег `v1.0.0` — EXE попадёт в **Releases**.

### Вариант Б: собрать локально (Windows)

```powershell
git clone https://github.com/<owner>/shr.git
cd shr
.\scripts\build.ps1
# → dist\SHR.exe
```

### Вариант В: запуск из исходников

```powershell
pip install -r requirements.txt
python -m shr
# или: PYTHONPATH=src python -m shr
```

### Первый запуск

1. Вкладка **Настройки** → вставьте **Personal Access Token** → «Сохранить токен».
2. Укажите **owner** и **repo** по умолчанию.
3. Нажмите **«Проверить подключение»** → подтвердите запрос во вкладке **Запросы**.
4. Перейдите во вкладку **Runner** и следуйте шагам 1–3 (см. гайд ниже).

---

## Как работает подтверждение запросов

Это ключевой принцип SHR:

```
Вы нажимаете кнопку в GUI
        │
        ▼
Создаётся ApprovalRequest (PENDING) ──► вкладка «Запросы»
        │
        ├── Вы нажимаете «Разрешить» ──► APPROVED ──► фоновый поток исполняет ──► DONE/FAILED
        │
        └── Вы нажимаете «Отклонить» ──► REJECTED (запрос никогда не отправится)
```

- **Все** операции (GET, POST, PUT, DELETE) сначала попадают в очередь.
- Вкладка **Запросы** показывает: заголовок, метод, статус, возраст, детали (URL, payload, результат/ошибка).
- Кнопки: «Разрешить выбранный», «Отклонить выбранный», «Разрешить все безопасные», «Отклонить все», «Очистить завершённые».
- Настройки безопасности:
  - **Авто-разрешать GET** — безопасное чтение без подтверждения (выключено по умолчанию).
  - **Авто-разрешать не-деструктивные** — всё, кроме DELETE (выключено по умолчанию).
  - Деструктивные операции (DELETE) всегда требуют подтверждения, если включено `confirm_destructive`.
- Запросы истекают через 5 минут (статус EXPIRED).

---

## Полный гайд: подключение runner'а

### Шаг 0. Создайте Personal Access Token

1. GitHub → **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)** → **Generate new token (classic)**.
2. Права (scopes):
   - `repo` — полный доступ к репозиториям (нужен для runner'ов, Actions, секретов).
   - `workflow` — запуск workflow_dispatch.
   - `admin:org` — если регистрируете runner на уровне организации.
   - `read:org` — чтение организаций.
3. Скопируйте токен (`ghp_...`) и вставьте в SHR → **Настройки** → «Сохранить токен».

> Для fine-grained PAT: Repository permissions → Actions (read/write), Administration (read/write); Organization permissions → Self-hosted runners (read/write).

### Шаг 1. Скачайте runner

Вкладка **Runner** → «Скачать runner (latest)» → подтвердите запрос → дождитесь распаковки в `C:\Program Files\GitHub Runner` (или в папку из настроек).

Что происходит под капотом:
- `GET /repos/actions/runner/releases/latest` → выбор ассета по ОС/архитектуре (`actions-runner-win-x64.zip`).
- Скачивание ZIP, распаковка в папку runner'а.

### Шаг 2. Получите токен регистрации

- **Repo-уровень** (один репозиторий): «Получить токен регистрации (repo)» → `POST /repos/{owner}/{repo}/actions/runners/registration-token`.
- **Org-уровень** (вся организация): «Получить токен регистрации (org)» → `POST /orgs/{org}/actions/runners/registration-token`.
- **JIT (эфемерный)**: «JIT-токен» → `POST /repos/{owner}/{repo}/actions/runners/generate-jitconfig` — runner живёт один запуск.

Токен действителен ~1 час. SHR покажет его в диалоге — скопируйте.

### Шаг 3. Зарегистрируйте локально

«Зарегистрировать локально…» → вставьте токен → имя (по умолчанию hostname) → метки (`self-hosted,windows,x64`) → SHR выполнит:

```bat
config.cmd --token <TOKEN> --name <NAME> --labels self-hosted,windows,x64 --work _work --runasservice --unattended
```

### Шаг 4. Служба Windows

- «Установить службу» → `svc.cmd install`
- «Запустить» → `svc.cmd start`
- Проверка: `sc query actions.runner` или статус во вкладке Runner.

> Для установки службы запустите SHR от администратора. Альтернатива — «Запуск вручную (foreground)» без службы.

### Шаг 5. Проверка

- Дашборд → «Список runner'ов (repo)» — ваш компьютер должен быть `online`.
- На GitHub: **Repo → Settings → Actions → Runners** — зелёный статус.
- Запустите workflow с `runs-on: [self-hosted, windows]` — job выполнится на вашем ПК.

### Удаление runner'а

1. «Остановить» службу → «Удалить службу» (`svc.cmd uninstall`).
2. «Снять регистрацию» (`config.cmd remove`).
3. На GitHub: «Удалить runner с GitHub (по ID)» → `DELETE /repos/{owner}/{repo}/actions/runners/{id}`.

---

## Все функции и возможности

### Дашборд
- Карточки: токен, локальный runner, система, rate limit.
- Быстрые действия: обновление статуса, список runner'ов, rate limit, открыть папку runner'а.
- Общий лог операций.

### Runner (полный жизненный цикл)
| Функция | API / Команда |
|---|---|
| Скачать latest | `GET /repos/actions/runner/releases/latest` |
| Скачать по URL | Прямое скачивание ZIP/TAR.GZ |
| Токен регистрации (repo) | `POST /repos/{o}/{r}/actions/runners/registration-token` |
| Токен регистрации (org) | `POST /orgs/{org}/actions/runners/registration-token` |
| JIT-конфиг | `POST /repos/{o}/{r}/actions/runners/generate-jitconfig` |
| Регистрация | `config.cmd --token ... --runasservice` |
| Служба install/start/stop/restart/uninstall | `svc.cmd <action>` |
| Foreground-запуск | `run.cmd` |
| Снятие регистрации | `config.cmd remove` |
| Удаление с GitHub | `DELETE /repos/{o}/{r}/actions/runners/{id}` |
| Список runner'ов | `GET /repos/{o}/{r}/actions/runners`, `GET /orgs/{org}/actions/runners` |

### Репозитории
- Список моих / по владельцу (`GET /user/repos`, `GET /users/{owner}/repos`).
- Создание (`POST /user/repos`).
- Клонирование через локальный `git clone` (с выбором папки).

### Actions
- Список workflows (`GET /repos/{o}/{r}/actions/workflows`).
- Список запусков (`GET /repos/{o}/{r}/actions/runs`).
- Запуск workflow_dispatch (`POST .../dispatches`).
- Отмена запуска (`POST .../runs/{id}/cancel`).
- Перезапуск failed jobs (`POST .../runs/{id}/rerun-failed-jobs`).

### Issues / PR
- Открытые issues и PR (`GET .../issues`, `GET .../pulls`).
- Создание issue (`POST .../issues`).

### Секреты
- Список (`GET .../actions/secrets`).
- Добавление: получение публичного ключа → NaCl-шифрование → `PUT .../actions/secrets/{name}`.

### Запросы (очередь подтверждения)
- Просмотр всех запросов, деталей, результатов.
- Разрешение/отклонение по одному, все безопасные, все ожидающие.
- Очистка завершённых, авто-обновление.

### Логи и настройки
- GUI-лог + файл `%APPDATA%\SHR\shr.log`.
- Настройки: PAT, owner/repo, имя/метки/папка runner'а, авто-разрешения.

---

## Что можно автоматизировать

### 1. CI/CD на вашем компьютере (главное)
- Workflow с `runs-on: [self-hosted, windows]` выполняется локально: сборка .NET, Python, Node, тесты, упаковка EXE/MSI.
- Пример `build.yml` уже в репозитории — каждый push собирает `SHR.exe` на `windows-latest`; замените на `self-hosted` для локальной сборки.

### 2. Эфемерные (JIT) runner'ы
- JIT-токен → runner на один запуск → сам удаляется. Идеально для масштабирования и безопасности.

### 3. Автоматическая регистрация runner'ов
- Скрипт `scripts/install_runner.ps1` — установка без GUI (для развёртывания на нескольких ПК).

### 4. Управление репозиториями и секретами из GUI
- Создание репозиториев, секретов, issue — всё через очередь подтверждения, с аудитом в логе.

### 5. Мониторинг Actions
- Просмотр статусов запусков, отмена зависших, перезапуск упавших — без браузера.

### 6. Идеи для расширения (что можно добавить)
- **Runner groups** (org): `GET/POST /orgs/{org}/actions/runner-groups`.
- **Webhooks**: `GET/POST /repos/{o}/{r}/hooks` — уведомления о push/PR.
- **Releases**: создание релизов, загрузка ассетов (`SHR.exe`) — уже частично в API-клиенте.
- **Environments / Deployments**: защита production-окружений.
- **Файловый браузер репозитория**: `GET /repos/{o}/{r}/contents/{path}`, создание/обновление файлов через API.
- **Git-операции**: pull/push/status/log/checkout (модуль `git_ops.py` готов).
- **Tray-режим**: сворачивание в трей (pystray в зависимостях), автозапуск Windows.
- **Уведомления**: Telegram/Discord о завершении workflow.
- **Мульти-профили**: несколько токенов/репозиториев.

---

## Сборка через GitHub Actions

Файл `.github/workflows/build.yml`:

```yaml
on:
  push: { branches: [main, master], tags: ["v*"] }
  pull_request: { branches: [main, master] }
  workflow_dispatch:
jobs:
  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5  # Python 3.12
      - run: pip install -r requirements.txt
      - run: python -m pytest tests/ -v
      - run: python -m PyInstaller --onefile --windowed --name SHR src/shr/__main__.py
      - uses: actions/upload-artifact@v4  # SHR.exe на 90 дней
      - uses: softprops/action-gh-release@v2  # релиз по тегу v*
```

- **Каждый push** → тесты + сборка + артефакт.
- **Тег `v*`** → GitHub Release с `SHR.exe`.
- **CI** (`.github/workflows/ci.yml`) — тесты на Ubuntu при каждом push/PR.

Локальная сборка: `scripts\build.bat` или `scripts\build.ps1`.

---

## Безопасность

- **PAT хранится зашифрованным DPAPI** (`CryptProtectData`) — расшифровка только текущим пользователем Windows. Файл: `%APPDATA%\SHR\token.dat` (права 0600).
- **Все API-вызовы — через очередь подтверждения.** Без разрешения пользователя запрос не отправится.
- **Деструктивные операции** (DELETE) требуют отдельного подтверждения.
- **Секреты шифруются NaCl sealed box** по публичному ключу GitHub — значение никогда не передаётся открытым текстом.
- **Логи** не содержат токен (маскируется как `ghp_…abcd`).
- Рекомендации: используйте fine-grained PAT с минимальными правами; не коммитьте токены; запускайте службу от администратора только при установке.

---

## Архитектура

```
src/shr/
├── __main__.py          # python -m shr
├── app.py               # SHRApp + RequestExecutor (фоновый поток)
├── config.py            # настройки, пути %APPDATA%\SHR
├── secure_store.py      # DPAPI-шифрование PAT
├── approval_queue.py    # очередь запросов с подтверждением
├── github_client.py     # REST API клиент (requests)
├── runner_manager.py    # скачивание/регистрация/служба runner'а
├── git_ops.py           # локальные git-операции
├── system_info.py       # CPU/RAM/диск/hostname
└── ui/
    ├── main_window.py   # все вкладки GUI (tkinter)
    └── widgets.py       # LogView, StatusCard, диалоги
```

Поток данных: GUI → `api_request()` → `ApprovalQueue` → (подтверждение) → `RequestExecutor` → `GitHubClient` → результат → callback в GUI.

Подробнее: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/API_REFERENCE.md](docs/API_REFERENCE.md), [docs/AUTOMATION.md](docs/AUTOMATION.md).

---

## FAQ

**Нужен ли Python на целевом ПК?** Нет — готовый `SHR.exe` (PyInstaller, onefile) самодостаточен.

**Runner не виден на GitHub?** Проверьте: служба запущена (`sc query actions.runner`), метки совпадают с `runs-on`, токен регистрации не истёк.

**Ошибка 401 Bad credentials?** Токен неверный/истёк/отозван. Создайте новый PAT.

**Ошибка 403 rate limit?** Подождите сброса (см. Дашборд → Rate limit) или используйте PAT с большим лимитом.

**Как собрать на self-hosted runner?** В `build.yml` замените `runs-on: windows-latest` на `runs-on: [self-hosted, windows]` и установите runner по гайду выше.

**Где логи?** Вкладка «Логи» + `%APPDATA%\SHR\shr.log`.

---

## Лицензия

MIT. См. `pyproject.toml`.
