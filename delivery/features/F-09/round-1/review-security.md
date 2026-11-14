VERDICT: PASS
COMMIT: 4efaee8910bfe52304b9f253e66d96689f03862b
REVIEWER: reviewer-security
AUTHORITY: security reviewer

## Summary
- Every write (evidence upload, claim, record response, reconcile) goes through the shared client, so `X-CSRFToken` is always sent; with no token the middleware throws before any request and the page shows the signed-out state.
- Authority comes only from the API: the entry link needs `you_can_act`, the form needs `you_can_act` plus a recordable `response` block, the reconcile panel needs `reconcile` plus `allowed_actions` containing `reconcile`. Nothing is read from `/me` roles, source text or the client, and `attested: true` is sent only after the tick.
- Uncertain effects are re-read and never resent: E-RESPONSE network/5xx does one GET (Record stays off if that also fails, and Try again only reads); a reconcile network/5xx locks the panel to "Reload the work item". No automatic retries, no resend or outbound-message call exists.
- No restricted detail leaks: no-access/404 shows `NoAccessState` with no id or title, the tab title is generic, every API string renders as escaped React text, links are built from fixed paths plus `encodeURIComponent`, and no API-supplied URL becomes an href.
- No new dependencies, no secrets; fixture addresses use `.example` and every fixture is `sample: true`.

## Findings
None.

## Verified
None (round 1).

## Notes
- Non-blocking, backend (T-RESPONSE): E-RESPONSE has no idempotency key. When an uncertain record is followed by a reload that still shows the task open, the client allows a deliberate new press, as the spec requires. In that case `expected_revision` is the only thing preventing a duplicate record. The real backend must reject a stale `expected_revision` strictly (and ideally gain an idempotency key in a later contract). `frontend/src/features/response/useResponse.ts` (the `confirm`/`settle` path).
- Non-blocking, backend: an upload that fails with a network error or 5xx is uncertain too. Try again reloads the item and uploads the same bytes, which can leave a duplicate append-only evidence row on the case. No outbound effect results, and only the evidence ids returned to the page are referenced. The backend could deduplicate on `sha256` per case. `frontend/src/features/response/useEvidenceUpload.ts` (`retry`/`run`).
- Non-blocking, backend: the spec intentionally leaves out client-side file size and type limits, so the backend must enforce size, type and filename sanitisation on E-EVIDENCE-UPLOAD. Today the whole file is read into memory as base64 in the browser.
- Mock only: in `frontend/mock/response.mjs`, `respond()` checks fields (422) before `you_can_act` (403), and the scenario header is checked before CSRF, as in the base mock. The real backend should check authority before giving per-field validation feedback. This has no effect on the frontend.
- Server error `message` strings for 403/422 are shown as text. The backend must keep them free of internal ids and other people's details (an existing pattern shared with F-03/decide).
