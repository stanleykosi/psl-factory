# Escalation: Tola checks a raised escalation, the PMO Lead decides "Escalate to the client" or "Don't escalate", and Tola drafts Message v1 for internal review, in four states (contract mock only)

> Tasks: FE-EMERGENCY-ESCALATION, part 1 of 4 (R-WORKITEM, R-DECIDE; acceptance A-WORKSPACE frontend half, with A-WORKITEM, A-DECIDE and the F-16, F-17, F-30 and F-33 tests kept green). Architecture: package `architecture/packages/v7`, manifest digest `f6231d20b4fdeabbdca9bde5986a0a7883536f1a5cafc883848ef62dd6d4b624`; FE-EMERGENCY-ESCALATION at `architecture/packages/v7/delivery.md:2146-2177`, `gate_ids: []`, "Unresolved gates: none"; depends on FE-WORKSPACE-FRAME (F-17) and FE-M2A (F-05), both merged. Endpoints typed in `frontend/src/api/schema.d.ts`: E-WORK-ITEM `:54` (`tasks[]` `:1359-1427`, `workspace` `:1693-1912`), E-TASK-CLAIM `:96`, E-TASK-DECIDE `:117`, E-WORK-STEP `:715`. This feature changes no generated type. Decisions consumed: D-LINE-WORKSPACE and D-TASK-DECISION-VIEW (both `proposed`, under the recorded exception `architecture/sources/decisions-2026-11-15.md` items (g), (i)); D-ROLE-PMO (Head of PMO = PMO Lead; escalations are a PMO Lead decision, `architecture/model.json:753-764`); D-64, D-83, D-89, D-91, D-92c, D-111, D-112, D-113. Gaps: `delivery/backend-handoff/gaps-c-client-lines.md:112-136` (G-SCR51-1 to G-SCR51-6 and the three questions). Design: client-approved canvas version 1794581312-b166 (13 Nov 2026; SCR-51 at `design/review.json:59`), republished with "+ Start" as 1794762832-cab1 (D-89). `python3 /Users/Hunchoo/software-factory/packages/design/design.py check --project /Users/Hunchoo/psl-factory` was run for this spec on 18 Nov. Result: `EXCEPTION`, `passes: true` (design_sha256 `2859ab21…3d82`, D-89 frame-only change). Screens: SCR-51, 8 of 12 artboards in `design/canvas/project/`: `SCR-51-{desktop,mobile}-investigating`, `-decide`, `-not-escalated`, `-draft`. Review and received (part 2) are out. Models: `delivery/features/F-33/spec.md` (decide in place, shape), `F-32/spec.md` (shape, `work` link), `F-30/spec.md` (the issue page and the Start work drawer that opens this work item).

## What is sent, and what stays held (read first)

- **Nothing reaches the client in part 1.** No message is sent, emailed or delivered to Lagoon Health or anyone outside PSL. "Message v1" is Tola's draft, shown as returned. "Send for review" hands it to the PMO Lead inside the app. No page, notice or button in this feature may say a message was sent, delivered or received by the client.
- **Sent (to the local mock only):** the decision claim (E-TASK-CLAIM), one decision per press (E-TASK-DECIDE: verdict `approve` for "Escalate to the client", `reject` with a note for "Don't escalate"), and the PM's `send_for_review` step (E-WORK-STEP). Nothing changes the issue: it stays open with its owner.
- **Held, because a product or backend decision is open:**
  1. Whether "Don't escalate" tells the person who raised it (backend question).
  2. Whether the PMO Lead may edit the draft (backend question; no edit is built).
  3. Which internal notes skip review (G-SCR51-1, no decision id): the page shows only the steps returned and defaults nothing.
  4. Who reviews client messages: no policy slot exists (`guide/10-POLICY-CONFIGURATION.md`, `contracts/policy-slots.json`). A missing reviewer is a hold that shows the returned `disabled_reason` (fixture W-3608), never a default.
  5. The per-verdict words (X-VERDICTS, G-SCR51-2): built from the F-33 step proposal until the backend answers.
- **Held to later parts:** part 2 SCR-51 review and received (the real client send, G-SCR51-3 recipients from contact records), parts 3 and 4 SCR-50, the CTO pre-authorisation (FE-DECIDE-VARIANTS).
- **Held on the page itself:** decide controls exist only where `tasks[i].you_can_act` is true. The panel's role words are `required_role`. A refused, stale, failed or uncertain decide never shows "escalated", "message drafted" or "not escalated". The page shows a state only when the re-read item says so.

## Conflicts with the boards (for the design engineer, before the build)

"Recommend" is what this spec builds if no answer comes. Each difference becomes a `delivery/features/F-39/fidelity-exceptions.json` entry with `approved_by: "builder proposal, pending design engineer"` until signed. Items 1 to 5 need an answer. Items 6 to 10 are layout. Items 11 to 13 are exceptions to sign. A "proposal" is a field built on the mock only; the backend developer may change or refuse it.

