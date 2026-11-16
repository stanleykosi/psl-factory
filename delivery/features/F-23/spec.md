# The minutes line: the PM confirms Tola's suggested decisions and actions, and client minutes go to the PMO Lead for review (contract mock only)

> Tasks: FE-LINE-MINUTES, first part (R-WORKITEM, R-DECIDE; acceptance A-WORKSPACE frontend half, with A-WORKITEM, A-DECIDE and the F-17, F-21 and F-16 tests kept green). Architecture: package `architecture/packages/v7`. FE-LINE-MINUTES is at `architecture/packages/v7/delivery.md:2046` and has no unresolved gates. The `workspace` block is at `frontend/src/api/schema.d.ts:1693` and E-WORK-STEP at `:5217`. This feature changes no generated type. Design: approved canvas version 1794581312-b166, client-approved 13 Nov 2026 (`design/review.json:41`). `design.py check --project .` was run by the spec writer on 16 Nov: `EXCEPTION`, `passes: true` (D-89, "+ Start" frame change), design_sha256 `2859ab21…`. Screens: SCR-28, 8 artboards: `SCR-28-{desktop,mobile}`, `-suggesting`, `-drafted`, `-review` (files in `design/canvas/project/`). Decisions consumed: D-LINE-WORKSPACE (proposal, under the exception), D-64, D-83, D-91 to D-96. Open decisions named: D-RETURN, D-ALERT-PROVIDERS, D-LINE-WORKSPACE. Models: `delivery/features/F-21/spec.md`, `delivery/features/F-17/spec.md`.

## Outcome
A PM opens a minutes work item (`/work/W-2301`, line key `minutes`). The page shows the meeting, the notes file and Tola's suggested decisions and actions. Each suggestion shows the place in the notes it came from. The PM keeps, edits or removes each suggestion, adds an action, and presses "Confirm and create actions". That sends exactly the set the PM saw. Nothing suggested becomes a decision or an action before that press.

For client minutes, Tola drafts the minutes on a **test template**. The PM sends them for review, and the PMO Lead approves or returns them as a human decision (E-TASK-CLAIM and E-TASK-DECIDE). After an uncertain send, the only next action is reconcile, and nothing is sent again.

Everything is rendered by the F-17 workspace frame on the contract mock. There is no minutes page, route or component.

## Boards
| Board | State | Page | Main elements |
|---|---|---|---|
| `SCR-28-desktop`, `SCR-28-mobile` | default | `/work/W-2301` | crumbs PROJECTS / LAGOON HEALTH / MINUTES; h1 "Confirm the minutes"; subtitle "Formal minutes and action handoff · MIN-0141"; "Decisions · Tola suggested 2" (two decisions, "Keep this decision" ticked, "From Notes · 14:12" / "14:30", Edit); "Actions · Tola suggested 3" table (ACTION / OWNER / DUE / Remove; owner "Client · Lagoon Health", "Engineering (recorded by PM)", "Choose an owner"; due "13 Nov", "15 Nov", "Unknown"); "+ Add an action"; "Who gets the minutes" Internal / Client and its sentence; "Confirm and create actions", "Save for later"; Meeting card (Weekly sync · Lagoon Health, 10 Nov 2026 · 14:00–14:45 · 6 attendees, weekly-sync-notes-10nov.docx · Uploaded · 42 KB); Tola note (3 sentences). The phone draws DECISION/ACTION rows with "owner · due" and only the confirm button. |
| `-suggesting` | Tola reading the notes | `/work/W-2302` | status "READING THE NOTES"; project tab bar; callout "Nothing Tola suggests becomes a decision or an action until you confirm it."; agent panel "Reading the meeting notes", "Tola · PMO agent · step 3 of 4", WORKING; items Read the meeting notes (WEEKLY-SYNC-NOTES-10NOV.DOCX), Found 2 decisions (14:12 · 14:30), Finding actions and owners, Hand them to you to confirm; "Started 10 Nov 15:02"; "Ask Tola" |
| `-drafted` | drafted | `/work/W-2303` | status DRAFTED; "Minutes v1 · client version" DRAFTED with rows "2 decisions · confirmed by you" IN, "3 actions · 1 has no owner yet" IN, "Attendees and notes" ATTACHED; agent panel "Tola · PMO agent · done" DONE with "Used the decisions and actions you confirmed" 2 DECISIONS · 3 ACTIONS, "Filled the client minutes template" TEST TEMPLATE, "Listed attendees from the invite" 6 ATTENDEES; "Drafted 10 Nov 15:20"; "Ask Tola"; Next: "Client minutes go to the PMO Lead before they're sent." and "Send for review" |
| `-review` | PMO Lead review | `/work/W-2304` | signed in as Kemi Adebayo · PMO Lead; status YOUR REVIEW; "Minutes v1 · for Lagoon Health"; the same three summary rows; "Open the minutes"; "Decide · PMO Lead" panel: "Approving sends this exact version to the client. Actions are created whether or not the client reads it.", Note "(needed to return or refuse)", "Approve and send", "Return with a note". **The phone board draws no note field.** |

## Conflicts with the boards (for the design engineer, before the build)
Each item is a place where the boards, the v7 contract and the F-17 frame disagree. The "Recommend" line is what this spec builds if no answer comes. Items 1 to 5 change what the page looks like or how it behaves and need an answer. The rest are exceptions to confirm. Every exception goes in `delivery/features/F-23/fidelity-exceptions.json` with `approved_by: "builder proposal, pending design engineer"` until you sign it.

