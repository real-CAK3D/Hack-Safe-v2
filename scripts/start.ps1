# Start Spac3-Gh0st on Windows/dev machines. Usage: .\scripts\start.ps1 [-Port 8765]
param([int]$Port = 8765, [string]$BindHost = '127.0.0.1')
$root = Split-Path -Parent $PSScriptRoot
$env:SPAC3GHOST_HOST = $BindHost
$env:SPAC3GHOST_PORT = "$Port"
Set-Location $root
$py = if (Test-Path "$root\.venv\Scripts\python.exe") { "$root\.venv\Scripts\python.exe" } else { 'python' }
Write-Host "Spac3-Gh0st -> http://${BindHost}:$Port"
& $py -m spac3ghost.app
