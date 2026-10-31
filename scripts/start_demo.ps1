# One command to bring the whole demo up (Windows PowerShell). Run from anywhere:
#   powershell -ExecutionPolicy Bypass -File scripts\start_demo.ps1
# Starts: MySQL service (if stopped), MongoDB (portable copy in .tools/ or the system service), the API (8000), the web UI (3000).
# Stop everything with scripts\stop_demo.ps1
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# --- MySQL (local Windows service) ---
$svc = Get-Service | Where-Object { $_.Name -match '^MySQL' } | Select-Object -First 1
if ($svc -and $svc.Status -ne 'Running') { Start-Service $svc.Name; Write-Host "started service $($svc.Name)" }
elseif ($svc) { Write-Host "MySQL service $($svc.Name) already running" }
else { Write-Host "No local MySQL service found - start MySQL (or docker compose up -d) yourself" -ForegroundColor Yellow }

# --- MongoDB ---
if (-not (Get-NetTCPConnection -LocalPort 27017 -State Listen -ErrorAction SilentlyContinue)) {
    $mongod = Get-ChildItem "$root\.tools" -Recurse -Filter mongod.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($mongod) {
        New-Item -ItemType Directory -Force "$root\.tools\data\db" | Out-Null
        Start-Process $mongod.FullName -ArgumentList '--dbpath', "$root\.tools\data\db", '--bind_ip', '127.0.0.1', '--port', '27017', '--logpath', "$root\.tools\mongod.log" -WindowStyle Hidden
        Write-Host "started portable MongoDB"; Start-Sleep 4
    } else { Write-Host "MongoDB not found: install it or run 'docker compose up -d mongo' (Feed Lab will show errors without it)" -ForegroundColor Yellow }
} else { Write-Host "MongoDB already listening on 27017" }

# --- schema + data + collections (all idempotent; seed resets demo stock to the seeded values) ---
python scripts\bootstrap_db.py | Out-Null
python scripts\migrate.py | Out-Null
python scripts\seed.py
try { python scripts\init_mongo.py | Out-Null } catch { Write-Host "init_mongo skipped (MongoDB down?)" -ForegroundColor Yellow }

# --- API + web in their own windows so their logs are visible during the viva ---
if (-not (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process powershell -ArgumentList '-NoExit', '-Command', "cd '$root'; python -m uvicorn app.main:app --app-dir backend --port 8000"
}
if (-not (Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process powershell -ArgumentList '-NoExit', '-Command', "cd '$root\frontend'; npm run dev"
}
Start-Sleep 12
Write-Host "`nUI:      http://localhost:3000   (logins in README / docs/DEMO_SCRIPT.md)"
Write-Host "API docs: http://localhost:8000/docs (Swagger: POST /auth/login first, then try any endpoint)"
Start-Process "http://localhost:3000"
