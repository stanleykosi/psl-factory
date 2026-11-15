VERDICT: PASS
COMMIT: c4d0b05e5e25272eb9a66bf37cc0c390ba487c01
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux

## Summary
- Walked /exceptions on the shared build (localhost:3611) at 1440 and 390 with the default signed-in persona (Finance Lead). The page now matches the SCR-10 boards: header and sub-line, search, Filter and "N OPEN" on one bar, bordered table, tag with "since" under it, bold title with reference.
- Search narrows the list (INV-04 gives 3 rows and "3 OPEN"). No match gives "No exceptions match your search and filter." with "Clear search and filter", which restores the list.
- Filter opens as a popover on desktop and a bottom sheet on phones (radios, Show results, Clear). Choosing Blocked gives 6 rows, a badge on Filter and a removable chip.
- Phone shows "Exceptions · N" with "← Queue", search plus a Filter icon button and separate outlined cards. scrollWidth is 390. Opening a row goes to /work/W-1504 at both widths. The deviations listed in D-04 (a to f) count as approved.

## Findings
None.

## Verified
- UX-1-1 | verified | "since" now sits under the tag in a fixed first column, so it aligns row to row (d1 screenshot, 1440).

## Notes
- Not exercised in this session: error, 401 and 403 states, and the paging bar controls below the table. The unit and e2e tests in build.md cover them.
