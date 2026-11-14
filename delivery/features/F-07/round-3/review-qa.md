VERDICT: PASS
COMMIT: 4e8a8c7d75957adbc9de381887453e0e5e11ecf4
REVIEWER: reviewer-qa
AUTHORITY: integrated QA reviewer (round 3 extra round, D-47)

## Summary
- Tested the shared production build http://localhost:4711, served from the f-07 worktree at 4e8a8c7 (worktree clean; `.next/BUILD_ID` 16:54, after the head commit at 16:46; the served chunks include `/agents/tola`). It talks to the contract mock on :4712. 12 of 12 headless browser journeys passed (10 at 1440, 2 at 390), plus 22 direct API calls through :4711. I reset the mock before and after every journey and at the end (204 each time).
- Success path: the list opens on Active and requests `?limit=20` with no `status`. It shows tabs Active 22 / Closed 2 / All I can see 24 and the count "22 PROJECTS". Show more requests `cursor=o20` and ends with "All 22 showing". Closed (`status=closed`, 2 rows) and All I can see (`status=all`, 20 rows, "24 PROJECTS") write the URL and survive a reload. Search "lagoon" requests `q=lagoon` and gives 1 row; "zzz" shows "No projects match", and Clear search brings back 20 rows. Opening P-0101 shows the breadcrumb, the title, "What is next", 8 lines in order with their tags, and Tola's panel. The panel has the mascot image (it loads, naturalWidth 192), the summary and "Ask me about this project" linking to `/assistant`. Line 7 opens `/work/W-1001`. Back returns to the journey, and the breadcrumb returns to `/projects`.
- Failure paths: P-0099 and pm opening P-0104 show "You can’t open this project" and name nothing (no "Delta", no id). An injected 403 on P-0101 shows the same no-access state. pm's list never shows Delta Foods. A 401 from the mock scenario shows Sign in with `next=%2Fprojects` or `next=%2Fprojects%2FP-0101`. A 403 on the list shows "This section isn’t open to your role." A 500 on the list or the journey shows the error card with the reference "server_error". Nothing is retried in the 2.5 s I waited. Try again then recovers (20 rows, or 8 lines). admin, who sees no projects, gets "No projects you can see yet." with tab counts of 0. Persona none sends no projects request on `/projects` or `/projects/P-0101`.
- Unknown values: I injected bodies into the live responses. Unknown facts show "Not known": `unknown:true`, an empty value, a non-string `0`, and PAID with `money {amount:null, unknown:true}`. No ₦0 appears. A milestone with an unknown due date reads "UAT sign-off · due not known". Null or wrong-shaped list cells show "—". Bad counts drop the tab badges. A null `total` reads "20 shown". Nothing shows 0 for a value that is not known.
- Phone 390 (pm): no horizontal scroll on the list, P-0101, P-0105 (empty) or P-0104 (no access). On the journey the frame bar shows "Back to Projects" (x 16, y 6, 44 px tall), main has no back link, and Tola's panel is not shown. The back link returns to `/projects`. Not proven here: everything runs against the contract mock, not the real backend (T-PROJECTS / FE-CONNECT-1 do not exist yet). The 500s and the 403 on a journey were injected in the browser (`page.route`); 401, 403 on the list and 404 came from the mock. I did not re-run axe, focus rings or stale-response ordering, because e2e and unit tests cover them.

## Findings
- QA-3-1 | non-blocking | low | frontend | UX-3-1 is still open. To reproduce, open `/projects` as finance_lead at 1440 or 390 and search "lagoon". Expected "1 PROJECT" (singular when the total is 1). Actual "1 PROJECTS" (`qa-evidence/q3-count-lagoon.png`, browser-journeys Q3). The string is built at `frontend/src/features/projects/ProjectsList.tsx:472` (`${total} PROJECTS`). "0 PROJECTS" for no results is grammatical. This is the same issue as UX-3-1, not a new defect.

## Verified
- TECH-2-2 | verified | Q1: the default list request is exactly `/api/v1/projects?limit=20`, with no `status`. Q2: Closed sends `&status=closed` and All I can see sends `&status=all`.
- UX-2-1 | verified | Q3: the count follows the search ("1 PROJECTS" for lagoon). Q2: it follows the tab ("2 PROJECTS" for Closed, "24 PROJECTS" for All). Q1: the Active badge stays at 22.
- TECH-2-1 | verified | Q10: wrong-shaped and unknown values in the live list and journey responses render "—" or "Not known". Nothing throws, and nothing shows "[object Object]" or 0.
- UI-3-1 | verified | Q4: P-0101 at 1440 has exactly one `img[src*=tola]`, it loads (naturalWidth 192), and the panel carries the Tola summary and the `/assistant` link. Q11: at 390 no Tola image is visible.
- FID-1 | verified | Q11: at 390 the journey shows the frame bar's "Back to Projects" at y=6, main has no in-page back link, and the link lands on `/projects`.
- UI-2-1 | not re-tested | Visual only. The UI review verified it at this head.

## Notes
- Evidence is in `delivery/features/F-07/round-3/qa-evidence/`:
  - `api-calls.txt`: exact curl commands and answers. pm sees 4 Active and 1 Closed. `limit=7`, an empty `q` and `status=bogus` each give 404 `invalid_query`. P-0099 gives 404. P-0104 gives 404 for pm and 200 for finance_lead. The 401 and 403 scenarios work on both endpoints. none and admin get an empty list.
  - `browser-journeys.txt`: the per-journey results, Q1 to Q12.
  - `qa.spec.ts.txt`: the scratch spec I ran.
  - Six screenshots.
- On the phone no-access page (P-0104) there are two back links: the frame bar's "Back to Projects" and the no-access card's own "Back to projects". This is consistent with the desktop card. Noted for the design engineer, not a defect.
- TECH-3-1 (the leftover `contractBody` stripping) has no effect on the user and is not in my lens.
- I started and stopped no servers, did not copy `frontend/`, build or run `npm ci`, and did not read `.runtime/demo-access.txt`. I deleted the scratch config and its `node_modules` symlink.
