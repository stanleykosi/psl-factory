VERDICT: PASS
COMMIT: 4f3831d4aef9088f75beb7aaaeda518fa14ee3f4
REVIEWER: reviewer-technical
AUTHORITY: reviewer-technical

## Summary
- All three round-1 findings are fixed in the diff and covered by tests. The gate passed on this head (checks.md).
- Mock: item lookup only for ids matching `^W-\d+$`, and the fixture test filters on `^W-\d+(\.history)?\.json$`. F-04 sidecars no longer break either.
- Polling: 401, 403 and 404 on a poll now replace the item with the error state and stop scheduling. Other failures still keep the last good item.
- The phone station list is CSS and e2e only, with no contract change. Existing tests are not weakened.

## Findings
None.

## Verified
- TECH-1-1 | verified | mock-contract.test.ts directory test now filters on `^W-\d+(\.history)?\.json$`.
- TECH-1-2 | verified | server.mjs `own()` returns undefined unless workId matches `^W-\d+$`, so `W-1004.history` returns the default item. A new test covers it.
- TECH-1-3 | verified | useWorkItem.ts poll catch sets the error state and returns without rescheduling for unauthenticated, forbidden and not_found. A unit test covers 403, 404 and 401.
