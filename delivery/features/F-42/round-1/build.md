STATUS: READY
COMMIT: 5fd62b4c65d9c80c66ebf0f6e3dd37bb0ddb8dc0
BUILDER: builder
LANE: full

## Summary
- PPE-0006 "Fixed asset schedule · October" now draws on F-33's schedule frame (`line_key: "fixed_assets"`). It covers four states: investigating (W-3901), register review (W-3902), date review (W-3903) and calculating (W-3904). Each state shows its stations, the agent card beside it, and decide in place through F-33's `InlineDecide`.
- There are two decide tasks on one item: T-3902 (register) and T-3903 (dates). Each is claimed and decided on its own `task_id`. After the register is decided it stays in `tasks[]` as `already_decided`, and it draws no card or claim.
- Money rules:
  - Costs are the backend's decimal strings, formatted as returned.
  - The page computes nothing.
  - Unknown reads "Unknown" (W-3910).
  - All 21 fixture files are `sample: true`.
  - Each unset rule is a `setup_needed` hold with no controls: W-3907 (who reviews assets), W-3908 (register rules), W-3909 (calculation rules).
  - An uncertain decide reads "October register: result not confirmed" and never shows success (W-3911).
- This round is the whole build. Base `be04d072` already contains F-33 (PRs #62-#64 merged, `4059b84a`).

## Changes
- `frontend/src/features/workspace/labels.ts`: new `scheduleLine(lineKey)` over the small set `{income_schedules, fixed_assets}`. F-35 has not merged, so this creates the line set itself. Whichever of F-35 and F-42 merges second reconciles the two sets.
- `frontend/src/features/workspace/Workspace.tsx` and `frontend/src/features/work-item/WorkItemOverview.tsx`: every F-33 `INCOME_LINE` / `'income_schedules'` check now reads `scheduleLine(...)`. That covers stations in the workspace, the agent card beside the sections with Ask in the card, the phone Drawer, the banner tone and the `already_decided` task filter. Other lines are unchanged. No `/me` is read.
- `frontend/src/features/workspace/workspace.css`: one additive phone rule. `.ws[data-line="fixed_assets"] .ws-table` stacks each row, with every cell under its column label, so the 3-column tables show every column with no sideways scroll. It uses tokens only. It does contain `width: 1px; height: 1px`, the visually-hidden thead, the same pattern as the existing `.ws-table--stack` rule. The media query is the file's existing `719.98px` breakpoint.
- `frontend/mock/fixtures/work/W-3901…W-3912.json` (12 items) and 9 decide sidecars: `W-3902.{approve,return,reject}`, `W-3903.{approve,return,reject}` and `W-3911.{approve,return,reject}`. No `.next.json` exists. The task ids T-3902…T-3937 are used only in W-39xx.
- Tests:
  - New: `frontend/tests/asset-schedule.test.tsx` (35 tests), `frontend/tests/asset-schedule-mock.test.ts` (11 tests) and `frontend/e2e/asset-schedule.spec.ts`.
  - `frontend/tests/mock-contract.test.ts` gets a new W-39xx block: 21 files are schema-valid with `steps[].verdict` stripped. W-3901 is also added to the links allow-list.
  - `frontend/tests/income-schedule-mock.test.ts`: the one assertion "verdict overlay only on W-27xx" becomes `W-(27|39)`. This was needed because the spec reuses the overlay. Nothing else in F-33's tests changed.
- `delivery/BACKEND-HANDOFF.md`: new section "## Added during F-42: fixed asset schedule (19 Nov)".
- Factory files in the main project folder:
  - `delivery/features/F-42/fidelity-exceptions.json`: 24 exceptions and 8 per-board visual waivers, all "builder proposal, pending design engineer".
  - `round-1/fidelity/` (`run.sh`, 8 reports, `scores.txt`).
- Not changed: `src/api/**`, `src/features/decide/**`, `src/shell/**`, `InlineDecide.tsx`, `proposals.ts`, `Sections.tsx`, `mock/server.mjs`, `mock/workspace.mjs`, `mock/fixtures/{response,finance,setup}/**`, `E-MONTH-END.json`, any existing fixture, `apps/**`, `architecture/**`, `design/**`, protected paths. Running `git diff --stat be04d072` over those paths shows nothing.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Four states from data. Component tests on W-3901…W-3904 check the status label and tone, the 6 stations, the facts, the table rows, the proof, the agent card and Next. A test walks `src` for the board strings. The spec grep over `frontend/src` returns 0 lines. I looked at the pages at 1440 and 390 (dev, then production in the fidelity run).
2. [x] Costs as returned. W-3902 shows ₦8,400,000.00, ₦14,000,000.00 and ₦3,150,000.00 at desktop and on the phone, with no short form. A copy set to `"14000000.10"` shows ₦14,000,000.10. e2e confirms these are visible at 1440 and 390.
3. [x] The page computes nothing:
   - "Assets" set to 65 changes only that value.
   - Removing a row leaves the consequence, the title and the other costs alone.
   - No opening, closing, total or net book value text appears on six pages. "Depreciation" appears only inside the backend's basis sentence.
   - `git diff -U0 be04d072 -- frontend/src | grep -E "parseFloat|Number\(|\.reduce\(|compactAmount"` returns 0.
4. [x] Unknown is never 0: the W-3910 Hilux COST cell reads "Unknown", not ₦0, 0.00, empty or a dash.
5. [x] Sample-marked: all 12 items show SAMPLE DATA when `NEXT_PUBLIC_SHOW_SAMPLE_LABEL=1`, and a `sample:false` copy does not. `jq '.sample' W-39*.json` gives 21 × true.
6. [x] Each unset key is a hold:
   - W-3907, W-3908 and W-3909 show "SETUP NEEDED", the "<rule> · NOT SET" fact and the `next` sentence.
   - None has a Decide panel, a button or a POST.
   - None shows "Ada Okafor" in main, "PPE reviewer", PROCESSING or ₦.
   - W-3909 has station 4 stopped and no Calculation facts.
7. [x] Controls come only from `you_can_act` and the steps:
   - W-3902 shows Approve register / Return with a note / Reject under "Decide · PPE reviewer".
   - W-3903 has one panel and claims only `/api/v1/tasks/T-3903/claim`.
   - W-3905 and W-3912 show "You prepared October register / October in-service dates, so someone else must review it." W-3906 shows the not_your_role copy. None of the three has a button or a claim.
   - The `finance_lead`, `ceo` and `pm` personas get the same controls.
   - None of the changed files contains `useMe` or `api/v1/me`.
8. [x] Agent work is not a decision:
   - On W-3901 the card shows WORKING, the 4 steps and their sources (VALUES NOT READ included), "Started 10:05" and "Ask Chidi" linking to `/assistant`, with no control.
   - The values line is the section `note`; removing it removes the text.
   - W-3904 has no agent card and no "Agent working" (see proposal P-4).
9. [x] Approved and calculating appear only from the re-read:
   - A held decide shows no PROCESSING or APPROVED until `W-3903.approve.json` is served.
   - W-3902 approve shows "WAITING FOR DATE EXPLANATIONS" and no Decide panel.
   - A 200 whose re-read is unchanged never shows APPROVED or PROCESSING.
   - W-3911 shows "October register: result not confirmed" and DECISION NOT CONFIRMED for all three verdicts, and still after a reload (component test and e2e).
10. [x] Approve sends one claim, then one POST with `{verdict:"approve",expected_revision:1}` and the CSRF header. The body validates against the generated request schema. A double press sends one. The same holds for T-3903. The e2e request log shows exactly the claim and the decision.
11. [x] Return and reject need a note:
    - Empty, blank or over 2000 characters sends nothing. The message appears under the field, is announced (`aria-invalid` and `aria-describedby`), and focus moves to the note.
    - With a note, one POST carries the trimmed note. The re-read shows RETURNED with the quote, or REJECTED.
    - There is no correction step. `grep "every return\|backend only waits" frontend/src` returns nothing.
12. [x] No write when the person cannot act: the e2e request log is empty across W-3901, W-3904…W-3909 and W-3912.
13. [x] Backend refusals are shown:
    - 403 gives the read-only not_your_role view with no "approved".
    - 409 gives the stale view, keeps the note, and the next press sends revision 2.
    - 422 shows the message under the note.
    - The mock test covers 422, 409 and 403 on the W-39xx tasks.
14. [x] Uncertain decide: a 500 and a network failure each re-read before anything else and show the uncertain notice. After 60 s with fake timers there is still exactly one POST. The e2e routed abort behaves the same. A later deliberate decide clears the earlier notice (test).
15. [x] Access:
    - 401 on read or write gives the signed-out view with `next=%2Fwork%2FW-390x`.
    - 403 and 404 on read look the same, with no title, cost or asset.
    - The `none` persona gets no further call.
16. [x] Phone at 390:
    - One column with the same sections and full costs.
    - The "Station n of 6" line shows.
    - The Decide bar is fixed and shows the step labels.
    - The Drawer opens, and Escape and Cancel return focus.
    - `scrollWidth` is at most the viewport, and no table frame scrolls.
    - Every main control is at least 44×44. The frame's History link is excluded as in F-33.
17. [x] Other lines are unchanged: `income-schedule.test.tsx` and `e2e/income-schedule.spec.ts` pass unchanged, and W-2411 (issue) draws none of the schedule frame.
18. [ ] Fidelity: one run over the 8 boards. Scores are below. Coverage after exceptions is 100 on 6 of 8 boards.
    - Register review 1440 is 94.1 and date review 1440 is 96.2. In both cases the tool does not read text nested in a `td` or a list row, so the three cost cells and the proof's two lines are false misses. The values are on screen (e2e and component tests); F-16/D-55 is the precedent.
    - I added these 5 as exceptions after the run (pending the design engineer), and I did not re-run or recompute.
    - Open design-engineer decision: accept them as tool false-misses, or ask for a shared `Sections.tsx` markup change (read-only for this feature).
    - Visual is under 90 on all 8 boards. Each has a D-83 waiver, all of them at least 70.
19. [x] Accessibility: axe (wcag2a, 2aa, 21a, 21aa, 22aa) is clean at 1440 and 390 on W-3901…W-3904, W-3907, W-3909, the open Drawer, the note error, the uncertain notice and the not-open view. The table has `th` headers and the note is labelled. The agent tag does not animate under `reducedMotion: 'reduce'`.
20. [x] Tokens and components only: no `#hex`, `rgb(` or `hsl(` was added. The only px values are the existing breakpoint, token names and the visually-hidden 1px (see Changes). No local copy of a shared component was added.
21. [x] Mock matches the contract (`asset-schedule-mock.test.ts`):
    - Every fixture and sidecar validates.
    - The W-39xx task ids are unique.
    - Claim then approve serves `W-3902.approve` (waiting) and `W-3903.approve` (calculating).
    - Return without a note gives 422; a stale revision gives 409; W-3905, W-3906 and W-3912 give 403.
    - W-3911 answers `effect_uncertain`, and reset clears.
22. [x] Contract not extended (see Changes). Proposals are listed below.
23. [~] Existing tests: see Validation. The full `checks.sh` failed twice, only on hook timeouts at load averages of 100 to 390, in files this feature does not touch. Each failing file passes alone. The e2e command passes 162/162.
24. [x] build.md evidence: this file.

## Validation
- `npx tsc --noEmit` and `eslint` on the changed files: clean.
- `npx vitest run tests/asset-schedule.test.tsx tests/asset-schedule-mock.test.ts tests/mock-contract.test.ts tests/income-schedule.test.tsx tests/income-schedule-mock.test.ts`: all pass (35, 11, 298 and F-33's).
- e2e: `cd frontend && E2E_PORT=4970 MOCK_PORT=4971 npx playwright test e2e/asset-schedule.spec.ts e2e/income-schedule.spec.ts e2e/workspace.spec.ts e2e/response.spec.ts e2e/finance-month-end.spec.ts e2e/issue-detail.spec.ts` gave 162 passed (7.5 min). `frontend/test-results` was deleted afterwards.
- Production build (`API_ORIGIN=http://127.0.0.1:4968 FRAME_FIXTURES=1 npm run build`): exit 0.
- `bash delivery/checks.sh`, under the shared lock, entered at load ($2) below 14 each time:
  - Run 1 (12:36, load rose to 390 during the run): Django check clean, lint and typecheck passed. Vitest failed 15 files with 8 failed tests, all "Hook timed out in 10000ms" or timeouts, none in a touched file. Re-run alone: 14 files gave 5 failures at load 230. Then `minutes-end-mock`, `mock-money` and `setup-proposal` passed 38/38, and `rfp` and `start-work-prefill` passed 62/62.
  - Run 2 (13:32, load rose to 190): Django check clean, lint and typecheck passed. Vitest: 108/109 files and 2490/2493 tests passed. The only failure was `tests/start-work-prefill.test.tsx` (3 tests, "Hook timed out in 10000ms"). Re-run alone it passed 9/9.
  - The lock was released both times. The gate's own run should be green at normal load.
- Fidelity: one run over the 8 boards on the production build (app 4969, mock 4968, fresh `__mock/reset` per board, persona finance_lead), using `round-1/fidelity/run.sh` with the tool unmodified.

| Board | Width | Coverage | With exceptions | Visual |
|---|---|---|---|---|
| SCR-55-desktop-investigating | 1440 | 84.8 | 100 | 84.1 |
| SCR-55-desktop-register-review | 1440 | 86.3 | 94.1 (3 cost cells, tool false-miss) | 75.0 |
| SCR-55-desktop-date-review | 1440 | 90.4 | 96.2 (proof lines, tool false-miss) | 74.5 |
| SCR-55-desktop-calculating | 1440 | 89.7 | 100 | 74.6 |
| SCR-55-mobile-investigating | 390 | 77.8 | 100 | 82.4 |
| SCR-55-mobile-register-review | 390 | 75 | 100 | 84.4 |
| SCR-55-mobile-date-review | 390 | 75 | 100 | 87.1 |
| SCR-55-mobile-calculating | 390 | 80 | 100 | 89.1 |

Each board has its own D-83 waiver in `fidelity-exceptions.json`. The main gaps are the shared frame (wider page, bell, History, crumbs as a list), the station strip with status lines, the taller shared rows, the AgentCard head, the basis drawn without bold, and the phone showing desktop content.

**Exceptions → Conflicts:**
- Crumbs and "← My work": 11.
- SAMPLE DATA: D-92, not a Conflicts item.
- "Bisi Ade · Finance": 13.
- Agent title and role line: 15.
- "October register" (bold) and the note label: 7.
- "Return" and the phone summary "4", "1", "Disposed", "EXPLAINED": 10.
- Phone titles: 9.
- The 3 costs and 2 proof lines: tool false-miss after the run (proof: 12).

All are "builder proposal, pending design engineer".

## Proposals and backend items (also in BACKEND-HANDOFF)
- P-1: `workspace.steps[].verdict` is reused as built (G-C-1, G-C-2).
- P-2: two decide tasks on one item (readiness question 1); does the date review skip when no date is unclear?
- P-3: `line_key: "fixed_assets"`, `screen: "SCR-55"`, and the view and state names (investigating, register_review, waiting_dates, date_review, calculating, returned, rejected, setup_needed, effect_uncertain).
- P-4: the Calculate station is sent as `waiting`, because `current_agent` would draw "Agent working" on a factory step. Which station status should a deterministic step carry? This costs blue-versus-amber on the calculating boards.
- P-5: the proof is a `cites` entry with `evidence_id` and is not opened (no app path).
- Others: the `setup_needed` shape and station per key (readiness question 2) and the Setup link (G-C-3); the explain-dates step (G-55-1, needs a board); D-RETURN (readiness question 3); the guard that keeps asset values out of Chidi's context (G-55-6); Ask Chidi context (G-C-4); no idempotency key on E-TASK-DECIDE (F-33 PMO-3-1).

## Held (from "What is sent")
- Reviewer, register rules and calculation rules, all NOT SET and all shown as holds.
- The explain-dates step.
- The return outcome (D-RETURN).
- The verdicts offered (G-C-1).
- The Setup link (G-C-3).
- Part 2: schedule by class, revoke, opening balance, accounting note, correct and resubmit, correction upload, the "Feeds MANAGEMENT ACCOUNTS" link, compact amounts.

## Mock seam
Option (b): new ids W-3901…W-3912, opened directly. The month-end row and W-1604 are unchanged.

## Blocked
None.
