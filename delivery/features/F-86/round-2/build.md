STATUS: READY
COMMIT: 1407fbe72551058290b2303a86580eef05b945c2
BUILDER: builder
LANE: full

## Summary
- The weekly start now sends the period as ISO datetimes with an explicit offset, so the real Django accepts it (QA-1-1). A live start from the form returned 200.
- The mock refuses date-only and offset-less values with the server's own 422 (`action_unavailable`, "Period start requires an explicit timezone offset"), and keeps the server's window rules, so the old body would have failed the tests.
- Mock lines now carry `request_schema` and `content_type` (TECH-1-1); the dead `invoice` filter is gone (TECH-1-3); the assistant start-result path is covered again (TECH-1-2).

## Changes
Paths relative to `frontend/`.
- `src/features/start-work/lines/weeklyReport.tsx`: `localMidnight(day, plusDays)` and `buildBody` send `start_at` = local midnight of the first day and `end_at` = local midnight after the last day, each as `YYYY-MM-DDT00:00:00±HH:MM`.
- `mock/start-live.mjs`: `periodProblem` (offset required for start then end, positive window, at most 8 days, period already ended, same messages as `apps/workflows/factory_reporting.py`), answered 422 `{code:'action_unavailable', message}` with no field list; `request_schema: {}` and `content_type: 'application/json'` on every line.
- `src/features/start-work/LineChooser.tsx`: removed `listedLines` and the `invoice` filter.
- `tests/start-work-live.test.tsx`: 54 tests (was 48).

## The rule I found (flag for the design engineer)
- Contract 1.26.0 (POST /work, weekly branch) types `start_at` and `end_at` only as strings of at most 64 characters; it says nothing about offset, timezone or boundaries.
- Backend (`apps/workflows/factory_reporting.py`, `apps/pmo/clocks.py`): each value must be an ISO datetime with an explicit offset (else "Period start/end requires an explicit timezone offset"); end after start; at most 8 days; end not in the future ("must have ended"). Times are stored in UTC. Neither says which timezone the week belongs to, nor whether the end is inclusive.
- ENGINEERING READING, not a business rule: the week is the browser's local days. Start is local midnight of the first day; end is local midnight after the last day, so the last day picked is included (Mon to Sun is 7 days, inside the 8-day limit). The offset is the browser's offset on each of those midnights. If PSL's weeks are in a fixed timezone (for example Lagos) or end at 23:59:59, this needs the design engineer's decision. One side effect: picking today as the last day is refused by the server ("must have ended"), since that day has not ended.

## Fixes
- QA-1-1 | the period sent with a local-midnight offset; mock and tests match the server | 1407fbe72551058290b2303a86580eef05b945c2
- TECH-1-1 | mock lines have `request_schema` and `content_type` (project items already carried `django_url`, `source_options_url`, `workflow_intake_url` in the served answer) | 1407fbe72551058290b2303a86580eef05b945c2
- TECH-1-2 | test starts the weekly line through the assistant draft path (`prefill` and `onStarted`): the work id arrives as a string and the page does not navigate | 1407fbe72551058290b2303a86580eef05b945c2
- TECH-1-3 | dead `invoice` filter and its test line removed | 1407fbe72551058290b2303a86580eef05b945c2

## Not mine, noted
- QA-1-2: the server reused an open weekly item and ignored the new `reference`; my own live check showed the opposite case (a new item). Backend question for A-24.
- QA-1-3: `/my-work` crash on a live work row (`WorkRows.tsx`), lane A's area.
- QA-1-4: live chooser order follows the server (spec's "order returned"); design engineer's call.

## Acceptance criteria
1. [x] AC5 body: unit tests for `localMidnight` (UTC+1, +0, +5:30, -3:30, a daylight change, month and year roll) and `buildBody`; the start_at/end_at rule above replaces the date-only assumption.
2. [x] Live: against Django 8021 (PG 55433) as `qa-seed` through the real form on Next 4982: `POST /work` body `start_at 2026-11-16T00:00:00+01:00`, `end_at 2026-11-23T00:00:00+01:00`, answered 200 `{work_id: 2, state: ready, revision: 1, background: queued}` (a new work item, id 2, on project 4a228bcb-f762-4bc6-858e-74e9ab11ebd3; the database is otherwise untouched). `/work/2` opens and reads: "Reviewed weekly client report", "Report template needed". After the click the dev page was still on `/projects` when I looked 8 seconds later (first compile of `/work/[id]` in dev); I did not see the redirect itself live, only in the mock e2e and the unit test for `onStarted`/push.
3. [x] The mock now fails on a date-only body: test "the mock refuses date-only and offset-less values as the server does".
4. [x] All round-1 criteria still hold; the other 53 tests in the file pass.

## Validation
- `tsc --noEmit` and eslint on the changed paths: clean.
- `npm test` through `heavy-lock.sh run lane-c`: 157 files, 3758 tests, all passed.
- Servers: Django (pid 73825) and Next (73827) stopped by PID; ports 4982 and 8021 free. No credentials were printed or copied; the sign-in file was read by a local script only.
- Fidelity tool: not re-run (no layout change this round).
