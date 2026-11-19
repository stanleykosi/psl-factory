STATUS: READY
COMMIT: 59ce7dc1e6896a89a54ccd7e83cf2addf5b51937
BUILDER: builder
LANE: full

## Summary
- `/work/W-4001`…`W-4004` draw the cash forecast FC-0014 in four states (investigating, review, uncertain delivery, verified) from E-WORK-ITEM fixtures alone. W-4005…W-4013 cover you-prepared-it, both NOT SET holds, not-your-role, two/one verdicts, link step, no grant and decision-not-confirmed. All are sample data on the contract mock.
- The review is decided in place through F-33's `InlineDecide` (one claim, then one decision per press; a note is needed for return and reject). An uncertain delivery is recorded through the existing `ReconcilePanel`, with line-scoped words for `cash_forecast`. Every amount is shown as returned. Nothing is computed and Unknown is never 0.
- This round (after the session restart) also:
  - added the decide timeout case;
  - fixed the eight-station row overflowing at 1440 (axe `scrollable-region-focusable`, which failed 11 desktop e2e tests);
  - moved "Record what happened" into the workspace side column above Next on desktop (it had pushed the whole workspace down by about 380px);
  - fixed a fragile diff test.
- Gate, unit tests and e2e are green. Fidelity: all 8 boards are at 100% coverage with the proposed exceptions, and visual is 71.3 to 84.6. The 8 D-83 waivers and 38 exceptions are builder proposals, not signed.

## Changes
- `frontend/src/features/workspace/labels.ts`: `cash_forecast` is added to the schedule lines. New `reconcileBeside(lineKey, phone)` is true only for `cash_forecast` on desktop.
- `frontend/src/features/workspace/Workspace.tsx`: on `cash_forecast` desktop, `ReconcilePanel` is drawn at the top of `.ws-side`, in both the writable and read-only branches. **Listed difference:** the spec limits this file to the line-key set. This change is needed to match the uncertain board, which draws the record control in the side column, and it is scoped to the line.
- `frontend/src/features/work-item/WorkItemOverview.tsx`: no exceptions button for `cash_forecast`. The overview's own `ReconcilePanel` is skipped where the workspace draws it (cash forecast, desktop). Phone and every other line are unchanged.
- `frontend/src/features/workspace/workspace.css`: two additive rules, no raw values. `.ws[data-line="cash_forecast"] .ws-stations` stations become equal `minmax(0, 1fr)` columns, as the board draws them (`repeat(8, minmax(0, 1fr))`).
- `frontend/src/features/response/ReconcilePanel.tsx`, `labels.ts`: the Conflicts 4 words for `cash_forecast` only:
  - heading and accessible name "Record what happened";
  - "Nothing is sent again until a person records what happened.";
  - "It arrived. I have proof it was received (upload it next)."

  Other lines keep the client-invoice words (`grep -c "invoiced twice"` is 1).
- Fixtures:
  - `frontend/mock/fixtures/work/W-4001…W-4013`;
  - the decide sidecars `W-4002.{approve,return,reject}` and `W-4013.{approve,return,reject}`;
  - `frontend/mock/fixtures/response/W-4003.{delivered,not_delivered,unknown}.json`.
- Tests:
  - new: `tests/cash-forecast.test.tsx` (41) and `tests/cash-forecast-mock.test.ts`, plus `e2e/cash-forecast.spec.ts`;
  - `tests/mock-contract.test.ts`: a new F-43 block, and W-4001 added to the links allow-list;
  - `tests/income-schedule-mock.test.ts`: the verdict-overlay allow-list widened to W-40xx. **Listed difference against AC 27's "unchanged"**: F-33's guard names the series allowed to carry `steps[].verdict`, so the new series has to be named in it.
- `delivery/BACKEND-HANDOFF.md`: an "Added during F-43" section.

## Fixes
- None (round 1).

