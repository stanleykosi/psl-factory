VERDICT: PASS
COMMIT: c4d0b05e5e25272eb9a66bf37cc0c390ba487c01
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead), round 2

## Summary
- Missing fields are handled safely: `ref` and `open_count` draw nothing when absent ("N OPEN", "Exceptions · N" and the reference line all depend on `!== undefined` or a truthy check). Nothing breaks against the v6 response schema.
- The request side depends on the v7 proposal (disputed, accepted by the coordinator). Search and Filter always render and always send `q`/`what`. The v6 `E-EXCEPTIONS` declares only `cursor` and `limit` and its response has `additionalProperties: false`. A real backend either ignores them, so the list stays unfiltered while the UI says it is filtered, or rejects them and turns the whole list into an error.
- `contractBody` strips exactly `open_count` and row `ref`, applies only to E-EXCEPTIONS, and the generic loop still checks every other operation unchanged. Shared edits are small and scope holds (`src/api`, `src/shell`, `server.mjs` unchanged this round).
- Round-1 findings are all non-blocking and carried over; none regressed.

## Findings
- TECH-2-1 | non-blocking | medium | frontend | DISPUTED, accepted by the coordinator pending architecture v7 (OVERNIGHT-DECISIONS D-05 adds q and what for the backend developer; board elements are built against proposals on the mock). Originally raised as blocking. `frontend/src/features/exceptions/useExceptions.ts` (`fetchPage`) and `ExceptionsList.tsx` (search form, Filter): `q` and `what` are sent to `/api/v1/exceptions` and the search box and Filter are always shown, though neither parameter exists in v4 to v6 (only `cursor`, `limit`). Expected: the page works against the real contract. Actual: with a backend that ignores unknown query params, typing a search or choosing a kind shows a chip and the same unfiltered rows, a silent wrong result; with one that validates them, the list fails. Fix: show Search and Filter only once a page has carried `open_count` (the proposal's capability signal), or filter client-side across loaded rows, and add a test for a response with no `open_count` that shows neither control and sends no `q`/`what`. The backend must otherwise add the parameters to the contract first.
- TECH-2-2 | non-blocking | low | frontend | `frontend/tests/mock-contract.test.ts` and `tests/exceptions-mock.test.ts`: the contract check strips fields from the response but never checks that the request query (`q`, `what`) is declared. Add a test that records which query names the page sends, so the gap in TECH-2-1 stays visible until the architecture adds them.
- TECH-2-3 | non-blocking | low | frontend | `useExceptions.ts` `showMore`: `openCount` is overwritten by each Show more page. If a backend sends it only on page 1 the "N OPEN" count disappears after Show more. Keep the earlier value when a later page omits it.
- TECH-2-4 | non-blocking | low | frontend | carried over, TECH-1-1 (malformed `since` or `as_of` throws in `sinceText`), TECH-1-2 (`limit` prop initial-only, now documented), TECH-1-3 (`M1_OPERATIONS` merge conflict, integration, now a one-line change again).

## Verified
- TECH-1-1 | reopen | still unaddressed by choice; non-blocking, unchanged.
- TECH-1-2 | verified | documented as initial-only on the prop; acceptable.
- TECH-1-3 | reopen | still for integration at merge; non-blocking.

## Notes
- I read the code and the builder's claim of 363 vitest tests passing; checks.md shows the gate passed. I did not re-run Playwright.