### Board vs contract
1. **One confirm set across two lists, decisions pre-ticked (G-SCR28-1).** The board draws ticked "Keep this decision" boxes on the decisions, no box on the actions, and one "Confirm and create actions" button. In the frame, an `applies_to: items` step draws an unticked box on each target item and one button per section. The contract has no default and no cross-section set.
   - **Recommend:** two small, general frame changes. (a) Honour the proposed `steps[].items_default: "checked"`: target items start ticked, and the frame falls back to unticked when the field is absent. (b) When an `items` step targets items in more than one section, draw **one** control in the workspace step row. That control sends `item_ids` = the ticked ids across those sections, in returned order.
   - The actions carry `confirm_minutes` in their `steps[]` too, so they get a ticked box. Their box is an extra element (exception). It is there because the set sent must be the set shown, and readiness requires `item_ids` to cover the remaining actions.
   - The box's accessible name stays the frame's "Select <text>". The board's "Keep this decision" has no field (exception).
   - **Option B for you:** no box on actions, with the backend rule "actions not removed are confirmed". That needs the backend developer to state it in D-LINE-WORKSPACE. It is not built here.
2. **Audience, edit and add open a form on press (G-SCR28-2, G-SCR28-5).** The board draws the owner dropdown inside the table, the audience as an inline Internal / Client control, and Edit as a link. The frame opens a step's form under its control when it is pressed (F-17, F-21 Conflicts 1, D-69).
   - **Recommend:** form on press. `confirm_minutes` has one field `audience` and opens a form with the audience, the consequence sentence and the submit button "Confirm and create actions".
   - `audience` is a `choice` field when the data says it may change (W-2301) and a `display` field when it may not (W-2307). The frontend never decides which.
   - Each action gets an "Edit" control (`edit_item`, an extra element on actions) whose form carries `text`, `owner` (a `record` field, placeholder "Choose an owner") and `due` (a `date` field, not required). Decisions get the same "Edit" with `text` only.
   - "Remove" is an `item` step with no fields.
   - "+ Add an action" is a workspace step `add_action` with `text`, `owner` and `due`.
   - Fidelity for the desktop default board is scored with the confirm form opened by the driver, so the audience is on screen. The in-table dropdowns and the always-open audience are exceptions.
3. **Approve and Return leave the page (readiness: E-TASK-CLAIM and E-TASK-DECIDE).** The review board draws the Note box and both buttons inside the work page. In the frame a step with `task_id` is a link to the F-16 decision page (`/work/{id}/decide?task=…`, F-17 Conflicts 4). The note, claim and decide happen there through `frontend/src/features/decide/DecidePanel.tsx`.
   - **Recommend:** links (Option A). W-2304's `approve_send` and `return` both carry `task_id: "T-2304"`. The in-page Note box is not drawn (exception "frame decision").
   - **Option B:** run Approve and Return in-page through E-WORK-STEP, as F-21's W-2204 does (D-85). Here `return` has a required `note` field that opens on press. Readiness bound F-23 to the decision path, so B needs your word and the backend developer's. It is not built here.
4. **OPEN DESIGN ITEM (pending design engineer): the phone review board draws no note field, but Return needs one.** E-TASK-DECIDE requires `note` to return (`architecture/packages/v7/endpoints.csv`, E-TASK-DECIDE request). The mock refuses a blank one (`frontend/mock/server.mjs` `NOTE_REQUIRED`).
   - **Proposal:** on a phone, "Return with a note" opens the F-16 decision page, which already draws "Note (needed to return or reject)" above Return and Reject. It refuses a blank note before any request (`DecidePanel.tsx:40`). The phone review page itself stays as the board draws it, with no note.
   - If you choose Option B in item 3, the note instead appears in the Return form under the button at both widths. The phone then shows a field the board lacks, which is a fidelity exception request, not a silent change.
   - Either way, no Return is sent without a note. The F-16 page's words "Approve" and "Return" differ from the board's "Approve and send" and "Return with a note" (X-VERDICTS, G-SCR51-2, backend proposal).
5. **Recipients are not drawn on the review board, but the PMO Lead must see them (G-SCR28-8).** The board says only "for Lagoon Health". Readiness requires the exact recipients from client contact records before an approval that sends.
   - **Recommend:** W-2304 carries a `recipients` section "Goes to" (names, channel "email", `receipt: not_yet`). It is an extra element (exception "safety").
   - **Alternative:** show the recipients on the F-16 decision page only (`decision.recipient`). Then the work page matches the board and the recipients appear where the decision is taken. Say which you want.
6. **Decisions sit in the side column.** Decisions are a `suggestions` section (gaps doc). The frame puts `suggestions` and workspace-scope steps in the side column (F-17, D-62). The board puts decisions and actions in the main column and the meeting card and Tola's note on the right. **Recommend:** keep the frame layout, exception category `frame layout`, as F-21 Conflicts 4. A section `placement` hint is a contract proposal and is not built.
7. **Links: "Ask Tola" and "Open the minutes" (G-SCR28-3, X-LINKS).** The contract has no link list.
   - **Recommend:** fixtures carry the proposed `workspace.links[]` `{key, label, target: {kind, document_id?, version?}}` under the D-LINE-WORKSPACE exception (see Contract, "Proposals"). The frame draws a link only when the data supplies it, and only for the kinds `assistant` (to `/assistant`) and `document` (reads E-DOCUMENT). Any other kind is not drawn.
   - The drafted board draws no "Open the minutes", although readiness listed it there. The drafted fixture follows the board.
   - "Open actions" belongs to F-23b.
