# Автоматизация: что можно делать со связкой ПК ↔ GitHub

## 1. Локальный CI/CD (self-hosted runner)
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
Плюсы: бесплатные минуты, доступ к локальным ресурсам, Windows-специфика.

## 2. Эфемерные runner'ы (JIT)
JIT-токен → `config.cmd` с JIT-конфигом → один job → автоматическое удаление. Масштабирование без постоянного runner'а.

## 3. Массовое развёртывание
`scripts/install_runner.ps1 -Token <t> -Name <pc> -Labels "self-hosted,windows"` на нескольких машинах. Токен регистрации — через SHR (очередь подтверждения).

## 4. Управление через API (всё доступно в SHR)
- Репозитории: создание, список, клонирование.
- Actions: trigger, cancel, rerun.
- Issues/PR: список, создание.
- Секреты: NaCl-шифрование, PUT.
- Runner'ы: регистрация, удаление, список.

## 5. Расширения (roadmap)
- Runner groups, webhooks, releases с ассетами, environments.
- Файловый браузер репозитория (contents API).
- Git pull/push из GUI (git_ops.py готов).
- Tray + автозапуск, уведомления Telegram/Discord.
- Мульти-профили токенов.

## 6. Безопасность автоматизации
- Fine-grained PAT с минимальными правами.
- JIT вместо постоянных runner'ов для публичных репозиториев.
- Очередь подтверждения как аудит: каждый вызов виден в логе.
