# Fixed asset schedule · October: Chidi checks the register, a PPE reviewer approves the register changes and then the explained dates in place, and the item goes to calculation or is held (contract mock only)

> **The build starts only after F-33 is merged into `dlv-00-delivery-setup`.** This spec is written against F-33's branch `fe-fin-schedules-income-detail-review` in `/Users/Hunchoo/psl-factory-worktrees/f-33`, head `d20fd9b2` (the branch tip is now `b8265cdb`, which only adds one line to `delivery/BACKEND-HANDOFF.md`, so the frontend is the same). F-42 reuses F-33's `InlineDecide.tsx`, `stepVerdict`, the `steps[].verdict` overlay and the "reviewer not set" hold fixture pattern. It does not copy them. If F-33 changes in a later round, this spec is re-checked before the build.
>
> Tasks: FE-FIN-PPE, part 1 (R-FINANCE; acceptance A-WORKSPACE, frontend half, with A-WORKITEM, A-DECIDE and the F-16, F-17, F-29, F-33 and month-end/response tests kept green). Architecture: package `architecture/packages/v7`, manifest digest `f6231d20b4fdeabbdca9bde5986a0a7883536f1a5cafc883848ef62dd6d4b624`. FE-FIN-PPE is at `architecture/packages/v7/delivery.md:2711-2740`, with `gate_ids: []` and "Unresolved gates: none". It depends on FE-WORKSPACE-FRAME (F-17, merged). Endpoints are typed in `frontend/src/api/schema.d.ts`: E-WORK-ITEM `:54` (`workspace` `:1693-1912`, table `cells[].money` `:1767`, `cites` `:1830`, `tasks[].cannot_act_reason` `:1419`), E-TASK-CLAIM `:96` and E-TASK-DECIDE `:117` (verdict `:2136`, `work_state` `:2157`). E-WORK-STEP and E-EVIDENCE-UPLOAD are not sent. This feature changes no generated type. Decisions consumed: D-LINE-WORKSPACE (`proposed`, under the recorded exception `architecture/sources/decisions-2026-11-15.md` items (g), (i)); D-RETURN (open, revision 2, a working assumption, `architecture/model.json:859-869`), used here only for the re-read after a return; D-64, D-83, D-89, D-91, D-92 (c), D-111, D-112, D-113 (F-33's inline decide accepted). Policy, all unset: `finance.asset_schedule.register`, `.calculation` and `.reviewer` (`frontend/mock/fixtures/setup/finance.desktop.json:137-175`, `set: false`), and F07.source_rules, F07.calculation_rules and F07.review_authority (`contracts/ppe-policy-components.json`, `UNCONFIGURED`). Gaps: `delivery/backend-handoff/gaps-f-finance-workspaces.md:17-37` (SP-1 to SP-9, G-C-1 to G-C-9) and `:95-112` (SCR-55, G-55-1 to G-55-6). Design: client-approved canvas version 1794581312-b166 (13 Nov 2026, covering the Finance and Payroll canvas), republished with "+ Start" as 1794762832-cab1 (D-89). `python3 /Users/Hunchoo/software-factory/packages/design/design.py check --project /Users/Hunchoo/psl-factory` was run for this spec on 18 Nov: `EXCEPTION`, `passes: true` (design_sha256 `2859ab21…3d82`, the D-89 frame-only change). Screens: SCR-55, 8 of its 14 artboards in `design/canvas/finance/project/`: `SCR-55-{desktop,mobile}-investigating`, `-register-review`, `-date-review` and `-calculating`. Part 2 (`-schedule-review`, `-returned`, `-verified`) is out. Models: `delivery/features/F-33/spec.md` (shape, inline decide, money rules), `F-35/spec.md` (building on F-33's line branches).

## What is sent, and what stays held (read first)

- **Sent (to the local mock only):** the review claim (E-TASK-CLAIM) and one decision per press (E-TASK-DECIDE, verdict `approve`, `return` or `reject`, with a note for return and reject). There are two decide tasks, the register review and the date review. Each is claimed and decided on its own `task_id`. Nothing is calculated, posted, uploaded or exported, and nothing goes to anyone outside the app.
- **Held, because a product or backend decision is open.** The page shows whatever the re-read work item says and adds no rule. Each item below is held:
  1. Who reviews assets: `finance.asset_schedule.reviewer` and F07.review_authority are NOT SET, so no real review can start. The review fixtures are sample-marked, and a "reviewer not set" fixture shows the backend's hold.
  2. Register rules: `finance.asset_schedule.register` and F07.source_rules are NOT SET. A fixture shows the hold at Register review.
  3. Calculation rules: `finance.asset_schedule.calculation` and F07.calculation_rules are NOT SET. This includes which date starts depreciation, useful life and capitalisation. A fixture shows the hold at Calculate, with no calculation shown as started.
  4. The step where someone writes the date explanation and attaches the proof. It has no board (G-55-1), so it is not built.
  5. What a returned register or returned dates gives the preparer (D-RETURN). No correction step is built.
  6. Which verdicts each review offers (G-C-1).
  7. The Setup link from a hold (G-C-3).
- **Held to part 2:** the schedule by asset class with Unknown, and its review; Withdraw approval (`revoke`, G-55-4); the furniture opening balance (G-55-2); the accounting note (G-55-3); "Correct and resubmit"; the correction proof upload; the "Feeds MANAGEMENT ACCOUNTS" link (G-C-3); the board's compact amounts.

## Conflicts with the boards (for the design engineer, before the build)

"Recommend" is what this spec builds if no answer comes. Each becomes a `fidelity-exceptions.json` entry, with `approved_by: "builder proposal, pending design engineer"` until it is signed. Items 1 to 8 change what a person sees or can do and need an answer. Items 9 to 13 are layout. Items 14 to 16 are exceptions to sign. "Contract" means a proposal field built on the mock only, which the backend developer may change or refuse.

### Need an answer

