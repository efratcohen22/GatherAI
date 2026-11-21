# Installs dependencies, applies migrations and loads fictional demo data.
$root = Split-Path $PSScriptRoot -Parent
Set-Location "$root/services/api"
if (-not (Test-Path .venv)) { python -m venv .venv }
if (-not (Test-Path .env)) {
  # Local-only settings with a freshly generated signing secret. .env is gitignored.
  $secret = -join ((1..48) | ForEach-Object { '{0:x}' -f (Get-Random -Maximum 16) })
  (Get-Content .env.example) -replace '^LOCAL_JWT_SECRET=$', "LOCAL_JWT_SECRET=$secret" | Set-Content -Encoding utf8 .env
}
.venv/Scripts/python -m pip install -q -e ".[dev]"
.venv/Scripts/alembic upgrade head
.venv/Scripts/python seed_demo.py
Set-Location "$root/apps/web"
npm install
npx playwright install chromium
