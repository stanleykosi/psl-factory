# The cash forecast page shows the live forecast, its group disclosure and its delivery state, read only

> Tasks: FE-CONNECT-1 (read side of W-4001..W-4013 and W-2004; part 1 of 2, part 2 is F-103B). Architecture: v9 package (revision as pinned in the feature record at branch time); contract `contracts/psl-factory.openapi.json` 1.24.0. Design: approved 13 Nov canvas with the D-173/D-181 exceptions in `design/review.json`; screens: SCR-56 (investigating, review, group-rows, group-review, uncertain, verified, actuals; desktop and mobile; `design/canvas/finance/project/SCR-56-*.dc.html`). Builds on the F-85 line adapter (`/Users/Hunchoo/psl-factory-main/delivery/features/F-85/spec.md`); the build starts when F-85 is on main.

## Summary
- The `cash_forecast` work page (`/work/{id}`) reads the live `GET /work/{id}/forecast` through a forecast line adapter and draws the forecast months, findings, jobs, matches, and the group disclosure the API permits. The v7 mock shape (F-43) is no longer read for numeric work ids.
- The actuals for one month are read from `GET /work/{id}/forecast/actuals/{month}` (rows, actuals, history, with "more" flags shown as such).
- The delivery state comes from `forecast.observation`, `jobs[]`, `can_restart` and `restart_policy_id`, shown read only, including the uncertain state. The recorded proof is a link only.
- Group disclosure shows only what the API returns: permitted rows, selected fields and metadata, recipients. No staff names or individual pay appear, and nothing payroll-related is built from another read.
- Nothing is sent. Review verdicts, withdraw, post, record or match an actual, disclosure edits, observation recording and retry/cancel are F-103B; their controls are hidden or disabled. Unknown money stays unknown.

## Context
Today (lane D worktree `/Users/Hunchoo/psl-factory-worktrees/lane-d/frontend`, main b8542c79):
- The forecast page is the v7 build from F-43: `src/features/workspace/Workspace.tsx` draws `item.workspace` for `line_key: "cash_forecast"`; `forecastLine()` in `src/features/workspace/labels.ts:77` selects the forecast layout; `src/features/work-item/WorkItemOverview.tsx:717-744` skips `ReconcilePanel` for it. Mock fixtures `mock/fixtures/work/W-4001..W-4013*.json`, `mock/fixtures/response/W-4003.*.json`; e2e `e2e/cash-forecast.spec.ts` pins the v7 behaviour.
- After F-85 merges: `src/features/workspace/adapter.ts` (`LineAdapter`, `registerLineAdapter`, `adapterFor`, `CommandDescriptor`), the live work item read in `src/features/work-item/`, and `liveApi`/`call()` in `src/api/client.ts`. Live types are generated in `src/api/live-schema.d.ts` (regenerate from 1.24.0 if the forecast types are not present).
- Live reads (`GET /api/v1/work/{work_id}` lists the forecast panel in `panels[]`; panel keys per line are not published, backend question A-16):
  - `GET /work/{work_id}/forecast` (`forecasting_detail`): `expected_revision, case_revision, scenario_id, run_id|null, version_id|null, stage, finding, review_roles[], audience internal|management|group, result|null, jobs[], disclosure|null, can_restart, restart_policy_id|null, observation|null, matches[]`.
    - `result` (when not null): `status, entity, currency, basis, as_of (date), findings[], items[], periods[], actuals[]`; the four arrays are untyped objects.
    - `jobs[]`: `id, status, receipt_ids[], can_retry, can_operate`.
    - `disclosure` (when not null): `configuration_id, row_keys[], recipient_ids[], oracle_choices[], decision_choices[], selected_rows[], selected_fields[], selected_metadata[]`, arrays untyped.
    - `observation` (when not null): `id, outcome delivered|not_delivered|unknown, has_proof`.
    - `matches[]`: `id, item_key, actual_id, amount (string)`.
  - `GET /work/{work_id}/forecast/actuals/{month}` (`forecasting_month`): `expected_revision, case_revision, scenario_id, month, rows[{key, expected, actual, status, notes[]}], actuals[{id, direction inflow|outflow, amount, verified}], history[{id, item_key, actual_id, amount, reversed}], more_actuals, more_history, more_notes`. It has no paging parameter; the three `more_*` flags only say that the list is cut.
  - `GET /work/{work_id}/forecast/observations/{observation_id}` (`forecasting_delivery_proof`): returns the private proof file (`application/octet-stream`), not a JSON state. See Question 1.
  - Errors on all three: 400, 401, 403, 404 (missing and not yours alike), 409, 422, 500, 503. Only `{code, message, fields[]}` bodies on 400/409/422.
