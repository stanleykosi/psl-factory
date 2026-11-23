VERDICT: CHANGES
COMMIT: 020724df7e55a58ab2e00d32d4bdde5b273f088a
REVIEWER: qa
AUTHORITY: integrated QA (lighter panel, D-180)

## Summary
- Mock run (Playwright against a production build, app on 4970, mock on 4971): `e2e/projects.spec.ts`, `project-tabs.spec.ts`, `delivery-release.spec.ts`, `delivery-hypercare.spec.ts` gave 98 passed, 2 failed. Both failures are the same builder-edited step in `projects.spec.ts:228` ("project tab: Documents", desktop and phone).
- Live run (Django 8010 on the local PG, `next dev` on 4970 with API_ORIGIN=8010, test account `lane-b-qa` created with manage.py, no roles or grants, so no project is visible to it): signed out shows the signed-out state. Signed in, `/projects` calls `GET /api/v1/projects?status=active` with no `limit` and gets 200, then shows "0 shown / No projects you can see yet. / You see projects your roles cover." Closed sends `status=closed`, All sends `status=all`, Active leaves the URL clean. A 200-character search is cut to 120 in the box and in `q`.
- Live wrong-user check: two real project ids exist in the DB (b0f4e2f4-..., 0d790a54-...). Both return 404 from `GET /api/v1/projects/{id}`. In the browser `/projects/<id>` (real UUID, the mock UUID and `P-0101`) shows "You can't open this project" with no title or id, and `/delivery` on it shows the same.
- NOT proved live: a populated list, a project body checked against the live contract, the facts strip and work rows, "Show more", the Delivery "not available yet" panel and the tab bar from live `tabs[]`. They need an account with project access. I did not grant one, to avoid changing the shared dev DB. Those paths are covered only by the mock e2e and the unit tests. The `/sign-in` page is not on this branch (base 924e7cdc is before F-58), so I signed in with `POST /api/v1/session` through the Next proxy, same cookie jar as the browser.

## Findings
- QA-1-1 | blocking | medium | frontend | A builder-edited e2e step fails. `e2e/projects.spec.ts:228` opens `/projects/P-0101/documents`, clicks the first tab, then expects the URL to end in the UUID `.../00000000-0000-4000-8000-000000000101`. The tab links keep the id the route was opened with, so the URL is `/projects/P-0101`. Both widths fail on the same step. The mock accepts both id forms, so this is a wrong expectation in the spec, not a product bug. Fix the expectation (accept either id form, or open the Documents tab by UUID), then rerun the spec. The builder reported these specs as edited but not run.
- QA-1-2 | non-blocking | low | integration | The live journey and populated list were never run on this head, so acceptance criteria 1, 7, 9 to 12 and 16 have no live evidence. Before merge, run once with a project-reading account (for example live-lead) with the live-lead credentials held by the user.

## Verified
None (round 1).
