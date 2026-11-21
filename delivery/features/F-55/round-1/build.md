STATUS: BLOCKED
COMMIT: af3e8affead32290818f6a9e7ec54bf52209a984
BUILDER: builder
LANE: full

## Summary
- The HR sample data is built and pushed on fe-hr-mock-data-sample-hr: 10 HR rows (3 Needs me, 4 Waiting on others, 3 Done) with work item pages and a History of 6 entries each (one Restricted), 4 alerts, 5 Zainab conversations, and the stand-in line `hr_staff_list`.
- STOPPED because free disk fell to 1.8 GB (limit 2.5 GB; F-54's build is running at the same time). The full vitest run, lint, typecheck and the browser e2e are NOT finished or run.
- The mock on port 4953 still serves the old data. It is a plain `node mock/server.mjs` from this worktree. A permission rule refused me when I tried to kill and restart it, and I did not work around that. It needs a restart before the design engineer can see the HR data.
- No salary or payroll amount appears anywhere; a vitest check scans the HR fixtures for money fields and currency signs.

## Changes
- `frontend/mock/fixtures/work/W-4601..W-4610.json` and `.history.json`: the HR work items (staff list, staff with no business unit, Finance question on a leaver, Finance matching, HR Lead decision, new joiner, agent checking, three done). `W-4611.json` is the item a started `hr_staff_list` lands on.
- `frontend/mock/fixtures/E-WORK-LIST.rows.json`: 10 rows for persona `hr` only (project C-HR-STAFF).
- `frontend/mock/fixtures/me.hr.json`: `startable_lines` is `["hr_staff_list"]`. `start-work/lines.hr.json`: the line with Month, Staff list file (evidence kind `staff_list`) and a note; its subtitle and summary say it is a stand-in.
- `frontend/mock/fixtures/alerts/notifications.hr.json` plus `alerts.mjs` (hr reads its own file; preferences stay the empty persona's).
- `frontend/mock/fixtures/assistant/CV-2421..CV-2425.json` and `index.json`: five Zainab conversations: ready for Finance, a draft card, a leaver question, a declined salary question (payroll visibility not set up, no one sees pay), joiners and leavers. `assistant.mjs`: a new message from hr gets an HR-flavoured sample reply.
- `frontend/mock/start-work.mjs`: `hr_staff_list` lands on W-4611.
- Tests: new `tests/hr-mock.test.ts` (13 tests); `mock-contract.test.ts` (hr notification id N-0301, removed the old hr 404 case); `mock-work-list.test.ts` (the "no payroll lines" check now excludes hr rows); `assistant-mock.test.ts` (fixture id list). New `e2e/hr.spec.ts` (written, NOT yet run).
- No shared components or CSS edited. F-54's worktree untouched.

## Fixes
None (round 1).

## Acceptance criteria
1. [~] Three queues: `hr-mock.test.ts` passes (counts 3/4/3, line filter, search, waiting_on filter). Browser e2e not run.
2. [~] Item pages and History: `hr-mock.test.ts` passes for all 10 rows (title and reference match the row, Zainab agent card, next step, history 5 or more with one Restricted, person and agent entries). Browser e2e not run.
3. [~] Alerts: mock test passes (4 alerts, 3 unread, all open HR items). Bell and Notifications page e2e not run.
4. [~] Assistant: mock test passes (5 conversations, full threads, draft card, salary declined, new message reply, other personas get 404). Browser e2e not run.
5. [~] Start work: mock test passes (upload, start, 201 to W-4611; 403 for other personas). Browser flow not run.
6. [~] hr destinations stay `my_work` and `assistant`, exceptions stays 403. NOTE: the mock API answers 200 to hr on `/setup/rules` (as before this branch; only pm and none are denied there). Projects and Setup are refused only by the app's destinations, so the e2e refusal test needs checking in a browser, and its message wording is a guess.
7. [ ] checks.sh and the full e2e: not done.

## Validation
- `npx vitest run tests/mock-contract.test.ts assistant-mock start-work-mock mock-work-list mock-row-item-match alerts-mock start-work-proof-mock`: before my two test edits, 2 failed (both expected: the assistant id list and the "no payroll lines" rule), now fixed in the commit but not re-run.
- `npx vitest run tests/hr-mock.test.ts`: 13 passed.
- Full vitest, lint, typecheck: started, interrupted by the disk stop; no result.
- Not run: `bash delivery/checks.sh` (it runs `npm ci` and a production build, both forbidden here), the e2e, any fidelity run (no board owned).

## Blocked
Paused: moved into the F-54 worktree, D-145. The coordinator told me to stop, push as is and run no more tests. Everything is pushed but not fully checked.

Ran after the first build.md:
- `npm run lint`: passed. `npm run typecheck`: passed.
- `e2e/hr.spec.ts` against 4953/4954: 5 passed, 3 failed. The failures are in my spec, not known data faults:
  - W-4601 and W-4605 item pages: my "next step" text locator found nothing (the page probably wraps or words it differently). To fix: match the page's real next-step element.
  - hr refused /projects, /exceptions, /setup: my guessed refusal wording did not match (/exceptions showed none of it). To fix: read the real refusal text in the browser and use it.
- Full vitest and the re-run of the three edited tests: not run. `checks.sh`: not run (gate will).
