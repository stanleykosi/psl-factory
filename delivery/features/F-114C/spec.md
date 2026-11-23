# Go-live document review records the reviewer's verdict on the exact version

> Tasks: FE-DELIVERY-RELEASE (part 3; part 1 is F-114, part 2 is F-114B). Architecture: v9 package (revision as pinned in the feature record at branch time); contract `contracts/psl-factory.openapi.json` 1.25.0 (lane-d worktree). Design: approved 13 Nov canvas under the recorded exceptions in `design/review.json`; screens: SCR-45 (the "Open the document review" part of boards SCR-45-desktop and SCR-45-mobile; no board draws the review form itself).

## Summary
- The form, its wiring and its tests are built now: a reviewer chooses approve, return or reject, gives a note, and the page sends `POST /work/{id}/reviews` with `kind: "document"` and refetches.
- **The live write is held.** In API 1.25.0 no read a non-PM reviewer can call supplies `version_id` or a review task for line `delivery-go-live/v1` (see Context). The builder does not type, guess or borrow an id. The live page therefore shows no review control until the backend answers Question 1. The change is one function (`readReviewSubject`) that returns `null` today.
- Everything else is real: the form and the error words are tested against fixtures at component level, and an e2e check proves the control stays absent on the live-shaped work read.
- Waits (delay the build start only): F-114 (page `/work/{id}/go-live` and the mock), F-85 (shared frame), F-87 (`Actions` slot and `useWorkCommand`). F-114B edits the same page; this feature adds only its own files and must not edit F-114B's.
- High risk; merge goes to the design engineer's batch. Nothing is sent to the client from this page.

