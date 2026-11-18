VERDICT: PASS
REVIEWER: reviewer-security
COMMIT: 9ebc7cbc98a2cedb7345180e50c1489ca0930d19
AUTHORITY: delivery security review

## Summary
- Scope: diff 552c9160..9ebc7cbc only (`InlineDecide.tsx`, `Workspace.tsx`, `tests/income-schedule.test.tsx`). Everything else carries forward from my round-1 PASS, because the decide write path, claim, CSRF and access-loss handling are unchanged.
- No path shows a decision as done after an uncertain or failed result. The outcome words are used only when `confirmed` is true. That needs all of these: the result's `work_state` is not `effect_uncertain`; the re-read item is not `effect_uncertain` and has no `reconcile`; and both re-reads succeeded (`now !== undefined && reloaded !== null`) (`InlineDecide.tsx:108-117`). Otherwise the page shows the warning "<label>: result not confirmed". A failed page reload returns `undefined` (`usePageReload.ts:42-56`), so it falls to "not confirmed".
- No second decision is sent. The settle effect only calls `page.reload()`, which is a GET, and runs once per settled object (`handled` ref). In the `done` view the component draws no buttons, only `UncertainNotice` or nothing (`InlineDecide.tsx:256`). After an uncertain write the page re-read waits for `useDecision`'s reconcile (`submit.status === 'idle'`) and never resends.
- Controls still come only from `task.you_can_act === true && claim !== null` (`InlineDecide.tsx:122`), unchanged. The revision guard in `Workspace.tsx` (`decidedShown`) only hides a notice. It grants nothing.
- No new write, link, `href`, fetch, method or `dangerouslySetInnerHTML` was added. The read-only branch now draws `LineStations` and `LineAgent`, which are display only, and it stays write-free (`writable` still needs a numeric revision). I ran `tests/income-schedule.test.tsx` (vitest): 37 of 37 passed.

## Findings
None.

## Verified
- TECH-1-1 | verified (security lens) | An unsettled 200 is worded "result not confirmed" with `role="alert"`, never as approved, returned or rejected (`InlineDecide.tsx:110-116`, `Workspace.tsx:442-448`). The new tests for `work_state: effect_uncertain` and for a re-read with a `reconcile` pass.
- TECH-1-4 | verified (security lens) | After a failure there is one page GET once the reconcile settles, and no decide resend. The test counts exactly 2 item GETs.

## Notes
- Carried forward, non-blocking, backend: E-TASK-DECIDE still has no idempotency key (see round 1). The frontend behaviour that protects against a second decision (the claim plus `expected_revision`, no automatic resend) is unchanged and is now stricter.
