# Leadership report: a PMO Lead follows Tola's draft, a leadership reviewer approves and sends it or returns it, and each recipient's delivery shows, with the Tuesday report published without review (contract mock only)

> Tasks: FE-LEADERSHIP-REPORT, part 1 (R-WORKITEM, R-REPORTS; acceptance A-WORKSPACE and A-REPORT, frontend half, with A-WORKITEM, A-DECIDE and the F-16, F-17, F-22, F-28, F-29 and F-33 tests kept green). Architecture: package `architecture/packages/v7`, manifest digest `f6231d20b4fdeabbdca9bde5986a0a7883536f1a5cafc883848ef62dd6d4b624`; FE-LEADERSHIP-REPORT at `architecture/packages/v7/delivery.md:2179-2211`, `gate_ids: []`, "Unresolved gates: none"; depends on FE-WORKSPACE-FRAME (F-17, merged, PR #30) and FE-M3-REPORT (F-26, merged, PR #50). Endpoints typed in `frontend/src/api/schema.d.ts`: E-WORK-ITEM `:54` (`workspace` `:1693-1912`, recipients `receipt` `:1842`, `agent` `:1508-1521`, `allowed_actions`/`reconcile` `:1542-1548`, `tasks[].cannot_act_reason` `:1419`, which already carries `prepared_by_you`), E-TASK-CLAIM `:96`, E-TASK-DECIDE `:117`, E-WORK-STEP `:715` (response `outcome` `:5258`), E-WORK-ACTION `:201` (not sent in part 1, Conflicts 6), E-REPORT `:631` (reference only). This feature changes no generated type. Decisions consumed: D-LINE-WORKSPACE (`proposed`, under the recorded exception `architecture/sources/decisions-2026-11-15.md` items (g), (i)); D-64, D-83, D-89, D-91, D-92 (b) and (c), D-111, D-112, D-113 (F-33's inline decide accepted). Open and held: D-REPORT-DELIVERY (suggested), D-ALERT-PROVIDERS (open), the Setup values for reviewer and audience (no decision id). Gaps: `delivery/backend-handoff/gaps-c-client-lines.md:134-149` (G-SCR52-1 to G-SCR52-7). Design: client-approved canvas version 1794581312-b166 (13 Nov 2026; SCR-52 at `design/review.json:60, 110`), republished with "+ Start" as 1794762832-cab1 (D-89). `python3 /Users/Hunchoo/software-factory/packages/design/design.py check --project /Users/Hunchoo/psl-factory` was run for this spec on 18 Nov: `EXCEPTION`, `passes: true` (design_sha256 `2859ab21…3d82`, D-89 frame-only change). Screens: SCR-52, 8 of 10 artboards in `design/canvas/project/`: `SCR-52-{desktop,mobile}-drafting`, `-review`, `-tuesday`, `-received`. Part 2 (`-setup`, G-SCR52-1, G-SCR52-2) is out. Models: `delivery/features/F-33/spec.md` (shape, inline decide), `F-30/spec.md`, `F-28/spec.md` (recipients and receipts).

## What is sent, and what stays held (read first)

- **Sent (to the local mock only):** the review claim (E-TASK-CLAIM), one decision per press (E-TASK-DECIDE, verdict `approve` or `return`, a note with return), and "Send for leadership review" (E-WORK-STEP `send_for_review`) only where the backend offers that step. No email, message or alert leaves the app; no report is delivered to anyone; no receipt is recorded by the page; nothing posts to E-WORK-ACTION.
- **Held, because a product or backend decision is open:** (1) who the leadership reviewer is: a Setup value with no decision id and no value, so the review fixtures are sample-marked and a "reviewer not set" fixture shows the backend's hold; (2) who the monthly and the Tuesday audience are (Setup values, no id); (3) whether Tuesday reports go out without review (shown only as the backend's words and status); (4) whose visibility builds the report, and whether left-out projects are a count only (G-SCR52-3); (5) the delivery channel (D-REPORT-DELIVERY suggested, D-ALERT-PROVIDERS open); (6) who confirms an uncertain internal delivery, and in what words (Conflicts 6). The page shows whatever the re-read work item says and adds no rule.
- **Held to part 2 or later:** the setup boards and "Start the report" (G-SCR52-1, G-SCR52-2); a `/reports/{id}` page, "Open the full report" / "Open the report" and the Overview reports list (G-SCR52-5).

## Conflicts with the boards (for the design engineer, before the build)

"Recommend" is what this spec builds if no answer comes. Each becomes a `fidelity-exceptions.json` entry (`approved_by: "builder proposal, pending design engineer"` until signed). Items 1 to 8 change what a person sees or can do and need an answer; items 9 to 14 are layout; items 15 to 17 are exceptions to sign. "Contract" means a proposal field built on the mock only; the backend developer may change or refuse it.

### Need an answer

