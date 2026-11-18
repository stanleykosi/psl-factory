# Ledger source LED-0052: a Finance person records what they found in QuickBooks with proof, and an independent reviewer approves or rejects it as a reference, in four states (contract mock only)

> **The build starts only after F-33 is merged into dlv-00.** This spec is written against F-33's branch head (`fe-fin-schedules-income-detail-review`, worktree `/Users/Hunchoo/psl-factory-worktrees/f-33`, head `d20fd9b2`; the worktree is now at `b8265cdb`, which adds one line to `delivery/BACKEND-HANDOFF.md` and no code). It reuses F-33's `features/workspace/InlineDecide.tsx`, `proposals.ts` `stepVerdict`, the `steps[].verdict` overlay and its `mock-contract` strip, the income line's frame branches in `Workspace.tsx` and `WorkItemOverview.tsx`, and the "reviewer not set" hold fixture pattern (D-113). If F-33 changes before it merges, the builder first re-reads this spec against the merged code and lists every difference in build.md.
>
> Tasks: FE-FIN-LEDGER, part 1 (R-FINANCE; acceptance A-WORKSPACE frontend half; A-WORKITEM, A-DECIDE and the F-16, F-17, F-29, F-33 and response tests stay green). Architecture: package `architecture/packages/v7`, manifest digest `f6231d20b4fdeabbdca9bde5986a0a7883536f1a5cafc883848ef62dd6d4b624`. FE-FIN-LEDGER is at `architecture/packages/v7/delivery.md:2804-2833`, `gate_ids: []`, "Unresolved gates: none". It depends on FE-WORKSPACE-FRAME (F-17, merged). The endpoints are typed in `frontend/src/api/schema.d.ts` (F-33 tree): E-WORK-ITEM `:54` (`workspace` `:1693-1912`, `steps[]` `:1853-1890`, `tasks[].cannot_act_reason` `:1419`), E-TASK-CLAIM `:96`, E-TASK-DECIDE `:117`, E-EVIDENCE-UPLOAD `:159` (body `:2344-2360`), E-WORK-STEP `:715` (body with `evidence_ids` `:5228-5242`). This feature changes no generated type. Decisions consumed: D-LINE-WORKSPACE (`proposed`, under the recorded exception `architecture/sources/decisions-2026-11-15.md` items (g), (i)); D-64, D-83, D-89, D-91, D-92c, D-111, D-112, D-113; D-114 (F-47 provisional, for the landing link only). D-RETURN does not apply: ledger review is approve or reject only. Gaps: `delivery/backend-handoff/gaps-f-finance-workspaces.md:17-37` (SP-1 to SP-9, G-C-1 to G-C-9) and `:163-182` (SCR-58, G-58-1 to G-58-6). Design: client-approved canvas version 1794581312-b166 (13 Nov 2026, covers the Finance and Payroll canvas; SCR-58 at `design/review.json:66`), republished with "+ Start" as 1794762832-cab1 (D-89). `python3 /Users/Hunchoo/software-factory/packages/design/design.py check --project /Users/Hunchoo/psl-factory` was run for this spec on 18 Nov. Result: `EXCEPTION`, `passes: true` (design_sha256 `2859ab21…3d82`, the D-89 frame-only change). Screens: SCR-58, 8 of 12 artboards in `design/canvas/finance/project/`: `SCR-58-{desktop,mobile}-investigating`, `-observe`, `-review`, `-verified`. Part 2 (duplicate, rejected) is out. Models: `delivery/features/F-33/spec.md` (shape, inline Decide), `F-34/spec.md` (the shared upload seam, the proof driver), `F-47/spec.md` (the start that lands here).

## What is sent, and what stays held (read first)

- **Sent (to the local mock only):**
  - the observer's proof file (E-EVIDENCE-UPLOAD on the ledger source's case, `kind: "ledger_observation"`);
  - the observation (E-WORK-STEP `record_observation`: what they found, plus the proof's `evidence_id`);
  - the review claim (E-TASK-CLAIM) and one decision per press (E-TASK-DECIDE, verdict `approve` or `reject`; reject needs a note).
  Nothing is posted to the ledger. Nothing is read from or sent to QuickBooks: a person looks the entry up and says what they saw. Nothing goes to anyone outside the app. No amount is shown anywhere in part 1.
- **Held, because a product or backend decision is open:**
  1. All three ledger policy values are NOT SET (`frontend/mock/fixtures/setup/finance.desktop.json:343-379`): `finance.ledger_sources.verification` ("Verification rules"), `.conflict` ("Conflict rules") and `.reviewer` ("Who reviews ledger sources"). So every fixture is sample-marked. An unset reviewer is the backend's `setup_needed` hold with no control (W-4205). The page names no reviewer and states no rule, and it offers no control for any of the three values.
  2. Whether the backend keeps the capturer, the observer and the reviewer three separate people, and with which reason code (G-58-4). The page shows the separation only as the backend's own words (`decision.basis`, the step's `consequence`, `cannot_act_reason`, `disabled_reason`).
  3. What an "Unknown" or "More than one" observation does, and who is told (G-58-3). The page shows the hold the re-read returns (W-4209) and adds nothing.
  4. Which verdicts a ledger review offers (G-C-1). Built as approve and reject from the steps sent.
  5. "Ask Chidi" context (G-C-4) and the re-check that reopens a verified reference (G-58-5).
- **Held to part 2:** the duplicate refusal (G-58-1), "Correct" with `continues` (G-58-2, G-C-6), "Open LED-0049" (G-C-3), and the rejected board. After a Reject in part 1, the re-read is shown read-only with no "Correct" step.

## Conflicts with the boards (for the design engineer, before the build)

"Recommend" is what this spec builds if no answer comes. Each becomes a `fidelity-exceptions.json` entry (`approved_by: "builder proposal, pending design engineer"` until signed). Items 1 to 7 change what a person sees or can do and need an answer. Items 8 to 12 are layout. Items 13 to 16 are exceptions to sign. "Contract" means a proposal field built on the mock only; the backend developer may change or refuse it.

### Need an answer

