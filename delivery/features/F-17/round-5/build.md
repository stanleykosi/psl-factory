STATUS: READY
COMMIT: af3b958cfa5807108e940017aefdc04e60375b1b
BUILDER: builder
LANE: records only

## Fixes
- QA-5-1 | af3b958c | Decide bar flows (position: static, no reserved bottom padding) while every step is locked and a reconcile action exists, so F-09's fixed "Record and continue" bar is tappable
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
