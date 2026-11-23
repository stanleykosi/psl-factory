# Mark a milestone complete, recorded only after a re-read

> Tasks: FE-MILESTONE-COMPLETE. Architecture: live contract `contracts/psl-factory.openapi.json` 1.24.0 (main b8542c79; D-185); connection map `delivery/connect/screens-b-projects-setup-clients.md` SCR-19; backend answers B-28 to B-31. Design: approved canvas as recorded in `design/screens.md`; screens: SCR-19 (`design/canvas/project/SCR-19-desktop.dc.html`, `SCR-19-mobile.dc.html`, state: default).

## Summary
- From the Milestones tab, a person opens "Mark a milestone complete" for one named milestone, picks the proof (an existing proof on record, or a private PDF they upload), ticks the confirmation and presses "Mark complete". One press sends one `POST /projects/{case_id}/milestones/completions`.
- The control shows only when the options read (`GET …/milestones/completions?name=`) returns `can_complete: true`. A hold (`baseline_required`, `proof_required`, `name_in_use`) shows its reason in plain words and no control. The UI never decides authority.
- "Recorded" shows only after a re-read (`GET …/milestones/{id}`) confirms it. A 409 reloads the options and keeps what the person entered. An uncertain failure is never resent automatically.
- Completion only queues the Finance handoff (D-187, B31). The screen never starts, drafts or promises an invoice.
- Flagged for the PR: LB-2, PMO Lead enforcement on the server, is unconfirmed (see Assumptions).

## Context
F-71 (READY, spec `delivery/features/F-71/spec.md`; must be merged first, then F-78 branches from main) rebuilds the Milestones tab on the live API. F-78 builds on its files and does not rewrite them:
- `frontend/src/features/projects/milestonesModel.ts` (F-71): live types, `isCompletions`, `isCompletion`, the stage filter and `milestone_id` join. F-78 adds `isCompletionOptions(body)`, `isRecordedCompletion(body)` (the 201 body), `HOLD_WORDS`, and `completeHref(caseId, name)`.
- `frontend/src/features/projects/useMilestones.ts` (F-71): the two list reads plus `readProof(milestoneId)`. F-78 adds one more read on open, `readOptions()` (the options read with no `name`), and exposes `canComplete`, `hold`. It reuses `readProof`'s `GET …/milestones/{id}` call for the re-read, via a shared `readCompletion(caseId, id)` extracted in `milestonesModel.ts`/`useMilestones.ts`.
- `frontend/src/features/projects/MilestonesTab.tsx` (F-71): F-78 adds the "Mark complete" entry (below).
- The "Proof" button and the live-shaped mock with Ajv validation (`tests/mock-live-projects.test.ts` pattern, F-71's mock tests) are reused. F-78's new mock bodies are validated the same way.
- Existing parts to reuse: `FileUpload` and `PROOF_MAX_BYTES` (`frontend/src/components/FileUpload.tsx`), `Breadcrumb`, `Callout`, `Button`, `LoadingState`, `WorkErrorCard`, `SignedOutState`, `ApiError`/`UNEXPECTED_MESSAGE` and `call(liveApi.…)` (`src/api/client.ts`, `src/api/errors.ts`), `useProject.ts` for the sequence guard and case read. There is no shared evidence picker on main (`origin/main` has only `features/response/useEvidenceUpload.ts`, which targets the v7 evidence route and is not reused). The proofs list here is a plain radio list of `{id, label}`, so no picker is needed.
- Live contract (1.24.0), `project_operations_milestone_options`, `project_operations_record_milestone`, `project_operations_milestone`, `agents_upload`:
  - `GET /api/v1/projects/{case_id}/milestones/completions?name=&page=` returns `{revision, proofs[{id,label}] (max 50), next_page, can_complete, can_attach_pdf, hold}`.
  - `POST` same path, `X-CSRFToken`, body one of `{revision, name (1..200), evidence_id}` or `{revision, name, upload_id, checked: true}`; 201 `{id, revision, name, evidence_id}`; 400/401/403/404/409/413/415/422/429/5xx.
  - `GET …/milestones/{milestone_id}` returns `{id, name, completed_at, evidence_id, proof_version}` (F-71 already types it).
  - `POST /api/v1/cases/{case_id}/files` (multipart, `file`) returns `{upload_id, name, size, sha256, download_url}`. This is the "checked private PDF upload" route 1.24.0 gives for B-29.
- Today there is no SCR-19 route: `frontend/src/app/projects/[caseId]/` has `(tabs)/[tab]`, `documents/[documentId]` only. `milestones/complete` is a separate two-segment path and does not collide with `(tabs)/[tab]`.

## Contract

### Route and entry
- New route `/projects/[caseId]/milestones/complete?name=<milestone name>` (`frontend/src/app/projects/[caseId]/milestones/complete/page.tsx`, client component `MilestoneCompletePage`). Breadcrumb `<Project name> / Milestones` links back to `/projects/[caseId]/milestones`. Title "Mark a milestone complete".
- Entry from the Milestones tab: on opening the tab, `useMilestones` issues one `GET …/milestones/completions` with no `name`. When it returns `can_complete: true`, each contract-stage row with `completed_at: null` shows a "Mark complete" link to `…/milestones/complete?name=<encodeURIComponent(label)>`. (Phone: in the card.) With `can_complete: false` and a non-null `hold`, no link, and one plain line above the table: the hold's reason (below). With a 403/404/error on this read, no link and no message (the tab is otherwise unchanged; a failed options read must not break F-71's reads). The `name` is the stage `label` exactly as `/money` gives it.
- No `name` in the URL: the page shows "Choose a milestone from the Milestones tab." with a link back, and makes no write and no read.
- The name is shown read-only. The person cannot edit it, because the backend binds to the exact configured milestone name (B-28).