1. **The review board draws the Decide panel in the page with "Approve reference" and "Reject" only** (G-C-1, G-C-2). **Recommend:** decide in place with F-33's `InlineDecide` (D-113), unchanged. Each step with `task_id` and a `verdict` of `approve` or `reject` is one button in "Decide · " + `required_role`, labelled with the step's `label`. The write goes through F-16 `useDecision` (claim, then decide). The buttons exist only while that task's `you_can_act` is true. The review fixtures send no `return` step, so no Return button is drawn; the page has no "ledger" rule that hides one. **Option B:** the existing link to the F-16 decision page (no overlay field); the drawn panel becomes a listed difference.
2. **The observe board draws "Found" already chosen and the proof already uploaded ("qb-screenshot-je7741.png · Uploaded · 310 KB").** These are the observer's own answers, not the backend's. **Recommend:** the form opens with nothing chosen and no file. The fidelity driver presses "Record observation", chooses Found and uploads a 310 KB `qb-screenshot-je7741.png`, then freezes the page without submitting (the F-23/F-34 driver, D-98 (2)). **Option B:** a `value` on the choice field pre-selects Found. We advise against it: the observer would be recording a finding the system chose for them.
3. **The board draws the four answers as a row of radio segments; the shared field rule draws a choice of more than three options as a `Select`** (`src/features/start-work/IntakeField.tsx:147-161`). **Recommend:** the `Select` ("What you found", placeholder "Choose…", options in the order sent), as the shared rule draws it. No shared component changes, and "More than one" fits at 390 without the board's "Many". Listed (`component`). **Option B:** the step form draws a 4-option choice as `Segmented`. That is a change to `IntakeField` or a new `StepForm` prop, it touches every Start work drawer with four options, and the builder lists the affected tests.
4. **"Who reviews ledger sources" is not set, and no board draws that state.** **Recommend:** one extra fixture (W-4205). The backend returns `state: setup_needed` with its status label, a facts line "Who reviews ledger sources · NOT SET" and its `next` sentence. The page draws exactly that in the same frame, with no Decide panel, no button and no reviewer's name or role. The Setup link is not drawn (G-C-3). This state has no board and is not in the fidelity run. **Option B:** the design engineer draws the hold first (the feature then waits).
5. **A reviewer who captured or observed the source: no board, and v7 has no reason code for it** (G-58-4). **Recommend:** the backend's `cannot_act_reason: prepared_by_you`, drawn as the existing copy "You prepared LED-0052 v1, so someone else must review it." (`cannotActCopy`, with `decision.version.label` "LED-0052 v1"), with no button and no claim. The same fixture shape covers the person who observed it: after recording an observation, the re-read shows them this copy (W-4202 → `W-4202.next.json`). The page never compares names with `/me`. **Option B:** the backend sends a new code (e.g. `involved_in_this_record`). The frontend then adds one `cannotActCopy` case in a later change to `src/features/decide/**`, which this feature does not touch.
6. **An "Unknown" or "More than one" answer "holds the check", and no board draws the hold** (G-58-3). **Recommend:** one fixture (W-4209, reached by recording Unknown on W-4208). The backend returns station 3 `stopped`, status "CHECK HELD" `stopped`, facts "What was found" "UNKNOWN", "Verification rules" "NOT SET", and a `next` sentence. There is no step and no Decide panel. The page draws what it returns and decides nothing from the chosen answer. Not in the fidelity run. **Option B:** the design engineer draws the held state first.
7. **The boards' words state rules.** These are:
   - The observe board's "an independent reviewer (not Bisi, who captured it, and not you) decides".
   - The review board's "You captured nothing and observed nothing here, so you can review." and "Ledger review is approve or reject only…".
   - The review board's Note label "(needed to return, reject or withdraw)".
   **Recommend:**
   - The first is the step's `consequence` and the second is `tasks[0].decision.basis`, each as returned. The third is the approve step's `consequence`. The page composes none of them.
   - The Note label is F-33's `DECIDE_TEXT.needed` over the verdicts sent: "Note (needed to reject)".
   - "Recording what you saw isn't an approval. “Unknown” or “More than one” holds the check." is the choice field's `help`, as returned.
   - The wording is checked at product acceptance.
   **Option B:** the Note label as drawn. We advise against it, because Return and Withdraw are not offered here.

### Layout (phone against desktop, frame)

8. **Phone titles differ from desktop** ("Chidi investigating", "Record what you found", "Independent review", "Verified", against "QuickBooks journal JE-7741 · October"). **Recommend:** the work item's `title` at both widths (D-111); the status tag carries the state. Listed (`frame item`).
9. **The phone boards drop desktop content.**
   - Phone investigating has no "Source" facts and no "Ask Chidi".
   - Phone observe has no proof field, no consequence and no help line, and says "Many".
   - Phone review shows only "Observed · FOUND", with no basis and no Note.
   - Phone verified shows "Reference RECORDED" and "Posted NO" only.
   **Recommend:**
   - The phone shows the same sections, words and values as desktop in one column (D-111, the F-28, F-30 and F-33 precedent).
   - "Record observation" opens the step form in the full-height `Drawer`, including the required Proof: on a phone the observation cannot be sent without it.
   - On the pinned Decide bar, "Reject" opens the `Drawer` with the Note (F-29/F-33 pattern).
   - Extra elements are listed (`extra element`).
10. **The observe board draws the form open under the heading "Look up JE-7741 in QuickBooks"; the step form's heading is the step's `label`.** **Recommend:** the form opens on press (D-98 (2)). Its heading and its submit button are the step's label, "Record observation". The board heading is not drawn. The help line sits under the choice, not under the button. Listed (`component`). **Option B:** the backend sends "Look up JE-7741 in QuickBooks" as the step `label`. The opener and the heading would then match the board, but the submit button would read the same words instead of "Record observation".
11. **The proof box.** The desktop board draws a card ("qb-screenshot-je7741.png", "Uploaded · 310 KB"). `StepForm`'s `EvidenceField` uses `ProofField`'s `drop` layout, a chip ("qb-screenshot-je7741.png · 310 KB" with "×"). **Recommend:** keep `drop`, as F-34 does for its workspace proof, so `StepForm.tsx` stays unchanged. Listed (`component`). **Option B:** a `layout` prop on `EvidenceField` set to `card`. That is a shared `StepForm` change, and F-34's boards would change with it.
12. **Frame items.** These are:
    - The phone "← My work · LED-0052 · Start" bar.
    - The "STATION n OF 5 · NAME" line.
    - The desktop top bar. Ada's review and verified boards show "Overview" and "Setup" from `/me` navigation.
    - The crumbs "FINANCE / LEDGER SOURCES / LED-0052" from `workspace.context.crumbs`, with no project tab bar.
    - The signed-in names "Bisi Ade · Finance" (investigating), "Chuka Eze · Finance" (observe) and "Ada Okafor · Finance Lead" (review, verified). The mock's Finance persona is Ada Okafor on all four, and no persona is added.
    These follow the F-17/F-33 frame as built. Listed (`frame item`, `sample data`).

### Exceptions to sign

13. **Every board string is data.** All of these come from fixtures:
    - Status labels: "CHIDI INVESTIGATING", "RECORD WHAT YOU FOUND", "AWAITING FINANCE DECISION", "VERIFIED".
    - Station names: Chidi investigates, Capture lineage, Record what was found, Independent review, Verified.
    - Fact labels and values: QUICKBOOKS, JE-7741, ACCRUAL REVERSAL, BISI ADE, "CHUKA EZE · FOUND", "NEW · NO PREDECESSOR", NO, "YES · 14 NOV".
    - The four answers, the agent's steps and sources, "Started 15:12" and the re-check sentence.
    No board string is in `src/`. Case and time formats follow the library (`When`, `Tag`): category `component`.
