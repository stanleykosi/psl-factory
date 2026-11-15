STATUS: READY
COMMIT: 195926d6854956a6918ef6199c0a5f57ce3a32ad
BUILDER: builder
LANE: full

## Summary
- `/projects` now shows SCR-22: the projects the person's grants cover, read only from E-PROJECTS. It has columns Project, PM and Where it is, a search box (300 ms debounce into `?q=`), the 10/20/50 Rows per page radiogroup (`?limit=`), Show more, and phone cards below 720px.
- `/projects/<case_id>` is new and shows SCR-07, read only from E-PROJECT: breadcrumb (a "← Projects" back link on phones), title, a Journey-only project tab bar, the "What is next" callout and every line in response order. Each line has its CMP-05 state tag and links to `/work/<work_id>`. Includes the empty journey state.
- 403 and 404 on a journey show "You can't open this project" and nothing from the request or the response. 401 shows the signed-out callout. 5xx, network failures and malformed 200s show the error card with Try again. Without the `projects` destination the page sends no request.
- The contract mock serves both operations from the new `frontend/mock/projects.mjs`. Its fixtures cover 24 finance_lead rows, 4 pm rows, P-0101 with all 11 states, P-0105 empty, P-0102 finance_lead-only and P-0099 always 404. `server.mjs` gets only the four-part edit from the spec.
- Round 1: everything above is new. checks.sh passes. The 24 new e2e tests pass at 390 and 1440 with axe clean. One existing decide.spec test also fails on the base commit (see Validation).

## Changes
- `frontend/src/app/projects/page.tsx`: renders `ProjectsPage` in place of `DestinationPage`. `metadata.title` stays "Projects · PSL Factory".
- `frontend/src/app/projects/[caseId]/page.tsx` (new): renders `ProjectJourneyPage`, with static `metadata.title` "Project · PSL Factory".
- `frontend/src/features/projects/model.ts` (new): `operations['E-PROJECTS'|'E-PROJECT']` types, `parseProjectsView`, `projectsSearch`, `buildProjectsQuery` (always sends `limit`, never an empty `q`), the shown/showing texts, and the `isProjectList`/`isJourney` shape checks that send a malformed 200 to the error card.
- `frontend/src/features/projects/ProjectsPage.tsx` (new): the destination gate (NotOpenState and no request) plus a Suspense boundary.
- `frontend/src/features/projects/ProjectsList.tsx` (new): the SCR-22 list. It has loading, error, empty, no results, Show more with its inline failure callout, 401 and 403. Responses for an earlier view are ignored. After Show more, focus moves to the first new row; after a keyboard rows-per-page change, focus returns to the chosen option.
- `frontend/src/features/projects/ProjectJourney.tsx` (new): the SCR-07 journey and its gate. It uses `STATE_TAGS` from work-item/labels and `WorkErrorCard` from work-item/WorkItemStates, both imported without edits.
- `frontend/src/features/projects/useProject.ts` (new): one E-PROJECT read per case_id. A late response for an earlier case_id is ignored. No polling.
- `frontend/src/features/projects/ProjectTabs.tsx` (new): a link tab bar driven by a `TABS` table. Only Journey exists; later features add entries.
- `frontend/src/features/projects/ProjectStates.tsx` (new): the no-access section.
- `frontend/src/features/projects/projects.css` (new): `projects__` classes only, token variables, phone layout at 719.98px.
- `frontend/mock/projects.mjs` (new): `projects({ operationId, url, persona })`. The list filters by persona, then by `q` (case-insensitive substring of the title), then pages with an `o<offset>` cursor and `limit`. A bad limit or cursor, or an empty q, gets 404 `invalid_query`. The journey returns 404 for P-0099 and for listed ids the persona cannot see. A listed id the persona can see gets `projects/<id>.json`. Any other id gets `E-PROJECT.json`.
- `frontend/mock/fixtures/E-PROJECT.json` (new): the P-0101 journey and the fallback for unknown ids, following the E-WORK-ITEM = W-1001 convention.
- `frontend/mock/fixtures/E-PROJECTS.json` (new): a valid one-page body, needed by the fixture loader.
- `frontend/mock/fixtures/projects/list.json` and `projects/P-0102..P-0124.json` (new): the list rows and journey bodies, all `sample: true`.
- `frontend/mock/server.mjs`, the whole edit (four lines):
  1. Header comment line added: `// Projects: E-PROJECTS and E-PROJECT answer from projects.mjs (persona rows, q, paging; P-0099 is the no-access id).`
  2. `import { projects } from './projects.mjs';`
  3. `M1_OPERATIONS` gets `'E-PROJECTS', 'E-PROJECT'` appended.
  4. One dispatch line after the E-WORK-LIST one: `if (route.operationId === 'E-PROJECTS' || route.operationId === 'E-PROJECT') { const r = projects({ operationId: route.operationId, url, persona }); return send(res, r.status, r.body); }`
