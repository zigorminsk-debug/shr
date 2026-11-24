# Справочник API (используемые эндпоинты GitHub REST)

Все вызовы — через ApprovalQueue. Метод, путь, назначение:

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

Локальные команды runner'а: `config.cmd`, `svc.cmd`, `run.cmd` (см. README, раздел «Полный гайд»).
