VERDICT: PASS
COMMIT: ff48d19d80a904de760cf524166ad820107267dd
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead)

## Summary
Lean confirm of `git diff af3b958..9757462` and the merge resolution in ff48d19. TECH-5-1 is fixed: the lock now also comes from the item's own state (`Boolean(item.reconcile)`), so it holds after a reload and for any viewer. I did not rerun the gate; I rely on build.md "### Base merge" (checks.sh exit 0, Playwright 405/405).

## Findings
- TECH-5-2 | non-blocking | low | builder | `awaitingReconcile` uses `item.reconcile` alone, while the reconcile panel also needs the `reconcile` grant. A viewer without that grant on an item awaiting reconcile sees every step off with no reconcile button. That matches the invariant (reconcile before any retry) and is the safe side, so no change is needed. Make sure the "confirm first" hint copy still reads sensibly for that viewer.

## Verified
- TECH-5-1 | verified | `allLocked = pressLocked || awaitingReconcile` (useWorkspaceStep.ts:81). The server-side item state now drives the lock, so a fresh load no longer depends on client memory.
- Send-path coverage | verified | The only send path is `flow.submit` (Workspace.tsx:120). Its guard at useWorkspaceStep.ts:100 checks `allLocked`. `off()` (Workspace.tsx:111) checks `flow.allLocked`, so buttons get aria-disabled. The forms and item-level actions I grepped for in Workspace.tsx go through the same `submit`. ReconcilePanel's own E-WORK-ACTION write is a separate path and is deliberately not locked.
- Release | verified | After a successful reconcile the item reloads without `item.reconcile`, so the derived lock drops. The press-time lock still resets only when the page is opened again, as before, which is the existing behaviour.
- Tests | verified | The new reload test at 390 and 320 asserts that every `.ws-steps button` is aria-disabled. It force-clicks Approve and asserts `stepPosts()` is unchanged. It then reconciles at the bottom of the page. Before the fix, the reload left the steps enabled, so the force-click would post and the assertions would fail. The scrolled-to-bottom tests cover the padding change. I did not run them against the old code.
- CSS | verified | The padding is `--control-lg + 30px` under `.ws:has(.ws-decide--flow)`, with a matching `scroll-padding-bottom`. All of it sits inside the phone media block.
- Merge ff48d19 | verified | WorkItemOverview.tsx keeps both imports (the F-17 `WorkspacePage` and `Workspace` imports, and the F-18 `RfpOutcomeLink`). The F-17 reconcile and workspace code is intact. The other conflict was a fidelity report.json under delivery/, which is not product code.
