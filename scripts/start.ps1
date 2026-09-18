param([switch]$Install)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
Set-Location $taskRoot
if ($Install -or !(Test-Path '.venv\Scripts\python.exe')) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 first.' }
    & .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
    Push-Location frontend
    npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    Pop-Location
}
if (!(Test-Path '.env')) { Copy-Item '.env.example' '.env' }
$env:PYTHONPATH = 'backend'
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
$taskBackend = Start-Process -FilePath $taskPython -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput "$taskRoot\backend-output.log" -RedirectStandardError "$taskRoot\backend-error.log"
try {
    Write-Host 'Orderly: http://localhost:5173 | Customer demo / Demo123! | Admin admin / Admin123!'
    Set-Location (Join-Path $taskRoot 'frontend')
    npm.cmd run dev
} finally {
    if (!$taskBackend.HasExited) { Stop-Process -Id $taskBackend.Id }
}
