VERDICT: PASS
COMMIT: d9cd1d2e011106564b113229ce15100497d81ca7
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead)

## Summary
- TECH-2-1 is fixed: usePageReload ignores a read that lands after the id changed, in both the success and the error path.
- The new test starts a reload on W-2001, rerenders to W-2002, then releases the W-2001 response and expects `fresh` to be null. On the old code `fresh` would be set after the reset, so the test fails there.
- The phone Decide bar, scroll and notice changes touch no write path: no change to useWorkspaceStep, the request payloads or the step gating (`off`, locks, pending).
- Both changed assertions are justified and not weakened.

## Findings
None.

## Verified
- TECH-2-1 | verified | usePageReload.ts adds a `current` ref set in an effect, with the guard before `setFresh`/`setRefreshFailed`/`setLost` in both try and catch. The test "a read that lands after the id changed" in workspace-step.test.tsx covers it. checks.md shows the gate passed.
- Decide bar and scroll | verified | Workspace.tsx adds only a ResizeObserver that sets `--ws-bar-h`, a `scrollIntoView` for a failure notice and a wrapper div. StepForm.tsx changes only the submit button's class, so danger stays red and the button is not disabled differently. The CSS changes hide nothing interactive (the only `display: none` is for the empty live region and the checklist marks).
- Changed assertion, suggestions text | verified | "Suggested by Tola" and "RFP p.6" now show once on purpose (UI-2-6). The new test checks that the ref, the answer box and the source each appear once. Content is not lost: the reference and answer text are still asserted.
- Changed assertion, checklist marks | verified | Marks were removed by the design engineer's D-63 answer. The test now asserts they are absent and keeps the status-word assertions in the same test.

## Notes
- TECH-2-2 (a manual retry sends the reloaded revision; it needs a backend answer on idempotency before a real-API cutover) is carried forward unchanged and is not in this diff.
- The `current` ref updates in an effect, so a reload fired in the same render pass as an id change could still use the old value. That case is not reachable from the page.
