VERDICT: PASS
COMMIT: 30143e1a4f9376200d9fc6f89797ff57e97a3b54
REVIEWER: qa
AUTHORITY: integrated QA, round 2

## Summary
- D-193 sync-only re-check of head 30143e1a (coordinator merge of origin/main 4fd055ce, F-71 and F-64): `npx vitest run tests/issue-followup.test.tsx tests/mock-issues-live.test.ts tests/next-config.test.ts tests/mock-live-decide.test.ts` in the lane-d frontend worktree gave 4 files, 48 tests, all passed. No servers started, no Railway tools used. Earlier journey evidence carries forward; QA-2-4 remains unproven live. GitHub checks on 30143e1a are reported separately by the coordinator.
- Mock stack (next dev 4990 pid 11835, mock 4991 pid 11834, API_ORIGIN 4991; both stopped by recorded pid) walked as pmo_lead with a browser script at 1440 and 390: fixtures 5101 to 5108 plus scenario cookies 401, 403, 404, 429, 503, csrf_failed. No horizontal overflow on any page and no non-GET request on any page.
- Success states match the spec: 5101 (ISS-0233, HIGH, IN PROGRESS, Engineering, Raised 20 Nov 09:30, 3 days, Blocks Go-live as text), 5102 (banner "No response since 09 Nov", Asked with receipt, Reminder "No receipt yet", Reminder due, Escalate by, "Escalation goes to PMO lead"), 5103 (no-owner sentence once, Raised and Age "Not recorded", no severity, no Owner fact, "No message has been sent to the owner."), 5104 (Verified, RESOLVED, "UAT (planned)", never says Closed).
- Failure states: 5105 messages 403 gives "Chasing is not available to you" with the rest intact; 5106 and 5108 404 give "No access. This record is unavailable."; 5107 detail 503 keeps the facts and shows the reload message; work-read 429 and 503 give "Try again shortly" with Try again; 401 gives the signed-out state; csrf_failed is not shown as no-access. Detail and messages reads forced to 403, 404, 429 and 503 by browser-side interception, at both widths.
- Live Django (8030 pid 19831, DB 55433, qa-seed): sign-in, /me, /projects, /work and the project issues read all return 200, but the one synthetic project has `issues: []`, so there is no issue follow-up work item and nothing to start with POST /work (it needs an existing issue_id). The live journey and AC17 comparison are NOT proved.
- Not proved: live follow-up, detail and messages shapes against the page; polling (belongs to F-85's PanelView); real provider behaviour.

## Findings
- QA-2-1 | non-blocking | medium | frontend | A 404 on only the issue detail or only the messages read (after the follow-up read returned 200) replaces the whole panel with the frame's "We couldn't load this part of the page. Try again" box, losing the facts, and does not say "This record is unavailable." (spec section states, AC12). Reproduced with browser interception of /projects/{case}/issues/233 and /messages returning 404 at 1440 and 390. The real 404 on /work/{id} (5106) is correct. Rare edge (the follow-up just answered), leaks nothing, and sits with the frame-level handling accepted under D-202.
- QA-2-2 | non-blocking | low | frontend | Detail 429 and 503 read "This is not available right now. Reload the page to try again." instead of "Try again shortly" with Try again; accepted under D-202 (reload wording), listed so it is on record.
- QA-2-3 | non-blocking | low | frontend | The first 5105 load at 390 showed only the frame (no sections) after a 4 s wait during dev compile; a repeat at 6 s rendered fully. Treated as dev compile latency, not a defect.
- QA-2-4 | non-blocking | low | integration | Live evidence missing: the local 55433 database has no project issue. A synthetic issue (raised through the issues write, or a seed command such as a `seed_*` issues demo) is needed, then POST /work with line `pmo-issues/v1`, case_id 4a228bcb-f762-4bc6-858e-74e9ab11ebd3, case_revision, idempotency_key and intake.issue_id. I did not run any seed command or create an issue, as F-111 is read-only. List it for the merge batch.

## Verified
- TECH-1-1 | verified | mock fixtures serve django_url; every page loaded against the mock with 200 reads and no contract error.
- UI-1-1 | verified | Blocks sits in the facts block on 5101, 5102, 5103, 5104 at both widths.
- UI-1-2 | verified | 5102 Chasing shows no "Time unknown".
- UX-1-2 | verified | same as UI-1-2.
- UX-1-4 | verified | 5103 shows "This issue has no owner. Choose an owner for this issue." once; no NEXT section.
- UX-1-5 | verified | timeline row "Owner acknowledged | 20 Nov 11:00"; the separate acknowledgement line carries "Owner replied by email".
- TECH-1-4 | verified | 5104 reads "UAT (planned)", not a link.
- TECH-1-5 | verified | no write control on any page; only GET requests recorded.
- UI-1-5 and UI-1-6 | verified | accepted under D-203; not retested visually.
- TECH-1-2, UX-1-1, UI-1-3, UI-1-4, TECH-1-3, UX-1-3 | accepted risk under D-202 (reload message, amber banner, frame next-step line, plain-text Blocks); observed as described, not re-raised.
