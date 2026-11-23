# Archive: the PM reserves the project archive, watches the copy, and checks files the store did not confirm

> Tasks: FE-DELIVERY-HYPERCARE-ARCHIVE. Architecture: v9 package (`architecture/packages/v9/tasks.csv`; revision as pinned in the feature record at branch time); contract `contracts/psl-factory.openapi.json` 1.24.0. Design: approved 13 Nov canvas under the D-173/D-181 exceptions in `design/review.json`; screens: SCR-47 (6 artboards in `design/canvas/project/`: `SCR-47-desktop`, `-mobile` (archived), `-desktop-working`, `-mobile-working`, `-desktop-uncertain`, `-mobile-uncertain`). The builder runs `python3 /Users/Hunchoo/software-factory/packages/design/design.py check --project /Users/Hunchoo/psl-factory` before starting.

## Summary
- An archive work item (`delivery-archive/v1`) at `/work/[id]` reads its own resource `GET /work/{id}/archive-files` and draws the archive index grouped by the API's `group` (D-20), with counts taken only from each file's `job.state`. "N files, each matched" is drawn only when `verified` is true.
- A person starts the archive: the source list is preselected from `required_source_ids`, shown for review, and sent with `POST /work/{id}/archive-files` (202). The board's "no approval step" becomes "a person reserves" (D-21, PSL's decision, D-185). The result is "Queued", never "archived".
- Files the store did not confirm (`job.state` `unknown`) get a per-file "Look up" (`recovery` `lookup`). "Copy again" (`retry`) shows only when that file's `actions[]` lists `retry`. The page also offers "Check what happened" (`POST /work/{id}/actions` `reconcile`, 202) when the work read lists it.
- Hidden, no placeholder (D-182): Tola's step card and notes (DC-3), the manual "mark each file found or not found" check, the "keep, never purge" rule text. The human delivery observation (`delivery-observations`) is held; see Questions 1.
- Build-start wait: F-85 (shared line adapter, lane C, PR #101) is not on main. The coordinator holds the builder until it is. This spec is written against `/Users/Hunchoo/psl-factory-main/delivery/features/F-85/spec.md` and changes nothing in `frontend/src/features/workspace`.

## Context
Worktree `/Users/Hunchoo/psl-factory-worktrees/lane-d/frontend` at origin/main (API 1.24.0).
- No archive page exists on the live path. F-34 part 3 (SCR-47) was never built; the v7 reconcile pieces are `src/features/response/ReconcilePanel.tsx` and `useResponse.ts` (reuse the banner wording, not the v7 call). Project sub-nav lives in `src/features/projects/DeliveryTab.tsx` (no archive entry).
- Live client: `src/api/client.ts` (`liveApi`, `call()`, shared CSRF), `src/api/live-schema.d.ts` (already carries `archive_files_inventory`, `archive_files_reserve`, `archive_files_recover`), `src/api/errors.ts`.
- From F-85 (not yet on main): `src/features/workspace/adapter.ts` (`LineAdapter`, `PanelRef`, `LineContext`, `CommandDescriptor`, `registerLineAdapter`, `adapterFor`) and `useWorkItem` reading the live `GET /work/{id}` with `panels[]`.
- Live operations (look up with `python3 /Users/Hunchoo/psl-factory-main/delivery/connect/oa.py live <METHOD> <path> 3`):
  - `GET /work/{work_id}/archive-files` returns `{expected_revision, case_revision, plan_id|null, store|null, finding, verified, can_reserve, limited, required_source_ids[int], sources[{id,label}], files[{id, name, status, job{id, revision, state pending|leased|unknown|missing|confirmed|held}|null, group, source_id|null, source_kind|null, actions[lookup|retry], receipt{id,at}|null}]}`.
  - `POST /work/{work_id}/archive-files` takes `{expected_revision, case_revision, source_ids[int]}` and returns 202 `{work_id, state, revision, plan_id}`.
  - `POST /work/{work_id}/archive-files/{job_id}/recovery` takes `{revision, action:"lookup"|"retry"}` and returns 200 `{id, revision, state}`.
  - `POST /work/{work_id}/actions` takes `{expected_revision, action:"reconcile"}` and returns 202 `{work_id, state, revision}`. `GET /work/{id}`'s `actions[]` lists `reconcile` when allowed.
  - `GET /work/{work_id}` and `GET /work/{work_id}/history` as in the F-85 spec.
  - Not used: `POST .../archive-files/rules` (Setup), `POST /work` start (Start work), `POST /work/{id}/corrections`, `POST /work/{id}/delivery-observations` (held, Questions 1).

## Contract

### Adapter mapping (this feature's own file)
`src/features/delivery-archive/archiveAdapter.ts` (new, in the feature, not in `workspace`) implements F-85's `LineAdapter`:
- `read()` fetches `GET /work/{id}/archive-files` and returns one `ArchiveReadback`. Registered for the `panels[].key` the live `GET /work/{id}` carries for this line; the builder names the key in `build.md`. If `panels[]` has no key for this line, the page routes by `line === "delivery-archive/v1"` inside this feature's own page wrapper (Questions 3).
- Tokens: `expected_revision` and `case_revision` come from the same `archive-files` response the command is built from; a null token stays null, never 0. Recovery `revision` is `files[].job.revision` of that row from the same read. Reconcile uses `expected_revision` from the archive read.
- `commands()` returns `archive.reserve`, `archive.lookup`, `archive.retry`, `archive.reconcile` descriptors. `idempotency.field` is null for all (the bodies carry no key). Double presses are prevented in the UI (below).
- `disabledReason` only from the readback (`can_reserve:false`, absence of `retry` in `actions[]`); the page never invents a reason.

### Screen states
The page header is the F-85 work item header (title, state tag, next step, blocker, activity). Below it the archive panel draws these parts, each only when its data exists:

1. **Status sentence** (always), from `verified`, `finding`, `job.state` counts and the work `state`:
   - Verified: "Archived and verified: N files, each matched in the archive index." only when `verified` is true; N is `files.length`. Add "Nothing was purged" only if the API says so; it does not, so the sentence stops at "matched in the archive index."
   - Working (any file `pending` or `leased`, or work `state` `processing`): "Archiving in progress. N of M files copied." N is the count of `confirmed`, M is `files.length`. Not drawn when `files` is empty.
   - Uncertain (any file `unknown`): "The archive store didn't confirm N of M files. They won't be copied again until someone checks what arrived." Same sentence for work `state` `effect_uncertain` or `awaiting_reconciliation` when no file is `unknown`: "The archive result is not confirmed." plus the reconcile control.
   - Otherwise `finding` text as given. A `held` file adds "N files are on hold." (no reason is served; none is invented).
2. **Archive index** (table, success): one row per distinct `group` string, in the order first seen. Columns: Group (the `group` text as served, lightly capitalised), Files (count of files in the group), State. The group state word: "Archived" when every file in the group is `confirmed`; "Copying" when any is `pending` or `leased`; "Not confirmed · N" when any is `unknown` (N = count); "Missing · N" when any is `missing`; "On hold · N" when any is `held`; "Not started" when `job` is null for all. When a group mixes states, the worst of unknown, missing, held, copying, archived is the headline and the others are listed after it as words with counts. Under a group, a disclosure lists its files: `name`, `status` text, state word, and receipt time when `receipt` is non-null (`receipt.at`). A file with `source_id` and `source_kind` shows the kind and a link to the source only if F-85 or the project documents route can open that kind and id; otherwise the kind and id are plain text. No link is invented.
3. **Start the archive** (only when `can_reserve` is true): a short list of `sources[]` as checkboxes (label only), preselected to those whose `id` is in `required_source_ids`, with the line "Review the list, then start the archive." Button "Start archive" posts as below. A person may uncheck or check any listed source; a source not in `sources[]` cannot be added. Zero checked disables the button (the only local rule). When `can_reserve` is false the part is absent: no disabled button, no explanation.
4. **Check files** (uncertain state): per file with `job.state` `unknown`, a "Look up" button (`lookup`). Per file whose `actions[]` contains `retry`, a "Copy again" button. The group row shows a bulk line "Check the N files" that only scrolls to those rows; there is no bulk send. Intro text: "Look each file up first. Only files the archive confirms missing can be copied again." A file with `actions` empty has no button. A `held` or `pending` file never has a button.
5. **Check what happened** (button): shown only when `GET /work/{id}` `actions[]` contains `reconcile`. Posts reconcile. Uses `ReconcilePanel.tsx` wording where it fits.
6. **Store line** (small, under the index): "Store: {store}" when `store` is non-null; "Copy limit reached" when `limited` is true. Nothing for null/false.
7. **History**: the F-85 `/work/{id}/history` page, unchanged. The "Started" time on the board comes from the first history row's `at`, shown as "Started {at}" only when a row exists.

Page states, following the F-85 work item:
- Loading: skeleton for the header and the index.
- Error: 401 signed-out link to `/sign-in?next=<current path>`; 403 `csrf_failed` "Refresh your session and try again"; 403 `forbidden` no-access; 404 "This record is unavailable." (same for missing and not yours); 429/503 "Try again shortly" with Try again; network "We couldn't reach the server." with Try again. A failed poll keeps the last good read and shows "couldn't refresh".
- Empty: `files` empty and `can_reserve` false: header, then "Nothing is waiting to be archived." (the page's own words). `files` empty and `can_reserve` true: header and the Start part only.
- Working: part 1 Working sentence, index with Copying rows. Polling every 5 s (F-85's `POLL_MS`, visibility pause) while any file is `pending` or `leased` or work `state` is `processing`; none otherwise. Stops on 401, 403, 404.
- Uncertain: parts 1, 2, 4, 5 as above.
- Success (verified): part 1 Verified sentence, index with every group "Archived", the "Next" block "Handover can start now that the archive is verified." with link "Open handover" to the handover page of the same project only when the project's delivery lines read gives a handover work id (F-113's delivery overview read); otherwise the sentence is drawn without the link. Never shown unless `verified` is true.

### Start the archive
- `GET /work/{id}/archive-files` on load and after every write.
- `POST /work/{id}/archive-files` body `{expected_revision, case_revision, source_ids}` where `source_ids` are the checked ids, all from `sources[]`. No other fields.
- 202 `{state, revision, plan_id}`: show "Queued" (not archived), re-read, and poll as above.
- Errors: 409 "This changed while you were looking. The page has been refreshed." and re-read; no automatic second post. 422 shows `message` and the first `fields[].message`. 403 `csrf_failed` refreshes the session and says "Press Start archive again" (nothing was sent). 403 otherwise "You can't start this archive." 404 "This record is unavailable." 429/503 "Try again shortly. Check below before you press Start archive again" and the page re-reads first. A dropped connection or timeout is treated as uncertain: re-read; if the work `state` is `effect_uncertain` show part 5, never post again by itself.
- The button is disabled from the first press until the re-read returns. One press makes one POST.

### Look up and copy again
- `POST /work/{id}/archive-files/{job_id}/recovery` body `{revision, action}`; `job_id` is `files[].job.id`, `revision` is that row's `job.revision`.
- 200 `{id, revision, state}`: set that row to the returned state and re-read the whole inventory; a lookup that returns `missing` makes `retry` appear only if the re-read lists it. "Copy again" is never offered from a lookup result alone.
- Errors as above (409 refresh, 422 `message`, 403, 404, 429/503). A retry press that fails with a dropped connection is uncertain: the page re-reads and does not send a second retry until the re-read shows `retry` in `actions[]`.
- Each row's buttons are disabled while any recovery call is in flight; one press makes one POST. No bulk look-up or retry.

### Check what happened
- `POST /work/{id}/actions` body `{expected_revision, action:"reconcile"}`. 202 shows "Checking. This can take a moment." and polls. Errors as above. No outcome or evidence field is sent.

### Fixture examples (mock serves these for numeric ids; the builder creates them in `frontend/mock/`)
- `4401` verified: `verified:true`, 42 files over five groups, all `job.state:"confirmed"` with receipts, `can_reserve:false`, `store:"archive-store"`.
- `4402` working: `can_reserve:false`, 42 files, 28 `confirmed`, 10 `leased`, 4 `pending`, `verified:false`, work `state:"processing"`.
- `4403` uncertain: 42 files, 6 in group "RFP response and submission" with `job.state:"unknown"`, `actions:["lookup"]`; after a lookup the mock returns `missing` for two files and `actions:["retry"]` for them.
- `4404` ready to start: `files:[]`, `can_reserve:true`, `sources:[{id:11,label:"RFP response"},{id:12,label:"Costing and SOW"},{id:13,label:"Planning"}]`, `required_source_ids:[11,12]`.
- `4405` restricted: 404 for any caller. `4406` held: two files `job.state:"held"`, `limited:true`.
- `4407` token null: `GET /work/4407` has `revision:null`; the archive read still loads and Start is disabled because a null token is not sent as 0 (the page waits for a read with both tokens).

## Lanes
- Frontend lane (owner, all of this feature): `frontend/src/features/delivery-archive/**` (new: `ArchivePage.tsx`, `ArchiveIndex.tsx`, `StartArchive.tsx`, `FileChecks.tsx`, `archiveAdapter.ts`, `useArchive.ts`, `model.ts`, `archive.css`), `frontend/mock/**` (live-shaped archive-files, recovery, reconcile routes and fixtures 4401 to 4407), tests under `frontend/src/features/delivery-archive/**` and `frontend/e2e/delivery-archive*.spec.ts`.
- Backend lane: none. No backend change, no contract edit.
- Integration owner: lane D coordinator. Shared files: `src/features/workspace/*` (lane C owns; not touched; any frame need is named as a dependency on lane C), `src/api/*` (shared; edits limited to live types and error kinds not already there), `src/features/work-item/*` (lane C; the one line that routes `delivery-archive/v1` to `ArchivePage` is added as a separate small commit after `git merge origin/main`), `src/features/projects/DeliveryTab.tsx` (lane D; sub-nav "Archive" link only if the delivery overview read supplies the archive work id, else untouched).
- Protected paths in `delivery/config.json` stay unchanged.

## Acceptance criteria
1. `/work/4402` against the mock (Next 4990, mock 4991) shows "Archiving in progress. 28 of 42 files copied.", groups with "Copying" rows, and no Tola step card, no "step 3 of 4", no "Ask Tola" — verify: open the page; `frontend/e2e/delivery-archive.spec.ts` asserts those absent.
2. `/work/4401` shows "Archived and verified: 42 files, each matched in the archive index." and every group "Archived"; the same page with `verified:false` and all files confirmed does not show the sentence — verify: e2e on both mock states; unit test on the status mapper.
3. Group rows come from `files[].group` as served: a mock with a group the builder did not know ("Legal") draws a "Legal" row with its count; no hard-coded group list exists — verify: unit test; `grep -rn "RFP response" frontend/src/features/delivery-archive` returns nothing outside tests.
4. The group state words follow part 2: a group with 6 `unknown` and 3 `confirmed` reads "Not confirmed · 6", and the counts across rows equal `files.length` — verify: unit test on the grouping model.
5. "Handover can start now…" and "Open handover" appear only when `verified` is true; the link appears only when the handover work id is known — verify: e2e with and without it.
6. `/work/4404` shows the three sources with "RFP response" and "Costing and SOW" checked and "Planning" unchecked; unchecking all disables Start; no source outside `sources[]` can be added — verify: e2e plus component test.
7. Pressing Start on `/work/4404` sends one `POST /work/4404/archive-files` with `{expected_revision, case_revision, source_ids:[11,12]}`, shows "Queued" (not "Archived") on the 202, and disables the button until the re-read returns — verify: network panel shows one POST; unit test with a mock that counts calls.
8. With `can_reserve:false` (`/work/4401`) no Start control and no disabled placeholder exist — verify: e2e.
9. A 409 on Start shows "This changed while you were looking. The page has been refreshed.", re-reads, and sends no second POST — verify: mock scenario `conflict`; count POSTs.
10. A 422 on Start shows `message` and the first `fields[].message`; a 403 `csrf_failed` refreshes the session once and says "Press Start archive again" with no second POST; a 404 shows "This record is unavailable."; a dropped connection re-reads before any further POST — verify: unit tests with fetch counts.
11. `/work/4403` shows "The archive store didn't confirm 6 of 42 files…", the RFP group "Not confirmed · 6", and one "Look up" per unknown file; no "Copy again" button exists before a lookup — verify: e2e; assert no element named "Copy again".
12. "Look up" posts `{revision: <that row's job.revision>, action:"lookup"}` to that row's `job.id`; after the 200 the page re-reads the inventory, and "Copy again" appears only for rows whose re-read `actions[]` contains `retry` — verify: e2e on the 4403 lookup scenario; network panel.
13. "Copy again" posts `{revision, action:"retry"}` once per press; while any recovery call is in flight all row buttons are disabled — verify: e2e with a slow mock; count POSTs.
14. A 409 on a recovery refreshes the inventory with no automatic repeat; a recovery that dropped the connection is not repeated until a re-read lists `retry` again — verify: unit tests.
15. "Check what happened" shows only when `GET /work/{id}` `actions[]` includes `reconcile`; it posts `{expected_revision, action:"reconcile"}` with no outcome or evidence and shows "Checking…" on 202 — verify: e2e on a mock with and without `reconcile`; request body assertion.
16. No part of the page offers "mark found" or "mark not found", and no archive screen text promises "no approval step", "keep, never purge" or "nothing was purged" — verify: `grep -rniE "mark (each|found)|never purge|no approval" frontend/src/features/delivery-archive` returns nothing; e2e text check.
17. A null `job` (not started) draws the group as "Not started" and no buttons; a null `receipt` shows no receipt time; a null `store` draws no store line; `limited:true` shows "Copy limit reached" — verify: unit test on the mappers.
18. Unknown is not zero: a null `revision`/`case_revision` (`/work/4407`) is not sent as 0 and Start stays disabled — verify: unit test on the token mapper; e2e.
19. Polling: re-reads every 5 s while any file is `pending` or `leased` or work `state` is `processing`; one read when idle; paused in a hidden tab; a failed poll keeps the last read and shows "couldn't refresh"; 401/403/404 on a poll replaces the page and stops polling — verify: unit test with fake timers; network panel count on `/work/4402` and `/work/4401`.
20. Another user's work item (`/work/4405`) and a live id the account cannot see both show exactly "This record is unavailable." — verify: open both; unit test on the 404 body. A person without write rights (`can_reserve:false`, no `reconcile`) sees the index but no write control — verify: e2e.
21. `/work/4406` shows "2 files are on hold." and "Copy limit reached", with no buttons on the held rows — verify: e2e.
22. Against live Django (8030, account with PM scope) on a real archive work item, the page's group counts, file count, `verified` word and store line equal `GET /api/v1/work/{id}/archive-files` — verify: compare the page with `oa.py live GET /api/v1/work/{work_id}/archive-files 3` shape and the `curl` JSON with the session.
23. The code imports live types from `live-schema.d.ts` and not the v7 `@/api/schema` for this page — verify: `grep -rn "api/schema'" frontend/src/features/delivery-archive` returns nothing.
24. `archiveAdapter.ts` registers with F-85's `registerLineAdapter`, `sections()` returns existing `Section` objects the `Sections` renderer draws, and `commands()` returns the four descriptors whose `body()` includes the action, the tokens and no key field; a null token stays null — verify: `archiveAdapter.test.ts`; typecheck.
25. Viewport check at 1440 and 390: the page matches the SCR-47 default, working and uncertain boards for the parts that remain (header, status sentence, archive index with group, files, state, the Next block); parts removed leave no empty gap or empty heading — verify: screenshots at both widths against `design/screens.md` SCR-47 artboards.
26. `npm run lint`, `npm run typecheck`, `npm test` pass, and the live-schema drift test still passes — verify: `delivery/checks.sh` result.
27. New tests cover: the grouping and counts model, the status sentence, token mapping with nulls, each write's single-POST rule, and the 409/422/403/404/429/503 mapping — verify: test files named in the build report.

## Out of scope
- The human delivery observation (`POST /work/{id}/delivery-observations`): held (Questions 1).
- Tola's step card, notes and "Ask Tola" (DC-3); the manual "mark each file found or not found" check; the "keep, never purge" storage rule text.
- Setup of store rules (`POST .../archive-files/rules`), `POST /work` start, `POST /work/{id}/corrections`, `intake-sources` lists beyond the `sources[]` already on the archive read.
- Opening or downloading an archived original; per-file checksums or sizes; any retry count or attempt number (none is served).
- Handover, closure and the other Delivery screens (F-113 to F-119); the Delivery sub-nav and Journey/Planning tabs with counts.
- Any frame change in `frontend/src/features/workspace`; backend, migrations, contract edits.

## Assumptions
- The group state headline order (unknown, missing, held, copying, archived) is the worst-first order. Reason: the board draws only "Archived" and "Not confirmed"; a worst-first order never hides an uncertain file.
- Group labels are the served `group` text, only capitalised. Reason: D-20 says the group is stable and the API owns its words.
- "Queued" after a 202. Reason: the API says a worker processes the reservation; archived is known only from `verified` and receipts.
- Start requires at least one source checked. Reason: an empty reservation has no meaning; the server stays the final rule.
- The status sentence omits "Nothing was purged". Reason: no field says so and the board's claim is a storage rule held in Setup.
- "Started {at}" uses the first `history` row. Reason: no `started_at` is served (DC-3).
- Recovery buttons need the row's `job` non-null. Reason: the path takes `job_id`.
- Mock ids 4401 to 4407 are the builder's to create. Reason: no live-shaped fixtures exist.
- A file's `source_kind` and `source_id` are drawn as plain text unless an existing page can open them. Reason: D-20 says use the source link where authorised, but no route for each kind is in the contract.

## Questions
1. **Human delivery observation for an unconfirmed file.** `POST /work/{id}/delivery-observations` needs `effect {job_id, job_type}`, a work-bound `proof_id` and a reason, and the backend checks recovery authority. The archive read and `GET /work/{id}` expose none of: whether the viewer has that authority, the archive's `job_type`, or a list of proofs. Building the form would guess.
   1. Hold it. The page uses lookup, retry and `reconcile` only. Recommended: nothing is invented and the board's recovery is covered.
   2. Build the form with `job_id` from `job.id`, `job_type` typed by the builder from the live response and `proof_id` typed in. Not recommended: guesses authority and a proof list.
   3. Ask the backend to expose a recovery flag and proofs on the archive read, then build. Cleanest but waits on the backend.
   No board draws it, so option 1 changes no board.
2. **Board wording that no longer holds.** The working board says "Archiving has no approval step. Nothing is deleted or purged; the originals stay where they are." The live product has a person reserve (D-21) and the API does not say the storage rule.
   1. Replace with "Review the list, then start the archive." and drop the purge line. Recommended: matches PSL's answer.
   2. Keep the first sentence in the Working state only. Conflicts with D-21.
   Needs the design engineer's word, since the copy is on the board.
3. **Which panel key and route.** Whether `GET /work/{id}` lists an archive panel key in 1.24.0 is unconfirmed.
   1. Route by `panels[]` key when present, else by `line` in this feature's page wrapper. Recommended: no frame change.
   2. Ask lane C for a panel key. Cleaner but waits on another lane.
4. **Start control placement.** No board draws the source list or the Start button (the boards start with Tola already working).
   1. A "Start the archive" block above the index, only when `can_reserve` is true, plain list of checkboxes. Recommended: smallest, uses existing CMP-05 style.
   2. A drawer opened from a button. Matches other starts but adds a surface. Needs a board either way.
5. **Per-file checks on 390.** Six or more unknown files with two buttons each are long on mobile.
   1. A disclosure per group with row buttons, as specified. Recommended.
   2. A single "Check the N files" screen. Closer to the board's single button but a new surface.

## Conflicts with the boards
All for the design engineer to decide once before the build. Marked where also in Questions.
1. Working board: the "Tola · PMO agent · step 3 of 4" card, its three step lines (42 files · 6 lines, "SETUP › RULES · KEEP, NEVER PURGE", "28 OF 42") and "Ask Tola" are not drawn (no live source, DC-3). The "28 of 42" figure is kept as a sentence built from `job.state` counts. Recommendation: hide the card, keep the sentence.
2. Working board: "Archiving has no approval step. Nothing is deleted or purged; the originals stay where they are." is replaced (Questions 2). Recommendation: option 1.
3. Working and default boards: no group table in the working board; the page draws the same archive index with Copying rows while working. Recommendation: keep (the index is the same table the other two boards draw).
4. Default board: "Archived and verified on 05 Apr" date is dropped when no verified time is served (the sentence stops at "matched in the archive index."); "Nothing was purged" is dropped. Recommendation: hide.
5. Default board: the Next block "Open handover" is kept but drawn only when the handover work id is known. Recommendation: keep.
6. Uncertain board: "An admin checks the archive store, then marks each file found or not found" and the single "Check the 6 files" button become a per-file "Look up", then "Copy again" only for confirmed-missing files (Questions 5). Recommendation: as specified; this is PSL's decision, not a design choice.
7. Uncertain board: the "EFFECT UNCERTAIN" tag is shown from work `state` and the "Not confirmed · 6" state text is kept. Recommendation: keep.
8. Sub-nav (Overview … Closure), Journey/Planning tabs with counts, and the byline are not drawn (F-85 header applies). Recommendation: as F-85 conflict 6.
9. Added with no board: the Start block with source checkboxes (Questions 4), the Store/limit line, the "On hold" and "Missing" group states, "Check what happened". Recommendation: keep; they need a board from the design engineer.
