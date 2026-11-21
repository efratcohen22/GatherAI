# Starts the API and the web app, each in its own window, skipping whichever is already running.
# Closing a window stops that server. Run ./scripts/setup.ps1 once before the first use.
$root = Split-Path $PSScriptRoot -Parent

function Test-Port([int]$port) {
  [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

if (Test-Port 8000) { Write-Host "API already running on port 8000" }
else { Start-Process powershell -ArgumentList "-NoExit", "-File", "$root/scripts/dev-api.ps1" -WindowStyle Minimized }

if (Test-Port 5173) { Write-Host "Web app already running on port 5173" }
else { Start-Process powershell -ArgumentList "-NoExit", "-File", "$root/scripts/dev-web.ps1" -WindowStyle Minimized }

for ($i = 0; $i -lt 30; $i++) {
  try {
    if ((Invoke-RestMethod http://127.0.0.1:8000/api/health -TimeoutSec 2).status -eq "ok") { break }
  } catch { }
  Start-Sleep -Seconds 1
}
if (Test-Port 8000) { Write-Host "API:     http://localhost:8000 (docs at /docs)" } else { Write-Warning "The API did not start. Check its window for errors." }
Write-Host "Web app: http://localhost:5173"