## Context
- No review UI exists. F-114 owns `frontend/src/features/go-live/**` and `frontend/src/app/work/[id]/go-live/page.tsx`; F-87 adds `LineAdapter.Actions?: ComponentType<LineActionsProps>` (`{readback, ctx, commands, reload}`) and `useWorkCommand`. F-89's `WeeklyReportActions.tsx` is the pattern.
- Server: `apps/core/factory_api/reviews.py` `review()` takes `kind: document`, calls `DOCUMENTS['delivery-go-live/v1']` = `apps/workflows/factory_go_live.py` `review(actor, work_id, expected, case_expected, version_id, verdict, note)`. It rejects with `STALE_VERSION` unless `work.revision == expected_revision`, the work has no lease or cancel request, and `version_id` is the go-live document version the work holds. It then records the decision through `review_version` and wakes the waiting work. Who may review, and independence from the author, are the server's decision.
- **Where `version_id` can be read, checked in the contract and the code:**
  - `GET /work/{id}` gives `revision` and `case_revision` (these are the request's `expected_revision` and `case_revision`). Its `tasks[]` items carry `{id, kind, role, status, revision, claimed_by_you, can_claim, can_decide, verdicts, url}` and no version id. `apps/core/factory_api/work.py` (about line 484) fills `tasks[]` only for `finance-invoice` and `finance-accounting`; for the go-live line it is `[]`. `actions[]` only ever holds `background`, `reconcile`, `release_invoice`.
  - `GET /work/{id}/go-live-signoff` gives `version_id` but only to the appointed PM, and only after the document is delivered (`go_live()` calls `factory_go_live.published`). The review happens before delivery, so this read does not exist yet when review is needed.
  - `GET /work/{id}/go-live-replies` lists `replies[].version_id`, which are versions a client has replied to, not the version awaiting review.
  - `GET /projects/{case_id}/document-versions` lists standalone report versions (`status_report` templates without minutes, forecast or finance bindings). Nothing in it says which version belongs to this go-live work, so choosing from it would be guessing.
  - Result: no read gives a non-PM reviewer `version_id`. Typing it is not allowed. The write is held (readiness Scope, DC-5).

## Contract
### Operation (API 1.25.0, unchanged by this feature)
`POST /api/v1/work/{work_id}/reviews`, `X-CSRFToken` through `liveApi`.
- Request: `{kind: "document", expected_revision, case_revision, version_id, verdict: "approve"|"return"|"reject", note}`; `note` is a string, 0 to 4000. No other key is sent (`additionalProperties: false`). No `evidence_id`, so the PSL proof rule has nothing to add.
- Response 200: `{work_id, state, revision, review_id}` (`review_id` may be null; show the result without it then).
- Errors: 400/422 show the first `fields[].message` or `message` (a 422 `STALE_VERSION` text is shown as it comes); 403 `csrf_failed` refreshes the session once and says "Press the button again" (nothing was sent); 403 otherwise and 404 show "This record is unavailable." (same for missing and not yours, as F-85); 409 "This changed while you were working. We reloaded it. Check it and try again."; 429 "Try again shortly."; 503 and network "We couldn't reach the server. Nothing was recorded."; a lost response after send reads the work again and says "Check the record before trying again", with no automatic retry. Same words as F-114.
- Idempotency: none. The button is disabled while a call is in flight and after a 2xx until the work read is refetched. Versioning: 409 or `STALE_VERSION` means someone changed the record; the next press sends a fresh body with the new revisions.

### Where each request value comes from
- `expected_revision` = `GET /work/{id}` `revision`; `case_revision` = the same read's `case_revision`. Both are read at send time from the latest read, never cached across a refetch. Per F-85, revisions and the idempotency key are not passed inside `inputs` to `makeCommand`; use the F-87 command path.
- `version_id`: only from `readReviewSubject(readback)` in `frontend/src/features/go-live/reviewSubject.ts`. Today it returns `null` for every real read. When the backend answers Question 1, this function is the only code that changes. It returns `{version_id, task_id|null, verdicts[]}` or `null`.
- Which verdicts to offer and whether to offer the control at all: the control shows only when `readReviewSubject` returns a subject and the supplying read says this caller can decide (for a `tasks[]` item: `can_decide` true; offered verdicts are the item's `verdicts[]`, nothing else). The person's role is never used to decide access.

### Screen states of the review form (inside the go-live page's `Actions` slot, `GoLiveReviewActions.tsx`)
- Absent (live today): `readReviewSubject` is `null` or the caller cannot decide. Nothing is drawn, no placeholder text about reviewing. This is the state every live read produces in 1.25.0.
- Loading: the work read is loading; the form is not drawn.
- Ready: heading "Review the go-live document", the version under review ("Version {version_id}" only; no title, template or preview, because no supplied read gives them), a choice of the offered verdicts (none preselected), a note box (max 4000 characters, counter), and one submit button "Record my review". The button stays off until a verdict is chosen. For return and reject the note must have non-blank text; for approve it is optional and the API's 422 text is shown if it needs one.
- Sending: button disabled, "Recording...".
- Success: the form is replaced by "Review recorded: {Approved|Returned|Rejected}" and, when `review_id` is not null, "Review {review_id}". The page then shows the refetched work `state` and `status_label`. The text says nothing about what is sent to the client; the system does that afterwards.
- Error: the words above, inline above the button; the typed verdict and note stay.
- Mobile (390 px): the form is one column, verdict choices stacked, full-width button, no horizontal scroll.

### Fixtures (mock, port 4991; builder creates `frontend/mock/go-live-review.mjs` and registers it in `frontend/mock/server.mjs` with one line; ids are free, the shapes are the contract)
The mock must not add a field that API 1.25.0 does not have to a real read shape. The review subject for the fixtures is passed to the component in unit tests and, for e2e, injected through a test-only seam in `readReviewSubject` that is compiled out of the production build and named in build.md.
- `4601` not reviewable: work read with `tasks: []` (the real 1.25.0 shape). The control is absent.
- `4602` reviewable: subject `{version_id: 5120, verdicts: [approve, return, reject]}`, work `revision` 7, `case_revision` 12.
- `4603` not the reviewer: subject present, `can_decide` false. The control is absent.
- `4604` approve 200: `{work_id: 4602, state: "waiting", revision: 8, review_id: 9001}`.
- `4605` conflict: the POST answers 409 once, then 200.
- `4606` stale: POST answers 422 `STALE_VERSION: refresh current go-live work`.
- `4607` 404 on the work read ("This record is unavailable.").
- `4608` return and reject: same shape as `4604`, with a note required.

## Lanes
- Frontend lane (owner): `frontend/src/features/go-live/GoLiveReviewActions.tsx`, `reviewSubject.ts`, their tests under `frontend/src/features/go-live/`, `frontend/mock/go-live-review.mjs`, and an e2e `frontend/e2e/go-live-review.spec.ts`. One registration line to add `GoLiveReviewActions` to the go-live adapter's `Actions` once F-87 is on main.
- Shared files and owners: `frontend/src/features/go-live/*` (page and adapters) belongs to F-114; F-114B edits the same page. This feature adds files and one registration line only, and does not reformat or move F-114/F-114B code. `frontend/mock/server.mjs` registration: one line, named in build.md. `src/features/workspace/*` and `src/features/work-item/*` are lane C's and are not changed. Never add the `Actions` slot.
- Backend lane: none. No contract edit. The version source is a backend question (Question 1) in `delivery/connect/backend-questions.md`.
- Integration owner: lane D coordinator. Protected paths in `delivery/config.json` stay unchanged.

## Acceptance criteria
1. On the live-shaped work read (`4601`, `tasks: []`) the go-live page shows no review control and no error — verify: `cd frontend && npx playwright test e2e/go-live-review.spec.ts` (Next 4990, mock 4991) asserts the heading "Review the go-live document" is absent.
2. `readReviewSubject` returns `null` for the real 1.25.0 work read and for the go-live-signoff and go-live-replies reads; no code path takes `version_id` from user input, a URL parameter, or `document-versions` — verify: unit test on the function; `grep -rn "version_id" frontend/src/features/go-live/GoLiveReviewActions.tsx` shows it only as a prop.
3. With a subject (`4602`), the form shows "Version 5120", the three verdicts unselected, and the button is off — verify: component test and e2e screenshot at 1440 and 390 px.
4. A subject that is present but `can_decide` is false (`4603`) draws nothing — verify: component test.
5. Only the verdicts in the subject's `verdicts[]` are offered; a subject with `[approve, return]` offers no reject — verify: component test.
6. Approve sends exactly `{kind:"document", expected_revision:7, case_revision:12, version_id:5120, verdict:"approve", note:""}` with the work read's revisions and no other key — verify: unit test on the request body.
7. Return and reject with a blank note do not send and say a reason is required; with text they send the note unchanged — verify: component test counts calls.
8. After a 200 the form shows "Review recorded: Approved" and `review_id` when present, the work is refetched once, and the page shows the refetched `state`; with `review_id: null` it shows the result without an id — verify: e2e with `4604`; unit test on null.
9. A double click on "Record my review" sends exactly one POST — verify: unit test with a slow mock counts calls.
10. A 409 (`4605`) shows "This changed while you were working. We reloaded it. Check it and try again.", re-reads the work, keeps the typed note, and the next press sends the new revisions — verify: e2e compares revision values in the two POST bodies.
11. A 422 `STALE_VERSION` (`4606`) shows the server's text inline and records nothing — verify: component test.
12. Wrong user or wrong tenant: a 404 on the work read (`4607`) and a 403 on the POST both show exactly "This record is unavailable." with no difference between them and no form — verify: e2e and mapper unit test.
13. A 403 `csrf_failed` refreshes the session once and says "Press the button again"; no second POST is sent automatically. A lost response says "Check the record before trying again" after re-reading the work, with no automatic retry — verify: unit tests count calls.
14. The control is not drawn for a work item on any line other than `delivery-go-live/v1` — verify: unit test with another `line`.
15. Nothing on this page sends, publishes or previews the document to the client; no "send" control exists — verify: e2e asserts the text and controls list.
16. No Tola, agent step or "ask the agent" wording appears (D-182) — verify: `grep -rni "tola" frontend/src/features/go-live/GoLiveReviewActions.tsx` returns nothing.
17. `git diff --name-only origin/main...HEAD` contains no file under `frontend/src/features/workspace/`, `frontend/src/features/work-item/`, none of F-114's or F-114B's files other than the one registration line, and none of `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json` — verify: command output.
18. build.md lists the held write, the test-only seam, the one-line `server.mjs` change, and each board part hidden — verify: file content.

## Out of scope
- Everything F-114 and F-114B own: sign-off, replies, decline, successor, the milestone, corrections of replies.
- Other `reviews` kinds (`bid`, `closure`, `asset`, `schedule`, `payroll`, `business_unit`) and `POST /work/{id}/corrections`.
- Publishing or sending the document, previewing its text, `document-reviews/{version_id}` reads and their publication endpoint (system-reserved or another screen).
- Finding `version_id` from `document-versions`, the project Documents tab, a URL, or from the PM's signoff read. Do not pick "the current one".
- Inventing a `tasks[]` entry, a field or an action in the mock that the live read lacks, or deciding access from the person's role.
- Agent steps and Tola wording (D-182); `POST /setup/{case}/policy-configurations/{id}/review`.

## Assumptions
1. The live write is held, not guessed. Reason: no 1.25.0 read gives a non-PM reviewer `version_id`, and the readiness Scope says to hold and say so.
2. The form is built now behind `readReviewSubject`. Reason: it removes the build risk later and the e2e proves the control stays absent today.
3. Return and reject require plain-text note on our side; approve does not. Reason: readiness Scope; the API accepts an empty string.
4. The version is shown as "Version {version_id}" only. Reason: no supplied read gives title, number or preview for it.
5. `revision` and `case_revision` come from `GET /work/{id}`, matching the server's check in `factory_go_live.review`. Reason: the work read supplies both for every line.
6. Result wording ("Review recorded: Approved/Returned/Rejected") and the button label "Record my review" are the builder's plain words. Reason: no board text.
7. The test-only seam for e2e is acceptable as long as it is compiled out and named. Reason: no real fixture can supply a subject while the backend has none.

## Questions
1. **Where does a non-PM reviewer read the go-live document's `version_id` and review task?** (a) The backend adds the go-live document review to `GET /work/{id}` `tasks[]` for this line, with an exact `version_id` field next to `can_decide` and `verdicts` (recommended: follows the existing task shape and the DC-5 rule, and `readReviewSubject` becomes a small mapping). (b) The backend returns the reviewable `version_id` and the caller's `can_decide` on a go-live read that reviewers can call before delivery, such as a field on `go-live-replies`. (c) The builder lists `document-versions` and the reviewer picks (not recommended: nothing links a version to this work, so a wrong pick would review the wrong document). Context: until answered the live page shows no review control; this goes to `backend-questions.md`.
2. **Who may review, in plain words?** (a) Show nothing about who; the server decides and the control appears only when the read says this caller can decide (recommended). (b) Add a line "Reviewed by someone other than the author" (needs a read that supplies the rule). Context: independence is a server rule; no read states it.
3. **Is the held write acceptable for this PR?** (a) Merge the built form with the live control absent, and switch it on in a small follow-up when Question 1 is answered (recommended). (b) Hold the whole feature until the backend answers. Context: (a) keeps the page final, with one function to change.

## Conflicts with the boards
1. The boards draw "Open the document review" and the document version "in review" on the go-live page. This spec draws the form only when a read supplies the review subject, which no live read does today, so on live data it is hidden. Recommendation: accept; revisit after Question 1.
2. The boards draw no review form (verdicts, note, button), no confirmation text and no error states. The spec adds them as plain controls using the existing form styles. Recommendation: keep; the design engineer draws or approves a board before release (Question 2/3 context).
3. The document's title, attachments (checklist, incident plan, rollback plan) and "sent" details on the boards are not supplied by any read before delivery. Recommendation: hide; show "Version {version_id}" only.
4. Any Tola card or agent step beside the review is not drawn (D-182). Recommendation: hide.
