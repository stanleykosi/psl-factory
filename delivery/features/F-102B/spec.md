# Fixed assets: record the register, date and schedule reviews, answer a return and correct the register (SCR-55, part 2)

> Tasks: FE-CONNECT-1 (part 2 of SCR-55; the read-only panels are F-102). Architecture: v9 package (`architecture/packages/v9/tasks.csv`); contract `contracts/psl-factory.openapi.json` 1.25.0 or later (lane D worktree `/Users/Hunchoo/psl-factory-worktrees/lane-d`). Design: approved 13 Nov canvas under the recorded exceptions in `design/review.json` (D-173/D-181); screens: SCR-55, 8 of 14 boards in `design/canvas/finance/project/`: `SCR-55-{desktop,mobile}-{register-review,date-review,schedule-review,returned}`.

## Summary
- On line `fixed_assets` (W-3901..W-3912), a finance person decides the register, date and schedule reviews (approve, return, reject, revoke) from the panel F-102 draws, and the basis review appears as a further choice only when the server lists it.
- The same page lets the person capture a register, record unclear dates with a checked PDF proof, and answer a return with a corrected proof (`opening-proof`). All writes are in one `FixedAssetsActions.tsx` registered as the line adapter's `Actions` slot.
- What the person may do comes only from `review_options`, `review_evidence` and `opening_return` in `GET /work/{id}/assets`. The client never decides authority, and the independent-reviewer hold shows as the server returns it.
- Evidence ids come from `review_evidence[]` with nothing preselected; the button stays off when the list is empty. No id is invented.
- **Waits** (build start only, not blockers): F-102 (panels, merged), F-85 (adapter) and F-87 (`Actions` slot, `useWorkCommand`). The spec is written against their specs.

