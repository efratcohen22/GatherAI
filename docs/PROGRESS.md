# Progress

| Milestone | Objective | Status | Evidence / remaining |
|---|---|---|---|
| M0 | Planning and architecture | Done | Docs in `docs/` |
| M1 | Repo and local environment | Done | Servers run locally |
| M2 | Auth and database | In progress | Local auth and migrations tested. Blocked: Supabase auth and PostgreSQL/RLS not exercised |
| M3 | Core events | Done | API and e2e tests |
| M4 | Participants, rides, stays, tasks | Done | API tests and UI journeys |
| M5 | AI organizer assistant | In progress | Tools, approvals, loop tested with a fake client and rule-based mode. Blocked: live Claude needs an API key |
| M6 | Participant simulator | Done | Keyword extraction tested. Claude extraction needs an API key |
| M7 | Integration, security, visual QA | In progress | Automated tests and screenshots done. Remaining: independent security review, formal accessibility audit |
| M8 | Demo and deployment readiness | In progress | Demo loads; deployment files prepared. Nothing deployed |

## External connections
None connected. GitHub, Supabase, Vercel, Render and Anthropic await founder authorization. See `DEPLOYMENT.md`.

## Known limitations
One ride per participant per event. No route times. Date inputs use the browser's time zone. Co-organizers must already have an account because there is no invitation email. Hebrew covers navigation only. Tooltip and a custom date picker are not built; native controls and titles are used.

## Resume here
Connect Anthropic, then run the driver-cancellation flow with the live model. Next, connect Supabase and run migrations against PostgreSQL.
