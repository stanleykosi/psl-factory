VERDICT: CHANGES
COMMIT: 86aefc6d97a27dcb0f7c0801c9edce099038752d
REVIEWER: reviewer-security
AUTHORITY: security reviewer

## Summary
- Writes are handled correctly. Claim and decide go through the shared client, which sets `X-CSRFToken` from memory and refuses to send when no token is held. The token is never stored in the browser, and every write carries `expected_revision`.
- Who may act comes only from `you_can_act` and `cannot_act_reason`. The page never reads `/me` roles or destinations, and the cannot-act, 403 and stale views have no note field and no Approve, Return or Reject buttons.
- 401, 403, 404, 409 and 422 all go through `ApiError.kind`, and nothing resends a decision on its own. One gap remains: when a decide's effect is uncertain and the follow-up reload also fails, the buttons come back even though nothing has been checked (SEC-1-1).
- `/__mock/reset` cannot reach a production build. The mock is a separate Node process bound to 127.0.0.1, `src/` never imports it, and the Next rewrite forwards only `/api/v1/*`.
- No new packages and no secrets. Fixtures use `.example` addresses and mock-only CSRF values. All server text is rendered as React text (no `dangerouslySetInnerHTML`), and links are built from encoded ids.

## Findings
- SEC-1-1 | blocking | medium | frontend | Uncertain decide effect re-arms the controls without reconciling. Expected (AGENTS.md "reconcile uncertain effects before retrying"; spec E-TASK-DECIDE: controls come back only "if the reloaded task is still actionable at the same revision"): when a decide gets a network or 5xx error and the single reload also fails with a network or server error, the buttons stay disabled and the copy says the item could not be checked, with a Try again that only reloads the item (a GET, never a resend). Actual: `reload()` returns the ApiError, then `setSubmit({status:'idle'})` runs and the function returns. The view stays `item` and the claim stays `ready`, so Approve, Return and Reject are enabled again on the old snapshot. The notice still says "We've reloaded this item so you can see whether it was recorded." (DecideView.tsx:25), which is not true here. A second tap is deliberate and the backend's revision check should answer 409 if the first decision landed, but that check is unproved here and the UI should not depend on it. No test covers reload failure after an uncertain decide; tests/decide.test.tsx:467 covers only a reload that succeeds. Path: frontend/src/features/decide/useDecision.ts:182-186.
- SEC-1-2 | non-blocking | low | frontend | The done view can claim an approval the server did not report. `DoneView` maps any `result.verdict` that is not one of its three keys to `'approve'` (`result.verdict in VERDICT_WORDS ? … : 'approve'`), so an unexpected echo (for example `revoke`) would show "YOU APPROVED" and "<label> is approved". The `in` operator also matches inherited keys (`constructor`), which would crash the render. Expected: use the verdict the client sent, or show a neutral "Decision recorded" when the echo does not match, and check with `Object.hasOwn`. Path: frontend/src/features/decide/DecideStates.tsx:221.

## Verified
None (round 1).

## Notes
- The mock's `POST /__mock/reset` has no CSRF check and no Origin check. Because it binds to 127.0.0.1, a web page open in the developer's browser could still post to it and clear the in-memory overrides. This affects local test state only and is in scope by design (spec: "needs no CSRF"). The mock also builds `url.pathname` with WHATWG URL, which resolves `%2e%2e` segments, so a request to `/api/v1/%2e%2e/%2e%2e/__mock/reset` on the dev proxy would probably reach reset. I did not test this, to leave the shared mock state alone. It only matters while the proxy points at the mock (dev and e2e), never with `API_ORIGIN` set to Django. Optional hardening: answer reset only when `NODE_ENV !== 'production'`, and require a mock-only header.
- The mock reads request bodies with no size limit (server.mjs request handler). This is a local tool, so it is not a real risk.
- The mock checks the revision before eligibility, so a stale request to a task you cannot act on gets 409, not 403 (build.md Departures). The 409 body says nothing about the task, so nothing leaks. The backend (T-DECIDE) should still settle the real order, and should make sure a 409 never tells an ineligible caller whether a task exists or which revision it is at.
- 403 on claim or decide reloads the item and shows the read-only view. If that reload fails with a non-access error, the page falls back to the snapshot it already had, but still shows the read-only view with no controls. That is correct.
- The 401 sign-in link carries a same-site path (`/work/<encoded id>/decide?task=<encoded>`), built with `encodeURIComponent` in SignedOutState. Whether the sign-in page safely checks `next` against open redirects is the backend's job and pre-existing.
- Real Django session, CSRF and grant enforcement are not proved by this frontend-against-mock round. They belong to T-DECIDE and FE-CONNECT-1.
