# Log a received RFP and assign its accountable PM through the live API

> Tasks: FE-CONNECT-1. Architecture: v9 (contract 1.22.0, `contracts/psl-factory.openapi.json`; manifest digest not re-verified by the spec writer, readiness did not check it either). Design: 13 Nov approval under the recorded exception in `design/review.json`; screens: SCR-23, SCR-24.

## Summary
- SCR-23: the Start work drawer line `rfp_intake` logs a received RFP with one multipart `POST /received-bids`, the client chosen from `GET /received-bids/organisations`, and confirms by reading the receipt.
- SCR-24: the Assign PM drawer over the Unassigned list reads `GET /received-bids/assignments` and `GET /received-bids/{case_id}/assignment`, and assigns with `POST /received-bids/{case_id}/assignment`. "Assigned" shows only after a re-read.
- Three visible changes from the approved boards, all forced by the live contract: proof and reason are required, the Note has no home, and success words carry no "what happens next" lines (see Conflicts with the boards).
- Frontend only. No backend change. Sizing: one PR; if the work spreads beyond the two forms and five calls, split SCR-24 into its own PR.
- Builds after F-85 (shared evidence picker and per-line adapter) and F-86 (Start work first slice, which also edits `src/features/start-work`).

## Context
Both screens exist and run on the v7 mock.
- SCR-23: `frontend/src/features/start-work/` (`LineForm.tsx`, `IntakeField.tsx`, `useStartWork.ts`, `intake.ts`, `labels.ts`; line `rfp_intake`, label "Log RFP"); mock `frontend/mock/start-work.mjs`. Today the form is drawn from `GET /lines` fields and starts with `POST /work`, using the base64 evidence upload and `case_id`/`case_revision`.
- SCR-24: `frontend/src/features/rfp/AssignPmDrawer.tsx` (copy in `ASSIGN_PM_TEXT`), `rfp/proposals.ts`, `workspace/AssignForm.tsx` (shared with other workspace lines, so do not change its other callers), `workspace/useWorkspaceAssign.ts` (posts v7 `/work/{id}/assignment`). It reads `assign.candidates` from `GET /work/{id}`; live has none of that.
- All paths are relative to `frontend/`. The generated API types are `src/api/schema.ts`; regenerate or extend them from 1.22.0 for the five operations below if they are still v7.
- Ids: live `case_id` is a uuid, `intake_id`, `receipt_id`, nominee, proof and person ids are integers. Lines are keyed by `case_id`, not `work_id` (DC-1, DC-2).
- F-85 spec (`delivery/features/F-85/spec.md`) did not exist when this was written. Use the F-85 shared evidence picker by its exported name if it can choose from a supplied list; do not create a second picker. If F-85 lands only an uploader, SCR-24 renders `proofs[]` through the existing `Select` from `@/components`. SCR-24 never uploads (see Assumptions).

## Contract

### SCR-23, Log a received RFP
Reads and writes (all under `/api/v1`):

| Step | Call | Notes |
|---|---|---|
| Client picker | `GET /received-bids/organisations` -> `{items:[{id:int, organisation:string}]}` | The chosen `id` is sent as `authority`. Empty list: say "You can't log a received RFP for any organisation yet." and disable submit. |
| Log | `POST /received-bids`, `multipart/form-data`, header `X-CSRFToken` | Fields: `authority` (int, required), `start_key` (uuid, required), `reference` (1-160, required), `received_at` (date-time, required), `deadline_status` (`unknown`\|`stated`\|`not_stated`, required), `deadline_at` (date-time; required when `stated`, else omit), `prospect_name` (1-160, optional), `submission_method` (`email`\|`portal`\|`by_hand`\|`not_stated`), `submission_target` (non-empty), `context_attested` (boolean), `document` (file, Word or PDF, at most 5 MiB, required). Response 200 `{receipt_id, case_id, django_url}`. |
| Confirm | `GET /received-bids/{case_id}/receipts/{receipt_id}` | Read `reference`, `received_at`, `deadline_status`, `deadline_at`, `customer_instructions`, `original{filename,bytes}`, `number`, `current`. |