### Reads on the page
- On open: `GET …/milestones/completions?name=<name>` (once; `?page=` for "Show more", appended and de-duplicated by `id`). `revision` from the latest successful options read is the revision sent on the write.
- The project name and the milestone's stage number are not required from a second read. The title area shows the milestone name only (see conflicts).

### Hold reasons (plain words, shown instead of the control)
| `hold` | Text | Notes |
|---|---|---|
| `baseline_required` | "This project has no signed baseline yet. A milestone can be completed once the SOW baseline is signed." | no control |
| `proof_required` | "There is no proof on record for this milestone yet." | If `can_attach_pdf` is true the PDF upload stays shown (see below); then the hold clears only by the next options read. Otherwise no control. |
| `name_in_use` | "A completion with this name is already recorded." | links to the Milestones tab; no control |
| null, `can_complete: false` | "You can't mark this milestone complete." | no control |
The text is client wording; the server's message is not shown.

### Control
- "Mark complete" (primary Button) renders only when `can_complete` is true. It is enabled only when all of: exactly one evidence chosen (a proof radio, or an uploaded PDF), the confirmation checkbox "I confirm this milestone is complete as the SOW describes it." ticked, no write in flight, and no recorded/uncertain state.
- Evidence section "Evidence":
  - `proofs[]`: radio list labelled by each `label` (for example "Completion evidence · version 2"), "Show more" while `next_page` is non-null. No proofs and `can_attach_pdf` false: "No proof is on record for this milestone." and no control.
  - Only when `can_attach_pdf` is true: a `FileUpload` ("Or upload a private PDF", `.pdf` only, `PROOF_MAX_BYTES`). Choosing a file uploads it at once with `POST /api/v1/cases/{case_id}/files` (multipart `file`; a non-live shape such as `content_base64` is not used). The row shows `name` and `size`. Success keeps `upload_id`. Choosing the PDF deselects any proof radio and vice versa; Remove clears `upload_id` locally (the private file stays on the case; the screen does not claim it was deleted). A failed upload shows Try again; nothing retries on its own. 413 "That file is too large to upload.", 415 "Only a PDF can be attached as proof.", 429 the standard `rate_limited` wording.
  - With a PDF chosen, a second checkbox is required: "I have checked this file is the proof for this milestone." Ticking it is what sets `checked: true` in the body; the body never sends `checked: true` otherwise.

