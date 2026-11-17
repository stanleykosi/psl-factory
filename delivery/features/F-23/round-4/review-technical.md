VERDICT: PASS
COMMIT: 81e06419df1929371e460af6cd2f2adb13192903
REVIEWER: reviewer-technical
AUTHORITY: delivery technical review

## Summary
- Reviewed d5f10f5a..eb6ddf08 and the dlv-00 merge (eb6ddf08..778e868). `DoneView` now never shows an unconfirmed effect as an outcome, and the change is general, for every line.
- `UncertainNotice` moved from `DecideView.tsx` to `DecideStates.tsx` and is exported. There is one wording, with no copy. `Callout` is still used in `DecideView` (by `UnconfirmedNotice`), so no import is left dangling.
- F-16 tests are only added to, never edited (two new tests in `decide.test.tsx`; the existing ready-answer approve test is untouched).
- The merge brings the F-26 Money tab. It keeps every F-23 operation in the mock server and every guard in the contract test.
- The second merge of dlv-00 (778e868..81e06419, F-27 delegation) is a clean union and touches no F-23 file. One non-blocking note. No blocking findings.

## Findings
- TECH-4-1 | non-blocking | frontend/src/features/decide/DecideStates.tsx:417 | The uncertain condition is `result.work_state === 'effect_uncertain' || reloaded.state === 'effect_uncertain' || Boolean(reloaded.reconcile)`. A reloaded item that carries `reconcile` for an unrelated earlier delivery would also show "NOT CONFIRMED" after a clean approve. That is the safe direction (INV-RESEND), and the component test covers it. | Leave as is. Revisit only if the backend ever returns `reconcile` on an item whose current decision is certain.

## Verified
- QA-3-1 (technical side) | verified | `approved` is false when uncertain, so the banner is neutral. The "recorded" status line, the next-step card and the Paid line are all suppressed, and the heading reads "<label>: result not confirmed". "Open the work item" stays, and the notice is in a `role="alert"`. The decide POST count stays at 1 (asserted).
- Shared notice | verified | `DecideView` imports `UncertainNotice` from `DecideStates`. The wording is the same text as before.
- Tests | verified | New tests cover the `work_state` answer and a reloaded `reconcile`. The e2e W-2305 asserts the notice at 1440, 390 and 320. The ready-answer approve path is unchanged, so no existing F-16 assertion was weakened.
- QA-3-3 / QA-3-4 | verified | Only the sidecar facts and a test title changed. The behaviour of the test is the same as before.
- dlv-00 merge, `mock/server.mjs` | verified | `M1_OPERATIONS` still includes `E-DOCUMENT` and the assistant operations. The D-2304-only 501 guard is intact. The only addition is F-26's `isMoneyRequest` branch, placed before the `M1_OPERATIONS` check and scoped to the money tab and `E-REPORT`.
- dlv-00 merge, `mock-contract.test.ts` | verified | The only change is that the "non-M-1 returns 501" probe moved from `E-REPORT` (now mocked by F-26) to `E-PAYROLL-MATCH`. That is a reasonable repoint, not a weakening. `minutesProposalsStripped` and all its guards remain.
- Merged-head evidence | accepted | `merge-checks.log` exit 0 with 1952 tests, and `merge-e2e.log` with 116 passed, as reported by the coordinator.
- dlv-00 merge 2 (778e868..81e06419, F-27), `mock/server.mjs` | verified | `M1_OPERATIONS` is the union: `E-DOCUMENT`, `...ASSISTANT_OPERATIONS`, `...START_OPERATIONS`, `...CLIENT_OPERATIONS` plus `E-DELEGATIONS` and `E-DELEGATION`. The F-27 import, `resetDelegations()` in the reset and the delegation route are additive. The D-2304-only E-DOCUMENT 501 guard and F-26's money branch are intact.
- dlv-00 merge 2, `mock-contract.test.ts` | verified | Additions only: the delegation body, the `pm`/`none` 403 rows and the contract-body hooks. The `minutesProposalsStripped` guards and the `E-PAYROLL-MATCH` 501 probe are unchanged.
- Merge 2 scope | verified | `git diff --stat 778e868..81e06419` shows no change under `features/workspace`, `features/decide`, `mock/fixtures/work`, `E-DOCUMENT.json` or `minutes.test.tsx`, so the F-23 code and fixtures are unchanged since the last review. I accept the coordinator's merge2 logs (checks.sh exit 0 with 2017 tests, 122/122 e2e); I ran no tests.
