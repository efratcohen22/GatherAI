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
