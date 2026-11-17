VERDICT: PASS
COMMIT: 81e06419df1929371e460af6cd2f2adb13192903
REVIEWER: reviewer-ux
AUTHORITY: delivery UX review

## Summary
- After an uncertain approve the decision page no longer claims an approval. It shows a warning notice, a neutral "NOT CONFIRMED" header and "<label>: result not confirmed", and keeps "Open the work item". This is clear and correct for the PMO Lead.
- Checked from code, tests and my round-1 live walk of W-2305; not re-run live because the machine is busy. No blocking findings.

## What I checked
- `DecideStates.tsx` `DoneView`: `uncertain` is true when the decide answered `effect_uncertain` or the reloaded item is `effect_uncertain` or carries `reconcile`. Then the green banner, the "Your decision was recorded" status line, the "Next step" card and the Paid line are all dropped; the header is neutral. Nothing says approved, sent or recorded.
- Wording: "We couldn't confirm your decision. We've reloaded this item so you can see whether it was recorded." is plain, says what the factory did and what the PM should do. It sits in a `role="alert"`, so it is announced after the press. The facts strip still shows sent as unknown.
- "Open the work item" is the right way on: in my round-1 walk W-2305 opens on the "Confirm what happened" panel first, with Approve and Return disabled and "Confirm what happened first." That is the only next action and it is where the PM is sent.
- Tests: decide.test.tsx covers both triggers (no banner, no "Next step.", no "is approved", no Paid line); the ready-answer approve test is unchanged; e2e W-2305 checks 1440, 390 and 320. Shared change, so it applies to every line.
- The merge from dlv-00 (Money tab) does not touch the decide or minutes flows.

## Findings
- UX-4-1 | non-blocking | uncertain notice | The notice says "see whether it was recorded" but does not say that Open the work item leads to a confirm step. | Optional: add "Open the work item to confirm what happened." Not needed for this feature.
- The shared Paid sentence on a normal approve (UX-1-2) stays accepted for the follow-up.

## Re-check at 81e06419 (dlv-00 merge bringing F-27 delegation)
- Diff 778e868..81e06419 under `frontend/`: 25 files, all delegation (setup delegation page, DelegationForm/View, `mock/delegations.mjs` and its fixtures, setup tests) plus a small `mock/server.mjs` change (delegation import, reset call, two operations added to `M1_OPERATIONS`; `E-DOCUMENT` and the other minutes operations remain) and a 7-line `mock-contract.test.ts` addition.
- No file under decide, work-item, workspace or minutes fixtures changed (name filter on the diff is empty). The round-4 verdict stands unchanged.
