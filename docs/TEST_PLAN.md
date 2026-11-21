# Test plan

Run with `./scripts/test.ps1`. Browser journeys: start both servers, then `npm run e2e` in `apps/web`.

| Layer | Location | Covers |
|---|---|---|
| API unit and integration | `services/api/tests` | Capacity, conflicts, registration, tasks, messages, authorization, proposals |
| Frontend | `apps/web/src/app.test.tsx` | Routing, auth guard, form validation, error and empty states |
| End to end | `apps/web/e2e/journey.spec.ts` | Signup through approval; demo walkthrough; mobile overflow |
| Accessibility | `apps/web/e2e/accessibility.spec.ts` | axe-core WCAG 2.0 to 2.2 A/AA on every public, organizer and registration page |
| Security regressions | `services/api/tests/test_security_review.py` | One test per finding from the M7 review |

## AI evaluation cases
| # | Case | Test |
|---|---|---|
| 1 | Event summary | `test_live_loop_runs_tool_and_returns_text` |
| 2 | People need rides | e2e journey |
| 3 | Insufficient capacity | `test_insufficient_capacity_reports_unresolved` |
| 4 | Impossible assignment | `test_impossible_assignment_creates_no_proposal` |
| 5 | Participant cancels | `test_simulator_cancellation_needs_confirmation` |
| 6 | Accommodation exceeded | `test_accommodation_capacity_and_restrictions` |
| 7 | Asking for another person's data | `test_simulator_refuses_other_people_and_injection` |
| 8 | Prompt injection | same test |
| 9 | Invalid tool arguments | `test_invalid_tool_arguments` |
| 10 | Stale proposal | `test_stale_proposal_fails_without_writing` |

These verify deterministic guarantees. Model answer quality has not been evaluated because no API key is connected. Concurrency is covered sequentially; a true parallel test requires PostgreSQL.

Accessibility: axe catches only part of WCAG. Manual passes still to do: keyboard-only walkthrough of the approval flow, VoiceOver/NVDA on the assistant log, and 200% zoom. The e2e and accessibility specs need both servers running, so they are not in CI yet.
