# Decisions

## D1: SQLite for local development, PostgreSQL in production
Context: the machine has no Docker or PostgreSQL, and no Supabase credentials exist yet.
Decision: SQLAlchemy models stay portable. Local runs use SQLite; production uses Supabase PostgreSQL through `DATABASE_URL`. PostgreSQL-only items (RLS, row locks) activate on that dialect.
Trade-off: RLS and row-lock concurrency cannot be exercised until Supabase is connected.

## D2: Two auth modes behind one verification path
`AUTH_MODE=local` issues development JWTs from a local credential table. `AUTH_MODE=supabase` validates Supabase access tokens. The API refuses to start with local auth when `APP_ENV=production`.

## D3: The backend is the only database client
The frontend never queries tables directly. Authorization is enforced in FastAPI; RLS is deny-by-default defense in depth for the `anon` and `authenticated` roles.

## D4: shadcn-style components written directly
shadcn/ui copies component source into a repo. The components here follow the same pattern (Radix primitives, class-variance-authority, Tailwind) and are authored directly so they bind to the GatherAI tokens.

## D5: AI runs in a labeled rule-based mode without an API key
Without `ANTHROPIC_API_KEY`, the assistant uses a keyword router over the same validated tools, and every reply is labeled as demo mode. With a key, the Anthropic tool loop runs.

## D6: Simple in-process rate limiter
Render runs one instance at MVP scale, so Redis is not justified. Limits reset on restart and do not span instances.

## D7: Duplicate registration returns 409
Registering the same email twice returns a clear conflict, which reveals that the email is registered for that event. Low friction was preferred; the endpoint is rate limited.

## D8: One active ride per participant
A participant has at most one active ride per event, enforced by a partial unique index. Separate outbound and return rides are out of MVP scope.

## D9: Structured restriction tags
Participants carry `tags`; vehicles and accommodations carry `excluded_tags`. Compatibility is deterministic and contains no religious or event-specific assumptions. Free-text restrictions remain informational.

## D10: Success green darkened to #147356
The suggested #198765 measured 4.47:1 on white and 3.93:1 on the soft green badge, below WCAG AA for small text. The axe audit flagged it. #147356 measures 5.81:1 and 5.1:1 and keeps the same hue.

## D11: Production is the default environment
`APP_ENV` defaults to `production`, so a deployment that forgets the variable cannot fall into development auth. Local auth requires `APP_ENV=development` or `test` and a `LOCAL_JWT_SECRET` of at least 32 characters, which `scripts/setup.ps1` generates into the gitignored `.env`. The chat simulator router is not mounted in production.

## D12: Daily live AI budget per organization
`AI_DAILY_REQUEST_LIMIT` (default 300) caps live model calls per organization in a rolling 24 hours, counting both organizer chat and participant extraction. Past the cap, the organizer assistant answers that the limit is reached and participant chat falls back to keyword extraction. This bounds API cost before real usage data exists.
