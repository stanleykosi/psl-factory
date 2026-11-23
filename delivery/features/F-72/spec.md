# Document review reads and records its decision through the live document-review API

> Tasks: FE-CONNECT-1. Architecture: live contract `contracts/psl-factory.openapi.json` (API 1.22.0; D-180 connection push, `delivery/connect/LANES.md`). Design: approved canvas as already built in F-29, no new board; screens: SCR-08 (states: loading, no access, error, ready, returned, approved, stale, uncertain).

## Summary
- `/projects/[caseId]/documents/[documentId]` reads `GET /api/v1/projects/{case_id}/document-reviews/{version_id}` (and, for the status word and blockers, `GET .../publication`) instead of the v7 `E-DOCUMENT` and work-item reads. `[documentId]` is now the integer live `version_id`; `?v=` is gone.
- Approve and Return record through `POST .../document-reviews/{version_id}` with `{expected_revision, verdict, delegated:false, note}`. The claim step is removed. Only verdicts present in `decisions[]` are offered; no Reject button (B8 default).
- The note is required (1 to 4000 characters) for Approve as well as Return (B8 default).
- Parts with no live source are dropped, not replaced (B7 default): section notes, "changed since" marks, Compare, the per-check list, who/when/note on the returned banner, the reference in the crumb, TEST TEMPLATE.
- The v7 mock is moved to the live shape for this one route and validated against the live contract, so design review keeps working.

