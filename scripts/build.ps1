# Сборка SHR.exe через PyInstaller (Windows PowerShell)
$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\.."

Write-Host "[1/3] Установка зависимостей..."
python -m pip install -r requirements.txt

Write-Host "[2/3] Сборка..."
python -m PyInstaller --noconfirm --clean --onefile --windowed `
  --name SHR `
  --add-data "src/shr;shr" `
  src/shr/__main__.py

Write-Host "[3/3] Готово: dist\SHR.exe"
