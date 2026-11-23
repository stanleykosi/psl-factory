# A Finance person reads a ledger source's incumbent reference, records what they found with proof, and an independent reviewer approves or rejects it, live

> Tasks: FE-CONNECT-1. Architecture: v9 package (revision as pinned in the feature record at branch time); contract `contracts/psl-factory.openapi.json` 1.24.0. Design: approved 13 Nov canvas under the recorded exceptions in `design/review.json`; screens: SCR-58 part 1 (states investigating, observe, review, rejected, verified; the duplicate state is F-104B).

## Summary
- `/work/{id}` for a ledger source (line `ledger_sources`) draws a "Ledger source" panel from the live `GET /work/{work_id}/incumbent-reference`: the source being referenced, what was observed in QuickBooks, the review, and the verified result. It replaces the v7 `workspace` sections and steps for this line.
- A person who `can_observe` records what they found (Found, Not found, Unknown, More than one) with a PNG or PDF proof. One press makes the observation evidence, then sends the proof as multipart.
- A person with `review_options` approves or rejects with a reason and one chosen evidence item. The latest decision shows its reviewer and date (E-29). When the independent-reviewer rule blocks the person, the panel shows the stable hold code as plain words and no buttons.
- Everything the API does not supply is hidden, not faked (D-182): station track, Chidi's steps and "Ask Chidi", who captured and who observed, the lineage row, the treatment name, the completeness row, the month-end link, "refused, nothing was posted". No amount is shown anywhere.
- Duplicate and reference-correction resolutions, `incumbent-resolutions`, recheck and restart, and the lineage display are F-104B. Waits for F-85 (shared adapter) and F-87 (`useWorkCommand`) to be on main; the coordinator holds the builder until then.

## Context
Where this lives today (lane D worktree `/Users/Hunchoo/psl-factory-worktrees/lane-d/frontend`, origin/main b8542c79, API 1.24.0). Paths marked (F-85) or (F-87) arrive when those merge.
- Work item page: `src/features/work-item/` (v7 today). The live page `src/features/work-item/live/LiveWorkItemView.tsx` and `PanelView` (F-85) draw `panels[]` through `adapterFor(key)`. The adapter contract (`PanelRef`, `LineContext`, `LineAdapter`, `CommandDescriptor`, `registerLineAdapter`, `adapterFor`, `makeCommand`) is in `delivery/features/F-85/spec.md` and lives at `src/features/workspace/adapter.ts`. `useWorkCommand` (press lock, uncertain lock, csrf, 409 re-read) is F-87's `src/features/workspace/useWorkCommand.ts`.
- v7 built SCR-58 as fixtures `mock/fixtures/work/W-4201` to `W-4213` (F-45), drawn by `src/features/workspace/Workspace.tsx`, `StepForm.tsx` and `InlineDecide.tsx` from `item.workspace`. Those stay for `W-xxxx` ids and are not touched.
- Shared UI to reuse by name: `src/components/FileUpload.tsx` (`PROOF_TYPES`, `PROOF_MAX_BYTES`, `FileState`), `Button`, `Callout`, `Select`, `Tag`, the section kinds in `src/features/workspace/labels.ts` (`Section`, `Item`, `Cell`), `Sections.tsx`. `src/api/client.ts` (`liveApi`, `call`, `refreshSession`) and `src/api/errors.ts` (`ApiError`, kinds).
- Start work already names the line: `src/features/start-work/labels.ts:18` (`ledger_sources: 'Record source'`) and `mock/start-work.mjs:52`.
- Live operations (viewer: `python3 /Users/Hunchoo/psl-factory-main/delivery/connect/oa.py live <METHOD> <path> 3`):
  - `GET /api/v1/work/{work_id}/incumbent-reference` (`ledger_detail`).
  - `POST /api/v1/work/{work_id}/incumbent-reference` (`ledger_command`): observe, review, recheck/restart (the last is F-104B).
  - `POST /api/v1/work/{work_id}/incumbent-reference/observations` (`ledger_observe_file`, multipart), `GET .../observations/{check_id}` (`ledger_observation_file`, download).
  - `POST /api/v1/projects/{case_id}/incumbent-evidence` (`ledger_evidence`).
  - `POST /api/v1/work` (`intake_start`, `finance-ledger/v1`, `intake {evidence_id, predecessor_id}`).

