VERDICT: PASS
COMMIT: 020724df7e55a58ab2e00d32d4bdde5b273f088a
REVIEWER: reviewer-ux
AUTHORITY: UX reviewer (lighter panel, D-180)

## Summary
- Read the spec, build.md and the SCR-22 / SCR-07 code at head. No browser tool was available to me, so I did not walk the running app by eye. I confirmed 4970 serves both routes (HTTP 200) and checked states, copy, links and keyboard behaviour in the code.
- The journeys match the spec. Every board change is a recorded option-1 removal, accepted under D-182, so none is a finding.
- Every state in the spec is present: loading, empty list, empty search with "Show all projects", error card with Retry, 401, 403, and 403/404 as the same "You can't open this project" page. Null values read "No manager", "Unknown" and "Not available", never 0.
- Accessibility looks sound: real links, a table caption, a labelled search role, `aria-live` on the shown count, `role="alert"` on a failed "Show more", focus moves to the first added row, and the repeated-title link name carries a hidden suffix. The phone cards are single links.
- One small non-blocking keyboard gap on the Delivery route (below).

## Findings
- UX-1-1 | non-blocking | low | frontend | On `/projects/{id}/delivery` the Delivery tab is not in the bar by design, so `selected="delivery"` matches no tab. `Tabs` sets `tabIndex 0` only on the selected tab (`src/components/Tabs.tsx:65`), so no tab in the bar is tab-reachable by keyboard on that page. The same happens on any route whose key is missing from live `tabs[]`. Expected: when the selected key is absent, the first tab keeps `tabIndex 0`. Seen at `src/features/projects/ProjectTabs.tsx:13` (passes `selected={current}`).

## Verified
None (round 1).

## Notes
- The phone Journey line and the desktop route line both render in the DOM, so CSS must hide one. This is for the fidelity run; I did not check it by eye.
- Work links go to `/work/{int}` and will 404 on the mock until the work-item feature (the builder noted this). Not a finding here.
