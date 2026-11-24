@echo off
REM Сборка SHR.exe через PyInstaller (Windows)
setlocal
cd /d %~dp0\..

echo [1/3] Установка зависимостей...
python -m pip install -r requirements.txt

echo [2/3] Сборка...
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name SHR ^
  --add-data "src/shr;shr" ^
  src/shr/__main__.py

echo [3/3] Готово: dist\SHR.exe
pause
