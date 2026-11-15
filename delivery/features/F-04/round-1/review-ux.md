VERDICT: PASS
COMMIT: 86aefc6d97a27dcb0f7c0801c9edce099038752d
REVIEWER: reviewer-ux
AUTHORITY: UX reviewer

## Summary
- Walked /work/[id]/decide on the shared build (app 3401, mock 3402) at 1440 and 390 as the mock persona Ada Okafor (Finance Lead): default (W-1201, W-1202 Unknown, W-1208), approve, reject, return-without-note, stale (W-1207, Review version 3), not-yours (W-1203), prepared-by-you (W-1204), already decided (W-1205), not-your-turn (W-1206), and not-found (W-1001/T-2001, T-9999). Mock reset before and after every state-changing flow.
- Every standard state matches the approved boards (SCR-03 default, done, stale, not-yours, own) and the spec copy. No SAMPLE DATA tag appears, per the 14 Nov decision. No sideways scroll at 390. Title is "Decision · PSL Factory" everywhere.
- Phone: mini station line shows, facts strip is hidden on default and shown on done, and the action bar is pinned with 44px-class targets. Return with no note moves focus to the Note field and shows "Add a note to return or reject." above the pinned bar, so the cause is visible. Tab order is Note, Approve, Return, Reject. Stale columns stack.
- Unknown amount reads "Unknown", never 0. Stale keeps the replaced values beside the current ones with "unchanged" / "changed". Review version 3 loads v3 with Approve v3.
- Gaps against the boards are the ones the builder listed under "Not built" (pager, "Next decision", comment box, agent sentences, preview). The spec records them as out of scope, so none is blocking.

## Findings
- UX-1-1 | non-blocking | low | frontend | Chain header reads "1 steps" for a single-step chain (W-1203, W-1204; spec says "<step_count> steps"). Expected: "1 step". Actual: ungrammatical. Fix with a plural rule in the chain header in `frontend/src/features/decide/DecisionContent.tsx`, and update the spec line.
- UX-1-2 | non-blocking | low | frontend | The already-decided view (W-1205) shows "Waiting for Finance Lead" above a chain whose only step is Approved, then "Nobody has been asked yet." Both contradict "This decision has already been made." The spec's read-only panel copy causes it. Suggest dropping "Waiting for <role>" and the Asked list when `cannot_act_reason` is `already_decided`.
- UX-1-3 | non-blocking | low | frontend | The "Add a note to return or reject." error has no `role="alert"` or `aria-describedby` link to the textarea. Focus does move to the textarea, but a screen reader may not announce the cause. Suggest linking it with `aria-describedby` and `aria-invalid`.
- UX-1-4 | non-blocking | low | backend | Mock-only: the persona is always Ada Okafor (Finance Lead), so W-1203 (not_your_role) says "This decision needs a Finance Lead" to a Finance Lead. The board's viewer is Bisi (Finance). Not a defect in the real app, but it can confuse a demo. Consider a persona switch in a later round.

## Notes
- Clearing the stale callout detail ("after the billing contact changed" on the board) has no contract field, so it is rightly omitted.
- Done eyebrow time comes from the mock's `decided_at`, so it differs from the board's 10:47 and shows today's clock. That is expected.
- The state and e2e results were taken after `/__mock/reset`, and the mock is reset again at the end of this review.
