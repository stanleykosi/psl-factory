VERDICT: CHANGES
COMMIT: e35acf835f4162ea0fb1e350933c0a866f8667a3
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead), round 1

## Summary
- Read-only issue follow-up adapter on F-85's `registerLineAdapter`; the mapper, the four states and fixtures 5101 to 5107 are sound. The adapter is registered by one import in `LiveWorkItemView.tsx`, which lane C's rule allows while `lines/index.ts` is not on main (it is not).
- Lane D question: the mock no longer carries the work item's `django_url`, which the live contract (1.26.0) marks required. The frontend never reads it, so nothing breaks at runtime, but the fixture no longer matches the contract and was changed to satisfy the next-config guard. Blocking (TECH-1-1).
- Two spec acceptance criteria are unmet (shown partial in build.md): the Try again control on the error states, and the drawn-disabled write controls. "Try again shortly." is printed with no button. Blocking (TECH-1-2); the fix depends on lane C's F-87 slot or a recorded spec change.
- Non-blocking: Blocks links to the project, not the milestone route; wording gaps; no fake-timer test for polling.
- Re-run on this head: `tests/issue-followup.test.tsx` and `tests/next-config.test.ts`, 25 passed. The full gate and the live Django and viewport checks (AC17, AC18) are not part of this review.

## Findings
- TECH-1-1 | blocking | medium | frontend | `frontend/mock/issues.mjs:18` drops `django_url` from the served work item. Expected: the contract's `WorkItem` lists `django_url` as required (`contracts/psl-factory.openapi.json`, `/api/v1/work/{work_id}` 200; also `frontend/src/api/live-schema.d.ts`), and the spec says fixture shapes are the contract. Actual: every other required field matches the 1.26.0 schemas for the work item, the follow-up, the detail and the messages, including nested `blocked_milestone`, `receipt`, `timing` and `acknowledgement`. Only `django_url` is missing, and build.md says the mock follows the live shapes. The removal was made to pass `frontend/tests/next-config.test.ts:104`, whose allowlist names only `work-live.mjs` as the mock that must carry the required field. Nothing catches the drift: `issues.mjs` is untyped JS, and no schema test covers the issue reads, unlike `tests/mock-live-projects.test.ts`. Runtime impact is nil: no `src` or test reads `django_url` on the work item. Expected fix: restore `django_url: \`/work/${id}/\`` in `issues.mjs`; add `issues.mjs` to the guard's allowlist with the reason the comment gives for `work-live.mjs`; add an Ajv check of the work item and the four issue-read bodies against the contract, as `mock-live-projects.test.ts` does. The allowlist edit is a test-file change for the coordinator to see; the guard's purpose (no legacy page link) is unchanged.
- TECH-1-2 | blocking | medium | frontend (lane C dependency: an F-87 `Actions` slot, or a section retry in `workspace`) | `frontend/src/features/issue-followup/model.ts:46` prints "Try again shortly." for 429, 503 and read-limited errors, but no Try again control is drawn. Spec "Section states" and AC11: each such state carries a Try again, and Try again re-reads only the failed read. Spec Q2 Option A: a write control is hidden when its flag is false and drawn disabled when true. Actual: no control is drawn; `allowedActions()` (`model.ts:51`) is used only by unit tests. build.md marks AC9 and AC11 partial. Copy that promises a retry with no retry is a user-facing defect. Expected: either the frame gains the slot and the adapter wires the control, or the coordinator and product record an accepted spec change before merge. Do not only hide the copy.
- TECH-1-3 | non-blocking | low | frontend (lane C for `refPath`) | `model.ts:101` links Blocks to `/projects/{case_id}`. Spec's Blocks row and AC1 name the milestone route as the link target. The deviation is recorded in build.md, so the coordinator can accept it for this round.
- TECH-1-4 | non-blocking | low | frontend | `model.ts:32`: the `state` kind has no "Logged" word (spec: "Logged" or "Status changed"). `model.ts:97`: the planned milestone reads "UAT (planned UAT)"; spec says "planned UAT". Align the wording.
- TECH-1-5 | non-blocking | low | frontend | `allowedActions()` (`model.ts:51`) is exported and used only by tests until F-111B. Drop it until F-111B, or keep it with its caller named.
- TECH-1-6 | non-blocking | low | frontend | Spec AC15 asks for a fake-timer test of polling. None exists in `tests/issue-followup.test.tsx`. The adapter has no timers (polling is F-85's `PanelView`); the coordinator decides whether the test lives with F-85 or here.


## Verified
- None. Round 1: build.md lists no fixes.

## Notes
- Lane D checks, answered:
  - Mock against the live shape the frontend reads: every field `src/features/issue-followup` and `src/features/workspace` read is served in the live form. The only gap is TECH-1-1. Type dependence: `live-schema.d.ts` types the work item with `django_url` required, but the mock is untyped (`@ts-expect-error` import in `tests/issue-followup.test.tsx`), so `tsc` cannot see the gap. No test or type reads the field.
  - Adapter registration: `LiveWorkItemView.tsx:15` has one side-effect import, the same form as the F-85 `weeklyReportAdapter` line. `frontend/src/features/workspace/lines/index.ts` does not exist on this head or on main, so the import is allowed. When F-87 lands, move it to `lines/index.ts` in its own commit. No adapter import was added to the workspace frame.
- The adapter reads `GET /api/v1/work/{id}` again on every poll (for `case_id` and `state`). Lane C's rule drops it once `LineAdapter.read` receives `LineContext` (after F-87). Carried forward.
- `alone()` rethrows 401 and 404 on the detail and messages reads, so a 404 there replaces the page. A reasonable reading of the spec. Carried forward.
- Mapping checks against the spec: overdue, no-owner, verified and Blocks come from flags and work state, not dates; Owner is `team.label` only; timeline rows keep the order sent; a null age or date never shows 0; 401 and 404 replace the page; 403 csrf maps to the refresh wording; 403 on messages maps to "Chasing is not available to you"; no write is sent (GET only, `commands()` returns `[]`, no `liveApi.POST` in the folder).
- Mock server: `issuesRoute` sits ahead of the work-live branch and matches only the 51xx work ids and the issue paths; other GETs fall through.
- AC17 (live Django compare) and AC18 (1440 and 390 screenshots) were not run; they belong to QA and the coordinator.
