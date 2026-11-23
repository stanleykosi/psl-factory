VERDICT: PASS
COMMIT: cdea4f987fb2e1d59cf051a8bdf96dd7197cf6e9
REVIEWER: qa
AUTHORITY: integrated QA (lighter panel, D-180)

## Summary
- Mock (dev Next 4980, mock 4981, headless Chromium at 1440 and 390) re-run on this head: /work/4101 to 4108 and 9999 behave as the spec says; 4106 and 9999 both show "This record is unavailable."; 4103 has the one "Open decision" link to /work/4103/decide?task=9101; 4101 "Open the output" links to /api/v1/work/4101/output; 4102 reads work plus weekly-report, others read once; no buttons in main and no horizontal overflow at either width.
- History (4101): the filters are radios; All, Decisions, Agent work and Evidence call history, kind=decision, kind=worker and kind=evidence. The caption "Showing the latest 30 changes. As of ..." shows only on 4108. 4106 history shows the same unavailable state. Rows with actor_kind and entry_id render; the odd station and status show raw text. Signed out: mock 401 on work and history. Upload via curl: 200 with upload_id 8001; no token gives 403 csrf_failed; scenarios 413, 415, 422 (fields), 429 and 404 return their bodies. vitest evidence, live-work-item and mock-work-live: 50 pass.
- Live (Django 8020 API-only, Postgres 16 on 55433, Next 4980 proxying to it): sign-in through GET and POST /session works for live-lead and live-none (200, csrf_token returned). /me differs as the server decides (live-lead has pmo-lead/lead; live-none has no positions). CSRF: upload with no token or a foreign Origin gives 403 csrf_failed; with the token for a non-existent case gives 404 "This record is unavailable."; signed out /work/4102 gives 401 unauthenticated.
- BLOCKED live: every /work/{id}, /work/{id}/history and /weekly-report call returns 500 ProgrammingError, "column workflows_factorywork.status_changed_at does not exist", for live-lead and live-none alike. `showmigrations` shows many unapplied: agents 0004 to 0023, core 0003 to 0008, documents 0020 to 0032 and 0064 to 0090, identity 0005 to 0021 and 0044 to 0086, policy 0017 to 0104 (including 0102_work_status_timestamp). I did not migrate or seed. So criteria 2, 19, the live 404/403 shapes and the live-lead versus live-none difference on a work record could not be shown. In the browser the 500 shows a "couldn't load" error state, not a blank page.
- Unproved: any real work item, the live upload (no visible case and file storage not run), the sign-in link (`/sign-in?next`) on this base, the live weekly report, and the page's 401, 403 csrf and 500 wording in a browser (the mock scenario still hits the shell first; see QA-1-1).

## Findings
- QA-2-1 | non-blocking | medium | integration | Live journeys cannot be run on the shared test database until it has the migrations from main. Expected: `GET /api/v1/work/{id}` and `/history` give 404, 403 or 200. Actual: 500 HTML ProgrammingError on `workflows_factorywork.status_changed_at` (policy 0102). Re-run this QA after the design engineer applies the migrations and seeds one weekly report item; nothing in F-85's code is at fault.
- QA-2-2 | non-blocking | low | frontend | Carried forward from QA-1-1: the page's own wording for 401, csrf_failed and 500 was not seen in a browser, because the mock scenario applies to the app shell first. Covered by unit tests, which I did not re-run apart from live-work-item (green).
- QA-2-3 | non-blocking | low | frontend | Carried forward from QA-1-2: weekly report period end shows in the browser's zone ("To 23 Nov 00:59" for an end of 22 Nov 23:59:59Z); a Sunday-ending week reads as Monday.
- QA-2-4 | non-blocking | low | frontend | Carried forward from QA-1-3: mock scenario 500 does not cover /work/4102, so the plain server-error wording was not seen on the mock.
- QA-2-5 | non-blocking | low | integration | The mock 401 body code is `not_signed_in`, while live Django returns `unauthenticated` ({"code":"unauthenticated","message":"Sign in to continue."}). The page does not branch on the code (it uses the status), so no break, but the mock differs from live.

## Verified
- MAIN-1-1 | verified | History rows carry actor_kind and entry_id and render on 4101 at both widths; the mock work item, panel and weekly report fixtures load and render on 4101 to 4108; mock-work-live, live-work-item and evidence tests pass (50). Not re-checked against live Django: the live endpoints fail on unapplied migrations (QA-2-1).

## Evidence
- Processes: `node scripts/dev.mjs -p 4980` with MOCK_PORT=4981 (stopped by PID); then Django 8020 and `next dev -p 4980` with API_ORIGIN=http://127.0.0.1:8020 (stopped by PID); ports 4980, 4981 and 8020 listen on nothing now. Cookie jars deleted; the test password was read by shell only and written nowhere.
- Scripts and screenshots in /private/tmp/claude-501/qa2/. Not run: lint, typecheck, full vitest, Playwright suites, design fidelity.
