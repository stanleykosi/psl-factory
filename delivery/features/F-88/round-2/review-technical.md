VERDICT: PASS
COMMIT: eacdc7045a458039ad42eb19ea5852cc411578df
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead), lighter panel D-180

## Summary
- I reviewed `git diff bdeee685 cbccc7a3`. It changes labels, hints, callouts and the segmented control only. The payload builder in `receivedBid.tsx` is untouched: lines 133-135 still send `submissionMethod` only when set, and `contextAttested` only when optional fields are filled and attested. No write body, key or endpoint changed against contracts/psl-factory.openapi.json 1.26.0.
- The submission-method change from a Select to a Segmented control keeps the same `SubmissionMethod | undefined` draft value and the same optional send rule. The "Client portal" label does not change the sent `portal` value.
- Removing `withOwnLines` and `OWN_LINES` makes Log RFP show only when `/lines` lists it. `isStartable` still allows an own line once it is listed. This fixes TECH-1-1. The mock `start-live.mjs` now lists `received-bid`. The test in `start-work-live.test.tsx` was changed to check the empty state, which is reachable again.
- The `notice` state and its Callout are removed from `MyWork.tsx`, which fixes TECH-1-2. One orphaned F-36 comment remains at line 69.
- I did not rerun the tests. The CI gate on eacdc704 passed per round-2/checks.md. The tests changed in line with the new wording, and none were weakened or skipped.

## Findings
- TECH-2-1 | non-blocking | low | frontend | `frontend/src/features/my-work/MyWork.tsx:69` still has the F-36 comment about the assign panel's `notice`, but the state it described is gone. Delete the comment in a later pass. It is harmless.

## Verified
- TECH-1-1 | verified | `withOwnLines` and `OWN_LINES` are removed from LineChooser, StartWorkDrawer and lines/index.ts. The chooser and `direct` prefill read `state.data.items` only. The updated test expects the "There are no lines you can start right now." empty state.
- TECH-1-2 | verified | The `notice` state, `setNotice(undefined)` and the Callout are removed, and the unused `Callout` import is dropped. A stale comment is left (see TECH-2-1).
- TECH-1-3 | verified | Carried forward, no change in this diff. It is a coordinator decision outside F-88's lane.
- TECH-1-4 | verified | Carried forward, no change in this diff. Playwright was not run.