- Backend answers: E-25 (shapes above), E-26 (group recipients get a separate approved projection with only the selected row fields and metadata; the field list excludes staff names, individual pay records and raw payroll input; a payroll-related cash assumption needs explicit inclusion and review on that exact projection).

## Contract

### Forecast line adapter (new, this feature's folder)
File `frontend/src/features/forecast/forecastAdapter.ts` (new), registered with `registerLineAdapter` under the key the live work item lists for the forecast panel (see Assumptions), reading `GET /work/{id}/forecast` through `call(liveApi.GET(...))`. `sections(readback, ctx)` returns existing `Section` objects only; `commands()` returns nothing in this feature. No file under `src/features/workspace/` changes; a needed frame change is named as a dependency on lane C (see Lanes).

### Section mapping (presentation only; nothing here decides access)
| Section | Source | Rule |
|---|---|---|
| Header facts | `result.entity`, `result.currency`, `result.basis`, `result.as_of`, `result.status`, `audience` | `as_of` shown as "As of {date}". Audience words "Internal", "Management", "Group". `result` null shows no figures and the empty state below. |
| Stage and finding | `stage`, `finding` | `finding` is shown as sent when non-empty (it is the live "why"). Unknown `stage` values are shown as raw text, never dropped. |
| Forecast months | `result.periods[]` | One table row per period, columns as the review board draws them (month, opening, in, out, closing) **only where the period object carries that field**; a missing amount shows "Unknown", never 0 or a carried-forward number. Amounts are the backend's decimal strings through `formatAmount`; the page adds, subtracts and rounds nothing. A period shape the mapper does not recognise is listed by its keys as text, never hidden (see Assumptions). |
| Expected items | `result.items[]` | A list under the table: item key and any amount or expected date it carries. |
| Findings | `result.findings[]` | One note each; none draws no section. |
| Actuals in the forecast | `result.actuals[]`, `matches[]` | Matches: item key, actual id, amount. Empty draws "No actuals matched yet." |
| Review roles | `review_roles[]` | "Reviewed by {roles}" as words. If empty the line is absent; no "reviewer not set" warning is drawn (no API field; D-182). |
| Group disclosure | `disclosure` | Drawn only when `disclosure` is not null. Shows `selected_rows` and `selected_fields` as the group's version (labels only for keys the API sent), `selected_metadata`, and the recipients (`recipient_ids`, plus names only if the item object carries them). `row_keys`, `oracle_choices` and `decision_choices` are shown read only as "Available" and "Choices on file", with no checkbox or select. Nothing is derived. |
| Delivery | `jobs[]`, `observation`, `can_restart`, `restart_policy_id` | Per job: status words, and "Receipt {n}" for each `receipt_ids[]`; a job with none reads "No receipt yet", never a tick. `can_retry` / `can_operate` are shown as "Can be retried" / "Can be operated" text only, for the reader to see. `observation.outcome` words: delivered "Recorded as delivered", not_delivered "Recorded as not delivered", unknown "Outcome not known"; `has_proof` true shows a "Proof on file" link to the observation route (below), false "No proof on file". `restart_policy_id` is shown only inside the line "Restart allowed under rule {id}" when `can_restart` is true. |

### Uncertain state
Drawn when `observation` is null and a job has a status the API reports as not finished, or `observation.outcome === 'unknown'`, or the mapped stage is the uncertain stage. The page says only what the response carries: the stage/finding text, each job's status, "Nothing has been resent from this page." No Cancel, Retry, Record what happened or Resend control is drawn (F-103B). A job status the page does not recognise is shown raw, and the uncertain banner is shown whenever `observation.outcome === 'unknown'` regardless of other fields.

