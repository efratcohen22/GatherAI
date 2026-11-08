$root = Split-Path $PSScriptRoot -Parent
Set-Location "$root/services/api"
.venv/Scripts/python -m pytest -q
.venv/Scripts/ruff check app tests
Set-Location "$root/apps/web"
npm run build
npm test