8. **"Started 10 Nov 15:02", "step 3 of 4", "Drafted 10 Nov 15:20" have no field.** **Recommend:** as in F-21 Conflicts 9, they are the backend-composed `note` of the agent `checklist` section ("PMO agent · step 3 of 4 · Started 10 Nov 15:02"). Placement differences are exceptions. "WORKING" and "DONE" are frame words for the agent status (D-85 approved "WORKING" for F-21).
9. **Status tags inside panels.** "DRAFTED" on the "Minutes v1 · client version" panel and "DONE" on the agent panel have no section-level tag. **Recommend:** `workspace.status` carries DRAFTED. The panel tags are exceptions `no field`.
10. **Phone wording and rows.** The phone titles ("Minutes", "Minutes drafted", "Review minutes"), the phone back links ("← Lagoon Health", "← Project", "← My work"), the "No owner yet · due Unknown" line and the DECISION/ACTION row style differ from desktop. The frame has one title and one rendering for both widths. **Recommend:** desktop wording and rendering at both widths. The phone extras (Remove, Edit, Add, Save for later, the decision list in the side column stacked below) are exceptions; the back link is a frame item.
11. **Frame items.** The top bar, signed-in name and role, phone back link, "+ Start", the PMO Lead's "Overview"/"Setup" nav, the "Decide · PMO Lead" panel title and the project tab bar with counts (Journey, Milestones 4, Documents 6, Money, Registers 6, Actions 9) are exceptions, as in F-14, F-16, F-17 and F-21. The tab counts are a missing field under D-83.
12. **Tokens.** Board colours that the design system lacks are exceptions, not hard-coded values (F-17 Conflicts 5). "Effect uncertain" is amber (D-92b).

### Behaviour and wording
13. **Nothing suggested becomes an action until confirmed.** The page offers no "accept all", no auto-confirm and no pre-submit. Only the board's pre-ticked boxes (item 1) are pre-ticked. Text from the notes cannot set an owner, a due date, an audience or an approval (INV-AGENT, G-SCR28-9). The suggested owner and due only display what the backend returns.
14. **Test template.** "TEST TEMPLATE" is a tag from the data on the drafted checklist row, and `test_template: true` comes from E-DOCUMENT. The frame adds no template wording of its own and never calls the template real (product decisions, Nov 2026).

## D-LINE-WORKSPACE limits (binding on the PR description and build.md)
- D-LINE-WORKSPACE is `proposed` and has no recorded approval. F-23 consumes it only under the recorded exception (`architecture/sources/decisions-2026-11-15.md` items (g), (i)): **contract mock only**.
- **The backend developer may change or refuse any field** of `workspace`, E-WORK-STEP, the minutes steps, the owner options and the proposals below (`items_default`, `links[]`). Proposed fields live only in the mock fixtures and in one typed proposal reader (`features/workspace/proposals.ts`). They are stripped before the contract check, as the D-WORKITEM-VIEW `presentation` block is (`frontend/tests/mock-contract.test.ts:262`). `schema.d.ts` and `openapi.json` are not edited.
- **Nothing is released.** There is no real send, no real client template, no real recipient, no real meeting record and no notes parsing. The PR and build.md must not claim a real backend, that duplicate sends are prevented, or that the minutes line works. D-ALERT-PROVIDERS gates the real client send. D-RETURN gates what a return does to confirmed items.

## Summary
- `/work/W-2301` shows the meeting, Tola's suggested decisions (with notes cites) and actions (owner, due, "Unknown" where unknown). Edit, Remove and "+ Add an action" are step forms. "Confirm and create actions" sends exactly the ticked set with the workspace revision.
- While Tola reads the notes (W-2302), the page shows the agent's progress list in words, respects reduced motion, and offers nothing to confirm.
- Drafted (W-2303) shows the summary rows and tags from the data, including "TEST TEMPLATE", and "Send for review".
- Review (W-2304) shows the version, recipients and "Open the minutes". Approve and Return are links to the F-16 decision page, which claims and decides. After an uncertain send, every step and decision link on the work page is locked and only reconcile is offered.
- Internal and published (F-23b) are not built.

## Context
- Renderer: `frontend/src/features/workspace/` (`Workspace.tsx` `WorkspaceSteps` with `selected`, `itemsSteps`, `sectionControls.select/foot` at `:171-232`; `inSide` at `:66`; `Steps.tsx` `StepControl`, whose `task_id` branch at `:56` ignores `off` today; `Sections.tsx`; `StepForm.tsx`; `useWorkspaceStep.ts` with `awaitingReconcile` and `allLocked`; `labels.ts` `refPath`). It is mounted from `frontend/src/features/work-item/WorkItemOverview.tsx`. The route is `frontend/src/app/work/[id]/page.tsx`.
- Shared components (D-91, use from the start): `frontend/src/components/` (`Button`, `Checkbox`, `Link`, `Tag`, `Panel`, `Callout`, `Field`, `Select`, `DateField`, `TextArea`, `Loading`, `index.ts`). There are no local copies of buttons, tags, tables, checkboxes or panels.
- Decision page: `frontend/src/features/decide/` (`useDecision.ts` claims once per task revision and decides one version; `DecidePanel.tsx` has the note rule; `DecideView.tsx` has the uncertain notice). The mock's `taskResponse` (`frontend/mock/server.mjs:140`) applies `<work_id>.approve.json` / `.return.json` sidecars after a decide.
- Reconcile: `frontend/src/features/response/` (`ReconcilePanel`, `workAction`).
- Mock: `frontend/mock/workspace.mjs` (E-WORK-STEP handler, idempotency map, `GET /__mock/workspace-log`). In `frontend/mock/start-work.mjs`, `STEP_RECORD_FIELDS` and `OPTION_FILES` hold the F-21 step-field options hook, and the `minutes` line is registered. `frontend/mock/fixtures/start-work/lines.pm.json:81` holds the minutes intake (project, meeting, audience Internal/Client, proof `meeting_notes`). Generic operation fixtures are `frontend/mock/fixtures/<operationId>.json` (`server.mjs:283`).
- Taken fixture ids: W-1xxx, W-2001 to W-2010 (F-17) and W-2201 to W-2208 (F-21). **F-23 uses W-2301 to W-2308.**
- Records: model.json has no REC-ACTION, REC-DECISION or REC-MEETING (G-SCR28-6). That is a backend item and not a frontend change.

