# GatherAI

Less organizing. More gathering. An AI-assisted event coordination platform where every AI change is validated and approved by a person.

## Run locally (Windows PowerShell)

```powershell
./scripts/setup.ps1     # once: installs dependencies, migrates, loads fictional demo data
./scripts/dev-api.ps1   # terminal 1: http://localhost:8000
./scripts/dev-web.ps1   # terminal 2: http://localhost:5173
./scripts/test.ps1      # run tests
```

Local mode uses SQLite and development-only authentication. See `docs/DECISIONS.md`.

Documentation is in `docs/`; current status is in `docs/PROGRESS.md`.
