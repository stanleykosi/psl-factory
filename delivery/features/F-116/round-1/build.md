STATUS: READY
COMMIT: df543dd324979cfc4f58606d10db939185980118
BUILDER: builder
LANE: full

## Summary
- The archive work item (`delivery-archive/v1`, panel key `archive-files`) now draws live: status sentence, archive index by the served `group`, store line, per-group file lists, and the Next block only when `verified` is true.
- A person starts the archive from the served source list (preselected from `required_source_ids`); "Look up" and "Copy again" appear per file only where the read allows.
- Every write follows the shared rules: one request per press, no automatic retry, a lost answer locks all archive controls ("We couldn’t confirm that this happened. Check the page before trying again."), the result is said only from the re-read.
- New files only plus one import line in `workspace/lines/index.ts`; nothing in shared public APIs changed.
- Mock ids: the spec's 4401 to 4407 are taken, so fixtures are 5301 to 5308 (5301 verified, 5302 working, 5303 uncertain, 5304 ready to start, 5305 unavailable, 5306 held and limit, 5307 work revision null, 5308 all confirmed but not verified).

## Changes
- `frontend/src/features/delivery-archive/archiveModel.ts`: types from `live-schema`, grouping, group state words (worst first, counts), status sentence, sections, start source rules, command descriptors (`archive.reserve`, `archive.lookup.<job>`, `archive.retry.<job>`; tokens from the same read, null stays null, no key field, `action: null` used for the start so the makeCommand `fixed` bug is not hit).
- `.../ArchiveActions.tsx`: Start block (checkboxes from `sources[]`, only when `can_reserve`), files by group in a disclosure with the row buttons, "Queued" line after a 202, error callout.
- `.../archiveAdapter.ts`: registers `archive-files`.
- `frontend/src/features/workspace/lines/index.ts`: one import line.
- `frontend/mock/archive-live.mjs` + `mock/server.mjs` (registration and reset): work read, `archive-files`, recovery, `actions`. `tests/next-config.test.ts`: allow-list entry `archive-live.mjs` (one line).
- Tests: `tests/archive-model.test.ts` (15), `tests/archive-live.test.tsx` (17), `tests/archive-mock.test.ts` (5, contract shapes via ajv), `e2e/archive-live.spec.ts` (4 tests at 1440 and 390, axe clean, 44px Start on phone).

## Fixes
None (round 1).

## Acceptance criteria
1. [x] 5302 working sentence, Copying rows, no Tola card, no "Ask Tola": live test and e2e (`e2e/archive-live.spec.ts`).
2. [x] 5301 verified sentence; 5308 (verified:false, all confirmed) shows no sentence: live test and model test.
3. [x] Groups from `files[].group` as served (a "Legal" group in the model test); no hard-coded group list in src.
4. [x] "Not confirmed · 6" for a 6 unknown plus 3 confirmed group; the model test checks counts add to `files.length`. A mixed group reads "Not confirmed · 6, Archived · 3" (headline first, the others after, per part 2).
5. [~] "Handover can start now…" only when `verified`. The "Open handover" link is HELD (see Held): no delivery overview read is wired, so the sentence is drawn without the link.
6. [x] 5304: three sources, two checked, none checked disables Start with its reason; no source outside `sources[]` can be sent (`chosenSources`).
7. [x] One POST `{expected_revision, case_revision, source_ids}`, "Queued" on 202, button held while the write runs: live tests (double press, gate).
8. [x] `can_reserve:false`: no Start control and no placeholder (5301, 5302).
9. [x] 409 on Start: the shared "This changed while you were working" notice, a re-read, no second POST. Wording is the shared hook's, not the spec's "The page has been refreshed.".
10. [x] 422 message and first field message; 403 csrf "Press the button again."; 404 unavailable; 429/503 "Try again shortly."; dropped connection locks and re-reads. Wording is the shared hook's.
11. [x] 5303: sentence, group "Not confirmed · 6", six Look up buttons, no Copy again.
12. [x] Lookup posts `{revision: row job.revision, action:"lookup"}` to that row's job.id, re-read, Copy again only for rows whose re-read lists `retry`.
13. [x] Copy again posts `{revision, action:"retry"}` once; all row buttons disabled while a write runs or is locked.
14. [x] 409 on a recovery: refresh, no repeat; a lost lookup locks every row and no Copy again is guessed.
15. [x] "Check what happened" is the work item's own control (shared `work.reconcile`, listed by `actions[]`): shown only with `reconcile`, body `{expected_revision, action:"reconcile"}`, tested on 5303. Not duplicated in the panel.
16. [x] No "mark found", "never purge", "no approval": grep returns nothing in src; text check in tests.
17. [x] Null job: "Not started", no buttons; null receipt: no receipt text; null store: no store line; `limited`: "Copy limit reached".
18. [x] Null token: command disabled and body keeps null (model test); 5307 (work revision null) sends nothing.
19. [~] Polling is the work item frame's (`useLiveWorkItem`: 5 s while `processing`/watching, visibility pause, panel re-read on each new `updated_at`). No separate poll in this feature; a failed panel read keeps the last good read with the frame's warning.
20. [x] 5305 and an unknown id read "This record is unavailable."; a person with no write rights sees the index and no controls (5301).
21. [x] 5306: "2 files are on hold." and "Copy limit reached", no buttons on held rows.
22. [ ] Not run against live Django (no backend session used); shape-checked against the contract with ajv in `archive-mock.test.ts`.
23. [x] Only `@/api/live-schema` types; `grep "api/schema'"` returns nothing in the feature.
24. [x] Adapter registered via `registerLineAdapter`; `commands()` returns the descriptors (per-file ids carry the job id); body has the action, tokens, no key field.
25. [x] 1440 and 390 e2e pass: no side scroll, axe clean, no empty headings. Fidelity tool not run (lean mode, board has no live-shape equivalent for the Start block).
26. [x] lint, tsc, full vitest pass.
27. [x] Tests listed above.

## Held
- Delivery observation form (`delivery-observations`): held per Question 1 (no authority flag, `job_type` or proof list served).
- "Open handover" link: the handover work id comes from the delivery overview read, not wired here; the Next sentence shows without it.
- The "Check the N files" scroll line: not built (the group disclosures open on their own for groups with unknown or missing files).
- Backend gives `lookup` on `held` files too (`archive_transfer.py`); following the spec, held and waiting files get no button.
- "Started {at}" from the first history row: not drawn (the frame's History tab already shows history).

## Validation
- `npx eslint . --max-warnings 0`: clean. `npx tsc --noEmit`: clean. `node --check mock/server.mjs` and `mock/archive-live.mjs`: ok.
- `npx vitest run`: 210 files, 4781 tests passed (includes next-config, demo-mock, mock-contract, line-adapter, live-work-item).
- `E2E_PORT=4890 MOCK_PORT=4891 npx playwright test e2e/archive-live.spec.ts`: 8 passed (4 tests x 1440 and 390, production build). Ports free afterwards.
- `delivery/checks.sh` not run locally (ci mode waits for GitHub on the pushed head); the same steps ran above.
- Recurring bug note: `useWorkCommand` draws no success notice for line writes (only the item's own controls do), so any line wanting text after a 202 needs its own, as "Queued" here.
