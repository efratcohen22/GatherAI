# GatherAI

Less organizing. More gathering. An AI-assisted event coordination platform where every AI change is validated and approved by a person.

## Run locally (Windows PowerShell)

```powershell
./scripts/setup.ps1     # once: installs dependencies, migrates, loads fictional demo data
./scripts/dev.ps1       # starts API (http://localhost:8000) and web (http://localhost:5173) in their own windows
./scripts/test.ps1      # run tests
```

If the app says the API is not responding, run `./scripts/dev.ps1` again; it restarts only what stopped.

Local mode uses SQLite and development-only authentication. See `docs/DECISIONS.md`.

Documentation is in `docs/`; current status is in `docs/PROGRESS.md`.
