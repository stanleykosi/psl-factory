VERDICT: PASS
COMMIT: 808e022dd99ef05d39614d16acdfbe4fb0e44f55
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux

## Summary
- Walked /exceptions on the shared build (localhost:3611) at 1440 and 390 as finance_lead, as pm and with the empty cookie. Each matches SCR-10 and the spec.
- Default list: h1, sub-line, 4 headers, 20 rows in API order, tags in amber/red, linked titles, "20 shown", rows-per-page select. Phone shows cards with tag, since, link, doing and "Who acts"; no horizontal scroll (scrollWidth 390).
- Empty ("No exceptions. / Everything is moving or verified. / As of ...") and pm no-access ("This list is for Leads", "Go to My work", no rows or As of) work at both widths. No dead ends.
- Copy is short and plain. Keyboard Tab reaches the title links, which are real anchors with a visible focus.
- Omitted board items (search, Filter, N OPEN, reference) are recorded in the spec as approved omissions.

## Findings
- UX-1-1 | non-blocking | low | frontend | On desktop the "since <t>" text sits right after each tag, so its left edge shifts row to row (tag widths differ). The board uses a fixed tag column. Optional: give the tag a fixed-width slot. src/features/exceptions/exceptions.css

## Notes
- Not exercised in this session: the 401, 5xx and Show more failure states, and the 25-row Show more path. Unit and e2e tests in build.md cover them.