1. **The review board decides on the page: "Approve and send" and "Return with a note".** **Recommend:** reuse F-33's inline Decide panel as accepted in D-113 (`InlineDecide` over the F-16 `useDecision`: claim, then decide). The buttons exist only when the task's `you_can_act` is true, with the step labels as returned. Pressing "Approve and send" never says "sent" or "received". After the re-read, the notice is the existing "Monthly report v1 is approved". The page then shows whatever the backend says about delivery. **Option B:** link to the separate decision page (F-23 pattern); the drawn panel becomes a listed difference.
2. **The drafting note promises that projects you can't see are "named as left out".** Naming a project the author cannot see tells them it exists (INV-ACCESS, G-SCR52-3). **Recommend:** the sentence is the backend's text. The fixture says "The report only uses records you can see. Projects you can't see are left out and counted as left out, never counted as zero." A second review fixture shows "Projects covered 3 OF 5" with the backend's coverage line "2 projects are left out because you can't see them", with no names. **Option B:** the board's words, word for word, as sample text, with the question left to PSL and the backend.
3. **"Send for leadership review" is drawn as Tola's fourth step, not as a button.** **Recommend:** draw it as the boards do, as the agent's step. A "Send for leadership review" button appears only when the backend sends a `send_for_review` workspace step (one extra fixture, no board). That button sends one E-WORK-STEP, and the re-read shows the item in review. **Option B:** no person step in part 1. Tola hands the report over by itself and nothing is sent from the drafting page.
4. **"Who reviews" is not set, and no board draws that state.** **Recommend:** one extra fixture where the backend returns `state: setup_needed`, status "SETUP NEEDED", a fact "Leadership reviewer · NOT SET" and its `next` sentence. The page draws exactly that: no Decide panel, no button, and no reviewer's name or role. This state has no board and is not in the fidelity run. **Option B:** the design engineer draws the hold first, and the feature waits.
5. **"Open the full report" (review) and "Open the report" (received) link to a report page that does not exist** (F-26 left it out, G-SCR52-5). **Recommend:** not drawn; listed difference. The received page keeps the backend's "Read it any time on Overview." **Option B:** drawn as disabled buttons with "Not available yet".
6. **Tuesday: one delivery is "CHECKING", and the board offers nothing to press.** The existing "Confirm what happened" panel is written for client sends ("the client received it", "the client is never invoiced twice"), so it would read wrongly here. **Recommend:** no leadership report fixture sends `reconcile` or `allowed_actions` in part 1, so that panel never shows on this line. The checking row and the backend's "It won't resend until it knows." are the whole state. There is no resend or confirm control. Who confirms an internal delivery goes to the backend list (G-SCR52-6). **Option B:** one fixture sends `reconcile`, and the panel's two client sentences get neutral wording. That touches the F-15 response panel and `tests/response.test.tsx:761`.
7. **Tuesday's header is green "PUBLISHED · NO REVIEW" while one delivery is still checking, and "CHECKING" is drawn blue.** **Recommend:** keep the header as drawn: green, label as returned (published is true; it never says "received"). Draw "CHECKING" in the amber "waiting" colour, as D-92 (b) fixes for every uncertain effect. That is a listed difference. **Option B:** an amber header too, while any delivery is checking.
8. **No board draws the moment after "Approve and send", and the received board lists no recipients.** **Recommend:** the re-read after approving shows the backend's "SENT · CHECKING DELIVERIES" state. Its recipients section lists the four audience roles (CEO, CTO, PMO Lead, Finance Lead; no names, since the audience is unset), each "Not yet". A second fixture shows one delivery not confirmed. "Received by every recipient" comes only from the received fixture. The received page is drawn as the board draws it: one sentence and Next, with no recipients list. **Option B:** the mock goes straight from approve to the received board, and the received page adds the recipients list.

### Layout (phone against desktop, frame)

9. **Phone titles differ from desktop** ("Monthly report", "Review report", "Tuesday report", "Report received"). The phone status labels are "REVIEW", "PUBLISHED" and "DONE". **Recommend:** the work item's `title` and `workspace.status` at both widths (D-111). Listed (`frame item`).
10. **The phone boards drop desktop content.** Phone drafting has no access note. Phone review has no Decide heading, no basis, no note and no "Return with a note". Phone tuesday reduces the note, recipients and Next to "Sent without review. 5 of 6 delivered, 1 checking." Phone received says only "Delivered to all 4 recipients. Verified." **Recommend:** the phone shows the same sections, words and values as desktop in one column (D-111, F-28/F-30/F-33 precedent). The Decide bar is pinned with both step labels; "Return with a note" opens the full-height `Drawer` with the note (F-29 pattern, as F-33 built). Listed (`extra element`).
11. **Frame items:** the crumbs "OVERVIEW / LEADERSHIP REPORTS / RPT-M-2026-10" come from `workspace.context.crumbs`, and there is no project tab bar. The phone back link ("← Overview", "← My work"), the top bar's nav items (the review board leaves out Overview and Setup) and the History link follow the F-17 frame as built. The signed-in name ("Kemi Adebayo · PMO Lead", "Ifeoma Nwosu · PMO Lead") comes from `/me`. The mock has no PMO Lead persona, so the pages run as persona `ceo` (Folake Bello) and no persona is added. The Tuesday board's crumb repeats the monthly id `RPT-M-2026-10`; the fixture uses its own reference `RPT-T-2026-11-10`. Listed (`frame item`, `sample data`).
12. **The drafting note is drawn as a blue information box.** The workspace banner today is amber unless the status is verified. **Recommend:** on `leadership_report` only, a status with tone `agent` or `neutral` draws the banner as the shared `Callout` `info`. Verified stays green; stopped or uncertain is `problem`. Other lines are unchanged.
13. **"Started 01 Nov 08:00" (desktop) and "Started 01 Nov" (phone).** The F-33 card footer shows the time only. **Recommend:** on this line the footer uses the existing `formatDayTime` ("Started 01 Nov 08:00") at both widths. Listed on the phone.
14. **Small words and extras.** The review note label says "(needed to return or refuse)". "Refuse" is not offered, so the F-33 label shows "Note (needed to return)". Recipient rows show the returned time, or the existing "Time unknown" when there is none; the board draws no time. Listed (`component`).

### Exceptions to sign

15. **Every board string is data.** These come from fixtures: the status labels ("DRAFTING", "YOUR REVIEW", "PUBLISHED · NO REVIEW", "RECEIVED BY EVERY RECIPIENT"), the access, Tuesday and received sentences, the figures ("5 OF 5", "3", "2", "2"), "Invoices verified · paid is reported by Finance", the recipients ("5 PMO staff", "Sola Martins"), the receipt tags ("DELIVERED", "CHECKING"), Tola's steps and their sources, the Decide basis, and the Next lines. No board string is in `src/`. Case and time formats follow the library (`When`, `Tag`); category `component`.
16. **Agent card.** "Tola · PMO agent · step 3 of 4", "WORKING", the four steps and their sources are drawn by the existing `AgentCard` from `item.agent`. The step count is the card's existing position in the returned list, not business data. "Ask Tola" is the existing `workspace.links` `assistant` link to `/assistant`, with no work-item context. Agent work is never shown as a decision, a delivery or a verified result.
17. **Visual waivers.** Scores under 90 are waived board by board in `fidelity-exceptions.json` citing D-83 and the shared frame, once the design engineer signs. A board under the 70 floor needs its own floor exception (as D-112 did).