## Context
Lane D worktree `/Users/Hunchoo/psl-factory-worktrees/lane-d/frontend`; merge origin/main (API 1.26.0, after the F-68 hotfix) before the first gate.
- F-102 adds `frontend/src/features/fixed-assets/` (`assetsAdapter.ts`, `line.ts`, panel components). Its adapter returns the `review_options` as text only ("Who may review what", F-102 criterion 8: no controls, no `liveApi.POST`). This feature turns that text into forms and does not rebuild the panels.
- F-85 (`frontend/src/features/workspace/adapter.ts`: `PanelRef`, `LineContext {workId, caseId, revision, caseRevision}`, `LineAdapter`, `CommandDescriptor`, `makeCommand`) and F-87 (`useWorkCommand`, `LineActionsProps = {readback, ctx, commands, reload}`, the optional `Actions` slot). F-89's `WeeklyReportActions.tsx` is the example for a form file.
- Live client: `frontend/src/api/client.ts` (`liveApi`, `call()`), types `frontend/src/api/live-schema.d.ts` (`reviews_review`, `assets_capture`, `assets_record_dates`, `assets_attach_opening`, `assets_detail`). F-85's `uploadCaseFile` exists for uploads into `POST /cases/{case_id}/files`; it is not used here, because each action takes its own file field (below).
- Evidence list: the `review_evidence[{id, version, kind}]` array already in `GET /work/{id}/assets`.
- Backend answers (`delivery/connect/backend-answers.md`): E-23 (register reviews the source register, basis reviews a required justification for the chosen date or calculation basis, schedule reviews the depreciation schedule; `review_options` sets the purpose and target to offer; a separate basis review is used where required), E-24 (link to the accounting note; no note text), and the line at 1415 (kind `schedule` on `/work/{id}/reviews`, exact `target_id`, current revisions, verdict and note; the schema requires `evidence_id`, including for approve).
- Boards (read by the spec writer): register-review (register changes table, "Decide · PPE reviewer", note, Approve register / Return with a note / Reject; "3 assets have unclear dates; they go to a date review next"), date-review (unclear dates table, proof file, Approve dates / Return / Reject), schedule-review (class schedule, "You didn't prepare it", Approve schedule / Return / Reject / Withdraw approval), returned (the returner's quoted note, proof file, "Correct and resubmit").

## Contract
All writes: `X-CSRFToken` from the shared client, as the person signed in. Permission and tenant rule are the server's alone (404 for "not yours" and "missing" alike). Do not pass `expected_revision`, `case_revision` or the idempotency key inside `inputs` to `makeCommand` until TECH-1-1 lands; the descriptor adds them from `readback.expected_revision`, `readback.case_revision`, or `ctx.revision`/`ctx.caseRevision`, taken at the moment of the press. One idempotency key per attempt, reused on a retry of the same attempt, replaced after success or after a change in the form. Where a body has no key field, the guard is the press lock in `useWorkCommand` and the revision tokens.

### 1. Record a review `POST /api/v1/work/{work_id}/reviews` (JSON, 200)
Offered only for an entry of `review_options` (up to 3, each `{target_id, purpose, verdicts[]}`) and only with the verdicts it lists. Nothing is offered when `review_options` is empty (the F-102 line "No review is open for you." stays).
- Purpose `register` or `basis`: body `{kind:'asset', expected_revision, case_revision, target_id, purpose, verdict, evidence_id, note}`.
- Purpose `schedule`: body `{kind:'schedule', expected_revision, case_revision, target_id, verdict, evidence_id, note}` (no `purpose` field; the contract's `schedule` variant forbids it).
- `verdict` is one of `approve|return|reject|revoke`; "Withdraw approval" on the board is `revoke`. It is drawn only when `revoke` is in that option's `verdicts`.
- `evidence_id` is required and is chosen from `review_evidence[].id` (label: kind and version). Nothing is preselected. The verdict buttons stay off while no evidence is chosen or `review_evidence` is empty, with the line "No evidence is available to attach."
- `note` is a string, max 4000. The board says the note is needed to return, reject or withdraw. The form requires a non-empty note for `return`, `reject` and `revoke` and allows an empty note for `approve`; the server stays the final rule.
- Response `{work_id, state, revision, review_id|null}`. On success: re-read the work item and `assets` (`reload`), show "Recorded", clear the form. The review is not shown as "approved" from this response; the re-read panel is what shows it.
- Board mapping: register-review = purpose `register`; schedule-review = purpose `schedule`; date-review = purpose `basis` (assumption 1). Each section's heading is "Review the asset register", "Review the dates", "Review the schedule", taken from the purpose, not from the server.

### 2. Capture a register `POST /api/v1/projects/{case_id}/asset-registers` (JSON, 201)
`case_id` is `ctx.caseId`, never typed. Body `{case_revision, reference, evidence_id}`; `reference` matches `^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$` (checked in the form with the server's message shown on 422); `evidence_id` from `review_evidence[]` as above. Response `{id, reference, version, case_revision}`. On success reload; the new register shows only when the re-read `assets` returns it. Drawn only when the panel has `register: null` or the stage allows (assumption 2).

### 3. Record dates with proof `POST /api/v1/projects/{case_id}/asset-registers/{register_id}/dates` (multipart, 201)
`register_id` is the panel's `register_id`. Fields: `case_revision`, `evidence_id` (from `review_evidence[]`), `asset_id` (string; chosen from the assets F-102 lists as "Date unclear"), `delivery_date` and `in_service_date` (`YYYY-MM-DD`, each optional), `fraction_basis` (`explicit_supplied_fraction` = "Supplied fraction", `reviewed_in_service_date` = "Reviewed in-service date"), `file`. The file is a PDF chosen in this action's own field; the form refuses before sending a file over `PROOF_MAX_BYTES` or a type that is not `application/pdf`, with the server as the final check (413, 415, 422). Content-Type is left to the browser. Response `{id, reference, version, case_revision}`. Date order is not checked on the client beyond the format.

### 4. Answer a return `POST /api/v1/work/{work_id}/assets/opening-proof` (multipart, 201)
Drawn only when `opening_return` is not null. Fields: `expected_revision`, `case_revision`, `target_id` and `review_id` (both from `opening_return`, not editable), `reason` (1 to 2000 characters, required), `file` (checked PDF). Button "Correct and resubmit". Response `{work_id, state, revision, record_id}`. An unchanged correction is refused by the server while the reviewed schedule is current; the 422 message is shown as returned. The existing proof can be opened from `GET /work/{id}/assets/opening-proof` only when `has_opening_attachment` is true.

### Errors (every write)
| Status | Shown |
|---|---|
| 401 | signed-out state, `/sign-in?next=<path>` |
| 403 `csrf_failed` | refresh the session once, "Refresh your session and try again"; no automatic resend |
| 403 other, 404 | "This record is unavailable." (no difference) |
| 409 | re-read panel and item, "This changed while you were working. Showing the latest version."; the press is not repeated; the server message under it when present |
| 422 | `fields[].message` against the field; otherwise `message`; entered values stay |
| 413, 415 | the server's message beside the file field |
| 429, 503, network | "Try again shortly" with Try again; after a network or server failure the form locks (an uncertain write) until the person reloads, as `useWorkCommand` does |

The independent-reviewer hold: when a review option is missing or the server answers 403/422 with a hold message, the message is shown as returned, with no client-side rule about who prepared what.

### Screen states
- Loading: the F-102 panel loading line; the forms are not drawn until `assets` has returned.
- Empty: `review_options` empty and `opening_return` null and no capture offered: no form and no heading; F-102's "No review is open for you." stays.
- Error: as above; the page header stays when only a write fails.
- Success: "Recorded" for one second line under the form, then the re-read panel.
- Phone: the same forms in one column, amounts and buttons full width, as F-102 (Question 3).

### Fixtures (mock, Next 4990 / mock 4991)
Extend F-102's `frontend/mock/` ids; shapes are the contract. `3901` investigating with `review_options:[]` and `register:null` variant `3908` (capture offered); `3911` register review (`review_options:[{target_id:501,purpose:'register',verdicts:['approve','return','reject']}]`, `review_evidence` with 2 entries); `3912` date review (purpose `basis`, three `Date unclear` assets, evidence entries); `3913` schedule review (`purpose:'schedule'`, verdicts include `revoke`, `schedule_review_id` set); `3914` all options with an empty `review_evidence` (buttons off); `3915` returned (`opening_return:{target_id:502,review_id:77}`, `has_opening_attachment:false`); `3916` independent-reviewer hold (a 403 with a hold message on `POST /reviews`); `3917` stale (409 on every write); `3918` 422 on a field. Mock routes for `POST /work/{id}/reviews`, the two multipart posts and `POST /projects/{case_id}/asset-registers`, each recording the body so the e2e can assert it. Example register body: `{"kind":"asset","expected_revision":4,"case_revision":9,"target_id":501,"purpose":"register","verdict":"approve","evidence_id":801,"note":""}`.

## Lanes
- Frontend lane (owner of everything here): `frontend/src/features/fixed-assets/**` (new: `FixedAssetsActions.tsx`, `reviewForm`, `captureForm`, `datesForm`, `openingProofForm`, a small multipart sender, commands in the adapter, tests), `assetsAdapter.ts` (F-102's, only to add `commands` and register `Actions`; its read mapping and panels stay), `frontend/mock/**` fixtures and routes above, `frontend/e2e/fixed-assets-reviews.spec.ts`.
- Backend lane: none. No backend change, no migrations, no contract edits.
- Integration owner: lane D coordinator. Shared files: `frontend/src/features/workspace/**` (lane C owns, F-87 adds `useWorkCommand` and the `Actions` slot; read-only here; a needed frame change is a named dependency on lane C), `frontend/src/api/*` and `frontend/src/components/*` (shared; generated types only). Any change under `frontend/mock/finance*` or the payments fixtures is named in `build.md` for lane B.
- `delivery/checks.sh`, `delivery/config.json` and `delivery/merge-policy.json` are protected and unchanged.

## Acceptance criteria
1. On mock `3911` the register review form shows the purpose heading, an evidence list from `review_evidence` with nothing selected, a note and only the verdicts listed; Approve, Return and Reject are off until evidence is chosen — verify: open `http://localhost:4990/work/3911`; `frontend/e2e/fixed-assets-reviews.spec.ts` asserts the disabled state and the choices.
2. Approve on `3911` sends one `POST /api/v1/work/3911/reviews` with `kind:'asset'`, `purpose:'register'`, the option's `target_id`, the chosen `evidence_id`, `expected_revision` and `case_revision` from the read, and an empty note allowed; afterwards the panel is re-read — verify: e2e inspects the recorded body and the follow-up GETs.
3. A schedule review on `3913` sends `kind:'schedule'` with no `purpose` field; `revoke` ("Withdraw approval") appears only when `revoke` is in that option's `verdicts` and is absent on `3911` — verify: e2e body and button assertions; unit test on the body builder.
4. Return, Reject and Withdraw with an empty note are refused in the form before sending; Approve with an empty note is sent — verify: unit test and e2e (no request on the refused cases).
5. A `basis` option (`3912`) draws "Review the dates" and is absent when `review_options` has no `basis` entry; no option is drawn that the server did not list — verify: e2e on `3912` and `3911`; unit test mapping `review_options` to forms.
6. With `review_options: []` (`3901`, `3904`) no review form, heading or empty gap is drawn and "No review is open for you." remains; with `review_evidence: []` (`3914`) the verdict buttons are off with "No evidence is available to attach." — verify: e2e.
7. No evidence id appears in any request unless the person chose it; `grep -rn "fileToEvidence" frontend/src/features/fixed-assets` returns nothing — verify: e2e asserts the chosen id in the body; grep.
8. A 403 hold message on `3916` shows as returned, the form stays and no automatic retry is sent; the client holds no "preparer cannot review" rule — verify: e2e counts requests; `grep -rn "prepared by\|preparer" frontend/src/features/fixed-assets` returns nothing.
9. Capture a register on `3908` sends `POST /api/v1/projects/{ctx.caseId}/asset-registers` with `case_revision`, `reference`, `evidence_id`; an invalid reference (`-x`) is shown as the 422 field message and sent only if it matched the pattern client-side or the server answered; there is no input for a case id — verify: unit test on the body and the pattern; component test on props.
10. Record dates on `3912` sends one multipart `POST .../asset-registers/{register_id}/dates` with `case_revision`, `evidence_id`, `asset_id` (one of the "Date unclear" assets), the dates, `fraction_basis` and a `file` part, with no hand-set Content-Type; a non-PDF or a file over the limit is refused before sending, a mock 413 and 415 show the server message — verify: e2e on request headers and body parts; unit tests.
11. Correct and resubmit on `3915` sends multipart `POST /work/3915/assets/opening-proof` with `expected_revision`, `case_revision`, the `target_id` and `review_id` from `opening_return` (not editable), `reason` and `file`; an empty reason or no file keeps the button off; with `opening_return: null` the control is absent — verify: e2e and unit test.
12. 409 on `3917` re-reads the panel and item, says "This changed while you were working. Showing the latest version.", and does not repeat the press; 422 on `3918` shows the field message and keeps the entered values — verify: e2e counting requests.
13. A 403 `csrf_failed` refreshes the session once, says to press again and does not resend by itself; a 403 other or 404 shows "This record is unavailable." with no difference; 429, 503 and a dropped network show "Try again shortly" and lock the form until reload or Try again — verify: mock scenarios; unit tests count fetches.
14. Pressing a verdict twice quickly sends one request; a retry of the same attempt reuses the same idempotency key where the body has one, and a new attempt after success gets a new one — verify: unit test on the lock and key.
15. No write happens on page load, polling or navigation; `grep -rn "liveApi.POST\|fetch(" frontend/src/features/fixed-assets` shows calls only in the forms' send functions — verify: e2e asserts zero POSTs on load; grep.
16. `FixedAssetsActions` is registered through F-87's `Actions` slot and renders inside its error boundary; `git diff` shows no change under `frontend/src/features/workspace/`; the F-102 panels and mapper tests are unchanged and still pass — verify: `git diff --stat`; `npm test`.
17. Against live Django (8030) with a finance reviewer account: the listed `review_options` produce a `POST /reviews` that returns 200 and a changed `review_id`, and a second account without access gets 404 on the work item and on every write and sees "This record is unavailable." — verify: `python3 /Users/Hunchoo/psl-factory-main/delivery/connect/oa.py live GET /api/v1/work/{work_id}/assets 3` before and after; the session `curl` JSON for the write. If no live case is in a review state, say so in `build.md` and list the mock result only; do not claim live evidence.
18. A schedule with a held status, or any null money field, never shows 0 in the new forms; money stays as F-102 draws it — verify: e2e on `3903`-style fixture with the forms present.
19. The drawn parts the API does not supply are absent and listed in the PR: "Chidi never reads asset values", the accounting-note text, the phone short money form, the review dates (including the returner's quoted note on the returned board), "Feeds MANAGEMENT ACCOUNTS" — verify: `grep -rn "never reads asset values\|MANAGEMENT ACCOUNTS" frontend/src/features/fixed-assets` returns nothing.
20. Viewport check at 1440 and 390 against the eight boards (`SCR-55-{desktop,mobile}-{register-review,date-review,schedule-review,returned}`): frame, decide card, note field, buttons and proof row match, and hidden parts leave no empty heading or gap — verify: screenshots at both widths reviewed against `design/screens.md` SCR-55.
21. Tests exist and pass: unit tests for the review body builder (asset and schedule variants, notes rule), option-to-form mapping, the multipart builders, the locking and the error mapping; `npm run lint`, `npm run typecheck`, `npm test` and `delivery/checks.sh` pass — verify: command output.

## Out of scope
Anything in F-102's read scope; changing the shared workspace frame (a needed change is a named dependency on lane C); ledger posting (`ledger_posted` is read-only); client-side sums, depreciation or date calculations; exporting the schedule; the accounting-note text; uploading to `POST /cases/{case_id}/files` or F-85's `fileToEvidence`; any control the server did not list in `review_options` or `opening_return`; any client rule about who prepared or may review; "Chidi never reads asset values", the phone short money form, review dates and "Feeds MANAGEMENT ACCOUNTS"; starting a case (F-102); backend, migrations and contract edits; the v7 `W-39xx` fixtures.

## Assumptions
1. The date-review board is the `basis` purpose. Reason: E-23 says basis reviews a justification for the chosen date or calculation basis, and the board approves "explained dates"; if live lists `basis` for something else the builder maps by `purpose` and reports it.
2. The capture control is drawn when the panel has `register: null` and the person has at least one `review_evidence` entry. Reason: the API has no flag saying who may capture; the server is the final check (403/404). No board draws it, so it is a plain form under the empty-register line.
3. `schedule` reviews use `kind:'schedule'` and register/basis use `kind:'asset'`. Reason: the 1.25.0 contract's two variants and the backend answer at line 1415.
4. For the dates form the proof's `evidence_id` is chosen from `review_evidence[]`, and the PDF goes in the action's own `file` field. Reason: the proof rule (PSL answer 1, D-1); the list is the only evidence the line read supplies.
5. A note is required in the form for return, reject and revoke only. Reason: the board says so; the schema only caps length.
6. Multipart posts use a small sender in this feature built on the shared client's CSRF handling, with the same lock and error mapping as `useWorkCommand`. Reason: F-87 describes JSON commands; the contract has multipart on two of the four writes (Question 4).
7. The returned board's quoted note from the returner is not drawn. Reason: `assets` carries no note text.

## Questions
1. The review form shows the basis review as a further choice beside register and schedule, only when `review_options` lists it. Options: (a) as written (recommended; E-23); (b) hide the basis review until the design engineer draws it.
2. One shared evidence picker (a select labelled by kind and version) for the review, capture and dates forms. Options: (a) one shared control (recommended; the list is the same); (b) a separate picker per form.
3. Phone shows the same forms in one column, as F-102. Options: (a) as written (recommended); (b) follow the phone boards exactly and drop the register and dates tables from the phone review sections.
4. F-87's `useWorkCommand` may be JSON-only. Options: (a) this feature sends its two multipart posts through its own sender, reusing the lock and error mapping (recommended; no frame change); (b) wait for lane C to add multipart to `useWorkCommand`.

## Conflicts with the boards
- Added: an evidence picker on every review (the boards show only a note; the API requires `evidence_id`, including for approve). Recommendation: keep; it is the proof rule. Design engineer decides before the build starts.
- Added: the basis review as a third decision, and a "capture a register" form, neither drawn. Recommendation: keep both as plain forms (Questions 1; Assumption 2).
- Added: a dates form (asset, delivery date, in-service date, fraction basis) on the date-review board, which draws only a read table, the proof and the decision. Recommendation: keep; the write needs these fields.
- Removed: the returned board's quoted returner note, "Chidi never reads asset values", the short money form, review dates and "Feeds MANAGEMENT ACCOUNTS" (D-182). Recommendation: hide.
- Changed: "Withdraw approval" shows only when `revoke` is listed (the board draws it unconditionally on the schedule review). Recommendation: keep the server's rule.
- Changed: phone shows the full forms in one column (Question 3).
