VERDICT: PASS
COMMIT: 698c74e87d6b51a3b85829a455e34a1a883a3453
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead), round 2

## Summary
- D-193 sync-only re-check of 698c74e8 (origin/main 90748de3: #115 checks.sh, #112 F-61 alerts; conflict only in `frontend/tests/next-config.test.ts`): the resolved `allowed` list is main's 90748de3 list in order, with every entry kept, plus `issues.mjs` appended, so both sides hold. `frontend/mock/server.mjs` merged without conflict: F-61 `ALERT_PATH` (`/api/v1/notifications`, `/api/v1/notifications/{id}/read`, `/api/v1/me/alert-preferences`) is checked before the v7 routes and cannot collide with F-111 `ISSUES_PATH` (`/api/v1/work/51dd`, `/api/v1/work/51dd/issue-followup`, `/api/v1/projects/{id}/issues/{n}` and `/messages`); the two regexes share no path, and F-111's issue reset and log routes are intact. The v7 alert operations removed from `M1_OPERATIONS` and the `ALERT_OPERATIONS` dispatch are not used by F-111. No new finding; verdict unchanged.
- D-193 sync-only re-check of main merge 30143e1a (origin/main 4fd055ce, #114 F-71 and #111 F-64) against 8a5c09fe: `frontend/mock/server.mjs` keeps the F-111 issue route (GET `/api/v1/work/51xx`, `issues.mjs`, before the decide block) and the F-64 decide block (`ownsLiveDecide`, owns `/api/v1/work/17-19` and `/api/v1/tasks/*`). No overlap: F-111 claims only 51xx and is GET-only; decide's work-id check falls through for other ids; the F-71 milestone GET sits after both. Resets for issues and live decide are both present. `frontend/tests/next-config.test.ts`: every entry from 8a5c09fe is still in `allowed`; the merge adds `money-model.test.ts`, `milestones-model.test.ts`, `decide.test.tsx`, `live-decide.mjs`, and the projects regex widens to `projects/money/` and `projects/tabs/`. Non-blocking: `ownsLiveDecide` owns any `/api/v1/tasks/*` id; only `work-live.mjs` names those urls, as fixture strings, so nothing is shadowed today. No new blocking issue.
- TECH-1-1 is fixed: `django_url` is back in every work fixture in `frontend/mock/issues.mjs`, the next-config allowlist names `issues.mjs` with the reason, and `tests/mock-issues-live.test.ts` validates the work item and the four issue reads for every fixture against `contracts/psl-factory.openapi.json`.
- TECH-1-4 and TECH-1-5 are fixed (planned wording, `allowedActions()` removed; no callers remain).
- Both main-merge conflicts kept both sides: `mock/server.mjs` has the F-111 issue route and reset plus main's F-62 line, and `tests/next-config.test.ts` has main's allowlist and comment plus `issues.mjs`.
- Single test files re-run on this head: `tests/mock-issues-live.test.ts` 12 passed; `tests/next-config.test.ts` 7 passed. No servers started.
- TECH-1-2 and TECH-1-3 are accepted risk under D-202 and are not re-raised. No new blocking issue found.

## Findings
- TECH-2-1 | non-blocking | low | frontend | `frontend/tests/next-config.test.ts:108` matches the allowlist with `file.endsWith('issues.mjs')`, a suffix match that would also admit any future file whose name ends in `issues.mjs`. Same pattern as the existing entries; tighten to a path match when next touched.

## Verified
- TECH-1-1 | verified | `frontend/mock/issues.mjs:18` serves `django_url: /work/{id}/`; `tests/mock-issues-live.test.ts` (Ajv, strict, against the 1.26.0 contract) passes 12 of 12; allowlist entry carries the reason; the merge kept both sides in `next-config.test.ts` and `server.mjs`.
- TECH-1-4 | verified | `frontend/src/features/issue-followup/model.ts:96` reads "UAT (planned)" and "completion (planned)" with the stage word, per spec line 43; no "planned UAT" duplication.
- TECH-1-5 | verified | `allowedActions()` is gone from `model.ts`; grep finds no caller in `src`, `tests` or `e2e`.

## Notes
- Accepted under D-202 (design engineer, "Ship simpler for demo"), not re-raised: TECH-1-2 (Try again not drawn; reload wording instead), TECH-1-3 (Blocks as plain text, no link).
- Carried forward, non-blocking: TECH-1-6 (no fake-timer polling test; polling belongs to F-85's `PanelView`). The lane C follow-ups (adapter import to `workspace/lines/index.ts` once F-87 lands; the adapter re-reads the work item on each poll until `LineContext` arrives) remain for the coordinator.
- The mock test's status checks are conditional (`if 200 validate, else expect 503/403`); the else branches assert specific codes, so this is acceptable and not a weakening.
- Gate: the round-2 checks record the GitHub frontend-checks run passing on 8a5c09fe (run 45414315359). Full gate, e2e and the live Django compare were not re-run by this review.