## Acceptance criteria
1. [x] Four states from data: the component tests for W-4001…W-4004 pass. The AC 1 grep over `frontend/src` returns nothing. Pages were checked at 1440 and 390 (fidelity screenshots).
2. [x] Amounts as returned: "₦22,600,000.00" at both widths; the changed and 17-digit amounts are shown digit for digit; no "M" form (component and e2e).
3. [x] Nothing computed: tests on modified copies pass. `git diff -U0 $(git merge-base HEAD origin/dlv-00-delivery-setup) -- frontend/src | grep -nE "parseFloat|Number\(|\.reduce\(|compactAmount|toFixed"` returns nothing.
4. [x] Unknown is never 0 at both widths, and a real "0.00" reads ₦0.00 (component).
5. [x] Sample-marked: every fixture and sidecar has `sample: true`. SampleLabel shows only with the env flag and `sample: true` (component).
6. [x] W-4006 and W-4007 are holds: no panel, no button, zero POSTs, no names (component and e2e request log).
7. [x] `required_role` is shown as returned: "Finance Lead" for that copy, and no role when it is absent.
8. [x] Decide controls follow `you_can_act` and the steps only. W-4009, W-4010, W-4011, W-4005 and W-4008 behave as specified, with three personas. No new code reads `/me` (the grep checks `\buseMe\b`).
9. [x] W-4001 shows the agent card with steps, sources, WORKING, "Started 08:40" and Ask Chidi (`/assistant`). There is no decide control.
10. [x] W-4003 is drawn from the response only. Changed strings change only that text. Without reconcile and grant, the lock is shown. There is no cancel, resend or retry control at either width.
11. [x] No grant means no panel and no action: W-4012, W-4004 and W-4002.
12. [x] Verified only after the re-read: approve re-reads to APPROVED. For reconcile, a 200 with a stale re-read never says Verified, Delivered or received. Note 1 (below): the option label is excluded from that check.
13. [x] Approve: one claim, then one decision `{verdict:"approve", expected_revision:1}` with CSRF, valid against the schema. A double press sends one (component and e2e).
14. [x] Return and reject need a note: empty, blank and over 2000 characters send nothing; the trimmed note is sent; RETURNED and REJECTED come from the re-read.
15. [x] No write when the person cannot act: the e2e request log is zero for W-4001, W-4004…W-4008 and W-4012.
16. [x] 403 gives the read-only view; 409 gives the stale view with the note kept and the new revision on a new press; 422 shows the message under the note.
17. [x] Uncertain decide: 500, network failure and timeout (`DOMException TimeoutError`, added this round) re-read first, show UncertainNotice and send one POST after 60 s of fake time. W-4013 shows DECISION NOT CONFIRMED. e2e covers a routed abort.
18. [x] Record what happened:
    - with no choice, the "choose" message is shown and nothing is sent;
    - "It arrived" stays off until a proof is uploaded, then sends one POST with `evidence_id` and `case_revision`;
    - the other outcomes send no evidence;
    - a double press sends one;
    - nothing goes to steps, claim or decision;
    - the panel has no "client" or "invoiced" words.
19. [x] Reconcile failures never resend: 500, network failure and timeout show "We couldn't confirm your answer…"; 409, 403 and 422 show their messages.
20. [x] Access: 401 shows the signed-out view with `next`. 403 and 404 look the same. Persona `none` gets the not-open view with no further call.
21. [x] Phone (e2e at 390): one column, the table scrolls only in its region, `scrollWidth <= 390`, a pinned bar with three labels, the Drawer with Escape and Cancel returning focus, and every target at least 44 px.
22. [~] Fidelity: 100% coverage after the proposed exceptions; visual 71.3 to 84.6 with D-83 waivers. Everything is pending the design engineer (see Fidelity).
23. [x] Axe is clean (WCAG 2.2 AA tags) at 1440 and 390 on W-4001…W-4007, the Drawer, the note error, the reconcile panel, the uncertain notice and the not-open view. Reduced motion works.
24. [x] Tokens and components only: the CSS adds no hex, rgb, hsl or px, and there is no component copy. InlineDecide and ReconcilePanel are reused.
25. [x] Mock matches the contract: the mock tests pass, with schema validation and every id in the W-40xx and T-40xx ranges.
26. [x] Contract not extended: compared with the merge-base 006599ef, `frontend/src` changes only the files above. `api/**`, `decide/**`, `shell/**`, `InlineDecide.tsx`, `proposals.ts`, `mock/*.mjs`, existing fixtures, `apps`, `architecture`, `design` and protected paths are untouched. The branch is 20 commits behind `origin/dlv-00`, so a plain diff against `origin/dlv-00` also shows dlv-00's own newer changes. Read the diff from the merge-base.
27. [x] Gate and existing tests are green (below). The listed difference is `income-schedule-mock.test.ts` (one allow-list).
28. [x] This file and the handoff section are written.

## Validation
- `delivery/checks.sh` at 59ce7dc1, under the shared lock: Django check is clean; lint, typecheck, `vitest run` (Test Files 116 passed, Tests 2712 passed) and build all pass; `exit 0`. The earlier run at dae538ed was also exit 0.
- e2e at 59ce7dc1: `cd frontend && E2E_PORT=4895 MOCK_PORT=4894 npx playwright test e2e/cash-forecast.spec.ts e2e/income-schedule.spec.ts e2e/workspace.spec.ts e2e/response.spec.ts e2e/finance-month-end.spec.ts` gives `141 passed (5.3m)`, exit 0. The first e2e run (at dae538ed) had 11 failures, all at 1440 and all from `scrollable-region-focusable: .work-track`. They are fixed in 1cc41919. `test-results` was deleted afterwards.
- Targeted: `npx vitest run tests/cash-forecast.test.tsx tests/response.test.tsx tests/income-schedule.test.tsx tests/workspace.test.tsx tests/workspace-step.test.tsx` gives 222 passed.
- Fidelity (`round-1/fidelity/run.sh`): production build with `API_ORIGIN=http://127.0.0.1:4894 FRAME_FIXTURES=1`, app on 4895, mock on 4894 reset before each board, persona `finance_lead`, the shared tool unmodified.
  - The scores below are from the second run, at the head's code. The first run (before the reconcile placement fix) had desktop uncertain at visual 66.6, under the floor. The fix was a real layout defect, so I re-scored all 8 rather than report stale numbers. That is one more run than D-64's one per round.
  - The run used an empty exceptions file. "With exceptions" is recomputed from each `report.json` missing list with the tool's own `norm` and role and name rule (`exceptionFor`), using the proposed `fidelity-exceptions.json`.

