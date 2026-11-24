VERDICT: PASS
COMMIT: 48221d25fe73354c183109e18cfaaa5c621ae4d1
REVIEWER: qa
AUTHORITY: integrated QA

## Summary
- UX-5-1 (AC 24) confirmed on phone: in this pass, on mock 4990/4991 at 390x844 (touch), I focused the first box at scroll 0 and pressed Tab through every control to Save. Empty form (case 2001): 7 stops, smallest gap above the bar 8px (the Lessons box), no violation. New version with a carried decision (case 2002): 10 stops (boxes, people, held-at, notes file, decision text, its file, Remove, Add a decision, Save new version), smallest gap 16px, no violation. Every stop was the element at its own centre. Screenshot at the last stop before Save shows Cancel and Add a decision clear above the bar (`shots/tab-end-2002-390.png`).
- Live checklist strip (the leftover item) is not provable on this database: 127.0.0.1:55433 `psl` now holds two projects, `0d790a54` and `b0f4e2f4`. None of live-lead, live-multi or live-none can record a retrospective (`/meetings/options` returns 403 `forbidden`, `can_record` false), and no delivery dossier exists (ids 1 to 10 return 404 on `/closure-checklist` on both projects). Live save, new version and strip-with-version were therefore not repeated this pass; the earlier pass's live save evidence (below) came from a differently seeded database.
- Live this pass (Django 8030 API-only, next 4990 proxying to it): the read-only view for a lead without recording authority ("Nothing saved yet", no Save button, no horizontal scroll at 1440 or 390); `?dossier=1` shows only "The closure checklist is unavailable." and the rest of the page still works; unknown project and another person's project (live-none) both show "This record is unavailable." (404 on all three reads); `?meeting=999999` falls back to the empty read-only view; signed out shows "You're signed out. Sign in" after 401 on `/me`. No write was sent in this pass.
- Mock this pass at 1440 and 390: strip with dossier 5001 shows five checks in board order plus "Retrospective saved · this screen"; empty form says "Not yet / No retrospective saved"; after the first save it says "Current" and then "The checklist used version N"; on case 2002 it reads "The checklist used version 1 (saved 10 Nov 2026)" and "A newer version has been saved. The checklist has not picked it up yet." Zero "draft" text, no horizontal scroll. Screenshots reviewed (`shots/mock-*`, `shots/tab-end-*`, `shots/live-*`): layout matches the described board shape, no overlap except the dev-only Demo persona button and Next dev badge, which float over content and are not product UI.
- Earlier pass (previous QA run, own Playwright scripts, mock 4992/4993, live 8031):
  - Mock journeys passed at 1440 and 390 (mock 4993, `next dev` 4992). Scripts were my own Playwright (playwright-core) scripts, not the repo e2e suite. They covered:
  - empty form and checklist strip, with no "draft" text;
  - first save with one POST and the toast "Saved HH:MM WAT, version 1." only after the re-read;
  - follow-up action on case 2002 (one `actions/create`, `meeting_id` 301, `due_at` null, "No owner / No deadline set", no link call, duplicate reference 422 under Reference);
  - unplaced 422 ("Pick people who are on the project.", no generic text, Save re-enabled, message above the bar at 390: bottom 689 against bar top 762);
  - field 422 on a duplicate reference;
  - 409 stale (typed values kept, next press succeeds);
  - 503 on case 2005 ("We couldn't confirm it saved.", one POST, then "It was not saved. Press Save again.");
  - double click sends one POST;
  - injected 403, 404 and 429 on save, and `csrf_failed` giving "Press Save again";
  - 403 and 404 and 503 on action create (503 shows "We couldn't confirm it was created.");
  - 401 sign-in link with `next=`;
  - unknown project and not-yours project show "This record is unavailable.";
  - case 2003 (cannot record) is read-only with no alert;
  - case 2004 (no proofs) explains why Save is off;
  - old version read-only with the "newer version" line;
  - checklist 503 (dossier 5009) hides only the strip;
  - "More" paging (case 2006).
  - AC 24 at 390: my own Tab walk, started at scroll 0 with Save enabled, ended above the bar every time.
  - Empty form: 7 stops to Save, with at least an 8px gap above the bar.
  - Case 2002 new version with a carried decision: 10 stops to Save, with at least a 16px gap.
  - Every stop was the element at its own centre point.
  - Negative case: a textarea forced under the bar had its bottom below the bar top and `elementFromPoint` returned another element, so the check does fail.
  - Live (Django 8031 on the 55433 database, qa-seed, project `4a228bcb`, no seed command run):
  - Sign-in through the Next proxy worked.
  - Meetings, options, first save (201), new version (201 with a read-only reference) and signed-out 401 behaved as specified at both widths.
  - The 404 for an unknown case and the phone page without horizontal scroll were also confirmed.
  - The save leaves local synthetic data behind: one retrospective on that project, with version 1 at 1440 and further versions at both widths.

## Findings
- QA-2-1 | non-blocking | medium | integration | The live checklist strip and its reference to the saved version (AC 6, AC 18, AC 21 "checklist references the saved version") has no live evidence. Cause is local data, not the page: no seeded dossier and no account with recording authority on the current `psl` database; writes may only go through the API and no seed was run. Mock evidence passes for all three. Expected: before F-118 relies on it, run it once against a database that has a delivery dossier and a recorder. A human accepts this gap or asks for a seeded rerun.
- QA-2-2 | non-blocking | low | frontend | A 403 on the follow-up action create shows "You can't record a retrospective on this project." The spec says "errors as Save", so this is arguably right, but the wording does not name the action. Confirm with the UX lens.
- QA-2-3 | non-blocking | low | frontend | `?meeting=<unknown id>` on the live API (404 on the detail read) shows the empty "Nothing saved yet" page with no message that the asked-for version was not found. Spec says 404 reads follow "unavailable"; low impact, observed live with live-lead at 1440. Confirm with the UX lens.
- Script mistakes of the first pass, not product defects: Save was assumed enabled on an empty form; one "Save disabled while unconfirmed" read was a timing effect of my script.

## Verified
- UX-5-1 | verified | Own Tab walk at 390 on mock this pass: 7 stops (empty form) and 10 stops (new version, carried decision), gap above the bar at least 8px and 16px, `elementFromPoint` at every centre is the control. Phone focus handling holds on head 48221d25.
- TECH-1-1 | verified | Full Tab walk first box to Save on two forms, in both passes.
- TECH-1-2 | verified | No stray scroll in the walk. The unmount cancel was not separately exercised (code and unit evidence only).
- TECH-1-3 | verified | The earlier pass's negative case (a control forced under the bar fails the check) detects it. The builder's red run at 53c24b19 was not re-run by me.

Processes (this pass): started Django 8030 (PID 39920), the mock-backed next dev on 4990 with mock 4991 (PIDs 39954 and 39947, parent npm in `mock.pid`), then a live-backed next dev on 4990 (PID 40943). All stopped by PID; ports 4990, 4991 and 8030 are free. No database write. The test-account password was read by curl only and never copied or printed.