1. **The register review and the date review are two Decide panels on one work item. Today the frame sends a decision to the separate decision page** (G-C-1, G-C-2). **Recommend:** decide in place with F-33's `InlineDecide` as built and accepted (D-113). Each step that carries a `task_id` and a `verdict` (`approve`, `return`, `reject`) becomes one button in that task's "Decide · <required_role>" panel. The buttons use the step labels: "Approve register", "Return with a note" and "Reject"; or "Approve dates", "Return with a note" and "Reject". `Workspace.tsx` already groups verdict steps by `task_id`, so each fixture's open task draws its own panel. The buttons exist only when that task's `you_can_act` is true. The register task, once decided, is still in `tasks[]` on the date review with `cannot_act_reason: already_decided`, and it draws no second card (F-33's settled-task filter, extended to this line). **Option B:** link to the decision page. There would be no overlay field, and the drawn panel becomes a listed difference.
2. **There is no board for the step between the two reviews, where someone explains the 3 unclear dates and attaches the proof** (G-55-1). This one needs the design engineer. The date-review board already shows the explanations and an uploaded `asset-dates-explanation.pdf`. Nothing says who wrote them or where. **Recommend:** build no explain step and no upload. After "Approve register", the page draws the backend's re-read only. The sample sidecar `W-3902.approve.json` has `state: waiting`, the backend's status label, the register task `already_decided`, no decide control and a `next` sentence as returned. The date-review fixture `W-3903` opens with the explanations and the proof already present, as the board draws them. That waiting state has no board, so it is not in the fidelity run. **Option B:** the design engineer draws the explain-dates board, which part 2 or a follow-up then builds as an E-WORK-STEP `explain_dates` (G-55-1 contract). Until then, the register approval re-read stays as recommended.
3. **The date-review basis says "Depreciation starts from these dates."** Which date starts depreciation (delivered or live) is F07 Calculation rules, which is NOT SET. **Recommend:** the whole sentence is the date task's `decision.basis`, shown word for word from the sample fixture, and its wording is checked at product acceptance. The page never chooses a date from "Delivered 02 Oct, live 15 Oct", and no frontend string mentions depreciation. **Option B:** the sample fixture's basis reads only "Approve the explained dates." until F07 is set. The second sentence then becomes a listed difference.
4. **No board draws the three unset-policy holds.** **Recommend:** three hold fixtures, built like F-33's `W-2706`. Each returns `state: setup_needed`, the backend's own status ("SETUP NEEDED", `stopped`), the station it stops at (`stopped`), a "Why it's held" facts line with the value "NOT SET", and its `next` sentence. The three are "Register rules" (stops at Register review), "Who reviews assets" (stops at Register review) and "Calculation rules" (stops at Calculate). The page draws exactly that in the same frame. It has no Decide panel, no button, no reviewer's name or role, no figure and no "calculating" claim. The Setup link is not drawn (G-C-3). The `next` sentence names the place in words. These states have no board and are not in the fidelity run. **Option B:** the design engineer draws the holds first, and the feature waits for them.
5. **The calculating board shows "Rule F07 CALCULATION RULES" as if a rule were set; the rule is NOT SET.** **Recommend:** `W-3904` and the date approval sidecar `W-3903.approve.json` draw the board as a sample: the "Calculation" facts and the `next` sentence as returned. The real state today is the hold `W-3909` (conflict 4). Both are reachable, and the sample label marks the board one. **Option B:** the date approval sidecar goes to the hold `W-3909` content, and `W-3904` stays reachable only by its URL.
6. **No board draws a returned or rejected register or date review** (D-RETURN, open). **Recommend:** the return and reject sidecars are the backend's re-read only. A return shows the status "RETURNED" (`person`) with the reviewer's words as an untitled `text` section, drawn as F-33's returned-quote banner. A reject shows "REJECTED" (`stopped`, `state: cancelled`). Neither shows a correction step or a `next` sentence, and the frontend writes no D-RETURN wording. **Option B:** return and reject are held to part 2, and only the approve buttons are sent. The board's Return and Reject would then be missing, which is a listed difference.
7. **The Decide panel's words.** The note label says "(needed to return, reject or withdraw)", but withdraw is part 2. The basis lines are record wording. **Recommend:** as F-33 conflict 7 (D-113). The panel title is "Decide · " + `required_role` ("PPE reviewer" appears only in the sample fixtures). The basis is `tasks[i].decision.basis` as returned. The note label lists only the verdicts offered that need a note: "Note (needed to return or reject)". The approve consequence "3 assets have unclear dates; they go to a date review next." is the step's `consequence`. Wording is checked at product acceptance.
8. **The month-end row "Fixed asset schedule" opens `W-1604`.** That is the response tests' no-grant fixture (`tests/response.test.tsx:791`, `tests/response-mock.test.ts:257`), and the month-end tests pin the link (`mock/fixtures/E-MONTH-END.json:16`, `mock/fixtures/finance/month-end.*.json`). **Recommend:** readiness option (b). The four states live on new ids `W-3901`…`W-3904`, opened directly. The month-end row and `W-1604` stay unchanged. In the real app, the backend's `tasks[].work_id` sets the link. **Option B:** repoint the month-end row to `W-3901` and update the pinned assertions.

### Layout (phone against desktop, frame)

9. **The phone titles differ from desktop** ("Investigating", "Register review", "Date review", "Calculating" against "Fixed asset schedule · October"). **Recommend:** the work item's `title` at both widths (D-111). The status tag carries the state. Listed (`frame item`).
10. **The phone boards drop desktop content.** Phone investigating has no "Register" facts, no values-note line and no "Ask Chidi". Phone register review shows "Added 4 / Disposed 1" in place of the "Register changes" table, with no basis or note. Phone date review shows "3 unclear dates EXPLAINED" in place of the table and proof. Phone calculating shows only "PROCESSING". **Recommend:** the phone shows the same sections, words and values as desktop in one column (D-111, F-28, F-30, F-33). Costs show in full ("₦14,000,000.00") with no short form. The phone Decide bar is pinned with the step labels. "Return with a note" and "Reject" open the full-height `Drawer` with the note (F-33 as built). The phone labels are the desktop ones ("Return with a note", not "Return"). If three buttons do not fit one row at 390, the bar wraps. Extra elements are listed (`extra element`).
11. **Frame items.** These follow the F-17/F-22/F-33 frame as built:
    - the phone "← My work · PPE-0006 · Start" bar;
    - the "STATION n OF 6 · NAME" line, from F-33's `LineStations` (`MiniStationBar`);
    - the desktop station row and top bar;
    - the crumbs "FINANCE / SCHEDULES / ASSETS · PPE-0006", from `workspace.context.crumbs`;
    - no project tab bar.

    The top-bar nav also differs between boards ("Overview" and "Setup" appear only on the review boards). That nav comes from the signed-in persona. Differences listed (`frame item`).
12. **Drawn styles with no field to carry them:**
    - "Unclear dates 3" draws the 3 as a tag. **Recommend:** the backend's value "3" as a plain fact value. F-33's beside-value tag is drawn only when the item sends one, and this fixture sends none.
    - The proof row has a paperclip icon and a bold file name. **Recommend:** the cite's `label` as text, with the item's `detail` "Uploaded · 64 KB". It is no link, because a cite with only `evidence_id` has no app path (`labels.ts` `refPath`) and nothing is downloaded or uploaded here.

    Both are listed (`component`).
13. **The signed-in name** ("Bisi Ade · Finance" on investigating and calculating, "Ada Okafor · Finance Lead" on the reviews) comes from `/me`. The mock's Finance persona is Ada Okafor on all four. No new persona is added. Listed (`sample data`).

### Exceptions to sign

14. **Every board string is data.** All of these come from fixtures, and no board string is in `src/`:
    - status labels: "CHIDI INVESTIGATING", "AWAITING FINANCE DECISION", "PROCESSING";
    - stations;
    - facts values: "64", "4", "1", "3", "REGISTER · APPROVED", "APPROVED", "F07 CALCULATION RULES";
    - table cells: "Dell server rack · A-0412", "Added 02 Oct", "\"Oct 2026\"", "Blank", "Delivered 02 Oct, live 15 Oct";
    - the proof's file name;
    - the agent's steps and sources;
    - "Started 10:05".

    Case and time formats follow the library (`When`, `Tag`). Category: `component`.
15. **Agent card.** `AgentCard` draws these from `item.agent` beside the sections, through F-33's agent-beside branch extended to this line: "Chidi · Finance agent · step 3 of 4", "WORKING", the four steps and their sources ("PPE_REGISTER_OCT.XLSX · 64 ASSETS", "PPE-0005", "VALUES NOT READ"), and the footer "Started 10:05". "Ask Chidi" is the `workspace.links` `assistant` link to `/assistant`, with no work-item context (G-C-4). The line "Chidi never reads asset values; he checks structure, dates and provenance." is the "Register" section's `note`, from data. It is not frontend copy, and the guarantee is the backend's (G-55-6). Agent work is never shown as a decision or a verified result.
16. **Visual waivers.** Scores under 90 are waived board by board in `fidelity-exceptions.json`, citing D-83 and the shared frame, after the design engineer signs. A board under the 70 floor needs its own floor exception, as D-112 gave for SCR-08-mobile and SCR-30-mobile-verified.

## Boards

| Board | File (`design/canvas/finance/project/`) | Page | Mock |
|---|---|---|---|
| SCR-55 investigating, desktop / phone | `SCR-55-desktop-investigating.dc.html`, `SCR-55-mobile-investigating.dc.html` | `/work/W-3901` | persona `finance_lead` |
| SCR-55 register review | `SCR-55-desktop-register-review.dc.html`, `SCR-55-mobile-register-review.dc.html` | `/work/W-3902` | persona `finance_lead` |
| SCR-55 date review | `SCR-55-desktop-date-review.dc.html`, `SCR-55-mobile-date-review.dc.html` | `/work/W-3903` | persona `finance_lead` |
| SCR-55 calculating | `SCR-55-desktop-calculating.dc.html`, `SCR-55-mobile-calculating.dc.html` | `/work/W-3904` | persona `finance_lead` |

All 8 are live URLs, and no driver is needed. Each fidelity run starts with `POST /__mock/reset`, so `W-3902` and `W-3903` are not served from a decided override.

## Summary
- A Finance person opens PPE-0006 "Fixed asset schedule · October". In the F-17 line workspace they see what Chidi read: 64 assets, 4 added, 1 disposed, 3 unclear dates, values not read. All of it comes from data.
- A PPE reviewer who did not prepare the item approves, returns with a note, or rejects the register changes in place. They then do the same for the explained in-service dates, a second task on the same item. Both go through F-33's `InlineDecide` over the F-16 claim-then-decide flow.
- After the dates are approved, the item shows "PROCESSING" with the backend's "Calculation" facts. When Calculation rules are not set, it shows the backend's hold. "Approved" and "calculating" appear only from the re-read item.
- Every cost is the backend's decimal string, formatted as returned, and Unknown reads "Unknown". The page computes no total, count or depreciation. Controls come only from `tasks[].you_can_act` and the steps sent, and nothing reads `/me`.
- New: `fixed_assets` added to F-33's line branches, 12 fixtures (`W-3901`…`W-3912`) with decide sidecars, and tests. No mock server change and no contract change. Contract mock only.

## Context
- **Base must include F-33.** These exist only on F-33's branch, which is not yet in `dlv-00-delivery-setup`:
  - `frontend/src/features/workspace/InlineDecide.tsx` (`InlineDecide`, `DECIDE_TEXT`, the phone bar and `Drawer`, `onDeciding` clearing earlier notices; TECH-2-1);
  - `proposals.ts` `stepVerdict`;
  - in `Workspace.tsx`: `INCOME_LINE`, `LineStations`, `LineAgent`, `splitAsk`, the income `bannerTone` branch, `inDrawer`, and `decideTasks` grouping by `task_id`;
  - in `WorkItemOverview.tsx`: the `AgentCard` `foot` prop, the stations and agent hiding for the income line, and the `already_decided` task filter (`settled`);
  - the `Sections.tsx` beside-value tag.

  F-35 (spec Lanes) plans to turn the `INCOME_LINE` checks into small line sets. F-42 adds `fixed_assets` to those sets if F-35 has merged first. Otherwise it creates the same sets, and whichever merges second reconciles them.
- **Work item page and frame:** `frontend/src/features/work-item/WorkItemView.tsx` (`LineHeader`, crumbs from `workspace.context.crumbs`) and `WorkItemOverview.tsx`. Workspace: `Workspace.tsx`, `Sections.tsx` (`facts` with `note`; `table` with `money` cells through `MoneyValue`/`moneyText`, and `Unknown`; `text` items with `cites` through `Cites`/`RefView`), `Links.tsx` (`assistant`) and `usePageReload.ts`.
- **Decide flow (reuse, do not change):** `frontend/src/features/decide/useDecision.ts` claims once per task revision, allows one write at a time, re-reads after an uncertain write and never resends automatically. Also `DecideStates.tsx` (`cannotActCopy`, `UncertainNotice`) and `format.ts` (`NOTE_MAX` 2000, `VERDICT_WORDS`, `findDecisionTask` by `task_id`, so two tasks on one item resolve separately). E-TASK-DECIDE has no idempotency key in v7 (F-33 PMO-3-1). A double send is guarded by `expected_revision` and one write per press.
- **Money:** `frontend/src/components/format.ts` (`formatAmount`, string digits, no float; `UNKNOWN`). `features/finance/month-end/model.ts` `compactAmount` is not used.
- **Mock:** `frontend/mock/server.mjs` `taskResponse` (`:149-180`) validates the body and applies the note rule for return and reject. It checks `expected_revision` (409) before `you_can_act` (403), then swaps in `<work_id>.<verdict>.json`. `findTask` scans only the base `W-nnnn` fixtures and overrides, so **task ids must be unique across base fixtures**. **A `<id>.next.json` makes the first decide answer 409**, so no fixture here has one. A second decide on the same work id would serve the same `<id>.<verdict>.json` again. That is why each sidecar leaves no task the person can act on (conflict 2). Fixtures go in `frontend/mock/fixtures/work/`. `W-1604` lives in `mock/fixtures/response/work/` and is not touched. This feature takes `W-3901`…`W-3912` (reserve to `W-3999`) and `T-3901`…`T-3999`.
- **Setup keys:** `frontend/mock/fixtures/setup/finance.desktop.json:137-175` (Register rules, Calculation rules, Who reviews assets, all `set: false`).
- **Tests that must stay green:**
  - Vitest: `tests/workspace.test.tsx`, `tests/workspace-step.test.tsx`, `tests/workspace-mock.test.ts`, `tests/decide.test.tsx`, `tests/decide-board.test.tsx`, `tests/mock-decide.test.ts`, `tests/document-review.test.tsx`, `tests/response.test.tsx`, `tests/response-mock.test.ts`, `tests/finance-month-end.test.tsx`, `tests/finance-month-end-mock.test.ts`, `tests/mock-contract.test.ts`, and F-33's `tests/income-schedule.test.tsx` and `tests/income-schedule-mock.test.ts`;
  - e2e: `e2e/workspace.spec.ts`, `e2e/response.spec.ts`, `e2e/finance-month-end.spec.ts`, `e2e/income-schedule.spec.ts`, `e2e/issue-detail.spec.ts`;
  - F-35's leadership-report tests, if F-35 has merged.

## Contract

### E-WORK-ITEM `GET /api/v1/work/{work_id}` (unchanged)
`useWorkItem` reads it. The page draws `workspace` in returned order for `line_key: "fixed_assets"` and branches on nothing else.
- 401 → the signed-out state with `next=/work/<id>`.
- 403 and 404 look the same (`NoAccessState`, with no title, cost or fact, and no further call).
- 5xx → `WorkErrorCard` with Retry.
- Loading → `LoadingState`.

After any write the page re-reads (`usePageReload`). It never builds an optimistic state from a 200 body.

### Fixtures

Every fixture has `sample: true`, `reference: "PPE-0006"`, `title: "Fixed asset schedule · October"`, `line: "Fixed asset schedule"`, `workspace.line_key: "fixed_assets"` and `screen: "SCR-55"`. Crumbs are FINANCE / SCHEDULES / "ASSETS · PPE-0006", with no `context.project`. There are 6 `stations`: Chidi investigates, Register review, Date review (if unclear), Calculate, Schedule review, Verified.

| Id | `state`, `workspace.status` (label, tone) | Sections | Tasks and steps |
|---|---|---|---|
| W-3901 investigating | `processing`, "CHIDI INVESTIGATING" `agent`; station 1 current | `facts` "Register": Assets "64", Added since September "4", Disposed "1", Unclear dates "3" (no tag, conflict 12); section `note` "Chidi never reads asset values; he checks structure, dates and provenance." `item.agent`: Chidi, `working`, 4 steps ("Read the asset register" with source "PPE_REGISTER_OCT.XLSX · 64 ASSETS"; "Compared with September's schedule" with source "PPE-0005"; "Found 3 assets with unclear in-service dates" with source "VALUES NOT READ"; "Hand to register review", not started), `started_at` `2026-11-13T09:05:00Z` (10:05 Lagos). `workspace.links` `assistant` "Ask Chidi" | `tasks: []`; no steps |
| W-3902 register review (can act) | `action_needed`, "AWAITING FINANCE DECISION" `person`; station 2 current | `table` "Register changes", columns ASSET `text`, CHANGE `text`, COST `money`. Rows: "Dell server rack · A-0412" / "Added 02 Oct" / `{amount: "8400000.00", currency: "NGN", unknown: false}`; "Toyota Hilux · A-0388" / "Disposed 20 Oct" / `"14000000.00"`; "3 laptops" / "Added" / `"3150000.00"` | `T-3902` `kind: decide`, `required_role: "PPE reviewer"`, `you_can_act: true`, `revision: 1`, `decision.version.label` "October register", `decision.basis` "Approve the October register as the source for the schedule.", `prepared_by {name: "Bisi Ade", role: "Finance", is_you: false, with_agent: "chidi"}`. Steps, all with `task_id: T-3902`: `approve_register` (primary, `verdict: approve`, consequence "3 assets have unclear dates; they go to a date review next."), `return_register` (secondary, `verdict: return`), `reject_register` (danger, `verdict: reject`). Sidecars, each one revision higher with T-3902 `you_can_act: false`, `cannot_act_reason: already_decided`: `W-3902.approve.json` (`waiting`, the backend's status, station 2 done, station 3 current, `next` as returned, no task the person can act on; conflict 2), `W-3902.return.json` ("RETURNED" `person`, the reviewer's quote as an untitled `text` section, no step; conflict 6), `W-3902.reject.json` (`cancelled`, "REJECTED" `stopped`, read-only). **No `W-3902.next.json`.** |
| W-3903 date review (can act) | `action_needed`, "AWAITING FINANCE DECISION" `person`; stations 1 and 2 done, 3 current | `table` "Unclear dates", columns ASSET, REGISTER SAYS, EXPLANATION, all `text`. Rows: "A-0412 server rack" / "\"Oct 2026\"" / "Delivered 02 Oct, live 15 Oct"; "A-0415 laptop" / "Blank" / "Issued 07 Oct"; "A-0416 laptop" / "\"Q4\"" / "Issued 09 Oct". `text` "Proof": one item with `cites [{label: "asset-dates-explanation.pdf", evidence_id: "EV-3903"}]` and `detail` "Uploaded · 64 KB" | `T-3931` (register, `already_decided`, no steps) and `T-3903` (dates: `you_can_act: true`, `revision: 1`, `required_role: "PPE reviewer"`, `decision.version.label` "October in-service dates", `decision.basis` "Approve the explained dates. Depreciation starts from these dates." (conflict 3)). Steps `approve_dates`, `return_dates` and `reject_dates`, all `task_id: T-3903`, with verdicts approve, return and reject. Sidecars: `W-3903.approve.json` (the W-3904 calculating content, with T-3931 and T-3903 `already_decided`), `W-3903.return.json`, `W-3903.reject.json` (as for W-3902). **No `W-3903.next.json`.** |
| W-3904 calculating | `processing`, "PROCESSING" `agent`; stations 1 to 3 done, 4 current; `item.agent` `done` (Chidi does not calculate) | `facts` "Calculation": Source "REGISTER · APPROVED", Dates "APPROVED", Rule "F07 CALCULATION RULES". `next`: ["The factory calculates the schedule with the approved rules; Chidi doesn't see the values."] | `T-3934` and `T-3935`, both `already_decided`; no steps |
| W-3905 register review, you prepared it | as W-3902 | as W-3902 | `T-3905` `you_can_act: false`, `cannot_act_reason: prepared_by_you`; the three verdict steps sent |
| W-3906 register review, not your role | as W-3902 | as W-3902 | `T-3906` `you_can_act: false`, `cannot_act_reason: not_your_role`; steps sent |
| W-3907 reviewer not set | `setup_needed`, "SETUP NEEDED" `stopped`; station 2 `stopped` | `facts` "Why it's held": "Who reviews assets" with value "NOT SET" and tag `stopped`. `next`: ["An admin sets Who reviews assets in Setup · Finance rules. The register review starts then."] | `tasks: []`; no steps; no `required_role` and no reviewer anywhere |
| W-3908 register rules not set | `setup_needed`, "SETUP NEEDED" `stopped`; station 2 `stopped` | `facts` "Why it's held": "Register rules" "NOT SET". `next` as returned | `tasks: []`; no steps |
| W-3909 calculation rules not set | `setup_needed`, "SETUP NEEDED" `stopped`; stations 1 to 3 done, 4 `stopped` | `facts` "Why it's held": "Calculation rules" "NOT SET". `next`: ["An admin sets Calculation rules in Setup · Finance rules. The calculation starts then."] No "Calculation" facts and no figure | `T-3936` (register) and `T-3937` (dates), both `already_decided`; no steps |
| W-3910 unknown cost | as W-3902 | as W-3902, but the Toyota Hilux cost is `{currency: "NGN", unknown: true}` (no `amount`) | `T-3910` can act; steps as W-3902 |
| W-3911 decide effect uncertain | as W-3902 | as W-3902 | `T-3911` can act. Sidecars `W-3911.approve.json`, `.return.json` and `.reject.json`, each `state: effect_uncertain`, "DECISION NOT CONFIRMED" `uncertain` (the F-33 `W-2712` pattern) |
| W-3912 date review, you prepared it | as W-3903 | as W-3903 | `T-3932` (register, `already_decided`) and `T-3912` (dates, `you_can_act: false`, `cannot_act_reason: prepared_by_you`); steps sent |

Each fixture and sidecar validates against the generated E-WORK-ITEM 200 schema once the overlay is stripped. Every money value is either `{amount: "<decimal string>", currency, unknown: false}` or `unknown: true` with no amount. The `facts` "64", "4", "1", "3" are backend strings, not counts.

### Overlay proposals (mock only; each recorded in build.md for the backend developer)
- `workspace.steps[].verdict` (F-33 G-C-1), reused as built, read by `stepVerdict`. `approve`, `return` and `reject` are drawn; anything else is not drawn.
- Two decide tasks on one work item, in order (readiness question 1). No new field: `tasks[]` already carries both.
- `line_key: "fixed_assets"` and `screen: "SCR-55"` (D-LINE-WORKSPACE, proposed).
- **Financial values the boards show that no endpoint supplies.** "₦42.1M" and "₦0.0M" are part 2, and no short form is drawn. Costs come from the typed table cell `money`. "64 / 4 / 1 / 3" and "3 assets have unclear dates" are backend text, never counted by the page. Part 1 shows no depreciation, opening, closing or class total.

### E-TASK-CLAIM `POST /api/v1/tasks/{task_id}/claim` and E-TASK-DECIDE `POST /api/v1/tasks/{task_id}/decision`
- **Writes go through F-33's `InlineDecide` and `useDecision(work_id, task_id)` only,** keyed by the step's `task_id` (T-3902 on the register review, T-3903 on the date review). There is no new write path. The claim is sent once per task revision, only while that task's `you_can_act` is true. No claim is sent for a task that is `already_decided`. Until the claim answers, the buttons are off and the existing "Getting this review ready…" line shows.
- **Decide request:** `{verdict, note?, expected_revision: <task revision as read or claimed>}` with the `X-CSRFToken` header and no extra keys. `note` is required and non-blank for `return` and `reject`, at most `NOTE_MAX` (2000). This is checked before any request. The message goes under the Note field ("Add a note to return it." or "Add a note to reject it."), is announced, and focus moves to the note. Approve sends no note.
- **200:** the item is re-read, and the page draws the re-read state. The done notice is the existing `VERDICT_WORDS` heading ("October register is approved", "October in-service dates is approved"), and only when the re-read is settled (F-33 `settled`). With a re-read of `effect_uncertain`, or a decide answering `work_state: effect_uncertain`, the notice is "<label>: result not confirmed". "Approved", "APPROVED" and "PROCESSING" appear only from the re-read's facts and status. A new decide clears the earlier notice (F-33 TECH-2-1).
- **Errors:**
  - 401 → signed out.
  - 403 → the read-only view keyed on the re-read `cannot_act_reason` (403 and 404 alike on read).
  - 409 → the existing stale view. The note is kept and nothing is resent automatically.
  - 422 → the backend message under the note.
  - 5xx, network or timeout → re-read first and show `UncertainNotice`. The page never shows "approved", "returned" or "rejected" from the click, and the next decide is sent only on a new deliberate press.
- **Permission and tenant:** buttons show only when `tasks[i].you_can_act` is true for the step's `task_id`. Otherwise the page shows `cannotActCopy(cannot_act_reason, task)` and no button. The page has no role, person or `prepared_by` rule, and does not read `/me`.

### Screen states
- **Loading:** the existing skeleton.
- **Empty:** a workspace with no sections draws the header and status only.
- **Error:** the problem card with Retry.
- **Success:** the four board states plus W-3905, W-3906 and W-3910…W-3912.
- **Held:** W-3907, W-3908, W-3909.
- **Waiting after the register approval:** `W-3902.approve.json` (conflict 2).
- **Restricted:** a section, item or cell with `restricted: true` draws "Restricted" and never shows its value.

## Lanes
- **Frontend lane (builder, Opus for the first build: high risk, D-64)** owns:
  - `Workspace.tsx` and `WorkItemOverview.tsx`: add `fixed_assets` to F-33's (or F-35's) line checks for the stations row, the agent card beside the sections with Ask in the card, the phone `Drawer`, the banner tone and the `already_decided` task filter. Other lines are unchanged.
  - Additive rules in `workspace.css`, tokens only, if any.
  - Fixtures `frontend/mock/fixtures/work/W-3901…W-3912`, with the `.approve`, `.return` and `.reject` sidecars named above.
  - Tests: `frontend/tests/asset-schedule.test.tsx`, `frontend/tests/asset-schedule-mock.test.ts`, `frontend/tests/mock-contract.test.ts` (new fixtures only, `steps[].verdict` stripped as F-33 does), `frontend/e2e/asset-schedule.spec.ts`.
  - Factory files in `delivery/features/F-42/` (`fidelity-exceptions.json`, `round-<N>/`).
