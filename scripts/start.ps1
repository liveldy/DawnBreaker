$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed' }
if (-not (Test-Path -LiteralPath 'node_modules')) { npm ci; if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed' } }
npm run build
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
Write-Host 'API: http://127.0.0.1:7779 ; web: http://127.0.0.1:7780'
$apiProcess = Start-Process -FilePath (Resolve-Path -LiteralPath '.venv\Scripts\python.exe') -ArgumentList '-m','uvicorn','server.main:app','--host','127.0.0.1','--port','7779' -WindowStyle Hidden -PassThru
try { npm run dev } finally { Stop-Process -Id $apiProcess.Id -ErrorAction SilentlyContinue }
