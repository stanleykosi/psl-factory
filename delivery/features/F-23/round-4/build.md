STATUS: READY
COMMIT: 778e868137d79b0b808b55c5c994c7345613d586
BUILDER: builder
LANE: full

## Summary
- Round 4 fixes blocking QA-3-1 and the non-blocking QA-3-3 and QA-3-4. Contract mock only; nothing is released (D-LINE-WORKSPACE limits as before; test template; no real send).
- QA-3-1 is a small shared change in `features/decide`, authorised by the coordinator as a correctness fix, general for every line.

## Changes
- `DecideStates.tsx` `DoneView`: when the decide answered `work_state: "effect_uncertain"`, or the reloaded item is `effect_uncertain` or carries `reconcile`, the page shows the shared uncertain notice ("We couldn't confirm your decision. We've reloaded this item so you can see whether it was recorded."), a neutral header "NOT CONFIRMED" / "<label>: result not confirmed", and no green approved banner, no "Next step" card, no "recorded" status line and no Paid line. "Open the work item" stays. `UncertainNotice` moved from `DecideView.tsx` to `DecideStates.tsx` and is exported, so both views use one wording.
- QA-3-3: `W-2304.approve.json` and `W-2305.approve.json` facts: reviewed and approved earned (with a time); W-2305's sent is unknown.
- QA-3-4: the test at `tests/minutes.test.tsx` is renamed to say a blank is refused before any request and a typed text reaches the 422 (AC 10 is read that way).
- Tests: two component tests in `tests/decide.test.tsx` (uncertain work_state; reloaded item with reconcile); `e2e/minutes.spec.ts` W-2305 asserts the notice and no approved or next-step text at 1440, 390 and 320.

## Fixes
- QA-3-1 | eb6ddf081dbbdb476a6e2b71bd94140073b4b219 | decision page shows the uncertain notice, not an approval
- QA-3-3 | eb6ddf081dbbdb476a6e2b71bd94140073b4b219 | approve sidecars show approved facts earned
- QA-3-4 | eb6ddf081dbbdb476a6e2b71bd94140073b4b219 | test renamed

## Left
- QA-3-2 (the shared "Paid is tracked separately by Finance" sentence on every approve): stays a follow-up, as instructed. It is not shown on the uncertain view now.

## Validation
- bash delivery/checks.sh: exit 0 (a first run had one start-work.test.tsx timing failure in a file F-23 does not touch; it passes alone and the re-run passed).
- Playwright (4761/4762): minutes, decide, decide-board, workspace: 104 passed.
- Fidelity not re-run. No scored board shows an uncertain decision done view: the F-16 decide boards use W-1201 style fixtures that answer ready, and the SCR-28 boards are work pages. The only changed fixtures are the two approve sidecars, which no board scores.
- Servers stopped, test-results deleted.

## Verified
- QA-3-1 | verified | decide.test.tsx: effect_uncertain answer and a reloaded reconcile both show the notice, no success banner, no "Next step.", no "is approved", no Paid line; the existing approve test (ready answer) is unchanged and passes; e2e W-2305 at 1440, 390 and 320.
- QA-3-3 | verified | fixtures show reviewed and approved earned.
- QA-3-4 | verified | test title now matches its behaviour.

## Base merge
The coordinator merged dlv-00 (with F-26, the Money tab) into the branch; head is 778e868137d79b0b808b55c5c994c7345613d586 (my last own commit was eb6ddf081dbbdb476a6e2b71bd94140073b4b219). I checked the two files the merge touched: `frontend/mock/server.mjs` still lists `'E-DOCUMENT'` and the assistant operations in `M1_OPERATIONS` and keeps the D-2304-only 501 guard; `frontend/tests/mock-contract.test.ts` keeps `minutesProposalsStripped` and its `warn_lines`, `values`, `date_format`, `items_default` and `links` guards. `mock-contract`, `minutes-mock` and `minutes` tests pass on this head (325). The coordinator's merged-head checks.sh and 116 e2e passed, so the round-4 evidence stands.
