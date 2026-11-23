DECISION: READY
RISK: low
SURFACES: ui
PRODUCT-ACCEPTANCE: not-required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Guard so /my-work shows its existing error or not-available state instead of crashing on live rows (lane C F-86 QA-1-3).
- Crash site: KINDS[kind] is undefined for live rows in frontend/src/features/my-work/WorkRows.tsx:11, because the page still reads the v7 row shape.
- Frontend only, inside frontend/src/features/my-work. No new design, data or API.
- F-63 connects the page properly later and is out of scope.

## Scope
Outcome: with the live API, /my-work renders its existing error or not-available state and does not throw.
In: frontend/src/features/my-work only. Detect rows that do not match the v7 shape (for example an unknown kind) and fall back to the existing state. Add a test for a live-shaped row.
Out: mapping live rows to the page, new copy or states, new data or endpoints, and any change to the v7 mock path. Also out: other features and shared components. F-63 owns the real connection.
No task IDs or endpoints are covered.

## Risk
Low. The change is a contained guard in one feature folder. It uses existing states, touches no data, auth, money or contracts, and is easy to verify against the live API. The only surface is ui, and it adds no new flow or copy.
