# Установка self-hosted runner вручную (альтернатива GUI)
# Использование: .\install_runner.ps1 -Token <registration-token> -Name <имя> -Labels "self-hosted,windows"
param(
    [Parameter(Mandatory=$true)][string]$Token,
    [string]$Name = $env:COMPUTERNAME,
    [string]$Labels = "self-hosted,windows,x64",
    [string]$RunnerDir = "$env:ProgramFiles\GitHub Runner"
)
$ErrorActionPreference = "Stop"

Write-Host "Скачивание runner'а..."
$arch = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "arm64" } else { "x64" }
$asset = "actions-runner-win-$arch.zip"
$release = Invoke-RestMethod "https://api.github.com/repos/actions/runner/releases/latest"
$url = ($release.assets | Where-Object { $_.name -eq $asset }).browser_download_url
if (-not $url) { throw "Ассет $asset не найден" }

$zip = "$env:TEMP\$asset"
Invoke-WebRequest $url -OutFile $zip
New-Item -ItemType Directory -Force -Path $RunnerDir | Out-Null
Expand-Archive $zip -DestinationPath $RunnerDir -Force

Write-Host "Регистрация runner'а..."
Set-Location $RunnerDir
.\config.cmd --token $Token --name $Name --labels $Labels --work _work --runasservice --unattended

Write-Host "Готово. Служба запущена."
