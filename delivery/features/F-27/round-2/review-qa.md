VERDICT: PASS
COMMIT: 43a3d5fcad8e0072a85bcab2625a446b88d037e6
REVIEWER: qa
AUTHORITY: delivery integrated QA

## Summary
- Merged head 43a3d5fc (the dlv-00 merge that brings in F-26): I checked it and carried my verdict forward (see "Merged head" below). The journeys below were run on 34c38e4e, and the merge changes none of their code.
- I ran a production build of 34c38e4e (`next start -p 4808`, built by the e2e run with `API_ORIGIN=http://127.0.0.1:4807`) against the contract mock (`MOCK_PORT=4807 node mock/server.mjs`). A Playwright session named `f-27-qa` drove 39 journeys at 1440 and 390 across the scenarios default, empty, readonly, forbidden, many, authority and single, and the save outcomes invalid, stale, uncertain and uncertain_written. All 39 passed. I also called the endpoints directly with curl.
- e2e `E2E_PORT=4808 MOCK_PORT=4807 npx playwright test e2e/setup-delegation.spec.ts e2e/setup.spec.ts`: **26 passed (2.5m)**, exit 0. Focused vitest `npx vitest run tests/setup-delegation.test.tsx tests/setup-delegation-mock.test.ts tests/mock-contract.test.ts`: **3 files, 322 tests passed**.
- `bash delivery/checks.sh` did **not** pass in my runs, and the cause was machine load, not this head. Django check, lint and typecheck passed both times, and both runs stopped at vitest. Run 1: 16 files failed, 69 passed (85); 6 tests failed, 1325 passed, 540 skipped (1871). Run 2: 17 files failed, 68 passed (85); 21 failed, 1357 passed, 493 skipped (1871). Every failure was "Hook timed out in 10000ms", "Test timed out in 30000ms" or a loading spinner still showing when the wait ran out. Parallel vitest runs from other worktrees (for example f-25) pushed the load average to 111 in run 1 and 585 in run 2. The build step did not run because the script stops at the first failure. The recorded gate on this head is `round-2/checks.md` GATE: PASS (1871 passed). I re-ran once, as instructed, and did not try a third time.
- What remains unproved: no backend exists. Every result is against the contract mock, which is a proposal (D-DELEGATION-VIEW, G-SCR13A-1/-2/-4, `can_add`). Real per-record authority, tenant isolation, D05 delegation effects and the authority ceiling are the backend's and PSL's to build and prove. I faked 401, 403 and 404 on the PUT, a 5xx on the re-read, `can_add:false` and a missing `revision` with Playwright `page.route`, because the mock has no switch for them. Each such journey is marked "injected" below.

## Merged head 43a3d5fc (checked by reading the diff and the logs; not re-driven)
- `git merge-base --is-ancestor 34c38e4e 43a3d5fc`: yes, 34c38e4e is an ancestor. `git diff --stat 34c38e4e 43a3d5fc` limited to the F-27 and shared paths shows one change only: 3 added lines in `frontend/mock/server.mjs`. The paths were `features/setup`, `app/setup`, `mock/delegations.mjs` and its fixtures, `mock/proposals/setup.json`, `components`, `shell`, the package files, and the delegation tests and e2e.
- The 3 lines import money.mjs and route `isMoneyRequest` before the M1 check. `isMoneyRequest` matches only `E-REPORT` and the `money` tab of `E-PROJECT-TAB`, so E-DELEGATIONS and E-DELEGATION go through the same CSRF, persona and delegations.mjs path as before. In `tests/mock-contract.test.ts`, the 501 probe moves from E-REPORT to E-PAYROLL-MATCH; the delegation cases are untouched.
- The coordinator's logs:
  - `round-2/merge-checks.log`: Django check with no issues; Test Files 88 passed (88); Tests 1947 passed (1947); the build completed (22/22 static pages).
  - `round-2/merge-e2e.log`: 49 passed (4.3m) across setup-delegation (9), setup (17), setup-templates (11) and money (12).
  - The logs do not print the commit they ran on. I accept the coordinator's statement that they were run on 43a3d5fc.
- Judgement: this is enough. No F-27 code changed, the one shared change is fenced off from delegation, and a full gate plus the e2e passed at normal load. That also settles my earlier note that the gate needed a quiet re-run. The 39 journeys on 34c38e4e carry forward unchanged. I did not re-drive them on the merged head.

