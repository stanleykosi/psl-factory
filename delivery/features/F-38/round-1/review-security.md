VERDICT: PASS
COMMIT: 32c97d3df9f2b6f5ae78bf523744c57ee74d83b4
REVIEWER: reviewer-security
AUTHORITY: delivery security review

## Summary
- The page never sends to the client. It sends only the person's own step, claim, decision or reconcile answer, and only to the local mock.
- "Submitted", receipts and "Record the outcome" show only after the re-read returns them. An uncertain send leaves the reconcile panel as the only control, with no resend.
- Controls come only from `you_can_act`, the steps the response sends and their `disabled_reason`. CSRF, `expected_revision` and the UUID idempotency key go through the existing shared paths, and double presses are tested.
- A 403 and a 404 on the read look the same. A 403 on the decide shows the read-only view. Links are built from encoded or validated ids. No HTML sinks were added, and no secrets or new dependencies came in.

## Findings
None.

## Verified
- Diff `b11b48d8...32c97d3d`, source part: `RfpFrame.tsx`, `WorkItemView.tsx`, `WorkItemOverview.tsx`, `InlineDecide.tsx`, `Sections.tsx`, `Workspace.tsx`, plus `mock/documents.mjs` and the fixtures. No `dangerouslySetInnerHTML`, `innerHTML`, `mailto:` or `window.open` was added. The Submission tab and the phone's "← RFP" go through `encodeURIComponent` (`RfpFrame.tsx:15`, `WorkItemView.tsx:266`). Document and work links still pass `RECORD_ID` validation (`proposals.ts`).
- The page never sends to the client. `decision.recipient` is only displayed ("Goes to …", `InlineDecide.tsx:333`) and never goes into a request. `tests/rfp-submission-mock.test.ts:164` checks that every decide body the mock accepts has no extra keys beyond the generated schema. The `sends: true` step flag does not trigger anything.
- "Submitted" and "sent" only after the re-read: covered by `tests/rfp-submission.test.tsx:431`, `:452` (a 200 whose re-read still serves the review shows no Submitted), `:560`-`:672` (uncertain, network failure, reconcile lock) and `e2e/rfp-submission.spec.ts:103`, `:157`, `:175`.
- Authority only from `you_can_act`: tested on W-3501 (prepared_by_you), W-3509 (not_your_role) and the submitted items, which show no button and send no claim (`:277`). The pm, ceo and finance_lead personas see the same controls (`:318`). A `disabled_reason` step is drawn disabled with its reason (`InlineDecide.tsx:247`).
- CSRF and idempotency: send for review sends one POST with CSRF, `expected_revision` and a UUID key, and a double press sends one (`:333`). Try again reuses the key (`:352`). Approve sends one claim and one decide (`:431`). W-3506 answers 409, then the page shows v2 and sends no second decision (`:519`). E-TASK-DECIDE has no idempotency key: this is carried as backend priority 1 in `BACKEND-HANDOFF.md` and was not introduced by this change.
- 403 and 404 look the same with nothing leaked: `:791`, and e2e `:209` shows nothing of the RFP. A 404 on the document shows "You can't open this document." with no title (`:747`).
- No recipient, approver or deadline is made up. The recipient, approver name, "submit by", the check results and the pack contents all come from fixtures. W-3509's unknown deadline reads "Unknown" (`:253`). The source-scan test finds no board strings, money, date arithmetic, size check or resend control in `src` (`:176`). There is no amount or "₦" in any fixture (mock test `:101`).
- Nothing restricted is exposed. The fixtures carry only `.example` addresses (`procurement@tamarindloans.example`), and there are no tokens, phone numbers or secrets (the "sk_" grep hits are only `task_id`). No change to `package.json` or the lockfile. Nothing was read from `.runtime/`.
- Gate: `round-1/checks.md` PASS at this head.

## Notes
- Non-blocking, mock only: `mock/documents.mjs:70` serves D-3501 v1 to every persona, while D-2901 checks the row's personas first. Real document access belongs to the backend (E-DOCUMENT), and the page treats a 403 or 404 the same either way.
- Non-blocking copy, for UX: the shared `ReconcilePanel.tsx:149` sentence ends "so the client is never invoiced twice". If W-3505 hits this branch, it is the wrong wording for a proposal submission. This is not a security exposure.
- Already known, backend: the resend refusal, the send happening exactly once, and the version `sha256` binding (G-40-1, PMO-3-1) are not built. Until then a double decide is stopped only by the claim and `expected_revision`. `build.md` and `BACKEND-HANDOFF.md` say so and claim no working send.
