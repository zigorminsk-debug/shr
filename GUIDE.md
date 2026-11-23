# SHR — Полный и подробный гайд по программе

> **SHR (Self-Hosted Runner GUI)** — Windows-приложение для подключения компьютера к GitHub через self-hosted runner.
> Все операции к GitHub API выполняются **только через очередь запросов с подтверждением пользователя**.
> Сборка запускается **на GitHub Actions сразу после внесения изменений** (push → `build.yml` → `SHR.exe` + артефакт гайда).
> Этот файл (`GUIDE.md`) также **сохраняется в GitHub Actions как артефакт** при каждой сборке (job `guide` в `build.yml`).

---

## Оглавление

1. [Что такое SHR и зачем он нужен](#1-что-такое-shr-и-зачем-он-нужен)
2. [Требования](#2-требования)
3. [Установка](#3-установка)
4. [Создание Personal Access Token (PAT)](#4-создание-personal-access-token-pat)
5. [Первый запуск и настройка](#5-первый-запуск-и-настройка)
6. [Как работает очередь подтверждения запросов](#6-как-работает-очередь-подтверждения-запросов)
7. [Пошаговое подключение self-hosted runner'а](#7-пошаговое-подключение-self-hosted-runnera)
8. [Описание всех вкладок и функций](#8-описание-всех-вкладок-и-функций)
9. [Все возможности связки «компьютер ↔ GitHub»](#9-все-возможности-связки-компьютер--github)
10. [Что можно автоматизировать](#10-что-можно-автоматизировать)
11. [Сборка через GitHub Actions (все действия задокументированы)](#11-сборка-через-github-actions-все-действия-задокументированы)
12. [Безопасность](#12-безопасность)
13. [Архитектура программы](#13-архитектура-программы)
14. [Справочник API-эндпоинтов](#14-справочник-api-эндпоинтов)
15. [Устранение неполадок (FAQ)](#15-устранение-неполадок-faq)
16. [Чек-лист после установки](#16-чек-лист-после-установки)

---

## 1. Что такое SHR и зачем он нужен

**GitHub Actions** — система CI/CD от GitHub. По умолчанию workflow'ы выполняются на облачных машинах GitHub (`windows-latest`, `ubuntu-latest`). **Self-hosted runner** — это ваш компьютер, который сам выполняет workflow'ы GitHub Actions. Зачем это нужно:

- **Бесплатные минуты** — облачные минуты GitHub ограничены; свой ПК безлимитен.
- **Windows-специфика** — сборка .NET, PyInstaller, MSVC, доступ к локальным ресурсам.
- **Приватность** — код и артефакты не покидают ваш компьютер.
- **Контроль** — вы решаете, когда и что запускать.

**SHR** — графический интерфейс для управления этим подключением:

- Подключается к GitHub по **API-ключу (PAT)**.
- Скачивает, регистрирует и запускает runner'а на вашем ПК.
- Управляет репозиториями, Actions, issues, секретами — **но только через очередь запросов**: каждый запрос к GitHub ждёт вашего разрешения во вкладке «Запросы».
- Собирается автоматически на GitHub Actions при каждом изменении кода.

---

## 2. Требования

| Компонент | Требование |
|---|---|
| ОС | Windows 10/11 (64-bit). Код работает и на Linux/macOS для отладки, но runner'а и DPAPI — Windows-специфичны |
| Python | 3.10+ (для запуска из исходников; для готового EXE не нужен) |
| GitHub | Аккаунт + репозиторий (или организация) |
| Права PAT | `repo`, `workflow`, `admin:org` (для org-runner'ов) |
| Администратор | Нужен только для установки службы Windows (`svc.cmd install`) |
| Интернет | Доступ к `api.github.com` и `github.com` |

---

## 3. Установка

### Вариант А — готовый EXE (рекомендуется)

1. Откройте репозиторий на GitHub → вкладка **Actions**.
2. Выберите последний успешный запуск **Build SHR (Windows)**.
3. Внизу страницы — **Artifacts** → скачайте `SHR-windows-<sha>` (ZIP с `SHR.exe`).
4. Распакуйте и запустите `SHR.exe`. Python на ПК не нужен.
5. Если в репозитории есть **Releases** (тег `v*`) — скачайте EXE оттуда.

### Вариант Б — сборка локально (Windows)

```powershell
git clone https://github.com/zigorminsk-debug/shr.git
cd shr
.\scripts\build.ps1
# Результат: dist\SHR.exe
```

Или вручную:

```powershell
pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --onefile --windowed --name SHR src/shr/__main__.py
```

### Вариант В — запуск из исходников (для разработчиков)

```powershell
pip install -r requirements.txt
$env:PYTHONPATH="src"
python -m shr
```

### Проверка установки

- Окно SHR открылось, видны 9 вкладок.
- Вкладка «Дашборд» показывает hostname и ОС.
- Лог: «SHR запущен», «GUI инициализирован».

---

## 4. Создание Personal Access Token (PAT)

### Classic PAT (проще)

1. GitHub → **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)** → **Generate new token (classic)**.
2. Note: `SHR-runner` (любое имя).
3. Expiration: 90 дней или без срока (рекомендуется 90 дней с напоминанием).
4. Scopes (отметьте):
   - ✅ `repo` — репозитории, runner'ы, Actions, секреты.
   - ✅ `workflow` — запуск workflow_dispatch.
   - ✅ `admin:org` — регистрация runner'а на уровне организации.
   - ✅ `read:org` — чтение организаций.
5. **Generate token** → скопируйте `ghp_...` (показывается один раз!).

### Fine-grained PAT (строже, рекомендуется для продакшена)

1. **Personal access tokens** → **Fine-grained tokens** → **Generate new token**.
2. Repository access: только нужные репозитории.
3. Repository permissions:
   - Actions: Read and write.
   - Administration: Read and write (для runner'ов).
   - Contents: Read and write (для файлов/релиза).
   - Issues: Read and write.
   - Pull requests: Read and write.
4. Organization permissions:
   - Self-hosted runners: Read and write.

### Куда вводить токен

SHR → вкладка **Настройки** → поле «Personal Access Token» → **Сохранить токен**.

Токен хранится **зашифрованным DPAPI** в `%APPDATA%\SHR\token.dat` — расшифровать его может только текущий пользователь Windows. В `config.json` токен не сохраняется.

---

## 5. Первый запуск и настройка

1. Запустите SHR.
2. **Настройки**:
   - Вставьте PAT → «Сохранить токен» (лог: «Токен GitHub сохранён (DPAPI)»).
   - **Владелец (owner)** — ваш логин или организация.
   - **Репозиторий** — имя репозитория по умолчанию.
   - **Имя runner'а** — по умолчанию hostname ПК.
   - **Метки** — по умолчанию `self-hosted,windows,x64`.
   - **Папка runner'а** — по умолчанию `C:\Program Files\GitHub Runner`.
   - «Сохранить настройки».
3. Нажмите **«Проверить подключение»** (верхняя панель).
4. Перейдите во вкладку **Запросы** → увидите запрос «Проверка подключения (GET /user)» со статусом PENDING.
5. Нажмите **«Разрешить выбранный»** → запрос исполнится → статус DONE, верхняя панель покажет «Подключено как <login>».

> Если токен не задан, SHR предупредит и не создаст запросы до ввода PAT.

---

## 6. Как работает очередь подтверждения запросов

Это ключевая защита SHR. Схема:

```
Вы нажимаете кнопку в GUI
        │
        ▼
ApprovalRequest создаётся (PENDING) ──► виден во вкладке «Запросы»
        │
        ├── «Разрешить» ──► APPROVED ──► RequestExecutor (фоновый поток)
        │                                   │ GitHubClient.request()
        │                                   ▼
        │                              DONE (результат) / FAILED (ошибка)
        │
        └── «Отклонить» ──► REJECTED (запрос никогда не отправится в сеть)
```

### Статусы запроса

| Статус | Значение |
|---|---|
| PENDING | Ждёт вашего решения |
| APPROVED | Разрешён, ждёт исполнения |
| EXECUTING | Исполняется прямо сейчас |
| DONE | Успешно исполнен (результат в деталях) |
| FAILED | Ошибка API/сети (текст ошибки в деталях) |
| REJECTED | Отклонён вами |
| EXPIRED | Просрочен (PENDING дольше 5 минут) |

### Кнопки вкладки «Запросы»

- **Разрешить выбранный** — исполнить один запрос.
- **Отклонить выбранный** — отменить один запрос.
- **Разрешить все безопасные** — все GET-запросы разом.
- **Отклонить все ожидающие** — отменить всё.
- **Очистить завершённые** — убрать DONE/FAILED/REJECTED/EXPIRED из списка.
- **Обновить** — перечитать список.

### Детали запроса

При выборе строки внизу показываются: заголовок, метод, URL, описание, статус, флаги (безопасный/деструктивный), payload, результат или ошибка.

### Настройки авто-разрешения (Настройки → Безопасность)

- **Авто-разрешать GET** — чтение без подтверждения (выключено по умолчанию).
- **Авто-разрешать не-деструктивные** — всё, кроме DELETE (выключено по умолчанию).
- По умолчанию **ВСЕ запросы требуют подтверждения** — это и есть смысл приложения.

---

## 7. Пошаговое подключение self-hosted runner'а

### Шаг 1. Скачайте runner

Вкладка **Runner** → «Скачать runner (latest)» → подтвердите запрос во вкладке «Запросы».

Что происходит:
1. `GET /repos/actions/runner/releases/latest` — SHR узнаёт версию и ассеты.
2. Выбирается ассет по вашей ОС/архитектуре: `actions-runner-win-x64.zip` (Windows).
3. ZIP скачивается и распаковывается в папку runner'а (прогресс-бар).

Альтернатива: «Скачать по URL…» — вставьте прямую ссылку на ZIP/TAR.GZ.

### Шаг 2. Получите токен регистрации

Выберите уровень:

| Уровень | Кнопка | API |
|---|---|---|
| Репозиторий | «Получить токен регистрации (repo)» | `POST /repos/{owner}/{repo}/actions/runners/registration-token` |
| Организация | «Получить токен регистрации (org)» | `POST /orgs/{org}/actions/runners/registration-token` |
| Эфемерный (JIT) | «JIT-токен» | `POST /repos/{owner}/{repo}/actions/runners/generate-jitconfig` |

Токен действителен ~1 час. SHR покажет его в диалоге — скопируйте.

### Шаг 3. Зарегистрируйте локально

«Зарегистрировать локально…» → вставьте токен → имя → метки → SHR выполнит:

```bat
config.cmd --token <TOKEN> --name <NAME> --labels self-hosted,windows,x64 --work _work --runasservice --unattended
```

### Шаг 4. Служба Windows

| Кнопка | Команда |
|---|---|
| Установить службу | `svc.cmd install` |
| Запустить | `svc.cmd start` |
| Остановить | `svc.cmd stop` |
| Перезапустить | `svc.cmd stop` + `svc.cmd start` |
| Удалить службу | `svc.cmd uninstall` |

> Запустите SHR от администратора для установки службы. Проверка: `sc query actions.runner` в командной строке.

Альтернатива без службы: «Запуск вручную (foreground)» → `run.cmd` (runner работает, пока открыто окно SHR).

### Шаг 5. Проверка

1. Дашборд → «Список runner'ов (repo)» — ваш ПК должен быть `online`.
2. На GitHub: **Repo → Settings → Actions → Runners** — зелёный статус.
3. Запустите workflow с `runs-on: [self-hosted, windows]` — job выполнится на вашем ПК.

### Удаление runner'а (полный цикл)

1. «Остановить» службу.
2. «Удалить службу» (`svc.cmd uninstall`).
3. «Снять регистрацию» (`config.cmd remove`).
4. «Удалить runner с GitHub (по ID)» → `DELETE /repos/{owner}/{repo}/actions/runners/{id}`.

---

## 8. Описание всех вкладок и функций

### 8.1 Дашборд

- **Карточки**: токен (задан/не задан), локальный runner (установлен/нет), система (hostname, ОС, архитектура), rate limit (осталось запросов).
- **Быстрые действия**: «Обновить статус», «Список runner'ов (repo)», «Rate limit», «Открыть папку runner'а».
- **Лог** — последние операции.

### 8.2 Runner

Полный жизненный цикл runner'а (см. раздел 7): скачивание, токены (repo/org/JIT), регистрация, служба, foreground, удаление. Статусная строка показывает: установлен, имя, метки, служба (запущена/установлена/нет).

### 8.3 Репозитории

- «Мои репозитории» — `GET /user/repos`.
- «Репозитории владельца…» — `GET /users/{owner}/repos`.
- «Создать репозиторий…» — `POST /user/repos` (с выбором приватности).
- «Клонировать (git)…» — локальный `git clone` в выбранную папку.
- Таблица: имя, язык, звёзды, дата обновления.

### 8.4 Actions

- «Workflows» — `GET /repos/{o}/{r}/actions/workflows`.
- «Запуски (runs)» — `GET /repos/{o}/{r}/actions/runs`.
- «Запустить workflow…» — `POST .../workflows/{wf}/dispatches` (файл + ветка).
- «Отменить последний запуск» — `POST .../runs/{id}/cancel`.
- «Перезапустить failed jobs» — `POST .../runs/{id}/rerun-failed-jobs`.
- Таблица: workflow, статус, вывод, ветка, дата.

### 8.5 Issues / PR

- «Issues (open)» — `GET /repos/{o}/{r}/issues`.
- «PR (open)» — `GET /repos/{o}/{r}/pulls`.
- «Создать issue…» — `POST /repos/{o}/{r}/issues` (заголовок + описание).
- Таблица: номер, заголовок, автор, дата.

### 8.6 Секреты

- «Список секретов» — `GET /repos/{o}/{r}/actions/secrets`.
- «Добавить секрет…» — два запроса: `GET .../secrets/public-key` → NaCl-шифрование → `PUT .../secrets/{name}`. Значение никогда не передаётся открытым текстом.

### 8.7 Запросы

См. раздел 6. Центральная вкладка подтверждения.

### 8.8 Логи

- Общий журнал всех операций (GUI).
- «Очистить» — очистить панель.
- «Открыть файл лога» — `%APPDATA%\SHR\shr.log`.

### 8.9 Настройки

- PAT (сохраняется в DPAPI).
- Owner/repo по умолчанию.
- Имя/метки/папка runner'а.
- Авто-разрешения безопасности.

---

## 9. Все возможности связки «компьютер ↔ GitHub»

### Реализовано в SHR

| # | Возможность | Как |
|---|---|---|
| 1 | Подключение по PAT | DPAPI-токен, проверка `GET /user` |
| 2 | Скачивание runner'а | Latest release, выбор ассета по ОС/архитектуре |
| 3 | Регистрация runner'а | Repo/org/JIT токены + `config.cmd` |
| 4 | Служба Windows | `svc.cmd` install/start/stop/restart/uninstall |
| 5 | Foreground-запуск | `run.cmd` без службы |
| 6 | Список runner'ов | Repo и org уровни |
| 7 | Удаление runner'а | Локально + `DELETE` на GitHub |
| 8 | Репозитории | Список, создание, клонирование |
| 9 | Actions | Workflows, запуски, trigger, cancel, rerun |
| 10 | Issues/PR | Список, создание issue |
| 11 | Секреты | Список, NaCl-шифрование, запись |
| 12 | Rate limit | Мониторинг лимита API |
| 13 | Логи и аудит | Каждый запрос виден и записан |
| 14 | Системная информация | Hostname, ОС, CPU, RAM, диск |

### Доступно через API-клиент (можно добавить в GUI)

- Релизы: список, создание, загрузка ассетов (`GET/POST /repos/{o}/{r}/releases`).
- Runner groups (org): `GET/POST /orgs/{org}/actions/runner-groups`.
- Webhooks: `GET/POST /repos/{o}/{r}/hooks`.
- Environments: `GET /repos/{o}/{r}/environments`.
- Файлы репозитория: `GET /repos/{o}/{r}/contents/{path}`.
- Git-операции: pull/push/status/log/checkout (модуль `git_ops.py` готов).

---

## 10. Что можно автоматизировать

### 10.1 Локальный CI/CD (главное)

Workflow выполняется на вашем ПК:

```yaml
jobs:
  build:
    runs-on: [self-hosted, windows]
    steps:
      - uses: actions/checkout@v4
      - run: .\scripts\build.ps1
      - uses: actions/upload-artifact@v4
        with: { name: SHR, path: dist/SHR.exe }
```

В `build.yml` этого репозитория замените `runs-on: windows-latest` на `runs-on: [self-hosted, windows]` — и SHR будет собираться на вашем компьютере.

### 10.2 Эфемерные (JIT) runner'ы

JIT-токен → runner на один запуск → сам удаляется. Для масштабирования и безопасности (нет постоянного runner'а).

### 10.3 Массовое развёртывание

`scripts/install_runner.ps1 -Token <t> -Name <pc> -Labels "self-hosted,windows"` — установка на нескольких ПК без GUI.

### 10.4 Управление через GUI

Создание репозиториев, секретов, issue, запуск workflow — всё через очередь подтверждения, с аудитом в логе.

### 10.5 Мониторинг Actions

Статусы запусков, отмена зависших, перезапуск упавших — без браузера.

### 10.6 Идеи расширения

- Runner groups, webhooks, releases с ассетами, environments.
- Файловый браузер репозитория (contents API).
- Git pull/push из GUI.
- Tray-режим + автозапуск Windows.
- Уведомления Telegram/Discord о завершении workflow.
- Мульти-профили токенов.

---

## 11. Сборка через GitHub Actions (все действия задокументированы)

### 11.1 Файлы workflow

| Файл | Назначение |
|---|---|
| `.github/workflows/build.yml` | Сборка `SHR.exe` (Windows) + артефакт гайда + релиз по тегу |
| `.github/workflows/ci.yml` | Тесты на Ubuntu при каждом push/PR |

### 11.2 Триггеры (когда запускается сборка)

**`build.yml`**:

```yaml
on:
  push:            # любой push в любую ветку + теги v*
  pull_request:    # любой PR
  workflow_dispatch:  # ручной запуск (кнопка Actions → Run workflow)
```

**`ci.yml`**:

```yaml
on:
  push:            # любой push
  pull_request:    # любой PR
```

> Важно: workflow-файлы должны существовать на ветке, где происходит событие. Поэтому триггеры настроены **без фильтра веток** — сборка запускается и на ветке `arena/...`, и на `main`.

### 11.3 Job `build-windows` (пошагово)

1. **Checkout** — `actions/checkout@v4`: скачивание кода.
2. **Set up Python** — `actions/setup-python@v5`, Python 3.12, кэш pip.
3. **Install dependencies** — `pip install -r requirements.txt`.
4. **Run tests** — `pip install pytest responses` → `python -m pytest tests/ -v` (16 тестов).
5. **Build SHR.exe** — `PyInstaller --onefile --windowed --name SHR src/shr/__main__.py`.
6. **Upload artifact** — `actions/upload-artifact@v4`: `SHR.exe` на 90 дней, имя `SHR-windows-<sha>`.
7. **Create release on tag** — если тег `v*`: `softprops/action-gh-release@v2` публикует `SHR.exe` в Releases с автогенерацией описания.

### 11.4 Job `guide` (сохранение гайда в Actions)

1. **Checkout** — скачивание кода.
2. **Assemble guide** — сборка единого пакета гайда:
   - `README.md`, `GUIDE.md` (этот файл), `docs/*.md`, `docs/API_REFERENCE.md`.
   - Упаковка в `guide/SHR-Guide-<sha>.zip` + сводный `guide/GUIDE-ALL.md`.
3. **Upload guide artifact** — `actions/upload-artifact@v4`: артефакт `SHR-Guide-<sha>` на 365 дней.

Итог: после каждой сборки в Actions доступны **два артефакта**: `SHR-windows-<sha>` (EXE) и `SHR-Guide-<sha>` (полный гайд).

### 11.5 Как запустить сборку вручную

1. GitHub → репозиторий → **Actions** → **Build SHR (Windows)** → **Run workflow**.
2. Выберите ветку → **Run workflow**.
3. Дождитесь зелёного статуса → скачайте артефакты внизу страницы.

Или через CLI:

```bash
gh workflow run build.yml --ref <ветка>
gh run watch
```

### 11.6 Как проверить, что сборка запустилась

```bash
gh run list --limit 5
gh run view <run-id>
```

Или в браузере: **Actions** → список запусков (статус: queued → in_progress → completed).

---

## 12. Безопасность

- **PAT зашифрован DPAPI** (`CryptProtectData`) — расшифровка только текущим пользователем Windows. Файл: `%APPDATA%\SHR\token.dat` (права 0600).
- **Все API-вызовы — через очередь подтверждения.** Без разрешения пользователя запрос не отправится.
- **Деструктивные операции** (DELETE) требуют отдельного подтверждения.
- **Секреты шифруются NaCl sealed box** по публичному ключу GitHub — значение никогда не передаётся открытым текстом.
- **Логи не содержат токен** (маскируется как `ghp_…abcd`).
- Рекомендации:
  - Используйте fine-grained PAT с минимальными правами.
  - Не коммитьте токены в репозиторий.
  - Запускайте SHR от администратора только при установке службы.
  - Для публичных репозиториев предпочитайте JIT runner'ы постоянным.

---

## 13. Архитектура программы

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

Зависимости: `requests`, `PyNaCl`, `psutil`, `Pillow`, `pystray`, `PyInstaller`.

Тесты: `tests/` — 16 тестов (очередь, API-моки через `responses`, DPAPI, runner). Запуск: `python -m pytest tests/ -v`.

---

## 14. Справочник API-эндпоинтов

Все вызовы — через ApprovalQueue.

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/user` | Проверка токена |
| GET | `/rate_limit` | Лимит запросов |
| GET | `/user/repos` | Мои репозитории |
| GET | `/users/{owner}/repos` | Репозитории владельца |
| POST | `/user/repos` | Создать репозиторий |
| GET | `/repos/{o}/{r}/actions/runners` | Runner'ы репозитория |
| GET | `/orgs/{org}/actions/runners` | Runner'ы организации |
| POST | `/repos/{o}/{r}/actions/runners/registration-token` | Токен регистрации (repo) |
| POST | `/orgs/{org}/actions/runners/registration-token` | Токен регистрации (org) |
| POST | `/repos/{o}/{r}/actions/runners/generate-jitconfig` | JIT-конфиг |
| DELETE | `/repos/{o}/{r}/actions/runners/{id}` | Удалить runner |
| GET | `/repos/{o}/{r}/actions/workflows` | Workflows |
| GET | `/repos/{o}/{r}/actions/runs` | Запуски |
| POST | `/repos/{o}/{r}/actions/workflows/{wf}/dispatches` | Запуск workflow |
| POST | `/repos/{o}/{r}/actions/runs/{id}/cancel` | Отмена запуска |
| POST | `/repos/{o}/{r}/actions/runs/{id}/rerun-failed-jobs` | Перезапуск failed |
| GET | `/repos/{o}/{r}/issues` | Issues |
| POST | `/repos/{o}/{r}/issues` | Создать issue |
| GET | `/repos/{o}/{r}/pulls` | Pull requests |
| GET | `/repos/{o}/{r}/actions/secrets` | Список секретов |
| GET | `/repos/{o}/{r}/actions/secrets/public-key` | Публичный ключ |
| PUT | `/repos/{o}/{r}/actions/secrets/{name}` | Записать секрет |
| GET | `/repos/actions/runner/releases/latest` | Latest runner |

Локальные команды runner'а: `config.cmd`, `svc.cmd`, `run.cmd`.

---

## 15. Устранение неполадок (FAQ)

**Нужен ли Python на целевом ПК?** Нет — готовый `SHR.exe` (PyInstaller, onefile) самодостаточен.

**Runner не виден на GitHub?** Проверьте: служба запущена (`sc query actions.runner`), метки совпадают с `runs-on`, токен регистрации не истёк (живёт ~1 час).

**Ошибка 401 Bad credentials?** Токен неверный/истёк/отозван. Создайте новый PAT.

**Ошибка 403 rate limit?** Подождите сброса (Дашборд → Rate limit) или используйте PAT с большим лимитом.

**Ошибка 404 на runner-эндпоинтах?** У PAT нет прав `repo`/`admin:org`, или репозиторий приватный и токен без доступа.

**Служба не устанавливается?** Запустите SHR от администратора. Проверьте, что runner распакован в папку с правами на запись.

**Запросы не исполняются?** Они ждут подтверждения во вкладке «Запросы». Нажмите «Разрешить выбранный».

**Как собрать на self-hosted runner?** В `build.yml` замените `runs-on: windows-latest` на `runs-on: [self-hosted, windows]` и установите runner по разделу 7.

**Где логи?** Вкладка «Логи» + `%APPDATA%\SHR\shr.log`.

**Сборка не запустилась в Actions?** Проверьте: workflow-файл на текущей ветке, триггеры без фильтра веток, вкладка Actions → последний запуск. Для ручного запуска используйте **Run workflow** или `gh workflow run build.yml --ref <ветка>`.

---

## 16. Чек-лист после установки

- [ ] PAT создан и сохранён в SHR (Настройки).
- [ ] Подключение проверено («Подключено как <login>»).
- [ ] Owner/repo по умолчанию заданы.
- [ ] Runner скачан (вкладка Runner, статус «Установлен»).
- [ ] Токен регистрации получен и runner зарегистрирован.
- [ ] Служба запущена (`sc query actions.runner` → RUNNING).
- [ ] Runner виден на GitHub как `online`.
- [ ] Тестовый workflow с `runs-on: [self-hosted, windows]` выполнен локально.
- [ ] Артефакты `SHR-windows-<sha>` и `SHR-Guide-<sha>` доступны в Actions.

---

*SHR v1.0.0 · MIT · Документация: README.md (краткий гайд), GUIDE.md (этот файл), docs/ARCHITECTURE.md, docs/API_REFERENCE.md, docs/AUTOMATION.md*