| board | coverage | with proposed exceptions | visual |
|---|---|---|---|
| SCR-56-desktop-investigating-1440 | 86.1 | 100 | 84.6 |
| SCR-56-desktop-review-1440 | 74.6 | 100 | 75.6 |
| SCR-56-desktop-uncertain-1440 | 84.6 | 100 | 71.6 |
| SCR-56-desktop-verified-1440 | 68.8 | 100 | 75.8 |
| SCR-56-mobile-investigating-390 | 77.8 | 100 | 83.8 |
| SCR-56-mobile-review-390 | 56 | 100 | 78.4 |
| SCR-56-mobile-uncertain-390 | 57.1 | 100 | 71.3 |
| SCR-56-mobile-verified-390 | 29.4 | 100 | 72.6 |

- Servers on 4894 and 4895 are stopped. Disk had 4.7 GB free.

## Fidelity exceptions (all `approved_by: "builder proposal, pending design engineer"`)
- Frame, Conflicts 11: the crumbs line; "← My work".
- "SAMPLE DATA": D-92.
- Sample data, Conflicts 13: "Bisi Ade · Finance".
- Component, Conflicts 15: "Investigating the cash forecast"; "Chidi · Finance agent · step 3 of 4".
- Component, Conflicts 1 (an open "Need an answer" item): the 8 compact amounts. The full amounts are drawn.
- Component, Conflicts 6: "management"; the note label.
- Component, Conflicts 9: phone "Return".
- Component, Conflicts 12: the bold banner lead.
- Component, Conflicts 3: the long Next sentence; "Cancel delivery".
- Component, Conflicts 4: the "Record what happened" link (drawn as the panel).
- Component, Conflicts 5: "Record actuals".
- Frame item, Conflicts 9: the phone wording "Check with the CEO's office before sending again.", "CALC", "REVIEW", "DRAFT", "2/2".
- **Tool limit (D-119 precedent), Conflicts 1 and 14:**
  - "Unknown";
  - CALCULATED, REVIEWED, DRAFTED, PUBLISHED, RECEIPTS, "12 Nov", "13 Nov", "14 Nov" and "2 of 2";
  - "The forecast never moves cash or authorises a payment."

  These are on the page. The tool skips text in a span inside an `li` or `td` whose own text is empty (the `owned` rule in `extract.mjs`). **Design engineer:** AC 22 says no exception may cover a value the data supplies. These cover values that are shown but not read by the tool, not values that are missing. Accept them as tool limits (as D-119 did for F-41 and F-42), or have the tool fixed.
- D-83 visual waivers are proposed for all 8 boards (71.3 to 84.6, all at or above the floor of 70). No floor exception is needed. Reasons are in the file.

## Contract proposals and backend items (also in BACKEND-HANDOFF "Added during F-43")
- Overlay reused: `workspace.steps[].verdict` (G-C-1). `money.display_short` is not built (Conflicts 1, option B only).
- Backend questions:
  - who decides the forecast review (no Setup key; "Forecast reviewer" is sample text only);
  - the `setup_needed` shape and Setup link for the holds (G-C-3);
  - what Cancel delivery does while uncertain (gaps :137);
  - publishing as a step and who the 2 receipts are (G-C-7);
  - per-recipient reconcile (G-C-5);
  - the reconcile reply and the state after each outcome (the sidecars are assumptions);
  - the G-56-9 basis audience;
  - **no idempotency key on E-TASK-DECIDE**;
  - D-RETURN;
  - Ask Chidi context (G-C-4).
- Held per "What is sent": the preparer, the inclusion rule, the reviewer, cancel, publishing and receipts, per-recipient reconcile, the verdict set, the basis audience and D-RETURN. Parts 2 and 3 hold group rows and review, Record actuals and matching, Withdraw, Correct and resubmit, and the F-47B drawer.

## Notes for the design engineer and reviewers
1. The approved option wording "It arrived. I have proof it was received (upload it next)." collides with AC 12's ban on "received". The tests check the status, the notices and the side column with the choice labels removed (`.resp-options`), not the option label. Please confirm the wording or give another.
2. Existing F-33 behaviour, unchanged: `InlineDecide` shows "Forecast v1 is approved" after any decide 200, even when the re-read still says AWAITING. The status tag still comes from the re-read. Recorded here, not changed.
3. Listed differences: the `Workspace.tsx` and `WorkItemOverview.tsx` reconcile placement; the `workspace.css` station rule; the `income-schedule-mock.test.ts` allow-list; the second fidelity run.
4. Integration: the branch is 20 commits behind `origin/dlv-00-delivery-setup` (F-34 merge and others). Whoever merges second merges the base and reruns checks and e2e (spec Lanes).

## Blocked
None.
