# Installs dependencies, applies migrations and loads fictional demo data.
$root = Split-Path $PSScriptRoot -Parent
Set-Location "$root/services/api"
if (-not (Test-Path .venv)) { python -m venv .venv }
.venv/Scripts/python -m pip install -q -e ".[dev]"
.venv/Scripts/alembic upgrade head
.venv/Scripts/python seed_demo.py
Set-Location "$root/apps/web"
npm install
npx playwright install chromium
