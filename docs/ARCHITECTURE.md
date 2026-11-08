# Architecture

```
Browser (React SPA on Vercel)
   |  HTTPS, Bearer token
FastAPI (Render) -- auth/access -- services/validation -- workflows/proposals
   |                     |
   |                 agents + tools  --> Anthropic API
PostgreSQL (Supabase)         messaging provider (simulator now, WhatsApp later)
```

## Request path
Token verification, then `require_event` (membership and permission check; returns 404 for unauthorized events so existence is not disclosed), then a service, then a Pydantic response.

## AI path
The model only sees tool results scoped to one event. Read tools are permission-checked. Write intent becomes an `ai_action_proposals` row after deterministic validation. Execution happens only through the approval endpoint.

## Concurrency
Approval claims the proposal with a conditional `UPDATE ... WHERE approval_status='pending'`, so one request wins. A fingerprint of the affected records is compared to detect staleness, then every assignment is revalidated. PostgreSQL row locks protect capacity; partial unique indexes prevent double assignment.

## Participant path
The simulator is a state machine. The model, when present, only extracts fields from a message and has no data tools, so an injected instruction has nothing to reach. Replies are built from the participant's own record and public event fields.