## Contract

### Read: `GET /api/v1/work/{work_id}/incumbent-reference` -> 200
Required fields (all present on every 200): `expected_revision` int, `case_revision` int, `stage` string, `finding` string, `source_id` int, `source{provider:"quickbooks", realm, entity, source_reference, transaction_date, accounting_period "YYYY-MM", treatment_evidence_id, incumbent_user_reference, posting_evidence_id, target_reference string|null, outcome "reported_posted"|"uncertain", provenance[{kind,id}]}`, `lineage_id|null`, `predecessor_id|null`, `conflict_id|null`, `check_id|null`, `observation|null {provider, realm, entity, source_reference, target_reference|null, state "found"|"not_found"|"unknown"|"multiple", observed_at, transaction_date, accounting_period, treatment_evidence_id, incumbent_version|null}`, `latest_decision|null {id, verdict "approve"|"reject", reason|null, reviewer, at}`, `review_hold_code "independent_reviewer_required"|null`, `review_options[] ("approve"|"reject")`, `can_observe` bool, `has_attachment` bool, `verification_evidence[{id,version,kind}]` (max 30), `review_evidence[{id,version,kind}]` (max 30), `verified|null {lineage_id, source, check_id, review_id, incumbent, verification_mode:"supplied_read_only", native_authenticity_verified:false, posting_performed:false}`.
- Errors: 401 signed-out state; 403 `forbidden` no-access, 403 `csrf_failed` is not no-access (refresh the session, "Refresh your session and try again"); 404 shows "This record is unavailable." (same for missing and not yours); 409, 422 show the server message; 429 and 503 "Try again shortly."; network "We couldn't reach the server." Reads may be retried (Try again); the panel keeps the last good read on a failed re-read.
- Permission and tenant rule: every read is as the signed-in person; no client role check decides anything. Controls come only from `can_observe`, `review_options` and `review_hold_code`.
- The panel is reached through `GET /work/{id}` `panels[]`. Registered adapter key: `incumbent-reference` (the panel key is the route's last segment; the builder confirms the live `panels[].key` against a real Finance work item and uses it; the URL suffix `/incumbent-reference` is the fallback match).

### Mapping to the screen (adapter `ledgerSourceAdapter`)
Sections and rows drawn, with the source of each:
| Part | Source | Rule |
|---|---|---|
| Header facts: provider, reference | `source.provider` ("QuickBooks"), `source.source_reference` | title and sample tag come from the work item (F-85) |
| Where we are | `finding` (as given), small label `stage` as given | no words invented; empty string draws nothing |
| Source rows | `realm`, `entity`, `transaction_date`, `accounting_period`, `incumbent_user_reference`, `target_reference` (null -> "Not recorded"), `outcome` ("Reported as posted" / "Uncertain") | no amount, no treatment name (only `treatment_evidence_id` exists), no provenance ids |
| What was observed | present only when `observation` is not null: `state` ("Found", "Not found", "Unknown", "More than one"), `observed_at`, `target_reference`, `incumbent_version` (null -> "Not recorded"); "Proof attached" link to `GET .../observations/{check_id}` only when `has_attachment` and `check_id` are set | the link downloads through the browser with the session; no preview |
| Review | `latest_decision` when not null: "{reviewer} approved it" or "{reviewer} rejected it: "{reason}"" and the date from `at` (reason null draws no quote) | the reviewer and date are E-29; nothing derived |
| Hold | `review_hold_code === "independent_reviewer_required"` -> "Someone who didn't capture or observe this source has to review it." Any other code is drawn as the raw code in a plain line | no buttons while the code is set |
| Verified | `verified` not null: "Posting performed" `NO` from `posting_performed:false`, "Authenticity certified" `NO` from `native_authenticity_verified:false`, "Reference recorded" `YES` with the date from `latest_decision.at` when its verdict is approve (else no date) | a value that is not `false` is drawn as "Not recorded", never as NO; no "Completeness" row, no re-check sentence |
| Not drawn | station track, Chidi card and steps, "Ask Chidi", captured by, observed by, lineage row, treatment name, completeness row, started time, provenance, `verification_evidence`/`review_evidence` as lists (only as pickers below), month-end link | see Questions 1, 5 |

Unknown values read "Not recorded", never 0 and never a blank that looks like a value.

### Write 1: record what was found (`can_observe === true` only)
Form fields: "What you found" (four choices in the order Found, Not found, Unknown, More than one; nothing chosen when it opens), "Proof" (`FileUpload`, one file, `.png` or `.pdf` only, at most `PROOF_MAX_BYTES`, refused before any request). Button "Record observation" is off until both are set. Words under it (board): "Recording what you saw isn't an approval." Nothing else is promised.
One press runs two calls in order; the first result is kept if the second fails:
1. `POST /api/v1/projects/{case_id}/incumbent-evidence` body `{kind:"quickbooks_verification", case_revision, value:{provider:"quickbooks", realm, entity, source_reference, target_reference, state:<chosen: found|not_found|unknown|multiple>, observed_at:<now, ISO 8601 from the person's press>, transaction_date, accounting_period, treatment_evidence_id, incumbent_version:null}}`. `realm, entity, source_reference, transaction_date, accounting_period, treatment_evidence_id, target_reference` are copied from the read's `source`, not typed. `incumbent_version` is `null` (unknown; never invented). `case_revision` is the read's `case_revision`. 201 `{id, version, kind}`; `id` is the evidence id. `case_id` is the loaded work item's `case_id` (never typed).
2. `POST /api/v1/work/{work_id}/incumbent-reference/observations`, multipart: `expected_revision`, `case_revision` (both from the read), `lineage_id` (the read's `lineage_id`; if it is `null` the button is off with "This source has no lineage yet." and nothing is sent), `evidence_id` (step 1's `id`), `outcome` (chosen), `file`. Do not set `Content-Type` by hand. 201 `{work_id, state, revision, record_id}`.
- After 201: re-read the incumbent-reference and the work item; the panel shows the new observation, and the state tag from the re-read. "Recorded" is told from the re-read (an `observation` now present), not from the 201 alone.
- If step 2 fails with a definite error (400, 403, 409, 413, 415, 422, 429), a retry sends only step 2 with the same evidence id, never a second evidence record, unless the re-read shows a changed `case_revision` (then both steps run again from a fresh read).
- After a dropped connection or 5xx on step 2: uncertain. Re-read; if `check_id` is now set with the chosen `state`, show it recorded; else show "We couldn't confirm that this was recorded. Check the page before trying again.", lock the button until the re-read shows a different `expected_revision` or the person reloads, and send nothing by itself.
- Unknown and More than one are recorded like the others; the page draws whatever the re-read says (`finding`) and decides nothing from the answer.

### Write 2: approve or reject (`review_options` non-empty)
Fields: "Evidence" (a radio list of `review_evidence[]` rows labelled `kind` and "version {version}", nothing preselected; when the list is empty the buttons are off with "No evidence is available for this review yet." and nothing is sent), "Reason" (text, required for both verdicts, 1 to 2000 characters). Buttons: one per entry of `review_options`, in the API's order, labelled "Approve reference" and "Reject". Buttons are off until evidence and reason are set.
- `POST /api/v1/work/{work_id}/incumbent-reference` body `{action:"review", expected_revision, case_revision, check_id, evidence_id, verdict:"approve"|"reject", reason}`. The `action` literal for this body is the contract's own `action` const read from `live-schema.d.ts` (the builder takes it from the generated type, not from this text). `check_id` is the read's `check_id` (button off when `null`). 201 `{work_id, state, revision, record_id}`.
- After 201: re-read; the result is shown from the re-read (`latest_decision`, `verified`, the state tag). One verdict per press; both buttons lock while one runs.
- Errors: 403 non-csrf "You can't do this." plus the server message, then re-read (this covers the independent-reviewer rule if the server enforces it at write time); 409 re-read and "This changed while you were working. Showing the latest version."; 422 the server message and first `fields[].message`; 403 `csrf_failed` refresh once, "Press the button again"; 429 and 503 "Try again shortly."; network or 5xx uncertain as in Write 1 (lock until the re-read shows a different `expected_revision`). No verdict is sent twice by itself.

### Idempotency and versioning
Neither write body has an idempotency key. `expected_revision` and `case_revision` come from the incumbent-reference read, never from the work item and never defaulted; there is no 0 and no null in a body. A fresh read is made after every write and after every 409. Both tokens are required: a read that is not loaded disables the controls.

### Start of the line (`POST /work` `finance-ledger/v1`) and source capture (`incumbent-evidence` kind `ledger_source`)
No SCR-58 board draws a capture form (Question 7). In part 1 these are client functions with unit tests and mock routes only: `captureLedgerSource(caseId, caseRevision, value)` (`POST /projects/{case_id}/incumbent-evidence` kind `ledger_source`, value as in the contract) and `startLedgerWork({caseId, caseRevision, evidenceId, predecessorId})` (`POST /work` body `{line:"finance-ledger/v1", case_id, case_revision, idempotency_key:<uuid, new per attempt>, intake:{evidence_id, predecessor_id}}`). Neither is rendered by this feature; Start work's existing "Record source" entry uses `startLedgerWork` only if its request schema lists the line. They never run on load.

### Screen states
- Loading: the existing skeleton in the panel; the page header from F-85 shows already.
- Empty: a read with `observation` null, `latest_decision` null, `verified` null and no controls shows the Source rows and `finding` only; no empty headings.
- Error: the mapped error above with Try again, last good read kept on a failed re-read.
- Success: the five states of the table below.
- Held and restricted: hold code line; a 404 on the read shows "This record is unavailable."

| Board state | What the live read looks like |
|---|---|
| Investigating | `can_observe:false`, `observation:null`, `verified:null`, `review_options:[]` |
| Observe | `can_observe:true`, `observation:null` (the form shows) |
| Review | `observation` set, `review_options:["approve","reject"]` (the form shows); or `review_options:[]` with `review_hold_code` set (the hold line, no form) |
| Rejected | `latest_decision.verdict:"reject"`, `verified:null`; the panel shows the rejection and, when `can_observe` is true again, the observe form |
| Verified | `verified` not null |

### Fixture examples (mock, port 4991; ids are the builder's, shapes are the contract)
- `4201` investigating: `can_observe:false`, `finding:"Chidi is checking the source."` (sample wording).
- `4202` observe: `can_observe:true`, `lineage_id:11`, `check_id:null`.
- `4203` review: `observation.state:"found"`, `check_id:31`, `has_attachment:true`, `review_options:["approve","reject"]`, `review_evidence:[{id:71,version:1,kind:"quickbooks_verification"},{id:72,version:1,kind:"ledger_resolution_review"}]`.
- `4204` blocked reviewer: as 4203 with `review_options:[]` and `review_hold_code:"independent_reviewer_required"`.
- `4205` rejected: `latest_decision:{id:5,verdict:"reject",reason:"The screenshot shows JE-7714, not JE-7741.",reviewer:"Ada Okafor",at:"2026-11-14T10:05:00Z"}`, `can_observe:true`.
- `4206` verified: `verified` set, `latest_decision.verdict:"approve"`.
- `4207` unknown observation: `observation.state:"unknown"`, `review_options:[]`, `finding` holds the check.
- `4208` null `target_reference` and `incumbent_version`; `4209` 404 for any caller; `4210` returns 409 on the first write then succeeds after a re-read.
- The mock serves `GET`/`POST` for these ids with the live shapes above, a `POST .../incumbent-evidence` returning `{id, version:1, kind}`, and a multipart observations route that checks the field names and the file type. v7 `W-4201` to `W-4213` keep their v7 answers.

## Lanes
- Frontend lane (all of this feature): `frontend/src/features/ledger-source/**` (`ledgerSourceAdapter.ts`, `LedgerSourcePanel.tsx`, `ObserveForm.tsx`, `ReviewForm.tsx`, `labels.ts`, `ledgerSourceApi.ts`, tests), `frontend/mock/ledger-source.mjs` and `frontend/mock/fixtures/ledger-source/**`, `frontend/e2e/ledger-source.spec.ts`, live types for these operations in `frontend/src/api/types.ts` from `live-schema.d.ts`.
- Backend lane: none. No backend, migration or contract change. Backend questions E-29 is answered; the evidence-for-verdict question is flagged in Question 4.
- Integration owner: lane D coordinator.
- Shared files and owners: `src/features/workspace/adapter.ts`, `useWorkCommand.ts`, `EvidencePicker.tsx`, `PanelView` (lane C owns; this feature only registers an adapter and calls them). `src/api/*` (shared; additions limited to live types). `mock/server.mjs` (shared; one import line to mount `ledger-source.mjs`). `src/components/*` used as is.
- Dependency on lane C: `LineAdapter` draws `Section[]` only. This feature also needs a line to supply its own panel component (forms) from the adapter, for example an optional `render(readback, ctx, reload)` field. If F-87 or F-93 already added such a slot, reuse it; if not, lane C adds it as one small commit before the build starts. This feature does not change the shared frame itself.
- Protected paths in `delivery/config.json` stay unchanged.

## Acceptance criteria
Ports: Next 4990, mock 4991, Django 8030.
1. `/work/4201` (mock) shows the Source rows (provider "QuickBooks", reference, realm, entity, dates, period, user reference, outcome) and the `finding` line, and no form, no station track, no "Chidi" card and no "Ask Chidi" — verify: open the page; e2e asserts absence.
2. `/work/4203` shows "What was observed" with "Found" and a "Proof attached" link to `/api/v1/work/4203/incumbent-reference/observations/31`, and an Approve reference and a Reject button — verify: page and DOM; the link target.
3. `/work/4204` shows "Someone who didn't capture or observe this source has to review it." and no approve, reject, evidence list or reason field — verify: e2e asserts the buttons are absent.
4. A `review_hold_code` the page does not know is drawn as its raw text and no buttons — verify: unit test on the mapper.
5. `/work/4205` shows "Ada Okafor rejected it: "The screenshot shows JE-7714, not JE-7741."" with the date from `at`; no "Correct" button and no "re-check" text — verify: page; grep the panel code for no `incumbent-resolutions` call.
6. `/work/4206` shows Posting performed NO, Authenticity certified NO, and Reference recorded YES with the approve date; no "Completeness" row and no amount anywhere — verify: page and DOM text search.
7. A `verified.posting_performed` that is not `false` is drawn as "Not recorded", not NO — verify: unit test with a malformed read.
8. `target_reference:null` and `incumbent_version:null` (`/work/4208`) read "Not recorded", never 0 or blank — verify: page and unit test.
9. `/work/4202` opens with nothing chosen and no file; "Record observation" is off; choosing Found alone keeps it off; adding a PNG turns it on — verify: component test and page.
10. A `.exe`, a `.jpg` and a file over `PROOF_MAX_BYTES` are refused before any request, with the file row's error — verify: unit test asserts zero fetch calls.
11. One press on "Record observation" sends exactly two requests in order: `POST /api/v1/projects/{case_id}/incumbent-evidence` with body `{kind:"quickbooks_verification", case_revision, value:{... state:"found", incumbent_version:null ...}}` then multipart `POST /api/v1/work/4202/incumbent-reference/observations` carrying `expected_revision`, `case_revision`, `lineage_id`, `evidence_id` (from the first response), `outcome:"found"` and `file`; no `Content-Type` is set by hand — verify: e2e request capture; unit test on the two bodies.
12. The evidence value copies `realm`, `entity`, `source_reference`, `transaction_date`, `accounting_period`, `treatment_evidence_id` and `target_reference` from the read and the person types none of them — verify: unit test compares the body with the read.
13. After the 201 the page re-reads the incumbent-reference and shows the new observation from the re-read; with a mock that returns 201 but an unchanged re-read the page does not say "Recorded" — verify: e2e with both mock scenarios.
14. If the observations call returns 422 after the evidence was made, pressing Try again sends only the observations call with the same `evidence_id` — verify: unit test counts evidence and observation POSTs (one and two).
15. After a dropped connection on the observations call the page re-reads; when `check_id` is still null it says "We couldn't confirm that this was recorded. Check the page before trying again.", disables the button and sends nothing for 60 s of fake time — verify: unit test.
16. `lineage_id:null` turns "Record observation" off with "This source has no lineage yet." and sends nothing — verify: unit test.
17. In the review form no evidence row is chosen at first; with `review_evidence:[]` both verdict buttons are off with "No evidence is available for this review yet."; with rows, both buttons stay off until an evidence row and a reason are set — verify: component test.
18. Pressing Approve reference sends one `POST /api/v1/work/4203/incumbent-reference` with `{action, expected_revision, case_revision, check_id:31, evidence_id, verdict:"approve", reason}`; Reject sends `verdict:"reject"`; neither body has a null or 0 token — verify: e2e request capture; the `action` value equals the contract const in `live-schema.d.ts`.
19. A double click on a verdict sends one request; while it runs both verdict buttons are disabled; a poll result arriving mid-write does not clear the lock — verify: unit test with a deferred POST; e2e counts requests.
20. After a verdict 201 the page shows the result from the re-read (`latest_decision` and the state tag); the 201 alone changes nothing on screen — verify: e2e with the unchanged-re-read scenario.
21. A verdict with the reason empty is refused in the form with no request — verify: unit test.
22. `/work/4210`: the first write gets 409; the page re-reads, says "This changed while you were working. Showing the latest version.", and sends nothing more by itself — verify: e2e counts requests.
23. A 403 with `code:'csrf_failed'` on either write refreshes the session once, says "Press the button again", is not shown as no-access, and sends no second request — verify: unit test counts POSTs (one) and session reads (one).
24. A 403 `forbidden` on a verdict shows "You can't do this." plus the server message and re-reads — verify: mock scenario and e2e.
25. A 422 shows the server message and the first `fields[].message` as given; 429 and 503 show "Try again shortly." and nothing is retried by itself — verify: mock scenarios; fetch counts.
26. `/work/4209` (404) and a live work id the account cannot see show exactly "This record is unavailable." with no difference — verify: open both; unit test on the 404 body.
27. A person without `can_observe` and without `review_options` sees no form and no write button at any state; no client code reads `/me` or a role to decide a control — verify: grep `useMe`/`/me` in `features/ledger-source`; e2e on 4201 and 4204.
28. On load, poll and navigation the page sends no `POST`; every write is from a press — verify: e2e asserts zero POSTs after load and after a 12 s poll window.
29. `captureLedgerSource` and `startLedgerWork` send the bodies in Contract, with a new uuid `idempotency_key` per attempt, and are rendered by no page in this feature — verify: unit tests against the mock; grep imports show tests only.
30. Against live Django 8030 with a Finance account that may observe, a ledger work item shows the same source, observation and decision as `GET /api/v1/work/{id}/incumbent-reference`; recording an observation with a small PNG changes `observation` and `check_id` in that read — verify: compare the page with `oa.py live GET /api/v1/work/{work_id}/incumbent-reference 3` output and `curl` with the session. If no account or data can reach this state, say so and record it as not run.
31. Against live Django with an account that captured or observed the source, the page shows the hold line and no buttons (or, if the server lets the buttons show, the write returns the server's refusal and the page shows it unchanged) — verify: the live read's `review_hold_code` and the page.
32. Viewport check at 1440 and 390: the five states match the SCR-58 investigating, observe, review, rejected and verified boards for the parts that remain; hidden parts leave no empty gap or heading — verify: screenshots at both widths against `design/screens.md` SCR-58 artboards.
33. New tests: unit tests for the adapter mapper (all five states, nulls, unknown hold code), the two request builders and the lock rules, plus `frontend/e2e/ledger-source.spec.ts`; `delivery/checks.sh` passes — verify: the check run output.

## Out of scope
- Duplicate and reference-correction resolutions, `GET/POST /projects/{case_id}/incumbent-resolutions`, `ledger_resolution` and `ledger_resolution_review` evidence, the confirm/return/withdraw review, `recheck` and `restart`, the lineage display, the board's "Correct" button and "Open LED-0049" (F-104B).
- Payroll (SCR-59), SCR-53 and SCR-57. Month-end and the ledger month-end link. The "refused, nothing was posted" state.
- A capture form for the source itself, Setup screens for ledger policy, Chidi's agent card and "Ask Chidi", who captured and who observed, any amount, any posting to QuickBooks, any call to QuickBooks.
- Choosing an evidence id for the person, pre-selecting evidence, or sending a made-up reason, `incumbent_version`, observer or approver.
- The JSON-only observe call (`POST incumbent-reference` observation body without a file); this feature always sends the proof file.
- Backend, migrations, contract edits. Changes to F-85's frame beyond the one slot named under Lanes.

## Assumptions
- Evidence for an observation is made by this page through `incumbent-evidence` kind `quickbooks_verification` with the observed state and the source's own fields, then the file goes with it. Reason: the multipart body requires `evidence_id` and this is the only evidence kind whose value is an observation; `verification_evidence[]` is not used as a picker.
- Evidence for a verdict is chosen from the read's `review_evidence[]`. Reason: the read supplies exactly that list and the backend's answer for review tasks says to choose from it (A-18 precedent); how a reviewer creates one is not documented (Question 4).
- `observed_at` is the time of the press, in ISO 8601. Reason: the observation is the person's, made now; the contract takes any string.
- Reason is required for approve as well as reject. Reason: the contract's review body requires `reason` for both.
- The observation proof is required, PNG or PDF only. Reason: the board draws a required proof and the multipart route is "private PNG or PDF proof"; `.jpg`, `.jpeg` and `.eml` from `PROOF_TYPES` are not offered.
- The panel's adapter key is `incumbent-reference`. Reason: the panel URL ends in that segment; the real key is checked on the first live work item.
- The `action` value for the observe and review bodies comes from the generated type. Reason: the contract shows it as `any` in the viewer; the builder takes the const from `live-schema.d.ts` and fails typecheck if it cannot.
- `finding` and `stage` are shown as the API sends them, with light capitalisation only. Reason: no sentence field exists and the vocabulary is unknown.
- The hold sentence is mapped from the stable code, as E-29 intends. Reason: the answer gives a code, not text; it states the board's own rule ("not the capturer, not the observer").
- The four-way choice is drawn as the shared `Select`, as F-45 did. Reason: the shared field rule draws more than three options as a `Select` (Question 8 asks if the board's segments are wanted).
- Mock fixture ids 4201 to 4210. Reason: the live ids are integers and free in the mock.

## Questions
1. Parts the boards draw that API 1.24.0 does not supply: the five-station track, Chidi's "investigating" card with steps and "Ask Chidi", "Captured by" and "Observed by" names, the Lineage row ("New · no predecessor"), the treatment name ("Accrual reversal"), the "Completeness certified" row, the started time, and the verified board's sentence about re-checks. Options: (a) hide them all and say so, switch on when the backend adds data (recommended: D-182, LC-Q1 and D-185 already decided this way); (b) keep them as "Not available" placeholders; (c) hold the page. Context: live gives `finding`, `stage`, `latest_decision.reviewer` and `.at` only.
2. The observe board shows "Found" already chosen and a proof "qb-screenshot-je7741.png · Uploaded · 310 KB". Options: (a) open empty, nothing chosen, nothing uploaded (recommended: those are the person's own answers, not the backend's); (b) pre-select "Found". Context: a pre-selected answer would record something the person did not say.
3. The review board's note label reads "(needed to return, reject or withdraw)" and offers no reason for approve. The live body requires a reason for both verdicts. Options: (a) one "Reason" field required for both, label "Reason (needed)" (recommended: the only honest reading of the contract); (b) hide the field for approve and send fixed text (rejected: invents a reason in the reviewer's name). Context: boards also say "Return"; ledger review has only approve and reject live, so no Return.
4. The verdict needs one evidence item the boards never draw, and the API lists them in `review_evidence[]` without saying how a reviewer makes one. Options: (a) a radio list under the reason, nothing pre-selected, buttons off when the list is empty (recommended: same as the F-64 answer in batch 1, smallest); (b) pre-select the newest (rejected: cites evidence the person did not choose); (c) hold the verdict buttons until the backend says how review evidence is created. Context: if (a) leaves reviewers with an empty list in real data, the page will show "No evidence is available for this review yet." and the backend question goes to the coordinator.
5. The rejected board's "Correct" button and "Correct it with the right evidence; the correction continues the same lineage", and the "re-check reopens it" sentence on verified, rely on correction and recheck, which are F-104B. Options: (a) hide them in part 1 and draw the rejection (reviewer, reason, date) and, when `can_observe` is true, the observe form (recommended); (b) draw "Correct" disabled with "Coming soon". Context: with (a) a rejected source can be observed again but not corrected until F-104B.
6. The observation proof is optional on the JSON route but required on the board. Options: (a) require the PNG or PDF and always use the multipart route (recommended: the board and "private proof" intent); (b) allow no proof. Context: `has_attachment` exists because the backend can hold an observation without a file.
7. No SCR-58 board draws capturing the ledger source (`incumbent-evidence` kind `ledger_source`) or starting the line (`POST /work`, `finance-ledger/v1`). Options: (a) client functions, mock routes and tests only; the Start work page's "Record source" uses the start call if its request schema lists the line (recommended: no undrawn screen); (b) draw a capture form now (needs a new design, 4 concepts per the design-fidelity rule). Context: the source needs `treatment_evidence_id`, `posting_evidence_id` and `provenance` ids a person would not type.
8. The four answers are drawn as a row of segments on the board; the shared field rule draws more than three options as a `Select`. Options: (a) `Select` "What you found" with "Choose…" (recommended: no shared component changes; "More than one" fits at 390 without the board's "Many"); (b) segments as the board, a shared-component change. Context: F-45 recommended (a) too.

## Conflicts with the boards
Questions 1 (parts removed), 2 (pre-filled answers removed), 3 (note label and approve reason), 4 (an evidence list the boards do not draw), 5 (Correct and re-check hidden), 6 (proof rule) and 8 (segments vs `Select`) change something a board draws. Added by this spec and not drawn: the source `outcome` row ("Reported as posted" or "Uncertain"), the hold line for `independent_reviewer_required`, the "Proof attached" link, the reviewer's name and date on the decision. Recommendation: accept the recommended option of each; the added rows are the live replacements for the hidden parts and need a board by the design engineer.
