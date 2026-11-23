STATUS: READY
COMMIT: 35189b4503a76ae516ba153f77434a9a562bdc0d
BUILDER: builder
LANE: full

## Summary
- `/work/{id}` and `/work/{id}/history` read the live `GET /work/{id}` and `/history` when the id is an integer (new `src/features/work-item/live/`). The page draws title, sample tag, state tag, status label, owner (only when set), updated time, blocker, next step, activity line, decisions waiting (links only), the output link and adapter panels. No station track, facts strip or agent steps, and no placeholder in their place.
- v7 ids (`W-xxxx`) still go to the old v7 frame, unchanged, because about 30 other lines and their tests still read that shape. The route layout and both pages choose by `isLiveWorkId`. This is the one structural choice beyond the spec (see Changes).
- New shared `src/features/workspace/adapter.ts` (types, `makeCommand`, registry, `readPanel`) with `weeklyReportAdapter.ts` as the read-only reference adapter, drawn through the existing `SectionView`.
- New shared `EvidencePicker` + `evidence.ts` (`uploadCaseFile`, error words, branded `UploadId`/`EvidenceId`, `fileToEvidence` proposal). Used by tests only.
- Mock `mock/work-live.mjs` serves live shapes for ids 4101..4108, the weekly report, the file upload and the file-draft routes, validated against contract 1.22.0 in a test.

## Changes
- `src/features/work-item/live/model.ts`: pure mappers (`isLiveWorkId`, `needsPolling`, `activityOf`, `decisionHref`, `historyLine`, `historyCaption`, filters).
- `live/useLiveWorkItem.ts`: read plus polling every `POLL_MS` (reused from `useWorkItem.ts`) while `current_activity.watching` or `state === 'processing'`, visible tab only; failed poll keeps the item; 401/403/404 replace it and stop. `live/useLiveHistory.ts`: `GET /history?kind=` (none for All); tab kept through errors.
- `live/LiveWorkItemView.tsx`: frame, overview, history, error states (404 one wording "This record is unavailable."; 403 forbidden no-access; 403 csrf_failed "Refresh your session and try again."; 429/503 "Try again shortly."; network; 401 signed-out via the shared `SignedOutState`). Reuses `STATE_TAGS`, `nextStepKind`, `WorkErrorCard`, `NoAccessState` from the v7 files.
- `src/app/work/[id]/(item)/layout.tsx`, `page.tsx`, `history/page.tsx`: choose live or v7 by id.
- `src/api/types.ts`: `LiveWorkItem`, `LiveWorkTask`, `LiveWorkHistory`, `LiveHistoryRow`, `LiveWeeklyReport` (additions only). `src/api/errors.ts` and `client.ts` NOT touched: lane A's mapping already has 400/413/415/429 and `read_limited`; 503 without that code maps to `server` and is worded by the page.
- `work-item.css`: 3 lines for the history list. `workspace/adapter.ts`, `weeklyReportAdapter.ts`, `evidence.ts`, `EvidencePicker.tsx`: as in Summary.
- `mock/server.mjs`: one block routing live work and case-file paths to `work-live.mjs`, plus reset and a `/__mock/work-live-log` read.
- Tests: `tests/live-work-item.test.tsx`, `line-adapter.test.tsx`, `evidence.test.tsx`, `mock-work-live.test.ts`, `e2e/work-item-live.spec.ts`.
- Two existing tests touched, each for a spec-mandated name only: `tests/weekly.test.tsx` (the scan for "returned|received" now allows `weeklyReportAdapter.ts`, which must say "Returned to you"); `tests/next-config.test.ts` (allows `mock/work-live.mjs`, which must carry the live item's required `django_url`). No assertion weakened otherwise.
- Shared files from the checklist: Workspace, InlineDecide, WorkItemOverview, Sections, labels not edited.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] 4102 shows title, Processing tag, next step, activity line; no track/facts/agent steps, no "not available": e2e `work-item-live.spec.ts` and `live-work-item.test.tsx`, screenshots reviewed at 1440 and 390.
2. [ ] Live Django check not possible here: the live database has 0 work items for live-lead (queue returned `items: []`), so there is no real work id. The 404 body from live (`This record is unavailable.`) matches what the page shows. Needs a seeded work item.
3. [x] The live files import no v7 work item type: `grep "api/schema'" src/features/work-item/live` is empty. The old v7 files in `src/features/work-item/` still import it (kept for `W-` ids; see Summary).
4. [x] Polling: fake-timer tests (5 s while watched/processing, one read otherwise, hidden tab pauses).
5. [x] Failed poll keeps item with the refresh note; 401/403/404 replace the page and stop polling (unit tests).
6. [x] `/work/4106` and unknown id give identical text (e2e) and one heading in the unit test.
7. [x] csrf_failed shows "Refresh your session and try again.", not no-access, and reads `/session` (unit test).
8. [x] 401 shows signed-out with `<SIGN_IN_URL>?next=/work/4102`. On this base `SIGN_IN_URL` is `/accounts/login/`; the link becomes `/sign-in` when lane A's F-58 lands (shared `SignedOutState` is used as is).
9. [x] 4103: one "Open decision" link to `/work/4103/decide?task=9101`, none for the task with both flags false; no writes (e2e, unit).
10. [x] 4101 output link equals `output_url`; none on 4103.
11. [x] Null revisions (4104, 4105) load, nothing drawn as 0.
12. [x] History tabs send `kind=decision|worker|evidence`, none for All; no counts, no Show more; caption "Showing the latest 30 changes." only for 30 rows (4108).
13. [x] Unknown station/status shown as text (first letter raised, underscores to spaces); no actor line when absent; evidence shown only when `evidence_id` set. The contract has no evidence page, so it is a plain "Evidence 11" line, not a link.
14. [x] Empty "No changes recorded yet."; error keeps the tab and Try again recovers (unit and e2e).
15. [x] No write buttons; e2e asserts no non-GET requests on 4102 and 4103. `liveApi.POST` appears only in `evidence.ts` (upload and the proposal).
16. [x] `adapter.ts` exports the specified types, `registerLineAdapter`, `adapterFor` (plus `makeCommand`, `readPanel`, `isPanelUrl`); `line-adapter.test.tsx` registers a fake adapter, draws its sections with `SectionView`, gets a descriptor whose body has action, tokens and a uuid key.
17. [x] Null token stays null; no key field gives `idempotency.field === null` and no key in the body.
18. [x] 4102 draws period, four parts with "N records cited", recipients ("No receipt yet" when `receipt_id` null), next action; no parts section without `editable_parts`/`draft`.
19. [ ] Not checked live (no work items, see 2).
20. [x] A panel key with no adapter is omitted; page loads (4107 has a `forecast` panel).
21. [x] `correct` descriptor carries tokens and a `disabledReason` when `can_correct` is false; no button drawn.
22. [x] Mock: multipart POST returns `upload_id`, name, size, sha256 (unit test). [ ] Live: not possible, `POST /cases/{id}/files` fails in this environment with "Private file storage client is unavailable." (object storage is not running).
23. [x] `.exe`, `RUN.EXE`, `plan.pdf.exe`, no extension, `.txt` and 10 MB + 1 are refused with no fetch.
24. [x] 413, 415, 422 (first field message), 429, 404 and dropped network each map to their words; each sent once.
25. [x] 403 csrf_failed: one upload, one session read, "Press upload again."
26. [x] `@ts-expect-error` test in `evidence.test.tsx`; typecheck passes.
27. [x] `fileToEvidence` runs drafts then review and returns `reviewed_evidence_id`; null stays null; labelled "PROPOSAL, backend question 1" in code. It takes a fourth argument, `review`, because the spec's three-argument form has no place for the human's reviewed draft.
28. [x] `EvidencePicker` and `fileToEvidence` are imported only by tests: unused by design until F-87.
29. [x] Picker props have `caseId` only, no case input; test posts to the given case.
30. [~] Screenshots at 1440 and 390 checked (4102, 4103, 4104, 4101 history): no empty headings or gaps. Compared with the SCR-02 boards only by eye; the `design/` folder is not in this slim worktree.
31. [x] lint, typecheck, full `vitest run` (160 files, all pass after the two test allowances), drift test passes (`live-schema.d.ts` unchanged).