14. **Agent card.** The existing `AgentCard`/`LineAgent` draws "Chidi · Finance agent · step 3 of 4", "WORKING", the four steps and their sources from `item.agent`, in the side column (F-33 line layout). "Ask Chidi" is the existing `workspace.links` `assistant` link to `/assistant`, with no work-item context (G-C-4). Agent work is never shown as an observation, a decision or a verified result.
15. **Driven observe state.** Both observe boards are compared against the driven page described in Conflicts 2. The driver's only DOM edits are the freeze (values copied into attributes, scripts removed, `<base>` added). It does not submit.
16. **Visual waivers.** Scores under 90 are waived board by board in `fidelity-exceptions.json`, citing D-83 and the shared frame, after the design engineer signs. A board under the 70 floor needs its own one-board floor exception, as D-112 did for SCR-08-mobile and SCR-30-mobile-verified.

## Boards

| Board | File (`design/canvas/finance/project/`) | Page | Mock |
|---|---|---|---|
| SCR-58 investigating, desktop / phone | `SCR-58-desktop-investigating.dc.html`, `SCR-58-mobile-investigating.dc.html` | `/work/W-4201` | persona `finance_lead`, live |
| SCR-58 observe | `SCR-58-desktop-observe.dc.html`, `SCR-58-mobile-observe.dc.html` | `/work/W-4202` | driver: reset, press "Record observation", choose Found, upload `qb-screenshot-je7741.png` (310 KB), freeze; on the phone the Drawer is open |
| SCR-58 review | `SCR-58-desktop-review.dc.html`, `SCR-58-mobile-review.dc.html` | `/work/W-4203` | persona `finance_lead`, live |
| SCR-58 verified | `SCR-58-desktop-verified.dc.html`, `SCR-58-mobile-verified.dc.html` | `/work/W-4204` | persona `finance_lead`, live |

Each fidelity run starts with `POST /__mock/reset`, so W-4202 and W-4203 are not served from an override. The driver is `delivery/features/F-45/round-<N>/fidelity/drive-states.mjs`. After the drive, `GET /__mock/workspace-log` shows no step.

## Summary
- A Finance person opens LED-0052 "QuickBooks journal JE-7741 · October" in the F-17 line workspace. While Chidi works, they see the source he is reading (provider, reference, treatment) and his steps with their sources.
- The observer looks the entry up in QuickBooks themselves. They record Found, Not found, Unknown or More than one with a required proof file, through F-17's step form. The re-read shows the next station, or the backend's hold after Unknown or More than one.
- An independent reviewer approves or rejects the reference in place through F-33's inline Decide. The item reads "Verified" only from the re-read `state`, with its stated negatives (Posting performed NO, Authenticity certified NO, Completeness certified NO).
- Controls come only from `you_can_act`, `disabled_reason` and the steps sent; nothing reads `/me`. All three ledger policy values are NOT SET, so every fixture is sample-marked and the unset reviewer is a hold with no control. No amount appears.
- New: fixtures W-4201 to W-4213 with their sidecars, `ledger_sources` added to F-33's Finance line layout, one additive mock fix (the workspace step's proof upload, shared with F-34), and the phone "×" size inside the step form. No contract change. Contract mock only.

## Context
- Work item page and frame: `frontend/src/features/work-item/WorkItemView.tsx` (`LineHeader`, crumbs) and `WorkItemOverview.tsx:698-728`. F-33 adds two `line_key === 'income_schedules'` checks there: stations and agent drawn in the workspace, and a decided task not repeated.
- Workspace (F-33 tree):
  - `frontend/src/features/workspace/Workspace.tsx`. `INCOME_LINE` is `:105`, `bannerTone` is `:154-161`, the phone `Drawer` rule `inDrawer` is `:180`, `incomeLine` with `LineStations` and `agentSide` is `:181`, `:447`, `:560`, and `Workspace` with `income` is `:643-646`.
  - `Sections.tsx`: `facts`, `text`; an absent value reads "Unknown".
  - `Steps.tsx`: `StepControl`, `disabled_reason` at `:43-55`, `Consequence`.
  - `StepForm.tsx`: `EvidenceField` over `ProofField` and `useEvidenceUpload` at `:123-148`; `stepRequest` puts evidence ids in `evidence_ids` at `:74-90`.
  - `useWorkspaceStep.ts` (key, revision, replay, `STEP_TEXT`), `usePageReload.ts`, `labels.ts`, `proposals.ts` (`stepVerdict`), `Links.tsx`, `InlineDecide.tsx` (`DECIDE_TEXT`, a phone `Drawer` for verdicts that need a note) and `workspace.css:221-240` (the F-33 line rules).
- Decide flow (reuse, do not change): `frontend/src/features/decide/useDecision.ts`; `DecideStates.tsx` (`cannotActCopy` `:31-61`, `UncertainNotice`); `format.ts` (`NOTE_MAX`, `VERDICT_WORDS`, `findDecisionTask`).
- Proof: `frontend/src/features/response/ProofField.tsx`. Its chip remove "×" is `resp-chip__remove`, 24px (`response.css:77`). F-31 round 3 raised it to `--control-phone` inside its own panel on the F-31 branch, not merged. `useEvidenceUpload.ts` re-reads the case revision through E-WORK-ITEM after a 409.
- Mock:
  - `frontend/mock/server.mjs:261-264` routes E-EVIDENCE-UPLOAD for `C-SETUP-*` to `evidence.mjs` and every other case to `response.mjs`.
  - `frontend/mock/response.mjs` `upload` is at `:108-138`. It accepts only kinds named by response tasks, `reconcile` or `rfp_outcome`, so **a workspace step's proof is refused today**. Its order of checks is CSRF, then persona `none` (403), then the case served (404), then the body schema (422), then the kind (422), then `case_revision` (409), then the grant (403). An upload bumps `case_revision` on every served item of the case.
  - `frontend/mock/workspace.mjs`: E-WORK-STEP `<id>.steps.json` scripts per step key (a failure with `next: true` is written and then fails), and `<id>.next.json`.
  - `server.mjs` decide: `<id>.<verdict>.json` sidecars; a `<id>.next.json` makes the first decide 409, so no review fixture has one. The F-33 `W-2712` pattern covers an uncertain decide (sidecars in `effect_uncertain`).
