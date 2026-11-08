Set-Location "$(Split-Path $PSScriptRoot -Parent)/services/api"
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
