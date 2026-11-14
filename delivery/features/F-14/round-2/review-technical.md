VERDICT: PASS
COMMIT: 5b9605a81d197187056995c793c626b1b3c2c55d
REVIEWER: reviewer-technical
AUTHORITY: reviewer-technical

## Summary
- Round 2 follows D-41: board overviews draw no tabs or next-step block, `NextStep` stays in the page inside a visually hidden wrapper with the F-06 slot, and items without `presentation` keep F-03's layout, tabs, facts and Unknown rules.
- Contract fields win. The presentation block is optional and read with a safe cast; an unknown fact reads "Unknown" whatever the block says, links are limited to app paths, and the contract fact and station words stay in the accessible text.
- F-09 seams are intact: `TaskPanels({ id, tasks })` is unchanged, "Open the decision" is still the single `you_can_act` link, and the `ReconcilePanel` slot comment sits in `.work-aside`. Hidden content holds no focusable control (quiet station lists drop `tabIndex`; closed disclosures use `hidden`).
- One change to an F-03 assertion (no-access wording split into two list items) is justified by the board. The other test edits only add the AppShell/E-ME harness or count item requests.
- Three non-blocking points below, mainly phone behaviour on live items and the phone history board.

## Findings
- TECH-2-1 | non-blocking | medium | frontend | On phones, items with no `presentation` (every live item) render the Overview/History tabs after the page content instead of under the header as F-03 did. `WorkItemView.tsx:161` (`{phone && !(tab === 'history' && view) && tabs}`) puts the tabs at the bottom, so History is reached by scrolling to the end of the overview, and Overview on the history tab sits below the list. Expected: tabs stay under the header for items without a board, and move only on board pages.
- TECH-2-2 | non-blocking | medium | frontend | On the phone history board (`counts` present) the "Rows per page" control is not rendered at all, and neither are "Showing N" and "As of" (`WorkItemHistory.tsx:195,234`: `!board && !side`). The spec says the rows-per-page control and Show more stay as F-03 requires. Only fixtures carry `history_counts`, so live pages are unaffected. Putting the select in `work-sr` would leave a focusable invisible control, so the board owner should decide where it goes (for example a visible small control) and record an exception.
- TECH-2-3 | non-blocking | low | frontend | On phones `presentation.phone.title` replaces the contract `title` in the h1, and the header sub-line shows "ref · revision N" instead of the contract started line (`WorkItemView.tsx:34,45-52`), so `started_by` and `started_at` are absent on phones even for screen readers. Rule 1 says contract fields come first. Only fixtures are affected. Keep the contract title and started line in a `work-sr` span, or record both as exceptions.
- TECH-2-4 | non-blocking | low | frontend | Note for F-06: `NextStep` sits inside a `work-sr` wrapper (`WorkItemOverview.tsx:707-709`). A "See all exceptions" link added there would be focusable but invisible. F-06 must either draw it visibly or keep it out of that wrapper. Not a defect today (no control inside).

## Verified
- FID-1-1 is a fidelity finding, outside my lens. Build.md shows 24 of 26 boards at visual 90 or more. The two awaiting-reconciliation boards wait on F-09's panel, which is a sound reason not to draw an unfunctioned control.

## Notes
- Checked from the diff: history filter, radio keys, paging (`showMore`), restricted rows, polling hooks and the `Open the decision` href are unchanged. The mock-contract schema is stricter than before (`additionalProperties: false` on the block, and `lines` rejected outside W-17xx), so no test was weakened. No test is skipped. I did not run the checks (the gate passed on this head).