## Contract

### E-WORK-ITEM `GET /api/v1/work/{work_id}` (read, `workspace`; unchanged, proposal)
Every rule of F-17 Contract 1 to 11 applies: hide when absent, words for enums, INV-UNKNOWN, INV-RESTRICTED, sample label, WAT dates, no `/me`. The minutes line sets:

| Field | Minutes use (the backend composes it; the frame shows it) |
|---|---|
| `line_key` | `minutes` |
| `screen`, `view` | `SCR-28`, one of `default`, `suggesting`, `drafted`, `review` (informational; the frame does not branch on them) |
| `title`, `subtitle`, `context.crumbs` | "Confirm the minutes" / "Weekly sync · 10 Nov"; "Formal minutes and action handoff · MIN-0141"; PROJECTS / LAGOON HEALTH / MINUTES |
| `status` | default: absent; suggesting "Reading the notes" (tone `agent`); drafted "Drafted" (`neutral`); review "Your review" (`person`) |
| `version` | drafted and review: `{label: "Minutes v1 · client version", number: 1, document_id: "D-2304"}` |
| `agent_note` | default: the board's three sentences, ending "…it will show as \"No owner\" on the action list."; suggesting: "Nothing Tola suggests becomes a decision or an action until you confirm it." |
| `sections` (default) | `facts` "Meeting" (meeting, date and time, attendees, notes file and size); `suggestions` "Decisions · Tola suggested 2" (items `text`, `cites[{label: "From Notes · 14:12", evidence_id}]`, `steps: ["edit_item", "confirm_minutes"]`); `table` "Actions · Tola suggested 3" (columns `action` text, `owner` text, `due` date; cells as the board; owner cell "Choose an owner" when there is no owner; due `{unknown: true}` reads "Unknown"; items `steps: ["edit_item", "remove_item", "confirm_minutes"]`) |
| `sections` (suggesting) | `checklist` `agent: "tola"`, title "Reading the meeting notes", note "PMO agent · step 3 of 4 · Started 10 Nov 15:02", items done, done, now, next with `detail`; `item.agent.status: "working"` |
| `sections` (drafted) | `checklist` "Minutes v1 · client version" (three rows, `tag` IN, IN, ATTACHED); `checklist` `agent: "tola"` "Minutes v1", note "PMO agent · done · Drafted 10 Nov 15:20" (three rows, `tag` "2 DECISIONS · 3 ACTIONS", "TEST TEMPLATE", "6 ATTENDEES") |
| `sections` (review) | the summary `checklist`; `recipients` "Goes to" (Conflicts 5) |
| `steps` (default) | `confirm_minutes` (applies_to `items`, primary, proposal `items_default: "checked"`, field `audience`, `consequence` "Client minutes are reviewed by the PMO Lead before they're sent."); `save_for_later` (workspace, secondary, no fields); `add_action` (workspace, fields `text` required, `owner` record `options_source: line_options` placeholder "Choose an owner", `due` date not required); `edit_item`, `remove_item` (item) |
| `steps` (drafted) | `send_for_review` (workspace, primary, no fields, `consequence` "Client minutes go to the PMO Lead before they're sent.") |
| `steps` (review) | `approve_send` (primary, `sends: true`, `task_id: "T-2304"`, `consequence` "Approving sends this exact version to the client. Actions are created whether or not the client reads it."); `return` (secondary, `task_id: "T-2304"`) |
| `revision` | a number; without it no step control is drawn (F-17) |
| `tasks[]` (review) | T-2304, the PMO Lead review of version 1 (`you_can_act` per fixture), so the F-16 page works |

Counts ("Tola suggested 2", "1 has no owner yet", "6 ATTENDEES") are returned text. The frame computes no count. Whether actions are created at confirm or at approval is the backend's rule (G-SCR28-7). The frame shows the returned `consequence` and adds no wording.

