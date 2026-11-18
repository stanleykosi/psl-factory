VERDICT: PASS
REVIEWER: reviewer-security
COMMIT: 552c91602c0dc6e3d1e089517c3cb4bc19e9fcfd
AUTHORITY: delivery security review

## Summary
- The approve, return and reject buttons appear only when the backend's `tasks[].you_can_act === true` and a claim is held. A missing task, a missing flag or a refusal reason shows the backend reason, or "This review isn't open to you here", and sends nothing. The page never reads /me, a persona, role text or `prepared_by`.
- Separation of duties appears only as the backend's `tasks[].decision.basis` text. The "reviewer not set" hold (W-2706) has `tasks: []` and no steps, so the page shows no control and names no reviewer.
- The write reuses the F-16 `useDecision` path: the global middleware adds the X-CSRFToken header, the body is `{verdict, note?, expected_revision}` from the claim, and a synchronous `writing` ref stops a double press. After an uncertain result the page reads the item again and never sends the decision again. A 401, 403 or 404 replaces the page, with no title, amount or id left on screen.
- Amounts go through the existing `moneyText` as the backend's decimal string; nothing is totalled or shortened. All backend text renders as React text, and the diff adds no `dangerouslySetInnerHTML` or raw `href`.
- I ran `tests/income-schedule.test.tsx` (vitest): 28 of 28 passed.

## Findings
None.

## Notes
- Non-blocking, contract (existing): E-TASK-DECIDE (`frontend/src/api/schema.d.ts:117-130`) carries no `idempotency_key`. Protection against a second decision is the claim plus `expected_revision`: after the first decision the revision goes up, so a second press after an uncertain result gets a 409. The only way to send again is a deliberate press after the re-read, when the task is still `you_can_act` at the claimed revision (`frontend/src/features/decide/useDecision.ts:132-136`). This change keeps that behaviour and does not weaken it. The backend must still reject a second decide at the same revision. This is unchanged since F-16.
- Non-blocking, proposal: `steps[].verdict` (`frontend/src/features/workspace/proposals.ts:70-77`) only picks which button label is offered; it gives no authority. A value the page doesn't offer (`revoke`, `post`) is not drawn, and the backend still decides whether any verdict is allowed (403/422 are shown). BACKEND-HANDOFF asks the backend to confirm who carries the verdicts.
- Links: the only new link is the `assistant` kind, which goes to the fixed path `/assistant` (`frontend/src/features/workspace/proposals.ts:30`, `Links.tsx:95`). Project-tab links are built from `RECORD_ID`-checked ids. No download or external URL is added.
- Fixtures W-2701..W-2711 are marked sample data and contain no emails, tokens, secrets or external URLs.
- The "Station N of M" phone text (`Workspace.tsx` LineStations) counts stations, not money; that is display text only.