### Write
- `POST /api/v1/projects/{case_id}/milestones/completions` through `call(liveApi.POST(…))`:
  - Proof: `{"revision": 5, "name": "UAT sign-off", "evidence_id": 31}`.
  - PDF: `{"revision": 5, "name": "UAT sign-off", "upload_id": 88, "checked": true}`.
  - Only one of the two shapes is ever sent. `name` is the URL name (trimmed length 1 to 200, else the page shows the "Choose a milestone" state).
- Press rules: the button is disabled and `aria-busy` from the first press until the response; a second press while in flight sends nothing. One press is exactly one POST. There is no timer, no auto-retry and no resend on reconnect. A CSRF failure (`call` refreshes the token) shows the standard session-refreshed message and the person presses again.
- No idempotency key exists in the contract. The server-side `name_in_use` hold is the only duplicate guard, so the page must not resend after an uncertain result.
- Response 201 `{id, revision, name, evidence_id}` is not by itself shown as "recorded". It triggers the re-read.

### After the write: the re-read
1. On 201, the page enters "Confirming" (spinner text "Checking the record…") and issues `GET …/milestones/{id}` with the returned `id`.
2. The re-read passes the guard `isCompletion` and its `name` equals the written `name`: show "Recorded" (below) from the re-read body (`name`, `completed_at`, `proof_version`), not from the 201.
3. The re-read fails (network, 5xx, 404, wrong name): show "We saved your completion but couldn't confirm it yet. Check again." with a "Check again" button that repeats only the `GET …/milestones/{id}`. Never claims "recorded". Never offers "Mark complete" again for this entry.

### Failure handling
| Result of the POST | What shows | Input |
|---|---|---|
| 409 | "This project changed while you were confirming. We reloaded it. Check the proof and press Mark complete again." The page re-reads the options (`?name=`), replaces `revision` and `proofs`, and, if the hold is now `name_in_use`, shows that hold instead. | Selected proof (kept when its id is still in `proofs[]`; else deselected with a note "That proof is no longer available."), uploaded PDF and both checkboxes are kept. No auto-resend. |
| 400, 422 | The server's field-level message where the live error body gives one, else "We couldn't record this. Check the proof and try again." | kept |
| 403 | "You can't mark this milestone complete." | kept; the control is removed after a re-read of options |
| 404 | "This project or milestone isn't available to you." | n/a |
| 401 | `SignedOutState` with the page's path | n/a |
| 413, 415 | PDF wording above (only reachable if the upload route accepted what the write then refuses) | kept |
| 429 | standard `rate_limited` wording; the person presses again | kept |
| Network error, timeout, 5xx (uncertain: the server may have recorded it) | "We couldn't tell whether this was recorded. Check before trying again." with a "Check again" button. | kept |
Uncertain "Check again" reads only `GET …/milestones/completions?name=<name>`. If it returns `hold: "name_in_use"` the page says "A completion with this name is now recorded. Open the Milestones tab to see it." with a link and does not claim it was this press (no id is known). If `hold` is null and `can_complete` is true, the page says "It wasn't recorded." and returns to the form with input kept, and the person may press again (a deliberate second press). Any other result keeps the uncertain message. The write is never sent by "Check again".