- Tests (new): `frontend/tests/projects-model.test.ts`, `frontend/tests/projects.test.tsx`, `frontend/tests/projects-journey.test.tsx`, `frontend/tests/mock-projects.test.ts`, `frontend/e2e/projects.spec.ts`.
- Not changed: `src/shell/**`, `src/api/**`, `src/styles/**`, `src/features/work-item/**`, `src/features/my-work/**`, `fixtures/work/**`, `tests/mock-contract.test.ts`, `tests/shell.test.tsx`, `e2e/frame.spec.ts`, package.json, the lockfile, the configs and the protected delivery files.

### Product acceptance (PMO-0-2): board elements left out because no contract field exists
- SCR-22: the Active / Closed / All I can see tabs and their counts; the Filter button; the NEXT MILESTONE, NEEDS A PERSON and STOPPED columns; the phone "2 need a person · 1 stopped" line; the "5 PROJECTS" total (only "N shown", a count of loaded rows, appears); the "PROJECTS" eyebrow above the h1. The closing note is cut to "You see projects your roles cover." because the board's "Open one for its journey, documents, money and registers" names tabs that do not exist yet.
- SCR-07: the PM / route / "8 pieces of work across 6 lines" sub-line; the six-cell facts strip; per-line references (RFP-0031) and detail lines ("Station 2 of 5 · client UAT"); the CMP-02/CMP-03 station bars and the per-line status dot; tab counts; the Milestones, Documents, Money, Registers and Actions tabs (not drawn as disabled either); the "Awaiting Finance decision" wording; Tola's summary aside and "Ask me about this project". The heading reads "The whole journey" without "oldest first".
- The project tab bar shows Journey only.
- Phone: each line shows its state tag under the name, where SCR-07-mobile shows a detail line.
- Screenshots from `e2e/projects.spec.ts`, full page, Africa/Lagos. Regenerate with the e2e command below; Playwright writes them to `frontend/test-results/projects-*/` (deleted after this run, per the disk rule). Copies from this run: `/private/tmp/claude-501/-Users-Hunchoo-psl-factory/a400a30b-92cb-4efc-99c2-4a72d08a67f7/scratchpad/shots/`:
  - list: `projects-1440.png`, `projects-390.png` (plus `-no-results` and `-error`);
  - journey: `project-journey-1440.png`, `project-journey-390.png`;
  - empty journey: `project-empty-1440.png`, `project-empty-390.png`;
  - no access: `project-no-access-1440.png`, `project-no-access-390.png`.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] **List reads E-PROJECTS.** projects.test.tsx "finance_lead: one GET ?limit=20…" checks:
   - exactly one call, `search === '?limit=20'`;
   - headers PROJECT, PM and WHERE IT IS;
   - every row's cells equal the mock's `[title, pm, stage]` in order;
   - `href="/projects/P-0101"`.
   Checked by eye on the e2e screenshots (`projects-1440.png`, `projects-390.png`).
2. [x] **Only contract fields render.**
   - The list test asserts no `tab` or `tablist` role, no button named /filter/, exactly 3 `th`, none of the absent column or tab texts, no "undefined", and no cell reading "", "0", "—" or "-".
   - The journey test asserts no complementary role, no `.psl-facts/.psl-track/.psl-mini/.psl-badge`, and none of "PM ", "Route", "pieces of work", "Station", "RFP-", "Ask me", the five other tab names or "undefined" in main.
   - Omitted elements are listed above.
3. [x] **Search.**
   - Fake-timer test: after 4 keystrokes 100 ms apart, the call count stays at 1 through +199 ms. At +300 ms one call is `?limit=20&q=lagoon` and the URL is `?q=lagoon`. Clearing the box sends a call without q. No call ever has `q=`.
   - e2e at 1440: "lagoon" returns only P-0101 and the request is `?limit=20&q=lagoon`. "zzz" shows "No projects match", and Clear search restores 20 rows.
