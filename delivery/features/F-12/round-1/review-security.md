VERDICT: PASS
COMMIT: 831b17164ca8b1200e9ff84d2d486ea0d7dc7dc5
REVIEWER: reviewer-security
AUTHORITY: security reviewer

## Summary
- The API decides whose alerts are shown. The UI sends only q/agent/unread/cursor, with no person or user id, and shows the rows exactly as returned. The mock serves each persona only its own records, and another persona's id answers 404 on mark-read.
- The masked WhatsApp number is read in one place and rendered as React text. It never goes into the PUT body, which is built only from channel, frequency, revision, events{key,whatsapp,email} and the chosen option values.
- Both writes (mark-read POST and settings PUT) go through the shared client's CSRF middleware. The mock rejects a missing token or another persona's token with 403 csrf_failed.
- Alert links are always `/work/${encodeURIComponent(work_id)}`. Hostile ids such as "/.//evil.example", "//evil", "\\evil", "https://evil", "javascript:…" and control characters all stay same-origin under /work/. No external calls, no new dependencies, no secrets.

## Findings
None.

## Verified
- Not applicable (round 1).

## Notes
- Evidence (code): `frontend/src/features/alerts/NotificationsPage.tsx:312` builds `workHref` with encodeURIComponent, and `:152-162` mark-read runs and then calls `router.push(workHref(alert))`. `frontend/src/features/alerts/model.ts:83-90` builds the query from v7 parameters only, and `:115-123` builds the PUT body with no masked_number, label, timing or note. `AlertSettingsPage.tsx:211,296` renders the number as escaped text. There is no dangerouslySetInnerHTML, window.location, storage or cookie access, and no raw fetch in `src/features/alerts/**`.
- Evidence (encoding check, run with node): every hostile work_id resolves to `http://<app>/work/<encoded>`. The one exception is ".." (and "."), which resolves to `/` (or `/work/`): same-origin, so not an open redirect. If you want to harden this further, add a unit test that pins hostile work_id values to `/work/` encoding (non-blocking).
- Evidence (live, read-only, shared mock on 4212): as pm, GET /api/v1/notifications returned only N-0101 and N-0102, and GET /api/v1/me/alert-preferences returned `+234 805 *** 1180`. Shared build `/notifications` answers 200.
- Mock seam (`frontend/mock/server.mjs:224-232`): persona is allowlisted against PERSONAS and the alerts scenario against ALERT_SCENARIOS before any fixture path is built, so a cookie cannot cause path traversal in `alerts.mjs` `read()`. The CSRF check runs before the alerts dispatch.
- On the 422/403/5xx save callouts, the UI shows the server's `message` and `code` verbatim as escaped text. The real backend (T-ALERTS) must keep these free of internals.
- The real backend must enforce what the mock only simulates: own-record filtering, the 404 on another person's id, server-side masking (the full number never leaves the server), the CSRF check on both writes, and revision checks. This work is outstanding until T-ALERTS.
- Pre-existing, mock only: `/__mock/reset` and the `X-Mock-Scenario` header take no authentication. This is acceptable for a local contract mock, but it must never ship.
