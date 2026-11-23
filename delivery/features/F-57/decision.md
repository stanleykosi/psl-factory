RECOMMENDATION: ESCALATE
COMMIT: 5262fbd45ea1743f1bbde3e0c5fc07eaa992e732
APPROVER: approver

## Summary
- F-57 connects the app frame to the live API 1.22.0. It adds generated live types with a drift test, a live-typed client, session and CSRF handling, and a top bar and menu that load from live GET /me.
- Gate PASS on this head (round 2, attempt 1). Technical, security, UX, UI and QA reviews and PMO acceptance all PASS on 5262fbd4. Both round 1 blocking findings are verified fixed.
- Product acceptance is recorded as "Accept" by the design engineer on this head, with the visible changes listed.
- The change is large: 83 files, frontend only, with no backend or contract file touched. It sits on the always-human surfaces auth, security and contract-change, and it adds a script line to frontend/package.json.
- Several live paths are unproved (a signed-in download, an administrator account, the /me 401 reload path). All are named in the PMO acceptance.

## Why
The work looks sound and I would not block it on quality. But it changes how every later screen handles session, CSRF and 403 (auth, security, contract-change), and it ships product-visible choices PSL has not seen: an unfiltered menu that shows Setup to everyone, no sign-in page live until wave 1, and role words with a name-only fallback. It is also well over the 15-file auto-merge cap, and merges into main in this project need the design engineer's word. A person has a real decision to make.

## Acceptance criteria
1. Frame loads from live GET /me and objects in destinations[] are looked up by key: met. QA ran live and mock, and the technical review agrees.
2. Generated live types plus a drift test: met. The gen:api:live script is added and the gate passed.
3. CSRF refresh with no auto-retry of writes, and csrf_failed kept apart from forbidden: met. QA proved one PUT, one GET /session, and the second press using the new token. The loop bug TECH-1-1 is fixed and unit-tested.
4. Dedicated error kinds for 429, 503 read_limited, 400, 413 and 415, and 422 fields kept: met per the gate's full test run (3706 tests) and the technical review. I did not rerun them.
5. A 401 gives a signed-out state with no link to retired Django pages: met. QA saw no anchor in the live signed-out state.
6. Role words come from role-dashboard positions[], with the name alone on failure: met for lead, multi and none personas. The administrator path is unproved because of backend issue QA-2-1.
7. Mock /me moves to the live shape and is validated against the contract: met per the gate. The mock startable_lines still use v7 keys (TECH-1-2, non-blocking).
8. Exact download destinations are asserted, and the live check ran through next start: met. QA confirmed six routes reach Django with exact paths.
9. Long role words clip with an ellipsis and nothing overflows (UI-1-1): met. UI and QA re-ran it at 1440, 1280 and 1100.

## For the human
Decision needed: merge F-57 (PR #97) into main. The design engineer has already accepted the visible changes. Please confirm the merge itself, and in particular that you accept these points for the live API until later waves:
- Setup shows for everyone, because backend question A-2 is open.
- There is no sign-in page against live until wave 1.
- Nine non-blocking follow-ups stay open. The main ones are QA-2-1 (backend 422 for the superuser) and restarting the mock on port 3001 (UX-1-1).

Files to look at:
- /Users/Hunchoo/psl-factory/frontend/src/api/client.ts
- /Users/Hunchoo/psl-factory/frontend/src/api/errors.ts
- /Users/Hunchoo/psl-factory/frontend/src/shell/
- /Users/Hunchoo/psl-factory/frontend/package.json
- /Users/Hunchoo/psl-factory-main/delivery/features/F-57/round-2/acceptance-pmo.md