Rules:
- Do not call `GET /lines`, `GET /lines/{line}/fields/*/options`, `POST /work` or the base64 evidence upload for this line. The form's fields are fixed in the frontend for `rfp_intake`; other lines in F-86's Start work are unchanged.
- `start_key` is one uuid generated when the drawer opens (`newIdempotencyKey` in `useStartWork.ts`) and reused on every resend of the same form. It changes only after a confirmed success or when the person changes a field after a failure that said nothing was recorded.
- After a timeout, 5xx or network failure the person gets "Check again", which resends the same body and the same `start_key`. It never silently creates a second RFP. If the status is unknown the words are "Not confirmed. Check before trying again." (as for other Start work lines).
- `definition` is deprecated and optional: do not send it. `context_attested` is sent as the contract's own wording only if the form carries a checkbox. The form shows one checkbox labelled with the contract's description wording in a plain sentence: "I confirm the details above match the RFP we received." sent as `context_attested`; it is required before submit. Flagged under Assumptions (C-8).
- The file travels in the POST. Show the file name and size; reject over 5 MiB or a non Word/PDF type before sending; a 413 or 415 from the server shows the same words.
- Success: "RFP logged." with the reference and received time read back from the receipt, the file name, and a link "Open Unassigned" to `/work` (Unassigned list). No work id is shown or invented (C-7). If the receipt read fails after a 200, show "RFP logged. We couldn't read the receipt back." with the `receipt_id` kept for a retry of the read only (never a resend of the POST).
- Errors by status: 401 signed out (existing `SignedOutState`); 403 "You can't log RFPs for this organisation."; 409 or 422 on `reference` show the API's own `code` and `message` and map `fields[].name` to the field (C-11, nothing invented); 413 "The file is larger than 5 MB."; 415 "Use a Word or PDF file."; 429 "Too many tries. Wait a moment."; 5xx or network: uncertain, as above.

Screen states: loading (picker loading), empty (no organisations), validation (required-field summary using `ValidationSummary`), submitting (button busy, one write at a time via the existing synchronous guard), error, uncertain, success.

Fixture example (mock, `frontend/mock/start-work.mjs` plus a new `frontend/mock/received-bids.mjs`):
- organisations `{items:[{id:11,organisation:"Northwind Bank"},{id:12,organisation:"Harbour Insurance"}]}`
- POST ok `{receipt_id:501,case_id:"2f0c8a54-6b0e-4f7a-9d1a-0c5b2f6f1a11",django_url:"/received-bids/501/"}`
- duplicate reference: `409 {code:"duplicate_reference",message:"This reference has already been logged.",fields:[{name:"reference",message:"Already logged"}]}`. This code is a mock invention for the mock only; the screen must show whatever `code`/`message` come back.

### SCR-24, Assign the accountable PM
| Step | Call | Notes |
|---|---|---|
| Unassigned list | `GET /received-bids/assignments?cursor=` -> `{items:[{case_id,intake_id,revision,reference,received_at,deadline_status,deadline,owner_access_required}] (max 12), cursor, checked}` | The row key is `case_id`. Rows with `owner_access_required: true` show "You need access to this RFP's owner first" and no Assign button. "Load more" while `cursor` is non-null. The Unassigned queue of `GET /work?queue=unassigned` is not used for these rows. |
| Drawer read | `GET /received-bids/{case_id}/assignment` -> `{bid, setup_required, assignment, roles[], nominees[{id,label}], proofs[{id,label}]}` | Opened on a row press. |
| Assign | `POST /received-bids/{case_id}/assignment`, JSON, `X-CSRFToken`: `{intake, revision, candidate, role, evidence, reason}` -> 201 `{id, person_id, role, intake_id}` | `intake` = `bid.intake_id`, `revision` = `bid.revision`, `candidate` = a `nominees[].id`, `role` one of `roles[]`, `evidence` one of `proofs[].id`, `reason` 1-4000 chars. |

Rules:
- Drawer fields: "Accountable PM" (Select of `nominees[].label`, nothing preselected), "You are assigning as" (Select of `roles[]`; shown as plain text when exactly one), "Proof" (required, chosen from `proofs[].label`), "Reason for choosing this PM" (required text, 4000 limit with a counter). Nothing is filtered or chosen by the frontend; the backend names who may be chosen. The nominee's role and hint are not shown (C-13).
- `setup_required: true` shows "Nobody is set up to assign yet. Ask a PSL admin to finish setup." (plain words, no jargon) and no form. No nominees, with `setup_required: false`: "No one can be chosen for this RFP yet."
- An existing `assignment` (non-null) shows "Already assigned" with the nominee label when `person_id` is in `nominees`, else "Assigned to another person", and no form.
- The POST has no idempotency key. One write at a time (existing `writing` ref guard). On 5xx, timeout or network failure the drawer first re-reads `GET …/assignment`; it offers the form again only if `assignment` is still null, otherwise shows the "Already assigned" state. It never resends automatically.
- Success words appear only after the re-read of the assignment AND the list: "PM assigned: <nominee label chosen>." The row leaves the list only if the re-read list no longer has it; the screen does not assume it will (C-14). No "alerted" or "what happens next" sentence.
- Errors: 401 signed-out state; 403 "You can't assign a PM for this RFP."; 404 "This RFP isn't available." with the list kept; 409 (stale revision or already assigned) "This changed while you were working." and re-read, showing the new state; 422 map `fields[].name` (`candidate`, `role`, `evidence`, `reason`) to the field with the API's message; 413/415/429 as for SCR-23 where relevant; other: "We couldn't confirm the PM was assigned. Check before trying again." using the existing unconfirmed copy.

