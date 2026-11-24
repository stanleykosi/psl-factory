VERDICT: PASS
COMMIT: a24195b3bd085eb5730a9155bce08b2e22fc9e92
REVIEWER: qa-reviewer
AUTHORITY: integrated QA reviewer

## Summary
- D-193 re-check on head a24195b3 (merge of origin/main 1e78793f, F-111 and F-87). The sync changes no F-75 tab code, shared tab import or project-tab mock response: the only F-75 files it touches are mock/server.mjs (new issue and work-live hooks that match no project tab path) and tests/next-config.test.ts (one allow-list entry). Verdict PASS carries forward. No servers or suites were run for this re-check.
- Earlier round evidence (head d5c20396, which had the same F-75 code) is kept below. Frontend-checks passed on a24195b3 (run 45486815610, reported by the coordinator; not rerun by me). Ci-mode checks passed on d5c20396 (GitHub Actions run, success, reported by the coordinator; not rerun by me).
- MOCK, shared dev server (Next 4970, mock 4971), not touched. `e2e/project-tabs.spec.ts` ran in full through a scratch config with the existing server: 31 passed, 4 failed. All 4 failures are the "exactly one request" checks (registers test line 126 and the error/Try again test line 217, at 1440 and 390). Each received the same URL twice. The same doubling shows on the F-71 tabs (milestones makes 2x money + 2x milestones, money 2x) on first load. That is the `next dev` StrictMode double effect, not an F-75 defect. Not proved under `next start`.
- The spec's success and failure journeys were walked by hand at 1440 and 390 on the mock (P-0101, P-0102, P-0106, P-0099, P-0103), with 401/403/404/422/500/503 forced by route stubs. All behaved as specified (details below). F-71 Money and Milestones load beside these tabs with no console errors and no sideways scroll, and the e2e milestones cases passed.
- LIVE (criterion 20), read-only on Django 8010 (started by me, PID 68245, stopped afterwards; 8010 no longer listens): the qa-seed account's registers and actions bodies validate against the 1.24.0 contract schema with Ajv (strict). But the account's only project is empty (all totals 0), so only the empty state is proved live.
- Not proved: a live browser render (the shared frontend points at the mock; no second frontend was started), live rows, counts, `counts.overdue`/`unassigned` with real values, live Show more, the `live-lead` account named in criterion 20, and the 4 one-request checks under a production build.

## Findings
None.

