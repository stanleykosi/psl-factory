VERDICT: PASS
COMMIT: ff48d19d80a904de760cf524166ad820107267dd
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux

## Summary
Lean confirm, read only (git objects, no server, no build). Scope is `git diff f91bc63..ff48d19 -- frontend/src` for the workspace, work-item and shell files. The remaining files in that range came in with the F-18 base merge and were reviewed in F-18. No persona's task gets worse. My earlier PASS at f91bc63 stands, and the earlier non-blocking notes (UX note 1 on step-label squeeze, which the wrap fix now addresses; notes 2 and 3 unchanged) are kept by reference.

## Findings
- UX-5-1 | non-blocking | low | builder | TECH-5-2 follow-up. A viewer without the `reconcile` grant on an item awaiting reconcile sees every step off and no reconcile button, with no sentence saying who can act. Locking is correct and safe. A short hint would help, for example "Waiting for someone with reconcile access to confirm what happened." It can ship as a later follow-up and does not block the merge, because the person cannot act and the item's state panel still shows that it is waiting.

## Verified
- Phone Decide bar when the item awaits reconcile and the viewer can reconcile: the Decide panel flows (`position: static`) rather than being fixed, so it no longer sits on top of the reconcile panel's own pinned button. Bottom padding and `scroll-padding-bottom` of `--control-lg + 30px` keep the last content and Tab focus clear of that button. This is an improvement for the reconcile persona.
- Viewer without the grant: the flow class needs both all-locked and the reconcile panel, so the Decide bar stays on its normal measured-height path. Nothing is hidden behind it, and the steps are off. Not worse.
- Everyone else (no reconcile set): `allLocked` is unchanged and the layout is as reviewed at f91bc63.
- Every step is locked whenever `item.reconcile` is set, including after a reload. This matches the resend invariant and removes the way to retry before confirming. Locked steps are disabled, not hidden, so the layout is stable.
- Labels now wrap (`white-space: normal`) with 44px minimum height, which resolves my earlier 320px squeeze concern.
- F-18's "Record the outcome" is a real link styled as a secondary button. It shows only when the backend sends `rfp_outcome`, so people without the grant never see it. Its placement after the task panels causes no dead end. The outcome page title does not name the item.
- QA at ff48d19 (round-5/review-qa.md) checked these changes by touch. I agree with it and did not repeat the walk.