### Actuals for a month
Route `/work/{id}` with the month selected in the page (a month control built from `result.periods[]` month keys; no new route; selection lives in the query `?month=YYYY-MM`). Request `GET /work/{id}/forecast/actuals/{month}`. Shows `rows` (key, expected, actual, status, notes), `actuals` (direction "In" or "Out", amount, "Verified" or "Not verified"), `history` (item key, actual id, amount, "Reversed" when `reversed`). Amount `null` or unknown shows "Unknown". When `more_actuals`, `more_history` or `more_notes` is true the section ends with "Showing the first rows only. The rest isn't available here." and no "Show more" control (the route has no paging parameter, see Question 2). A month with no rows shows "No actuals recorded for {month}." A 404 on the month shows "This record is unavailable."
No "Record actual", "Match" or "Leave unmatched" control is drawn.

### Observation proof
`GET /work/{id}/forecast/observations/{observation_id}` is a file download. The "Proof on file" link is a plain anchor to that URL (same origin, session cookie); no JSON is parsed and the page does not preview it. A 403/404 on download is the browser's response and is not intercepted. Nothing else is read from this route.

### States (each screen state)
- Loading: existing `WorkItemStates` loading while `GET /work/{id}` or the forecast read is pending.
- Empty: `result` null (no calculation yet): header, `stage`, `finding` and "No forecast figures yet." only; `jobs: []` draws no delivery section; `disclosure` null draws none; `matches: []` draws "No actuals matched yet."
- Error: 401 sign-in link (`/sign-in?next=<current path>`); 403 `forbidden` no-access; 403 `csrf_failed` is not no-access (refresh session, "Refresh your session and try again"); 404 "This record is unavailable." (the same words for missing and not yours); 409 "This changed while you were reading it. Reload."; 422 first `fields[].message`; 429/503 "Try again shortly" with Try again; network "We couldn't reach the server." Reads may be retried; there is no write. A failed forecast read does not blank the work item header; the section shows its own error.
- Uncertain: as above.
- Success: as the mapping above. At 390 px the same sections in one column; the periods table scrolls sideways inside its own focusable region (`ws-tablewrap`), never the page.
- Group view: when `audience === 'group'` the page shows no section other than what is listed under Group disclosure plus the header, periods and delivery; it draws no staff name and no per-person pay, whatever the arrays contain (see Acceptance 9).

### Hidden, with the gap stated
- "Reviewer not set" warning (no API field, D-182).
- Short phone money ("₦12.4M"): full `formatAmount` amounts at every width, since no shared short formatter exists in `src/components/format.ts`; the page never rounds an amount.
- All write controls: Approve, Return, Reject, Withdraw, Post, Record actual, Match, Leave unmatched, Save disclosure, Record what happened, Retry, Cancel. These are drawn as absent, not disabled, unless a board draws them inside a read state (then disabled with `title` "Available in the next release" is not used; absent is chosen, see Question 3).

### Fixture examples (mock serves live shape for numeric ids; v7 `W-xxxx` ids keep v7 answers)
- `4301` verified management forecast: `audience:"management"`, `result` with 6 periods (Jan with an unknown closing), `jobs:[{id:1,status:"delivered",receipt_ids:[9],can_retry:false,can_operate:false}]`, `observation:null`, `disclosure:null`, `matches:[{id:1,item_key:"inv-17",actual_id:5,amount:"12400000.00"}]`.
- `4302` review: `stage:"review"`, `review_roles:["Finance"]`, `jobs:[]`, `result` present.
- `4303` investigating: `result:null`, `finding:"Chidi is reading the opening balances."`, `run_id:null`.
- `4304` group disclosure: `audience:"group"`, `disclosure` with `selected_rows:["rent","loan"]`, `selected_fields:["kind","amount","expected_on"]`, `selected_metadata:["entity"]`, `recipient_ids:[3,4]`; the mock also serves a poisoned variant in which `selected_rows` contains a payroll key and a row object carries `staff_name` and `pay` (Acceptance 9).
- `4305` uncertain: `observation:{id:7,outcome:"unknown",has_proof:false}`, `jobs:[{id:2,status:"sent",receipt_ids:[],can_retry:false,can_operate:true}]`, `can_restart:true`, `restart_policy_id:12`.
- `4306` observation with proof (`has_proof:true`); `4307` 404 for any caller.
- Actuals `GET .../actuals/2026-11`: two rows, one actual with `amount:null`, `more_actuals:true`.
The numbers are the builder's; the shapes are the contract.

