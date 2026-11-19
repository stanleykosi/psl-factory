VERDICT: PASS
COMMIT: 5020a86be7320090efa1b2888295f52e205e761a
REVIEWER: reviewer-security
AUTHORITY: delivery security review

## Summary
- The code change is small: `cash_forecast` is added to `scheduleLine()`, the existing `ReconcilePanel` is moved into the workspace side column on desktop, and the reconcile panel gets internal wording. No new write path, endpoint, client or dependency.
- Decide controls come only from `tasks[].you_can_act` and the returned steps, through F-33's unchanged `InlineDecide`/`useDecision`. Reconcile is still gated on `reconcile` plus `allowed_actions` including `reconcile`. CSRF comes from the shared client middleware.
- The policy holds (W-4006, W-4007) send `tasks: []`, no steps and no `required_role`, reviewer or approver name. No Decide panel is drawn.
- An uncertain delivery can't be recorded as delivered without a proof upload, and Verified comes only from the backend's re-read state. Failures never resend.
- The new fixtures contain no secrets, tokens, emails or external URLs, and every one is `sample: true`. Nothing is sent externally.

## Findings
None.

## Verified
- Round 1: there are no earlier findings to retest.
- Authority from `you_can_act` only: `Workspace.tsx`, `InlineDecide.tsx` and `proposals.ts` are unchanged apart from the `beside` placement. In the fixtures, W-4005 (`prepared_by_you`), W-4008 (`not_your_role`) and every decided task have `you_can_act: false`. W-4011 sends `revoke`/`post` verdicts, which are not drawn. No new code reads `/me`. `required_role` is fixture text ("Forecast reviewer") and is shown as returned. It grants nothing.
- The reconcile move (`Workspace.tsx:662-664`, `:774-776`; `WorkItemOverview.tsx:740`): `reconcileBeside` is the inverse of the overview's condition, both use the same `useIsPhone`, and the read-only and writable Workspace branches are exclusive. So exactly one `ReconcilePanel` mounts and there is no double-POST path. The panel keeps its own gate (`ReconcilePanel.tsx:34-36`) and the synchronous `writing` ref.
- CSRF and idempotency: decide and claim go through F-16 `useDecision` with `expected_revision`. Reconcile goes through `workAction` with `expected_revision` and `case_revision`, and CSRF comes from `src/api/client.ts:18-22`. The mock refuses a stale revision with 409 and a missing grant with 403 (`mock/response.mjs:200-202`, `mock/server.mjs:171-172`).
- 403 and 404: a read returns the same not-open view (cash-forecast.test.tsx:613-630). A 404 on reconcile gives NoAccessState. A 403 on reconcile shows the backend's message, which is existing F-17 behaviour.
- Uncertain-delivery record: "It arrived" needs `evidence_id` (UI `ready` check; the mock gives 422 without an issued id). 500, network failure and timeout show "We couldn't confirm your answer…" and offer only a manual reload. Delivered or verified state comes only from the backend's sidecar re-read. W-4003 `reconcile.resend` is absent, so no resend control is drawn.
- Secrets and external effects: grepping the fixtures for http(s) URLs, emails, `token`, `secret`, `password`, `api_key` and `Bearer` finds nothing. The `BACKEND-HANDOFF.md` addition is questions only. `server.mjs`, `response.mjs` and `api/**` are unchanged. I did not read `.runtime/demo-access.txt`.
- Injection: the new strings are JSX text. No `dangerouslySetInnerHTML` was added in the workspace, response or work-item features.

## Notes
- E-TASK-DECIDE has no idempotency key. This is existing behaviour (F-33 PMO-3-1, F-42) and is already a backend question in BACKEND-HANDOFF. A replay is stopped only by the claim and `expected_revision`, so the real backend must refuse a second decide at the same revision. Non-blocking for this mock build.
- Reconcile authority comes from `allowed_actions`, not from a task's `you_can_act`. This is by spec and existing F-17 design. The backend must enforce per-record authority on E-WORK-ACTION.
- `InlineDecide` shows "Forecast v1 is approved" after any decide 200, even if the re-read still says AWAITING (build.md note 2). The status tag stays truthful. This is existing F-33 behaviour and non-blocking, but worth tightening so a success message follows the re-read.
- On desktop, `ReconcilePanel`'s `<aside>` is nested inside `.ws-side`'s `<aside>`. This is not a security issue; it is for the UX/a11y lens.

## Carried forward to round 2 (impact assessment)
Round 2 (5020a86b) changed presentation only: the verified strip, the facts tags, the phone order, the disabled-reason text, and technical tidy-ups (TECH-1-2..4). No write, authority, CSRF or data-visibility path changed; the round-2 technical review re-checks the shared Sections.tsx change. Carried forward by the coordinator on 19 Nov, without a fresh security review.