- **Shared, read only:**
  - `InlineDecide.tsx`, `proposals.ts`, `Sections.tsx`, `Steps.tsx`, `StepForm.tsx`: change only if a test proves a defect, and list it;
  - `src/features/decide/**`, `src/features/documents/**`, `src/features/finance/**`, `src/components/**`, `src/shell/**`, `src/api/**` (including `schema.d.ts`), `src/styles/**`;
  - `mock/server.mjs`, `mock/workspace.mjs`, `mock/fixtures/response/**` (including `W-1604`), `mock/fixtures/finance/**`, `mock/fixtures/E-MONTH-END.json`, `mock/fixtures/setup/**`, and every existing fixture (including F-33's `W-27xx`);
  - `frontend/package.json`, the lock file, `playwright.config.ts`, `vitest.config.ts`;
  - `architecture/**`, `design/**`, `apps/**`;
  - the protected `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json`.
- **Backend lane:** none. These go to build.md and do not block part 1:
  - G-C-1 `steps[].verdict` and G-C-2 inline placement;
  - two decide tasks per item, and whether the date review is skipped when no date is unclear (readiness question 1);
  - the `setup_needed` shape and station for each unset key (readiness question 2), and the Setup link (G-C-3);
  - the explain-dates step (G-55-1, which needs a board);
  - what a return gives the preparer (D-RETURN, readiness question 3);
  - the guard that keeps asset values out of Chidi's context (G-55-6, INV-AGENT);
  - G-C-4 "Ask Chidi" context;
  - the missing idempotency key on E-TASK-DECIDE (F-33 PMO-3-1);
  - the state and `view` names for investigating, register review, date review and calculating.
- **Integration owner:** the coordinator. This build starts only once F-33 is merged into the base. F-35, F-43 to F-45 and other Finance lines are likely to touch `Workspace.tsx`, `WorkItemOverview.tsx`, `workspace.css` and `mock-contract.test.ts` in parallel. Whichever merges second merges the current base and reruns `delivery/checks.sh` and the e2e. F-47B may later point its start's mock `work_id` at `W-3901`. That is optional, and it is not done here.
- **Ports:** app 4942, mock 4943. Run `cd frontend && E2E_PORT=4942 MOCK_PORT=4943 npx playwright test e2e/asset-schedule.spec.ts e2e/income-schedule.spec.ts e2e/workspace.spec.ts e2e/response.spec.ts e2e/finance-month-end.spec.ts` with `timezoneId: 'Africa/Lagos'`. Fidelity runs on a production build, one run per round over all 8 boards (D-64). Run `df -h /System/Volumes/Data` first and stop under 3 GB. Delete `frontend/test-results` afterwards. e2e is not in `checks.sh`, so paste its output in build.md.
- **Review routing (high risk):**
  - technical (Sonnet);
  - UI (fidelity gate, Opus for the first review);
  - UX (Sonnet);
  - QA (Opus);
  - security (Opus: an authority-bearing approval of a Finance source that carries money);
  - PMO.

  Product acceptance is required. It merges only on the design engineer's "merge".
- **Size:** about 1,100 to 1,500 lines, most of it fixtures and tests. One PR.

## Acceptance criteria

### Page
1. **Four states from data.** `/work/W-3901`…`W-3904` show their fixture's status label and tone, stations, sections, agent card, table rows, proof, facts and "Next", and nothing else. No board string is in `src`. — verify: `grep -rn "CHIDI INVESTIGATING\|AWAITING FINANCE DECISION\|PPE reviewer\|never reads asset values\|VALUES NOT READ\|Depreciation starts\|F07\|PPE_REGISTER\|asset-dates-explanation" frontend/src` returns nothing; `cd frontend && npx vitest run tests/asset-schedule.test.tsx`; pages at 1440 and 390.
2. **Costs as returned.** On W-3902 the cost cells read "₦8,400,000.00", "₦14,000,000.00" and "₦3,150,000.00" at 1440 and at 390, with no short form. If the fixture's `"14000000.00"` is changed to `"14000000.10"`, the page shows "₦14,000,000.10" exactly. — verify: component test at both widths.
3. **The page computes nothing.**
   - Changing W-3901's "Assets" value to "65" changes only that value.
   - Removing a row from W-3902's table changes no other text, including the consequence "3 assets have unclear dates…".
   - No depreciation, opening, closing, total or count appears on any part 1 page.
   - No new or changed file adds `parseFloat`, `Number(`, `reduce(`, `compactAmount`, or arithmetic on an amount or count.

   — verify: component tests on modified copies; `git diff -U0 <base> -- frontend/src | grep -nE "parseFloat|Number\(|\.reduce\(|compactAmount"` returns nothing.
4. **Unknown is never 0, blank or a dash.** W-3910 shows "Unknown" in the Toyota Hilux COST cell. That cell is not "₦0", "0.00", empty, "-" or "—". — verify: component test on W-3910.
5. **Sample-marked.** Every fixture page shows the shared `SampleLabel` ("SAMPLE DATA") because the record says `sample: true`. A copy with `sample: false` does not show it. — verify: component test; `jq '.sample' frontend/mock/fixtures/work/W-39*.json` all `true`.
6. **Each unset key is a hold with no controls.**
   - W-3907 shows the backend's "SETUP NEEDED", the "Who reviews assets · NOT SET" fact and its `next` sentence.
   - W-3908 shows "Register rules · NOT SET".
   - W-3909 shows "Calculation rules · NOT SET" with station 4 stopped.
   - On all three there is no Decide panel, no button and no claim or decide request. No reviewer's name or role appears anywhere. W-3909 shows no "PROCESSING", no "Calculation" facts and no figure.

   — verify: component tests with a recording `fetch` (zero POSTs); `document.body.textContent` checked for "Ada Okafor", "PPE reviewer" and "PROCESSING" (absent).
7. **Decide controls only from `you_can_act` and the steps.**
   - W-3902 shows "Approve register", "Return with a note" and "Reject" under "Decide · PPE reviewer".
   - W-3903 shows "Approve dates", "Return with a note" and "Reject". It has one Decide panel only, and no card, link or claim for the decided T-3931.
   - W-3905 shows "You prepared October register, so someone else must review it." and W-3912 shows the same for "October in-service dates". W-3906 shows the `not_your_role` copy. Each has no button and sends no claim.
   - The same pages for personas `finance_lead`, `ceo` and `pm` draw the same controls.
   - The new and changed code does not read `/me`.

   — verify: component tests with three personas and a recording `fetch` (W-3903 claims only `/api/v1/tasks/T-3903/claim`); `grep -rn "useMe\|/me\b" frontend/src/features/workspace/` shows no new match.
8. **Agent work is not a decision.**
   - On W-3901, Chidi's steps, sources ("VALUES NOT READ" included), "WORKING" and "Started 10:05" render in the agent card.
   - The values line is the section's `note` from data.
   - There is no decide control. "Ask Chidi" links to `/assistant`.
   - On W-3904 no agent is shown as calculating.

   — verify: component test; link href; a copy of W-3901 with the `note` removed shows no "never reads" text.
9. **Approved and calculating only when the response says so.**
   - Pressing "Approve dates" on W-3903 shows "PROCESSING" and "REGISTER · APPROVED" only after the re-read serves `W-3903.approve.json`.
   - Pressing "Approve register" on W-3902 shows the waiting state from `W-3902.approve.json` and no date-review panel.
   - If the decide answers 200 but the re-read still serves the review state (test double), the page does not say "approved", "APPROVED" or "PROCESSING".
   - On W-3911, each verdict shows "October register: result not confirmed" and the backend's "DECISION NOT CONFIRMED", before and after a reload.

   — verify: component tests with a recording `fetch`; e2e on W-3911.

### Writes
10. **Approve.** On W-3902 the page sends one E-TASK-CLAIM to `/api/v1/tasks/T-3902/claim`. Pressing "Approve register" then sends exactly one POST `/api/v1/tasks/T-3902/decision` with the CSRF header and `{verdict: "approve", expected_revision: 1}`. The body validates against the generated request schema, with no note and no extra keys. A double press sends one. The same holds for W-3903 and T-3903. — verify: component test; e2e request log.
11. **Return and reject need a note.**
    - Pressing "Return with a note" or "Reject" with an empty or blank note sends nothing. The note message appears under the field, is announced, and focus moves to it.
    - A note over 2000 characters is refused before sending.
    - With a note, one POST is sent with `verdict: "return"` (or `"reject"`) and the trimmed note. The re-read shows "RETURNED" with the quote (or "REJECTED"), with no correction step and no D-RETURN wording of our own.

    — verify: component tests; `grep -rn "every return\|backend only waits" frontend/src` returns nothing; the e2e request log shows no decision POST without a note.
12. **No write when the person cannot act.** On W-3901, W-3904, W-3905, W-3906, W-3907, W-3908, W-3909 and W-3912, no claim and no decision is sent, whatever is pressed or typed. — verify: e2e request log (zero task POSTs).
13. **Backend refusals are shown.**
    - With `psl_mock_scenario` 403, the decide shows the read-only view and no "approved".
    - A 409 shows the stale view and keeps the note. It sends again only on a new press with the new revision.
    - A 422 shows the message under the note.

    — verify: component tests; `tests/asset-schedule-mock.test.ts`.
14. **Uncertain decide.** A network failure, timeout or 500 on decide re-reads the item before anything else and shows `UncertainNotice`. It never shows "approved", "returned" or "rejected" from the click, and sends no second decision automatically. A later deliberate decide clears the earlier notice. — verify: component test with fake timers (one POST after 60 s); e2e with a routed abort.
15. **Access.**
    - 401 on read or write → signed out with `next=/work/<id>`.
    - 403 and 404 on read look the same and show no title, cost or fact.
    - Persona `none` gets the same not-open view with no further call.

    — verify: component tests with a recording `fetch`.

### Frame and layout
16. **Phone.** At 390:
    - each state is one column with the same sections, words and values as desktop, with the full costs;
    - the "STATION n OF 6" line shows;
    - the Decide bar is pinned with the step labels;
    - "Return with a note" and "Reject" open the full-height `Drawer` with the note, and Escape and Cancel close it and return focus to the button;
    - there is no sideways scroll, including the 3-column table;
    - every button, link, tab and segment is at least 44 by 44 px (D-92c; links inside sentences are exempt, D-95).

    — verify: e2e at 390 measuring bounding boxes and `scrollWidth`.
17. **Other lines unchanged.** The income schedule pages (`W-2701`…`W-2712`) and every other line workspace render as before. — verify: F-33's `tests/income-schedule.test.tsx` and `e2e/income-schedule.spec.ts` pass unchanged.

### Quality
18. **Fidelity (D-64, D-83).** There is one design-fidelity run per round over the 8 boards, on a production build at `--width 1440` and `--width 390`.
    - Every board's element coverage after approved exceptions is 100%.
    - Visual is at least 90, or there is a board-level waiver citing D-83 in `fidelity-exceptions.json` with visual at least 70. Lower needs a signed one-board floor exception.
    - Every exception has `role`, `name`, `category`, `reason` and `approved_by`, and maps to a Conflicts number.
    - No exception covers a value the data can supply (an amount, a name, a date, a tag, a count, a sentence).
    - The UI reviewer's side-by-side reading finds no fixable gap.

    — verify: the fidelity command per board; `round-<N>/fidelity/scores.txt`.
19. **Accessibility.** There are no axe violations (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`) at 1440 and 390 on these states: W-3901…W-3904, W-3907, W-3909, the open Drawer, the note error, the uncertain notice and the not-open view. Also:
    - the table has column headers;
    - every field is labelled;
    - errors are announced;
    - status words are in text, not colour only;
    - focus is visible;
    - the agent pulse does not animate under `reducedMotion: 'reduce'`.

    — verify: `e2e/asset-schedule.spec.ts`.
20. **Tokens and components only.** The diff adds no `#hex`, `rgb(`, `hsl(` or raw px outside tokens in `features/workspace/*.css`. It adds no local copy of a component that `@/components` exports (`Button`, `Drawer`, `TextArea`, `Callout`, `Panel`, `Tag`, `MiniStationBar`). — verify: grep on the diff.
21. **Mock matches the contract.** `tests/asset-schedule-mock.test.ts` checks that:
    - every new fixture and sidecar validates against the generated E-WORK-ITEM schema with `steps[].verdict` stripped;
    - task ids are unique across base fixtures;
    - claim then approve on W-3902 serves `W-3902.approve.json`, and on W-3903 serves `W-3903.approve.json`;
    - return without a note is 422;
    - a stale revision is 409;
    - W-3905's decide is 403;
    - W-3911's decides answer `work_state: effect_uncertain`;
    - reset clears.

    — verify: `cd frontend && npx vitest run tests/asset-schedule.test.tsx tests/asset-schedule-mock.test.ts tests/mock-contract.test.ts`.
22. **Contract not extended.** `git diff --stat` against the base (with F-33 merged) shows no change in any of these:
    - `frontend/src/api/**`, `frontend/src/features/decide/**`, `frontend/src/shell/**`, `InlineDecide.tsx`, `proposals.ts`;
    - `frontend/mock/server.mjs`, `frontend/mock/workspace.mjs`, `frontend/mock/fixtures/response/**` (`W-1604`), `frontend/mock/fixtures/finance/**`, `E-MONTH-END.json`, `mock/fixtures/setup/**`, any existing fixture;
    - `apps/**`, `architecture/**`, `design/**`, the protected paths.

    Every overlay field is listed as a contract proposal in build.md. — verify: `git diff --stat`; build.md.
23. **Existing tests green.** `delivery/checks.sh` passes. The tests listed under Context pass unchanged, including `tests/response-mock.test.ts` and `tests/response.test.tsx` (W-1604 no grant) and the month-end link assertions. — verify: `delivery/checks.sh`; `cd frontend && npx vitest run` and the e2e command under Lanes, pasted in build.md.
24. **build.md evidence.** build.md records:
    - the commands and their results;
    - the 8 scores and waivers;
    - every exception with its Conflicts number;
    - every proposal and backend item;
    - the held list from "What is sent";
    - the base SHA, showing F-33 merged;
    - the mock-seam choice (option (b)).

    — verify: file content.

## Out of scope
- **Part 2:** the schedule by asset class and its review, the returned board with "Correct and resubmit", the verified board, Withdraw approval (`revoke`), the furniture opening balance, the accounting note, the "Feeds MANAGEMENT ACCOUNTS" link, and the compact amounts "₦42.1M" and "₦0.0M".
- **Calculations in the browser:** any depreciation, opening, additions, disposals, closing, class total, row count or difference; useful life; which date starts depreciation; capitalisation; a short amount.
- **Steps with no board:** the explain-dates step and its form (G-55-1), any upload or download of the proof or the register file (E-EVIDENCE-UPLOAD), and a correction step after a return.
- **Policy:** naming or choosing a reviewer or a rule, editing Setup (SCR-13), a link to Setup (G-C-3), and filling in any NOT SET value.
- **Authority in the page:** separation-of-duties logic (comparing the signed-in person with `prepared_by`), and reading `/me` to show or hide a control.
- **Untouched records:** repointing the month-end row, changing `W-1604` or the response fixtures, and a new Finance preparer persona.
- **Untouched code:** changes to `InlineDecide`, `useDecision`, the F-16 decision page or the decide mock; automatic retries; optimistic states from a 200 body.
- **Other work:** the F-47B Start work drawer; backend, OpenAPI, `schema.d.ts` regeneration, `architecture/**`, `design/**`, `src/shell/**`, new npm dependencies.

## Assumptions
- **Ids:** work ids `W-3901`…`W-3912` (reserve to `W-3999`) and task ids `T-3902`…`T-3937`, unique across base fixtures. Reason: the caller assigned the W-39xx/T-39xx block, and the mock's `findTask` scans every base fixture.
- **Mock seam:** option (b), with the month-end row left on `W-1604`. Reason: `W-1604` is the response tests' no-grant fixture, and month-end tests pin the link (conflict 8).
- **Sidecars:** the register approval re-read is a `waiting` state with no task the person can act on. Reason: the explain-dates step has no board (G-55-1), and a second decide on the same mock id would re-serve the same sidecar.
- **Agent:** `item.agent.status: done` on calculating, with the factory doing the calculation. Reason: the board draws no agent card and says "Chidi doesn't see the values".
- **Values note:** "Chidi never reads asset values…" is the Register section's `note`. Reason: it is a typed field already drawn by `Sections.tsx`, and the guarantee itself is the backend's (G-55-6).
- **Proof:** a titled `text` section whose item carries one `cites` entry with `evidence_id` and the `detail` "Uploaded · 64 KB". Reason: the gaps file says the proof is a cite with the file name in `label`, and there is no download path in part 1.
- **Version labels:** "October register" and "October in-service dates". Reason: `VERDICT_WORDS` and `cannotActCopy` read `decision.version.label`, and no source names them. They are sample text, and the backend's labels win.
- **Required role:** "PPE reviewer" appears only in the sample review fixtures. Reason: it is the board's panel title, and it is sample data while Who reviews assets is NOT SET. The hold fixtures carry none.
- **Reject:** a rejected review uses `state: cancelled` with "REJECTED" (`stopped`). Reason: F-33 precedent, and no source says what a rejected register becomes.
- **Hold order:** all three holds stop at the station their rule gates: register rules and reviewer at Register review, calculation rules at Calculate. Reason: readiness question 2 is open, and this is the reading of `holds_work: true` in Setup.
- **Line sets:** F-42 extends F-33's line checks rather than adding a new frame branch. Reason: the SCR-55 boards draw the same frame as SCR-54 (station row, agent card beside, inline Decide).
- **Ports:** 4942/4943. Reason: no other spec uses them.