## Validation
- `npm run lint`: 0. `npm run typecheck`: 0.
- `npx vitest run` (full): 3767 pass; the 2 failures were the two name-scans above, fixed; re-run of those files plus new tests: 59 pass.
- `npx playwright test e2e/work-item-live.spec.ts` (ports 4980/4981, production build): 14 pass (7 at 1440, 7 at 390), including axe on 4102.
- Not run: `checks.sh` as one command (it runs `npm ci`, which builder turns skip); its lint, typecheck, tests and the production build (via playwright) were run separately. Django `manage.py check` not run (no backend change).
- Live Django via the test client (live-lead): `GET /api/v1/work` returns no items; `GET /api/v1/work/99999999` returns 404 `{"code":"not_found","message":"This record is unavailable."}`; upload fails on missing storage.
- Design-fidelity tool: NOT run. The page deliberately omits board parts under LC-Q1, LC-Q4..LC-Q6 and the tool is not in this worktree; an under-100% result would be those named exceptions. The design engineer can run it from the main checkout.

## Notes for the coordinator
- v7 and live work items coexist under one route by id shape. When every line has moved, delete the v7 files in `src/features/work-item/` and the dispatch in the route files.
- Project crumb from `GET /projects/{case_id}` (board conflict 6) is not built: crumb is "My work / line / Work {id}".
- `usePhoneBack` needs `AppShell`; the live view uses it as the v7 one does.
