# API

Interactive OpenAPI documentation is served at `http://localhost:8000/docs` while the API runs. Routes live in `services/api/app/api/`.

Errors use `{"detail": "..."}`. Status codes: 401 not signed in, 403 known event but missing permission, 404 not found or not authorized, 409 rule conflict or already handled, 422 invalid input, 429 rate limited.

Implementation additions beyond the original list: `/api/config`, `/api/auth/local/*` (development only), `/api/public/registrations/{token}`, participant CSV export, and message send.