## Boards

| Board | File (`design/canvas/project/`) | Page | Mock |
|---|---|---|---|
| SCR-52 drafting, desktop / phone | `SCR-52-desktop-drafting.dc.html`, `SCR-52-mobile-drafting.dc.html` | `/work/W-3201` | persona `ceo` |
| SCR-52 review | `SCR-52-desktop-review.dc.html`, `SCR-52-mobile-review.dc.html` | `/work/W-3202` | persona `ceo` |
| SCR-52 tuesday | `SCR-52-desktop-tuesday.dc.html`, `SCR-52-mobile-tuesday.dc.html` | `/work/W-3203` | persona `ceo` |
| SCR-52 received | `SCR-52-desktop-received.dc.html`, `SCR-52-mobile-received.dc.html` | `/work/W-3204` | persona `ceo` |

All 8 are live URLs, and no driver is needed. Each fidelity run starts with `POST /__mock/reset`, so `W-3202` is not served from a decided override.

## Summary
- A PMO Lead opens "Monthly leadership report · October" and sees Tola's work in progress, with the coverage stated as the backend words it. Where the backend offers it, they send the report for leadership review.
- A leadership reviewer who may act approves and sends that exact version, or returns it with a note, in place, through F-33's inline Decide panel over the F-16 decide flow. The page shows "sent", "delivered" or "received" only when the re-read item says so.
- The Tuesday report shows as published without review, with one row per recipient or group. A delivery still being checked reads "CHECKING", is never counted as received, and offers no resend.
- The reviewer and audience are unset Setup values. Every fixture is sample-marked; a "reviewer not set" fixture shows the backend's hold with no control and no invented approver. Controls come only from `tasks[].you_can_act` and the steps sent; nothing reads `/me`.
- New: the line's layout branches (on F-33's code), 12 fixtures `W-3201`…`W-3212` with decide and step sidecars, and tests. No mock server change, no contract change. Contract mock only.

