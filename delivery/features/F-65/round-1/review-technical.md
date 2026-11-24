VERDICT: PASS
COMMIT: 15ad8e8b0d20155707c459097c067c6dfff28dc6
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead), lighter panel (D-180)

## Summary
- Unknown figures are never 0. No counts gives "Totals are not available yet." and no squares. A line missing from limited counts gives null stations and "Not available yet". Five known zeros appear only when the counts are not limited. Tested in tests/overview-lines.test.ts and tests/overview.test.tsx.
- All four totals and the phone summary go through `figure()`, so limited reads "at least N". The coverage line follows `limited` and `evaluated`. This is tested for both desktop and phone.
- The local floor map is tested against the 26-key `line` enum in contracts/psl-factory.openapi.json. Each key lands on exactly one floor, unmapped keys go to "Other lines", and `FLOOR_MAP_VERSION` is 1.
- A 403 or 404 on /overview is a shown state with the server's message, no retry and polling stopped. The code has no client role rule. A counts-only failure gives the partial state. A 401 on either read gives the signed-out state.
- I ran three test files (overview-lines, overview, floor3d-strip): 49 passed. I did not run the full suite, as instructed. One non-blocking gap is listed below.

## Findings
- TECH-1-1 | non-blocking | low | frontend | Station squares and the station strip show sampled counts as plain numbers when `limited` is true. For example, the strip reads "3 items" and a 0 square is blank, with no "at least" wording. The footnote at OverviewPage.tsx:~337 says station figures come from recent items, which covers it. Spec acceptance 3 and 5 only require "at least N" on the totals. Optional: add "at least" to the strip text when limited (src/features/floor/StationStrip.tsx:28).

## Verified
None.
