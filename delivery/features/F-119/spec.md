# A person records the project retrospective as a saved version and sees where it stands in the closure checklist

> Tasks: FE-DELIVERY-CLOSURE. Architecture: v9 package, live contract `contracts/psl-factory.openapi.json` 1.24.0 (origin/main b8542c79). Design: approved 13 Nov canvas under the recorded exceptions D-173/D-181 in `design/review.json`; screens: SCR-33 (`design/canvas/project/SCR-33-desktop.dc.html`, `SCR-33-mobile.dc.html`; 2 boards).

## Summary
- New page `/projects/[caseId]/retrospective` reads and writes the project's retrospective through the live project-meetings operations (`kind:"retrospective"`). Every save is a recorded version; there is no draft.
- The three boxes (What went well / What didn't / Lessons for next projects) are packed into the single `summary` as three headed sections (D-8) and parsed back out on read. A summary with no recognisable headings is shown whole.
- The closure checklist strip shows the retrospective check and names the exact `version_id` the checklist used (D-9), never "the latest".
- A lesson can become a follow-up project action (`POST /actions/create` with the meeting id).
- **No dependency on F-85.** This screen reads and writes project meetings, not a work line. It does not use `GET /work/{id}`, the per-line adapter (`src/features/workspace/adapter.ts`) or the F-85 `EvidencePicker`. It uses only the live client already on main (`liveApi`, `call`, `refreshSession` in `frontend/src/api/client.ts`). It can be built before F-85 (PR #101) merges. It does not edit `src/features/workspace` or `DeliveryTab.tsx`.

## Context
- No retrospective code exists. `frontend/src/app/projects/[caseId]/(tabs)/[tab]/page.tsx` serves the project tabs from `PROJECT_TABS` (`src/features/projects/model.ts`); a static `retrospective` segment beats that dynamic `[tab]`, so the new route does not collide and does not become a tab.
- Live operations (inspect with `python3 /Users/Hunchoo/psl-factory-main/delivery/connect/oa.py live GET /api/v1/projects/{case_id}/meetings 3`; the viewer needs the full `/api/v1/` prefix). Types are already generated in `src/api/live-schema.d.ts` (`meeting_records_collection`, `_record`, `_detail`, `_options`, `_create_action`, `_link_action`, `closure_checklist`).
- Backend behaviour read in `apps/core/factory_api/meeting_records.py` and `apps/pmo/meetings.py`: a first save needs a unique `reference`; a later save passes the same `meeting_id` and the same `reference` and appends version n+1; `create_action` with `meeting_id` already links the action to the meeting; `options` answers 403 when the viewer holds neither `meeting.record` nor `action.manage`.
- F-118 (closure view) shows the checklist and links to this screen from the retrospective row via the checklist's `retrospective_url` (an API url). The page route for that link is defined here (below); F-118 maps `retrospective_url` to it.
- Frame pieces to reuse by name from `src/components`: `Panel`, `PageTitle`, `Breadcrumb`, `Field`, `Select`, `Checkbox`, `DateField`, `Callout`, `Button`, `Disclosure`, `ShowMore`, `Loading`, `SampleLabel`.

## Contract

### Route
`/projects/[caseId]/retrospective` (`caseId` uuid). Optional query: `dossier=<integer>` (the Delivery dossier, for the checklist strip), `meeting=<integer>` and `version=<integer>` (open that saved retrospective, that exact version). No query: open the newest saved retrospective if any, else the empty form.
Files: `src/app/projects/[caseId]/retrospective/page.tsx`, `src/features/retrospective/` (view, hooks, `summary.ts`, `model.ts`, tests).

### Reads (all `liveApi`, signed-in person, 404 for missing and not-yours alike)
1. `GET /projects/{case_id}` for the project title (crumb and subtitle "<title> · needed before closure"). Also `sample` for `SampleLabel`.
2. `GET /projects/{case_id}/meetings?kind=retrospective&page=` returns `{revision, items[{id, version_id, version, reference, kind, occurred_at, purpose}], next_page, can_record, can_manage_actions}`. `revision` is the case revision used by every write below. One row per retrospective (its current version), newest first.
3. `GET /projects/{case_id}/meetings/{meeting_id}?version_id=` returns the meeting fields plus `revision, summary, participants[{id,label}], decisions[{text, evidence_id, change_evidence_id?}], evidence_id, actions[], next_page, current`. `actions` is empty for a non-current version.
4. `GET /projects/{case_id}/meetings/options` returns `{revision, participants[{id,label}], owners[{id,label}], proofs[{id,label}], more_participants, more_owners, more_proofs}`. 403 `forbidden` means the person cannot record: hide the form (read-only view). Only the first page is used; when a `more_*` flag is true show "More are available than shown." and nothing else.
5. `GET /projects/{case_id}/delivery/{dossier_id}/closure-checklist` only when `dossier` is in the query. Returns `{revision, as_of, ready_to_prepare, recorded_closure_id, checks[{key,title,status,summary,references[int],finding|null}], debt, retrospective_url}`. Use `checks[]`; ignore `debt`.

### Summary convention (D-8), `src/features/retrospective/summary.ts`
Written on save, in this order, only for boxes with text, separated by one blank line:
```
## What went well
<text>

## What didn't
<text>

## Lessons for next projects
<text>
```
Parse on read: split on lines that equal one of the three headings (case-insensitive, straight or curly apostrophe, trailing spaces ignored). Text before the first heading, or text under an unknown heading, is kept as "Other notes" when any recognised heading exists. No recognised heading at all: show the whole `summary` as one block titled "Retrospective" and load it into no box (the form for a new version then opens with the whole text in a single box labelled "Retrospective"; saving writes it back unchanged unless the person edits it). Round trip must be lossless for text a person typed, including blank lines. A box line that equals one of the three headings exactly is refused on Save with "That line is a section heading. Reword it." under that box (nothing is escaped or altered). Limit: the joined summary is at most 16000 characters; show a live count near the limit and block Save above it.

### Decisions
Each decision row: `text` (1 to 2000), `evidence_id` (a choice from `options.proofs`). A saved version's decisions are shown read-only on that version. A new version starts with the previous version's decisions loaded so they are carried forward, not dropped; the person may remove a row or add one ("Add a decision", at most 50). `change_evidence_id` is carried forward unchanged and never offered as a control.

### Save (one operation, one recorded version)
`POST /projects/{case_id}/meetings`, header `X-CSRFToken` (`liveApi` and `call` handle it), 201:
```json
{
  "revision": 41, "reference": "Retrospective 2026-11-23", "kind": "retrospective",
  "occurred_at": "2026-11-23T10:00:00Z", "purpose": "Project retrospective",
  "summary": "## What went well\nUAT finished on time.\n\n## What didn't\n...\n\n## Lessons for next projects\n...",
  "participant_ids": [12, 15],
  "decisions": [{"text": "Ask for the client's device mix during planning.", "evidence_id": 88}],
  "evidence_id": 87, "meeting_id": null
}
```
Response `{id, version_id, version, reference, kind, occurred_at, purpose, revision}`.
- `revision`: the `revision` of the latest meetings read (re-read first if the page is older than the last write). Never 0 or invented.
- `reference`: first save is prefilled `Retrospective <YYYY-MM-DD>` and editable; for a new version of a saved retrospective it is that meeting's `reference`, read-only. A second distinct retrospective is not offered (see Out of scope).
- `meeting_id`: null on first save; the meeting id when saving over a saved retrospective (button reads "Save new version").
- `purpose`: constant `Project retrospective`, not shown as a field.
- `occurred_at`: a "When it was held" date-time field, prefilled with now, required, not in the future (see Questions 2).
- `evidence_id`: the notes file, chosen from `options.proofs` as "Notes file" (required). Uploading a new file from this screen is not offered; DC-4 (how an upload becomes an evidence id) is open and the F-85 picker returns an `upload_id`, which a meeting write does not accept. When `proofs` is empty the field is disabled with "No supporting file is recorded for this project yet. Add the notes file to the project first." and Save is disabled.
- Required: at least one box has text; `evidence_id`; `occurred_at`. Participants optional (empty array allowed).
- Errors: 409 shows "This changed while you were editing. Reload and try again." and re-reads, keeping every typed value. 422 shows `fields[].message` under the named field, else the `message` in a `Callout`; 422 `invalid_evidence` is shown on the proof field. 403 `csrf_failed` refreshes the session and shows "Press Save again" (nothing was sent). Other 403: "You can't record a retrospective on this project." 404: "This record is unavailable." 429/503: "Try again shortly." Network failure or 503 after sending: say "We couldn't confirm it saved", re-read the meetings list, and keep Save disabled until that re-read has shown the result (a new `version` means it saved). No automatic retry; a press is one attempt; the button is disabled while in flight.
- Success: re-read list and detail; the new version shows as current with "Saved <time>, version <n>". Draw "saved" only from the re-read.

### Follow-up action from a lesson
Only on the current version of a saved retrospective and only when `can_manage_actions` and `owners` were returned. Button "Make this a follow-up action" under the lessons box opens a small form: description (prefilled with the lessons text, editable, max 1000), owner (optional, from `options.owners`), deadline (optional date-time; empty means no deadline, shown as "No deadline set", never a made-up date), why (required, max 4000), proof (required, from `options.proofs`), reference (prefilled `Retro action <n>` from the count of listed actions plus one, editable, must be unique, max 160).
`POST /projects/{case_id}/actions/create` `{revision, reference, description, owner_id|null, due_at|null, evidence_id, reason, meeting_id}` 201 returns the action. Because `meeting_id` is sent, the backend already links the action to the meeting; **do not also call `POST .../meetings/{id}/actions`** (that would try to link twice). Linking an existing action is not built. Errors as Save; 422 "Action reference already exists" shows under reference. After 201 re-read the detail; the action appears in "Follow-up actions" with description, owner label (none: "No owner"), deadline or "No deadline set", status and timing from the read. `calculated` and `change_evidence_id` are not sent.

### Screen states
- **Loading:** `Loading` skeleton for the form and strip; the header (crumb, title) draws as soon as the project read returns.
- **Error:** 401 signed-out state linking to `/sign-in?next=<path>`; 404 or a 403 on the project/meetings read: "This record is unavailable." (one wording); 429/503/network: "Try again shortly" with Try again. A failed checklist read hides only the strip and shows "The closure checklist is unavailable." in that block; the form still works. A failed options read other than 403 shows "We couldn't load the people and files you can pick." and disables Save.
- **Empty (no retrospective saved):** the form with empty boxes, the closure sentence, and if a checklist is present its retrospective row ("Not yet" with the checklist `finding`). If `can_record` is false: no form, text "No retrospective has been saved for this project yet." and nothing to press.
- **Success (saved):** Saved versions list (one row per retrospective: `reference`, "Version n", `occurred_at`), the selected one open. Boxes show the parsed text read-only with a "Save new version" button that loads the text into the editable boxes (when `can_record`). Participants as labels from `participants[]`, decisions as text with "Supporting file <evidence_id>" (no invented file names), the notes file as "Supporting file <evidence_id>", follow-up actions list. A historical version opened with `version=` shows "Version n, not the current version" and no edit or action controls.
- **Read-only (viewer cannot record):** same as Success without any form or button; no explanation of why.
- **Checklist strip:** rows for the six board keys present in `checks[]` (`go_live`, `hypercare`, `archive`, `handover`, `retrospective`, `finance`), in the order returned. Name: API `title`. Status words: current "Current", recorded "Recorded", closed "Closed", held "Not yet", unknown "Unknown", unavailable "Unavailable". The retrospective row is marked as the row for this screen. Under it: when `references[0]` exists, "The checklist used version <n> (saved <date>)", from `GET .../meetings/{id}?version_id=<references[0]>` where the meeting id is the one in `retrospective_url` or, when that is null, the list row whose `version_id` matches; if the read fails show "The checklist used version id <references[0]>" with no number or date. When that version's `current` is false: "A newer version has been saved. The checklist has not picked it up yet." No `retrospective_id` filter is applied and "latest" is never assumed. A checklist with the other two checks (`context`, `report`) does not show them here. No `dossier` in the query: the strip is not drawn.
- Phone: the same content in one column, order: title, boxes, who took part, notes file, Save, strip. The phone board omits the people, file, footnote and strip; the data is the same at both widths (D-99), as approved for F-32/F-40 phone boards.

### Fixture examples (mock, 4991; mirror the live shapes exactly)
- Case `3f6c1a52-0d2b-4c11-9b0a-5a1e7d9c2001` ("Sabi Market web store"), dossier `5001`, revision 41, `can_record:true`, `can_manage_actions:true`: no retrospective saved. Checklist: retrospective `held`, `references:[]`, `finding:"No retrospective saved"`; finance `unknown`; the other four `closed`/`recorded`.
- Case `...2002`: one retrospective, meeting 301, versions 1 (id 9001) and 2 (id 9002, current), checklist retrospective `current` with `references:[9001]` and `retrospective_url:"/api/v1/projects/<case>/meetings/301?version_id=9001"` (the checklist used v1; v2 is newer, `current:false` for v1). v2 `summary` uses the three headings; v1 `summary` has no headings (shown whole). One decision (evidence 88) and one linked action (owner `{id:12,label:"Tunde Bello"}`, `deadline:null`, status `open`, timing `UNKNOWN`).
- Case `...2003`: viewer without `meeting.record`: `can_record:false`, options 403.
- Case `...2004`: one saved retrospective whose `participants[]` is empty and `proofs` empty in options.
- Any other case: 404 `{code:"not_found", message:"This record is unavailable."}` (wrong tenant).
- Mock write behaviour: first save on 2001 returns 201 `version:1` and the next list read shows it; a second save with a stale `revision` returns 409; `reference` "Retrospective 2026-11-20" on a different meeting returns 422 with `fields:[{field:"reference", message:"Meeting reference exists; create a new revision"}]` (shape as live: `{code, message, fields}`); `POST .../actions/create` with an existing reference returns 422; a forced `503` on one named case exercises "We couldn't confirm it saved".

## Lanes
- **Frontend lane (owner):** `frontend/src/app/projects/[caseId]/retrospective/**`, `frontend/src/features/retrospective/**`, mock routes and fixtures for the operations above (`frontend/mock/retrospective.mjs`, fixtures under `frontend/mock/fixtures/retrospective/`), `frontend/e2e/retrospective.spec.ts`.
- **Shared files, one-line edits only:** `frontend/mock/server.mjs` (register the new mock module; F-118 and others edit it too, so rebase over theirs), `frontend/src/api/types.ts` (add retrospective aliases from `live-schema.d.ts`; no change to generated files).
- **Not touched:** `src/features/workspace/**` and `src/features/work-item/**` (lane C, F-85), `src/features/projects/DeliveryTab.tsx` and the closure view (F-118), `src/api/live-schema.d.ts`, `contracts/**`.
- **Backend lane:** none. No backend change is needed; API 1.24.0 supplies every field used.
- **Integration owner:** F-118's builder maps the checklist's `retrospective_url` to `/projects/<case>/retrospective?dossier=<id>&meeting=<id>&version=<version_id>`. If F-118 merges first it links to a page that does not exist yet; the coordinator should merge F-119 first or hold that link until then.

## Acceptance criteria
1. Case 2001 on Next 4990 + mock 4991 at `/projects/<2001>/retrospective?dossier=5001` shows the project title, three empty boxes, Who took part, Notes file, "Save retrospective" and no "Save draft" anywhere. — verify: open the page; search the page text and `src/features/retrospective` for "draft" (none).
2. Saving with only "What went well" filled, one participant, a notes file and a time sends one `POST /api/v1/projects/<case>/meetings` whose body has `kind:"retrospective"`, `meeting_id:null`, the current `revision`, a `reference`, and a `summary` that is exactly `## What went well\n<text>` — verify: network panel / Playwright request assertion; then the page shows "Saved ... version 1" only after the re-read.
3. Saving with all three boxes sends them in the order went well, didn't, lessons, each under its heading, joined by one blank line — verify: unit test on `summary.ts` and the e2e request body.
4. Parsing: a `summary` with the three headings fills the three boxes; one with no headings (case 2002 v1) shows as a single "Retrospective" block and saving it unchanged sends the identical text; a heading in different case or with a curly apostrophe still parses; text before the first heading appears under "Other notes" — verify: unit tests in `summary.test.ts` including a round trip.
5. Saving again on case 2002 sends `meeting_id:301` and the same `reference` (read-only field) and the page then shows version 3 — verify: e2e request body and page.
6. Case 2002 with `dossier=5002`: the strip shows "The checklist used version 1" with its date, and "A newer version has been saved. The checklist has not picked it up yet."; no request carries a "latest" filter or `retrospective_id` — verify: e2e and request log.
7. `/projects/<2002>/retrospective?meeting=301&version=9001` shows "Version 1, not the current version" with no Save new version button and no action controls — verify: e2e.
8. A stale save (mock 409) shows "This changed while you were editing. Reload and try again.", re-reads, and keeps every typed box, participant and proof — verify: e2e.
9. A duplicate reference (mock 422 with `fields`) shows the message under the Reference field, not as a generic error; Save re-enables — verify: e2e.
10. A forced 503 after sending shows "We couldn't confirm it saved", re-reads the list, and keeps Save disabled until the re-read returns; there is no automatic second POST (exactly one POST in the request log) — verify: e2e.
11. Double click on Save sends one POST — verify: e2e request count.
12. Save is disabled with the reason shown when no box has text, when no notes file is chosen, when the joined summary exceeds 16000 characters, or when `proofs` is empty (case 2004 shows "No supporting file is recorded for this project yet...") — verify: unit and e2e.
13. A decision row needs text and a supporting file; saving a new version loads the previous version's decisions and sends them unchanged when untouched, including any `change_evidence_id` — verify: unit test on the body builder; e2e on case 2002.
14. "Make this a follow-up action" sends one `POST /actions/create` with `meeting_id` and no call to `/meetings/{id}/actions`; empty deadline sends `due_at:null` and the new row reads "No deadline set"; an empty owner reads "No owner"; a duplicate action reference shows the 422 under Reference — verify: e2e request log and page.
15. Wrong user: case 2003 (`can_record:false`, options 403) shows saved versions read-only with no form and no action button; the 403 from options is not shown as an error — verify: e2e.
16. Wrong tenant or unknown case shows only "This record is unavailable." for both 404 on project read and on meetings — verify: e2e on an unknown uuid; same text for a case the mock marks not-yours.
17. A signed-out 401 shows the sign-in state with `next=` the current path — verify: e2e with the mock session cleared.
18. A checklist read failure (mock 503 for dossier 5009) hides only the strip, shows "The closure checklist is unavailable.", and the form still saves — verify: e2e.
19. `meetings` returns `next_page`: the list shows "More" and loads the next page via the `page` query — verify: e2e with a 30-row fixture.
20. Phone width (390px) shows one column with Save reachable and tap targets at least 44px — verify: Playwright mobile project screenshot.
21. Against Django 8030 with a project that has `meeting.record`: first save creates the meeting, `GET /api/v1/projects/<case>/meetings?kind=retrospective` returns it, and the closure checklist `retrospective` check references the saved version — verify: curl with the session, compare to the page.
22. No money, no client message, no approver or count is drawn; any value the API returns as null shows as "Not recorded" or the specific wording above, never 0 or blank — verify: review of the rendered pages and `model.ts` tests for null mapping.
23. New tests: `summary.test.ts` (write, parse, round trip, no headings, oversize), `model.test.ts` (body builders, null handling, status words), and `retrospective.spec.ts` (criteria 1 to 20 against the mock) — verify: `npm test` and `npx playwright test e2e/retrospective.spec.ts` in `frontend/`.

## Out of scope
- The closure screen and the closure decision (F-118), archive (SCR-47), handover (SCR-48), hypercare, minutes-preparation drafting (SCR-28) and any "draft" path (D-8).
- Uploading the notes file and turning an upload into evidence (DC-4/D-1 open); F-85's `EvidencePicker` and adapter; any change to `src/features/workspace`.
- Tola's panel ("I pulled the project's issues...") and the per-box "Cites" (no live source; D-182 rule). Recording people outside the project's granted users as participants ("recorded" parties): the API accepts person ids only.
- Linking an existing action to a meeting (`POST .../meetings/{id}/actions`), editing or completing actions (SCR-29), `calculated` deadlines, `change_evidence_id` controls.
- Several separate retrospectives per project, deleting or editing a saved version (versions are append-only), a version-history browser beyond the current version of each retrospective and the version the checklist used.
- Retrying a save by itself, offline queueing, and any role check in the browser (the backend decides; the screen follows `can_record`, `can_manage_actions` and the options 403).
- Choosing a different `retrospective_id` for the checklist (F-118's selection).

## Assumptions
- Route `/projects/[caseId]/retrospective` with query `dossier`, `meeting`, `version`: no route is defined anywhere; the checklist read needs a dossier id that no project read returns (F-113 takes it from the release register), so the caller supplies it.
- `reference` is generated `Retrospective <date>` and locked on later versions: the API needs one and the board has no field; the backend rejects a changed reference on a new version.
- `purpose` is the constant "Project retrospective": required by the API, absent from the boards.
- At least one box must have text (not all three): the API only requires a non-empty summary and no rule demands more.
- Empty `participant_ids` is allowed: the API allows it and no rule is given.
- Notes file is chosen from existing project proofs, no upload: DC-4 is open.
- The follow-up action does not call the link operation: the backend links it when `meeting_id` is sent.
- Only the first page of options and 25 actions is used: the lists are short in practice and the API pages them; "More" is shown when a next page exists.
- Status words for the checklist (Current, Recorded, Closed, Not yet, Unknown, Unavailable) replace the board's DONE/NOW/UNKNOWN, which are not the live status set.
- "Head of PMO" replaces "PMO Lead" in the footnote wording only if F-118's question 4 is answered that way; until then the board wording is kept.

## Conflicts with the boards
1. Boxes' "Cites" lines are not drawn (no live per-box citation). Recommendation: keep hidden (D-182).
2. "Save draft" is not drawn (D-8, no draft exists). Recommendation: keep hidden.
3. Board shows the notes file as an uploaded chip ("retrospective-notes-sabi.docx · Uploaded · 36 KB"); built as a "Notes file" select of existing project proofs. Recommendation: keep until DC-4 is settled.
4. Board "Who took part" lists recorded outside parties; built as a pick-list of project people only. Recommendation: keep.
5. Added elements not on the boards: "When it was held" field, Reference field (first save), Decisions rows with their proof, Follow-up actions list and form, "Other notes" block, the version label and the "checklist used version n" line. Recommendation: keep; each is required or read-only data the API returns.
6. Tola's panel is not drawn (no live source, DC-3). Recommendation: keep hidden.
7. The checklist strip uses API titles and status words and omits context and report; board words DONE/NOW are not used. Recommendation: keep.
8. Phone board shows only the three boxes and Save; built phone shows the same data in one column (D-99).

## Questions
1. Decisions rows (not on the board). Options: (a) show an optional "Decisions" block with add-row and a supporting file per row (recommended: readiness says per-decision proof stays, and the API stores decisions); (b) show saved decisions read-only and carry them forward, with no way to add one; (c) hide decisions completely and send `[]`. Context: the board draws none; option (c) would silently drop decisions saved by others on a new version.
2. "When it was held" (not on the board). Options: (a) show a date-time field prefilled with now (recommended: the API needs a real meeting time and guessing it would record an unknown as a fact); (b) hide it and send the save time; (c) show it read-only as "Recorded <save time>". Context: `occurred_at` is required.
3. Notes file source. Options: (a) pick from the project's recorded proofs, with the empty case explained (recommended, buildable now); (b) hold the save until the upload-to-evidence path exists (D-1); (c) show the board's upload chip using F-85's picker (would send an `upload_id`, which the API rejects). Context: this decides whether a person can save today when the project has no recorded proofs.
4. Footnote wording "PMO Lead decides on". Options: (a) "Head of PMO" (recommended, matches F-118 Q4 and the 13 Nov naming); (b) keep "PMO Lead"; (c) drop the role name. Context: presentation only.
5. Where the checklist strip sits when there is no `dossier` in the link. Options: (a) not drawn (recommended: no dossier id source on the project read); (b) draw a "Closure checklist unavailable" note; (c) find the dossier from the release register as F-113 does (extra reads, more coupling to lane D). Context: only affects pages opened without the F-118 link.
