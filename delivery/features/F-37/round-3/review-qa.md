VERDICT: PASS
REVIEWER: qa
COMMIT: 435ef7d9d8d5d407902dffba40b1efcb8bc9bc7f
AUTHORITY: delivery integrated QA

## Summary
- Ran W-3401..W-3404 on the demo (app 4995, mock 4994) at 1440 and 390 with Playwright, after POST /__mock/reset, as pm, finance_lead, ceo and none. Scripts are in the scratchpad (qa.mjs, qa2.mjs, qa3.mjs). The mock stands in for the backend, so this is a contract-mock pass, not a real-backend pass.
- Accept, accept selected, edit and accept, write own, select-all, the past-answer link, uncertain hold, stale 409, 500 retry and access refusals all behave as spec at both widths. No blocking finding.
- The 409 and 500 paths were forced. 409: the mock scenario cookie `psl_mock_scenario=409` works on E-WORK-STEP, and a real stale revision also works (a second session bumps it). 500: the mock does not declare a 500 for E-WORK-STEP, so the cookie falls through. I injected a 500 with Playwright `page.route`, which proves the frontend only.
- Not proved: the final "Record input" for Security/Product. The mock answers `POST /api/v1/tasks/T-3401/response` with 501 not_mocked, so no recorded input could be completed end to end. Reject/return (part 2) is out of scope.

## Findings
- QA-3-1 | non-blocking | medium | integration | Record team input on W-3401 (drawer at both widths): proof upload (200) and claim (200) work, but `POST /api/v1/tasks/T-3401/response` returns 501 `not_mocked`. The UI shows "We couldn't confirm your input was recorded… reloaded" and claims no success, but the PM journey "record the Engineering Lead's part with proof" cannot complete on this stack. The checklist stays at Record. Mock gap in the shared F-18/F-31 response mock (`frontend/mock/response.mjs`), not part-1 code. The spec only requires the link and drawer (AC5). Add a T-3401 response handler or prove it against the real backend.
- QA-3-2 | non-blocking | low | integration | The 500 for E-WORK-STEP cannot be triggered by `psl_mock_scenario` (not declared, `mock/workspace.mjs:143`). AC11 says "psl_mock_scenario 500". Add a scripted 500 (a `.steps.json` entry or a cookie) so the e2e and QA can drive it without a route override.
- QA-3-3 | non-blocking | low | frontend | The "N selected" count carries over after Accept answer (the same as UX-1-5). Select-all after one accept gives "4 SELECTED" while the accepted R-07 stays in the list. Seen again at both widths; confirms UX-1-5.

## Verified
- UI-1-5 / UI-2-1 | verified | At 390 the select-all and row boxes sit in a 44x44 label with no stray rule seen. The box is 20x20 inside a 44x44 label. No sideways scroll.
- UI-2-2 | verified | W-3402 draws "that bid was won" and a link "Harmattan Bank RFP 2025 · R-12" to /work/W-1999. Link box 216x15 at 1440 (inline text) and 216x44 at 390. No "₦" anywhere.
- TECH-2-1 | verified | The RFP pages render normally at both widths, 0 page errors. The F-30/F-31 stacked tables were not checked.
- Accept answer | verified | One POST, log `accept:R-07:200`, notice "R-07 accepted under your name." at both widths.
- Accept selected | verified | After select-all, the log shows `accept_selected:R-08,R-09,R-10:200`. R-07 was already accepted, so only the ticked rows were sent.
- Edit and accept | verified | The form is prefilled with Tola's text. After editing, the log shows `edit_accept:R-07:200`.
- Write my own | verified | Empty submit names "Your answer" and sends nothing. Filled, the log shows `write_own:R-07:200`.
- Stale 409, scenario cookie | verified | The typed answer stays in the field and the page says "This changed while you were working. Showing version 7." Nothing claims accepted.
- Stale 409, real revision | verified | On W-3401 Add requirement, a second session added one first. The log shows `add_requirement 200` then `add_requirement 409`. The notice shows and both typed fields are kept ("Typed requirement QA", page 9). A write_own on an item already accepted elsewhere gets 422 item_ids, not 409, because the item check comes first, and the typed answer is kept.
- 500 (route-injected) | verified | The page shows "We couldn't confirm this step. Check the page before trying again." with Try again, no accepted notice, and no new ADDRESSED row. Try again resends the same idempotency_key (keys[0] === keys[1]).
- Uncertain W-3403 | verified | "Accept answer" shows the being-checked notice and exactly one accept in the log. Accept, Accept selected, Edit and Write my own are all disabled right after, and still disabled after a reload (only Reload is on).
- Access | verified | `none` sees the not-open view at both widths. W-3404 (pm, finance_lead, ceo) draws no action buttons. W-3499 shows another item's page, not an RFP one. A POST without CSRF returns 403. Controls are the same for pm, finance_lead and ceo, as AC15 asks.
- Past-answer link | verified | The link goes to /work/W-1999 and is 44px tall on the phone.