Screen states: list loading, empty ("Nothing is waiting for a PM."), list error, drawer loading, drawer error, setup required, no nominees, already assigned, form, submitting, validation, uncertain, success.

Fixture example (mock): list item `{case_id:"2f0c8a54-6b0e-4f7a-9d1a-0c5b2f6f1a11",intake_id:77,revision:3,reference:"RFP-2026-041",received_at:"2026-11-20T09:30:00Z",deadline_status:"stated",deadline:"2026-12-05T17:00:00Z",owner_access_required:false}`; assignment read `{bid:{...},setup_required:false,assignment:null,roles:["Head of PMO"],nominees:[{id:301,label:"Amara Okoye"}],proofs:[{id:901,label:"Delegation email, 18 Nov"}]}`. Fixtures also for `setup_required:true`, an existing assignment, an empty list and a 409. The `roles` value is fixture text only, not a PSL role.

Both screens: Django 8020 against Postgres 127.0.0.1:55433; Next 4980; mock 4981 (this feature's ports).

## Lanes
- Frontend lane owns: `src/features/start-work/*` (the `rfp_intake` path only, additive to F-86's work), `src/features/rfp/AssignPmDrawer.tsx`, `src/features/rfp/proposals.ts`, a new `src/features/rfp/receivedBids.ts` (typed client and hooks for the five calls), `src/features/workspace/AssignForm.tsx` and `useWorkspaceAssign.ts` (changes must keep other callers working; prefer a new hook `useReceivedBidAssign` and leave `useWorkspaceAssign` untouched), `frontend/mock/received-bids.mjs` and fixtures, and tests beside them.
- Backend lane: none. Backend questions go to `delivery/connect/backend-questions.md` (LC-3 to LC-5).
- Integration owner: the lane C coordinator owns the shared files `src/api/schema.ts`, the F-85 evidence picker and adapter in `src/features/workspace`, and the merge order F-85, F-86, F-88.
- Protected paths in `delivery/config.json` stay unchanged.

## Acceptance criteria
1. Opening Log RFP loads the client list from `GET /received-bids/organisations` and offers exactly those organisations — verify: open `/work`, Start work, Log RFP against the mock on 4981 (and Django 8020); the picker lists the two fixture organisations; network log shows no `GET /lines`.
2. A valid submit sends one `POST /received-bids` as `multipart/form-data` with `authority`, `start_key`, `reference`, `received_at`, `deadline_status`, `document`, with no `definition`, then one `GET …/receipts/{id}`, and shows "RFP logged." with the reference — verify: network log; test in `useStartWork` or the new `receivedBids` test asserting the form-data keys.
3. `deadline_at` is sent only when the status is `stated` and is required then — verify: unit test; with "stated" and no date the form shows a field error and sends nothing.
4. A failed or uncertain POST, then "Check again", sends the same `start_key` and body, and never two different keys for one form — verify: test that fails the first POST with a 503 and compares the two requests.
5. A file over 5 MiB or not Word/PDF is refused before sending with plain words; a 413 and a 415 from the server show the same words — verify: test with a 6 MiB file and a `.png`; mock fixtures for 413/415.
6. A duplicate reference shows the API's own `code`/`message` against the Reference field and logs nothing new — verify: mock 409 fixture; the page shows the field message and one POST was made.
7. The form has no Note field, and the success words name no work item or id — verify: open the drawer; no Note; success shows reference, time, file name.
8. A person with no organisations sees the empty state and a disabled submit; a 403 shows "You can't log RFPs for this organisation." and nothing else changes (wrong user / wrong tenant) — verify: mock persona with `{items:[]}`, and a 403 fixture.
9. The Unassigned list reads `GET /received-bids/assignments`, keyed by `case_id`, pages with `cursor`, and shows no Assign button on rows with `owner_access_required: true` — verify: mock list with 13 items over two pages and one restricted row.
10. The drawer shows nominees, roles and proofs exactly as served, preselects nothing, and requires candidate, role, proof and a non-empty reason before sending — verify: submit empty: summary names all four and no POST is sent; test.
11. Submit sends one JSON POST `{intake, revision, candidate, role, evidence, reason}` with integer ids taken from the read, and "PM assigned: <name>" appears only after the assignment and list are re-read — verify: network log order POST, GET assignment, GET assignments; test that the success text is absent until the re-reads resolve.
12. A 5xx or network failure on assign re-reads first and never resends; if `assignment` is now present the drawer shows "Already assigned" — verify: test with a mock that fails the POST but stores the assignment.
13. A 409 shows "This changed while you were working." and shows the re-read state; a 403 and a 404 show their own plain words; a 422 maps `reason` and `evidence` to their fields — verify: mock fixtures and tests.
14. `setup_required: true` shows the plain setup message with no form; no nominees shows "No one can be chosen for this RFP yet." — verify: mock fixtures.
15. The drawer shows no nominee role, no "What happens next" and no "(optional)" on Proof, and the Note is replaced by the required Reason — verify: open the drawer in the mock; file content of `ASSIGN_PM_TEXT` has no `nextHead`/`next`.
16. A signed-out person on either screen gets the existing signed-out state, not an error — verify: mock 401.
17. The v7 paths `POST /work`, `POST /work/{id}/assignment` and the base64 `POST /cases/{id}/evidence` are no longer called from these two screens — verify: `grep` in `src/features/start-work` (rfp_intake path) and `src/features/rfp/AssignPmDrawer.tsx`; network log.
18. Keyboard and accessibility: focus moves to the error callout on failure and to the success message on success; every field has a label — verify: the existing drawer a11y tests extended, and a manual tab through both drawers.
19. Add tests for each of the above where testable (the five operations in a mocked client, the two drawers with the mock); the existing `AssignForm` callers (other workspace lines) still pass their tests — verify: `delivery/checks.sh` passes and the AssignForm tests are unchanged and green.

## Out of scope
- Backend changes, new roles, approvers or business rules; deciding who may assign (the backend names nominees).
- Any other screen, including SCR-25 onward and SCR-16; the generic `GET /lines` path for other lines (F-86); the answer to C-2 (how an uploaded file becomes an evidence id); uploading proof inside the Assign drawer.
- Opening the new work item from the success message (no `work_id` returned); finding it in `GET /work?queue=unassigned` (C-7) is not built.
- Showing the PM's role, hint, the "what happens next" lines, "alerted" claims, or any value the API does not serve.
- Editing or re-logging a received RFP, versions and download of the original file, listing earlier receipts.
- Notes about the RFP (the Note field is removed, not stored elsewhere).

## Assumptions
- The Assign proof is chosen from `proofs[]` only (the read lists the allowed ones); no upload in this feature. Reason: the API gives integer ids for existing proofs, and the file-to-evidence path (C-2) is unanswered.
- "Proof" label stays "Proof" and the new field label is "Reason for choosing this PM". Reason: need words for a required reason; the design had "Note".
- The `context_attested` checkbox wording "I confirm the details above match the RFP we received." Reason: the contract gives no label (C-8); the client should confirm the wording.
- `prospect_name` is free text, optional, labelled "Client name as written in the RFP" (LC-Q8 option 1). Reason: C-9 unanswered.
- Success after logging is read back from the receipt; the new item is not looked up in the Unassigned queue. Reason: C-7 unanswered.
- Repeat-reference behaviour is shown from whatever status and `code` the server returns (C-11).
- Size and type limits (5 MiB, Word or PDF) come from the OpenAPI field description for `document`.
- Row-level "needs access" wording for `owner_access_required` is frontend copy only.

## Conflicts with the boards
- SCR-23 Log RFP: the board draws a Note field and a client picked by name. This spec removes the Note, adds the required "I confirm" checkbox and a client-name text field, and makes the picker an organisation delegation. Recommendation: accept (LC-Q8 option 1, LC-Q7 option 1 for the pair).
- SCR-23: the board's success sentence opens or names the new work item. This spec shows the receipt and a link to the list. Recommendation: accept (LC-Q9 option 1).
- SCR-24 Assign PM: the board draws Proof as optional, an optional Note, the nominee role/hint and the "What happens next" block. This spec makes Proof required, replaces Note with a required Reason, drops role/hint and the next-steps block, and adds the setup-required and already-assigned states. Recommendation: accept the required proof and reason (LC-Q7 option 1); the new states need a board for the design engineer.
- SCR-24 list: rows gain a "needs access" state (`owner_access_required`) and "Load more", neither drawn. Recommendation: accept, small additions that follow the board's row style.
- Questions appended to `delivery/connect/questions-batch.md` as LC-Q7, LC-Q8, LC-Q9 and to `delivery/connect/backend-questions.md` as LC-3, LC-4, LC-5.