## Journeys (all on head 34c38e4e; evidence from `qa-run2.log` in my scratch folder)
- J1 pass | default @1440: one GET; the rows are exactly the mock's items ("Kemi Adebayo · PMO Lead → Femi Ade · PMO Lead, 18–25 Nov 2026, Annual leave, Upcoming"; Ada → Chika, Ended).
- J1b pass | injected read: no role or reason → nothing drawn; no `ends` → "02 Jan 2026 – Unknown"; a past-dated `scheduled` row still shows Upcoming; the year-crossing range shows "28 Dec 2026 – 03 Jan 2027". The list shows only what the read returns.
- J2 pass | desktop add (default):
  - To is disabled with "Choose who is delegating first." until From is chosen. From lists exactly [Kemi, Ada]. With Kemi, To lists only [Femi]; with Ada, only [Chika]. Changing From clears To.
  - A double click sent **1 PUT**, with `X-CSRFToken: mock-csrf-admin` and body `{"expected_revision":2,"delegate":"P-FEMI","starts":"2026-12-01","ends":"2026-12-03","from_person_id":"P-KEMI","reason":"Training"}`. The reason was typed with surrounding spaces and was sent trimmed.
  - Then 2 GETs in total. The live region read "Delegation added: Kemi Adebayo to Femi Ade, 01–03 Dec 2026.", the new row came from the re-read with focus on its `TR`, and the mock held 3 items at revision 3. No effect-claim wording was found.
- J3 pass | authority (one From option): From is read-only text "Kemi Adebayo · PMO Lead" with no combobox. To lists only [Femi]. Authority is a required Select with 2 options. Submitting without an Authority showed "Choose an authority." and sent 0 PUTs. The PUT then carried `from_person_id:"P-KEMI"` and `authority:"approve_invoices"`, and the row shows "Authority: Approve invoices".
- J4 pass | single: From reads "You". To lists both unpaired options. The single authority is shown as a line and sent. The body has no `from_person_id` and no `reason` (`expected_revision:1`), and the mock recorded `from {"name":"Ada Okafor","is_you":true}`.
- J5 pass | empty: the empty state shows with the panel beside it; the PUT sent `expected_revision:0`, and 1 row appeared after the re-read.
- J6 pass | readonly @1440 and @390: 0 add buttons, 0 panels, no note, axe clean. J6b (injected `can_add:false`, options still present): 0 add buttons, 0 comboboxes. J6c (injected `can_add:true` with no `revision`): 0 add buttons. No add control appears without `can_add`.
- J7 pass | forbidden @1440/@390: "This section isn’t open to your role.", no delegation names in `main`, axe clean. pm and none @1440/@390: 0 delegation calls. none sees the shell's "No sections are open to your role yet." J7b (`psl_mock_scenario=401`) and J7c (injected 401 on the list only): signed-out with link `/accounts/login/?next=%2Fsetup%2Fdelegation`. J7d (injected 404 on the read) shows the same not-open view as a 403.
- J8 pass | many @1440 and @390: 20 → 40 → 45 rows with cursors `[null,"o:20","o:40"]`, then "All 45 delegations" and no Show more; Unknown shows. J8b: a failed second page keeps the 20 rows and shows the problem text.
- J9 pass | 422 (`invalid`) in the panel @1440 and in the sheet @390: the top message reads "Check these fields: To, Ends." with no raw keys. Under To: "This person can’t take this delegation."; under Ends: "Choose an end date within the next 90 days.". Focus moves to To, entries are kept, 1 PUT and no re-read, axe clean.
- J9b pass | format checks only: an empty submit marks From and Starts; Ends before Starts → "Ends can't be before Starts." with 0 PUTs. A past-dated 01–02 Jan 2026 is sent as is.
- J10 pass | 409 (`stale`): the stale sentence shows and entries are kept. After a 5 s wait there was still only 1 PUT, so nothing is resent on its own. The next press sent `expected_revision` 3 (rebased from 2). 3 GETs, axe clean.
- J10b pass | 409 with the re-read failing (injected): "…we couldn’t reload the list. Reload the page before adding again." It does not claim the list was reloaded.
- J11 pass | `uncertain` @1440 and @390: "It was not added. You can add it again." Add stays enabled, nothing says "added", and the mock still has 2 items at revision 2. Entries are kept and the sheet stays open on the phone. Adding again sent a 2nd PUT with revision 2.
- J12 pass | `uncertain_written` @1440 and @390: the "list changed" warning shows and Add is disabled. A forced click and Enter in Reason sent no 2nd PUT (1 in total), and nothing says "added". The mock holds 3 items. On the phone the sheet closed and the warning shows above 3 cards; reopening the sheet shows Add held and "Start again". Only Start again re-enables Add, with an empty form. Axe clean.
- J13 pass | uncertain with the re-read failing (injected 503): the form locks with "We couldn’t check whether the delegation was added…" and Add disabled. "Try again" while reads still fail keeps it locked and sends no PUT. Once reads work, "Try again" settles to "list changed" plus Start again (1 PUT in total). Axe clean.
- J14 pass | injected 401 on the PUT → signed-out with `next=%2Fsetup%2Fdelegation`. Injected 403 and 404 on the PUT → the backend message is shown, the list is re-read (2 GETs), and nothing says "added".
- J15 pass | persona switch: admin and finance_lead give identical rows, comboboxes, buttons and From options with the same fixture. ceo (`/me` without `setup`) makes 0 delegation calls. Switching persona changes nothing that is not in the response.
- J16 pass | DevTools tampering, 0 PUTs from every attempt:
  - (a) removed `disabled` from the waiting To and opened it → 0 options;
  - (b) injected a cloned `<li role=option>` "Chika Obi" into the To listbox and clicked it;
  - (c) called the To and From Selects' React `onChange` props (through the fiber) with `P-CHIKA` (not paired with Kemi) and `P-NOBODY`;
  - (d) a valid From with only To planted as `P-CHIKA`.
