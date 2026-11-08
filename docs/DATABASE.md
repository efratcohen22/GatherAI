# Database

Source of truth: `services/api/app/models/models.py` and Alembic migrations.

Tables: users, local_credentials (dev only), organizations, organization_members, events, event_members, participants, registration_requests, vehicles, ride_assignments, accommodations, accommodation_assignments, event_tasks, event_messages, ai_conversations, ai_messages, ai_action_proposals, audit_logs, analytics_events.

## Key invariants
| Rule | Enforcement |
|---|---|
| Vehicle or host capacity | `validation.py`, rechecked at execution |
| One active ride per participant | Partial unique index |
| One active stay per participant | Partial unique index |
| One active registration per email in an event | Partial unique index |
| Valid status values | CHECK constraints |
| Tenant isolation | `organization_id` on events; `require_event` on every route |

## RLS
On PostgreSQL the migration enables RLS on every application table with no policies for `anon` or `authenticated`, so direct client access is denied. The API connects with a privileged server-side role.
