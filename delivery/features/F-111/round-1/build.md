STATUS: READY
COMMIT: e35acf835f4162ea0fb1e350933c0a866f8667a3
BUILDER: builder
LANE: full

## Summary
- `/work/{id}` for a `pmo-issues/v1` item with panel `issue-followup` now draws the live issue, read only, through a new line adapter on F-85's `registerLineAdapter`.
- The adapter reads the follow-up, the work item (for `case_id` and the state), then the issue detail and messages together. A failed messages or detail read only affects its own section.
- Mock fixtures 5101 to 5107 and the three issue reads are in `frontend/mock/issues.mjs`. No write, no POST, no write control is drawn.
- Gaps against the spec because the shared frame cannot draw them, listed under Blocked: none blocks the build.

## Changes
- `frontend/src/features/issue-followup/model.ts` (new): mapper `sections()`, `allowedActions()`, error wording; types from `live-schema`.
- `frontend/src/features/issue-followup/issueFollowupAdapter.ts` (new): `read`, `sections`, `commands() = []`, registration.
- `frontend/src/features/work-item/live/LiveWorkItemView.tsx`: ONE import line registering the adapter (separate small commit, outside my folder, as the spec lanes allow).
- `frontend/mock/issues.mjs` (new) and one registration block plus reset in `frontend/mock/server.mjs`.
- `frontend/tests/issue-followup.test.tsx` (18 unit tests), `frontend/e2e/issue-followup.spec.ts` (7 e2e).
- No change to `src/features/workspace`, `src/shell`, `src/api`, `src/components`. No change to `mock/finance*` or the payments fixtures.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] 5101 header facts: e2e asserts ISS-0233, High, In Progress, Engineering, 3 days, Go-live link.
2. [x] Timeline rows equal the detail `timeline` in order, with kind words: unit test compares labels and text.
3. [x] 5102 banner from `timing.finding`, Asked/Reminder with "No receipt yet", due dates, target; flags false removes the banner with past dates: e2e and unit test.
4. [x] 5103: banner with `team.finding` and `next_action`, no owner fact, "Not recorded", no severity, no timing: e2e and unit test.
5. [x] 5104: finding as lead, planned UAT not a link, no "Closed": e2e and unit test. The work-state tag comes from the frame's header.
6. [x] Both blocked milestones null leave out Blocks: unit test.
7. [x] Banned strings absent on all four states: unit and e2e. No Tola note drawn.
8. [x] Only GET sent (e2e records non-GET requests: none); no write controls; no `liveApi.POST` in the folder.
9. [~] Flags are mapped by `allowedActions()` (unit tested for 5101 and 5103) but no control is drawn at all: the shared frame has no way to draw a disabled button. See Blocked.
10. [x] 5105: Chasing reads "Chasing is not available to you", rest shows: e2e.
11. [~] 5107: facts and Next show, "What has happened" shows "Try again shortly.". The per-section Try again button is NOT drawn (sections cannot carry a button); see Blocked.
12. [x] 5106 shows "This record is unavailable." (e2e); the mapper's wording tested.
13. [x] 401 replaces the page (rethrown to the frame) and 403 csrf maps to the refresh message: unit tests.
14. [x] Case id requested is the work item's `case_id`: unit test with the case changed.
15. [~] Polling is F-85's `PanelView`, which re-reads the panel (all reads together via `read`) when the item's `updated_at` changes. I did not add my own timers; no fake-timer test.
16. [x] Registered as `issue-followup`, `commands()` returns `[]`: unit test.
17. [ ] Not run against live Django (no work items exist on 55433 without Start work). The mock shapes follow the 1.25.0 types.
18. [ ] Fidelity tool and 1440/390 screenshots not run this round (see Validation).
19. [x] Mapper tests cover null `age_days`, `opened_at`, `severity`, unknown kind, null receipt, null timing.

## Validation
- `npx vitest run tests/issue-followup.test.tsx`: 18 passed.
- `npx tsc --noEmit`: clean. `npx eslint` on the new files: clean (final re-run was still in flight at hand-in; the earlier run on the same files, before the e2e locator edit, was clean).
- `heavy-lock.sh run lane-d -- npx playwright test e2e/issue-followup.spec.ts` (ports 4994/4995, production build): 7 passed.
- Full vitest suite and `checks.sh` not run (left to the coordinator's gate, D-189).

## Blocked
Not a block on READY; items for the coordinator or lane C:
- `LineAdapter.read(ref)` has no context, so the adapter makes one extra `GET /work/{id}` to get `case_id` and the state. Lane C could pass `LineContext` to `read` (additive), then the extra read goes.
- The shared Section renderer draws links only to a project or work item (`refPath`), so the blocked milestone links to `/projects/{case_id}`, not the milestones route. The "Open the issue register" link is not drawn for the same reason. "See full history" is the frame's History tab.
- No per-section Try again and no disabled write controls can be drawn until F-87's `Actions` slot exists; both belong to F-111B or a lane C frame change. Option 2A's "drawn disabled" part is therefore not done.
- Board parts hidden as D-182/Question 4 recommends: Tola's note, owner update, Record a reply, Set an owner and Raise an escalation forms.
- Fidelity run, 1440/390 screenshots and the live-Django comparison (AC17, AC18) remain for the QA stage or the coordinator.

## Round-1 note (gate attempt 1)
- cash-forecast guard: the work id is now read by `workIdOf()` with `parseInt(..., 10)`, returning null (and an error) when the route does not match; no `Number(` under src.
- next-config guard: `mock/issues.mjs` no longer carries the legacy page-url field (the frontend never reads it). Neither test was changed.
- Re-run: cash-forecast, next-config and issue-followup tests, 68 passed; tsc and eslint clean.