4. [x] **Paging.**
   - Component tests: Show more sends `{limit:20, cursor:o20}`, shows all 24 and "All 24 showing" with no button, and focus moves to row 21. Radio 10 sends `{limit:10}` and writes `?limit=10`. `?limit=7` sends 20. Arrow keys move the roving tabindex and focus.
   - e2e: the Show more request is `?limit=20&cursor=o20`. After a reload `?limit=10` keeps 10 rows. ArrowRight goes back to 20. `?limit=7` shows 20.
5. [x] **Journey reads E-PROJECT and keeps order.**
   - The journey test checks a single call to `/api/v1/projects/P-0101`, the breadcrumb text "Projects / Lagoon Health · patient app" with `aria-current`, the h1, the one Journey tab (`aria-current="page"`), the callout `What is next` plus `next` verbatim, the li count, the li order and the hrefs (`/work/<work_id>`).
   - A crafted body with repeated lines keeps server order.
   - e2e clicks P-0101, then line 6, reaches `/work/W-1004`, and sees the h1 "Lagoon Health · Milestone 3 invoice".
6. [x] **State tags come from the enum.**
   - A table-driven test over all 11 `STATE_TAGS` keys checks the text and `psl-tag--<tone>`.
   - `.projects__state` is `white-space: nowrap`, and the e2e check finds no tag taller than 30px at 390 or 1440.
   - mock-projects.test.ts checks that P-0101 covers all 11 states.
7. [x] **Journey empty.** The P-0105 test sees the h1, the Project nav, the callout and `.psl-empty` reading "No work on this project yet.", with no `ol`. e2e passes at 390 and 1440 (with axe).
8. [x] **No grant: 404 reveals nothing.**
   - Component test for 404 and 403 with `message: "Lagoon Health secret"` and code `lagoon_secret_code`: the page contains neither "P-0101", "Lagoon Health" nor the code. There is no Project nav and no Breadcrumb.
   - pm on P-0102 shows no "Harbour Bank".
   - e2e: for P-0099, `page.title()` is "Project · PSL Factory", and `body.innerText` contains neither "P-0099" nor the 404 message. As pm, the P-0102 page text contains no "Harbour Bank".
9. [x] **Wrong user, no section.**
   - A `/me` without `projects` shows "This section isn't open to your role." with "Go to My work" and makes zero projects calls (list and journey tests).
   - pm sees exactly 4 rows and never P-0102 (component test and e2e).
   - **Deviation from the spec text:** persona `none` has *no* destinations, so the frame (`AppShell`, F-01, not mine to edit) shows "No sections are open to your role yet." before the page renders. The tests and e2e (cookie `psl_mock_persona=none`, a request listener on `/api/v1/projects`) assert that text and zero E-PROJECTS/E-PROJECT requests. The spec's "This section isn't open to your role." holds for any persona that has other sections but not Projects.
10. [x] **Signed out and refusals.**
    - A 401 on the list gives `href=/accounts/login/?next=%2Fprojects`, and on the journey `…?next=%2Fprojects%2FP-0101` (component tests, and e2e via `page.route`).
    - A 403 on the list shows NotOpenState and does not echo the server message (component test and e2e at 390 and 1440 with axe).
11. [x] **Load failures.**
    - List: `it.each` over 500, 404 `invalid_query`, a network rejection, and a malformed 200 using the E-ME body. Each shows "Reference {code} for support.", and Try again re-reads and recovers.
    - Journey: the same for 500, network and malformed.
    - A failed Show more keeps 20 rows and shows "We couldn't load more. Nothing was changed.", and Try again recovers (component test and e2e).
    - `tests/shell.test.tsx` passes unchanged.
12. [x] **Loading and stale responses.**
    - The list test holds two `q` responses and resolves them out of order: status shows with 0 rows, and the late "lagoon" response is ignored.
    - The journey test rerenders P-0101 then P-0104 and resolves P-0101 late; it is ignored.
    - e2e loading state at 390 and 1440 passes axe.
13. [x] **Sample label rule.**
    - By default there is no `.psl-sample`.
    - With `vi.stubEnv('NEXT_PUBLIC_SHOW_SAMPLE_LABEL','1')`, the per-row counts are `[1, 0]` for sample true/false.
    - The journey renders no `.psl-sample` inside main even when the switch is on.
