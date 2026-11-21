# GatherAI

**Less organizing. More gathering.**

GatherAI is an AI-assisted coordination platform for group events such as retreats, community weekends, group trips and small conferences. Organizers see the real state of their event: registrations, rides, accommodation and tasks. An assistant reads that live data through scoped tools, finds problems and proposes fixes. Nothing changes until a person approves.

> Status: early-stage MVP that runs locally. Nothing is deployed, and no external service (Anthropic, Supabase, WhatsApp) is connected yet. See [Development status](#development-status).

## Features

| Area | What works today |
|---|---|
| Organizer dashboard | Metrics computed from stored records, a "Needs your attention" list, an event switcher and recent activity |
| Participants | Add, edit, search and filter participants, change registration status, view requests in detail drawers, export CSV, delete a participant's data |
| Public registration | Mobile-friendly form with consent, a honeypot, rate limits, duplicate protection and a private manage link |
| Transportation | Vehicles, drivers, seats and pickup points. Assignments are checked against capacity and conflicts, and a driver who cancels is flagged automatically |
| Accommodation | Hosts, capacity and structured restrictions. Assignments need confirmation, and private host details are masked |
| Tasks | Status, priority, assignee, due date, and a link to a participant |
| Messages | Drafts, approval before sending, and simulated delivery status |
| AI organizer assistant | Tool-calling agent with suggested prompts, structured proposals, approve and reject actions, and conversation history |
| Participant chat simulator | WhatsApp-style chat that handles registration, ride and stay requests and cancellations. It is clearly labeled as a simulator |
| Team | Event-scoped co-organizers with explicit permissions |

### How the AI stays trustworthy

1. The model reads only the current event, through permission-checked tools with Pydantic-validated arguments. It has no SQL, shell or HTTP access.
2. Write intent becomes an **action proposal**. Capacity and conflict rules are checked by deterministic code, never by the model.
3. An organizer approves or rejects. On approval the backend checks that the data hasn't changed since the proposal, revalidates it, and applies it in one transaction. It also writes an audit entry and drafts unsent notifications.
4. Stale proposals, repeated approvals and cross-event proposals fail without writing anything.
5. Participant messages are treated as untrusted input. The participant chat model only extracts fields and cannot read any records.

Without an API key the assistant runs in a **labeled rule-based demo mode** over the same tools. Live AI calls are capped per organization per day (`AI_DAILY_REQUEST_LIMIT`).

## Architecture

```
Browser: React SPA (Vite)            planned host: Vercel
   |  HTTPS + Bearer token
FastAPI API                          planned host: Render
   |-- auth/access      server-side membership and permission checks
   |-- services         deterministic validation and planning
   |-- agents + tools   Anthropic tool loop, scoped to one event
   |-- workflows        proposal approval, revalidation, execution
   |-- messaging        simulator provider now, WhatsApp Business later
Database: SQLite locally, PostgreSQL on Supabase (planned)
```

The backend is the only database client. Unauthorized events return 404 so their existence is not disclosed. Details are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

**Stack:**
- Frontend: React 19, TypeScript, Vite, Tailwind CSS 4, shadcn-style components on Radix, TanStack Query, React Hook Form, Zod and Lucide.
- Backend: Python 3.13, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic and PyJWT.
- Testing: Pytest, Vitest, React Testing Library, Playwright and axe-core.

## Repository layout

```
apps/web/            React app (pages, components, i18n, e2e tests)
services/api/        FastAPI service
  app/api/           REST routes
  app/agents/        organizer assistant and participant chat
  app/tools/         AI tool registry with permission scopes
  app/workflows/     proposal approval and execution
  app/services/      validation, planning, shared helpers
  migrations/        Alembic migrations, including RLS for PostgreSQL
  tests/             API, security and AI tests
docs/                product, architecture, security and progress documents
scripts/             Windows PowerShell developer commands
.claude/agents/      specialist subagent definitions used to build the project
.github/workflows/   CI
```

## Run locally (Windows PowerShell)

Requirements: Node.js 22+, Python 3.12+, Git.

```powershell
./scripts/setup.ps1   # once: installs dependencies, creates services/api/.env, migrates, loads demo data
./scripts/dev.ps1     # starts API and web app, each in its own window
```

- Web app: http://localhost:5173
- API docs (OpenAPI): http://localhost:8000/docs
- Demo login (fictional, local mode only): `demo@gatherai.example` / `demo-organizer-2026`

If the app says the API is not responding, run `./scripts/dev.ps1` again. It restarts only the server that stopped.

### Configuration

Copy the templates into `services/api/.env` and `apps/web/.env`; `setup.ps1` creates the API file for you. Never commit real values: `.env` files are gitignored.

| Variable | Where | Purpose |
|---|---|---|
| `APP_ENV` | API | `development`, `test` or `production` (default `production`) |
| `DATABASE_URL` | API | SQLite locally, Supabase PostgreSQL in production |
| `AUTH_MODE` | API | `local` (development only) or `supabase` |
| `LOCAL_JWT_SECRET` | API | Development signing secret, at least 32 characters, generated by setup |
| `SUPABASE_URL`, `SUPABASE_JWT_SECRET` | API | Supabase token verification |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | API | Live AI. Leave the key empty for demo mode |
| `AI_DAILY_REQUEST_LIMIT` | API | Live AI calls per organization per 24 hours (default 300) |
| `CORS_ALLOWED_ORIGINS` | API | Comma-separated frontend origins |
| `VITE_API_BASE_URL` | Web | API URL (default `http://localhost:8000`) |
| `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` | Web | Supabase Auth in the browser |

## Tests

```powershell
./scripts/test.ps1                      # API tests + lint, web build + unit tests
cd apps/web; npx playwright test        # browser journeys and accessibility (both servers must be running)
```

| Suite | Count | Covers |
|---|---|---|
| API (`services/api/tests`) | 57 | Capacity and conflict rules, registration, authorization, cross-tenant isolation, proposal approval, staleness, duplicates, prompt injection, security-review regressions |
| Web unit (`apps/web/src`) | 8 | Routing, auth guard, form validation, empty and error states |
| End to end (`apps/web/e2e`) | 5 | Sign up through AI proposal and approval, demo walkthrough, mobile layout, axe WCAG 2.2 AA on every page |

CI (GitHub Actions) runs the API and web unit suites on every push.

## Development status

| Milestone | Status |
|---|---|
| M0 Planning and architecture | Done |
| M1 Repository and local environment | Done |
| M2 Auth and database | In progress: local auth and migrations work; Supabase and PostgreSQL are not connected yet |
| M3 Core events | Done |
| M4 Participants, rides, stays, tasks | Done |
| M5 AI organizer assistant | In progress: tools and approvals are tested; the live model is not connected yet |
| M6 Participant simulator | Done |
| M7 Integration, security, accessibility | In progress: security review findings fixed and automated AA audit passing; manual screen reader pass remaining |
| M8 Demo and deployment readiness | In progress: deployment files prepared, nothing deployed |

Known limitations: one ride per participant per event; no route or travel times; Hebrew covers navigation only; co-organizers need an existing account (no invitation email yet). The full log is in [docs/PROGRESS.md](docs/PROGRESS.md).

## Documentation

[PRD](docs/PRD.md) · [Architecture](docs/ARCHITECTURE.md) · [Database](docs/DATABASE.md) · [API](docs/API.md) · [AI agent spec](docs/AI_AGENT_SPEC.md) · [Design system](docs/DESIGN_SYSTEM.md) · [Security](docs/SECURITY.md) · [Test plan](docs/TEST_PLAN.md) · [Deployment](docs/DEPLOYMENT.md) · [Decisions](docs/DECISIONS.md) · [User guide](docs/USER_GUIDE.md) · [Portfolio case study](docs/PORTFOLIO_CASE_STUDY.md)

## Data and privacy

All demo data is fictional and labeled as demo content. The project contains no real participant data. Sending real messages, deploying, or creating billable resources requires explicit approval from the project owner.

## License

Private project. All rights reserved. No license is granted.
