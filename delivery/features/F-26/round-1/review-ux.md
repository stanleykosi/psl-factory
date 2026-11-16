VERDICT: PASS
COMMIT: 14c685cf577c6e9396a2a9c6ace316cc0998b697
REVIEWER: reviewer-ux
AUTHORITY: delivery UX review

## Summary
- Walked the Money tab on a production build against the mock (finance_lead at 1440 and 390; pm on P-0101): stages, Unknown, differ line, missing sources, report 500 and 403, money 403, empty, deep link and phone sheet all match the spec and D-104.
- Desktop aside and phone bottom sheet carry the same title, sources and Chidi card; no sideways scroll at either width; no totals; Unknown is amber text, never 0 or a dash.
- Two non-blocking gaps below; the visual scores under 90 are the UI reviewer's gate, not a UX finding.

## Findings
- UX-1-1 | non-blocking | MoneyTab.tsx, phone width, P-0103 (report 500) and P-0106 (report 403) | On phones the report failure or refusal is invisible: amounts are plain text, the hint is hidden and there is no message or "Try again", because the message lives only in the aside/sheet. Fix: show the same short line (and Try again for 5xx) under the cards at phone width, or ask the design engineer.
- UX-1-2 | non-blocking | ProjectNoAccess inside the Money tab (P-0107) | The panel says "Nothing about it is shown here, not even its name" while the project name, breadcrumb and tabs stay visible above it (spec Conflicts 14, Option B not chosen). Fix: the design engineer may choose the money-specific line "You can't see this project's money."

## Verified
None (round 1).
