# A Finance reviewer reviews the BU totals source and result, seeing only what the API serves them

> Tasks: FE-FIN-BU. Architecture: v9 package (revision as pinned in the feature record at branch time); contract `contracts/psl-factory.openapi.json` 1.25.0. Design: approved 13 Nov canvas under the recorded D-173/D-181 exceptions in `design/review.json`; screens: SCR-57 part 1 (`SCR-57-{desktop,mobile}-{source-review,investigating,held,result-review}`). Decisions: D-187 (LD-Q1 "Build on the API"), D-185, D-182 rule.

## Summary
- The BU totals work item (`finance-bu/v1`) opens as a panel of the live work page. It draws four states from `GET /work/{id}/business-units`: source and rule review, Chidi investigating, held by small-group protection, result review. Nothing is sent to anyone in this feature (publish, receipts and verified are F-107B).
- A reviewer approves or returns the source/rule, or approves/returns the result, with `POST /work/{id}/reviews` (`kind: business_unit`). The page infers no role: `review_subjects[]`, `can_publish`, `can_correct` and `recipient_only` decide what is drawn.
- Disclosure follows D-187: the page shows exactly the fields the API returned to this person and nothing else. Any board figure the API did not serve (staff counts, "Legal (2 people)", the minimum group size, "6 BU heads", people's names, owner names) is hidden, with no placeholder and no gap. A recipient-only reader gets the reduced view.
- Money is shown only as the served decimal strings with the served `currency` and `period`. Unknown shows "Unknown", never 0. The page computes no sum, count or percentage.
- Waits (not blockers): F-85 (shared adapter, PR #101), F-87 (the `Actions` slot and `useWorkCommand`) and F-108/F-110 (the payroll match this reads) must be on main before the build starts. Merge goes to the design engineer's merge batch (high risk).

## Context
Code is the lane D worktree `/Users/Hunchoo/psl-factory-worktrees/lane-d/frontend` (API 1.25.0).
- Page and frame: `src/features/work-item/` (`WorkItemView.tsx` etc.; F-85 adds the live view and `PanelView`) and `src/features/workspace/` (lane C's; `adapter.ts` with `PanelRef`, `LineContext`, `LineAdapter`, `CommandDescriptor`, `makeCommand`, `registerLineAdapter`, `adapterFor`; F-87 adds `Actions`, `LineActionsProps` and `useWorkCommand`). Not changed here.
- Existing Finance features for layout reference: `src/features/finance/month-end`, `src/features/finance/payments`; the sibling line adapters from lane D (F-100 to F-104) set the pattern for a per-line folder. This feature adds `src/features/finance/business-units/`.
- Client: `src/api/client.ts` (`liveApi`, `call()`), `src/api/errors.ts` (`ApiError` kinds), generated `src/api/live-schema.d.ts` (must be from 1.25.0; builders merge origin/main first, main currently fails typecheck until lane A's hotfix lands).
- Boards: `design/canvas/finance/project/SCR-57-{desktop,mobile}-{source-review,investigating,held,result-review}.dc.html`; line map `LINE-finance-bu-desktop.dc.html`.
- Live reads and writes (contract 1.25.0):
  - `GET /api/v1/work/{work_id}/business-units` (`business_units_detail`) required: `expected_revision, case_revision, stage, finding, recipient_only, inputs, result, publication_id, receipt_id, receipt_ids, totals, period, currency, review_subjects[], proofs[], can_publish, can_correct, verified_at`.
    - `inputs`: `null` or `{mode: staff|event, payroll_id|null, source_id|null, rule_ids[], comparison: null|{run_id, metric: revenue|direct_cost|staff_cost|opex|other}}`.
    - `result`: `null` or `{id, kind: event|staff, status: held|complete, codes[], scope: null|{entity, period, currency}, totals: null|{<key>: string(<=128)|null}}`.
    - `totals`: `null` or an object of key to decimal string or null (keys are not typed in the contract; see Questions 1).
    - `review_subjects[]`: `{id, kind: source|rule|event|staff, version, purposes[]: source|rule|event|staff|historical}`. `proofs[]`: `{id, version, kind}`.
  - `GET /api/v1/projects/{case_id}/business-unit-intake` returns `{case_revision, payroll[{id, reference}], events[{id, reference, version}], rules[{id, reference, version, payroll_id}], comparisons[int]}`; only matches the current operator may use.
  - `POST /api/v1/work/{work_id}/business-units` (201 `{work_id, state, revision, record_id}`), bodies by `action`: `prepare_rule {expected_revision, case_revision, reference, operation_key, payload{employee_id, component, entity, period, standard_pool_ref, weights[{bu, weight}], rationale_evidence_id}}`; `publish {expected_revision, case_revision}` (F-107B, not built here); `restart {expected_revision, case_revision, inputs, configuration_id, instruction_key, reason}`.
  - `POST /api/v1/work/{work_id}/reviews` body `{kind:'business_unit', expected_revision, case_revision, work_id, purpose (1..64), verdict: approve|return|revoke, operation_key, evidence_id}`.
  - All errors: 400, 401, 403 (incl. `csrf_failed`), 404, 409, 413/415 on uploads, 422, 429, 500, 503 with `{code, message, fields?}`.
- Backend answers: E-27 (fields; a too-small group holds the publication; a recipient does not get private staff counts), E-28 (actions), E-32 (staff totals use the exact eligible payroll match run), E-26 and E-30 (recipient views are approved projections).

## Contract

### Where the screen lives
The panel for a `finance-bu/v1` work item is a `LineAdapter` registered once from `src/features/finance/business-units/index.ts` with `key` equal to the `panels[].key` that `GET /work/{id}` serves for this line (builder reads the real key from a live work item and records it in build.md; the mock uses `business-units`). `read(ref)` calls the panel's `url`; the adapter also reads `GET /projects/{ctx.caseId}/business-unit-intake` once per load, and a failure of that read only hides the reference text (see Inputs table), never the panel. Write forms are `BusinessUnitActions.tsx` (`adapter.Actions`, F-87's slot, sending through `useWorkCommand`); nothing is added in `src/features/workspace`. The page crumb and header (project, "BU totals", work reference, SAMPLE DATA tag, sample = `item.sample`) come from F-85's live header.

### Which board shows (a pure function of the served read; the page infers no role)
| Served | State drawn |
|---|---|
| `recipient_only === true` | Reduced view only (below), whatever else is present |
| `result === null` and `review_subjects[]` non-empty | source-review |
| `result === null` and `review_subjects[]` empty | investigating |
| `result.status === 'held'` | held |
| `result.status === 'complete'` and `verified_at === null` and `publication_id === null` | result-review |
| `publication_id` non-null, or `verified_at` non-null, or `receipt_id`/`receipt_ids[]` non-empty | "Sent. This is shown on the next screen." plain note only (F-107B draws it); no publish control |
| none of the above | the header and the served `finding`, nothing else |

`stage` and `finding` are shown as served (the stage as the one-line status under the title, `finding` as the sentence under it). The seven-station track the boards draw is hidden (F-85 LC-Q1 option 1).

### Source-review (`SCR-57-*-source-review`)
- Inputs list: one row per served input, each with a state word. Rows come from `inputs` and `review_subjects[]`: "Payroll staff match" (when `inputs.mode === 'staff'`, with the `payroll[].reference` for `inputs.payroll_id` when the intake read gives it), "Event source" (`mode === 'event'`, `events[].reference` for `source_id`), and "Exception rule" for each `inputs.rule_ids` entry (`rules[].reference` and `version` when the intake read gives it). A row is "Needs you" when a `review_subjects[]` entry of the same `kind` and `version` is listed, and "Approved" otherwise. No count line ("2 inputs"), no names (the boards' "Bisi Ade"/"FROM" column is not drawn).
- Decide block: copy "Approve the payroll staff match as this run's source." only in `staff` mode (event mode: "Approve this event source."). The old line "You see counts only, never individual pay." is kept only when the person is not shown pay by the API, which is always true for this screen: it stays.
- Per `review_subjects[]` entry and each of its `purposes[]` that is `source` or `rule`: a decision row with "Approve" and "Return". An evidence list (radio) from `proofs[]` (kind and version words, nothing preselected, nothing invented); both buttons stay off while it is empty or none is chosen, with the reason written beside them. No "Reject" (board note: "BU totals have no Reject; return it with a note instead", the "note" part is removed, Conflicts 1).
- A purpose the person cannot decide is simply not listed by the API and not drawn. `can_correct` false hides the exception-rule form entry points (there are none drawn; see Out of scope).

### Investigating (`SCR-57-*-investigating`)
Shows the stage and finding, the Inputs list above (all "Approved" states), and "Chidi is working" only from the served `stage`/`finding` text; the board's "Population: Staff in the match 136 / Business units 6", "1 BU below the minimum", "step 2 of 3", "Started 09:30" and the "Ask Chidi" box are hidden unless the API serves them (it serves none). No action buttons. While the work `state` is `processing` the page re-reads on F-85's 5 s polling rule.

### Held (`SCR-57-*-held`)
- Headline: "Publishing is blocked by small-group protection." only when `result.status === 'held'` (the held word comes from the status; the reason text is the served `finding`, shown as given). The board's second sentence "Legal has 2 people, so its total would reveal their pay" is hidden: it names a group and its size, which the API does not serve.
- "Hold reasons" shows one row: the served `finding` with the tag "Blocks publishing". When `finding` is empty the page shows "Held" and no reason (never an invented one). Raw `result.codes[]` are not shown to the person; they are used only to choose the state (a code is never turned into a number or a group name).
- "Payroll match: Approved" and "Comparison with Finance totals: Matches" rows: drawn only from served data: the payroll row from the Inputs list; the comparison row only when `inputs.comparison` is non-null, as "Compared with Finance {metric word}" and no Matches/Differs verdict (none is served).
- "Next: A Finance Lead sets the disclosure rule" is drawn only as the link "Open Finance rules" to the existing Setup Finance rules route when the app has one and it is reachable for the person; otherwise nothing. No minimum group size number appears anywhere unless it is inside `result`/`finding` text as served.

### Result-review (`SCR-57-*-result-review`)
- Table "Totals · aggregates only", title and sub-line from `period` and `currency` (and `result.scope.entity` when non-null). Rows from `totals` (see Questions 1 for the key shape; the assumed shape is below). Business unit label as served; staff cost as the served decimal string formatted with `currency` (for example `NGN` shown as ₦ with two decimals, using the existing money formatter `src/lib/money` or the one F-100/F-103 use). A null value shows "Unknown". Staff count column: drawn only when the served totals carry a staff count for the row; otherwise the column and header are not drawn at all (no gap, no dash).
- The page computes nothing: no total row, no share, no count of units, no sum of the rows. If `totals` is null or empty on a complete result the table is replaced by "No totals were served for this result."
- "Decide · BU reviewer" block: for each `review_subjects[]` purpose that is `staff`, `event` or `historical`: Approve and Return, the same evidence list as above. The `historical` purpose is explained with the board's sentence, "A historical review is added if this replaces a period already published", only when the API lists a `historical` purpose. "Withdraw approval" (verdict `revoke`) is drawn beside them for the purposes listed (Questions 3). No note field (Questions 2).
- No "Publish" control in this feature, even when `can_publish` is true.

### Reduced view (`recipient_only === true`)
Shows the title, period, currency, the served `finding`, and the `totals` rows as served (approved aggregate only). No Inputs list, no hold detail, no reviewer block, no evidence list, no intake read is made, no write control, and no counts. Header words: "Your copy of the BU totals". If `totals` is null: "Nothing has been published to you yet."

### Writes
All writes go through `makeCommand` and F-87's `useWorkCommand` (one write at a time, press lock, uncertain lock after a timeout/5xx, fresh descriptor per attempt, reload on 409). Revision tokens and the idempotency key are never inside `inputs`.
| id | url | body | key | success |
|---|---|---|---|---|
| `business-units.review` | `POST /api/v1/work/{id}/reviews` | `{kind:'business_unit', expected_revision, case_revision, work_id, purpose, verdict, operation_key, evidence_id}` | `operation_key` (uuid, new per attempt) | 201 |
| `business-units.prepare_rule` | `POST /api/v1/work/{id}/business-units` | `{action:'prepare_rule', expected_revision, case_revision, reference, operation_key, payload}` | `operation_key` | 201 |
| `business-units.restart` | same url | `{action:'restart', expected_revision, case_revision, inputs, configuration_id, instruction_key, reason}` | `instruction_key` | 201 |
- Tokens come from the business-units read (`expected_revision`, `case_revision`), not the work item header; a null/absent token holds the write with the reason "We don't have this item's current version yet. Reload and try again."
- Only `business-units.review` has a form in this feature. `prepare_rule` and `restart` are defined as descriptors (shape-tested) and not drawn: no part 1 board has a form for them and `restart` needs a `configuration_id` the API does not serve (Questions 4). `publish` is not defined here.
- After 201: re-read the panel; the decision row shows "Recorded: Approved" / "Returned" / "Withdrawn" from the verdict the person pressed only after the re-read no longer lists that purpose (or lists the new state); otherwise "Recorded. The page will update when the review is applied."
- Errors: 400/422 show the server message and `fields[]` as given; 403 "You can't do this." plus server message (also `csrf_failed`: refresh session, "Press again"); 404 "This record is unavailable."; 409 re-reads and shows the server message (includes "you cannot review your own work" style independence holds as served); 429 "Try again shortly."; network/5xx lock until the re-read shows what was recorded.

### Read states and permission
- Loading: panel skeleton as F-85's. Empty: `result === null` and no subjects is the Investigating state, not "empty".
- Error: 401 signed-out state; 403 and 404 both render exactly "This record is unavailable." (no difference, no existence leak); 429/503/network show Try again.
- A restricted payroll row in the Inputs list has no link; the page never links to payroll, working rows or individual records. No request is made to payroll routes.
- 200 with some served fields null shows nothing for that field (not 0, not "Not set").

### Fixture examples (mock, port 4991; the shapes are the contract, ids are the builder's)
Mock file: new `frontend/mock/work-bu.mjs` registered from `mock/server.mjs`. Work ids 4701 to 4708 (mock-only, named in build.md; no change to `mock/finance*.mjs` unless unavoidable, and then named).
- `4701` source-review, Finance Lead: `result:null`, `inputs:{mode:'staff', payroll_id:10, source_id:null, rule_ids:[21,22], comparison:null}`, `review_subjects:[{id:10,kind:'source',version:1,purposes:['source']},{id:21,kind:'rule',version:2,purposes:['rule']}]`, `proofs:[{id:31,version:1,kind:'pdf_copy'}]`, `can_publish:false`, `recipient_only:false`.
- `4702` investigating: `result:null`, `review_subjects:[]`, `stage:'calculating'`, `finding:''`.
- `4703` held: `result:{id:7,kind:'staff',status:'held',codes:['small_group'],scope:{entity:'PSL',period:'2026-10',currency:'NGN'},totals:null}`, `finding:'<served sentence>'`.
- `4704` result-review: `result.status:'complete'`, `totals:{...}` as in Questions 1, `period:'2026-10'`, `currency:'NGN'`, `review_subjects:[{id:7,kind:'staff',version:1,purposes:['staff','historical']}]`.
- `4705` result-review where one value is `null` (Unknown) and the served totals carry no staff counts (column hidden).
- `4706` recipient_only: `recipient_only:true`, `totals` set, `inputs:null`, `result:null`, `review_subjects:[]`, `proofs:[]`.
- `4707` held-and-no-finding: `finding:''` (shows "Held" only).
- `4708`: 404 for any caller (also used for the not-yours case; the 403 fixture `4709` returns the same wording).
- Canary rule: fixtures for 4701 to 4707 must also carry, in the mock server's raw response only, extra keys the real API would never send to that person (`staff_count`, `employee_id`, `names`, `legal_staff`, `recipient_count`, `min_group_size`). The tests assert none of their values reach the DOM.

## Lanes
- Frontend lane (owner of all of this feature): `frontend/src/features/finance/business-units/**` (adapter `businessUnitsAdapter.ts`, `model.ts` read-to-view mapper, `BusinessUnitsPanel` sections, `BusinessUnitActions.tsx`, `commands.ts`, css), `frontend/mock/work-bu.mjs` and its registration line in `frontend/mock/server.mjs`, `frontend/src/api/types.ts` (BU read types only, from `live-schema.d.ts`), unit tests under the same folder, `frontend/e2e/finance-bu.spec.ts`.
- Backend lane: none. No backend, migrations or contract edits. Open backend questions go to `delivery/connect/backend-questions.md` via the coordinator.
- Integration owner: lane D coordinator. Shared files and owners: `frontend/src/features/workspace/*` (lane C; read only here), `frontend/src/features/work-item/*` (lane C; read only, including F-85/F-87 `PanelView` and `Actions` slot), `frontend/mock/server.mjs` (shared; one registration line), `frontend/mock/finance*` (lane B; not changed, any change named in build.md), `src/api/*` (shared; only types). The registration of the adapter happens once F-85 and F-87 are on main.
- Protected paths in `delivery/config.json` stay unchanged.

## Acceptance criteria
Ports: Next 4990, mock 4991, Django 8030 (Postgres per the local dev note, account names per the seed; the builder records which accounts were used).
1. `/work/4701` (mock) shows the Source and rule review: an Inputs list with "Payroll staff match" (with its reference) and two "Exception rule" rows marked Needs you, an evidence list (nothing preselected), and Approve and Return buttons that are off until an evidence item is chosen; there is no Reject, no note box, no "FROM" column and no person's name — verify: open the page at 1440 and 390 wide against the two source-review boards; `frontend/e2e/finance-bu.spec.ts` asserts these.
2. Choosing evidence and pressing Approve sends exactly one `POST /api/v1/work/4701/reviews` with `kind:'business_unit'`, the `purpose` and `verdict:'approve'`, `work_id`, `evidence_id`, `expected_revision`, `case_revision` from the BU read, and a uuid `operation_key`; Return sends `verdict:'return'` — verify: network panel and unit test of `business-units.review` body; assert no token or key appears in any `inputs`-style object.
3. With an empty `proofs[]` both buttons stay off and the reason is written beside them; no evidence id is invented or taken from another source — verify: e2e on a fixture with `proofs:[]`.
4. `/work/4702` shows the Investigating state with the stage and finding only: no "136", "6 business units", "1 BU below the minimum", "step 2 of 3", start time or "Ask Chidi", and no buttons — verify: e2e asserts those strings are absent; compare with the investigating boards.
5. `/work/4703` shows the held headline, one hold-reason row whose text equals the API's `finding`, and no group name, no "2 people" and no minimum-size number; `/work/4707` (empty finding) shows "Held" with no reason row and no invented text — verify: e2e DOM text equals fixture `finding`; grep the DOM for `Legal`, `people`, `minimum` returns nothing.
6. A held result shows no totals table and no Approve button — verify: e2e on 4703.
7. `/work/4704` shows the Totals table with business unit and cost rows from `totals`, formatted with the served `currency`, titled with `period`; no total row, no percentage, no number the page computed — verify: e2e compares each cell with the fixture string; unit test that the mapper output contains only served values (property test: every cell string appears in the input).
8. A null cost in `totals` (`/work/4705`) shows "Unknown", never 0, `0.00` or a dash; where the served totals carry no staff counts the Staff column and its header do not exist in the DOM — verify: e2e on 4705.
9. In result-review the Approve, Return and Withdraw buttons post `verdict` `approve`, `return`, `revoke` to `/reviews` for the served purpose; no Publish button exists even when `can_publish` is true — verify: e2e on 4704 with `can_publish:true`; grep `action:'publish'` in `frontend/src` finds only a comment or nothing.
10. A recipient (`/work/4706`, `recipient_only:true`) sees only the title, period, currency, finding and totals; no Inputs list, hold detail, evidence list, review or other write control, and no request to `business-unit-intake` is made — verify: e2e asserts the DOM and the request list.
11. Disclosure proof, mock: for fixtures 4701 to 4707 the canary keys (`staff_count`, `employee_id`, `names`, `legal_staff`, `recipient_count`, `min_group_size`) and their values appear nowhere in the DOM text, attributes or the page's serialized state — verify: e2e `finance-bu.spec.ts` "disclosure" tests read `document.body.innerHTML` for each fixture; unit test that the model mapper drops unknown keys (allowlist, not blocklist).
12. Disclosure proof, live: against Django on 8030 (seeded BU work item), for three people (a Finance reviewer, a BU recipient, a person with no access), the DOM of each equals what `GET /api/v1/work/{id}/business-units` returned to that same session: every figure on the page is in the JSON, and every staff count, name or pay figure absent from the JSON is absent from the page; the no-access person gets exactly "This record is unavailable." — verify: `curl` with each session cookie next to the page text; record the three comparisons in build.md.
13. A 403 and a 404 on the BU read both show exactly "This record is unavailable." and nothing distinguishes them; `/work/4708` and `/work/4709` match — verify: e2e compares the text and DOM structure.
14. A restricted payroll row in Inputs has no link or button; no request is made to any payroll or working-rows route anywhere on the page — verify: e2e asserts zero requests matching `/payroll`; DOM has no anchor in the Inputs list.
15. A failed `business-unit-intake` read (403/404/500) leaves the panel drawn with the Inputs rows labelled by kind only ("Payroll staff match", "Exception rule"); it does not hide the review controls — verify: mock scenario `intake_fail`.
16. Stale write: a 409 on Approve re-reads the BU read, shows the server message, and does not retry by itself; a second press sends a fresh `operation_key` — verify: unit test of the descriptor and e2e with mock scenario `stale`.
17. Uncertain write: a dropped connection after Approve locks the buttons, says it could not confirm, and unlocks only when the re-read shows a changed `expected_revision` or purpose state; no automatic resend — verify: e2e with mock scenario `drop`; count POSTs.
18. A 403 with `csrf_failed` refreshes the session once and says "Press again" without sending a second review — verify: unit test counts fetches.
19. A 422 shows the server message and `fields[]` as given — verify: mock scenario `invalid`.
20. A null `expected_revision` or `case_revision` holds the write with the "current version" reason and sends nothing — verify: unit test on the descriptor.
21. `prepare_rule` and `restart` descriptors exist with the bodies in the table (including `operation_key` and `instruction_key`) and are not rendered; the page has no control that sends `publish`, `prepare_rule` or `restart` — verify: unit test on `commands.ts`; grep `liveApi.POST` shows only `useWorkCommand` and the upload route use.
22. Page load, polling and navigation make no write — verify: e2e asserts zero POSTs on load of each fixture.
23. Viewport check at 1440 and 390: each of the eight boards is matched for the parts that remain; every hidden part leaves no empty heading, no gap and no "not available" text — verify: screenshots of 4701 to 4705 at both widths reviewed against `design/screens.md` SCR-57 artboards; the conflicts list below is the allowed difference.
24. Typecheck, lint and tests pass, and `api-live-schema-drift.test.ts` still passes with `live-schema.d.ts` regenerated from 1.25.0 — verify: `delivery/checks.sh`.
25. build.md and the PR description state, in plain words, what is hidden under D-182/D-187, and name every change under `frontend/mock/finance*` (expected: none) — verify: read build.md.

## Out of scope
- `SCR-57-{desktop,mobile}-{publish,receipts,verified}` (F-107B): the Publish action to the CEO and BU heads, `POST /work/{id}/aggregate-receipt`, recipient confirmation, verified states, cancel-after-publish.
- Starting a BU totals run (`POST /work`, `finance-bu/v1`, SCR-04) and the Event mode (no board); capturing an event source (`POST business-unit-intake`).
- The payroll import and run (F-108/F-110), payroll corrections, working rows and any link to them.
- The exception-rule form (`prepare_rule`) and the restart form: descriptors only.
- Setup editing of Finance rules or of disclosure rules; any minimum-group-size number or rule invented in the UI.
- Backend, OpenAPI, migrations, and anything in `frontend/src/features/workspace` or `frontend/src/features/work-item` (lane C).
- A client-side role check, hiding by job title, or computing any sum, count, percentage or group size from `totals`.
- Notifying anyone; no message or email is sent by this feature.

## Assumptions
- The panel `key` is `business-units` in the mock; the builder uses the key the live work item serves. Reason: the contract serves `panels[].key` as free text and no answer names it.
- `totals` is a map of key to decimal string or null (per the contract), and the model reads each entry as one row: key = business unit label, value = staff cost. A staff-count value is shown only if the live server's actual keys carry it per unit. Reason: untyped in the contract; the builder reads a real live response and records the exact key shape in build.md. Not guessed in code beyond an allowlist of the served keys.
- The state table above (which board shows) is derived from `result`, `review_subjects[]`, `publication_id`, `verified_at` and `recipient_only`, not from the free-text `stage`. Reason: `stage` has no enumerated values.
- One decision row per purpose listed in `review_subjects[]`: purposes `source`/`rule` in source-review and `staff`/`event`/`historical` in result-review. Reason: `/reviews` takes one `purpose` per decision and no answer maps boards to purposes.
- The review body needs an `evidence_id`; it is chosen from `proofs[]`, nothing preselected, per the lane D proof rule (PSL answer 1, D-1). Reason: the review route has no other proof route.
- The Return button sends `return` with no note. Reason: the review body has no note or reason field.
- Raw `result.codes[]` are not shown; the `finding` text is the staff-facing wording. Reason: E-27 says use the authorised staff-facing finding; codes are stable machine values.
- Money formatting reuses the existing formatter that F-100/F-103 use, with `currency` as served. Reason: one money presentation across Finance.
- Intake read failure is non-fatal. Reason: it only supplies reference words.
- Mock ids 4701 to 4709 are free. Reason: no fixtures exist yet.

## Questions
1. Totals keys and the Staff column (board conflict G-57-4 also). The contract types `totals` only as a key to string-or-null map, so which key is the staff count is unknown. Options: (a) build to the real keys read from live Django and draw the Staff column only where served, otherwise hide it (recommended); (b) ask the backend to type `totals` (new backend question) and hold the Staff column until then; (c) draw the column always with "Unknown". The boards show 4 BUs and 7 recipients, the investigating board 6 BUs and 7 recipients: build to live data, never to a board number.
2. The decision note. Boards draw "Note (needed to return, reject or withdraw)" and "Return with a note"; `/reviews` for `business_unit` has no note field, only `evidence_id`. Options: (a) remove the note box and say "Return" (recommended); (b) keep a note box that is not sent (misleading, not recommended); (c) ask the backend to add a reason field and hold Return until then.
3. "Withdraw approval" on result-review. The API accepts `revoke` but serves no flag saying an approval exists. Options: (a) draw Withdraw for each served purpose and show the server's refusal as given (recommended, matches the board); (b) hide it until the backend serves "approved by you"; (c) draw it only after a reviewer approved in the same session.
4. `restart` and `prepare_rule` forms. No part 1 board has a form, and `restart` needs a `configuration_id` that no read serves. Options: (a) descriptors only now, forms later when a board or the backend names the source (recommended); (b) build a free-text form (invents data, not recommended); (c) pull both into F-107B.
5. Board conflicts to settle once (all are hides, D-182/D-187; recommendation: hide each): the investigating board's "Staff in the match 136 / Business units 6", "1 BU below the minimum", "Started 09:30" and "Ask Chidi"; the held board's "Legal has 2 people", "Legal (2 people)" and the "Matches" verdict; the source-review "FROM" owner names and "Needs you/Approved" owner column; the seven-station track on all boards; the mobile held board's "Start" button (start is SCR-04). Options: (a) hide all (recommended); (b) keep "Ask Chidi" as a link to the existing assistant (not served by this endpoint); (c) draw the counts for entitled people only once the backend serves them.

## Conflicts with the boards
See Questions 1 to 5. In brief: the page removes the board's staff and unit counts, group names and sizes, owner names, the "Matches" verdict, the Note box, the station track, the "Ask Chidi" box and the "Start" button on the held phone board; it adds the "Reduced view" for recipient-only readers (no board draws it), the evidence list on the decision blocks (the review needs an `evidence_id`; no board draws it), and the "Sent. This is shown on the next screen." note. Recommendation: hide the removed parts, and the design engineer draws the two added parts before build if needed.
