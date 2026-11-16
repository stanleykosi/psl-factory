VERDICT: PASS
COMMIT: a0be1442b1c6f35fc0fb73dd93303f9062d816cf
REVIEWER: reviewer-security
AUTHORITY: delivery security review

## Summary
- SEC-3-1 is fixed. Every workspace step now locks whenever `item.state === 'effect_uncertain'`, with or without `reconcile` (Workspace.tsx:78). The lock applies at both layers: the controls are switched off (`off()`, Workspace.tsx:115), and `submit()` returns `kept` while `allLocked` (useWorkspaceStep.ts:102).
- The new test removes `reconcile` and `allowed_actions` from W-2205.next. It checks the "checking" sentence, no reconcile radiogroup, every step button `aria-disabled="true"`, and that real clicks on "Approve and send" and "Return with a note" send no POST. build.md says it failed on the round-3 code.
- The round-4 diff also tidies weekly-mock.test.ts: one helper, and an empty saved list is now rejected. Neither change is a security change.
- No new findings. Contract mock only, as before.

## Findings
None.

## Verified
- SEC-3-1 | verified | Workspace.tsx:78 is now `awaitingReconcile: Boolean(item.reconcile) || item.state === 'effect_uncertain'`, so `allLocked` holds on any uncertain item from the first render. Nothing in the hook can clear it, because it comes from the item and not from local state. `noReconcile` (:87) only drives the notice and drops the "Confirm what happened first." hint when there is nothing to confirm; it does not loosen the lock. Test: weekly-returned-received.test.tsx:313-326. `press` is a plain `fireEvent.click` (:85-89), so the clicks really happen and `sent` stays free of POSTs. Existing uncertain workspace fixtures behave as before: W-2205.next and W-2008.next already locked through `reconcile`, and W-2212 has no steps. The only behaviour change is for an uncertain item without reconcile, which is the case the finding covered. I did not re-run the tests (read-only review); build.md reports checks.sh exit 0 with 1677 tests, and 79 e2e passed.
- SEC-1-1, SEC-1-2 | verified (carried) | Access and whole-run request tests unchanged this round.
- SEC-1-3 | accepted (carried) | Recorded follow-up; ReconcilePanel.tsx unchanged.

## Notes
- The weekly-mock.test.ts `savedRecords` helper now matches mock-contract.test.ts, including the non-empty check (my round-3 low note). The stripping is still limited to `records` field `value` after a shape check.
- No change under `src/api/**`, `apps/**`, the mock handlers or the fixtures. No new dependency and no secrets in the diff.
