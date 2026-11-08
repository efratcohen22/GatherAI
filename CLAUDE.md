# GatherAI: engineering guide

Less organizing. More gathering. AI-powered event coordination SaaS.

The founder writes no code. Report progress to the founder in Hebrew; code, comments and docs are in English.

## Layout
- `apps/web`: React, TypeScript, Vite, Tailwind, shadcn-style components
- `services/api`: FastAPI, SQLAlchemy, Alembic
- `docs/`: PRD, architecture, decisions, and `PROGRESS.md` (resume from here)
- `.claude/agents/`: specialist subagents
- `scripts/`: developer commands

## Commands (from the repo root, Windows PowerShell)
- `./scripts/setup.ps1`: install everything, migrate, load demo data
- `./scripts/dev-api.ps1`: API at http://localhost:8000 (docs at `/docs`)
- `./scripts/dev-web.ps1`: web at http://localhost:5173
- `./scripts/test.ps1`: backend and frontend tests

## Hard rules
1. All authorization is server-side. Event routes use `app.auth.access.require_event`.
2. The AI never mutates state directly. It creates proposals; a human approves; `app/workflows/proposals.py` revalidates and executes.
3. Capacity and conflict rules live in `app/services/validation.py` and are never delegated to the model.
4. Never send real external messages, deploy publicly, or create billable resources without explicit founder approval.
5. Never commit secrets. Never use real participant data; demo data is fictional.
6. Simulated behavior must be labeled as simulated in the UI.
7. Colors come from design tokens in `apps/web/src/styles/tokens.css`.
8. Never claim a test passed unless it ran. Record decisions in `docs/DECISIONS.md`.