### Need an answer
1. **The PMO Lead decides on the page, with the board's own button words.** v7 has no per-verdict label (G-SCR51-2).
   - **Recommend:** decide in place with F-33's `InlineDecide`, unchanged. The fixture's two steps carry `task_id` and F-33's proposal `verdict`: "Escalate to the client" (`approve`, primary, with the board's consequence sentence) and "Don't escalate" (`reject`, secondary). The panel reads "Decide · " + `required_role`. The buttons exist only when the task's `you_can_act` is true. The backend's `decision.verdicts[]` (X-VERDICTS) is recorded for the backend, not built. The consequence sentence sits under the buttons as F-33 draws it, not above the note (`frame layout`).
   - **Option B:** build X-VERDICTS as a second overlay now. Two ways to say the same thing; not recommended.
2. **The note label.** The board says "Note (needed to return or refuse)", but this panel has no Return. F-33's shared rule names only the offered verdicts that need a note, so it reads "Note (needed to reject)".
   - **Recommend:** keep the shared rule ("Note (needed to reject)"); listed `wording`. "Don't escalate" without a note sends nothing and asks for one.
   - **Option B:** the shared rule says "refuse" for `reject` on every panel. That changes F-33's income schedule wording too.
3. **"Back to the issue" needs an issue to go back to.** The board's issue is ISS-0241, which has no work item in the mock (F-30's overdue issue is ISS-0233, a different issue).
   - **Recommend:** keep the board's sample (ISS-0241, "Client test data three weeks late") and add one read-only issue fixture `W-3609` for it. "Back to the issue" is a `workspace.links[]` entry of F-32's kind `work` to `/work/W-3609` (G-SCR51-6). Without a work id the link is not drawn.
   - **Option B:** no issue fixture; the link is not drawn and is listed `no field`.
4. **The phone decide board has no note field, but "Don't escalate" needs one** (gaps question 3).
   - **Recommend:** F-33's phone pattern: the two buttons pinned at the bottom; "Don't escalate" opens the full-height `Drawer` with the note (D-111, F-29). Listed `extra element`.
   - **Option B:** the design engineer draws the phone note first (the feature waits).
5. **No board draws "no one is set to review client messages".**
   - **Recommend:** one extra fixture (W-3608): the draft state with `send_for_review` carrying the backend's `disabled_reason`. The button is drawn unavailable with that reason, sends nothing and names no reviewer. Not in the fidelity run.
   - **Option B:** leave the hold out until the backend answers G-SCR51-1.

