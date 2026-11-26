STATUS: READY
COMMIT: b92c63b75451d6be0d30f2683f9830b59597f0a7
BUILDER: builder
LANE: full

## Summary
- Hypercare work items (`delivery-hypercare/v1`) now draw from `GET /work/{id}/stability`, `/stability/events` and the project issues register: four states (Setup needed, Evaluating, Qualified, Not met), each criterion Met / Not met / Not known, checks, metric readings per owner (counts only), open issues in a separate table, and release and acceptance counts.
- Pause and continue is NOT rebuilt: F-87's work item controls already send `POST /work/{id}/background` `{expected_revision, enabled}` on every line whose `actions` lists `background` (buttons "Pause background work" / "Continue background work"). A second control in the page would duplicate it, so this feature adds tests and mock data for it on hypercare and no button. Deviates from the spec's own `BackgroundControl` and its watching/resume signal (see Held).
- Mock ids: the spec's 4201 to 4208 are taken on main, so each is the spec number plus 1000: 5201 to 5208 (5209 not used). 5201 setup, 5202 evaluating, 5203 qualified, 5204 not met, 5205 paused, 5206 404, 5207 events 503, 5208 issues 503.

## Changes
- `frontend/src/features/hypercare/hypercareLabels.ts`: criterion wording, rule words (at most, at least, exactly), result tags.
- `hypercareModel.ts`: state order, sections for each panel, open-issue table and Blocks hypercare tag, release and acceptance facts, `readOpenIssues` (follows `next_before`, stops at 100 rows read, keeps Open and In Progress).
- `hypercareAdapter.ts`: registers `stability` and `stability/events`. `HypercareActions.tsx` (the stability panel's Actions slot) draws the open issues block with its own Try again, then the Next lines; it sends nothing. `useHypercareIssues.ts`: the issues read, re-run only when `assessment_id` changes.
- `workspace/lines/index.ts`: one import line. No other shared file changed (nothing in `workspace/` or `work-item/` apart from that line).
- `mock/hypercare-live.mjs` (new), registered in `mock/server.mjs` (route plus reset call, braces checked with `node --check`). `tests/next-config.test.ts`: one allow-list line (`hypercare-live.mjs`, carries the contract's required `django_url`).
- Tests: `tests/hypercare-model.test.ts`, `hypercare-mock.test.ts` (contract-shape check by ajv, including the background body), `hypercare-live.test.tsx`, `e2e/hypercare-live.spec.ts`.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Setup needed (5201): tag, "Hypercare criteria are not set.", held stability check with its finding, no Criteria list: live test and e2e at 1440 and 390.
2. [x] 5202 Evaluating: Not known results (never Met), one Engineering reading, "No reading yet" for the other owner, Pause control (F-87's): live test, e2e.
3. [x] 5203 Qualified: "Verified", every result Met, "No open issues." (the Resolved issue is filtered).
4. [x] 5204 Not met: findings, Not met and Not known tags, open High issue tagged "Blocks hypercare" in a separate table from the readings.
5. [x] Criterion keys map to the wording; unknown key shown raw: model test.
6. [x] State order incl. edge combinations: model test.
7. [x] No Day N of 30, Tola cards, Log an observation, Log an issue, Record release, Ask Tola; no empty heading: model and live tests, e2e. (Those strings appear only in tests.)
8. [x] No reading value drawn; missing `due_at` reads "720 hours from the release"; null finding draws no line: model test.
9. [x] Release and acceptance counts, "None recorded", "Not recorded", no button: model and live tests. The acceptance packet is a 64-character digest in the contract, so the page shows its first 12 characters and an ellipsis (a 390 px page scrolled sideways with the full value). Question for the design engineer.
10. [x] Open issues from the register, Resolved and Closed dropped, missing owner "No owner", two pages followed, stops at 100: model test.
11. [x] 5207 (events) and 5208 (issues) each fail alone with their own Try again that repeats only that read: live test, e2e.
12. [x] 5206 reads "This record is unavailable." A live id the account cannot see answers the same 404 through the page's shared error mapping (F-85), not retested here.
13. [ ] 401 signed-out link and csrf not shown as no-access: shared page code (F-85/F-87 tests), not re-tested here. 403 csrf_failed on the write reads "Press the button again": live test.
14. [x] One POST `{expected_revision: 8, enabled: false}` with `X-CSRFToken`, no `case_revision`, disabled while running, double click makes one request: live test and e2e.
15. [x] Continue on 5205 sends `enabled: true`; the page re-reads the item and the stability panel and says the state from the re-read: live test (counts the GETs).
16. [x] Write errors: 409, csrf, 403, 422, 429, 503, 500, lost answer before and after the write: live tests count the POSTs (always 1). The 500 and lost-answer-before-write cases lock the button with "We couldn’t confirm that this happened. Check the page before trying again."
17. Not built as a separate rule: a null revision holds every F-87 control (existing F-87 tests).
18. Covered by F-87's rule: controls are drawn from the item's `actions` / `available_control`; the page keeps no rule of its own. The spec's "Pause only when watching" signal was not used (see Held).
19. [x] No v7 `WorkItem` import; `grep "api/schema'" frontend/src/features/hypercare` is empty; `git diff --stat origin/main -- frontend/src/features/work-item` is empty and the only `workspace/` change is the one import line.
20. [x] Adapters register and read through the real page (`LiveWorkItemView`). The `commands()` descriptor is not built (no separate control).
21. [x] The only POST is the background call: live test (`posts()` equals one path) and e2e.
22. Not run against live Django: the demo database has no hypercare work item (`GET /work?line=delivery-hypercare/v1` returned none for the demo PM). Contract shape of the reads and the write is checked by ajv against the mock.
23. [x] No horizontal scroll at 390 and 1440, axe WCAG 2.2 AA clean on four states, Pause at least 44 px on the phone. Not compared with the SCR-46 boards (fidelity tool not run, see below).
24. [x] tsc, eslint, vitest all pass.

## Held and why
- A separate pause control with the spec's signals (`current_activity.watching`, `available_control` has `resume`): not built. The work item's own F-87 controls already send this exact write on every line, so this page does not repeat it. Backend `actions` lists `background` for any controllable work, so both Pause and Continue buttons show on the work item (F-87 behaviour); the spec's one-button-by-state would be a change to that shared control, which belongs to lane C.
- Design fidelity tool: not run. The boards are replaced on purpose (no day count, no Tola card, counts instead of issue/note rows, added Checks and Release blocks) so the spec's own Conflicts list applies. The design engineer's board for SCR-46 and exceptions still needed.
- Issue reference is plain text, no link (spec Question 1a). "Open Setup" is text, no link.
- Next lines are drawn after the open issues (the frame draws a panel's own sections before its Actions); the events panel (Release and acceptance) follows below both, not above Next as the spec orders it.
- Not known counts: the readings table shows "n of m met", where unknown results count as not met yet; a metric-less owner reads "No results yet".

## Shared bugs
- `makeCommand` `action: null` deleting `action` in `fixed` was not hit (no command is built here).
- F-87 draws both Pause and Continue background buttons on every line, whatever the state. Worth fixing once in `workItemCommands`/`ItemControls` (lane C).

## Validation
- `npx tsc --noEmit`: clean. `npx eslint . --max-warnings 0`: clean. `node --check` on `mock/server.mjs` and `mock/hypercare-live.mjs`: ok.
- `npx vitest run`: all 205 files, 4687 tests passed (before the packet-shortening edit); after it the hypercare, next-config, demo-mock, mock-contract, line-adapter and live-work-item files rerun: 8 files, 433 tests passed; the two edited hypercare files 46 passed. New tests: model 25, mock 6, live page 21, total 52 plus 12 e2e.
- Playwright `e2e/hypercare-live.spec.ts` on the mock at ports 4900/4901 (production build, run by playwright's own web servers, both gone after the run): 12 passed (6 at 1440, 6 at 390).
- The old v7 W-31xx hypercare fixtures and `e2e/delivery-hypercare.spec.ts` are untouched.
