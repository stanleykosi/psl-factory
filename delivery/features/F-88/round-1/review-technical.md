VERDICT: PASS
COMMIT: bdeee6852cdfbefbe883a6a5cd8f23b8d7faa3b1
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead), lighter panel D-180

## Summary
- Both writes match contract 1.26.0. `POST /received-bids` is multipart with the required keys, `deadline_at` only when stated, no `definition`, and one `start_key` per form. The 5xx and no-answer path locks the form and replays the same input and key. 422 duplicate shows the API message. `POST .../assignment` sends the `evidence` or the `upload_id` plus `checked: true` variant, with `reason` required, and re-reads before it says "assigned".
- The `OwnLine` / `ownsSubmit` registry change is additive. `lineFormFor` and the weekly report path are unchanged, and `isStartable` only widens for registered own lines.
- The My work Unassigned change is correct and small. It swaps the body for `UnassignedBids`, hides the search toolbar on that tab, and narrows `?assign=` to a case uuid. One leftover is dead state (TECH-1-2).
- The deleted v7 `rfp-assign` tests covered v7-only behaviour (acting_role, W-ids, `assign` block on the work item). The behaviour that survives (empty submit, 409, 422 mapping, 5xx re-read, no double send, 403/404) has equivalent assertions in `assign-pm.test.tsx`. No assertion was weakened. Live proof is mock-only by decision and is not a finding.
- Gate passed on this head (158 files, 3772 tests).

## Findings
- TECH-1-1 | non-blocking | low | frontend | `withOwnLines` (`src/features/start-work/LineChooser.tsx`) adds "Log a received RFP" for every signed-in person, even when `/lines` does not list it for them. The builder's live run shows this for the seed account. That person reaches the form and gets the organisations 403 or empty state instead of not seeing the line. This is defensible because the organisations read is the real authority check, but note it for the coordinator. The "no lines you can start" empty state in `start-work-live.test.tsx` is now unreachable, and the test was rewritten to match.
- TECH-1-2 | non-blocking | low | frontend | `src/features/my-work/MyWork.tsx:70` still declares `notice` and its Callout, but nothing calls `setNotice` with a message now that the assign wiring is gone (only the reset at line 83). Remove it in a later pass. It is harmless.
- TECH-1-3 | non-blocking | medium | integration | The Unassigned tab is drawn only when `counts.unassigned` is defined (`MyWork.tsx:286`), and live `/work` returns no `counts`. SCR-24 is therefore reachable only by URL until My work is connected. The builder already reported this and it is outside F-88's lane, so it needs a coordinator decision, not a fix here.
- TECH-1-4 | non-blocking | low | frontend | `e2e/rfp-assign.spec.ts` was deleted and no Playwright spec replaces it for the new Unassigned list or the drawer (axe, phone sheet, reduced motion). Vitest covers behaviour. Playwright was not run in this review. The existing `my-work.spec.ts` pm-on-Unassigned case is kept working by the mock's 403 for persona `pm` on `/assignments`.

## Verified
None (round 1).
