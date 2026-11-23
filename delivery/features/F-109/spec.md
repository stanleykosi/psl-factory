# HR Lead decides payroll corrections; the named Finance reader confirms the HR export

> Tasks: FE-FIN-PAYROLL-CORRECTIONS (v9 tasks.csv:66). Architecture: v9 package; contract `contracts/psl-factory.openapi.json` 1.24.0 (main b8542c79). Design: approved 13 Nov canvas; screens: SCR-37 (`design/canvas/finance/project/SCR-37-desktop.dc.html`, `SCR-37-mobile.dc.html`; states: default only).

## Summary
- New restricted screen SCR-37 lists payroll correction requests waiting for the signed-in HR Lead (`pending_corrections[]` of `GET /projects/{case_id}/hr-disclosures`). Opening one shows its disclosure and records Approve, Return or Reject.
- The decision is `POST hr-disclosures {action: decide_correction}` with a required proof chosen from `proofs.decide_correction`. The result shown comes from the server answer, never an optimistic claim.
- The named Finance reader sees the HR export awaiting confirmation (`finance_acknowledgement` on the department-handoff read), opens its rows (`snapshots/{id}/rows`) and confirms receipt through `finance-acknowledgement`.
- Everything the API does not supply is hidden (masked staff reference, "3 corrections" count, the board's story text and Note field). Nobody without HR authority sees any payroll data; they see "not available to you".
- Waits on F-85 (shared line adapter, PR #101): build start only, not a blocker. High risk: restricted payroll data and an approval write; merge goes to the design engineer's batch.

## Context
Lane D worktree `/Users/Hunchoo/psl-factory-worktrees/lane-d/frontend`. Nothing for SCR-37 exists (no route, no feature).
- Routes live under `src/app/` (`finance/month-end`, `finance/payments`, `projects/[caseId]/(tabs)`); features under `src/features/<name>/` (`finance/month-end`, `finance/payments` are the nearest pattern).
- API client: `src/api/client.ts` (`api` v7, `liveApi` live, shared CSRF, `call()`), `src/api/errors.ts` (`ApiErrorKind`: unauthenticated, forbidden, csrf, not_found, stale, invalid, rate_limited, server, network...). Live types: `src/api/live-schema.d.ts` (regenerate from 1.24.0 if the hr-disclosures types are missing).
- Shared adapter (F-85 spec `delivery/features/F-85/spec.md`): `src/features/workspace/adapter.ts` exports `CommandDescriptor`, `makeCommand`, `LineContext`. Lane C owns it; this feature only uses it. Evidence for a write is chosen from `proofs`, not uploaded, so `EvidencePicker` is not used.
- Mock: `frontend/mock/server.mjs`, `mock/finance.mjs`, `mock/session.mjs` as models for live-shaped replies.
- Live item shapes are typed in 1.24.0 (readiness said untyped; this is better). The facts below are from the contract.

## Contract

### Reads (live, as the signed-in person)
1. `GET /api/v1/projects/{case_id}/hr-disclosures?page=` returns `{revision, needs[{id, reference, version, entity, period, purpose, fields[]}], disclosures[{id, need_id, latest_decision approve|return|revoke|null, created_at}], actions[], pending_corrections[{id, contract_id, snapshot_id, requested_at}] (max 25), proofs{need, contract, authorize, receive, correction, decide_correction, bind, draft_policy: [{id, version, kind}]}, next_page|null}`. `actions[]` lists what this person may do now.
2. `GET /api/v1/projects/{case_id}/hr-disclosures/{contract_id}` returns `{revision, disclosure, current_approval_id|null, fields[], entity, period, decisions[{id, verdict, created_at}], snapshots[{id, status accepted|rejected, retain_until, findings[], receipt_id|null}], corrections[{id, snapshot_id, decision response|correction_return|correction_reject|null, successor_id|null}], questions[{task_id, revision, snapshot_id, owner_id, question, status, reason, can_reply, can_cancel}]}`.
3. `GET /api/v1/projects/{case_id}/department-handoffs?before=&process=` returns `{items[{work_id, project_id, process, title, status, django_url}], next_before}`; for each item `GET /api/v1/work/{work_id}/department-handoff` returns `{..., receipt{verified_at}|null, finance_acknowledgement{snapshot_id, revision}|null}`. A row is "awaiting your confirmation" only when `finance_acknowledgement` is not null.
4. `GET /api/v1/projects/{case_id}/hr-disclosures/snapshots/{snapshot_id}/rows?page=` returns `{snapshot_id, entity, period, as_of, completeness complete|partial|unknown, total, fields[], rows[] (max 25, every field string|null), next_page|null}`. Only the named Finance recipient is admitted.
5. `GET /api/v1/projects/{case_id}/hr` (destinations, metadata only) is not read by this screen; the HR role's metadata view is a link target only (see Out of scope).

### Writes
All send `X-CSRFToken` (shared client). An `operation_key` is a uuid made once per attempt (`newIdempotencyKey`) and re-sent unchanged only when retrying after a network failure or 5xx; a fresh key after any 200 or 4xx answer.

**Decide a correction.** `POST /api/v1/projects/{case_id}/hr-disclosures`
```json
{"action":"decide_correction","revision":7,"request_id":14,"verdict":"approve","successor_id":null,"operation_key":"<uuid>","evidence_id":301}
```
Response 200 `{revision, record_id|null, configuration_ids[]}`. `request_id` = `pending_corrections[].id`; `revision` = the `revision` of the list read the person is looking at; `evidence_id` = one id from `proofs.decide_correction` (required; there is no free text field). `successor_id`: the matching `corrections[]` entry's `successor_id` when it is not null, else `null`. Errors: 401 sign-in; 403 `forbidden` "not available to you"; 403 `csrf_failed` refresh the session, "Press Record decision again", nothing was sent; 404 "This record is unavailable."; 409 stale revision: re-read both reads, keep the chosen verdict, say "This changed while you were looking. Check it and decide again."; 422 show the first `fields[].message`; 429 and 503 "Try again shortly"; network: "We couldn't confirm. Check before trying again." and the same key is reused.
After 200 the screen re-reads the list and the disclosure and shows the result from those (the request leaves the waiting list; `corrections[].decision` shows the verdict). If the re-read fails, show "Recorded. We couldn't refresh the list", never a guess of the new state.

**Confirm receipt.** `POST /api/v1/work/{work_id}/department-handoff/finance-acknowledgement` body `{snapshot_id, revision}` taken verbatim from `finance_acknowledgement` of the handoff read (no key or proof field exists on this route in 1.24.0). Response 200 `{receipt_id}`. The same error mapping applies. After 200 re-read the handoff and show "Receipt recorded" only when `receipt` is not null.

Request a correction (`action: correction`) is not built here (see Out of scope).

### Commands through the adapter
`src/features/payroll-corrections/correctionCommands.ts` builds the two writes with `makeCommand` (F-85): tokens `{revision}` for decide, `{revision}` for receive, idempotency field `operation_key` for decide and `null` for receive. Per lane C's rule, revision tokens and the key are not passed in `inputs`. `disabledReason` comes from the read (`actions[]` lacks `decide_correction`: "You can't decide corrections here"); never invented. A null token stays null.

### Permission and tenant rules
- The case id comes only from the route and the loaded project; never typed by the person. Every read and write runs as the signed-in person. The client makes no role check and infers no access: what the API returns and admits is what is drawn. 403 and 404 both read "This isn't available to you." on the payroll reads (the screen is restricted; no existence leak and no difference between missing and not yours).
- The HR role never sees snapshot rows. Only the named Finance recipient opens them (a 403/404 on rows shows the same "not available to you" in that section only).
- Group recipients' projections are server-side only; this screen requests and renders no group data, no staff names, no raw payroll input. Row fields are drawn exactly as `fields[]` lists them; a field not in `fields[]` is not drawn; `bank_account`, `home_address`, `date_of_birth` are drawn only when present in `fields[]` and the value is not null. Nothing restricted is written to the URL, page title, `localStorage`, logs or error text.
- Null is "Not recorded", never 0 (`monthly_pay`, `gross_pay`, `deductions`). Rows are text, never summed or reformatted as money by the client.

### Screen states (SCR-37 desktop, mobile)
Route (assumption A1): `/finance/payroll/corrections/[caseId]`.
- Loading: skeleton list, no counts.
- Empty: `pending_corrections` empty and no handoff awaiting: "No corrections are waiting for you." with the "As of {time}" line.
- Error: 401 signed-out state with `/sign-in?next=`; 403 and 404 "This isn't available to you." with no data and no hint of what exists; 429/503/network "We couldn't load this. Try again." with Try again; the list keeps its last good data on a failed refresh and says so.
- Success, default (matches board): header "Payroll corrections", "Restricted to HR roles" strip, list of waiting corrections, decision panel with Approve, Return, Reject, proof chooser, "Record decision". Mobile (board draws the list only): list rows; the decision panel opens as its own view, same content.
- Row content (only what the API gives): "Correction #{id}" (the API has no PC- reference), "Requested {requested_at}", entity and period of its disclosure (read 2), and state "WAITING FOR YOU". A decided correction opened from the disclosure shows the verdict from `corrections[].decision` and its time from the matching `decisions[].created_at` only when one matches that correction; otherwise no date.
- Decision panel content: entity, period, the list of fields shared (`fields[]` words), any `questions[]` open on that snapshot (question text, status), `snapshots[].findings[]` strings. Verdict buttons are three radio-style choices; "Record decision" is disabled until a verdict and a proof are chosen, while `actions[]` lacks `decide_correction`, and while a write runs. After success: the result line "Decision recorded: {verdict}" from the re-read.
- Finance section "HR export awaiting your confirmation" (named Finance reader only, drawn only when a handoff has `finance_acknowledgement`): snapshot id, entity, period, "As of", completeness (`unknown` shows "Not known"), `total` ("{n} rows"), a rows table in pages of 25 using `next_page`, and "Confirm receipt".

### Fixtures (mock on 4991; live-shaped, ids integers)
Case `c0000000-0000-4000-8000-000000000037`, mock sessions: `hr-lead` (admitted), `finance-recipient` (named Finance reader), `plain-member` (no HR authority).
- `hr-lead` list: `revision:7`, `pending_corrections:[{id:14,contract_id:51,snapshot_id:201,requested_at:"2026-11-10T09:00:00Z"},{id:13,contract_id:51,snapshot_id:200,requested_at:"2026-11-08T09:00:00Z"}]`, `actions:["decide_correction"]`, `proofs.decide_correction:[{id:301,version:1,kind:"evidence"}]`, `next_page:null`. Contract 51: `entity:"PSL-NG"`, `period:"2026-10"`, `fields:["employee_id","bu","effective_from","role"]`, `corrections:[{id:11,snapshot_id:199,decision:"correction_return",successor_id:null}]`, `decisions:[{id:9,verdict:"approve",created_at:"2026-11-02T10:00:00Z"}]`.
- Stale: a decide with `revision:6` answers 409. Retry: replaying the same `operation_key` returns the first 200 without a second decision.
- `plain-member`: every payroll read answers 403 `forbidden`; `GET .../hr-disclosures/999` answers 404.
- `finance-recipient`: list `actions:["receive"]`; handoff `{work_id:4301, finance_acknowledgement:{snapshot_id:201, revision:3}, receipt:null}`; rows with `fields:["employee_id","bu","monthly_pay","currency"]`, `completeness:"partial"`, `total:30`, one row with `monthly_pay:null`.

## Lanes
- Frontend lane (all of it): `frontend/src/app/finance/payroll/corrections/[caseId]/page.tsx`, `frontend/src/features/payroll-corrections/**` (page, list, decision panel, export section, `useCorrections`, `correctionCommands.ts`, labels, tests), live types in `frontend/src/api/types.ts` (hr-disclosures and handoff types only), `frontend/mock/payroll-corrections.mjs` and its route registration line in `frontend/mock/server.mjs`, `frontend/e2e/payroll-corrections.spec.ts`.
- Backend lane: none. No backend change.
- Integration owner: lane D coordinator. Shared files and owners: `src/features/workspace/*` (lane C, not changed); `src/api/*` (shared, additions to types and error wording only); `src/shell/*` navigation (lane A; no menu entry added, see A2). `frontend/mock/server.mjs` edit is one registration line; name it in build.md for lane B.
- `delivery/config.json` protected paths stay unchanged.

## Acceptance criteria
1. As `hr-lead` at `http://localhost:4990/finance/payroll/corrections/<case>` (mock 4991), the page lists correction #14 and #13 each with "Requested 10 Nov" and "08 Nov" and "WAITING FOR YOU", and shows "As of" — verify: open the page; `e2e/payroll-corrections.spec.ts`.
2. The page shows no masked staff reference (`S-●●●`), no "3 corrections" count, no story text and no Note field — verify: e2e asserts those strings absent; DOM check.
3. Selecting #14 shows entity PSL-NG, period 2026-10 and the four field words; "Record decision" is disabled until a verdict and the proof (id 301) are both chosen — verify: e2e.
4. Choosing Approve plus proof 301 and pressing Record decision sends exactly one `POST /api/v1/projects/<case>/hr-disclosures` with `action:"decide_correction"`, `revision:7`, `request_id:14`, `verdict:"approve"`, `successor_id:null`, a uuid `operation_key` and `evidence_id:301`, then re-reads, and #14 leaves the waiting list — verify: network panel; unit test on `correctionCommands.body()`.
5. Return and Reject send `verdict:"return"` and `"reject"`; a correction whose `corrections[]` entry has `successor_id: 88` sends `successor_id:88` — verify: unit tests.
6. While a decide is in flight the button is disabled; a double press sends one request — verify: unit test with a deferred mock.
7. A network failure on decide shows "We couldn't confirm. Check before trying again." and pressing again re-sends the same `operation_key`; after a 200 or 409 the next attempt uses a new key — verify: unit test on key handling; mock replay returns the first result.
8. A 409 (stale revision 6) keeps the chosen verdict, re-reads, and shows "This changed while you were looking. Check it and decide again."; no success message appears — verify: mock scenario `stale`; e2e.
9. A decide 200 followed by a failed re-read shows "Recorded. We couldn't refresh the list" and does not claim the new state — verify: mock scenario `reread_fails`.
10. `csrf_failed` 403 refreshes the session and says "Press Record decision again"; it does not show the no-access state — verify: mock scenario; unit test.
11. Failure journey, no HR authority: signed in as `plain-member`, opening the page shows only "This isn't available to you." with no list, counts, ids, entity names or fields; the browser makes no write and the page renders no payroll value; a direct URL for a contract the person cannot see (`.../hr-disclosures/999`, 404) shows the identical wording — verify: open both as `plain-member`; e2e compares text and asserts the DOM holds no entity, period or field words.
12. As `hr-lead` the "Confirm receipt" control and the rows table never render, and no request to `snapshots/{id}/rows` or `finance-acknowledgement` is made — verify: network panel; e2e.
13. As `hr-lead`, if `actions[]` lacks `decide_correction` the three verdicts and Record decision are disabled with "You can't decide corrections here" (text from the read-driven `disabledReason`) — verify: unit test with `actions:[]`.
14. With `proofs.decide_correction` empty, Record decision is disabled with "No proof is available to attach." — verify: unit test.
15. As `finance-recipient`, the "HR export awaiting your confirmation" section shows snapshot 201, "As of", "Partial", "30 rows", a rows table of at most 25 rows with "Next page" using `next_page`, and `monthly_pay:null` reads "Not recorded", never 0 — verify: e2e; unit test on the row mapper.
16. "Confirm receipt" sends one `POST /api/v1/work/4301/department-handoff/finance-acknowledgement` with body exactly `{snapshot_id:201, revision:3}`, then re-reads and shows "Receipt recorded" only when `receipt` is not null — verify: network panel; unit test; mock scenario where `receipt` stays null shows no tick.
17. A rows 403 or 404 for a reader who is not the named recipient shows "This isn't available to you." inside that section only and draws no table — verify: mock scenario; e2e.
18. Rows are never summed, no totals are computed on the client, and a `completeness:"unknown"` shows "Not known" — verify: unit test; grep shows no arithmetic on row money fields.
19. No payroll value (a row field, an entity name, a snapshot id) appears in the URL, document title, `localStorage`, `sessionStorage` or a console message — verify: e2e inspects them after opening a snapshot.
20. Empty and loading states: `pending_corrections:[]` shows "No corrections are waiting for you."; a pending request shows the skeleton; a failed refresh keeps the last list with "We couldn't refresh" — verify: mock scenarios.
21. On a 390 px-wide viewport the list shows as rows and the decision panel opens as its own view with the same controls; no horizontal scroll — verify: Playwright mobile viewport; screenshot compared with `SCR-37-mobile.dc.html`.
22. The same page against live Django 8030 for an HR account shows the same fields as `GET /projects/{case_id}/hr-disclosures` — verify: compare the page with the curl JSON using the session; typecheck and `delivery/checks.sh` pass.
23. Unit tests exist for: the pending list mapper, `correctionCommands` bodies and key handling, error mapping for 401/403/404/409/422/429/503/network, and the rows mapper (null handling) — verify: `npm test` shows them.

## Out of scope
- Requesting a correction (`action: correction`), `need`, `contract`, `authorize`, `bind`, `capture`, scope and policy actions, `exports`, clarification replies and cancels (`questions[].can_reply` and `can_cancel` are shown read-only, no reply control). Name differences (`payroll/name-checks`, F-108). HR field visibility (`/setup/{case_id}/hr-field-visibility`, SCR-13, D-PAYROLL-VISIBILITY). The payroll run stations (E-31, F-110). Upload of proof files and `EvidencePicker`. The `GET /projects/{case_id}/hr` destinations list beyond linking nothing.
- Masked staff reference, "N corrections · N waiting" counts, the board's story paragraph ("HR says staff record..."), "Proof: signed transfer letter", the Note field and the Filter control: hidden because the API supplies none of them (D-182).
- Any new navigation menu entry, any change to `src/features/workspace/*`, group-recipient views, exporting or downloading HR rows, and any client-side role check.

## Assumptions
- A1: Route `/finance/payroll/corrections/[caseId]` follows the existing `finance/*` routes; no route is named in the sources.
- A2: No menu entry is added; the page is reached by direct link or by the server's `django_url`/handoff links. Lane A owns navigation.
- A3: `revision` for decide is the list read's `revision`; the sources do not say list or detail. A 409 re-read corrects a wrong choice safely.
- A4: `successor_id` is taken from the matching `corrections[]` entry when set, else null; the sources do not say who supplies it.
- A5: Receipt uses `finance-acknowledgement` with `{snapshot_id, revision}` as the 1.24.0 contract defines it, not the `operation_key`/`evidence_id` body readiness listed (that body belongs to the `receive` action on `hr-disclosures`, which this screen does not use).
- A6: The Finance section finds its work item by reading `department-handoffs` and keeping items whose handoff read has `finance_acknowledgement`; the `process` value for payroll is not documented, so no `process` filter is sent.
- A7: Words "Correction #{id}" replace the board's "PC-014" because the API has no PC- reference.
- A8: Decided corrections appear only inside an opened disclosure, since the list read carries waiting ones only.

## Conflicts with the boards
- Board adds: Filter control, "3 CORRECTIONS · 2 WAITING", PC- references, story text, Proof line, Note, masked staff reference, a decided row ("APPROVED 02 NOV"); none are in the API. Spec hides them (Question 1, 2).
- Board omits: the Finance receipt section, proof chooser, list "as of" line and error/restricted states. Spec adds them (Questions 3, 4).
- Board header says "Finance only ever sees business-unit totals, never these records", which conflicts with the named Finance recipient opening HR export rows (Question 3).

## Questions
1. Note field and story text. Options: (a) hide the Note field, the "HR says..." paragraph and the Proof line, since decide_correction takes no note and the API supplies no description (recommended); (b) ask backend for a note and a request description; (c) draw them as static text. Context: board draws Note and a request story, API 1.24.0 has neither.
2. Waiting count, filter and decided row. Options: (a) show "N waiting" (from `pending_corrections` with an As-of line) and no filter, and show decided corrections only inside an opened disclosure (recommended); (b) hide counts and decided rows entirely; (c) fetch every disclosure to build the full list with decided rows. Context: the list read carries waiting items only, max 25 per page.
3. Finance receipt section is not drawn, and the board's header says Finance never sees these records. Options: (a) build a plain section from existing components (CMP-01, CMP-22, CMP-24) for the named Finance reader and change the header line to "Restricted to HR roles and the named Finance reader" (recommended); (b) hold the Finance part until the design engineer draws it and ship the HR decision alone; (c) put receipt on a separate screen. Context: readiness puts the receipt in scope; no board draws it.
4. Proof chooser. Options: (a) a simple select of `proofs.decide_correction` entries labelled "Evidence {id} (v{version})" (recommended); (b) hide proof and send nothing, which the API refuses; (c) upload a new proof (needs a backend route not in 1.24.0). Context: `evidence_id` is required, board shows no proof control.