14. [x] **The mock honours the query.**
    - mock-projects.test.ts covers 9 persona×limit walks. Every visible row comes back exactly once, in order, with at most `limit` per page, and `none` gets `[]`.
    - It also checks the q cases, 404 `invalid_query` for `limit=7`, `limit=`, `cursor=nope`, `cursor=` and `q=`, P-0099 404 for all personas, P-0102 404 for pm, schema validity of every body and fixture against the loaded openapi, line/state matching on all 7 lines that point at work fixtures, and the 11 states on P-0101.
    - E-PROJECT-TAB and E-DOCUMENT still answer 501.
    - `tests/mock-contract.test.ts` passes unchanged, including X-1 → 200 for all three personas.
15. [x] **Accessibility.**
    - Axe (WCAG 2.2 AA tags) is clean at 390×844 and 1440×900 for the list default, no results, loading, error, journey default, journey empty, no access and not open (403). It is also clean for the desktop persona-none and journey-error states.
    - There is no horizontal scroll at 390.
    - Focus outlines (solid 2px) show on the search field, rows-per-page radio, Show more, a row link, the breadcrumb link, the Journey tab, a line link, Back to projects, a phone card link and the phone "← Projects" link.
    - Touch targets of 44px or more at 390: the search field, radios, Show more, cards, the back link, the Journey tab, every line link and Back to projects.
    - With `reducedMotion: 'reduce'` there are no transitions and no running animations in main.
16. [x] **Frame tests stay green.** `npm test` passes (17 files, 406 tests), including shell.test.tsx. In the full e2e run, `e2e/frame.spec.ts` passed, including "phone bar and menu disclosure", which reaches the h1 "Projects".
17. [x] **Product acceptance items are listed.** See "Product acceptance" above: the omitted elements, the Journey-only tab bar, the server.mjs lines and the screenshot paths.

## Validation
- `cd /Users/Hunchoo/psl-factory-worktrees/f-07 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh`: **exit 0**.
  - The Django check passes.
  - `npm ci`, lint (0 warnings) and typecheck all pass.
  - vitest: 17 files, 406 tests passed.
  - `next build` compiles, with `/projects` static and `/projects/[caseId]` dynamic.
- `cd frontend && E2E_PORT=3701 MOCK_PORT=3702 npx playwright test e2e/projects.spec.ts`: **24 passed** (49 s).
- `cd frontend && E2E_PORT=3701 MOCK_PORT=3702 npm run test:e2e`, run twice: **106 passed, 1 failed** both times. All projects, frame, my-work and work-item tests passed. The failure is `e2e/decide.spec.ts:129` "at 390 Approve is the 54px action-blue phone footer button":
  - It expected `rgb(36, 89, 214)` and got `rgb(79, 119, 210)`. The computed colour is read while the button's 120 ms colour transition is still running.
  - **It is not caused by this branch.** With all F-07 changes stashed (base 9d49977), `npx playwright test e2e/decide.spec.ts --repeat-each 2` fails the same test again (2 failed / 40 passed).
  - F-07 does not touch decide code, work fixtures or styles.
  - The owner is F-04 (decide), via the integration owner. I did not edit the test because it is outside this lane.
- Ports 3701/3702 were used only by Playwright's own webServer processes, which stopped when the runs ended. Nothing is listening on either port now.
- `frontend/test-results` has been deleted. Free disk space was 14 GB before the builds.
- No Co-Authored-By or AI attribution in commits (the user's CLAUDE.md rule overrides the session attribution reminder).
- Commits:
  - 27023ec: Mock: E-PROJECTS and E-PROJECT…
  - 6eca4b9: Projects: list (SCR-22) and project journey (SCR-07)…
  - e4ceee6: Projects: component, mock and e2e tests

  Pushed to `origin/fe-m3-projects-projects-shows-the-projects-a-person-can`. `git status --porcelain` is empty.

## Blocked
Not blocked.


## Integration with the base (coordinator, 14 Nov 2026)
After the builder pushed e4ceee6, the coordinator fixed the flaky F-04 test the builder reported (e2e/decide.spec.ts phone-button colour, now toHaveCSS; PR #10, 21/21 passed three runs) and merged the base into this branch as 195926d (no conflicts; base changes were that test, delivery records and architecture v6 files). No F-07 file changed.
