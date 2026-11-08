# Deployment

Nothing is deployed. Each step below needs founder authorization.

| Step | Service | Needed from the founder |
|---|---|---|
| 1 | GitHub | Sign in so the repository can be created and pushed (`gh` is not installed yet) |
| 2 | Supabase | Create a project; provide the connection string and URL through a secure setting |
| 3 | Anthropic | Create an API key; usage is billed per token |
| 4 | Render | Approve the `render.yaml` blueprint; set secret variables in the dashboard |
| 5 | Vercel | Import `apps/web`; set `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` |

The API refuses to start with `AUTH_MODE=local` outside development. `/api/health` is the health check. Migrations run through `alembic upgrade head`.

The PostgreSQL path has not been executed yet: migrations, RLS and row locks have only run against SQLite, where RLS is skipped. Run them against a Supabase development project first.
