# Security and privacy

- Every event route resolves membership on the server. Unauthorized events return 404.
- Co-organizers are limited to events they are added to, cannot see participant email or phone without `manage_participants`, and cannot approve proposals by default.
- The AI has no SQL, shell or HTTP tools. Tools validate input with Pydantic and check permissions regardless of model output.
- The participant chat model only extracts fields and has no access to records.
- Spreadsheet exports neutralize formula injection.
- Passwords exist only in local development (scrypt). Production authentication is delegated to Supabase.
- Public registration is rate limited, uses a honeypot, and requires consent. Manage links are random tokens stored only as hashes.

## Data handling
Deleting a participant erases their record, assignments, requests and messages. Audit logs store identifiers and field names rather than personal values. Assistant messages are stored indefinitely today; a retention period must be chosen before launch. With a key configured, event data needed for an answer is sent to Anthropic.

## Known gaps
Rate limits are per process and reset on restart. Duplicate registration reveals that an email is registered for that event (D7). The local-mode token is held in browser storage. CSRF does not apply because requests use bearer tokens. No external penetration test has been done.

## Independent review (M7)
A read-only security review covered isolation, escalation, auth, public endpoints, the simulator, AI tools, secrets, logging and exports. It found no critical issues, and no IDOR on any nested resource. Fixed, with regressions in `services/api/tests/test_security_review.py`:

| Severity | Finding | Fix |
|---|---|---|
| High | A deployment missing `APP_ENV` fell back to development auth with a public default signing secret | D11: production default, mandatory strong local secret |
| Medium | The simulator let a default co-organizer look up names by phone and cancel participants | Requires `manage_participants`; not mounted in production |
| Medium | Participant search matched masked emails, which leaks them one character at a time | Search matches email only for `manage_participants` |
| Medium | Host addresses were visible to view-only members and in proposal labels | Address and restrictions masked without `manage_logistics`; labels use the host name only |
| Low | No issuer check on the Supabase HS256 path | Issuer enforced |
| Low | Supabase sign-in with an email owned by another account returned 500 | Returns 409; identities are never merged |
| Low | Tasks could be assigned to any user ID | Assignee must have access to the event |
| Low | Rule-based assistant crashed when a user lacked message permission | Returns an explanation |
| Low | Self-service updates could request a disabled module | Disabled modules are ignored |
| Low | CSV guard missed leading whitespace, `\|` and `%` | Extended |
| Low | A co-organizer could remove a member with more permissions | Forbidden (403) |
| Low | The manage token in the URL could leak through logs and Referer | Paths redacted in request logs, uvicorn access log disabled in production, `Referrer-Policy: no-referrer` |

Still open:
- Before launch, turn on "Confirm email" in Supabase Auth. Invitations match on email, so an unconfirmed account could otherwise claim an invite.
- The rate limiter trusts `X-Forwarded-For` from Render's proxy (`--forwarded-allow-ips '*'`). This is correct on Render only.
- The local-mode token lives in `localStorage` (development only).

Every response carries an `X-Request-ID`. Server errors show its first 8 characters as a reference, and logs record the method, the redacted path, the status and the duration, never bodies.