### Layout (phone against desktop, frame)
6. **Phone boards are shorter and worded differently** ("Escalation", "Escalate?", "Not escalated", "Message drafted"; the shorter quote "Ask their new lead directly first."; no Message v1, facts or Next on some phone boards). **Recommend:** the phone shows the desktop sections, words and values in one column, with the item's `title` at both widths (D-111). Extras and wording are listed (`phone composition`, `phone wording`).
7. **Tola's card (investigating and draft).** **Recommend:** F-33's visible `AgentCard` with its footer, turned on for the `escalation` line while `agent.status` is `working` or `done`. Steps and details come from `item.agent.steps[]` (`text`, `source`): "ACT-0420 · OVERDUE 15 DAYS", "FACTS AND DATES ONLY" (as the board draws it, on Tola's step, not on the message). "step 3 of 4" and WORKING/DONE are the card's own. The footer reads "Started <agent.started_at>" in both states, so the draft board's "Drafted 13 Nov 14:00" is a wording difference (no `finished_at`). "Ask Tola" is the existing `assistant` link in that footer. The card titles "Investigating the escalation" and "Escalation message" and "· PMO agent" have no field (`no field`).
8. **"What Tola found" (decide).** **Recommend:** a `facts` section titled "What Tola found" with `agent: "tola"`, so the shared meta line shows it is Tola's (`extra element`). Values are as returned; a missing one reads "Unknown". The `cites` (`reference` "ACT-0420", "ISS-0241") travel in the fixture but are not drawn, as on the board (G-SCR51-5 recorded). **Option B:** a `findings` section with the cites drawn; the label and value then read "Client test data · 15 DAYS LATE".
9. **Header and phone bar.**
   - The crumb "PROJECTS / LAGOON HEALTH / REGISTERS / ESCALATIONS / ESC-0012" is `workspace.context.crumbs` as returned, plain text, so no `escalations` register value is needed (G-SCR51-4 recorded).
   - The project tab bar links every tab and marks none current (F-30).
   - The investigating facts (Raised by, From issue, Asked for) are an untitled `facts` section at the top of the main column (`frame layout`).
   - Phone bar: "← Project" on all four states. This extends F-30's issue rule (`WorkItemView.tsx:242`) to the `escalation` line, with the reference at the bar's end. The decide board's "← My work" and the bar words DECIDE and CLOSED are listed (`frame item`).
10. **Next panel, lead text and timeline.**
    - The shared NEXT heading is used as it is ("Next", `STEP_TEXT.next`) on not-escalated and draft, with the returned `next` line.
    - The shared timeline row is not used: no fixture here has a timeline.
    - The not-escalated sentence with Kemi Adebayo's note is an untitled `text` section, as returned.

### Exceptions to sign
11. **Every board string is data.** No board string is in `src/`. That covers the status labels (INVESTIGATING, YOUR DECISION, NOT ESCALATED, MESSAGE DRAFTED), the facts and their values, the consequence, the quote, Message v1, Tola's steps and the Next lines. Case and time formats follow the library (`Tag`, `When`): category `component`.
12. **Frame items.**
    - The signed-in name comes from `/me`. The mock has no PMO Lead persona, so the decide board is served to `pm` (Tunde Bello). Its fixture's `you_can_act: true` is the data, and "Kemi Adebayo · PMO Lead", "Overview" and "Setup" are not drawn (F-32 precedent).
    - "+ Start" (D-89).
    - Tab counts come from P-0101.
    - Category `frame item`.
13. **Visual waivers.** A board under 90 visual (and at least 70) carries a D-83 waiver citing the shared frame (D-99, D-110), after the design engineer signs it. A board under 70 needs its own floor exception (as D-112).

## Boards

| Board | File (`design/canvas/project/`) | Page | Mock |
|---|---|---|---|
| investigating, desktop / phone | `SCR-51-desktop-investigating.dc.html`, `SCR-51-mobile-investigating.dc.html` | `/work/W-3601` | persona `pm` |
| decide | `SCR-51-desktop-decide.dc.html`, `SCR-51-mobile-decide.dc.html` | `/work/W-3602` | persona `pm` (the fixture's `you_can_act: true` is the data) |
| not-escalated | `SCR-51-desktop-not-escalated.dc.html`, `SCR-51-mobile-not-escalated.dc.html` | `/work/W-3603` | persona `pm` |
| draft | `SCR-51-desktop-draft.dc.html`, `SCR-51-mobile-draft.dc.html` | `/work/W-3604` | persona `pm` |

All 8 are live URLs at 1440 and 390; no driver is needed. Each fidelity run starts with `POST /__mock/reset`, so W-3602 is not served from a decided override.

## Summary
- `/work/{id}` on line `escalation` shows, in the F-17 line workspace, what Tola is checking (investigating). Then come the PMO Lead's decision with what Tola found (decide), the refusal with the note quoted (not escalated) and Tola's Message v1 with "Send for review" (draft).
- The decision is taken in place through F-33's `InlineDecide` over the F-16 `useDecision`: claim, then one decide. "Don't escalate" needs a note. Controls come only from `tasks[].you_can_act`; role words from `required_role`; nothing reads `/me`.
- "Send for review" is one E-WORK-STEP. The page shows a new state only from the re-read. An uncertain decide or step never reads as done (fixture W-3607). Nothing says anything was sent to the client.
- Unknown values read "Unknown", never 0, blank or a dash. The page counts and dates nothing.
- New: the `escalation` line turned on in two existing line rules (agent card, phone back), fixtures W-3601 to W-3609 with sidecars on project P-0101, and tests. No contract change. Contract mock only.

## Context
- **Work item page:** `frontend/src/features/work-item/WorkItemView.tsx`.
  - `LineHeader` draws the crumbs from `workspace.context.crumbs` and the status tag.
  - `ProjectBar` draws the project tab links whenever `context.project` is present.
  - `:242` sets the phone back link to "Project" for `issue_followup` only.
- **Overview:** `WorkItemOverview.tsx`.
  - `AgentCard` (`:116`). On a workspace page it stays screen-reader only (`:697-708`).
  - `TaskPanels` (`:494`) skips a task a workspace step links to.
- **Workspace frame:** `frontend/src/features/workspace/`.
  - `Workspace.tsx`: the side panel, links row and line rules (`ISSUE_LINE` `:100`).
  - `Sections.tsx`: `FactsList` with `Unknown`, untitled `text`, section `agent` and `as_of` meta.
  - `Steps.tsx`: `StepControl`, `Consequence`, `disabled_reason`. `step.sends` adds "This sends to the client." (`:15-18`), so no fixture step here sets `sends`.
  - `useWorkspaceStep.ts`: `STEP_TEXT`, key, revision, reconcile.
  - `usePageReload.ts`, `proposals.ts`, `Links.tsx`.
- **Needed from unmerged siblings (both READY_FOR_ACCEPTANCE):**
  - F-33 (`fe-fin-schedules-income-detail-review`): `InlineDecide.tsx`, `stepVerdict` in `proposals.ts`, and the visible `AgentCard` with `foot` for `income_schedules` (`Workspace.tsx` `INCOME_LINE`, `WorkItemOverview.tsx`).
  - F-32 (`fe-delivery-release-delivery-tab-and-release-gate`): the `work` link kind in `proposals.ts` and `Links.tsx`.
  - This build starts from dlv-00 after both merge (see Lanes).
- **Decide flow (reuse, do not change):** `frontend/src/features/decide/` (`useDecision.ts`, `DecideStates.tsx` `cannotActCopy` and `UncertainNotice`, `format.ts` `NOTE_MAX`, `VERDICT_WORDS`).
- **Mock:**
  - `frontend/mock/server.mjs` `taskResponse` (`:148-183`):
    - it checks the body and the note rule, then the revision (409) before `you_can_act` (403);
    - it applies `<work_id>.<verdict>.json` and returns that file's `state` as `work_state`;
    - a `<work_id>.next.json` makes the first decide answer 409, so no decide fixture has one.
  - `frontend/mock/workspace.mjs` (E-WORK-STEP): `<id>.steps.json` and `<id>.next.json`.
  - Persona `pm` is Tunde Bello.
  - The `escalation` start line is `mock/fixtures/start-work/lines.pm.json:225`.
  - P-0101 Lagoon Health is served to `pm`.
  - No W-36xx or T-36xx exists; the block W-36xx and T-36xx is this feature's (night log 06:16).
- **Tests that must stay green:** `tests/workspace.test.tsx`, `tests/workspace-step.test.tsx`, `tests/workspace-mock.test.ts`, `tests/decide.test.tsx`, `tests/decide-board.test.tsx`, `tests/mock-decide.test.ts`, `tests/issue-detail.test.tsx`, `tests/income-schedule.test.tsx`, `tests/income-schedule-mock.test.ts`, `tests/mock-contract.test.ts`, `e2e/workspace.spec.ts`, `e2e/issue-detail.spec.ts`, `e2e/income-schedule.spec.ts`.

## Contract

### E-WORK-ITEM `GET /api/v1/work/{work_id}` (unchanged)
- Read by `useWorkItem`. The page draws `workspace` in returned order for `line_key: "escalation"`. It branches only on `line_key`, `agent.status` and the task fields below.
- **Errors and states:**
  - 401: the signed-out state with `next=/work/<id>`.
  - 403 and 404 look the same (`NoAccessState`): no title, fact, quote or message, and no further call.
  - 5xx: the problem card with Retry.
  - Loading: the existing skeleton.
- After any write the page re-reads (`usePageReload`). It builds no state from a 200 body.

### Fixtures
Common to every fixture:
- `sample: true`, `case_id: "P-0101"`, `reference: "ESC-0012"`, `title: "Client test data three weeks late"`, `line: "Escalation"`.
- `workspace.line_key: "escalation"`, `screen: "SCR-51"`, `context.project {case_id: "P-0101", title: "Lagoon Health"}`.
- Crumbs: Projects / Lagoon Health / Registers / Escalations / ESC-0012.
- Four `stations`: Tola investigates, PMO Lead decides, Tola drafts, Review (part 2).

| Id | `state`, status (label, tone) | Sections and agent | Tasks and steps |
|---|---|---|---|
| W-3601 investigating | `processing`, "INVESTIGATING" `agent` | untitled `facts`: Raised by "You", From issue "ISS-0241", Asked for "ESCALATE TO THE CLIENT". `item.agent` `working`, `name: "Tola"`, `started_at` 13 Nov 11:00 Lagos, 4 steps with `source`: "ISS-0241 · 3 WEEKS OPEN" done, "ACT-0420 · OVERDUE 15 DAYS" done, "MILESTONE 3 · GO-LIVE 4 DEC" now, "Hand it to the PMO Lead" not started. `workspace.links` `assistant` "Ask Tola". | `T-3601` decide task, `you_can_act: false`, `cannot_act_reason: not_your_turn`, `required_role: "PMO Lead"`; no steps |
| W-3602 decide (can act) | `action_needed`, "YOUR DECISION" `person` | `facts` "What Tola found", `agent: "tola"`: Client test data "15 DAYS LATE" (cites `reference` ACT-0420), Delays "MILESTONE 3 · GO-LIVE 4 DEC", Already asked the client "3 TIMES" (cites ISS-0241). `agent.status: "waiting"`. | `T-3602` `kind: decide`, `required_role: "PMO Lead"`, `you_can_act: true`, `revision: 1`, `decision.version.label` "Escalation ESC-0012". Steps: `escalate_to_client` (primary, `verdict: approve`, label "Escalate to the client", consequence "Escalating means a formal message to the client's sponsor, reviewed before it's sent.") and `dont_escalate` (secondary, `verdict: reject`, label "Don't escalate"), both `task_id: T-3602`. Sidecars: `W-3602.approve.json` (the W-3604 content) and `W-3602.reject.json` (the W-3603 content); each one revision higher, task `already_decided`. **No `W-3602.next.json`.** |
| W-3603 not escalated | `cancelled`, "NOT ESCALATED" `stopped` | untitled `text`: "Kemi Adebayo decided not to escalate on 13 Nov: “Their new lead starts Monday. Ask them directly first.”" `next`: ["The issue stays open with its owner. You can raise the escalation again later."]. `links`: `work` "Back to the issue" to `W-3609`. `agent.status: "stopped"`. | task `already_decided`; no steps |
| W-3604 draft | `action_needed`, "MESSAGE DRAFTED" `person` | `text` "Message v1": "Your team's test data is now 15 days late (asked 22 Oct, 29 Oct, 5 Nov). Go-live on 4 Dec depends on it. Could you confirm a date this week?" `item.agent` `done`, `started_at` 13 Nov 13:40, steps "ESCALATE · 13 NOV", "FACTS AND DATES ONLY", "SPONSOR · PROJECT CONTACT". `links` `assistant` "Ask Tola". `next`: ["The PMO Lead reviews the message before it's sent."] | step `send_for_review` (primary, `applies_to: workspace`, no fields, no `sends`). `W-3604.steps.json`: 200 `done`. `W-3604.next.json`: status "WAITING FOR REVIEW" `person`, the same message, review task `T-3610` `you_can_act: false`, `not_your_role`, `asked` Kemi Adebayo · PMO Lead, no steps. |
| W-3605 decide, not your role | as W-3602 | as W-3602 | `T-3605` `you_can_act: false`, `cannot_act_reason: not_your_role`, `asked` [Kemi Adebayo, PMO Lead]; the same two steps sent |
| W-3606 unknown | as W-3602 | as W-3602 but "Already asked the client" and "Delays" have no `value` | `T-3606` as T-3602 |
| W-3607 uncertain decide | as W-3602 | as W-3602 | `T-3607` as T-3602. `W-3607.approve.json`: `state: effect_uncertain`, status "RESULT NOT CONFIRMED" `uncertain`, task `already_decided`, no steps |
| W-3608 review not set up | as W-3604 | as W-3604 | `send_for_review` with `disabled_reason` "No one is set to review client messages yet. An admin sets this in Setup." No steps script. |
| W-3609 issue ISS-0241 | `waiting`, "NO RESPONSE · 15 DAYS" `uncertain`, `line_key: "issue_followup"`, `reference: "ISS-0241"`, title "Client test data three weeks late" | lead `text` and `next` only (the F-30 frame) | none; read only |

Each fixture and sidecar validates against the generated E-WORK-ITEM 200 schema once the overlay fields are stripped (`steps[].verdict`, `workspace.links`). Nothing in a fixture is a count or date the page works out.

### Overlay (mock only; each listed in build.md for the backend developer)
- **Reused, not new:**
  - `steps[].verdict` (F-33, G-C-1), read by `stepVerdict`.
  - `workspace.links[]` kinds `assistant` and `work` (X-LINKS; F-28, F-32).
- **Recorded, not built:**
  - X-VERDICTS `tasks[].decision.verdicts[]` {verdict, label, consequence, note_required}, and that "Don't escalate" is `reject` closing as NOT ESCALATED (G-SCR51-2);
  - `escalations` in the register enums (G-SCR51-4);
  - `action_id` and `issue` in `cites` (G-SCR51-5);
  - the issue link (G-SCR51-6);
  - which internal notes skip review (G-SCR51-1);
  - recipients from contact records (G-SCR51-3, part 2);
  - `agent.finished_at` and an agent card title (Conflicts 7);
  - the three backend questions.

### E-TASK-CLAIM `POST /api/v1/tasks/{task_id}/claim` and E-TASK-DECIDE `POST /api/v1/tasks/{task_id}/decision`
- **Through `InlineDecide` and `useDecision(work_id, task_id)` only;** no new write path. The claim is sent once per task revision, only when `you_can_act` is true. Until it answers, the buttons are off.
- **Request:** `{verdict, note?, expected_revision}` with `X-CSRFToken` and no extra keys.
  - "Escalate to the client" sends `approve` with no note.
  - "Don't escalate" sends `reject` with the trimmed note, required and at most `NOTE_MAX` (2000), checked before any request ("Add a note to reject it.", announced, focus on the note).
- **200:** the page re-reads and draws what it gets (draft or not escalated). The done notice is the existing `VERDICT_WORDS` heading, and only when the re-read confirms it.
- **Errors:**
  - 401: signed out.
  - 403: the read-only view from the re-read `cannot_act_reason`.
  - 409: the stale view; the note is kept and nothing is resent.
  - 422: the message under the note.
  - 5xx, network, timeout or `work_state: effect_uncertain`: a re-read first, then `UncertainNotice` or "result not confirmed". Never "escalated" or "not escalated" from the click; the next decide only on a new press.
- **Permission and tenant:** buttons only for the step's task with `you_can_act: true`. Otherwise `cannotActCopy(cannot_act_reason, task)` and `asked`, as returned. No role, name or label grants a control.

### E-WORK-STEP `POST /api/v1/work/{work_id}/steps` (send for review)
- **Request:** `{expected_revision: workspace.revision, step: "send_for_review", inputs: {}, idempotency_key: <UUID per press, reused on a manual retry>}` with `X-CSRFToken`, through `useWorkspaceStep`.
- **200 `done`:** re-read. The page shows "WAITING FOR REVIEW" only from `W-3604.next.json`; the notice reads "Done: Send for review.".
- **Errors:**
  - 409: re-read and the stale sentence.
  - 5xx, network or timeout: a re-read, then "We couldn’t confirm this step…", with Try again on the same key.
  - `outcome: uncertain`: the existing reconcile panel; never "sent for review".
  - A step with `disabled_reason`: drawn unavailable with that reason; no POST.

### Screen states
- **Loading:** the skeleton.
- **Empty:** a workspace with no sections draws the header and status only.
- **Error:** the problem card with Retry.
- **Success:** the four board states plus W-3605 to W-3609.
- **Held:** W-3608.
- **Restricted:** an item with `restricted: true` reads "Restricted".

## Lanes
- **Frontend lane (builder, Sonnet: medium risk, D-64)** owns:
  - **Code:**
    - `Workspace.tsx`: the `escalation` line joins F-33's visible agent card rule for `working` and `done`.
    - `WorkItemOverview.tsx`: the screen-reader copy rule follows it.
    - `WorkItemView.tsx` `:242`: "← Project" for `escalation`.
    - Additive `workspace.css` with tokens only, if needed.
  - **Fixtures:** `frontend/mock/fixtures/work/W-3601…W-3609` and the sidecars named above.
  - **Tests:** `frontend/tests/escalation.test.tsx`, `frontend/tests/escalation-mock.test.ts`, `frontend/tests/mock-contract.test.ts` (new fixtures only), `frontend/e2e/escalation.spec.ts`.
  - **Factory files:** `delivery/features/F-39/` (`fidelity-exceptions.json`, `round-<N>/`).
- **Shared, read only:**
  - Code: `src/features/decide/**`, `InlineDecide.tsx`, `Sections.tsx`, `Steps.tsx`, `StepForm.tsx`, `proposals.ts`, `Links.tsx`, `src/features/start-work/**`, `src/components/**`, `src/shell/**`, `src/api/**`, `src/styles/**`.
  - Mock: `mock/server.mjs`, `mock/workspace.mjs`, every existing fixture (including W-2412 and the start-work lines).
  - Project: `frontend/package.json`, the lock file, `architecture/**`, `design/**`, `apps/**`, and the protected `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json`.
- **Backend lane:** none. For build.md: the overlay list above and the held list under "What is sent".
- **Integration owner:** the coordinator.
  - Branch from dlv-00 only after F-32 and F-33 have merged into it. Until then the build waits; no copy of `InlineDecide` or the `work` link.
  - F-31 also touches `Workspace.tsx`. Whichever merges second merges the current base and reruns `delivery/checks.sh` and the e2e.
- **Ports:** app 4936, mock 4937. Run `cd frontend && E2E_PORT=4936 MOCK_PORT=4937 npx playwright test e2e/escalation.spec.ts e2e/workspace.spec.ts e2e/issue-detail.spec.ts e2e/income-schedule.spec.ts` with `timezoneId: 'Africa/Lagos'`. Fidelity runs on a production build, one run per round over the 8 boards (D-64). Run `df -h /System/Volumes/Data` first and stop under 3 GB; delete `frontend/test-results` after.
- **Review routing (medium):** technical (Sonnet), UI (fidelity gate), UX (Sonnet), QA (Sonnet), PMO. Product acceptance is required. Merges only on the design engineer's "merge".
- **Size:** about 700 to 1,000 lines, mostly fixtures and tests. One PR.

## Acceptance criteria

### Page
1. **Four states from data.** `/work/W-3601` to `W-3604` show their fixture's status label and tone, facts, Tola's card, decide panel, quote, Message v1, Next line and links, and nothing else. No board string is in `src`: `grep -rn "INVESTIGATING\|YOUR DECISION\|NOT ESCALATED\|MESSAGE DRAFTED\|Escalate to the client\|Don't escalate\|FACTS AND DATES" frontend/src` returns nothing. — verify: `cd frontend && npx vitest run tests/escalation.test.tsx`; pages at 1440 and 390.
2. **Tola's work is shown, never a decision.** On W-3601 the card shows "Tola", "step 3 of 4", WORKING, the four steps with their details as returned, "Started 13 Nov 11:00" and "Ask Tola" (href `/assistant`). There is no decide control. On W-3604 the card shows DONE and the three done details. On W-3602 and W-3603 no visible card is drawn. Changing a fixture step's `source` changes only that text. — verify: component tests on the fixtures and modified copies.
3. **Unknown is never 0.** W-3606 shows "Unknown" for "Delays" and "Already asked the client". The page has no "0", "0 TIMES", empty value cell or "-" or "—" in their place. — verify: component test on W-3606.
4. **The page counts and dates nothing.** Changing "3 TIMES" to "4 TIMES", or "15 DAYS LATE" in the facts, changes only that value; Message v1's dates are not reread or reformatted. `git diff -U0 frontend/src | grep -nE "parseFloat|Number\(|\.reduce\(|new Date\("` adds nothing. — verify: component tests on modified copies; the grep.
5. **Sample-marked.** Every fixture page shows `SampleLabel` because `sample: true`; a copy with `sample: false` does not. — verify: component test.

### Decide
6. **Controls only from `you_can_act` and `required_role`; nothing from `/me`.**
   - W-3602 shows "Escalate to the client" and "Don't escalate" under "Decide · PMO Lead".
   - W-3601, W-3603 and W-3605 show no decide button. W-3605 shows the `not_your_role` copy and "Kemi Adebayo · PMO Lead" from `asked`, and sends no claim.
   - Personas `pm`, `finance_lead` and `ceo` draw the same controls on the same fixture.
   - `grep -rn "useMe\|/me\b" frontend/src/features/workspace frontend/src/features/work-item` shows no new line.

   — verify: component tests with three personas and a recording `fetch`.
7. **Escalate.** On W-3602 the page sends one claim to `/api/v1/tasks/T-3602/claim`. "Escalate to the client" then sends exactly one POST `/api/v1/tasks/T-3602/decision` with CSRF and `{verdict: "approve", expected_revision: 1}`: no note, no extra keys, valid against the generated schema. A double press sends one. The re-read shows MESSAGE DRAFTED from `W-3602.approve.json`. — verify: component test; e2e request log.
8. **Don't escalate needs a note.** An empty or blank note, or one over 2000 characters, sends nothing; "Add a note to reject it." appears under the note, announced, with focus on the note. With a note, one POST with `verdict: "reject"` and the trimmed note follows. The re-read shows NOT ESCALATED with the quote and "Back to the issue" linking to `/work/W-3609`, which opens ISS-0241. On the phone, "Don't escalate" opens the full-height `Drawer` with the note. — verify: component tests; e2e at 390.
9. **No success before the re-read.** With the decide answering 200 and a test double still serving the decide state on re-read, the page shows neither MESSAGE DRAFTED, NOT ESCALATED nor "is approved". The buttons follow the re-read task. — verify: component test with a recording `fetch`.
10. **An uncertain decide never reads as success.**
    - W-3607 escalate: the mock returns `work_state: effect_uncertain` and the re-read is `effect_uncertain`. The page shows "result not confirmed" and the status "RESULT NOT CONFIRMED", never "approved", "escalated" or MESSAGE DRAFTED.
    - A network failure, timeout or 500 on W-3602's decide re-reads first and shows `UncertainNotice`.
    - No second decide is sent without a new press.

    — verify: component tests (fake timers: one POST after 60 s); e2e with a routed abort.
11. **Backend refusals are shown.** With `psl_mock_scenario` 403 the decide shows the read-only view; 409 shows the stale view, keeps the note and resends only on a new press; 422 shows the message under the note. — verify: component tests; `tests/escalation-mock.test.ts`.

### Send for review
12. **Send for review.** On W-3604, "Send for review" sends one POST `/api/v1/work/W-3604/steps` with CSRF, `expected_revision`, `step: "send_for_review"`, `inputs: {}` and a UUID `idempotency_key`. A retry after a 500 reuses the key. On 200 the re-read shows WAITING FOR REVIEW, with no Approve, Send or Return control for `pm`. The page never shows "sent for review" before the re-read. — verify: component test; e2e request log.
13. **A missing reviewer is a hold.** On W-3608 "Send for review" is unavailable with the returned `disabled_reason`, no POST is sent whatever is pressed, and no reviewer's name appears. — verify: component test with a recording `fetch`.
14. **Nothing says sent to the client.** On every fixture, sidecar and notice in this feature, `document.body.textContent` contains none of: "sent to", "was sent", "has been sent", "delivered", "received", "This sends to the client". No new fixture step sets `sends`. Message v1 has no Send, Approve and send, or Edit control. — verify: component test over W-3601 to W-3609 and the sidecars; `grep -n '"sends"' frontend/mock/fixtures/work/W-36*` returns nothing.

### Access and frame
15. **Access 401, 403, 404.**
    - 401 on read or write shows signed-out with `next=/work/<id>`.
    - 403 (`psl_mock_scenario`) and 404 (`/work/W-3699`, no fixture) look the same, with no title, fact, quote or message.
    - Persona `none` gets the same not-open view with no further call.

    — verify: component tests with a recording `fetch`; e2e.
16. **Frame.** The crumbs read Projects / Lagoon Health / Registers / Escalations / ESC-0012 as returned. The project tab bar links every tab and marks none current. The phone bar shows "← Project" to `/projects/P-0101` and "ESC-0012" on all four states. F-30's issue pages and F-33's income pages draw as before. — verify: component tests; e2e.
17. **Phone.**
    - At 390 each state is one column with the desktop sections, words and values.
    - The decide buttons are pinned at the bottom.
    - Escape and Cancel close the Drawer and return focus to its button.
    - There is no sideways scroll.
    - Every button, link and tab is at least 44 by 44 px (D-92c; links inside sentences exempt, D-95).

    — verify: e2e at 390 measuring bounding boxes.

### Quality
18. **Fidelity (D-64, D-83).** One design-fidelity run per round over the 8 boards, on a production build at `--width 1440` and `--width 390`.
    - Every board's element coverage after approved exceptions is 100%.
    - Visual is at least 90, or the board has a signed D-83 waiver with visual at least 70. Lower needs a signed one-board floor exception.
    - Every exception has `role`, `name`, `category`, `reason` and `approved_by`, and maps to a Conflicts number. None covers a value the data can supply.
    - The UI reviewer's side-by-side reading finds no fixable gap.

    — verify: the fidelity command per board; `round-<N>/fidelity/scores.txt`.
19. **Accessibility.** There are no axe violations (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`) at 1440 and 390. This covers W-3601 to W-3604 and W-3608, the open Drawer, the note error, the uncertain notice and the not-open view. Also:
    - every field is labelled and errors are announced;
    - status words are in text, not colour only;
    - focus is visible;
    - the WORKING pulse does not animate under `reducedMotion: 'reduce'`.

    — verify: `e2e/escalation.spec.ts`.
20. **Tokens and components only.** The diff adds no `#hex`, `rgb(`, `hsl(` or raw px outside tokens in any `.css`. It adds no local copy of an `@/components` export (`Button`, `Drawer`, `TextArea`, `Callout`, `Panel`, `Tag`). — verify: grep on the diff.
21. **Mock matches the contract.** In `tests/escalation-mock.test.ts`:
    - every new fixture and sidecar validates against the generated E-WORK-ITEM schema, with the overlay stripped;
    - claim then approve on W-3602 serves `W-3602.approve.json`; reject without a note is 422;
    - a stale revision is 409, and W-3605's decide is 403;
    - W-3607's approve returns `work_state: effect_uncertain`;
    - the W-3604 step serves `W-3604.next.json`;
    - reset clears.

    — verify: `cd frontend && npx vitest run tests/escalation.test.tsx tests/escalation-mock.test.ts tests/mock-contract.test.ts`.
22. **Contract not extended.** `git diff --stat` shows no change in `frontend/src/api/**`, `frontend/src/features/decide/**`, `InlineDecide.tsx`, `proposals.ts`, `src/shell/**`, `mock/server.mjs`, `mock/workspace.mjs`, any existing fixture, `apps/**`, `architecture/**`, `design/**` or the protected paths. No new overlay field is added; every reused or recorded one is listed in build.md. — verify: `git diff --stat`; build.md.
23. **Existing tests green.** `delivery/checks.sh` passes, and the tests listed under Context pass unchanged. — verify: `delivery/checks.sh`; `cd frontend && npx vitest run` and the e2e command under Lanes, pasted in build.md.
24. **build.md evidence.** It records the commands and results, the 8 scores and waivers, every exception with its Conflicts number, the overlay and backend list, and the held list. It states that nothing reaches the client in part 1. — verify: file content.

## Out of scope
- Part 2 (review, "Approve and send", "Return with a note", receipts, any client send, recipients from contact records), parts 3 and 4 (SCR-50), the CTO pre-authorisation.
- Editing Message v1; choosing or naming recipients; any send, email or delivery.
- Changing the issue page, W-2412, the Start work drawer, the issue's state, or creating the escalation record (backend).
- Naming or defaulting a reviewer, or deciding which internal notes skip review; Setup changes.
- Role or person logic in the page; reading `/me` for a control; counting days, asks or dates in the browser.
- Changes to `InlineDecide`, `useDecision`, the F-16 page or the decide mock; X-VERDICTS as code; an `escalations` register tab; automatic retries.
- Backend, OpenAPI, `schema.d.ts` regeneration, `architecture/**`, `design/**`, `src/shell/**`, new npm dependencies.

## Assumptions
- Fixtures W-3601 to W-3609, tasks T-3601 to T-3610. Reason: the night log assigns W-36xx and T-36xx to F-39.
- All on P-0101 Lagoon Health. Reason: the boards name it and `pm` can open it.
- The board's issue ISS-0241 is kept as sample data with its own read-only fixture W-3609. Reason: F-30's ISS-0233 is a different issue; repointing it would change existing fixtures.
- The approve sidecar shows Tola's draft at once. Reason: no board draws "Tola drafting"; the page draws whatever the re-read returns.
- Not-escalated uses `state: cancelled` with status "NOT ESCALATED" `stopped`. Reason: sources do not say what state a refused escalation takes.
- `agent.status` `waiting` on decide and `stopped` on not-escalated. Reason: so the card draws only where the boards draw it, from data.
- The decide board is served to `pm`. Reason: no PMO Lead persona; F-32 did the same.
- The W-3608 `disabled_reason` wording is sample text. Reason: no policy slot exists; the real reason is the backend's.
- The build waits for F-32 and F-33 to merge. Reason: copying their code would fork the shared frame.
- Ports 4936 and 4937. Reason: unused by any spec.
