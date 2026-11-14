VERDICT: PASS
COMMIT: b6b4e25c64c758886df0b98151e9c67d52ccd039
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux

## Summary
- I ran the frontend at this head in a scratch copy (app 3311, mock 3312) and walked /my-work at 1440 and 390 as finance_lead and pm.
- Desktop and phone layouts match SCR-01. Tabs with counts, table and cards, toolbar, chips, footer with rows per page and Show more, and the filter popover and bottom sheet all look as approved or as the spec records.
- Empty (pm), no results, wrong role (403) and load error (500) each show clear copy and a way forward. The tabs and toolbar stay in place, as the spec requires.
- Keyboard and focus work. Tab order is skip link, nav, roving tab stop on the tabs, search, Filter, then rows. Focus moves into the filter panel on open. The page has no horizontal overflow at 390.
- No blocking deviations. The spec records the omissions (contract gaps) as approved.

## Findings
None.

## Notes
- The 403 view shows the tab counts as "–" because no counts arrive on an error. That is consistent with "unknown is not zero". The "Updated" text is also absent there, which is fine.
- The phone placeholder "Search work" matches SCR-01-mobile. The desktop placeholder matches the spec.
- The /work/[id] links 404 in this branch, as expected.
- Not exercised: live polling, Show more focus behaviour and axe. I relied on the builder's tests for these, and they pass in checks.
