STATUS: READY
COMMIT: a0be1442b1c6f35fc0fb73dd93303f9062d816cf
BUILDER: builder
LANE: full

## Summary
- SEC-3-1 fixed: every step is locked whenever the item is `effect_uncertain`, with or without `reconcile`, so the "Nothing was sent again" sentence can never sit beside a live send button.
- TECH-3-1 tidied: `weekly-mock.test.ts` uses one plain `savedRecords` function, and it rejects an empty saved list.
- Contract mock only (D-LINE-WORKSPACE proposed): no real send, delivery or idempotency claim.

## Changes
- `frontend/src/features/workspace/Workspace.tsx`: `awaitingReconcile: Boolean(item.reconcile) || item.state === 'effect_uncertain'`; a `noReconcile` flag drives the checking notice and drops the "Confirm what happened first." hint when there is nothing to confirm (that hint is unchanged whenever a reconcile exists or the lock came from a press).
- `frontend/tests/weekly-returned-received.test.tsx`: new test on a copy of W-2205.next with `reconcile` and `allowed_actions` removed.
- `frontend/tests/weekly-mock.test.ts`: plain function, empty list rejected.

## Fixes
- SEC-3-1 | a0be1442b1c6f35fc0fb73dd93303f9062d816cf | state-based lock plus test
- TECH-3-1 | a0be1442b1c6f35fc0fb73dd93303f9062d816cf | one plain helper; empty saved list rejected

## Acceptance criteria
11. [x] No resend while uncertain, now including an uncertain item that offers steps but no reconcile: component test.
Others unchanged from round 3.

## Validation
- `bash delivery/checks.sh`: exit 0, 79 files, 1677 tests passed.
- `E2E_PORT=4750 MOCK_PORT=4751 npx playwright test e2e/weekly.spec.ts e2e/weekly-returned-received.spec.ts e2e/workspace.spec.ts`: 79 passed.
- The new test failed on the round-3 code (run with the old Workspace.tsx) and passes now.
- No fidelity re-run: no scored board (W-2209, W-2211) is an uncertain item, so none can move. Servers stopped, test-results deleted, disk 3.8 GB free at the last step.

## Verified
- SEC-3-1 | fixed | test "an uncertain item that still offers steps but no reconcile locks every step": the sentence is shown, every step button has `aria-disabled`, forced presses on Approve and send and Return with a note send no POST; fails on the old code
- TECH-3-1 | fixed | `weekly-mock.test.ts` single `savedRecords` function with `list.length > 0` check; 250 mock tests pass

## Blocked
Not blocked.
