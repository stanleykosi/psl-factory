# The weekly client report line: the PM writes four cited parts, Tola assembles, the PMO Lead reviews (contract mock only)

> Tasks: FE-LINE-WEEKLY, first part (R-WORKITEM, R-DECIDE; acceptance A-WORKSPACE frontend half, with A-WORKITEM, A-DECIDE and the F-17 and F-09 tests kept green). Architecture: package `architecture/packages/v7` (the `workspace` block and E-WORK-STEP are typed in `frontend/src/api/schema.d.ts:1693` and `:5217`; this feature changes no generated type); FE-LINE-WEEKLY at `architecture/packages/v7/delivery.md:2014`, no unresolved gates. Design: approved canvas version 1794581312-b166 (`design.py check --project .` run by the coordinator: passes, client-approved 13 Nov 2026). Screens: SCR-25, 8 artboards: `SCR-25-{desktop,mobile}`, `-invalid`, `-assembling`, `-review` (files in `design/canvas/project/`). Decision consumed: D-LINE-WORKSPACE (proposal). Model: `delivery/features/F-17/spec.md`, `F-18/spec.md`.

## Conflicts (for the design engineer, before the build)

Each item is a place where the boards, the v7 contract and the F-17 frame disagree. "Recommend" is what this spec builds if no answer comes. Items 1 to 4 change what the page looks like and need an answer; the rest are exceptions to confirm.

### Board vs contract