### Idempotency, versioning, permission and tenant rules
- Reads send no key and no body. `expected_revision` and `case_revision` from the readback are held for F-103B and passed on as read; `null` stays null, never 0.
- Each read is made as the signed-in person. The page never decides access: group disclosure rows are shown exactly as the API returns them. No request to `payroll`-named routes is made from this page.

## Lanes
- Frontend lane (owner, all of this feature): `frontend/src/features/forecast/**` (new: `forecastAdapter.ts`, `ForecastSections.tsx` if the existing section kinds cannot draw the actuals or disclosure, `useForecastActuals.ts`, `labels.ts`, tests), `frontend/src/api/types.ts` (live forecast types if the generated ones are too loose), `frontend/mock/**` forecast routes and fixtures `4301..4307` (new files; v7 `W-4001..W-4013` fixtures kept), and `frontend/e2e/cash-forecast-live.spec.ts` (new). The v7 `e2e/cash-forecast.spec.ts` stays green.
- Backend lane: none. No backend change; no contract edit.
- Integration owner: lane D coordinator. Shared files and owners: `src/features/workspace/*` (lane C owns the frame and adapter; this feature registers an adapter and adds nothing to the frame; if the actuals month control or the disclosure list needs a new section kind there, that is a dependency on lane C and the builder uses the closest existing kind in the meantime), `src/features/work-item/*` (lane C), `src/api/*` (shared; edits limited to live types), `src/components/*` (used as is).
- Protected paths in `delivery/config.json` (`delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json`) stay unchanged.