### Proposals (fixtures only, read by `features/workspace/proposals.ts`, stripped before the contract check)
| Proposal | Shape | Frame behaviour |
|---|---|---|
| G-SCR28-1 `steps[].items_default` | `"checked"` or absent | Target items start ticked. Absent means unticked (today's behaviour). The PM can untick any item. The reload after a 409 re-applies the default to the new set, and the PM sees it before pressing again |
| X-LINKS (G-SCR28-3) `workspace.links[]` | `{key, label, target: {kind: "assistant" \| "document", document_id?, version?}}` | Drawn only when supplied. `assistant` is a link to `/assistant`. `document` is a button that sends one GET to E-DOCUMENT and shows a `Panel` with `title`, `version`, `status`, `template` and a `Tag` "Test template" when `test_template: true`. `body_url` becomes a link only when `isAppPath` accepts it, otherwise it shows as text. Other kinds are not drawn |

Not proposed for the frontend, only recorded in build.md: G-SCR28-4 `work_id` on E-LINE-OPTIONS (the frame sends only the contract's `parent`, `q`, `cursor`, `limit`); `hint` values on owner options ("client", "recorded by PM") are already in the contract and are drawn by `RecordPicker`; G-SCR28-6 records; G-SCR28-7 order of creation; D-RETURN behaviour; the meeting source.

### E-WORK-STEP `POST /api/v1/work/{work_id}/steps` (unchanged from F-17)
| | |
|---|---|
| Request | `{expected_revision: workspace.revision, step, item_ids?, inputs?, idempotency_key}` plus CSRF. `confirm_minutes`: `item_ids` = the ticked decision and action ids in returned order, as captured when the control was pressed, and `inputs.audience` = the chosen option value. `edit_item` and `remove_item`: `item_ids: [<that item>]`; `edit_item` adds `inputs` `{text, owner?, due?}`. `add_action`: `inputs` `{text, owner?, due?}`. A blank `owner` or `due` is **left out**: never today, never 0. `save_for_later` and `send_for_review` have no inputs. There is no `note` unless the descriptor has a `note` field |
| 200 | `{work_id, state, revision, outcome, message?}`. `done` reloads once and shows "Done: <label>.". `confirm_minutes` done moves to W-2303 (drafted) in the mock. `send_for_review` done moves to W-2304. `queued` follows F-17 |
| 409 | F-17 stale flow: inputs kept, reload once, "This changed while you were working. Showing version N.", ticks re-applied to the new set, and a new key for the next deliberate press |
| 422 | `fields[].name` (`text`, `owner`, `due`, `audience`) lands under its input; `message` shows at the top; new key |
| 401, 403, 404, 5xx | F-17 rows. A 5xx on a step without `sends` offers a manual "Try again" with the same key |
| Permission, tenant | The backend decides per record and per step. A wrong-tenant or wrong-user read is a 403 or 404 and shows `NoAccessState` with no client, title or id |
| Idempotency | One key per attempt and no client retry. The backend promise is unbuilt; the mock's map proves one send on the mock only |

### Review decision (E-TASK-CLAIM, E-TASK-DECIDE through the F-16 page)
- `approve_send` and `return` render as links to `/work/W-2304/decide?task=T-2304`. The workspace sends nothing to `/steps`, `/claim` or `/decision`.
- The F-16 page claims once, shows the note, refuses a blank note for Return before any request, and decides the exact version (`expected_revision` = the task revision).
- **Small general frame change:** a `task_id` link honours the page lock. While a write is in flight, while `item.reconcile` exists, or after a failed refresh, it renders as an unavailable control (`aria-disabled`, no `href`) with the existing confirm-first hint. Today `StepControl` draws it active regardless of `off`, which would let a PMO Lead approve again after an uncertain send.
- **Uncertain send (INV-RESEND).** W-2305's decide answers `work_state: "effect_uncertain"`, and its `.approve.json` carries `reconcile` and `allowed_actions: ["reconcile"]`. The decision page shows its uncertain notice and sends nothing again. Back on `/work/W-2305`, every step and link is locked and `ReconcilePanel` is the only action (one POST to `/actions`, none to `/steps` or `/decision`). There is no resend and no new key.
- After Approve or Return, the work page shows only the generic outcomes and renders whatever the mock returns. F-23 tunes no fixture to the internal or published boards.

### Screen states
- **Loading / error / signed out / no access:** as the work item page (`LoadingState`, `WorkErrorCard`, signed-out callout with `next`, `NoAccessState`).
- **default:** as the board. **Empty:** a section with `items: []` reads "Nothing here yet."; with no ticked items the confirm control is unavailable. **Success:** "Done: …" and the reload.
- **suggesting:** the agent list with status words; no actionable step; the `now` pulse stops under `prefers-reduced-motion: reduce`.
- **drafted** and **review:** as above. **Unknown:** "Unknown", never 0, blank or "-". An action without an owner shows the returned cell text, and the edit form's owner field shows its placeholder "Choose an owner".
- **E-DOCUMENT failure:** 403 or 404 show "You can't open this document." with no title. 5xx or network show "We couldn't open the minutes. Try again." with a manual retry of the read only. These are frontend-owned neutral sentences (Assumptions).
- **E-LINE-OPTIONS failure:** the owner picker shows `RecordPicker`'s existing error. The rest of the form stays usable, and a blank owner is left out.

### Fixtures (`frontend/mock/fixtures/work/`, new; existing files byte-for-byte unchanged)
After the proposals are stripped, all of them validate against the generated E-WORK-ITEM 200 schema. They copy board wording as the backend would return it.

| Id | Shows |
|---|---|
| W-2301 | default, client audience may change (`audience` `choice`, value `client`), decisions and actions as the board, `items_default: "checked"`, `links` none. `.next.json` = W-2303 after `confirm_minutes`. `.steps.json`: `save_for_later`, `remove_item`, `edit_item`, `add_action` 200 `done` |
| W-2302 | suggesting: agent working, `checklist`, `agent_note`, a `links[]` "Ask Tola" (`assistant`), no steps |
| W-2303 | drafted: two checklists with tags including "TEST TEMPLATE", "Ask Tola" link, `send_for_review`. `.next.json` = W-2304 |
| W-2304 | review: summary checklist, `recipients`, `links[]` "Open the minutes" (`document`, D-2304 v1), `task_id` steps, `tasks[]` T-2304. Decide sidecars `.approve.json` and `.return.json` |
| W-2305 | review whose approve answers `effect_uncertain`; `.approve.json` carries `reconcile` and `allowed_actions: ["reconcile"]` (modelled on W-2008) |
| W-2306 | default with a scripted 409 on `confirm_minutes` (`.next.json` revision 4 to 5 with a fourth suggested action), a 422 on `add_action` (`fields: [{name: "text"}]`) and a 500 on `save_for_later` |
| W-2307 | default where `audience` is `display` ("Client"), one action with `due.unknown` and no owner, a `restricted` meeting-notes item, and a decision with `tag` "OWNER NEEDED" absent (nothing drawn) |
| W-2308 | default with no `items_default` (boxes start unticked, the confirm control is unavailable until one is ticked) and an empty decisions section |

Mock changes (additive):
- `mock/start-work.mjs`: `STEP_RECORD_FIELDS.minutes = ['owner']` and a new `fixtures/start-work/options/owner.json` with people, "Engineering" (`hint` "recorded by PM") and "Lagoon Health" (`hint` "client").
- A new `mock/fixtures/E-DOCUMENT.json` for D-2304 v1 with `test_template: true`.
- `mock/workspace.mjs`: sidecars only.

## Lanes
- **Frontend lane (builder)** owns:
  - Fixtures W-2301 to W-2308 and their sidecars, `options/owner.json`, `E-DOCUMENT.json`, and the two-line `STEP_RECORD_FIELDS` and `OPTION_FILES` addition in `mock/start-work.mjs`.
  - Small, general changes in `frontend/src/features/workspace/**`, each listed in build.md with its reason. These are: `proposals.ts` (typed reader for `items_default` and `links[]`, marked PROPOSAL); the `items_default` initial ticks; the one cross-section `items` control; the `task_id` link honouring the lock; and the links row with the E-DOCUMENT panel. They are built on `frontend/src/components/**` and use tokens only. There is no minutes-specific code, route or copy in `src/`.
  - Tests: `frontend/tests/minutes.test.tsx`, `minutes-mock.test.ts`, `mock-contract.test.ts` (new fixtures, plus stripping the two proposal keys, checked on their own first), and `frontend/e2e/minutes.spec.ts`.
  - Factory files: `delivery/features/F-23/fidelity-exceptions.json`, `round-<N>/fidelity/**` (`drive-states.mjs`, `scores.txt`, per-board folders) and `build.md`.
- **Shared, read only:** `features/start-work/**` (type-only widening only), `features/decide/**`, `features/response/**`, `features/work-item/**`, `src/components/**` (import; a missing variant is a design-system change request, not a local copy), `src/shell/**`, `features/my-work/**`, `src/api/**` including `schema.d.ts`, `src/styles/**`, `package.json`, the lock file, `playwright.config.ts`, `vitest.config.ts`, `architecture/**`, `design/**` and `apps/**`. The protected `delivery/checks.sh`, `delivery/config.json` and `delivery/merge-policy.json` stay unchanged. Existing fixtures are untouched.
- **Backend lane:** none. Record in build.md: G-SCR28-1 to 9, D-RETURN, the meeting source, E-WORK-STEP, the `workspace` block, E-DOCUMENT and E-LINE-OPTIONS unimplemented, the idempotency promise and the server-side refusal of a resend while delivery is uncertain (SEC-5-C1), and the verdict words (X-VERDICTS).
- **Integration owner:** the coordinator. `features/workspace/**` is shared with F-17, F-21 and F-22 (FE-LINE-WEEKLY part 2, in flight). Whichever merges second merges the current base and reruns `delivery/checks.sh`, the F-21 e2e and the 390 e2e.
- **Ports:** app **4761**, mock **4762** (no other spec or config uses 476x; F-17 4701/4702, F-10 4712/4750, F-21 4741/4742). Run `cd frontend && E2E_PORT=4761 MOCK_PORT=4762 npx playwright test e2e/minutes.spec.ts` with `timezoneId: 'Africa/Lagos'`. Score on a production build (`next build`, `next start -p 4761`, mock on 4762). If a second process is needed, use 4763 to 4769. Run `df -h /System/Volumes/Data` first (stop under 3 GB) and delete `frontend/test-results` after.
- **Review routing (D-64):** technical (Sonnet); security (Opus: a decision that can send client minutes, and the lock change); UI (Opus first review, the fidelity gate on 8 boards); UX (Sonnet); QA (Opus). Product acceptance is not required. Medium risk; Sonnet builder.
- **Size:** about 1,400 to 2,000 lines. One PR. If it overruns, move the four phone boards to a follow-on first. Never pull in `internal` or `published`.

## Acceptance criteria
Fidelity command per board (swap `--board`, `--page`, `--width`, `--out`; cookie `psl_mock_persona=pm`):
```
node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs \
  --playwright <worktree>/frontend/node_modules/playwright/index.mjs \
  --board /Users/Hunchoo/psl-factory/design/canvas/project/SCR-28-desktop-review.dc.html \
  --page "http://localhost:4761/work/W-2304" --width 1440 \
  --cookies psl_mock_persona=pm \
  --exceptions /Users/Hunchoo/psl-factory/delivery/features/F-23/fidelity-exceptions.json \
  --wait-ms 500 --out /Users/Hunchoo/psl-factory/delivery/features/F-23/round-<N>/fidelity/SCR-28-desktop-review-1440
```
| Board suffix | Page | How reached |
|---|---|---|
| default (desktop) | `/work/W-2301` | driver: press "Confirm and create actions" to open the form (audience shown), then freeze |
| default (mobile) | `/work/W-2301` | live URL |
| `-suggesting` | `/work/W-2302` | live URL |
| `-drafted` | `/work/W-2303` | live URL |
| `-review` | `/work/W-2304` | live URL |

### Fidelity (8 boards, D-83)
1. **Desktop boards at 1440.** Each `SCR-28-desktop*` board has `scores.coverageWithExceptions` = 100 and `scores.visual` ≥ 90. A board that is at ≥ 70 but below 90 passes only with a D-83 visual waiver signed for that board in `fidelity-exceptions.json` and the UI reviewer's side-by-side reading finding no fixable gap. — verify: the command per board exits 0; `round-<N>/fidelity/scores.txt` lists board, width, coverage, visual, pass and waiver.
2. **Phone boards at 390.** The four `SCR-28-mobile*` boards meet the same rule at `--width 390`. — verify: the same command, with rows in `scores.txt`.
3. **Driven state is the real UI.** `drive-states.mjs` resets the mock (`POST /__mock/reset`) and uses real controls. The only DOM edits are freezing (copy values into attributes, remove scripts, add `<base>`). — verify: the script and `frozen/*.html`.
4. **Exceptions are limited.** Each entry has `role`, `name`, `category`, `reason` and `approved_by`, and maps to a Conflicts number. None covers a value the data can supply. — verify: file content and the build.md mapping.
5. **One fidelity run per round** (D-64). — verify: build.md.

### Page behaviour
6. **Default from data.** `/work/W-2301` shows the title, subtitle, crumbs, the meeting facts, the two decisions with "From Notes · 14:12" / "14:30", the three actions with owner and due ("Unknown" for the third), "+ Add an action", "Save for later", "Confirm and create actions" and the Tola note, all from the fixture. — verify: `tests/minutes.test.tsx`; the page at 1440 and 390.
7. **Pre-ticked from data only.** On W-2301 every decision and action box starts ticked because of `items_default`. On W-2308 none is ticked and the confirm control is `aria-disabled` and sends nothing. — verify: component tests.
8. **Exact confirm set.** Unticking one decision, then confirming with audience "Client", sends exactly one POST `/api/v1/work/W-2301/steps` with CSRF, `expected_revision` = `workspace.revision`, `step: "confirm_minutes"`, `item_ids` = the remaining ticked ids in returned order, `inputs: {audience: "client"}` and a UUID key. The body validates against the generated request schema. — verify: component test with a recording `fetch`; `minutes-mock.test.ts`.
9. **Nothing becomes an action before confirm.** Loading, ticking, unticking, opening Edit and cancelling sends no POST. No "accept all" or auto-confirm control exists. No request fires on load or on a timer (fake timers advanced 60 s). — verify: component test; `grep -rniE "accept all|auto.?confirm" frontend/src/features/workspace` returns nothing.
10. **Edit, remove, add.** "Edit" on an action opens a form with text, owner (options from E-LINE-OPTIONS `minutes/owner`, hints "client" and "recorded by PM" shown) and due. A blank due and a blank owner are left out of `inputs` (never today's date). "Remove" sends one POST with `item_ids: [<id>]`. On W-2306, "+ Add an action" with blank text sends the request and shows the 422 under `text`, with focus there, inputs kept and a new key. — verify: component tests.
11. **Audience from the descriptor.** W-2301 draws Internal / Client as a choice. W-2307 shows "Client" as display only and sends no `audience`. The returned consequence sentence shows in both. — verify: component test.
12. **Stale confirm.** On W-2306, confirming answers 409. The page reloads once, shows "This changed while you were working. Showing version 5.", shows the fourth suggested action ticked by default, and sends nothing until the PM presses again with a new key and `expected_revision: 5`. — verify: component test.
13. **Server failure on a non-sending step.** `save_for_later` 500 on W-2306 offers "Try again" with the same key. There is no automatic retry. — verify: component test.
14. **Suggesting is quiet and accessible.** W-2302 shows the agent list with status words, the callout and "Ask Tola" linking to `/assistant`. No step is actionable. The `now` mark does not animate under `reducedMotion: 'reduce'`. — verify: component test; e2e with `reducedMotion: 'reduce'`.
15. **Drafted and the test template.** W-2303 shows the rows with IN, IN and ATTACHED, the agent rows with "TEST TEMPLATE" and "6 ATTENDEES", and "Send for review". Pressing it sends one POST and reloads to W-2304. The strings "TEST TEMPLATE" and "Test template" appear in fixtures only, not in `src/` (except the `Tag` drawn from `test_template`). — verify: component test; `grep -rn "TEST TEMPLATE" frontend/src` returns nothing.
16. **Open the minutes.** On W-2304, "Open the minutes" sends exactly one GET `/api/v1/documents/D-2304/versions/1` and shows the title, version and a "Test template" tag. A 404 shows no title. `body_url` is a link only when it is an app path. — verify: component tests with a recording `fetch`.
17. **Review shows who and what.** W-2304 shows "Minutes v1 · for Lagoon Health", the version label, the recipients with "Not yet" (unless Conflicts 5 is answered otherwise), the consequence sentence, and "Approve and send" / "Return with a note" as links to `/work/W-2304/decide?task=T-2304`. The work page sends nothing to `/steps`, `/claim` or `/decision`. — verify: component test and e2e.
18. **Return needs a note.** On the decision page reached from "Return with a note", Return with a blank note is refused before any request, and an over-2000-character note is refused. A valid note sends one E-TASK-DECIDE with `verdict: "return"` and the note. This holds at 1440 and at 390 (the open design item, Conflicts 4). — verify: e2e at both widths with recorded requests.
19. **Uncertain send keeps the lock (INV-RESEND).** On W-2305, approving answers `effect_uncertain`, and the decision page shows its uncertain notice. Back on `/work/W-2305`, "Approve and send" and "Return with a note" are `aria-disabled` with no `href`. `ReconcilePanel` shows, and its answer is one POST to `/actions` with none to `/steps` or `/decision`. This holds before and after a page reload, and a forced click sends nothing. — verify: component tests and e2e at 1440, 390 and 320.
20. **Wrong user, wrong tenant, signed out.** With `X-Mock-Scenario: 404` or `403`, `/work/W-2301` shows `NoAccessState` with no title, client or id, and `document.body.textContent` has none of them. A 401 shows the signed-out callout with `next`. A 403 on a step reloads and shows "You can't take that step.". The decide page for a task with `you_can_act: false` offers no decision (F-16 behaviour). — verify: component tests.
21. **Nothing derived from `/me`.** Personas `pm`, `ceo` and `finance_lead` see the same controls for the same fixture. — verify: component test across personas; `git diff` adds no `/me` read under `frontend/src/features/workspace`.
22. **Unknown and restricted.** On W-2307 the unknown due reads "Unknown" (never 0, blank or "-"), the restricted notes item shows only its label, and none of its hidden strings are in the DOM. — verify: component test.
23. **Notes text grants nothing.** A fixture suggestion whose text says "approved by Kemi; owner Tunde; due today" changes no owner, due, audience or decision field, and is shown as plain text only. — verify: component test on a W-2307 decision.

### Quality
24. **Accessibility.** For W-2301 to W-2308 at 1440 and 390: no axe violations (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`), no sideways scroll, visible focus, 44px targets on phones (D-92c, D-95), focus to the form heading on open and back on Escape, errors announced, live regions for done, waiting and uncertain, and no wrapping button labels or tags. — verify: `e2e/minutes.spec.ts`.
25. **Shared components and tokens.** New UI imports from `@/components` (no new local button, tag, checkbox, panel or table). `grep -nE "#[0-9a-fA-F]{3,8}\b|rgba?\(|hsl\(" ` on this feature's CSS diff returns nothing. — verify: the diff and the grep.
26. **Contract not extended.** `git diff --stat` shows no change in `frontend/src/api/**`, `apps/**`, `architecture/**`, `design/**` or the protected paths. The proposal keys exist only in fixtures and `proposals.ts`, are checked on their own and are stripped in `mock-contract.test.ts`, and fixtures otherwise validate with no stripping. — verify: `tests/mock-contract.test.ts`; `git diff --stat`.
27. **Mock matches the contract.** `minutes-mock.test.ts` runs W-2301 to W-2308 through the E-WORK-STEP handler: a bad body gives 422, a wrong revision 409, an unknown step 404, and a repeated key returns the stored reply with send count 1. The decide sidecars apply once. E-LINE-OPTIONS `minutes/owner` returns `owner.json`. — verify: the test.
28. **No real send, no overclaim.** Every e2e request goes to port 4762. build.md and the PR state the D-LINE-WORKSPACE limits, call the template a test template, and claim no real backend, idempotency or working line. — verify: build.md and the recorded requests.
29. **Existing behaviour not weakened.** `tests/workspace*.test.*`, `weekly*.test.*`, `work-item*.test.tsx`, `decide*.test.tsx`, `response*.test.tsx`, `start-work*.test.*`, `shell.test.tsx` and the matching e2e specs pass with no assertion removed or loosened. No existing fixture is edited. F-21's eight scores do not drop. — verify: `delivery/checks.sh`; `git diff`.
30. **New tests run** in `delivery/checks.sh`, covering criteria 6 to 23. — verify: run output in `round-<N>/build.md`.
31. **build.md evidence:** commands and results, the 8 scores and waivers, every exception with its Conflicts number, every frame change with its reason, every proposal and backend item, and the open design item of Conflicts 4. — verify: file content.

## Out of scope
- The `internal` and `published` boards (F-23b): filed-at-once, "Actions created", "OWNER NEEDED", delivery receipts and "Open actions".
- Inline in-table owner dropdowns, an always-open audience control, an in-page Approve/Return (Conflicts 3 Option B) and a section placement hint. These are proposals only.
- Choosing recipients, editing them, or deciding whether client minutes need review. Creating actions client-side, computing counts, parsing notes, or deriving owners or dates from notes text.
- Backend, OpenAPI, `schema.d.ts`, `architecture/**`, `design/**`, real E-DOCUMENT bodies, real meeting records, and a `work_id` parameter on E-LINE-OPTIONS.
- Other lines, `src/shell/**`, `my-work/**`, the existing work item boards, new npm dependencies, and changes to F-17's region driver.

## Assumptions
- Approve and Return use `task_id` links to the F-16 page. Reason: readiness binds the review to E-TASK-CLAIM and E-TASK-DECIDE, and the frame already renders that.
- The phone Return gets its note on the F-16 page. Reason: it is the smallest change that never sends a Return without a note; it is pending the design engineer.
- Actions carry a ticked box. Reason: `item_ids` must equal what the PM saw, and no backend rule says "not removed means confirmed".
- `items_default` and `links[]` live in fixtures and one proposal reader, stripped for the contract check. Reason: the caller's instruction and the D-WORKITEM-VIEW precedent (`mock-contract.test.ts:262`).
- The `task_id` link honours the page lock. Reason: without that, an approve link stays active after an uncertain send (INV-RESEND); this is a general safety fix.
- The owner options are not scoped by work item in the mock. Reason: the contract has no `work_id` parameter, and adding one would extend it locally (G-SCR28-4 recorded).
- A blank owner or due is left out of `inputs`. Whether that clears or keeps the value is the backend's call. Reason: the sources are silent, and INV-UNKNOWN forbids sending today or 0.
- The recipients section is shown on review. Reason: readiness requires the exact recipients before a send; it is pending Conflicts 5.
- The drafted fixture has no "Open the minutes". Reason: the drafted board draws none, although readiness listed it.
- The fixtures are served to the `pm` persona for every board, including the PMO Lead's review. Reason: the mock has no PMO Lead persona and the frame derives nothing from role.
- The E-DOCUMENT failure sentences are frontend-owned and neutral. Reason: the sources are silent and they are not business rules.
- Ports are 4761/4762 and fixtures W-2301 to W-2308. Reason: they are unused by any other spec or config.
