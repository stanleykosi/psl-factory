VERDICT: PASS
COMMIT: 1407fbe72551058290b2303a86580eef05b945c2
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead), lighter panel D-180

## Summary
- `localMidnight` builds the offset from the offset of the very midnight it names, so half-hour zones, zero and a DST change (each end reads its own offset) come out right. The tests cover each.
- The mock's period rule matches `factory_reporting.py` and `pmo/clocks.py`: offset required (start checked first, then end), end after start, at most 8 days, end not in the future, same messages, 422 `action_unavailable` (as `http.py:122` maps a ValidationError).
- TECH-1-1, 1-2 and 1-3 are fixed. No assertion was weakened; the only edits to existing assertions follow removed behaviour (dead invoice line, date-only body).
- Two low notes: a skipped-midnight zone edge, and the mock's accepted format is a little stricter than Python's.

## Findings
- TECH-2-1 | non-blocking | low | frontend | `weeklyReport.tsx` `localMidnight` hardcodes `T00:00:00`. In a zone where local midnight does not exist on a DST day (a few, e.g. some South American zones), `new Date(y,m,d)` moves to 01:00 and the string would say 00:00 with the 01:00 offset, one hour off. Rare, and PSL's zone is not affected. Fix only if the design question LC-Q32 settles a fixed timezone, which would remove the browser dependence.

## Verified
- QA-1-1 | verified | the body now sends `YYYY-MM-DDT00:00:00±HH:MM`. Negative offsets use `Math.abs` before `trunc` and `%`, so -3:30 and +5:30 format correctly, and 0 gives `+00:00`. `end_at` is the local midnight of the day after the last day: 7 days for Mon to Sun, inside the 8-day limit. Python `fromisoformat` accepts the output. A date-only value fails `aware()` and the mock refuses it the same way. Timezone and end-boundary choice left to LC-Q32, as instructed.
- TECH-1-1 | verified | `/lines` mock items carry `request_schema: {}` and `content_type: 'application/json'`; project items already carry `django_url`, `source_options_url` and `workflow_intake_url` (`start-live.mjs:164`).
- TECH-1-2 | verified | the new test starts the weekly line through `StartWorkDrawer` with `prefill`. It asserts `onStarted('4102')` is called with a string, `nav.push` is not called, and the sent offsets match the pattern.
- TECH-1-3 | verified | `listedLines` and the `invoice` filter are removed, and the test no longer feeds an invoice line. The test is reworded, not relaxed: it still asserts no Invoice card appears.
- Weakened tests | none | the existing weekly body test now expects `localMidnight(...)` output instead of the date strings, which is the intended change. 6 tests were added (54 in the file). I read the diff and did not rerun the gate (checks.md: 157 files, 3758 tests passed on this head).