## Context
Built today (F-29, DONE), all on v7:
- Route `frontend/src/app/projects/[caseId]/documents/[documentId]/page.tsx` renders `DocumentReviewPage` (`frontend/src/features/documents/DocumentReview.tsx`) with `?v=<n>`.
- `useDocument.ts` calls `api.GET('/api/v1/documents/{document_id}/versions/{version}')`; `documentModel.ts` holds the v7 view (`DocumentView`, `isDocument`, `parseVersion`, `documentHref`, check and returned helpers, `noteProblem`); `DocumentParts.tsx` draws sections, notes, `ChecksPanel`, `ReturnedBanner`, `AgentPanel`; `ReviewControls.tsx` draws the controls with the claim states.
- The decision runs through `frontend/src/features/decide/useDecision.ts` (work item, `claim`, `decide`). That hook and the decide page are not touched.
- The Documents tab (`frontend/src/features/projects/DocumentsTab.tsx`, F-70's area) links rows with `documentHref(caseId, row.document_id, row.version)` when the row has a `work_id`.
- Tests that move: `tests/document-review.test.tsx`, `tests/document-review-model.test.ts`, `tests/mock-document-review.test.ts`, `e2e/document-review.spec.ts`. Mock: `frontend/mock/documents.mjs`, routed in `frontend/mock/server.mjs` (E-DOCUMENT at ~line 396).
- Live client pattern from F-56/F-57: `liveApi` in `frontend/src/api/client.ts` (typed by `src/api/live-schema.d.ts`), `call(...)`, `ApiError` kinds in `src/api/errors.ts` (409 = `stale`, 422 = `invalid` with `fields`, 403 = `forbidden`, 403 `csrf_failed` = `csrf`).
- Live reads (`documents_preview`): `{title, version:int, revision:int, audience, current:bool, decisions:string[], django_url, preview:[{field,text}]}` (all required, no extras). `documents_report_controls` (`.../publication` GET) gives `review_status` (string or null), `findings` (strings), plus fields this feature ignores.

## Contract

### Route and entry
- Route stays `/projects/[caseId]/documents/[documentId]`; `documentId` must match `^[1-9][0-9]{0,18}$` (the live `version_id`, 1 to 9223372036854775807). Anything else shows the "You can't open this document" state with no request sent. `?v` is ignored. The latest version is never guessed.
- `caseId` goes through the existing `routeCaseId` helper. The live case id is a UUID; the mock also accepts `P-nnnn` and its UUID.
- Entry from the Documents tab (B-7, no defensible link): the live tab row gives only an evidence `record_id` ("Version 2"), which is not stated to be a version id, so it is not used. The one defensible reading is the row's own `api_url`: a row links to review only when `api_url` is exactly `/api/v1/projects/{this case_id}/document-reviews/{n}`; the page opens `/projects/{caseId}/documents/{n}`. Any other row (no `api_url`, other path) is plain text, as a row without a `work_id` is today, and the PR lists "Documents tab entry to SCR-08: held, no live link to a version id (backend question B-7)". The builder runs the live Documents tab for a seeded project and records in `build.md` whether any row matches. If none do, direct URL is the only live entry. This is flagged for the backend answer, not worked around.
- The work item as an entry path is not built: no live read ties a work item to a `version_id`, and Lane C owns `src/features/work-item`.

### Reads (`useDocument.ts`, rewritten on `liveApi`)
1. `GET /api/v1/projects/{caseId}/document-reviews/{documentId}` is required. Response is checked for `title` (string), `version` (integer), `revision` (integer), `audience` (string), `current` (boolean), `decisions` (array) and `preview` (array of `{field,text}`); a 200 that fails the check is the error state, not a half page.
2. `GET .../document-reviews/{documentId}/publication` supplies `review_status` and `findings`. It runs in parallel and is non-fatal: if it fails, the page shows without a status tag and without blockers, and nothing else changes. Its other fields (`editable`, `publication`, `delivery`, `can_request_review`) are not read or shown.
3. `django_url` is never used or rendered.
4. Each open of a version is one read pair. A late answer for an earlier id is ignored. `refresh` re-reads both without clearing the page and never sends. No polling, no automatic retry.
5. Errors: 401 signed-out state; 403 and 404 look the same ("You can't open this document", nothing about the document, no server message); 409/422/5xx/network the error card with Retry ("We couldn't load this document. Your work is safe; nothing was changed.").

### Write (`documents_decide`)
`POST /api/v1/projects/{caseId}/document-reviews/{documentId}` with `X-CSRFToken` (the shared middleware), body exactly:
```json
{ "expected_revision": 7, "verdict": "approve", "delegated": false, "note": "Figures match the costing." }
```
- `expected_revision` is `revision` from the latest GET. `verdict` is `approve` or `return` only. `delegated` is always `false` (B-11 best reading: an ordinary reviewer; the builder never sets it any other way and the PR names this). `note` is what the person typed, 1 to 4000 characters, not blank after trimming.
- 200 `{review_id, verdict}`. The page then re-reads both reads and shows the result from them, not from the 200: a toast "You approved v{version}. Not sent to the client." or "You returned v{version}." (no person or time: live gives none). If the re-read fails, show "We couldn't reload to confirm it was recorded" with Try again (a re-read only).
- One write at a time (both buttons disabled while one is in flight). A write is never repeated automatically, and Try again never re-sends.
- 409 (`stale`): nothing recorded; re-read both; callout "This document changed while you were reading it, so nothing was recorded. We've loaded the latest; check it and press again." The typed note stays in the box.
- 422 `action_unavailable` (findings remain, or the verdict is no longer offered): nothing recorded; show the server message in a callout and re-read both; the controls follow the new `decisions[]`. A 422 with a `note` field error shows on the note field. Other 422 shows the server message.
- 403 on the write: callout "You can't record a decision on this document." and a re-read (the controls go if `decisions[]` is now empty). 403 `csrf_failed`: the client's refresh wording, nothing recorded.
- Network failure or 5xx on the write: the uncertain state (reuse `UncertainNotice` from `features/decide/DecideStates.tsx` if its wording fits, else a one-line equivalent): "We couldn't confirm whether your decision was recorded." Buttons stay off until a re-read answers; the re-read shows the truth.
- No idempotency key exists in the contract; none is sent.

### Screen states (SCR-08)
- Loading: existing `LoadingState`.
- No access: existing `DocumentNoAccess`.
- Error: `WorkErrorCard` with Retry.
- Ready: header with crumb, `{title} · v{version}`, tab bar, one status tag; sections from `preview[]` (`field` as the numbered heading, `text` as plain-text paragraphs split on blank lines, no markup); `audience` as the one fact in the aside where the audience is drawn; the review controls when `decisions[]` contains `approve` or `return`.
- Empty sections: `preview` empty shows "This document has no sections yet."
- Returned / not decidable: `decisions[]` has neither verdict: no controls and one line "No decision is open to you on this version." The status tag shows `review_status` text as sent. No banner with person, time or note. The "Edit as v{n+1}" held button stays held as today.
- Not the latest: `current: false` adds a neutral tag "Not the current version" beside the status tag; controls still follow `decisions[]` only.
- Blockers: when the publication read gives a non-empty `findings[]`, the aside lists those sentences as plain text under "Not ready to decide yet". Nothing is computed from them.
- Approved/returned, stale, unconfirmed states as under Write.

Fixture examples (live shape, these are the mock bodies):
```json
// GET .../document-reviews/2901  (ready, decidable)
{"title":"Statement of work","version":2,"revision":7,"audience":"Client · Lagoon Health","current":true,
 "decisions":["approve","return"],"django_url":"/legacy/unused","preview":[{"field":"Scope","text":"First paragraph.\n\nSecond paragraph."},{"field":"Fees","text":"..."}]}
// GET .../publication  (blocked)  review_status:null, findings:["Section Fees is empty."]  ; decisions:[] on the preview
// POST ok -> {"review_id":55,"verdict":"approve"}
// POST stale -> 409 {"code":"stale_revision","message":"..."}   POST blocked -> 422 {"code":"action_unavailable","message":"..."}
```

### Note rule (`noteProblem`)
One rule for every verdict: blank after trim is "Add a note to record your decision."; over 4000 is "Keep the note to 4000 characters or fewer." Checked before any request.

### Mock (contract mock only)
`frontend/mock/documents.mjs` and `mock/server.mjs` serve the two GETs and the POST in the live shape above for the existing demo document (integer version id, e.g. 2901 for v2), with scenarios: decidable (approve+return), blocked (findings, empty decisions), returned (`review_status` text, empty decisions), not-current, empty sections, 403/404 (the reserved no-access id), 409 on a stale `expected_revision`, 422 `action_unavailable`, and a write that records then changes the next GET. A new `tests/mock-live-document-review.test.ts` validates every served body against the live contract with Ajv2020 + ajv-formats (pattern of `tests/mock-live-me.test.ts`) and fails on any field the live schema forbids. The v7 `E-DOCUMENT` route and fixtures stay only if another screen still uses them (builder greps); otherwise they are removed with their test.

## Lanes
- Frontend lane (the builder, F-72): `frontend/src/features/documents/*` (`DocumentReview.tsx`, `DocumentParts.tsx`, `ReviewControls.tsx`, `documentModel.ts`, `useDocument.ts`, `document-review.css` as needed), `frontend/src/app/projects/[caseId]/documents/[documentId]/page.tsx` (param name only if changed), `frontend/mock/documents.mjs`, `mock/server.mjs` (the document routes only), `mock/fixtures/documents/*`, and the tests under Context plus the new `tests/mock-live-document-review.test.ts`.
- Backend lane: none. No file under `apps/`, `config/`, `legacy_ui/`.
- Integration owner: the builder, for the mock-to-contract test and the live checks below (`live-lead` and `live-none` accounts, Django 8010, Next 4970 live / 4971 mock, from `/Users/Hunchoo/psl-factory-worktrees/lane-b/frontend`).
- Shared files, each its own small commit named in `build.md`: `frontend/src/features/projects/DocumentsTab.tsx` (F-70's area; only the row link rule above) and `documentHref` use there. `src/api`, `src/shell` (lane A) and `src/features/workspace` (lane C) are not changed; if `liveApi` needs nothing new, none is touched. Protected paths (`delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json`) unchanged. If F-70 has already changed `ProjectBar`'s inputs (`useProject`, `ProjectTabs` props), follow F-70's version and make no change to those files.

## Acceptance criteria
1. The page reads the live preview by integer id and shows title, `v{version}`, audience and each `preview[]` item as a numbered section — verify: on the mock, open `/projects/P-0101/documents/2901`; the page shows "Statement of work · v2", the audience, and sections "Scope" and "Fees" with text as plain characters (a `<b>` in a fixture section shows literally); `tests/document-review.test.tsx` asserts the request path `/api/v1/projects/<case>/document-reviews/2901`.
2. An invalid id (`abc`, `0`, `2.5`, `02`, 20 digits) sends no request and shows "You can't open this document" — verify: `tests/document-review.test.tsx` asserts no fetch; `/projects/P-0101/documents/abc` in the browser.
3. 403 and 404 look identical and reveal nothing — verify: live as `live-none`, open a document URL of `live-lead`'s project (real case UUID and version id from the live Documents tab or database); and the mock no-access id; both show the same text with no title or id.
4. Controls follow `decisions[]` only — verify: with `["approve","return"]` both buttons show; with `["return"]` only Return; with `[]` no controls and "No decision is open to you on this version."; a test with `["approve","return","reject"]` shows no Reject button.
5. Approve sends exactly `{expected_revision, verdict:"approve", delegated:false, note}` to `POST .../document-reviews/{id}` and nothing is sent to `/tasks/*`, `/work/*` or any claim endpoint — verify: `tests/document-review.test.tsx` captures the body (all four keys, `delegated === false`, `expected_revision` equals the GET `revision`) and asserts no other POST.
6. The note is required for Approve and Return; checked before any request — verify: pressing Approve with an empty or blank note shows "Add a note to record your decision." beside the note field, focuses it and sends nothing; a 4001-character note shows the 4000 message and sends nothing (`tests/document-review-model.test.ts` for `noteProblem`, `tests/document-review.test.tsx` for the page). On a phone width (390) Approve opens the same note sheet as Return (see Conflicts).
7. After a 200, the page re-reads and shows the live result — verify: mock decidable then approve; a toast "You approved v2. Not sent to the client." shows, the next GET returns empty `decisions[]`, and the controls are gone and the status tag shows the new `review_status`. Return does the same with "You returned v2."
8. 409 stale keeps the note and records nothing — verify: mock scenario with a stale `revision`; the callout "This document changed while you were reading it..." shows, the page now carries the new revision, the note box still holds the typed text, and a second press sends the new `expected_revision`.
9. 422 `action_unavailable` shows its message and refreshes the controls — verify: mock blocked-after-load scenario; message shows, controls follow the new `decisions[]`, and `findings[]` sentences list under "Not ready to decide yet". A 422 with a `note` field error shows on the note field.
10. 403 on the write and an expired-CSRF write record nothing and say so — verify: mock 403 and `csrf_failed` scenarios in `tests/document-review.test.tsx`; the 403 shows "You can't record a decision on this document."
11. A network or 5xx failure on the write shows the uncertain notice, keeps the buttons off, and Try again only re-reads — verify: test counts POSTs (exactly one) and GETs after pressing Try again.
12. Double press sends one write — verify: test presses Approve twice quickly; one POST.
13. A failed publication read does not break the page — verify: test with `.../publication` answering 500; the document, sections and controls still show, without a status tag.
14. Dropped parts are gone and nothing replaces them — verify: `tests/document-review.test.tsx` asserts no TEST TEMPLATE text, no "changed since", no Compare control, no per-check Done/Held/Blocked list, no returned person/time/note, and no reference in the crumb; `matchingSources` (from `frontend/tests/source-files.ts`) finds no use of `django_url` in `src/features/documents`.
15. Crumb is the project title and "Documents" only, no reference — verify: mock page at 1440 and 390; the phone back link reads the project title with no reference note. If the project read fails the crumb is "Documents" alone and the page still works.
16. `current: false` shows "Not the current version" and `review_status` text shows in the status tag as sent, unquoted and unparsed — verify: mock not-current and returned scenarios.
17. A Documents-tab row links to review only when its `api_url` is exactly `/api/v1/projects/{this case}/document-reviews/{n}`; any other row is plain text, with a test for a row whose `api_url` names another case, another path, `//host/...` or null — verify: `tests/project-tabs.test.tsx` (or a new `tests/documents-link.test.ts`); live Documents tab run recorded in `build.md`.
18. The mock bodies validate against the live contract and a deliberately wrong fixture fails — verify: `npx vitest run tests/mock-live-document-review.test.ts` passes; adding a forbidden field to one fixture makes it fail.
19. Live end to end (integration owner) — verify: against Django 8010, as `live-lead` open a real document version URL, read it, and record one Return with a note; the next GET changes `decisions[]`/`review_status` and the database or API shows one new review; `live-none` gets the no-access state; record the commands and results in `build.md`. If no seeded document version exists in the live database, record that and mark this criterion held for a seeded fixture (backend), without faking data.
20. The E2E flow still passes on the mock — verify: `e2e/document-review.spec.ts` (rewritten) at 1440 and 390 covers read, return with note, approve with note, stale and no-access.

## Out of scope
- `.../publication` writes (revise, request review, publish, retry, cancel), receipts, delivery job state, editable fields and the packet: a separate feature. Only `review_status` and `findings` are read from the publication GET.
- A Reject button or any `reject` UI; "Edit as v{n+1}" stays the held button it is today.
- Compare, section notes, changed-since marks, the per-check list, who/when/note on a returned document, document reference, template name and TEST TEMPLATE: dropped, no placeholders.
- Any entry path from the work item or the assistant; changes to the decide page, `useDecision`, `src/features/work-item`, `src/features/workspace`, `src/api`, `src/shell`.
- Any change to the Documents tab beyond its row link rule; any change to the Money, Milestones, Registers or Actions tabs.
- Setting `delegated: true` for any reason; any value, policy or authority invented for a verdict.
- Backend changes, new endpoints, and the `django_url` field.

## Assumptions
- B7 and B8 recommended options are the defaults (drop parts; approve and return; note required on approve; no reject); product acceptance confirms or changes them.
- `delegated: false` for every write: B-11 is unanswered and this is the best reading for an ordinary reviewer; flagged in the PR.
- `[documentId]` is the live `version_id` and `?v` is retired: the live read has no document id or separate version number, and the old `?v` pair has no live meaning.
- The Documents-tab link rule uses the row's own `api_url` because it is the backend's own link and needs no guess; if live rows never carry that pattern, the entry is by URL only, flagged under B-7.
- The publication GET is read for `review_status` and `findings`: it is the only live source for the status word the readiness scope asks for, and the readiness scope says only that publication writes are out. Its failure is non-fatal.
- `findings[]` shown as a plain list is the smallest way to explain a 422 `action_unavailable`; it replaces nothing drawn (see Conflicts).
- `current:false` shows "Not the current version" as a neutral tag because readiness names `current` as something the reviewer reads; wording is the builder's plain-language choice.
- After a 200 the page trusts the re-read, not the response body, so the toast carries no person or time.
- A write that fails with a network error or 5xx is treated as possibly recorded (uncertain), per the product rule to reconcile before retry; the contract gives no idempotency key to make resending safe.
- Mock: v7 `E-DOCUMENT` stays only where another screen still uses it; if the v7 documents-tab fixture cannot carry an `api_url`, on the mock the review is entered by URL and the demo link from the tab is held the same way as live.

## Conflicts with the boards
B7 and B8 (already in `delivery/connect/questions-batch.md`) cover the dropped parts, reject and the approve note. This spec adds three more places where it changes what a board draws; the coordinator should append them to the lane B batch:
1. Phone Approve. The board's pinned bar Approve sends at once, with no note. With the note required, Approve on the phone opens the same sheet as Return (title "Approve with a note", button "Approve v{n}"). Recommendation: do this. Alternative: keep one-tap Approve and send a fixed note, which invents wording the reviewer did not write and is not recommended.
2. Desktop note label. The board reads "Note for the PM (needed to return)". With the note needed for both verdicts it reads "Note for the PM". Recommendation: change the label; no layout change.
3. Blockers list and "Not the current version" tag. Neither is drawn. The blockers list stands in for the dropped per-check panel only when live reports blockers; the tag shows only when `current` is false. Recommendation: keep both; they show nothing in the normal case. Alternative: show nothing and let the 422 message speak alone.