### Screen states
| State | What shows |
|---|---|
| Loading | `LoadingState` until the options read settles |
| Ready | name, evidence, confirmation, "Mark complete" and the "What happens next" block |
| Hold or no authority | name, hold text, no control, "What happens next" hidden |
| Empty proofs | "No proof is on record for this milestone." (PDF zone if `can_attach_pdf`) |
| Error (options read 5xx/network, or body fails the guard) | `WorkErrorCard` "We couldn't load this milestone. Nothing was changed." with Try again |
| No access (403/404) | "This project or milestone isn't available to you." |
| Signed out (401) | `SignedOutState` |
| Submitting | button busy, form read-only |
| Confirming / uncertain / conflict | as in the tables above |
| Recorded | heading "Milestone recorded", the milestone name, "Completed <completed_at>" (`When`, daytime), "Proof version <proof_version>", the Finance text below, and a "Back to Milestones" link. No Mark complete control. |

"What happens next" block (replaces the board's invoice text, see conflicts), shown in Ready and Recorded: "The milestone is recorded as complete, with the proof you chose. Finance is handed this milestone and starts any invoice itself. The amount comes from the contract, not from this form. Completing a milestone is not invoicing it. PMO completes milestones; Finance handles invoices." No invoice number, no "Chidi drafts", no "Start the invoice". The page makes no read of department handoffs (see Out of scope).

### Mock (`frontend/mock`)
- Serve `GET …/milestones/completions` (with `name`, `page`) and `POST …/milestones/completions` and `POST /api/v1/cases/{case_id}/files` in the live shape, from `mock/money.mjs`/`mock/project-tabs.mjs` neighbours (a new `mock/milestone-complete.mjs`, registered like F-71's money route in `mock/server.mjs`; if `server.mjs` needs a change, a separate small commit after `git merge origin/main`, noted in build.md). UUID and P-nnnn ids both accepted, as F-71.
- `GET …/milestones/{id}` already exists from F-71; the POST adds the new id so a re-read of it succeeds.
- Persona or fixture cases, selected by project id or a scripted cookie `psl_mock_complete=<case>`: `ok` (can_complete true, 2 proofs, `can_attach_pdf` true), `baseline` (`baseline_required`), `proofreq` (`proof_required`, `can_attach_pdf` false), `inuse` (`name_in_use`), `norole` (can_complete false, hold null), `paged` (`next_page` 2), `conflict` (first POST 409, then ok with a new `revision`), `uncertain` (POST returns 503 and records nothing), `uncertain-saved` (POST returns 503 but records, so the next options read gives `name_in_use`), `reread-fail` (201, then the re-read 503 once, then ok), `forbidden` (options 403), `notfound` (options 404).
- Every served body is validated against the live contract by Ajv in a new test, as in `tests/mock-live-projects.test.ts`.

Example options body (`ok`):
```json
{"revision":5,"proofs":[{"id":31,"label":"Completion evidence · version 2"},{"id":29,"label":"Completion evidence · version 1"}],"next_page":null,"can_complete":true,"can_attach_pdf":true,"hold":null}
```
Example 201 and re-read:
```json
{"id":412,"revision":6,"name":"UAT sign-off","evidence_id":31}
{"id":412,"name":"UAT sign-off","completed_at":"2026-11-23T10:15:00Z","evidence_id":31,"proof_version":2}
```

## Lanes
- Frontend lane (lane-b worktree, ports 4970/4971, Django 8010): `frontend/src/app/projects/[caseId]/milestones/complete/page.tsx`, a new `frontend/src/features/projects/MilestoneComplete.tsx`, `useMilestoneComplete.ts`, `milestoneCompleteModel.ts` (or the model additions in `milestonesModel.ts` named above), the F-71 files named in Context (`MilestonesTab.tsx`, `useMilestones.ts`, `milestonesModel.ts`), `frontend/mock/milestone-complete.mjs` and its fixtures, `project-tabs.css` additions for the new page, and the tests below. Commands run from `frontend/`.
- Backend lane: none. No contract or Django change. LB-2 is a backend open item (below), not built here.
- Integration owner: live smoke against Django 8010 (`PGHOST=127.0.0.1 PGPORT=55433`) with the local test accounts, covering one real completion on a disposable project and the re-read.
- Shared files, not edited: `src/api/*` (including `live-schema.d.ts`) and `src/shell/*` are lane A's; `src/features/workspace/*` is lane C's; `src/components/*` is shared (reuse `FileUpload`, `Callout`, `Breadcrumb` unchanged). `mock/server.mjs` is shared: edit only the route registration, as a separate small commit after `git merge origin/main`. The F-71 files are lane B's but F-75/F-74 share `tabsModel.ts`, `useProjectTab.ts`, `TabParts.tsx`; do not touch those.
- Ordering: build starts only after F-71 is merged to main; branch `fe-milestone-complete-<short>` from `origin/main` after that.

## Acceptance criteria
1. The control follows the server only: with the options body `can_complete: true`, "Mark complete" is present; with `can_complete: false` it is absent, whatever the user's role label says — verify: `tests/milestone-complete.test.tsx` renders both bodies for the same persona and asserts the button; `grep -rniE "pmo lead|isPmo|role" frontend/src/features/projects/MilestoneComplete.tsx frontend/src/features/projects/useMilestoneComplete.ts` finds no role check.
2. Each hold shows its plain-word text and no control: `baseline_required`, `proof_required`, `name_in_use`, and `can_complete:false` with `hold:null` — verify: test asserts text and `queryByRole('button', {name: 'Mark complete'})` is null for each; the raw hold codes never appear in the DOM.
3. With `can_complete: true` and no evidence chosen, or the confirmation unticked, the button is disabled — verify: test asserts `disabled` for each missing piece and enabled when all are present.
4. Choosing an existing proof and pressing sends exactly one `POST …/milestones/completions` with body `{revision, name, evidence_id}` and header `X-CSRFToken`, and no `upload_id` or `checked` — verify: test spies on `fetch` and asserts the count and exact JSON.
5. Choosing a PDF first sends `POST /api/v1/cases/<id>/files` as multipart with `file`, then (after both checkboxes) `POST …/completions` with `{revision, name, upload_id, checked: true}`; `checked` is never sent without the second checkbox — verify: test asserts request bodies and order; asserts the PDF zone is absent when `can_attach_pdf` is false.
6. Double activation (click twice, Enter then click) sends one POST — verify: test fires two clicks before the mock resolves and asserts one completions POST.
7. "Recorded" appears only after the re-read: after a 201, before the `GET …/milestones/<id>` resolves the page shows "Checking the record…" and not "Milestone recorded"; when the re-read fails (`reread-fail`) the page shows "couldn't confirm it yet" with "Check again", never "recorded", and "Check again" issues only a GET — verify: test with a deferred re-read, then the `reread-fail` mock case; asserts no second POST.
8. The Recorded view's name, date and "Proof version" come from the re-read body, not the 201 — verify: test serves different `name` casing/`proof_version` in the re-read and asserts the re-read values are shown; a re-read whose `name` differs from the written name does not show "recorded".
9. A 409 keeps the person's input and reloads: after `conflict` the options are re-read once with `?name=`, the new `revision` is used on the next press, the chosen proof, uploaded PDF and ticked boxes remain, the 409 message shows, and no POST is made until the person presses again — verify: test counts requests (one POST, one options GET) and asserts the form state; then press and assert the second POST carries the new revision.
10. An uncertain failure (network error or 503) shows "We couldn't tell whether this was recorded" and sends no second POST on its own (wait past a fake-timer advance of 60 s) — verify: test with `uncertain` and fake timers asserts one POST total. "Check again" issues a GET options only; for `uncertain-saved` it says a completion with this name is now recorded and does not show "Milestone recorded" for this press; for `uncertain` it says it wasn't recorded and returns the form with input kept.
11. 403 on the write shows "You can't mark this milestone complete." and keeps input; 404, 401, 400/422, 413, 415 and 429 show their wording above; 401 shows `SignedOutState` — verify: one test per status using a `fetch` stub.
12. Options read 403/404/5xx/guard failure on the page shows the no-access card or `WorkErrorCard` with Try again, and no control; no partial data is drawn — verify: tests with the `forbidden`, `notfound` cases and an invalid body (missing `can_attach_pdf`).
13. Completion never starts an invoice: no "Start the invoice", "Chidi drafts", "invoice started" or invoice number appears on the page in any state, and the page issues no request to any `billing-invoices` or work-start route — verify: `grep -rniE "start the invoice|chidi" frontend/src/features/projects/MilestoneComplete.tsx` has no match; test asserts the Recorded text equals the "What happens next" wording and the fetch log has only the files POST, completions GET/POST and milestone GET.
14. The Milestones tab shows "Mark complete" only on rows with `completed_at: null` and only when the tab's unnamed options read gives `can_complete: true`; the link goes to `…/milestones/complete?name=<encoded label>`; a hold shows its reason once above the table; an options-read failure leaves F-71's table and completions unchanged — verify: extend `tests/milestones.test.tsx` (F-71's file) with these cases; a completed row never has the link.
15. No name in the URL shows "Choose a milestone from the Milestones tab." and makes no request — verify: test with an empty `name` and an over-200-character `name`; assert `fetch` call count 0.
16. A "Show more" on proofs requests `?name=<name>&page=2` and appends without duplicating ids — verify: test with `paged`.
17. Every mock body served for the new routes validates against `contracts/psl-factory.openapi.json` 1.24.0 — verify: new Ajv test, as in `tests/mock-live-projects.test.ts`, covers each case above.
18. Phone (390 px): one column, "Mark complete" at the foot, 44 px tap targets, no horizontal scroll — verify: browser check of `/projects/<id>/milestones/complete?name=…` at 1440 and 390 against `SCR-19-desktop` and `SCR-19-mobile`.
19. Live smoke (integration owner), Django 8010: with an account whose options read gives `can_complete: true`, one real completion records, the re-read returns the same `id`, and a second visit shows `name_in_use`; with an account that gets `can_complete: false` there is no control — verify: recorded in build.md with the account names and responses.
20. LB-2 is named in the PR description as flagged: "PMO Lead enforcement on POST milestones/completions is unconfirmed server-side; the screen follows `can_complete` and invents no role rule" — verify: the PR body contains the text, and `delivery/connect/backend-questions.md` "New from lanes" has an LB-2 line (the coordinator adds it if missing).

## Out of scope
- Invoicing: starting, drafting or linking an invoice, stage amounts, a Finance handoff id, and any read of department handoffs (B-30: it may appear later; no endpoint is promised for this screen). The Recorded view makes no claim that a handoff exists beyond what the fixed sentence says.
- Edit, revoke or correct a recorded completion (no route exists).
- The SCR-38 change-to-milestone link (`change-milestone-link`) and the invoice, cash-lot and correction pages.
- Any role or PMO Lead check in the UI; any "PM only" wording.
- Choosing a milestone by id, editing the milestone name, or setting the completion date by hand (the server sets the time).
- A file download or preview of the proof (the contract has no route for the completion proof).
- Creating native proof evidence other than the private PDF upload.
- Changes to `src/api`, `src/shell`, `src/features/workspace`, or the v7 `useEvidenceUpload`.

## Conflicts with the boards
Build option 1 by default (D-182 pattern); the design engineer decides once before the build starts.
1. **Invoice text.** Board: "Chidi drafts the stage 2 invoice from the SOW terms… Finance reviews it; a Finance Lead approves it before anything goes to the client" (desktop), "Next: Chidi drafts the invoice… for Finance to review" (phone). D-187 says handoff only, Finance starts the invoice.
   - Option 1 (recommended, built): replace with the fixed "What happens next" wording above and keep "Completing a milestone is not invoicing it. PMO completes milestones; Finance handles invoices."
   - Option 2: keep the board text. Rejected: it claims an automatic draft that D-187 forbids.
   - Option 3: remove the whole block.
2. **Proof choice and hold states (added).** The board draws one fixed evidence row ("Client UAT sign-off · recorded on REL-0077 … proof lagoon-uat-signoff.pdf · Uploaded · 240 KB") and no disabled or hold state.
   - Option 1 (recommended, built): a radio list of existing proofs by `label`, an optional private PDF zone only when `can_attach_pdf`, a second checkbox for an uploaded PDF, and a plain hold line with no control.
   - Option 2: PDF upload only. This drops the existing proofs the API offers and the common case.
   - Option 3: existing proofs only. Rejected: `proof_required` would then have no way forward.
3. **Evidence detail and recorder.** Board: "recorded on REL-0077", "Recorded by Tunde Bello on 11 Nov with proof …" and "with your name". The options read gives only `label`; the recorder is not in the write or the re-read.
   - Option 1 (recommended, built): show the `label` only and say "with the proof you chose"; show no recorder name or REL id.
   - Option 2: ask the backend (new question) for recorder and source reference; not built now.
4. **"Completed on 11 Nov 2026" and "Milestone 2 · UAT sign-off / From the signed SOW v2, stage 2".** Live sets the time itself and the options read has no number or SOW version.
   - Option 1 (recommended, built): before recording show only the name; after the re-read show "Completed <completed_at>". The stage number and SOW version are omitted.
   - Option 2: pass `position` in the link from the Milestones tab and show "Milestone N" (a stage number already read from `/money`). Small and safe; not built unless the design engineer asks.
5. **Entry button.** SCR-38 board draws a per-milestone "Mark milestone N complete" with a disabled reason. F-71 left it out for SCR-19.
   - Option 1 (recommended, built): a "Mark complete" link per uncompleted row only when the tab's options read gives `can_complete`, with the one hold reason as a single line above the table.
   - Option 2: a disabled button with the reason on every uncompleted row. Needs one options read per row (the name decides `name_in_use`), so not built.
6. **"I confirm… as the SOW describes it" and the Mark complete button** are built as drawn. No conflict.

## Assumptions
- **LB-2 (flagged for the PR, a backend open item):** whether `POST milestones/completions` enforces the PMO Lead as PSL decided on 23 Nov. The screen shows the control only when `can_complete` is true and sends the write otherwise unchanged. If the server returns `can_complete: true` to a PM who is not the PMO Lead, that is a backend gap and not a UI fault. The UI has no role logic.
- The `checked: true` field in the PDF variant is read as the person's own confirmation that they checked the uploaded file (hence the second checkbox). The contract does not define it. If it means a server-side scan, the checkbox is wasted but harmless; raise as a backend question with LB-2.
- The unnamed options read for the Milestones-tab entry gives the project-wide `can_complete` and `hold` (the `name` query is optional). `name_in_use` is only knowable per name, so it is never shown on the tab; the page shows it.
- Uploads use the existing `POST /api/v1/cases/{case_id}/files` (private, current case, no `case_revision`). An uploaded file that is not then used stays on the case, as with every private upload; the screen says nothing of deletion.
- The completion name is the `/money` stage `label`, as B-28 says to use the expected name from the native project flow. A stage whose label differs from the configured milestone name returns a refusal from the server, shown as the 400/422 message.
- No idempotency key is available, so a repeat after an uncertain failure is only allowed after a re-read of the options and only by a deliberate press.
- The Recorded view makes no read of the department handoffs, because no handoff id is returned (B-30) and the board's invoice link is out of scope under D-187. It can be added later by reading the handoffs list.
- Page layout on desktop follows the board's single-column card (max width as SCR-19) inside the app shell; the phone variant puts "Mark complete" in a bottom bar as `SCR-19-mobile`.
