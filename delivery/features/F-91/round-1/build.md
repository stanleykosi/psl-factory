STATUS: BLOCKED
COMMIT: 4a2a81ca2186a1d6e7b3e4c1b326c4dde117b6ec
BUILDER: builder
LANE: full

## Summary
- Handed over to Codex before the final full test run; the code is complete for the spec but not fully verified. Honest status is not READY.
- Live work item now draws the station track with holders, the six facts (null = Unknown), the agent card (item.agent name and avatar, activity or progress, tracking.last_activity, no steps), reference beside the id, and a "Started by" line, all from the typed tracking call.
- History shows PERSON or AGENT tags and pages older events with the next_before cursor ("Older events").
- LC-Q24 built as the coordinator note says. No LC-Q23 items (counts, version, Restricted) drawn.

## Changes
- frontend/src/features/work-item/live/model.ts: stationsOf, factsOf, mergeHistory, historyLine with actorKind and entryId, new historyCaption(count, more); HISTORY_LIMIT removed.
- live/useLiveTracking.ts (new): reads tracking on each item read (readAt), keeps last good, access-lost errors go to the item's lose.
- live/useLiveHistory.ts: cursor paging, stale answers dropped, older-events error state.
- live/LiveWorkItemView.tsx: Header (reference, started line), TrackingBlock and AgentCard at top of Overview, History rows and Older events button with focus on first new row.
- src/api/types.ts: LiveTracking, LiveStation. work-item.css: .work-agent__body (additions only).
- mock/work-live.mjs: tracking route and fixtures 4101 to 4104 (4107 answers 503, 4105 no tracking_url), 4101 history in two pages of 30.
- Tests: tests/live-work-tracking.test.tsx (new), live-work-item.test.tsx and mock-work-live.test.ts updated, e2e/work-item-tracking.spec.ts (new), e2e/work-item-live.spec.ts updated.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Track, holders, current step: unit and e2e on 4102 pass.
2. [x] Unassigned, Not recorded, Unknown mapping: stationsOf unit tests.
3. [x] Facts Unknown, Not yet, Earned: unit and e2e.
4. [x] Only Verified shows a time: e2e on 4101.
5. [x] Reference beside id, null keeps "Work N": unit and e2e.
6. [x] Started line; 4105 draws no track or facts: unit and e2e.
7. [x] 503 callout, Try again reads tracking only: unit and e2e.
8. [x] Re-read on each poll while watched: unit with fake timers.
9. [x] 404, 403, 401 on tracking: unit.
10. [x] Agent card without steps: unit and e2e.
11. to 18. [x] History tags, raw unknown stations, kinds, Older events, dedupe, filter reset with a slow earlier answer, failed older events, captions, 404/401/csrf: unit and e2e.
19. [x] Only GETs: unit and e2e assert it.
20. [x] Live Django (8021, qa-seed, work 1): page showed Intake/qa-seed current, facts Unknown or Not yet, Started by qa-seed, matching GET /tracking for 1, 2 and 4; history empty ("No changes recorded yet."). The 390 run needed a wait for the tracking read, then showed the same.
21. [ ] Not fully reviewed: mock screenshots at 1440 and 390 for 4102 looked right; 4101, 4104 and history shots were taken but not inspected. The design-fidelity tool is not in this worktree and was not run.
22. [x] tsc clean; no api/schema import in live/.

## Validation
- vitest: live-work-tracking (27), live-work-item, mock-work-live all pass. tsc --noEmit and eslint on live/ clean.
- Playwright (E2E_PORT=4982 MOCK_PORT=4983): work-item-tracking and work-item-live, 26 passed.
- Full `npm test` via heavy-lock finished after the handover: 164 files, 3908 tests, all passed, on the pushed head. The lock is released.
- Servers: Django 8021 and Next 4982 stopped by recorded PID.

## Blocked
Handover only: the next owner should inspect the saved screenshots, and decide on the fidelity run. Possible flake: focus-on-first-new-row test once failed under load; now waits for focus.
