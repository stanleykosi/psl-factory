VERDICT: PASS
COMMIT: 9ee65d4d689c0101591a3f94a5146c72db9545bc
REVIEWER: reviewer-security
AUTHORITY: security reviewer

## Summary
- Every start goes through the shared client, which adds `X-CSRFToken` and refuses to send a write when it has no token. A refused send is treated as signed out, not as an uncertain result.
- The idempotency key is made when a line's drawer opens and is kept only in component state. A synchronous ref guard stops a double press from sending twice. After a network error, timeout, 5xx or non-201 2xx/3xx, the form locks and "Check again" resends exactly the same body and key. A new key is made only after a definitive 409 or 422.
- No authority is worked out in the browser. The button shows only when `/me startable_lines` is not empty. Lines and `default_line` come from E-LINES, read fresh on each opening. The case and revision come only from the line or the server's option. Option lists live in component state with no module-level cache, so nothing carries over between grants or personas.
- 401 shows the signed-out state, 403/404 show "You can't start this here." plus the server message, and 409/422 keep what was typed. React renders all error text as text. The work id is URL-encoded before routing.
- No new dependencies (package.json changes only the `gen:api` path to v6). Fixtures hold only mock CSRF strings, with no real credentials or personal data.

## Findings
None.

## Notes
- Non-blocking, low, frontend/backend: `next.journey_url` from E-LINES goes straight into `<Link href>` (frontend/src/features/start-work/LineForm.tsx:115-118). React 19.3 blocks `javascript:` URLs, and the value comes from the server. Still, nothing limits it to a same-origin path, so a bad server value could link off-site. Expected: the contract declares it as a relative path (pattern `^/`), or the client renders it only when it starts with `/` and not `//`.
- Non-blocking, by design (spec PMO-0-2): after an uncertain result, Back, change line or Cancel throws away the key. Reopening the same line then makes a new key, so if the first start did land, a second start could be created. The drawer warns "If it started, it will appear in My work." Only server-side duplicate detection per case and line can close this gap. That is a decision for the backend and product, not a defect in this round.
- Out of scope (frontend only, against the contract mock): real session, CSRF validation, per-record grants and option filtering belong to the backend. The mock's order (schema 422, grant 403, idempotency replay/reuse 409, case 404, revision 409, intake 422) matches the spec. That order should be confirmed again when the real API lands.
- Uploads are not in this round. Evidence and money fields are neither rendered nor sent.
