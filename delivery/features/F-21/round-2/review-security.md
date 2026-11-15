VERDICT: PASS
COMMIT: 798c17f8b0b30f6aabf94dc0ff621a901b6df7e4
REVIEWER: reviewer-security
AUTHORITY: delegated security review

## Findings
none

## Scope
Lean re-review of 0036fe0a..798c17f8 (7 files): Workspace.tsx (one attribute), workspace.css (one rule), fixtures W-2201..W-2204, weekly.test.tsx. Read round-2/build.md. Round-1 PASS carried forward for everything else (impact assessment below).

## Send path checks
- **No send without a press.** The change adds `data-form-open` to the Decide section when `open.token` starts with `ws:`; the CSS hides that section with `display: none` in the phone media query only. Nothing new submits, auto-opens or auto-confirms; no handler changed. The step forms are rendered after the Decide section (`workspaceSteps.map((s) => form(...))`), not inside it, so hiding the bar never hides the open form or its Cancel. Submitting still needs the person's press on the form's own submit.
- **No double send.** Hiding the bar removes a second visible Send trigger on phones; it adds none. The request path, the idempotency key, the revision and CSRF are unchanged. The Send test still pins one POST.
- **Uncertain-send lock not bypassed.** `flow.allLocked`, the `confirmFirst` hints and the `ws-decide--flow` class are untouched. While locked, only the reconcile step can open, and opening it shows the reconcile form itself. Closing any form clears `open` and the bar comes back.
- **Reconcile not hidden.** The bar hides only while a `ws:` form is open, which is a form the person opened. The reconcile entry point shows whenever no such form is open. Desktop is unaffected.

## Cites change
Leaving out untouched `*_cites` keys sends fewer fields. The new test pins that no empty list is sent, so a save cannot quietly wipe saved cites. The new help text claims "omitted = keep". The server must hold that, and must scope cites to the actor, case and week. Both are already tracked as SEC-1-1/SEC-1-2 and TECH-1-x backend notes, and are not made worse here.

## Fixtures
These edits only remove display fields (byline, version, subtitle) and add `cite_label` strings. The data is sample data: no secrets, tokens, real emails or new identifiers beyond the references the boards already draw. "MIN-0141" is a label only; the cited value stays MTG-0140, which is a data-consistency question for the backend/PMO, not exposure.

## Carried forward (impact assessment)
Access control, input handling, XSS, data exposure, dependencies and secrets: unaffected by this diff, because no new endpoints, renderers, packages or request fields were added. Round-1 notes SEC-1-1 and SEC-1-2 (server-side duplicate-send guard, cite scoping) stay open as non-blocking backend notes.

## Notes
- Non-blocking: the "saved cites stay" hint depends on the server treating an omitted field as "keep". The backend handoff should confirm this before go-live.
