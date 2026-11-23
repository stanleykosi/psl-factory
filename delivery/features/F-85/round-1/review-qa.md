VERDICT: PASS
COMMIT: 35189b4503a76ae516ba153f77434a9a562bdc0d
REVIEWER: qa
AUTHORITY: integrated QA (lighter panel, D-180)

## Summary
- Exercised on this head against the mock (production build of the lane-c worktree on 4980, mock 4981) with a headless Chromium at 1440 and 390: /work/4101 to 4106 and an unknown id, /history with all four tabs, 4108 caption, 11 s polling counts, read-only checks. Every success and failure journey matched the spec; no write request or write button anywhere.
- 4102 re-reads work and weekly report about every 5 s (3 work reads in 11 s). 4101 reads once. 4106 and unknown 9999 show the same "This record is unavailable." 4103 has one "Open decision -> /work/4103/decide?task=9101" and a read-only second row. 4101 "Open the output" href equals output_url. 4104 and 4105 (null revisions) load with no 0. History tabs call kind=decision, worker, evidence, none for All; the caption says "latest 30" only on 4108; unknown station and status show raw text. No horizontal overflow at either width.
- Live Django (8020, Postgres 55433) was reached only signed out. No password for live-lead or live-none is in any permitted seed file, and I did not change accounts, so criteria 2, 19, the live half of 22 and the live 404/403 shapes for a signed-in account are NOT verifiable here. Signed-out evidence: GET /work/4102, /work/99999999, /history?kind=worker and /weekly-report all return 401 {"code":"unauthenticated","message":"Sign in to continue."}; POST /cases/{id}/files without a token returns 403 csrf_failed.
- Not proved: sign-in link in the browser (this base predates F-58), live file storage, a real work id on live, and the page error states 7 and 8 through the work page in the browser (see QA-1-1).

## Findings
- QA-1-1 | non-blocking | low | frontend | Criteria 7 and 8 could not be driven end to end in the browser. The mock scenario cookie applies to every route, so the app shell's /me or /session read fails first: scenario 401 shows the shell's "You're signed out. Sign-in opens in a later release." (no /sign-in?next link, expected on this base before F-58) and scenario csrf_failed shows the shell's "We couldn't load your account", never the work page's own wording. Those work-page states rest on the builder's unit tests, which I did not re-run. Re-check once F-58 and a per-route scenario are in.
- QA-1-2 | non-blocking | low | frontend | Weekly report period end is shown in the browser's zone: end_at 2026-11-22T23:59:59Z reads "To 23 Nov 00:59" (zone UTC+1). A week that ends Sunday reads as Monday. The period is a business range, so the design engineer may want it shown as the end day. Not a spec break.
- QA-1-3 | non-blocking | low | frontend | Mock scenario 500 leaves /work/4102 loading normally (route not covered by the scenario for the 500 case), so the plain-server-error wording of the page was not seen. 429 ("Try again shortly.", Try again) and 503 ("Try again shortly.", Try again) were seen.

## Verified
None (round 1; no fixes to verify).

## Evidence
- Mock API with curl: GET /work/4101..4108 return the fixture shapes (4106 404 `{"code":"not_found","message":"This record is unavailable."}`, same body as /history for 4106). POST /cases/{case}/files with token returns 200 `{upload_id:8001,name,size,sha256,download_url}`; scenarios 413, 415, 422 (fields[0].message "The file is empty."), 429, 404 return their bodies; without a token 403 csrf_failed.
- Page network: GET /api/v1/work/{id}, /weekly-report (4102 only), /history and shell reads only; no POST, PUT or DELETE seen on any page; `main` buttons list empty on every item page.
- Not run by me: lint, typecheck, vitest, playwright suites (builder and checks.log cover them), design fidelity tool (UI review owns it).
- Processes started and stopped by PID/port: mock 4981, Next 4980, Django 8020. Screenshots in /private/tmp/claude-501/qa/.
