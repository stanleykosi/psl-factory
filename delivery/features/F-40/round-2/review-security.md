VERDICT: PASS
REVIEWER: reviewer-security
COMMIT: 1457df1c1d4ad44327640da4efcce7d5d85dc9cd
AUTHORITY: delivery security review

## Summary
- No client or Support send from the page; Publish is a backend step and shows only after the re-read.
- Authority comes from task `you_can_act` and the response's labelled actions; holds draw no control.
- Writes use the shared client (CSRF); step writes carry one idempotency key per attempt.
- 403 and 404 reach the same no-access view. Links are validated.

## Findings
None.

## Verified
- Page sends nothing: ResponseDrawer.tsx/SupportHandoverForm.tsx only POST step and response/evidence via `api`; "published/uncertain/acknowledged" come from re-read status (`afterReplyRecorded` waits for `page.reload()`); uncertain locks all steps (useWorkspaceStep.ts).
- Authority: `responseTaskFor` and `replySteps` require `task.you_can_act === true` plus `handoverOpen(response)`; an actionless response gives an aria-disabled button, never a form; Steps.tsx change only picks a reason sentence.
- CSRF: api/client.ts middleware adds X-CSRFToken to every write. Idempotency: step key per attempt, renewed only after done/409/422; sync `writing` guard stops double press.
- Access: read/write 401/403/404 call `onAccessLost`, rendering NoAccessState (WorkItemView.tsx:260) for 403 and 404 alike; message text not echoed.
- Holds (W-3702): no step or form is drawn; no recipient or approver text in code (fixture text only).
- Links: `work_id` checked against RECORD_ID and encoded; no raw HTML rendering; gaps rendered as text.

## Notes
- Non-blocking, pre-existing: E-RESPONSE has no idempotency key (useResponse.ts header); duplicate protection is client-side only. Backend should add one when real.
- Non-blocking, pre-existing: a 403 on a step write shows "You can't take that step." rather than the no-access view; no data leaks.
- Contract mock only; nothing here is a real send (G-48-1, G-48-2 open).

## Carried forward to round 2 (impact assessment, coordinator, D-123)
Round 2 (1457df1c) changed presentation and fixtures: chip tones, Handover row style, the single "Support replied" field, phone headings, the Back target to the Delivery tab, the mock 404 for ceo on W-37xx, and a 48px attest row. No write, authority, CSRF, send or data-visibility path changed; the 404 change tightens access. checks.sh passes; e2e 59/59. Carried forward without a fresh security review.
