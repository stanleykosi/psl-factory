VERDICT: PASS
COMMIT: a0be1442b1c6f35fc0fb73dd93303f9062d816cf
REVIEWER: reviewer-technical
AUTHORITY: delivery technical review

## Summary
- The lock change is one expression in `Workspace.tsx`: `awaitingReconcile` is now true when the item has a `reconcile` or its state is `effect_uncertain`. Items with a `reconcile` behave exactly as before. Only an uncertain item without one is newly locked, which is the INV-RESEND-safe direction.
- The `noReconcile` flag only drives the checking notice and drops the "Confirm what happened first." hint when there is nothing to confirm. The hint is unchanged for every other locked case.
- The test tidy is a plain function with an empty-list rejection. No `src/api`, mock handler or fixture change in this range.

## Findings
None.

## Verified
- TECH-3-1 | verified | `weekly-mock.test.ts` has one plain `savedRecords` function and a `list.length > 0` check.
- SEC-3-1 (my lens: correctness) | verified | The new W-2205.next test without `reconcile` asserts the sentence, every step button `aria-disabled`, and no POST after forced presses.