- J17 pass | phone sheet @390: Escape closes it and returns focus to "Add delegation". A double tap in the sheet sent **1 PUT** (CSRF and the body as in J2, `from_person_id:"P-KEMI"`). The sheet closed, 3 cards show, there is no sideways scroll and no effect-claim wording.
- J18 pass | phone sheet, authority: To lists only [Femi]; the PUT carried `from_person_id:"P-KEMI"` and `authority:"approve_milestones"`.
- No claimed effect: after J2 and J17 succeeded, I scanned the page text for `can now|now able|has been given|granted|in force|takes effect|is now active|can approve`, leaving out the board's note. No match.

## Direct API (curl on 127.0.0.1:4807, admin persona unless stated; mock reset before and after)
- PUT with no CSRF → 403 `csrf_failed`. Another persona's token → 403 `csrf_failed`. pm with its own token → 403 `forbidden`. `forbidden` scenario → 403.
- Kemi → Chika → 422 `delegate`. No `from_person_id` (the caller) → Femi → 422 `delegate`, because the caller has no paired delegate in default. Unlisted From → 422 `from_person_id`. Authority when none is offered → 422 `authority`. `idempotency_key` → 422 "Not part of a delegation.". Ends before Starts → 422 `ends`. Date 2026-13-45 → 422 `starts`.
- A valid body → 200 `{"revision":3,"delegation_id":"DL-9001"}`. My log labels this call "stale expected_revision 1", but it sent the valid body with revision 2; the label is mine and wrong. `expected_revision:1` → 409. Replaying the accepted body → 409, so the mock writes no duplicate. GET as pm → 403. GET as admin afterwards → revision 3, 3 items.
- The `readonly` scenario PUT is refused with 422 `delegate` (no options) before the `can_add` 403 step. This is TECH-1-1 as carried forward: the 403 step is unreachable, and it only affects the mock.

## Findings
None.

## Verified
- SEC-1-1 | verified | J3: a single From option sends `from_person_id:"P-KEMI"`. J2/J17: a chosen From is sent. J4: "You" sends none, and the mock records `is_you`.
- SEC-1-2 | verified | J3/J18: with pairing keys and one From, To lists only the paired option [Femi], not unpaired Chika. Curl: a caller with no From is refused for the paired Femi (422 `delegate`).
- TECH-1-3 | verified | J10b: a 409 whose re-read fails shows the "couldn’t reload the list" sentence, not the stale one.
- UX-1-1 | verified | J9 @1440 and @390: "Check these fields: To, Ends.", with no raw keys.
- UX-1-2 | verified | J12 @390: the sheet closes, the warning shows above 3 cards, and reopening shows Add held and "Start again", which clears the form.
- UI-1-2 | verified | J12/J17 @390: Add delegation, Cancel and Start again work from the sheet footer. The layout itself is UI's lens.

## Notes
- checks.sh: closed by the merged-head gate (1947 passed at normal load, above). Before that, my two runs on 34c38e4e failed only on timeouts under load averages of 111 and 585. The F-27 suites pass in isolation (322). The coordinator may want to re-run the gate when the machine is quiet; nothing in this head's diff explains the failures. They also hit unrelated suites (work-item-board, decide-board, assistant, alerts-mock and others).
- Carried from TECH review: the spec's Contract line "from_person_id sent only when From came from from_options[] with two or more choices" is now also met for a single option (SEC-1-1). The backend handoff should record the new rule.
- Housekeeping: I stopped mock PID 22440 (4807) and app PID 22497 (4808) after checking that both ran from the f-27 worktree's `frontend`. `frontend/test-results` is deleted and the worktree is clean at 34c38e4e. Scripts and logs are in `/private/tmp/claude-501/-Users-Hunchoo-psl-factory/984b2492-735a-4d33-833d-007cd38fd896/scratchpad/f27-qa/` (`qa.mjs`, `qa-run2.log`, `e2e.log`, `checks.log`, `checks2.log`).
