STATUS: READY
COMMIT: ff48d19d80a904de760cf524166ad820107267dd
BUILDER: builder
LANE: records only

## Fixes
- QA-5-1 | 97574624 | (reopened) the flow-mode page now keeps bottom space equal to F-09's reconcile bar (control height + 30px) and scroll-padding, so "Record and continue" is tappable at every scroll position at 390 and 320. Earlier: af3b958c | Decide bar flows (position: static, no reserved bottom padding) while every step is locked and a reconcile action exists, so F-09's fixed "Record and continue" bar is tappable
- QA-5-5 | 97574624 | every step is locked whenever the item itself has `item.reconcile` (with or without the reconcile permission), so a reload no longer unlocks Approve and send; the lock drives off(), the submit guard, the hint and ws-decide--flow; the in-memory press lock stays
- QA-5-2 | af3b958c | Decide button labels wrap on phones (white-space: normal)

## Summary
- No product code changed. The only change since round 4 (5dea11e) is `delivery/features/F-17/fidelity-exceptions.json`: every exception's `approved_by` now reads "design engineer, 15 Nov (D-65)", after the design engineer accepted the frame at its measured region scores.
- The round-4 build note (round-4/build.md) holds the last product evidence: checks.sh exit 0, e2e/workspace.spec.ts 31/31, region scores in round-4/fidelity/region-scores.txt.

## Validation
- `delivery/checks.sh` at f91bc63: exit 0 (gate round 5, attempt 1).

## Extra round (D-66)
Branch head af3b958c. Changed: Workspace.tsx (class `ws-decide--flow` when `flow.allLocked && hasReconcile`), workspace.css (phone block: flow rule, `.ws:has(.ws-decide--flow)` padding 0, labels wrap), e2e/workspace.spec.ts (new 390x844 test: Approve and send on W-2008, then click "Record and continue", expects 200). F-09 reconcile code untouched. QA-5-3 and QA-5-4 left alone. No design-fidelity run (budget).

Validation:
- `bash delivery/checks.sh`: exit 0.
- `E2E_PORT=4721 MOCK_PORT=4722 npx playwright test e2e/workspace.spec.ts e2e/response.spec.ts`: 48 passed.
- The new phone test fails on the old code ("ws-steps__buttons subtree intercepts pointer events") and passes on the new.

### Second fix (D-66)
- Lock: `useWorkspaceStep` takes `awaitingReconcile` (= `Boolean(item.reconcile)`); `allLocked` = press lock OR that. Space: `.ws:has(.ws-decide--flow)` padding-bottom and html scroll-padding-bottom = `--control-lg` + 30px. F-09 code unchanged.
- New e2e (390 and 320): press then scroll to bottom then Record and continue (200); press, reload, all steps aria-disabled, forced tap on Approve and send sends no POST, scroll to bottom, Record and continue (200). All 4 fail on af3b958 and pass now.
- `bash delivery/checks.sh` exit 0. Playwright (workspace, response, work-item, work-item-board, decide, decide-board; E2E_PORT=4721 MOCK_PORT=4722, FRAME_FIXTURES=1): 155 passed, 0 failed. Design-fidelity not run (per instruction).

### Base merge before final checks (coordinator)
- Merged origin/dlv-00-delivery-setup (now including F-18, PR #29) at ff48d19d80a904de760cf524166ad820107267dd. Conflicts: WorkItemOverview.tsx imports (kept both: Workspace and RfpOutcomeLink) and F-17's own round-2 recipients-1440 fidelity report (kept the branch copy).
- `bash delivery/checks.sh`: exit 0. Full Playwright suite (E2E_PORT=4841 MOCK_PORT=4842): 405 passed.