## Context
- **Base must include F-33.** The inline Decide panel (`frontend/src/features/workspace/InlineDecide.tsx`), `stepVerdict` in `proposals.ts`, the `AgentCard` `foot` prop, the agent-card-beside branch (`INCOME_LINE`, `agentSide`, `splitAsk`) and the `already_decided` task filter in `WorkItemOverview.tsx` exist only on F-33's branch `fe-fin-schedules-income-detail-review` (READY_FOR_ACCEPTANCE, not yet merged into `dlv-00-delivery-setup`). This build starts from a base that has F-33 merged. It does not copy those files.
- Work item page and frame: `frontend/src/features/work-item/WorkItemView.tsx` (`LineHeader`, crumbs as text from `workspace.context.crumbs`, no `ProjectBar` without `context.project`), `WorkItemOverview.tsx` (`AgentCard`, `AgentSteps`, `ReconcilePanel` mounted at `:730`, shown only with `reconcile` and `allowed_actions` `reconcile`). Workspace: `frontend/src/features/workspace/Workspace.tsx` (`bannerTone`, the side column `ws-side`, the phone pinned bar, the uncertain notices at `:388-418`), `Sections.tsx` (`recipients` row at `:337-348`: the backend's `tag` stands in for the receipt word, `RECEIPT_WORDS` never reads `uncertain` as received; `figures` row at `:350-357`: `value` string or `Unknown`; `SectionView` `banner` at `:443-452`), `labels.ts` (`STEP_TEXT.next` "Next", `WS_TEXT.timeUnknown`, `tagTone`: `uncertain` → `waiting`), `Steps.tsx`, `useWorkspaceStep.ts` (key, revision, replay, `effect_uncertain`), `usePageReload.ts`, `Links.tsx`.
- **Shared rows used as they are:** the "Next" panel heading (`STEP_TEXT.next`, `Workspace.tsx:360-363`) carries the backend's `next` lines unchanged on tuesday and received. The shared `recipients` row is used unchanged. The shared `timeline` row is not used, since no fixture sends a `timeline` section.
- Decide flow (reuse, do not change): `frontend/src/features/decide/useDecision.ts` (claim once per task revision, one write at a time, a re-read after an uncertain write, no automatic resend), `DecideStates.tsx` (`cannotActCopy`, `UncertainNotice`), `format.ts` (`NOTE_MAX` 2000, `VERDICT_WORDS`: approve → "<label> is approved", never "sent"). E-TASK-DECIDE has no idempotency key in v7 (F-33 PMO-3-1); a double send is guarded by `expected_revision` and one write per press.
- Mock: `frontend/mock/server.mjs` `taskResponse` (`:147-183`) validates the body and the note rule, checks `expected_revision` (409) before `you_can_act` (403), then swaps in `<id>.<verdict>.json` and answers `work_state` from it. **A `<id>.next.json` makes the first decide answer 409**, so no fixture with a decide task has one. `frontend/mock/workspace.mjs` E-WORK-STEP serves the `<id>.steps.json` scripts (including `outcome: effect_uncertain`, as `W-2205.steps.json`) and `<id>.next.json`. The Start work drawer's `leadership_report` opens `W-1408` (`mock/start-work.mjs:35`), which stays unchanged. Ids `W-3201`…`W-3299` and `T-3201`…`T-3299` are free; the caller assigned them.
- Existing names reused in fixtures: "Sola Martins" (P-0124's team, `mock/fixtures/projects/P-0124.json`). No project or client is shown: the report covers several projects and draws no project bar.
- Tests that must stay green: `tests/workspace.test.tsx`, `tests/workspace-step.test.tsx`, `tests/workspace-mock.test.ts`, `tests/decide.test.tsx`, `tests/decide-board.test.tsx`, `tests/mock-decide.test.ts`, `tests/document-review.test.tsx`, `tests/response.test.tsx`, `tests/response-mock.test.ts`, `tests/mock-contract.test.ts`, F-33's `tests/income-schedule.test.tsx` and `tests/income-schedule-mock.test.ts`, `e2e/workspace.spec.ts`, `e2e/response.spec.ts`, `e2e/income-schedule.spec.ts`, `e2e/issue-detail.spec.ts`, and the start-work tests that pin `W-1408`.

## Contract

### E-WORK-ITEM `GET /api/v1/work/{work_id}` (unchanged)
Read by `useWorkItem`. The page draws `workspace` in returned order for `line_key: "leadership_report"` and branches on nothing else.
- 401 → the signed-out state with `next=/work/<id>`.
- 403 and 404 look the same (`NoAccessState`: no title, no figure, no recipient, no further call).
- 5xx → `WorkErrorCard` with Retry. Loading → `LoadingState`.
- After any write the page re-reads (`usePageReload`). No state is drawn from a 200 body or from the click.

### Fixtures
All fixtures share these values:
- `sample: true`, `screen: "SCR-52"` and `workspace.line_key: "leadership_report"`. No `context.project` and no `case_id`.
- Crumbs: Overview / Leadership reports / `<reference>`.
- Monthly fixtures: `reference: "RPT-M-2026-10"`, `title: "Monthly leadership report · October"`. Stations: Gather, Draft, Leadership review, Send, Received.
- Tuesday fixture: `reference: "RPT-T-2026-11-10"`, `title: "Internal Tuesday report · 10 Nov"`. Stations: Gather, Draft, Publish, Received.
- `facts` use the six fact names with statuses true to the state; Tuesday's `reviewed` and `approved` are `not_yet`, as the schema has no "not applicable" fact.

| Id | `state`, `workspace.status` (label, tone) | Sections and agent | Tasks and steps |
|---|---|---|---|
| W-3201 drafting | `processing`, "DRAFTING" `agent` | One untitled note-only section, the access sentence (Conflicts 2). `item.agent` working, `name` Tola, 4 steps: "Gathered October's records" done, source "5 PROJECTS · 41 MEETINGS · 12 ISSUES"; "Summarised milestones and money" done, source "3 MILESTONES COMPLETE · 2 INVOICES VERIFIED"; "Drafting the escalations section" working, source "ESC-0011 · ESC-0012"; "Send for leadership review" not started. `started_at` `2026-11-01T07:00:00Z` (08:00 Lagos). `workspace.links` `assistant` "Ask Tola" | `tasks: []`; no steps |
| W-3202 review (can act) | `action_needed`, "YOUR REVIEW" `person` | `figures` "Monthly report v1": Projects covered "5 OF 5"; Milestones completed "3"; Open escalations "2"; Invoices verified · paid is reported by Finance "2". Agent done | `T-3202` `kind: decide`, `required_role: "Leadership reviewer"`, `you_can_act: true`, `revision: 1`, `decision.version.label` "Monthly report v1", `decision.basis` "Approving sends this exact version to the audience. Who reviews is set in Setup › Rules." Steps: `approve_send` (primary, `verdict: approve`, label "Approve and send", `sends: true`) and `return_note` (secondary, `verdict: return`, label "Return with a note"), both `task_id: T-3202`. Sidecars: `W-3202.approve.json` = `processing`, "SENT · CHECKING DELIVERIES" `agent`, `recipients` "Recipients": CEO, CTO, PMO Lead, Finance Lead, each `receipt: not_yet`, `next` ["The factory marks it received when every delivery is confirmed."]. `W-3202.return.json` = `processing`, "DRAFTING · RETURNED" `agent`, untitled text "Returned on 02 Nov: “Add the Lagoon Health escalation to the summary.”", Tola working again. Each sidecar is one revision higher, with the task `you_can_act: false`, `cannot_act_reason: already_decided`. **No `W-3202.next.json`.** |
| W-3203 tuesday | `waiting`, "PUBLISHED · NO REVIEW" `verified` | Note-only section: "Internal Tuesday reports go out without review. Sent to 6 PMO staff on 10 Nov 09:00; 5 deliveries confirmed, 1 still checking." `recipients` "Recipients": "5 PMO staff", `receipt: received`, tag "DELIVERED" `verified`, `at` `2026-11-10T08:00:00Z`; "Sola Martins", `receipt: uncertain`, tag "CHECKING" `uncertain`, no `at`. `next` ["The factory checks the last delivery before marking it received. It won't resend until it knows."] | `tasks: []`; no steps; **no `allowed_actions`, no `reconcile`** |
| W-3204 received | `verified`, "RECEIVED BY EVERY RECIPIENT" `verified` | Note-only section: "October's report was approved by Ifeoma Nwosu and delivered to all 4 recipients on 03 Nov, verified." `next` ["Read it any time on Overview."]. No links | `tasks: []`; no steps |
| W-3205 draft ready | `action_needed`, "DRAFT READY" `person` | As W-3201, but the agent is done (all 4 steps done) | Step `send_for_review` (primary, `applies_to: workspace`, label "Send for leadership review", consequence "It goes to the leadership reviewer set in Setup › Rules."). `W-3205.steps.json` scripts 200 `done`. `W-3205.next.json` = W-3206's content, one revision higher |
| W-3206 review, you prepared it | `action_needed`, "AWAITING LEADERSHIP REVIEW" `person` | As W-3202 | `T-3206` `you_can_act: false`, `cannot_act_reason: prepared_by_you`; the same two verdict steps are sent |
| W-3207 reviewer not set | `setup_needed`, "SETUP NEEDED" `stopped`; station 3 `stopped` | `facts` "Why it's held": "Leadership reviewer", value "NOT SET", tag `stopped`. `next` ["An admin sets who reviews leadership reports in Setup › Rules. The review starts then."]. Agent done | `tasks: []`; no steps; no `required_role` and no reviewer anywhere |
| W-3208 not your role | `action_needed`, "AWAITING LEADERSHIP REVIEW" `person` | As W-3202 | `T-3208` `you_can_act: false`, `cannot_act_reason: not_your_role`; steps sent |
| W-3209 approve not confirmed | As W-3202 | As W-3202 | `T-3209` can act; the same two steps. `W-3209.approve.json` = `effect_uncertain`, "SENT · DELIVERY NOT CONFIRMED" `uncertain`, recipients CEO, CTO and PMO Lead `received` (tag "DELIVERED"), Finance Lead `uncertain` (tag "CHECKING"), `next` ["The factory checks the last delivery before marking it received. It won't resend until it knows."], no `reconcile`. The decide answers `work_state: effect_uncertain` |
| W-3210 partial coverage, unknown | As W-3202 | As W-3202, but the figures section has `coverage` "2 projects are left out because you can't see them.", Projects covered "3 OF 5", and Open escalations with no `value` | `T-3210` can act; the same two steps |
| W-3211 monthly, one checking | As `W-3209.approve.json` (standalone, so QA can open it directly) | As `W-3209.approve.json` | `tasks` with `T-3211` `already_decided`; no steps |
| W-3212 send for review, uncertain | As W-3205 | As W-3205 | Step `send_for_review`. `W-3212.steps.json` scripts 200 `{outcome: "effect_uncertain", message: "We couldn't confirm the report reached the reviewer."}`; no `next.json` |

Each fixture and sidecar validates against the generated E-WORK-ITEM 200 schema once the overlay is stripped. No fixture carries money: every figure and count is a `value` string (G-SCR52-4).

### Overlay proposals (mock only; each recorded in build.md for the backend developer)
- `workspace.steps[].verdict` (F-33 G-C-1), reused as built: `approve` and `return` only on this line; any other value is not drawn.
- **Values the boards show that no endpoint supplies as typed data:**
  - "5 OF 5", "3", "2": figures `value` strings, never counted by the page.
  - The coverage count and the left-out sentence: section `coverage` and `text` (G-SCR52-3).
  - "5 PMO staff" and "5 deliveries confirmed, 1 still checking": backend text, never summed from the rows.
  - "verified" and "received by every recipient": `state` and `status` only.
- For the backend list (not built): G-SCR52-3 (whose visibility, count only), G-SCR52-4 (count/text values in E-REPORT, verified kept apart from paid), G-SCR52-5 (report page, approved version is the one sent, Overview list, X-LINKS `report`), G-SCR52-6 (no "received" while uncertain, no resend before reconcile, who reconciles an internal delivery and its words, Conflicts 6), G-SCR52-7 (already typed as `prepared_by_you`; nothing to add), a "not applicable" fact status for reports with no review, and the readiness questions 1 to 5.

### E-TASK-CLAIM `POST /api/v1/tasks/{task_id}/claim` and E-TASK-DECIDE `POST /api/v1/tasks/{task_id}/decision`
- **Through F-33's `InlineDecide` and `useDecision(work_id, task_id)` only.** No new write path. The claim is sent once per task revision, only when that task's `you_can_act` is true. Until it answers, the buttons are off with the existing "Getting this review ready…" line.
- **Request:** `{verdict, note?, expected_revision: <task revision as read or claimed>}`, header `X-CSRFToken`, no extra keys. `note` is required and non-blank for `return`, at most `NOTE_MAX` (2000). It is checked before any request, with "Add a note to return it." under the field, announced, and focus on the note. Approve sends no note.
- **200:** the item is re-read, and the page draws the re-read state. The done notice is "Monthly report v1 is approved" only when the re-read is settled (F-33 `settled`). With a re-read of `effect_uncertain`, or a decide answering `work_state: effect_uncertain`, the notice is "Monthly report v1: result not confirmed", and the page shows the backend's uncertain state. "Sent", "delivered" and "received" come only from the re-read's `status`, text and `receipt`s.
- **Errors:**
  - 401 → signed-out.
  - 403 → the read-only view keyed on the re-read `cannot_act_reason`.
  - 409 → the existing stale view; the note is kept and nothing is resent automatically.
  - 422 → the backend message under the note.
  - 5xx, network or timeout → re-read first and show `UncertainNotice`. Never "approved", "sent" or "returned" from the click; the next decide only on a new deliberate press.
- **Permission and tenant:** buttons only when `tasks[i].you_can_act` is true for the step's `task_id`. Otherwise `cannotActCopy(cannot_act_reason, task)` and no button. The page holds no role, reviewer, audience or "Tuesday skips review" rule, and does not read `/me`.

### E-WORK-STEP `POST /api/v1/work/{work_id}/steps` (`send_for_review`, only where offered)
- **Request:** `{expected_revision: workspace.revision, step: "send_for_review", idempotency_key: <UUID, new per press, reused on a manual retry of the same press>}`, header `X-CSRFToken`, through the existing `useWorkspaceStep`. No `inputs`; the frontend sends no reviewer and no audience.
- **200 `done`:** re-read; the page shows the item in review as the re-read says (W-3205 → `W-3205.next.json`, the `prepared_by_you` copy). The notice is the response `message` or the F-17 default, and never "sent to <name>".
- **200 `effect_uncertain`** (W-3212): the existing uncertain notice after a re-read ("We are checking what happened. Nothing was sent again."), never "sent for review", and no automatic resend.
- **Errors (as F-30):** 409 → re-read and the stale sentence. 422 → the message. 5xx, network or timeout → "Not recorded" after a re-read, and Try again with the same key.

### E-WORK-ACTION `POST /api/v1/work/{work_id}/actions`
Not sent in part 1 (Conflicts 6). No fixture carries `reconcile` or `allowed_actions`, so `ReconcilePanel` renders nothing on this line. There is no resend control of any kind.

### Screen states
- **Loading:** the existing skeleton.
- **Empty:** a workspace with no sections draws the header and status only.
- **Error:** the problem card with Retry.
- **Success:** the four board states, plus W-3205, W-3206 and W-3208 to W-3212.
- **Held:** W-3207.
- **Uncertain:** W-3203 (one receipt checking), W-3209 (approve not confirmed), W-3211, W-3212 (step not confirmed).
- **Restricted:** a section or item with `restricted: true` draws "Restricted", and its value is never shown.

## Lanes
- **Frontend lane (builder, Opus for the first build: high risk, D-64)** owns:
  - `Workspace.tsx`: turn F-33's `INCOME_LINE` checks into two small sets, "agent card beside while working, Ask in the card" (`income_schedules`, `leadership_report`) and "stations drawn" (`income_schedules` only). Add the `leadership_report` banner tone (Conflicts 12) and the `formatDayTime` footer (Conflicts 13).
  - `WorkItemOverview.tsx`: the same sets for its F-33 branches.
  - `Sections.tsx`: `SectionView` `banner` accepts `info`; additive.
  - Additive rules in `workspace.css`, tokens only.
  - Fixtures `frontend/mock/fixtures/work/W-3201…W-3212`, with the `.approve`, `.return`, `.steps` and `.next` sidecars named above.
  - Tests: `frontend/tests/leadership-report.test.tsx`, `frontend/tests/leadership-report-mock.test.ts`, `frontend/tests/mock-contract.test.ts` (new fixtures only, `steps[].verdict` stripped as F-33 does), `frontend/e2e/leadership-report.spec.ts`.
  - Factory files in `delivery/features/F-35/` (`fidelity-exceptions.json`, `round-<N>/`).
- **Shared, read only:** `InlineDecide.tsx` and `proposals.ts` (change only if a test proves a defect; list it), `src/features/decide/**`, `src/features/response/**` (including `ReconcilePanel`), `src/features/documents/**`, `src/components/**`, `src/shell/**`, `src/api/**` (including `schema.d.ts`), `src/styles/**`, `Steps.tsx`, `StepForm.tsx`, `mock/server.mjs`, `mock/workspace.mjs`, `mock/start-work.mjs`, every existing fixture (including `W-1408`), `frontend/package.json`, the lock file, `playwright.config.ts`, `vitest.config.ts`, `architecture/**`, `design/**`, `apps/**`, and the protected `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json`.
- **Backend lane:** none. Items for build.md (none blocks part 1): the G-SCR52 items listed under Overlay, the `setup_needed` shape for "Leadership reviewer", the state and `view` names for drafting, review, sent, tuesday and received, and the readiness questions 1 to 5.
- **Integration owner:** the coordinator. This build starts only once F-33 is merged into the base. `Workspace.tsx`, `WorkItemOverview.tsx`, `Sections.tsx`, `workspace.css` and `mock-contract.test.ts` are likely touched by F-31, F-32 and other parallel features: whichever merges second merges the current base and reruns `delivery/checks.sh` and the e2e.
- **Ports:** app 4935, mock 4936. `cd frontend && E2E_PORT=4935 MOCK_PORT=4936 npx playwright test e2e/leadership-report.spec.ts e2e/workspace.spec.ts e2e/response.spec.ts e2e/income-schedule.spec.ts`, with `timezoneId: 'Africa/Lagos'`. Fidelity runs on a production build, one run per round over all 8 boards (D-64). Run `df -h /System/Volumes/Data` first (stop under 3 GB) and delete `frontend/test-results` after. e2e is not in `checks.sh`, so paste its output in build.md.
- **Review routing (high risk):** technical (Sonnet), UI (fidelity gate, Opus for the first review), UX (Sonnet), QA (Opus), security (Opus: an authority-bearing approve-and-send, and record visibility in a cross-project report), PMO. Product acceptance is required. It merges only on the design engineer's "merge".
- **Size:** about 800 to 1,100 lines, most of it fixtures and tests. One PR.

## Acceptance criteria

### Page
1. **Four states from data.** `/work/W-3201`…`W-3204` show their fixture's status label and tone, sections, agent card, recipients and Next, and nothing else. No board string is in `src` (`grep -rn "YOUR REVIEW\|PUBLISHED · NO REVIEW\|RECEIVED BY EVERY RECIPIENT\|PMO staff\|Leadership reviewer\|paid is reported by Finance" frontend/src` returns nothing). — verify: `cd frontend && npx vitest run tests/leadership-report.test.tsx`; the pages at 1440 and 390.
2. **The page computes nothing.** Changing W-3202's "5 OF 5" to "4 OF 5" changes only that value. Changing W-3203's "5 PMO staff" row receipt changes neither the note sentence nor the header. No new or changed file under `frontend/src/features/workspace/` adds `parseFloat`, `Number(`, `reduce(` or a count of recipients or projects. — verify: component tests on modified copies; `git diff -U0 frontend/src | grep -nE "parseFloat|Number\(|\.reduce\("` returns nothing.
3. **Unknown is never 0, blank or a dash; hidden projects are never named.** W-3210 shows "Unknown" for Open escalations, with no "0", empty cell, "-" or "—" in its place. It shows the backend's coverage line "2 projects are left out because you can't see them." and "3 OF 5". The page contains no project name. — verify: component test on W-3210; `document.body.textContent` checked against every name in `mock/fixtures/projects/list.json` (absent).
4. **Sample-marked.** Every fixture page shows the shared `SampleLabel` because the record says `sample: true`; a copy with `sample: false` does not. — verify: component test.
5. **Reviewer not set is a hold.** W-3207 shows the backend's status, the "Leadership reviewer · NOT SET" fact and its `next` sentence. There is no Decide panel, no button, no claim or decide request, and no reviewer's name or role anywhere on the page ("Ifeoma", "Leadership reviewer" as a panel title and "Approve and send" are absent). — verify: component test with a recording `fetch` (zero POSTs) and a text check.
6. **Decide controls only from `you_can_act` and the steps.** W-3202 and W-3210 show "Approve and send" and "Return with a note" under "Decide · Leadership reviewer", with the basis sentence as returned. W-3206 shows the `prepared_by_you` copy and W-3208 the `not_your_role` copy, each with no button and no claim sent. W-3201, W-3203, W-3204 and W-3211 show no decide control. Personas `ceo`, `pm` and `finance_lead` see the same controls on the same page. The changed files do not read `/me` (`git diff frontend/src | grep -n "useMe\|/me\b"` returns nothing). — verify: component tests with three personas and a recording `fetch`.
7. **Agent work is not an output.** On W-3201, Tola's steps, sources and "WORKING" render in the agent card in the side column at 1440. "Send for leadership review" is the agent's fourth step there, not a button, and no write is possible. "Ask Tola" links to `/assistant`. "Started 01 Nov 08:00" shows in Lagos time. The agent pulse does not animate under `reducedMotion: 'reduce'`. — verify: component test; e2e link href and computed style.
8. **Nothing says sent, delivered or received unless the response says so.**
   - W-3203's header is "PUBLISHED · NO REVIEW". Sola Martins reads "CHECKING" in the amber waiting colour, and "received" appears nowhere on the page.
   - W-3211 and `W-3209.approve.json` never say "received" or "delivered to all".
   - "RECEIVED BY EVERY RECIPIENT" appears only on W-3204.
   - With E-TASK-DECIDE answering 200 but the re-read still serving the review state (test double), the page says neither "sent" nor "received".
   - verify: component tests with a recording `fetch`; `grep -rn "sent\b\|delivered\|received" frontend/src/features/workspace --include=*.tsx` shows no new literal outside `RECEIPT_WORDS`.
9. **No resend, no confirm, no action write.** On W-3203, W-3209 (after approve), W-3211 and W-3212 there is no "Resend", "Send again", "Try sending" or "Confirm what happened" control. The page sends no request to `/api/v1/work/<id>/actions`. — verify: e2e request log; component test.
10. **No report link yet.** W-3202 and W-3204 draw no "Open the full report" or "Open the report" link and no link to `/reports/`. W-3204 shows "Read it any time on Overview." as returned. — verify: component test.

### Writes
11. **Approve and send.** On W-3202 the page sends one E-TASK-CLAIM to `/api/v1/tasks/T-3202/claim`. Pressing "Approve and send" then sends exactly one POST `/api/v1/tasks/T-3202/decision` with the CSRF header and `{verdict: "approve", expected_revision: 1}`. The body validates against the generated request schema, with no note and no extra keys. A double press sends one. The re-read shows "SENT · CHECKING DELIVERIES" with four "Not yet" rows, and the notice "Monthly report v1 is approved" appears only after that re-read. — verify: component test; e2e request log.
12. **Return needs a note.** Pressing "Return with a note" with an empty or blank note sends nothing and shows "Add a note to return it." under the field, announced, with focus on it. A note over 2000 characters is refused before sending. With a note, one POST with `verdict: "return"` and the trimmed note is sent, and the re-read shows "DRAFTING · RETURNED" with the returned sentence. — verify: component tests; the e2e request log shows no decision POST without a note.
13. **No write when the person cannot act.** On W-3206, W-3207 and W-3208, no claim and no decision is sent, whatever is pressed or typed. — verify: e2e request log (zero task POSTs).
14. **Backend refusals are shown.** With `psl_mock_scenario` set to 403, the decide shows the read-only view and no "approved". With 409 it shows the stale view, keeps the note, and sends again only on a new press with the new revision. With 422 it shows the message under the note. — verify: component tests; `tests/leadership-report-mock.test.ts`.
15. **An uncertain decide never reads as success.** On W-3209, "Approve and send" answers `work_state: effect_uncertain`. The page re-reads, shows "Monthly report v1: result not confirmed" (never "is approved", "sent" or "received"), and shows the backend's "SENT · DELIVERY NOT CONFIRMED" with Finance Lead "CHECKING". On W-3202, a network failure, timeout or 500 on decide re-reads the item before anything else, shows `UncertainNotice`, and sends no second decision automatically. — verify: component tests with fake timers (one POST after 60 s); e2e on W-3209, and with a routed abort on W-3202.
16. **Send for leadership review, only where offered.** W-3205 shows "Send for leadership review" with its consequence. One press sends one POST `/api/v1/work/W-3205/steps` with CSRF, `expected_revision`, `step: "send_for_review"`, a UUID `idempotency_key` and no `inputs`, reviewer or audience. A retry after a 500 reuses the same key. On 200 the re-read shows "AWAITING LEADERSHIP REVIEW" with the `prepared_by_you` copy. On W-3212 the `effect_uncertain` answer shows the uncertain notice after a re-read, never "sent for review", and sends no second POST. — verify: component tests; e2e request log.
17. **Access.** A 401 on read or write → signed-out with `next=/work/<id>`. A 403 or 404 on read looks the same and shows no title, figure, recipient or sentence. Persona `none` gets the same not-open view with no further call. — verify: component tests with a recording `fetch` for 401, 403 and 404.

### Frame and layout
18. **Phone.** At 390 each state is one column with the same sections, words and values as desktop (W-3201 includes the access note; W-3203 includes the recipients and Next).
    - The review Decide bar is pinned with "Approve and send" and "Return with a note". Return opens the full-height `Drawer` with the note. Escape and Cancel close it and return focus to the button.
    - There is no sideways scroll.
    - Every button, link, tab and segment is at least 44 by 44 px (D-92 (c); links inside sentences are exempt, D-95).
    - verify: e2e at 390, measuring bounding boxes.

### Quality
19. **Fidelity (D-64, D-83).** One design-fidelity run per round over the 8 boards, on a production build at `--width 1440` and `--width 390`.
    - Every board's element coverage after approved exceptions is 100%.
    - Visual is at least 90, or there is a board-level waiver citing D-83 in `fidelity-exceptions.json` with visual at least 70 (lower only with a signed one-board floor exception).
    - Every exception has `role`, `name`, `category`, `reason` and `approved_by`, and maps to a Conflicts number. None covers a value the data can supply (a name, a date, a tag, a count, a sentence).
    - The UI reviewer's side-by-side reading finds no fixable gap.
    - verify: the fidelity command per board; `round-<N>/fidelity/scores.txt`.
20. **Accessibility.** No axe violations (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`) at 1440 and 390 on:
    - W-3201…W-3207 and W-3209 after approve;
    - the open Drawer, the note error and the uncertain notice;
    - the not-open view.

    Every field is labelled, errors are announced, receipt and status words are in text and not colour only, and focus is visible. — verify: `e2e/leadership-report.spec.ts`.
21. **Tokens and components only.** The diff adds no `#hex`, `rgb(`, `hsl(` or raw px outside tokens in `features/workspace/*.css`. It adds no local copy of a component that `@/components` exports (`Button`, `Drawer`, `TextArea`, `Callout`, `Panel`, `Tag`). The banner is the shared `Callout` `info`. — verify: grep on the diff.
22. **Mock matches the contract.** `tests/leadership-report-mock.test.ts` checks that:
    - every new fixture and sidecar validates against the generated E-WORK-ITEM schema with `steps[].verdict` stripped;
    - claim then approve on W-3202 serves `W-3202.approve.json`;
    - return without a note is 422;
    - a stale revision is 409;
    - W-3206's decide is 403;
    - W-3209's decide answers `work_state: effect_uncertain`;
    - the W-3205 step serves `W-3205.next.json`;
    - the W-3212 step answers `effect_uncertain`;
    - reset clears.

    verify: `cd frontend && npx vitest run tests/leadership-report.test.tsx tests/leadership-report-mock.test.ts tests/mock-contract.test.ts`.
23. **Contract not extended.** `git diff --stat` against the base (with F-33 merged) shows no change in any of these:
    - `frontend/src/api/**`, `frontend/src/features/decide/**`, `frontend/src/features/response/**`, `frontend/src/shell/**`;
    - `frontend/mock/server.mjs`, `frontend/mock/workspace.mjs`, `frontend/mock/start-work.mjs`;
    - any existing fixture (including `W-1408`);
    - `apps/**`, `architecture/**`, `design/**` or the protected paths.

    Every overlay field and backend item is listed in build.md. — verify: `git diff --stat`; build.md.
24. **Existing tests green.** `delivery/checks.sh` passes. The tests listed under Context pass unchanged, including F-33's income schedule tests after the line-set refactor and `tests/response.test.tsx:761`. — verify: `delivery/checks.sh`; `cd frontend && npx vitest run` and the e2e command under Lanes, pasted in build.md.
25. **build.md evidence.** build.md records:
    - the commands and their results;
    - the 8 scores and waivers;
    - every exception with its Conflicts number;
    - every proposal and backend item;
    - the held list from "What is sent";
    - the base commit, showing F-33 merged.

    — verify: file content.

## Out of scope
- Part 2: the setup boards, "Start the report", period range, include list, template and audience fields (G-SCR52-1, G-SCR52-2). Starting a report stays the existing Start work drawer and `W-1408`.
- A `/reports/{id}` page, "Open the full report" / "Open the report", the Overview reports list, and any report narrative (G-SCR52-5).
- Any real send: email, WhatsApp or any provider. Recording a receipt from the page. A resend, retry-send or confirm-delivery control. A reconcile panel for internal reports, and rewording the client `ReconcilePanel` (Conflicts 6 option B only).
- Naming or choosing a reviewer or recipients. Editing Setup rules. A link to Setup. Deciding in the browser which reports need review.
- Counting, summing or filtering projects, figures or recipients in the browser. Naming projects the viewer cannot see.
- Separation-of-duties logic in the page (comparing the signed-in person with the preparer). Reading `/me` to show or hide a control.
- Changes to `useDecision`, the F-16 decision page, `InlineDecide`'s behaviour or the decide mock. Automatic retries. Optimistic states from a 200 body.
- Backend, OpenAPI, `schema.d.ts` regeneration, `architecture/**`, `design/**`, `src/shell/**`, new npm dependencies.

## Assumptions
- Work ids `W-3201`…`W-3212` (reserve to `W-3219`) and tasks `T-3201`…`T-3219`. Reason: the caller assigned W-32xx and T-32xx; readiness's suggested W-3501 is superseded.
- The base has F-33 merged before the build starts. Reason: the inline Decide panel and the agent-card-beside branch are F-33 code that D-113 accepted; copying them would fork shared code.
- No project or client on any fixture. Reason: the report spans projects, and the boards draw no project bar.
- Persona `ceo` for every board. Reason: the mock has no PMO Lead persona, CEO is in the monthly audience and may start all lines (13 Nov decision), and adding a persona would change shared mock files.
- The sent-state recipients are the four audience roles, with no names. Reason: the audience is an unset Setup value; roles are what the setup board lists.
- The returned note in `W-3202.return.json` is sample text. Reason: no board draws a returned report; the page shows whatever the backend sends.
- Tuesday's `reviewed` and `approved` facts are `not_yet`. Reason: the schema has no "not applicable" fact status, and the facts strip is screen-reader only on line boards (D-73); asked of the backend.
- "AWAITING LEADERSHIP REVIEW" and "DRAFT READY" status labels. Reason: no board draws a non-reviewer's view or a finished draft; the labels are fixture data, not frontend wording.
- Ports 4935/4936. Reason: not used by any spec; other features are being specced in parallel.
