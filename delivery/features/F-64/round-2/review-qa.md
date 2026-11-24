VERDICT: PASS
COMMIT: 7108be9d709378a1d14333db432515028e087aa0
REVIEWER: reviewer-qa
AUTHORITY: reviewer-qa (integrated QA, lighter panel D-180)

## Summary
- Proved on the live stack (Django 8018 on local Postgres 55433, `next dev` 4980 in live mode, qa-seed): signed-out page, unknown work (404, no-access board), non-numeric id and a task not on the work (not-open board), and wrong-user/unknown-task API answers (404 on read, claim, decision and comment; 401 anonymous).
- NOT proved live: opening a real decision, the evidence picker, approve, return with a note, a live not-yours read and a live stale 409. The local database has no human tasks and no templates. A weekly report cannot reach a review task through the API alone: POST /work (qa-seed, work 12) returns state `ready` "Report template needed", and a template upload needs a recorded proof id, revision and request key plus an agent draft. The only other route is the invoice seed scripts, which need staff invitations and policy setup and would write shared local data; not attempted.
- Mock coverage, which the live data could not give: `e2e/decide.spec.ts` (production build on the mock, ports 4982/4983 through the heavy lock) 8 of 8 passed: approve with the evidence picker gating the buttons, return and reject needing a note, the stale board with the note kept and only "Review version 3", not-yours read-only with a comment box and no buttons, unknown amount reads "Unknown", not-open variants, no-access, signed-out and unconfirmed decision. The own board is not reachable by design (question 2) and was not exercised.
- Vitest `tests/decide.test.tsx`, `tests/mock-live-decide.test.ts` and `tests/api-live-schema-drift.test.ts`: all pass. The drift test timed out once at 32 s while the machine was loaded, and passed alone. `grep revoke` in the decide feature and InlineDecide, and `grep "api\.(GET|POST)"` in src/features/decide, return nothing.
- Round-2 changes are presentation only (stale table, phone stale card, phone strip, done aside); the e2e run covers them with the axe checks inside the specs.

## Findings
None.

## Verified
- UI-1-1 | verified | e2e stale spec (mock, production build) passes; the stale view is a table and the board still offers only "Review version 3".
- UI-1-2 | verified | decide-board phone stale card was covered by the builder's decide-board run and `tests/decide.test.tsx`; the e2e decide spec ran on desktop only here, so the phone layout was not re-driven by me.
- UI-1-4 | verified | done board in the e2e approve, return and reject specs renders after the decision with the verdict named.
- UI-1-5 | verified | covered by `tests/decide.test.tsx` (passed); title not drawn twice.
- UI-1-3 | verified | phone not-yours strip is CSS and test covered only (`tests/decide.test.tsx` passed); no live phone check.

Live commands, for the next agent (password never copied):
- Django `manage.py runserver 127.0.0.1:8018` with PGPORT=55433, PSL_DJANGO_UI=0, PSL_FRONTEND_ORIGINS=http://127.0.0.1:4980; `next dev -p 4980` with API_ORIGIN=http://127.0.0.1:8018, NEXT_PUBLIC_API_MODE=live. Sign-in through the Next proxy `POST /api/v1/session` returned 200 for qa-seed.
- `POST /api/v1/work` weekly report on case 4a228bcb... returned 200 `{work_id:12, state:"ready"}`; `GET /api/v1/work?queue=decisions` returned zero items; `GET /api/v1/tasks/{1,999}` 404; claim, decision and comment on 999 404; `GET /work/12/history?kind=decision` 200 empty; anonymous `GET /tasks/1` 401.
- Pages signed in: `/work/12/decide?task=1` shows "This decision isn't open here" with `GET /work/12` 200 only (no task call); `/work/abc/decide?task=1` shows the same with no work request; `/work/99999/decide?task=1` shows "You can't open this work item" after `GET /work/99999` 404; signed out shows "You're signed out".
- Cleanup: my Django (PID 63991) and next dev (PID 63992) stopped. A `next-server` on 4980 (PID 75160, started 15:16) is not mine and was left running. Work 12 ("F64 QA weekly") remains in the local test database.

## Pre-merge re-confirm (7108be9d)
- `git diff 9b921ea7 7108be9d`: 15 files, all the F-113 Delivery tab (projects feature, delivery tests, mock work-live and server, one ledger-source test wait). Nothing in src/features/decide, InlineDecide or the decide tests changed.
- Run singly from the worktree frontend: `tests/decide.test.tsx` 63 of 63 passed; `tests/mock-live-decide.test.ts` 11 of 11 passed.
- Not re-run: live stack, e2e, full suite (by instruction). Round-2 live and mock evidence stands.
VERDICT: PASS