## Verified
- UI-1-1 | verified | MOCK 1440, P-0101 Issues and Changes: column headers read ISSUE, WHAT, SEVERITY, OWNER, STATE, AGE (checked against the live DOM by the UI reviewer, and the render still loads here without errors).
- UX-1-1 | verified | MOCK, P-0102 Registers, Show more sends one `GET ?page=2`. The button goes. Focus lands on TR "ISS-1026 Android login loop (26)" at 1440 and on the card DIV "ISS-1026" at 390.
- UX-1-2 | verified | MOCK: the Severity note is shown on Issues only (UX reviewer's check; Changes shows none in my walk).
- TECH-1-1 | verified | MOCK: after the merge, the Milestones, Money, Registers and Actions tabs load at 1440 and 390 with no page errors and no sideways scroll. The e2e milestones, money and axe cases all pass. `?page=0` and `?page=x` against the mock registers endpoint answer 422 at both sizes.

## D-193 re-check (a24195b3)
- Range checked: `git diff d5c20396 a24195b3 --stat` is 26 files (2113 insertions, 80 deletions), all of main's F-111 (#116) and F-87 (#113) plus the merge; no backend or contract file.
- F-75's own frontend files: `git diff --name-only 4a88c26b 286b4105 -- frontend/` gives 89 files. Of these, only two differ between d5c20396 and a24195b3: `frontend/mock/server.mjs` (13 lines) and `frontend/tests/next-config.test.ts` (2 lines). The rest (including RegistersTab.tsx, ActionsTab.tsx, TabParts.tsx, useProjectTab.ts, useProjectSections.ts, sectionsModel.ts, tabsModel.ts, project-tabs.mjs and the project fixtures) have an empty diff.
- `mock/server.mjs` hunks: an import of issues.mjs; `resetIssues()` in the reset route; a GET hook that calls `issuesRoute` before the other routes; and a `drop` branch inside the work-live path. The hook only fires when `ISSUES_PATH` matches (`/api/v1/work/51nn[/issue-followup]` or `/api/v1/projects/{id}/issues/{n}[/messages]`). `/api/v1/projects/{id}/registers` and `/actions` do not match, so they fall through to `E-PROJECT-TAB` -> `projectTab` (server.mjs:469), which is unchanged. The `drop` branch applies only to `WORK_LIVE_PATH` and `CASE_FILES_PATH`.
- `tests/next-config.test.ts`: the sync adds the comment text for issues.mjs and the allow-list entry `'issues.mjs'`. F-75's `'project-sections-model.test.ts'` entry is kept and no assertion changed.
- Shared modules the F-75 tabs import (`@/components`, `@/api/client`, `@/api/errors`, `@/shell/FrameStates`, `@/features/work-item/WorkItemStates`) are untouched by the sync. The sync changes `src/features/workspace/*`, `work-item/live/*`, issue-followup, and the alerts/RFP/start-work code; F-75 tab files import none of them (grep).
- Not run: no servers, no `npm ci`, no suite, and no single test file. The live Django evidence below is unaffected (no backend file changed).
- Impact on my lens (Registers and Actions tabs, mock and live journeys): none. PASS.

## Evidence

Commands and results (scratch files in /private/tmp/claude-501/-Users-Hunchoo-psl-factory/4e9455a7-949a-43f4-9a55-a544c0864821/scratchpad/qa/):

Mock e2e
- `npx playwright test -c <scratch>/pw.config.mjs` from frontend/ (baseURL http://localhost:4970, cookies psl_mock_demo=off and psl_mock_speed=fast, no webServer). Result: 31 passed, 4 failed (4.6 min).
- Failures: `registers: the register and search live in the URL...` (1440, 390) at `expect(requests.map(u => u.search)).toEqual([''])` received `['', '']`; `a tab read that fails shows the error card and Try again sends one new request` (1440, 390) at `expect(requests).toHaveLength(1)`, received two identical URLs.
- Classification: StrictMode double read in dev. A probe of first-load requests at 1440 and 390 shows 2 GETs for registers, 2 for actions, 2 for money, and 4 for milestones (2x money + 2x milestones). The F-71 tabs double the same way. The steps after line 126 of the registers test did not run, so I walked them by hand below.
- Everything else passed on both sizes, including axe (WCAG 2.2 AA), the one-h1 and named-table checks for P-0101, P-0102, P-0106 across milestones, registers and actions, no sideways scroll, register keyboard keys, and the P-0102 paging case.

Mock journeys (P-0101 as persona pm, Africa/Lagos, 1440 and 390)
- Registers: the "Register" tab list reads Issues 3, Changes 2, Emergencies 0, RFPs 1. Only GET requests. Escalations text is absent. No row has a link.
- Register switch (Changes, Emergencies, Issues): URL follows (`?register=changes`, `?register=emergencies`, none for Issues), 0 extra reads. Over 9 clicks in a second run, 9 of 9 switched. One earlier click on Issues at 1440 right after a fresh load did not switch; I could not reproduce it and read it as a click before hydration on the first dev compile.
- Search `android`: 1 read `GET ?q=android` (URL `?q=android`), badges become Issues 1, Changes 0, Emergencies 0, RFPs 0. Switching register with the search set: 0 extra reads (`?register=changes&q=android`). Clearing the search returns to the register URL. `?q=zzz` shows the no-match text with Clear search.
- Show more on P-0102 (Issues 30): 25 rows, then `GET ?page=2`, button gone, focus on the first new row (1440) or card (390). No Show more on Actions in the mock data, so Actions paging was not walked (covered by the render tests only).
- Actions: header "9 ACTIONS · 2 OVERDUE · 1 WITHOUT OWNER", "From Weekly sync · 10 Nov" on rows, due "13 Nov", no OVERDUE row tag, no "due 0". Search `sign`: "1 actions match “sign”".
- Empty: P-0106 shows "No issues on this project yet." and "0 ACTIONS · 0 OVERDUE · 0 WITHOUT OWNER / No actions on this project yet." Emergencies shows "No emergencies on this project yet." (a 0 only because the server sent 0).
- Access: P-0099 shows "You can’t open this project" (no row text). P-0103 shows "No access to this tab" on both tabs.
- Stubbed statuses, both tabs, both sizes: 401 shows "You’re signed out. Sign in" and the path is kept; 403 and 404 show "No access to this tab"; 422, 500 and 503 show the error card ("We couldn’t load this tab. Your work is safe...") with Try again, and Try again sends exactly 1 new read.
- Requests are GET only throughout. `?page=x` on the page URL is ignored (the page reads page 1).
- Mock `GET .../registers?page=0` and `?page=x` answer 422.
- Unknown is never 0 in the walked pages. Dedicated `Unknown` due and null-owner cases were not walked (no fixture on this server shows them); the unit tests cover them.

Live (Django 8010, Postgres 55433, qa-seed)
- Started: `PGDATABASE=psl PGUSER=psl PGHOST=127.0.0.1 PGPORT=55433 PSL_ENV=development PSL_DJANGO_UI=0 PSL_FRONTEND_ORIGINS=http://127.0.0.1:4970 .venv/bin/python manage.py runserver 127.0.0.1:8010 --noreload` from the lane-b2 worktree, PID 68245, stopped with `kill 68245` at the end. The password was read from the login file by script and never printed or copied.
- Signed in (`POST /api/v1/session`, a session record only), then GET only: `/api/v1/projects` returned one project (4a228bcb-f762-4bc6-858e-74e9ab11ebd3, "Project delivery"). I did not call logout (my script stopped early), so one session remains on the dev database; no record or account was written.
- `GET .../registers`: 200, sections issues, escalations, changes, emergencies, rfp, all total 0, counts null, items empty. `GET .../actions`: 200, section meetings, total 0, counts {total 0, overdue 0, unassigned 0}. With `?q=zzzz` both are 200 with the same empty answers.
- Ajv 2020 strict plus ajv-formats against the contract's 200 schema for `/api/v1/projects/{case_id}/{tab}`: registers, actions, both `?q=zzzz` bodies and `?page=99` all VALID. live-schema.d.ts is generated from this contract, so it is not a separate check.
- `?page=0` and `?page=x` answer 422 invalid_filter ("Choose a page from 1 to 10000"). `?page=99` answers 200 with page 1 and empty items (not 404, unlike the mock's past-the-last 404 for Milestones). A case id the account cannot read answers 404 not_found, and an unknown tab 404.
- Hybrid check: the live empty bodies fed to the real page through a route stub at 1440 and 390 render "Issues 0 Changes 0 Emergencies 0 RFPs 0 / No issues on this project yet." and "0 ACTIONS · 0 OVERDUE · 0 WITHOUT OWNER / No actions on this project yet.". No console errors and no sideways scroll. Escalations in the live body is not drawn.

## Notes
- Mock versus live difference, not blocking: for registers `?page=99` live answers 200 page 1 where the mock answers 404 past the last page on Milestones (F-71's choice). Registers and Actions in the mock were not probed past the last page by me.
- The browser console shows "Failed to load resource" lines for the intended 403/404 answers on P-0099 and P-0103. One 500 console line appeared once on a first dev compile and not again.
- To close criterion 20 fully, someone needs a live project with real issues, changes, actions and overdue items, plus a browser pointed at 8010 as `live-lead`. Fidelity sign-off (B35) remains the design engineer's.

## D-193 re-check (diff only, no servers, no full runs)
- `git diff 286b4105 d5c20396 --stat`: 64 files, all under frontend/ (none outside). Changes are main's F-61 alerts, F-88 received RFP/assign-PM, start-work lines, the shell alert badge, mock server routes for alerts and received bids, and their tests.
- `git diff 286b4105 d5c20396 -- frontend/src/features/projects/RegistersTab.tsx frontend/src/features/projects/ActionsTab.tsx`: empty (0 lines). No F-75 screen code changed. No other file under features/projects or the project-tab mock changed.
- `frontend/tests/next-config.test.ts`: allow-list is now one entry per line; 'project-sections-model.test.ts' is kept as an entry. The F-61 sentence in the comment and 'received-bids.mjs' come from main. `frontend/tests/demo-mock.test.ts`: only main's alert-shape assertions changed. No F-75 assertion was weakened.
- `frontend/mock/server.mjs` and `AppShell.tsx` diffs: added alert and received-bid routes, removed the v7 alert operations from the mock list, and changed the bell count source. The project tab routes (E-PROJECT-TAB) and the registers/actions mock are untouched, so the mock journeys, status stubs and page-parameter 422s I walked are not affected.
- Impact: nothing from main changes what my lens covers on the Registers and Actions tabs. Live evidence (Django 8010, Ajv against the 1.24.0 contract) is unaffected: no backend or contract file is in the diff. The earlier note that the Show more and one-request checks are unproved under `next start` still stands.