1. **The four parts are drawn as an always-open form; the frame opens a step form on press.** The default board (desktop) shows four text areas with cites, and two buttons under them, on load. In the contract the PM's words travel only as `steps[].fields[]` of E-WORK-STEP (`long_text` and `records`), and `features/workspace/Workspace.tsx` opens a step's form under its button when the button is pressed (`needsForm`, `open`). No `steps[]` field says "show this form open". Recommend: **build on the existing contract, form on press (Option A).**
   - Two workspace steps with the same eight fields (four `long_text` parts, four `records` cites): `send_to_tola` (primary, `consequence` = the board's "Next: Tola assembles the report on the client template; the PMO Lead reviews it before it goes to Lagoon Health.") and `save_draft` (secondary). Pressing either opens the form with the saved draft values as the field `value`s.
   - The loaded default page shows the saved parts as a read-only `text` section "Your update" (words and cites from the draft) so the page is not empty before the form opens.
   - Whole-board fidelity for `default` and `invalid` is scored on the form opened by a driver (as F-18 did, `drive-states.mjs`). The extras this makes (the two buttons above the form and the submit inside it, the read-only "Your update" copy) are exceptions.
   - **Option B for the design engineer:** a contract proposal `steps[].inline: boolean` ("open this form at load, in the main column") so the page matches the board with no driver. The backend developer decides. The frame cannot build it first (no local contract extension); it goes in build.md as a contract proposal either way.
2. **"+ cite a record" has no field kind of its own, but `records` covers it.** Start work's field kinds (D-START-INTAKE) include `records` (a `multiple` picker, `options_source: "line_options"`, `frontend/src/features/start-work/RecordPicker.tsx`, options from E-LINE-OPTIONS). Recommend: **one `records` field per part, named `status_cites`, `risks_cites`, `timeline_cites`, `next_steps_cites`**, rendered by the existing `IntakeField`/`RecordPicker`. Differences from the board (all exceptions): the picker is a combobox that lists the options E-LINE-OPTIONS returns for this line and field (the board draws "+ cite a record" as a link under chips); chosen records show as the picker's own chips, not as the board's "Cites:" label with linked references. Readiness said the pick lists come from the records panel; they cannot, because the picker reads E-LINE-OPTIONS. The panel and the pick list must therefore both be fixtures that agree (same references), and the backend must serve this week's records through E-LINE-OPTIONS (contract proposal, recorded in build.md).
3. **Line key.** F-17's W-2001 uses `line_key: "weekly_client_report"`. Start work registers this line as `weekly_report` (`frontend/mock/fixtures/start-work/lines.pm.json`), and the mock's E-LINE-OPTIONS only answers for registered lines and their intake fields (`frontend/mock/start-work.mjs` `optionsField`). Recommend: the F-21 fixtures use `line_key: "weekly_report"` and the mock serves the cite fields' options for step fields of an F-21 fixture through a small, additive hook (Lanes). If the backend names the key differently, only fixtures change.
4. **Page layout: where things sit.**
   - The boards put "This week's records · 5–11 Nov" and the agent note in a right-hand column and the Decide panel under the parts. The frame draws sections in returned order in the main column; only `suggestions` and workspace-scope steps sit in the side column (F-17 round 3, D-62). Recommend: **keep the frame's layout**; the records panel is five `facts` sections after the form, the agent note is the frame's header callout (`agent_note`). Exception category `frame layout`, as F-17.
   - The work item page keeps its own title, tabs (Overview and the others), facts strip and station track around the workspace (F-17 Conflicts 2 and 3). The boards `invalid`, `assembling` and `review` draw the project tab bar (Journey, Milestones 4, Documents 6, Money, Registers 6, Actions 9); the work item page draws its own tabs. Exception category `frame item`.
   - One `h1` per page. The default board's h1 is "Write this week's client update"; the other three desktop boards use "Weekly client report · 5–11 Nov". Recommend: the fixtures' item `title` carries those words per state, as F-17.
5. **Phone titles differ from desktop.** The mobile boards title the page "Client update · 5–11 Nov", "Weekly report" and "Review weekly report", and use phone back links ("← Lagoon Health", "← Project", "← My work"). The frame has one title for both widths. Recommend: **desktop wording at both widths**; the mobile-only wording is an exception; the phone back link is a frame item as in F-14 and F-16.
6. **Mobile default is a collapsed list; the frame draws the form.** The phone default board shows the four parts as rows with "✓ cited" or "to write" and "Tap to write and cite". Recommend: the phone shows the same read-only "Your update" section and the opened form as on desktop; the "✓ cited / to write" chips and the tap-to-expand rows are exceptions (there is no per-part state field). If the design engineer wants them, they need a contract proposal (a `tag` per part is already allowed on text items; the renderer does not draw it for `text` items today). Out of scope here.
7. **Invalid: two kinds of message and four parts.** The board shows only the two failing parts (Risks "TBD", Next steps with no cite) and two messages at the bottom: "Two parts can't be sent yet. Every part needs words and at least one record from 5–11 Nov." and "The report can't start before the week has ended. This week ended 11 Nov." The frame form shows all four parts and has one top-of-form message (the 422 `message`). Recommend: the 422 `message` is the first sentence; the second sentence is the `note` of the "Your update" section in the loaded fixture. The two good parts stay in the form (extra elements, exception). Per-part messages come from 422 `fields[].name` mapped to `status`, `risks`, `timeline`, `next_steps` (text) and the matching `*_cites`. The frontend writes none of these sentences. The design engineer should confirm what "before the week has ended" means (when does the backend refuse), since both messages appear together on the board; this spec only renders what the backend returns.
8. **"NEEDS FIXING" status.** The tag is `workspace.status` (label "Needs fixing", tone `stopped`) in the loaded invalid fixture. A 422 does not reload the item, so the tag shows only when the page was loaded in that state (the backend returns it after a failed send was recorded). The fixture loads in that state. The driver for the board (item 1) presses Send to get the field messages.
9. **Assembling board.**
   - "Tola · PMO agent · step 3 of 4" and "Started 12 Nov 09:05" have no field of their own. Recommend: a `checklist` section (`agent: "tola"`, title "Assembling the weekly report") whose `note` is "PMO agent · step 3 of 4" and a `facts`-free line "Started 12 Nov 09:05" as a second `note` sentence (one string, backend-composed). The frame's `as_of` draws "As of …", not "Started", so `as_of` is not used.
   - "WORKING" is a tag on the board; the frame's word for a `now` item is "In progress" (`labels.ts` `STATUS_WORDS`). Recommend: keep the frame's word, exception category `frame vocabulary`. The three progress lines (counts "3 MEETINGS · 9 ACTIONS · 1 MILESTONE · 2 ISSUES", "STATUS · RISKS · TIMELINE · NEXT STEPS") are item `detail`s from the data. "TEST TEMPLATE" is an item `tag` from the data.
   - The disabled "Send for PMO Lead review" is a workspace-scope step with `disabled_reason`; the frame always shows the reason as text, which the board does not draw. Recommend: keep the reason (it is the frame's accessibility rule); extra text is an exception.
   - "Ask Tola" has no field or endpoint in the contract. Recommend: **not built**, listed as a contract proposal (a link or step kind that opens the assistant, `/assistant` exists). An exception `no field`. Do not hard-code a button.
10. **Review board.**
    - "Open the report as the client will see it" has no destination (no document route exists in `frontend/src/app`; `workspace.version.document_id` is drawn as text only). Recommend: **not built**, exception `no field`, contract proposal in build.md.
    - The Decide panel title "Decide · PMO LEAD" has no field (already an F-17 exception). "Note (needed to return or refuse)" is drawn when "Return with a note" is pressed (F-17 exception).
    - Approve and Return: W-2001's steps carry no `task_id`, so they go through E-WORK-STEP (the F-17 behaviour that shipped and is tested). A step that does carry `task_id` is a link to the F-16 decision page (F-17 Conflicts 4). Recommend: the review fixture W-2204 has no `task_id` on Approve and Return, matching the board (Approve and Return in the page); a second fixture W-2208 carries `task_id` to prove the link. Which one the real backend returns is open and the backend's choice.
    - The board's "Refuse" is absent; do not add one beyond what the fixture returns.
11. **Frame items** (top bar, signed-in name and role, phone back link, Start work, "Overview"/"Setup" nav on the PMO Lead's board) are exceptions, as F-14, F-16 and F-17.

### Behaviour and wording

12. **Nothing is generated.** The board says "the words to the client are yours". The page offers no "write for me", draft or suggest control. If a fixture carries a suggestion for this line, it is not drawn on the four parts.
13. **Tokens.** Colours on the boards that the design system lacks are exceptions, not hard-coded values (F-17 Conflicts 5).

## D-LINE-WORKSPACE limits (binding on the PR description and build.md)
- D-LINE-WORKSPACE is `proposed` and has no recorded approval. F-21 consumes it only under the recorded exception (`architecture/sources/decisions-2026-11-15.md` items (g), (i)): **contract mock only**.
- **The backend developer may change or refuse any field** of `workspace`, E-WORK-STEP or the weekly cite options. Anything the frame cannot render from the schema is a contract proposal in build.md. The frame never extends the contract locally.
- **Nothing is released.** No real send, no real client template, no real recipient. The PR and build.md must not claim a real backend, "no duplicate send" as verified, or that the weekly line works. The client template is a test template (product decisions, Nov 2026); the data says "TEST TEMPLATE", the frame does not.

## Summary
- A PM opens a weekly report work item (`/work/W-2201`). They write Status, Risks, Timeline and Next steps, cite records from the week's records, and press "Send to Tola to assemble" or "Save draft". The words are the PM's; nothing is drafted for them.
- A 422 puts each message under its part and the not-yet-sendable messages at the top; nothing is blocked client-side except what the descriptor states (INV: the backend owns "TBD" and "cite at least one").
- While Tola assembles, the page shows the agent's progress from the returned `checklist` and a disabled "Send for PMO Lead review" with its reason.
- The PMO Lead sees the assembled four parts with their records and the Decide panel; Approve and send and Return with a note run on the F-17 step flow, with the uncertain-send lock kept (reconcile only, no resend).
- Everything is on the contract mock. `returned` and `received` are F-21b and are not built here.

## Context
- Renderer to reuse: `frontend/src/features/workspace/` (`Workspace.tsx`, `Sections.tsx`, `StepForm.tsx`, `Steps.tsx`, `useWorkspaceStep.ts`, `labels.ts`, `workspace.css`), mounted from `frontend/src/features/work-item/WorkItemOverview.tsx`. The page is `frontend/src/app/work/[id]/page.tsx`. There is no weekly-specific code today; `W-2001` is a review-looking fixture of this line (`frontend/mock/fixtures/work/W-2001.json`, `W-2001.steps.json`).
- Step form: `StepForm.tsx` uses `IntakeField` from `frontend/src/features/start-work/` (`IntakeField.tsx`, `RecordPicker.tsx`, `intake.ts`); `records` options come from E-LINE-OPTIONS via `fetchOptions` (`useStartWork.ts:62`).
- Uncertain-send lock: `useWorkspaceStep.ts` (`awaitingReconcile`, `allLocked`) and the F-17 round-5/6 fixes (`delivery/features/F-17/round-5/build.md`: every step is locked while `item.reconcile` exists; the Decide bar leaves room for F-09's reconcile bar). `ReconcilePanel` and `workAction` in `frontend/src/features/response/`.
- Decision page (for a `task_id` step): `frontend/src/features/decide/`.
- Mock: `frontend/mock/workspace.mjs` (E-WORK-STEP handler, idempotency map, `GET /__mock/workspace-log`), `frontend/mock/server.mjs`, and `frontend/mock/start-work.mjs` (E-LINE-OPTIONS). Fixture ids used by earlier features: W-2001 to W-2010 (F-17), W-2101 to W-2109 (F-18). **F-21 uses W-2201 to W-2208.**
- Tests to model on: `frontend/tests/workspace.test.tsx`, `workspace-step.test.tsx`, `workspace-mock.test.ts`, `frontend/e2e/workspace.spec.ts`.
- Fidelity: F-17's region driver (`delivery/features/F-17/regions.json`) stays as it is; F-21 scores whole boards, as F-18 did (`delivery/features/F-18/spec.md`, "Acceptance criteria").

## Contract

### E-WORK-ITEM `GET /api/v1/work/{work_id}` (read, `workspace`; unchanged, proposal)
The page reads only `workspace` and the existing item fields. Every rule of F-17's Contract 1 to 11 applies (hide when absent, words for enums, INV-UNKNOWN, INV-RESTRICTED, sample label, WAT dates, no `/me`). Nothing new is added to the shape. The weekly line sets:

| Field | Weekly use (backend composes; the frame shows it) |
|---|---|
| `line_key` | `weekly_report` (Conflicts 3) |
| `screen`, `view` | `SCR-25`, one of `default`, `invalid`, `assembling`, `review` (informational; the frame does not branch on them) |
| `status` | default: none or "Draft"; invalid: "Needs fixing" (tone `stopped`); assembling: "Assembling" (tone `agent`); review: "Your review" (tone `person`) |
| `subtitle`, `byline`, `version` | e.g. "Lagoon Health · week ending 11 Nov"; "Written by Tunde Bello, assembled by Tola"; "Report v1" |
| `agent_note` | default: the board's two sentences ("Since last week: 1 milestone completed, 3 actions now overdue, 1 new change request. I've listed the records; the words to the client are yours."); review: as in W-2001 |
| `sections` | default/invalid: `text` "Your update" (saved parts with `cites`); five `facts` sections for the week's records (MEETINGS, MILESTONES COMPLETED, ACTIONS with `note` "3 overdue · 1 without an owner", ISSUES OPEN, CHANGES). assembling: `checklist` (Conflicts 9). review: `text` "Report v1 · written by Tunde Bello, assembled by Tola" |
| `steps` | default/invalid: `send_to_tola`, `save_draft`. assembling: `send_for_review` with `disabled_reason`. review: `approve_send` (primary, `sends: true`, `consequence` "Approving sends this exact version to Lagoon Health."), `return` (secondary, field `note`, `required: true`) |
| `revision` | a number; without it no step control is drawn (F-17) |

Counts ("3 overdue · 1 without an owner", "3 MEETINGS · 9 ACTIONS …") are returned text. The frame computes no count.

### The four-part form (steps `send_to_tola` and `save_draft`)
Descriptors in the fixture (same eight for both steps):

| name | type | required | notes |
|---|---|---|---|
| `status` | `long_text` | false | label "Status"; `value` = saved words |
| `status_cites` | `records` | false | `multiple: true`, `options_source: "line_options"`; `value` = saved cites |
| `risks`, `risks_cites` | as above | false | label "Risks" |
| `timeline`, `timeline_cites` | as above | false | label "Timeline" |
| `next_steps`, `next_steps_cites` | as above | false | label "Next steps" |

`required` is **false** on all eight on purpose: the rule "words and at least one cited record, TBD refused" is the backend's (`design/screens.md:116`) and the frame must not substitute its own message for the 422. If the backend marks them `required`, the frame shows the F-17 required message and sends nothing, which is correct; the fixtures do not do that.

Request, on press of either step: the F-17 E-WORK-STEP request, `{expected_revision: workspace.revision, step, inputs: {status, status_cites, …}, idempotency_key}` plus CSRF; `inputs` shaped per kind by the existing helper (`records`: a list of option values). No `note`, no `evidence_ids` (the descriptor has none). The frame does not trim, check for "TBD", count words or require a cite.

### E-WORK-STEP `POST /api/v1/work/{work_id}/steps` (unchanged from F-17; one weekly handler script added)
| | |
|---|---|
| 200 | `{work_id, state, revision, outcome: done | queued | effect_uncertain, message?}`. `done` on `save_draft`: reload, polite line "Done: Save draft." (the page stays on the default state with the saved values). `done` on `send_to_tola`: reload, the item now shows the assembling state |
| 409 | F-17 stale flow: inputs kept, reload once, "This changed while you were working. Showing version N.", new key for the next deliberate press |
| 422 | `{code, message, fields?[{name,message}]}`. `fields[].name` is one of the eight names above; a message lands under its input (`aria-invalid`, `aria-describedby`), focus to the first; `message` shows at the top of the form. Inputs kept, new key |
| 401, 403, 404, 5xx | F-17 Contract rows, unchanged |
| Permission, tenant | Backend decides per record and step. The mock returns what the fixture script says. A wrong-tenant or wrong-user read is a 403 or 404 and shows `NoAccessState` with no client, title or id |
| Idempotency, versioning | As F-17: one key per attempt, no client retry, `expected_revision` = `workspace.revision`. The backend promise is unbuilt; the mock map proves one send on the mock only |

### Review decision (steps `approve_send`, `return`)
- Run on F-17's flow. `approve_send` has no fields: it submits on press. `return` opens a form with the `note` field (required, 2000 cap); the pressed label is the step label.
- **Uncertain send (INV-RESEND).** If E-WORK-STEP answers `effect_uncertain` for `approve_send`, every step on the page is off, nothing resends, no new key is made, the reloaded item shows `ReconcilePanel` when it carries `reconcile`, and the only action is reconcile on E-WORK-ACTION (one POST to `/actions`, none to `/steps`). A reload while `item.reconcile` exists keeps all steps locked (F-17 QA-5-5).
- A `task_id` step (W-2208) is a link to `/work/W-2208/decide?task=<task_id>`; the workspace sends nothing for it.
- After Approve or Return the page shows only the generic F-17 outcomes (done reload, queued, uncertain). The reloaded item renders whatever the mock returns. F-21 draws no returned or received page and tunes no fixture to those boards.

### Screen states
- **Loading / error / signed out / no access:** as the work item page and F-17 (`LoadingState`, `WorkErrorCard`, signed-out callout with `next`, `NoAccessState`).
- **default:** header (status absent or Draft), "Your update" text section, records panel, step buttons, open form on press with saved values. **Empty:** a week with no records shows each `facts` section as "Nothing here yet." (F-17 rule); the form still opens. **Success:** the "Done" line and the reload.
- **invalid:** the state of Conflicts 7 and 8. **assembling:** header "Assembling", the agent checklist, the disabled step with its reason. **review:** the four read-only parts with records, the Decide panel. **Unknown values:** show "Unknown", never 0 or blank (a count the backend cannot give is not drawn).
- No state animates under `prefers-reduced-motion: reduce`: the `agent-now` pulse (`.psl-now`, `frontend/src/styles/psl-bundle.css:384`) stops; the state is always also written in words.

### Fixtures (`frontend/mock/fixtures/work/`, new; existing files byte-for-byte unchanged)
All validate against the generated 200 schema for E-WORK-ITEM and copy board wording as the backend would return it. Sidecars use the F-17 `W-22xx.steps.json` and `W-22xx.next.json` forms.

| Id | Shows |
|---|---|
| W-2201 | default: saved parts 1 and 2 only, five records `facts` sections, agent note, steps `send_to_tola` and `save_draft`; `.next.json` = W-2203 (a successful send); `.steps.json`: `save_draft` 200 `done` |
| W-2202 | invalid: status "Needs fixing", Risks "TBD" and Next steps without cites, section `note` "The report can't start before the week has ended. This week ended 11 Nov."; `.steps.json`: `send_to_tola` 422 with `fields` for `risks` and `next_steps_cites` and the top `message` of Conflicts 7 |
| W-2203 | assembling: `checklist` (done, done, now; third item `tag` "TEST TEMPLATE"), disabled `send_for_review` with `disabled_reason` |
| W-2204 | review: report text section with `cites`, `approve_send` and `return`; `.steps.json`: `approve_send` 200 `done`; `.next.json` = a plain reload of the same item with revision + 1 |
| W-2205 | review where `approve_send` answers `effect_uncertain`; `.next.json` carries `reconcile` and `allowed_actions: ["reconcile"]` (modelled on W-2008) |
| W-2206 | default with scripted 409 (with `.next.json`, revision 4 to 5) and a scripted 500 on `save_draft` |
| W-2207 | default where every part is saved and cited, `restricted: true` records section (shows its label only) and one `facts` value `unknown` |
| W-2208 | review with a `task_id` step (link to the F-16 page; `W-2208` also valid as a decision fixture, copied as W-2009 was) |

Mock changes (additive; existing responses unchanged): `mock/start-work.mjs` serves E-LINE-OPTIONS for the cite fields of a `weekly_report` step (a new `options/records.json` with this week's records, references matching the records panel and the cited chips); the E-WORK-STEP handler (`mock/workspace.mjs`) needs no change beyond sidecars.

## Lanes
- **Frontend lane (builder)** owns:
  - Fixtures `frontend/mock/fixtures/work/W-2201` to `W-2208` and sidecars; `frontend/mock/fixtures/start-work/options/records.json`; a minimal additive hook in `frontend/mock/start-work.mjs` (options for step fields of a workspace fixture whose `line_key` is registered).
  - Small, general changes in `frontend/src/features/workspace/**` only where a board needs a region the frame lacks and the change is not weekly-specific (for example a `text`-section note position, or a section `note` line); each is listed in build.md. No weekly page, route or component. No new renderer.
  - Tests: `frontend/tests/weekly.test.tsx`, `weekly-mock.test.ts`, `mock-contract.test.ts` (new fixtures only), `frontend/e2e/weekly.spec.ts`.
  - Factory files: `delivery/features/F-21/fidelity-exceptions.json`, `round-<N>/fidelity/**` (`drive-states.mjs`, `scores.txt`, per-board folders), `build.md`.
- **Shared, read only (import, do not edit):** `frontend/src/features/start-work/**` (type-only widening only, listed in build.md), `features/decide/**`, `features/response/**`, `features/work-item/**` (the F-17 mount stays as is), `src/shell/**`, `features/my-work/**`, `src/api/**` (including `schema.d.ts`), `src/styles/**`, `frontend/package.json`, the lock file, `playwright.config.ts`, `vitest.config.ts`, `architecture/**`, `design/**`, `apps/**`, and protected `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json`. Existing fixtures for W-1xxx, W-2001 to W-2010 and W-2101 to W-2109 are untouched.
- **Backend lane:** none. Backend items to record in build.md, not blocking: E-WORK-STEP and the `workspace` block are unimplemented; the idempotency promise is unbuilt (`delivery/COORDINATOR-HANDOFF.md`); the weekly cite options (this week's records through E-LINE-OPTIONS); the contract proposals of Conflicts 1, 2, 6, 9 and 10 (inline form flag, per-part state tag, "started"/"step n of m" fields, Ask Tola, open-the-report link).
- **Integration owner:** the coordinator. `features/workspace/**` is shared with F-17 and `features/response/**` with F-09 and F-18: whichever merges second merges the current base and reruns `delivery/checks.sh` and the 390 e2e.
- **Ports:** app 4741, mock 4742. `cd frontend && E2E_PORT=4741 MOCK_PORT=4742 npx playwright test e2e/weekly.spec.ts`, `timezoneId: 'Africa/Lagos'`. Score on a production build (`next build`, `next start -p 4741`, mock on 4742). Check `df` first and delete `frontend/test-results` after.
- **Review routing:** technical (sonnet); security (opus: a write that can send a client report); UI (opus, the fidelity gate on 8 boards); UX (sonnet); QA (opus). Product acceptance is not required. Medium risk. One fidelity run per round (D-64).
- **Size.** Estimated 1,200 to 1,800 lines (fixtures, tests, small frame changes). One PR. If the build exceeds it, drop the four phone boards to a follow-on first; never pull in `returned` or `received`.

## Acceptance criteria
Fidelity command for one board (swap `--board`, `--page`, `--width`, `--out`; cookie `psl_mock_persona=pm` on every board):
```
node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs \
  --playwright <worktree>/frontend/node_modules/playwright/index.mjs \
  --board /Users/Hunchoo/psl-factory/design/canvas/project/SCR-25-desktop-review.dc.html \
  --page "http://localhost:4741/work/W-2204" --width 1440 \
  --cookies psl_mock_persona=pm \
  --exceptions /Users/Hunchoo/psl-factory/delivery/features/F-21/fidelity-exceptions.json \
  --wait-ms 500 --out /Users/Hunchoo/psl-factory/delivery/features/F-21/round-<N>/fidelity/SCR-25-desktop-review-1440
```
| Board suffix (desktop and mobile) | Page | How reached |
|---|---|---|
| default | `/work/W-2201` | driver: open "Send to Tola to assemble", type the board's four parts, choose the board's cited records, freeze |
| `-invalid` | `/work/W-2202` | driver: open Send, press it, take the 422, freeze |
| `-assembling` | `/work/W-2203` | live URL |
| `-review` | `/work/W-2204` | live URL |

### Fidelity (8 boards)
1. **Desktop boards at 1440.** The four `SCR-25-desktop*` boards each pass: `report.json` `pass: true`, `scores.coverageWithExceptions` = 100 (every element present or covered by an approved exception), `scores.visual` >= 90. — verify: the command per board, exit 0; `round-<N>/fidelity/scores.txt` lists board, width, coverage, visual, pass.
2. **Phone boards at 390.** The four `SCR-25-mobile*` boards pass at `--width 390` on the same pages with the same thresholds. — verify: same, rows in `scores.txt`.
3. **Driven states are the real UI.** `round-<N>/fidelity/drive-states.mjs` resets the mock (`POST /__mock/reset`), uses the real controls, the real mock and the real 422 (no hand-edited DOM except freezing: copy input values into attributes, remove scripts, add `<base>`). — verify: the script and `frozen/*.html`.
4. **Exceptions are limited and explained.** Each entry of `fidelity-exceptions.json` has `role`, `name`, `category`, `reason`, `approved_by` (`"builder proposal, pending design engineer"` until confirmed) and maps to a Conflicts item; none covers a value the data can supply (a count, a label, a status, a cite). — verify: file content; build.md maps each to a Conflicts number.
5. **One fidelity run per round** (D-64); the UI review passes only on these 8 scores. — verify: build.md.

### Page behaviour
6. **Default state from data.** `/work/W-2201` shows the title, subtitle, agent-note lines, the saved parts with cites, the five records groups with their returned counts text, and the two step buttons, all from the fixture; a field the fixture omits draws nothing. — verify: `tests/weekly.test.tsx`; page at 1440 and 390.
7. **The form carries the PM's words.** Pressing "Send to Tola to assemble" opens a form with four labelled text areas and four cite pickers showing the saved values; the cite picker offers only the records E-LINE-OPTIONS returns for `weekly_report`; no control writes, suggests or generates text. — verify: component test with a recording `fetch`; a search of `features/workspace/**` and fixtures shows no generate/suggest control for these parts.
8. **Write request.** Submitting sends exactly one POST `/api/v1/work/W-2201/steps` with CSRF, `expected_revision` = `workspace.revision`, `step: "send_to_tola"`, `inputs` with the eight names (cites as lists of option values) and a UUID `idempotency_key`; no `note`, no `evidence_ids`; the body validates against the generated request schema. "Save draft" sends the same shape with `step: "save_draft"`. — verify: `tests/weekly.test.tsx` and `weekly-mock.test.ts`.
9. **Nothing is judged client-side.** Typing "TBD" or leaving a cite empty sends the request as is; the page shows only the server's answer. — verify: component test (request recorded; no local message).
10. **422 per part.** On W-2202 pressing Send shows the server message under `risks` and under `next_steps_cites` (`aria-invalid`, `aria-describedby`), the top `message` above the form, focus on the first failing input, inputs kept, and a new key for the next press. The "Needs fixing" tag and the week-end sentence come from the loaded fixture. — verify: component test and e2e; the strings are in the fixture, not in `src/`.
11. **Send moves to assembling.** A `done` on W-2201 `send_to_tola` reloads once and the page shows the assembling state (W-2203): the agent name, step text, three progress lines with their statuses as words, "TEST TEMPLATE", and the disabled "Send for PMO Lead review" with its reason; activating it sends nothing. — verify: component test and e2e with the recorded requests.
12. **Assembling is quiet and accessible.** The `now` item pulses only without `prefers-reduced-motion: reduce`; its state reads as a word; no step on W-2203 is actionable. — verify: e2e with `reducedMotion: 'reduce'` (no running animation on the `now` mark) and a component test for `aria-disabled`.
13. **Review state.** `/work/W-2204` shows "Report v1 · written by Tunde Bello, assembled by Tola", the four parts with their record references (as links only for app paths), the consequence sentence "Approving sends this exact version to Lagoon Health." and the buttons "Approve and send" and "Return with a note". — verify: component test; page at both widths.
14. **Approve.** "Approve and send" on W-2204 sends one POST with its own key; a double click sends one; `done` reloads once and shows "Done: Approve and send."; no automatic retry (fake timers advanced 60 s, count stays 1). — verify: component tests; e2e reads `GET /__mock/workspace-log` (send count 1 for that key; mock evidence only).
15. **Return needs a note.** "Return with a note" opens the form with the `note` field; sending it blank is refused client-side because the descriptor says `required`; a note over 2000 characters is refused before any request; the valid note goes as `note`/`inputs.note` per F-17 and `done` reloads. — verify: component test.
16. **Uncertain send keeps the lock (INV-RESEND).** On W-2205, `approve_send` answering `effect_uncertain` shows the warning callout with the returned `message`; every step control is off; after the reload `ReconcilePanel` shows and its answer is one POST to `/actions` and none to `/steps`; a forced click on "Approve and send" sends no POST, before and after a page reload; no new key exists. When the reloaded item has no `reconcile`, the page says "We are checking what happened. Nothing was sent again." and offers a reload only. — verify: component tests and e2e at 1440, 390 and 320 (the Decide bar leaves "Record and continue" tappable, as F-17).
17. **Stale, server and network errors.** W-2206: 409 keeps inputs, reloads once, shows "This changed while you were working. Showing version 5.", re-bases `expected_revision`; 500 on `save_draft` (a non-`sends` step) offers a manual "Try again" with the same key; a 500 on `approve_send` (a `sends` step) offers no resubmit. — verify: component tests.
18. **Access.** 401 shows the signed-out callout with `next` = this page; 403 on a step reloads and shows "You can't take that step."; 404 and a wrong-tenant read show `NoAccessState` with no title, client or id. A persona with any role sees the same controls for the same fixture; nothing is derived from `/me`. — verify: component tests with a recording `fetch`; `grep -n "/me\b" frontend/src/features/workspace` unchanged by this feature.
19. **Decision step.** The `task_id` step on W-2208 is a link to `/work/W-2208/decide?task=<task_id>`; the workspace sends nothing to `/steps`, `/claim` or `/decision`; following it opens the F-16 page. — verify: component test and e2e.
20. **Unknown, restricted, empty.** W-2207: a restricted records section shows its label only and none of the hidden strings appear in `document.body.textContent`; an unknown value reads "Unknown", never 0, blank or "-"; an empty records group reads "Nothing here yet.". — verify: component test.
21. **Returned and received are not built.** No file, route or component for either appears; a fixture in either state, if opened, renders only through the generic renderer. — verify: `git diff --stat`; no `returned`/`received` string in new `src/` code.

### Quality
22. **Accessibility and layout.** For W-2201 to W-2208 at 1440 and 390: no axe violations (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`), no sideways scroll, visible focus rings, 44px targets, focus to the form heading on open and back to the step control on close or Escape, errors announced (`role="alert"` or an associated live region), live regions for done, waiting and uncertain, reduced motion respected. — verify: `e2e/weekly.spec.ts`.
23. **Tokens only.** `grep -nE "#[0-9a-fA-F]{3,8}\b|rgba?\(|hsl\(" frontend/src/features/workspace/*.css` returns nothing from this feature's diff. — verify: the command on the diff.
24. **Contract not extended.** `git diff --stat` shows no change in `frontend/src/api/**`, `apps/**`, `architecture/**` or `design/**`; every wanted field the schema lacks is a contract proposal in build.md (Conflicts 1, 2, 6, 9, 10 and the cite options). Fixtures validate against the generated schema with no stripping. — verify: `tests/mock-contract.test.ts`; `git diff --stat`; build.md.
25. **Mock matches the contract.** `weekly-mock.test.ts` runs W-2201 to W-2208 and the scripted step answers through the E-WORK-STEP handler: a bad body is 422, a wrong `expected_revision` is 409, an unknown step key is 404, a repeated key returns the stored reply with no second send. — verify: the test.
26. **No real send, no overclaim.** Every request in the e2e run goes to the mock (4742). The PR description and build.md state the D-LINE-WORKSPACE limits, call the template a test template, and do not claim idempotency, a real backend or a working weekly line. — verify: build.md; recorded requests.
27. **Existing behaviour not weakened.** `tests/workspace*.test.*`, `work-item*.test.tsx`, `decide*.test.tsx`, `response*.test.tsx`, `start-work*.test.*`, `shell.test.tsx`, `e2e/workspace.spec.ts`, `e2e/work-item*.spec.ts`, `e2e/decide*.spec.ts`, `e2e/response.spec.ts`, `e2e/rfp.spec.ts` and `e2e/start-work.spec.ts` pass; no assertion removed or loosened; `git diff` shows no edit to any existing fixture. F-17's region check (`regions.json`) still passes at its recorded scores if the frame was touched. — verify: `delivery/checks.sh`; `git diff` on those files.
28. **New tests run.** `weekly.test.tsx`, `weekly-mock.test.ts` and `e2e/weekly.spec.ts` exist and run in `delivery/checks.sh`, covering at least criteria 6 to 21. — verify: file presence and the run output in `round-<N>/build.md`.
29. **build.md evidence.** build.md lists: the commands run and their results, the 8 scores, every exception with its Conflicts number, every frame change with its reason, every contract proposal, and the D-LINE-WORKSPACE limits. — verify: file content.

## Out of scope
- The `returned` and `received` boards (SCR-25 desktop and mobile), the return-and-edit loop, client receipts and delivery confirmations: F-21b.
- Any other line (FE-LINE-MINUTES, issue, change, delivery, finance) and any weekly-specific page, route, renderer or copy in `src/`.
- Writing, suggesting or generating the client text; computing counts; deciding "TBD", "cite at least one" or the week-end rule on the client.
- "Ask Tola", "Open the report as the client will see it", per-part "✓ cited / to write" chips and tap-to-expand rows, and a `steps[].inline` flag (contract proposals only).
- Backend, OpenAPI, `schema.d.ts` regeneration, `architecture/**`, `design/**`. A real E-LINE-OPTIONS for this week's records.
- Real sends, real client templates, real recipients, any claim that duplicate sends are prevented.
- `src/shell/**`, `my-work/**`, the existing work item boards, `work-item.css`, new npm dependencies.
- Whole-board scores for other lines; changes to F-17's region driver.

## Assumptions
- Form on press (Conflicts 1, Option A) is the build baseline. Reason: the contract and frame have no "open at load" signal and the readiness scope forbids a local extension; the design engineer may choose Option B.
- `records` fields carry the cites (Conflicts 2). Reason: it is the existing field kind for "pick records from the line's options".
- `line_key` is `weekly_report`. Reason: Start work registers that key; E-LINE-OPTIONS answers only for registered lines.
- All eight form fields are `required: false`. Reason: the four-part rule is the backend's; the frame must show its 422 text, not its own.
- The week-end sentence rides on the loaded fixture's section `note`, the "Two parts can't be sent yet" sentence on the 422 `message`. Reason: those are the two backend-returned places the frame already draws; which real source the backend uses is its call.
- Approve and Return run through E-WORK-STEP in W-2204 and through the decide page in W-2208. Reason: both are shipped F-17 behaviours; the real choice is the backend's.
- The mock serves one fixture to every persona; the PMO Lead view is the review fixture opened with persona `pm` for fidelity. Reason: the mock has no PMO Lead persona and the frame derives nothing from role.
- Fixture ids W-2201 to W-2208 and ports 4741/4742. Reason: W-2001 to W-2010 (F-17) and W-2101 to W-2109 (F-18) are taken; no other spec names 47xx.
- Frontend-owned neutral status sentences stay as F-17 ("Done:", "Waiting:", "Nothing here yet.", the uncertain and stale sentences). Reason: sources are silent; they are not business rules. The approver may escalate any wording.
- One PR for all 8 boards (about 1,200 to 1,800 lines). Reason: it fits the D-64 cap; the fallback split is phone boards first.