## Acceptance criteria
1. Opening `/work/4301` against the mock (Next 4990, mock 4991) shows the forecast header (entity, currency, basis, "As of {date}"), six month rows, and the delivery line "Receipt 9" — verify: open the page; `frontend/e2e/cash-forecast-live.spec.ts` asserts the rows and the receipt text.
2. Against live Django (8030) for a real forecast work id the page shows the same entity, currency, as_of, periods, jobs and matches as `GET /api/v1/work/{id}/forecast` — verify: compare the page with the `curl` JSON and `python3 delivery/connect/oa.py live GET /api/v1/work/{work_id}/forecast 4`.
3. A period with an unknown amount (4301 January closing) reads "Unknown" in the table and in the page text; no 0, no carried-forward opening, and no sum is computed — verify: e2e on 4301; unit test on the period mapper with a missing, null and `"0.00"` amount, which must render as Unknown, Unknown and the zero amount respectively.
4. `result: null` (4303) shows the stage, finding and "No forecast figures yet." with no table, no delivery section and no matched-actuals section other than "No actuals matched yet." — verify: e2e and mapper unit test.
5. `/work/4307` and a live id the account cannot see both show exactly "This record is unavailable."; 401 shows the sign-in link with `next`; 403 `csrf_failed` is not shown as no-access; 409 and 422 show their own wording; a failed forecast read keeps the work item header on screen — verify: mock scenarios plus unit tests on the error mapping.
6. The uncertain state (4305) shows the job status raw, "Outcome not known" when `observation.outcome` is `unknown`, "Restart allowed under rule 12", and the text "Nothing has been resent from this page."; no Retry, Cancel, Record what happened or Resend button exists — verify: e2e on 4305 asserts the texts and the absence of those four buttons.
7. A job with `receipt_ids: []` reads "No receipt yet" and never a tick or "Received" — verify: unit test and e2e on 4305.
8. `observation.has_proof` true (4306) shows a "Proof on file" link whose href is `/api/v1/work/{id}/forecast/observations/{observation.id}`; false shows "No proof on file" and no link; the page does not request that URL while rendering — verify: e2e asserts the href and that the network log has no request to it until clicked.
9. Group disclosure (4304) shows only `selected_rows`, `selected_fields`, `selected_metadata` and recipients as sent; the poisoned variant (a payroll key in `selected_rows`, an item with `staff_name` and `pay`) shows the key text only and draws no staff name and no pay figure anywhere on the page, and no request is made to any payroll route — verify: e2e on the poisoned fixture asserts the DOM text contains neither the staff name nor the pay figure and the request log has no `payroll` URL; unit test on the disclosure mapper drops unknown object fields other than a whitelist (`key`, `label`, `kind`, `amount`, `expected_on`, `original_due`, `commitment`, `residual`, `matched`).
10. A payroll-related assumption appears on a group view only when it is listed in `disclosure.selected_rows` or `selected_fields` of the read; with a null `disclosure` on `audience: 'group'` none appears — verify: unit tests on both inputs.
11. `disclosure.row_keys`, `oracle_choices` and `decision_choices` are drawn as read-only text with no checkbox, select or input in the disclosure section — verify: e2e asserts zero `input`, `select` and `[role=checkbox]` elements inside the disclosure section.
12. Selecting month 2026-11 loads `GET /work/{id}/forecast/actuals/2026-11` once and shows rows, actuals (direction In or Out, Verified or Not verified) and history (Reversed marked); an actual with a null amount reads "Unknown" — verify: e2e and network panel; unit test on the actuals mapper.
13. When `more_actuals`, `more_history` or `more_notes` is true the section says "Showing the first rows only. The rest isn't available here." and no "Show more" control exists; when all are false the sentence is absent — verify: e2e on both fixtures.
14. A month with no rows shows "No actuals recorded for {month}."; a 404 on a month shows "This record is unavailable." and leaves the forecast sections on screen — verify: mock scenarios and e2e.
15. The page sends no write: no `POST`, `PUT`, `PATCH` or `DELETE` is made on any forecast state, and none of Approve, Return, Reject, Withdraw, Post, Record, Match, Leave unmatched, Save, Retry, Cancel appears as a button — verify: e2e records the request methods and the button names on 4301 to 4306; `grep -n "liveApi.POST\|\.POST(" frontend/src/features/forecast` returns nothing.
16. No "reviewer not set" text and no shortened money ("M" suffix) is drawn at 1440 or 390 — verify: e2e text search on 4302 at both widths.
17. A null `expected_revision` or `case_revision` is carried as null and not rendered as 0 — verify: unit test on the adapter's context mapping.
18. The adapter registers under the live panel key and `adapterFor(key)` returns it; a panel key with no adapter still does not break the page — verify: `forecastAdapter.test.ts` and the F-85 unknown-key test stays green.
19. The generated live types for the three reads match contract 1.24.0 and `api-live-schema-drift.test.ts` passes — verify: `npm test`; `delivery/checks.sh`.
20. At 1440 and 390 the page matches the SCR-56 boards for the parts that remain (investigating, review without decide controls, group rows and group review without edit controls, uncertain without recovery controls, verified, actuals without record controls); hidden parts leave no empty heading or gap and the table scrolls only inside its region — verify: screenshots at both widths against the SCR-56 artboards; axe WCAG 2.2 AA has no violations on 4301 to 4305.
21. The v7 forecast pages `W-4001..W-4013` and `e2e/cash-forecast.spec.ts` still pass unchanged while lane C's adapter route is not used for them — verify: run that spec.
22. New tests: unit tests for the section mapper (periods, items, findings, matches, disclosure, delivery), the actuals mapper, and the error mapping; one e2e file for 4301 to 4307 — verify: the files exist and run in `npm test` and `npm run e2e`.

## Out of scope
- Everything F-103B owns: review verdicts (approve, return, reject), withdraw, post; record, match or leave unmatched an actual; `POST forecast/disclosure`, `POST forecast/observations`, `POST forecast/lifecycle`; the evidence picker; any request that sends data.
- Any change to `src/features/workspace` (frame, adapter, sections), `src/features/work-item`, or the generic step engine.
- Building payroll detail, staff names or pay from any other read; offering a payroll row as a selectable field; any call to payroll routes.
- A "reviewer not set" warning; short phone money; counts or attempt numbers the API does not send; paging that the actuals route does not support.
- Previewing the proof file; polling the observation; resending a delivery.
- Backend, migrations, contract edits; `GET /work/{id}/forecast` for non-forecast lines.