- Setup keys: `frontend/mock/fixtures/setup/finance.desktop.json:343-379`, all `set: false`, `holds_work: true`.
- F-47 (`delivery/features/F-47/spec.md:84`, `:96`): the "Record a ledger source" start lands on `W-4402` (LED-0053, `case_id: C-FIN-LEDGER`, revision 2 in `start-work.mjs`'s own revision map).
- Highest used ids: F-33 `W-2712`, F-47 `W-4402`. This feature takes `W-4201`…`W-4213` and `T-4202`…`T-4212` (reserve to W-4299 and T-4299).
- Tests that must stay green: `tests/workspace.test.tsx`, `tests/workspace-step.test.tsx`, `tests/workspace-mock.test.ts`, `tests/income-schedule.test.tsx`, `tests/income-schedule-mock.test.ts`, `tests/decide.test.tsx`, `tests/decide-board.test.tsx`, `tests/mock-decide.test.ts`, `tests/response.test.tsx`, `tests/response-mock.test.ts`, `tests/mock-contract.test.ts`, `e2e/workspace.spec.ts`, `e2e/income-schedule.spec.ts`, `e2e/response.spec.ts`.

## Contract

### E-WORK-ITEM `GET /api/v1/work/{work_id}` (unchanged)
- Read by `useWorkItem`. The page draws `workspace` in returned order for `line_key: "ledger_sources"`. The only branching is the shared Finance line layout (Lanes), which places the stations, the agent and the Decide panel.
- 401 shows the signed-out state with `next=/work/<id>`. 403 and 404 look the same (`NoAccessState`): no title, no fact, no further call. A 5xx shows `WorkErrorCard` with Retry. Loading shows `LoadingState`.
- After any write the page re-reads (`usePageReload`). Nothing is shown as recorded, approved or verified from a 200 body.

### Fixtures
All fixtures share these fields:
- `sample: true`, `reference: "LED-0052"`, `title: "QuickBooks journal JE-7741 · October"`.
- `case_id: "C-LED-0052"`, `case_revision: 4`.
- `workspace.line_key: "ledger_sources"`, `screen: "SCR-58"`, `view` = the state name.
- Crumbs FINANCE / LEDGER SOURCES / LED-0052, and no `context.project`.
- 5 `stations`: Chidi investigates, Capture lineage, Record what was found, Independent review, Verified.

| Id | `state`, `workspace.status` (label, tone), stations | Sections | Tasks and steps |
|---|---|---|---|
| W-4201 investigating | `processing`, "CHIDI INVESTIGATING" `agent`; station 1 `current_agent` | `facts` "Source": Provider "QUICKBOOKS", Reference "JE-7741", Treatment "ACCRUAL REVERSAL". `item.agent` is working, with 4 steps: "Read the ledger source file" (done, source "QB_EXPORT_JE7741.PDF"), "Checked date and period" (done, "28 OCT · 2026-10"), "Checked where it came from" (done, "QUICKBOOKS · REALM PSL-NG"), "Capture the lineage" (not started). `started_at` `2026-11-14T14:12:00Z` (15:12 Lagos). `workspace.links` `assistant` "Ask Chidi" | `tasks: []`; no steps |
| W-4202 observe | `action_needed`, "RECORD WHAT YOU FOUND" `person`; stations 1-2 `done`, 3 `current` | none | `tasks: []`. Step `record_observation` "Record observation" (primary, `applies_to: workspace`). Fields: `found` `choice`, required, label "What you found", options `found` "Found" / `not_found` "Not found" / `unknown` "Unknown" / `more_than_one` "More than one", no `value`, `help` "Recording what you saw isn't an approval. “Unknown” or “More than one” holds the check."; `proof` `evidence`, required, label "Proof", `evidence_kind: "ledger_observation"`. `consequence` "What happens next: an independent reviewer (not Bisi, who captured it, and not you) decides." `W-4202.steps.json` scripts 200 `done`, message "Observation recorded." `W-4202.next.json` = the review content, seen by the observer: `T-4202` `you_can_act: false`, `cannot_act_reason: prepared_by_you`, Observed by "CHUKA EZE · FOUND" |
| W-4203 review (can act) | `action_needed`, "AWAITING FINANCE DECISION" `person`; station 4 `current` | `facts` "Evidence": Captured by "BISI ADE", Observed by "CHUKA EZE · FOUND", Lineage "NEW · NO PREDECESSOR" | `T-4203`: `kind: decide`, `required_role: "Ledger reviewer"`, `you_can_act: true`, `revision: 1`, `decision.version.label` "LED-0052 v1", `decision.basis` "Approve JE-7741 as a supplied reference. You captured nothing and observed nothing here, so you can review.", `prepared_by {name: "Bisi Ade", role: "Finance", is_you: false, with_agent: "chidi"}`. Steps: `approve_reference` "Approve reference" (primary, `verdict: approve`, `task_id: T-4203`, `consequence` "Ledger review is approve or reject only. Approving records a reference; nothing is posted and authenticity isn't certified."); `reject_reference` "Reject" (danger, `verdict: reject`, `task_id: T-4203`). Sidecars: `W-4203.approve.json` = the verified content; `W-4203.reject.json` = status "REJECTED" `stopped`, station 4 `stopped`, read-only, no steps. Each is one revision higher, with the task `you_can_act: false`, `cannot_act_reason: already_decided`. **No `W-4203.next.json`.** |
| W-4204 verified | `verified`, "VERIFIED" `verified`; all stations `done` | `facts` "Recorded": Posting performed "NO", Authenticity certified "NO", Completeness certified "NO", Reference recorded "YES · 14 NOV". Then an untitled `text`: "A reference only. If the source changes later, a re-check reopens it." | task `already_decided`; no steps |
| W-4205 reviewer not set | `setup_needed`, "SETUP NEEDED" `stopped`; station 4 `stopped` | `facts` "Why it's held": "Who reviews ledger sources", value "NOT SET", tag `stopped`. `next`: ["An admin sets Who reviews ledger sources in Setup · Finance rules. The review starts then."] | `tasks: []`; no steps. No `required_role` and no reviewer anywhere |
| W-4206 reviewer took part | as W-4203 | as W-4203 | `T-4206` `you_can_act: false`, `cannot_act_reason: prepared_by_you`; both verdict steps sent |
| W-4207 not your role | as W-4203 | as W-4203 | `T-4207` `you_can_act: false`, `cannot_act_reason: not_your_role`; both verdict steps sent |
| W-4208 observe, answered Unknown | as W-4202 | as W-4202 | as W-4202. `W-4208.steps.json` scripts 200 `done`. `W-4208.next.json` = the W-4209 content |
| W-4209 held after Unknown | `waiting`, "CHECK HELD" `stopped`; station 3 `stopped` | `facts` "Why it's held": What was found "UNKNOWN" (tag `stopped`), Verification rules "NOT SET" (tag `stopped`). `next`: ["The check stays held. What happens next depends on Verification rules, which an admin sets in Setup · Finance rules."] | `tasks: []`; no steps |
| W-4210 observer captured it | as W-4202 | as W-4202 | `record_observation` with `disabled_reason` "You captured this source, so someone else must look it up." |
| W-4211 values not known | as W-4201 | as W-4201, but Treatment has no `value` and the third agent step has no `source` | as W-4201 |
| W-4212 uncertain decide | as W-4203 | as W-4203 | `T-4212`, as T-4203. Sidecars `W-4212.approve.json` and `W-4212.reject.json` have `state: effect_uncertain` and status "CHECKING" `uncertain`, so the decide answers 200 with `work_state: effect_uncertain` (the F-33 `W-2712` pattern) |
| W-4213 uncertain observation | as W-4202 | as W-4202 | as W-4202. `W-4213.steps.json` scripts `record_observation` 500 with `next: true` (written, then fails). `W-4213.next.json` = the review content as the observer sees it |

Each fixture validates against the generated E-WORK-ITEM 200 schema once the overlay (`steps[].verdict`, `workspace.links`) is stripped. No fixture carries a `money` value or an amount in any text.

### Overlay proposals (mock only; each recorded in build.md for the backend developer)
- `workspace.steps[].verdict` (F-33, G-C-1): reused as is. Values here are `approve` and `reject` only.
- `workspace.links[]` `assistant` (X-LINKS): reused.
- `line_key: "ledger_sources"`, the `view` names and `evidence_kind: "ledger_observation"`: proposal names (gaps `:11`, `:168`).
- **Values the boards show that no endpoint supplies:** none. Every value is a typed `facts` value, a `text` section, `next`, a step field or `item.agent`.

### E-EVIDENCE-UPLOAD `POST /api/v1/cases/{case_id}/evidence` (unchanged operation)
- **Through `StepForm`'s `EvidenceField` and `useEvidenceUpload` only.** The request is `{kind: "ledger_observation", filename, content_base64, case_revision: <item.case_revision as read>}` to `/api/v1/cases/C-LED-0052/evidence`, with CSRF. It is sent once per file chosen, and the step is never sent before the upload answers 200.
- **200:** the chip shows the file. The returned `evidence_id` goes into the step's `evidence_ids`, and the new `case_revision` is kept.
- **Errors:**
  - 409 re-reads the case revision (the hook's existing reload) and asks again only on a new press.
  - 422 and 5xx show `ProofField`'s problem, and the step stays unsent.
  - 403 shows the access message (`onAccessError`).
  - "×" removes the file from this observation only. The page never says "deleted": the uploaded proof stays on the case.
- **Mock seam (shared with F-34):** `mock/response.mjs` `upload` also accepts a `kind` named by an `evidence` field of a `workspace.steps[]` step with no `disabled_reason`, on a served item of that case. It grants that upload only on that condition. The change is additive: every existing kind and grant is unchanged. **Whichever of F-34 and F-45 builds first owns this change, and the other reuses it as is.** If F-34 is merged first, F-45 makes no change to `response.mjs`. The integration owner is the coordinator.

### E-WORK-STEP `POST /api/v1/work/{work_id}/steps` (record what you found)
- **Request:** `{expected_revision: workspace.revision, step: "record_observation", inputs: {found: <one options[].value>}, evidence_ids: [<the uploaded id>], idempotency_key: <UUID>}`, header `X-CSRFToken`, through the existing `useWorkspaceStep` and `stepRequest`. The key is new per opened form and reused on a manual retry of the same press. There are no other keys.
- **Client checks before any request:** both fields are required ("Add what you found to continue.", "Add proof to continue."), shown under the field, announced, with focus on the first. Nothing is pre-chosen.
- **200 `done`:** the page re-reads and draws what it returns. W-4202 shows the review station with the `prepared_by_you` copy. W-4208 shows the W-4209 hold. The notice comes from the response `message` or the F-17 default.
- **Errors:**
  - 409 re-reads, shows the stale sentence and keeps the choice and the uploaded proof.
  - 422 shows the message under the named field.
  - 5xx, network or timeout: re-read first, then show `STEP_TEXT.failed` ("We couldn't confirm this step. Check the page before trying again."). Try again keeps the same key. `outcome: uncertain` shows the existing reconcile panel.
  - The page never says "recorded" before the re-read, and never resends on its own.
- **Permission:** the step is drawn only if it is sent. With `disabled_reason` (W-4210) it is drawn inert with the reason, no form opens and no upload or step is sent.

### E-TASK-CLAIM `POST /api/v1/tasks/{task_id}/claim` and E-TASK-DECIDE `POST /api/v1/tasks/{task_id}/decision`
- **Through `InlineDecide` over `useDecision(work_id, task_id)` only;** there is no new write path. The claim is sent once per task revision, and only when the task's `you_can_act` is true. Until it answers, the buttons are off and the panel shows the existing "Getting this review ready…" line.
- **Decide request:** `{verdict, note?, expected_revision: <task revision>}` with `X-CSRFToken` and no extra keys. Reject needs a non-blank note of at most `NOTE_MAX` (2000), checked before any request ("Add a note to reject it.", under the Note, announced, with focus on the note). Approve sends no note.
- **200:** the page re-reads and draws the re-read state (verified, or rejected read-only). The done notice is the existing `VERDICT_WORDS` heading only once the effect is settled. "Verified" appears only from the re-read `state: verified`.
- **Errors:**
  - 401 shows the signed-out state.
  - 403 shows the read-only view keyed on the re-read `cannot_act_reason`.
  - 409 shows the stale view, keeps the note and sends nothing on its own.
  - 422 shows the backend message under the note.
  - 5xx, network or timeout: re-read first and show `UncertainNotice`. The page never says "approved" or "rejected" from the click, and the next decide needs a new deliberate press. A 200 with `work_state: effect_uncertain` (W-4212) is shown as the re-read says, never as verified.
- **Permission and tenant:** the buttons appear only when `tasks[i].you_can_act` is true for the step's `task_id`. Otherwise the panel shows `cannotActCopy(cannot_act_reason, task)` and no button. The page has no role, person, `prepared_by` or observer rule, and does not read `/me`.

### Screen states
- **Loading:** the existing skeleton.
- **Empty:** a workspace with no sections draws the header, status and stations only.
- **Error:** the problem card with Retry.
- **Success:** the four board states and W-4206 to W-4213.
- **Held:** W-4205 and W-4209.
- **Restricted:** a section or item with `restricted: true` draws "Restricted", and its value is never shown.

## Lanes
- **Frontend lane (builder, Opus for the first build: high risk, D-64).** It owns:
  - `frontend/src/features/workspace/labels.ts`: a `FINANCE_BOARD_LINES` set (`income_schedules`, `ledger_sources`) and a predicate. `Workspace.tsx` (`bannerTone`, `inDrawer`, `incomeLine`, `income`) and `frontend/src/features/work-item/WorkItemOverview.tsx:703,727` use it instead of `=== 'income_schedules'`. Behaviour on the income line is unchanged.
  - Additive rules in `workspace.css` (tokens only). The step form's and `Drawer`'s `.resp-chip__remove` is at least `var(--control-phone)` below 720px. If F-31's rule is already in dlv-00, this reuses it.
  - The `upload` fix in `frontend/mock/response.mjs`, unless F-34 has merged it (Contract).
  - Fixtures `frontend/mock/fixtures/work/W-4201…W-4213` with the `.steps`, `.next`, `.approve` and `.reject` sidecars named above.
  - Tests: `frontend/tests/ledger-source.test.tsx`, `frontend/tests/ledger-source-mock.test.ts` and `frontend/e2e/ledger-source.spec.ts`. In `frontend/tests/mock-contract.test.ts` the builder touches only the new fixtures; F-33's strip already covers them.
  - Factory files in `delivery/features/F-45/` (`fidelity-exceptions.json`, `round-<N>/`, the driver).
- **Shared, read only:**
  - `src/features/workspace/InlineDecide.tsx`, `Steps.tsx`, `StepForm.tsx`, `Sections.tsx`, `proposals.ts`, `useWorkspaceStep.ts`. Change one only if a test proves a defect, and list it.
  - `src/features/decide/**`, `src/features/response/**`, `src/features/start-work/**`, `src/components/**`, `src/shell/**`, `src/api/**` (including `schema.d.ts`), `src/styles/**`.
  - `mock/server.mjs`, `mock/workspace.mjs`, `mock/start-work.mjs`, `mock/evidence.mjs`, and every existing fixture (including F-33's `W-27xx` and F-47's `W-4402`).
  - `frontend/package.json`, the lock file, `playwright.config.ts`, `vitest.config.ts`, `architecture/**`, `design/**`, `apps/**`.
  - The protected `delivery/checks.sh`, `delivery/config.json` and `delivery/merge-policy.json`.
- **Backend lane:** none. For build.md (not blocking part 1):
  - G-58-3 (the state after Unknown or More than one, and who is told) and G-58-4 (the reason code for a capturer or observer).
  - Three separate people enforced for every ledger source.
  - The `setup_needed` shape for "Who reviews ledger sources", and which station "Verification rules" holds.
  - G-C-1 (`steps[].verdict`, approve and reject only), G-C-4 ("Ask Chidi"), G-58-5 (re-check).
  - The `evidence_kind` name, and which case a ledger source's proof lives on.
  - Confirmation that the factory reads nothing from QuickBooks.
  - The readiness questions 1 to 3.
- **Integration owner: the coordinator.**
  - `labels.ts`, `Workspace.tsx`, `WorkItemOverview.tsx`, `workspace.css` and `mock-contract.test.ts` are likely touched by F-42 and F-43 in parallel, as they bring their Finance lines into the same layout. Whichever merges second merges the current base, adds its line to `FINANCE_BOARD_LINES`, and reruns `delivery/checks.sh` and the e2e.
  - `mock/response.mjs` `upload` is shared with F-34 (above).
  - **F-47 landing:** whichever of F-45 and F-47 merges second points F-47's mock `WORK_IDS.ledger_sources` at `W-4201` and updates F-47's landing assertions. `W-4402` stays as a fixture unless no test reads it. The case ids stay split (Assumptions).
- **Ports:** app 4970, mock 4971. `cd frontend && E2E_PORT=4970 MOCK_PORT=4971 npx playwright test e2e/ledger-source.spec.ts e2e/income-schedule.spec.ts e2e/workspace.spec.ts e2e/response.spec.ts`, with `timezoneId: 'Africa/Lagos'`. e2e is not in `checks.sh`, so paste its output in build.md.
- **Fidelity:** on a production build, one run per round over all 8 boards (D-64).
- **Disk:** run `df -h /System/Volumes/Data` first and stop under 3 GB. It was at 4.1 GB on 18 Nov, so clear merged worktrees before the build. Delete `frontend/test-results` after.
- **Review routing (high risk):** technical (Sonnet), UI (fidelity gate, Opus for the first review), UX (Sonnet), QA (Opus), security (Opus: an authority-bearing approval write and an append-only upload grant), PMO. Product acceptance is required. The PR merges only on the design engineer's "merge".
- **Size:** about 900 to 1,300 lines, most of it fixtures and tests. One PR.

## Acceptance criteria

### Page
1. **Four states from data.** `/work/W-4201`…`W-4204` show their fixture's status label and tone, stations, sections, agent card, facts and text, and nothing else. No board string is in `src`: `grep -rn "CHIDI INVESTIGATING\|RECORD WHAT YOU FOUND\|JE-7741\|NO PREDECESSOR\|Ledger reviewer\|re-check reopens" frontend/src` returns nothing. — verify: `cd frontend && npx vitest run tests/ledger-source.test.tsx`; the four pages at 1440 and 390.
2. **No amount and no computing.** No page or sidecar of this feature shows a currency sign or an amount. Changing a fact value in a fixture copy changes only that text. The diff under `frontend/src` adds no `parseFloat`, `Number(`, `.reduce(` or `compactAmount`. — verify: component test over every fixture (`document.body.textContent` has no "₦" and no digit-group amount); `git diff -U0 dlv-00-delivery-setup -- frontend/src | grep -nE "parseFloat|Number\(|\.reduce\(|compactAmount"` returns nothing.
3. **Unknown is never 0, blank or a dash.** W-4211 shows "Unknown" for Treatment and draws the third agent step with no invented source. The Treatment cell is never empty, "0", "-" or "—". — verify: component test on W-4211.
4. **Sample-marked.** Every fixture page shows the shared `SampleLabel` ("SAMPLE DATA") because the record says `sample: true`; a copy with `sample: false` does not. — verify: component test.
5. **Reviewer not set is a hold.** W-4205 shows the backend's status, the "Who reviews ledger sources · NOT SET" fact and its `next` sentence. There is no Decide panel, no button and no claim or decide request, and no reviewer's name or role appears anywhere on the page. No page of this feature draws a control for any of the three ledger keys. — verify: component test with a recording `fetch` (zero POSTs); `document.body.textContent` checked for "Ada Okafor" and "Ledger reviewer" (both absent).
6. **Unknown or More than one is the backend's hold.** On W-4208, choosing Unknown with proof and pressing "Record observation" sends one step with `inputs.found: "unknown"`. The re-read shows W-4209's "CHECK HELD", station 3 stopped, its facts and `next`, with no step and no Decide panel. The page draws the hold only from the re-read: with a test double whose re-read still serves the observe state, it shows no hold. — verify: component tests with a recording `fetch`.
7. **Controls only from `you_can_act`, `disabled_reason` and the steps.**
   - W-4203 shows "Approve reference" and "Reject" under "Decide · Ledger reviewer", with the basis and the approve consequence as returned and the Note labelled "Note (needed to reject)". There is no Return button.
   - W-4206 shows "You prepared LED-0052 v1, so someone else must review it." and W-4207 the `not_your_role` copy, each with no button and no claim sent.
   - W-4210 shows "Record observation" inert with its reason; pressing it opens no form and sends nothing.
   - Personas `finance_lead`, `ceo` and `pm` see the same controls on every fixture. The new code does not read `/me`: `git diff dlv-00-delivery-setup -- frontend/src | grep -nE "useMe|/me\b|is_you|prepared_by"` adds nothing.
   — verify: component tests with three personas and a recording `fetch`; the grep.
8. **Agent work is not a decision.**
   - On W-4201, Chidi's steps, sources, "WORKING" and "Started 15:12" render in the agent style in the side column.
   - There is no observe step and no decide control, and nothing reads "found", "verified" or "approved".
   - "Ask Chidi" links to `/assistant`.
   - No request goes to any host but the app's API: the e2e request log has only `/api/v1/` and `/__mock/` paths.
   — verify: component test; link href; e2e request log.
9. **Verified only when the re-read says so.**
   - W-4204 shows "VERIFIED" from its status, with Posting performed, Authenticity certified and Completeness certified "NO" and Reference recorded "YES · 14 NOV", all from `facts`.
   - Pressing "Approve reference" on W-4203 shows "Verified" only after the re-read serves `W-4203.approve.json` (`state: verified`).
   - With the decide answering 200 but the re-read still serving the review state (test double), the page does not say "Verified" or "approved".
   - W-4204 has no step and no button.
   — verify: component tests with a recording `fetch`.

### Writes
10. **Observation with proof.** On W-4202, pressing "Record observation" opens the step form. "What you found" is a required choice of four with nothing selected, and "Proof" is required. Submitting with either empty sends nothing and shows the field message, announced, with focus on the first. Then:
    1. Choosing a file sends one E-EVIDENCE-UPLOAD to `/api/v1/cases/C-LED-0052/evidence` with `kind: "ledger_observation"`, `case_revision: 4` and CSRF. It validates against the generated request schema.
    2. Submitting sends exactly one POST `/api/v1/work/W-4202/steps` with CSRF, `expected_revision`, `step: "record_observation"`, `inputs: {found: "found"}`, `evidence_ids: ["EV-C-LED-0052-1"]` and a UUID `idempotency_key`, and no other keys. A double press sends one.
    3. The re-read shows the review station with the `prepared_by_you` copy and no Decide button.
    The page never says "recorded" before the re-read. — verify: component tests; e2e request log.
11. **Upload failures keep the step unsent.**
    - A 5xx on the upload shows `ProofField`'s problem and sends no step.
    - A 409 re-reads the case revision, and the next upload carries the re-read value.
    - Removing the file with "×" leaves "Proof" empty, and submitting then sends nothing.
    - An upload as persona `none` answers 403.
    - On the mock, an upload to `C-LED-0052` with a kind no served step names answers 422. The existing response, reconcile and RFP uploads behave as before.
    — verify: `tests/ledger-source-mock.test.ts`; `tests/response-mock.test.ts` unchanged and green; component test.
12. **Reject needs a note.** Pressing "Reject" with an empty or blank note sends nothing and shows "Add a note to reject it." under the field, announced, with focus on it. A note over 2000 characters is refused before sending. With a note, the page sends one POST with `verdict: "reject"` and the trimmed note, and the re-read shows "REJECTED" read-only with no "Correct" step. Approve sends `{verdict: "approve", expected_revision: 1}` with no note, after one claim to `/api/v1/tasks/T-4203/claim`. — verify: component tests; e2e request log.
13. **No write when the person cannot act.** On W-4201, W-4204, W-4205, W-4206, W-4207, W-4209 and W-4210, no claim, decide, upload or step is sent, whatever is pressed or typed. — verify: e2e request log (zero POSTs).
14. **Backend refusals are shown.**
    - With `psl_mock_scenario` 403, the decide shows the read-only view and no "approved", and the step shows "You can't take that step."
    - A 409 on decide shows the stale view, keeps the note and sends again only on a new press with the new revision.
    - A 409 on the step re-reads, keeps the choice and the proof, and sends nothing on its own.
    - A 422 shows the message under the field or the note.
    — verify: component tests; `tests/ledger-source-mock.test.ts`.
15. **Uncertain decide.**
    - On W-4212, Approve (and, after a reset, Reject with a note) answers 200 with `work_state: effect_uncertain`. The page re-reads and shows the re-read status, never "Verified", "approved" or "rejected".
    - On W-4203, a network failure, timeout or 500 on decide re-reads the item before anything else and shows `UncertainNotice`. No second decision is sent on its own: one POST after 60 s with fake timers.
    — verify: component test; `tests/ledger-source-mock.test.ts`; e2e with a routed abort.
16. **Uncertain observation.** On W-4213, the step answers 500 after it is written. The page re-reads first, draws the re-read review state and shows `STEP_TEXT.failed`, never "Observation recorded." A Try again (if still offered) reuses the same key, and the mock log shows one applied step. — verify: component test; `GET /__mock/workspace-log` in `tests/ledger-source-mock.test.ts`.
17. **Access.** 401 on read or write shows the signed-out state with `next=/work/<id>`. 403 and 404 on read look the same and show no title, fact or agent step. Persona `none` gets the same not-open view with no further call. — verify: component tests with a recording `fetch`.

### Frame and layout
18. **Phone (D-92c).** At 390 each state is one column with the same sections, words and values as desktop.
    - "Record observation" opens the step form in the full-height `Drawer`, with the `Select` and the Proof.
    - The Decide bar is pinned with "Approve reference" and "Reject". "Reject" opens the `Drawer` with the Note.
    - Escape and Cancel close the Drawer and return focus to the button that opened it. There is no sideways scroll.
    - Every button, link, select, file button and Try again is at least 44 by 44 px, **including the uploaded file chip's remove "×" after an upload** (F-31 QA-2-1). Links inside sentences are exempt (D-95).
    — verify: e2e at 390 measuring bounding boxes after an upload.

### Quality
19. **Fidelity (D-64, D-83).** One design-fidelity run per round over the 8 boards, on a production build at `--width 1440` and `--width 390`, with observe driven as in Boards.
    - Every board's element coverage after approved exceptions is 100%.
    - Visual is at least 90, or a board-level waiver citing D-83 in `fidelity-exceptions.json` with visual at least 70. Lower needs a signed one-board floor exception.
    - Every exception has `role`, `name`, `category`, `reason` and `approved_by`, and maps to a Conflicts number. None covers a value the data can supply (a name, a date, a tag, a reference, a sentence).
    - The UI reviewer's side-by-side reading finds no fixable gap.
    — verify: the fidelity command per board; `round-<N>/fidelity/scores.txt`; the driver and `frozen/*.html`.
20. **Accessibility.** There are no axe violations (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`) at 1440 and 390 on:
    - W-4201 to W-4205 and W-4209;
    - the open step form with an uploaded file, and the open Drawer;
    - the note error, the field errors, the uncertain notice and the not-open view.
    Every field is labelled, errors are announced, status words are in text and not colour only, focus is visible, and the agent pulse does not animate under `reducedMotion: 'reduce'`. — verify: `e2e/ledger-source.spec.ts`.
21. **Tokens and components only.** The diff adds no `#hex`, `rgb(`, `hsl(` or raw px outside tokens in `features/workspace/*.css`. It adds no local copy of a component that `@/components` exports (`Button`, `Drawer`, `Select`, `TextArea`, `Callout`, `Panel`, `Tag`, `Segmented`) or of `ProofField`. — verify: grep on the diff.
22. **Mock matches the contract.** `tests/ledger-source-mock.test.ts` checks that:
    - every new fixture and sidecar validates against the generated E-WORK-ITEM schema with the overlay stripped, and every one is `sample: true` with `line_key: "ledger_sources"`;
    - the upload, then the step, on W-4202 serves `W-4202.next.json`, and on W-4208 serves the hold;
    - claim then approve on W-4203 serves `W-4203.approve.json`;
    - reject without a note answers 422, a stale revision 409, and W-4206's decide 403;
    - W-4212 answers `effect_uncertain`;
    - reset clears every override and the issued evidence ids.
    — verify: `cd frontend && npx vitest run tests/ledger-source.test.tsx tests/ledger-source-mock.test.ts tests/mock-contract.test.ts`.
23. **Contract not extended.** `git diff --stat` shows no change in `frontend/src/api/**`, `frontend/src/features/decide/**`, `frontend/src/features/response/**`, `frontend/src/features/start-work/**`, `frontend/src/shell/**`, `frontend/mock/server.mjs`, `frontend/mock/workspace.mjs`, `frontend/mock/start-work.mjs`, any existing fixture, `apps/**`, `architecture/**`, `design/**` or the protected paths. The only allowed exception is the F-47 repoint, if F-45 merges second. `mock/response.mjs` changes only in `upload`, additively. Every overlay field is listed as a contract proposal in build.md. — verify: `git diff --stat`; `git diff frontend/mock/response.mjs`; build.md.
24. **Existing tests green.** `delivery/checks.sh` passes, and the tests listed under Context pass unchanged. This includes F-33's income schedule tests (the line layout is shared now) and `tests/response-mock.test.ts`. If F-45 merges second it also includes F-47's start tests, with the landing assertion on `W-4201`. — verify: `delivery/checks.sh`; `cd frontend && npx vitest run` and the e2e command under Lanes, pasted in build.md.
25. **build.md evidence.** It records:
    - the commands and their results;
    - the 8 scores and waivers, and every exception with its Conflicts number;
    - every proposal and backend item, and the held list from "What is sent";
    - who owns the upload seam (F-34 or F-45), and the F-47 landing status.
    — verify: file content.

## Out of scope
- Part 2: the duplicate refusal and its compare table (two amounts that only the backend may supply and flag), the rejected board, "Correct" and `continues`, and "Open LED-0049".
- Any QuickBooks integration, lookup, link or "check in QuickBooks" button; any posting or ledger entry; certifying authenticity or completeness.
- Comparing references, files or amounts in the browser to suggest a duplicate; any amount, total or count worked out in the browser.
- Naming or choosing a reviewer or observer; editing Setup rules (SCR-13); a link to Setup (G-C-3); filling any NOT SET value.
- Separation-of-duties logic in the page: comparing the signed-in person with `prepared_by`, the capturer or the observer, or reading `/me` to show or hide a control.
- A Return verdict, a Withdraw (`revoke`) step, or a re-check or reopen trigger (G-58-5).
- The SCR-04 "Record source" drawer (F-47), and repointing month-end (G-58-6).
- Changes to `InlineDecide`, `useDecision`, `StepForm`, `ProofField` or `IntakeField`. Automatic retries, and optimistic states from a 200 body.
- Backend, OpenAPI, `schema.d.ts` regeneration, `architecture/**`, `design/**`, `src/shell/**`, new npm dependencies.

## Conflicts with the boards
See "Conflicts with the boards (for the design engineer, before the build)" above: 7 need an answer, 5 are layout and 4 are exceptions to sign.

## Assumptions
- Work ids `W-4201`…`W-4213` and task ids `T-4202`…`T-4212`. Reason: the caller assigned W-42xx/T-42xx, and F-47 uses W-44xx.
- All fixtures sit on one case, `C-LED-0052` (revision 4), not F-47's `C-FIN-LEDGER`. Reason: F-47's start keeps its own revision map for `C-FIN-LEDGER` in `start-work.mjs`, while `response.mjs` reads the item's `case_revision`. Two owners of one case's revision would drift. Which case a ledger source's proof lives on is a backend question.
- The mock cannot branch a step on its inputs (`workspace.mjs` scripts by step key). So the Found and Unknown paths are two fixtures (W-4202, W-4208), and choosing Unknown on W-4202 still re-reads the review state on the mock. Reason: `workspace.mjs` stays unchanged. The tests assert the request, and the backend decides the real next state (G-58-3).
- The held-after-Unknown state is `waiting` with status "CHECK HELD" `stopped` at station 3, and its `next` sentence is sample wording. Reason: no board or source names it (G-58-3). The page draws whatever the backend sends.
- The rejected sidecar keeps the item's `state` as `cancelled` with status "REJECTED" `stopped`, read-only. Reason: the rejected board is part 2. The F-33 precedent applies.
- `required_role` "Ledger reviewer" and the version label "LED-0052 v1" appear only in the sample review fixtures. Reason: the board's panel title. `finance.ledger_sources.reviewer` is NOT SET, and W-4205 carries neither.
- The observation field names are `found` (options `found`, `not_found`, `unknown`, `more_than_one`) and `proof` (`evidence_kind: "ledger_observation"`). Reason: the gaps file names the step and choice (`:168`). The keys are proposals.
- The capturer and the observer are shown only as the backend's fact values ("BISI ADE", "CHUKA EZE · FOUND"). Reason: readiness binding 4. The page never derives who did what.
- The "×" size fix is a `workspace.css` rule, not a `response.css` change. Reason: `src/features/response/**` is shared and read only, and F-31 made the same scoped fix.
- `ledger_sources` joins F-33's income-line layout through one shared set in `labels.ts`. Reason: the SCR-58 boards draw the same station row, side agent card and inline Decide as SCR-54. One predicate is smaller than a second copy of each branch, and F-42 and F-43 can join it the same way.
- Ports 4970/4971. Reason: no spec uses them.