## Assumptions
- The forecast panel key on `GET /work/{id}` `panels[]` is not published (A-16). The builder reads it from a live forecast work item and registers the adapter under that exact key; the builder records the key in build.md. Reason: no published list.
- The shapes of `result.periods[]`, `items[]`, `findings[]`, `actuals[]` and the disclosure arrays are untyped. The mapper reads named fields it expects (month, opening, in, out, closing, key, label, amount) defensively and lists any other keys as text; the builder records the real shapes seen on live in build.md and the mock follows them. Reason: E-25 names the contents, not the field names.
- The uncertain state comes from `forecast.observation`, `jobs[]` and `can_restart`, not from the observation route, which returns a file. Reason: the contract shows an octet-stream response for that route (Question 1).
- Stage words are shown as the raw `stage` string, lightly capitalised, with no mapping table. Reason: `stage` is an unconstrained string.
- Month selection uses `?month=YYYY-MM` on `/work/{id}`. Reason: avoids a new route and keeps the shared frame untouched.
- Group-view arrays are filtered to a whitelist of known field names (Acceptance 9). Reason: E-26 excludes staff names and pay from the projection, and the client must not trust its contents as a second guard.
- The page shows no restart or cancel hint beyond the facts above. Reason: what cancelling an uncertain delivery does is an open product question (F-43 spec, gaps `:137`).
- Mock fixture ids 4301 to 4307 are free numbering. Reason: no live fixtures exist.

## Questions
1. **The uncertain delivery state: where does it come from?** `GET .../forecast/observations/{id}` returns the private proof file, not a state. Options: (1, recommended) take the state from `forecast.observation` and `jobs[]`, and link the proof file only; (2) ask the backend for a JSON state route and hold the uncertain board until it exists; (3) fetch and preview the file in the page. Recommendation 1: it is what the contract serves, and it needs no new read. Readiness listed the route as "state", so the coordinator should confirm.
2. **Actuals "more" flags have no paging route.** `more_actuals`, `more_history`, `more_notes` say a list is cut, but the route takes no cursor or limit. Options: (1, recommended) say "Showing the first rows only" and stop; (2) hide the sentence and show nothing; (3) ask the backend for a limit/offset. Recommendation 1: it is honest about missing rows and needs no backend change.
3. **Write controls drawn on the read boards (review Decide panel, group-rows editing, "Record what happened", "Record actuals").** The boards draw them on the same artboards as the read content. Options: (1, recommended) leave them absent in part 1 and add them in F-103B; (2) draw them disabled with "Available in the next release"; (3) draw them as links to F-103B pages. Recommendation 1: a disabled button invites a press that does nothing, and the part 1 merge is a read-only release. This also removes the Decide panel, the group-rows tick boxes, the recovery buttons and the actuals form from what the boards show.
4. **Board parts the API cannot fill (listed for the design engineer).** (a) "Reviewer not set" warning: hide (no field); (b) short phone money: full amounts at every width; (c) the "Forecast reviewer" panel title: not drawn (the decide panel is F-103B); (d) agent steps, the six facts strip and the station track on the review and investigating boards: hidden per LC-Q1 (D-182), so those boards show only header, stage, finding and sections. Recommendation: accept all four as built; the alternative is to hold the investigating board until the backend returns agent steps.

## Conflicts with the boards
- Added: month control for actuals via `?month=` (the actuals board draws a month already in context; no separate control drawn), and the "Showing the first rows only" sentence. Recommendation: keep both; they are the live replacements.
- Removed (part 1 only): Decide panel, Return/Reject note drawer, group-rows tick boxes and "Share with group" button, group-review verdict buttons, "Record what happened", "Record actual" form and match controls, reviewer-not-set warning, compact money. Recommendation: as Questions 3 and 4.
- Station track, six facts, agent card and "Ask Chidi": hidden under LC-Q1. Recommendation: as accepted in D-182.
