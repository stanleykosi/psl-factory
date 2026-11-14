VERDICT: PASS
COMMIT: 808e022dd99ef05d39614d16acdfbe4fb0e44f55
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead), round 1

## Summary
- No blocking findings. The /exceptions list matches the spec's contract, states, paging rules and no-action rule, and it reads only E-EXCEPTIONS (no role or destination checks in the frontend).
- Scope holds: all 40 changed files are inside the frontend lane or the three named shared files. Nothing under `src/api`, `src/shell`, `architecture`, `openapi.json` or `delivery/` changed.
- Shared edits are small and generic. `server.mjs` is an import, one M1 entry and one dispatch line. `mock-contract.test.ts` adds only `PERSONA_STATUS` and its use in the loop, and other operations still expect 200. `WorkItemOverview.tsx` adds only the `EXCEPTION_STATES` set and the `NextStep` link.
- Mock data is consistent. For all 25 rows, the work item exists, its title matches, its state matches the kind mapping, `sample` is true and `tasks` is empty. The new references use the 06xx range.
- Re-ran `npx vitest run` on `tests/exceptions.test.tsx`, `tests/exceptions-mock.test.ts` and `tests/mock-contract.test.ts` in the worktree: 3 files, 96 tests, all passing. No test is skipped, `.only`ed or weakened. The e2e and axe results are the builder's claim (checks.md shows the lint, typecheck, vitest and build gate passed; I did not re-run Playwright).

## Findings
- TECH-1-1 | non-blocking | low | frontend | `frontend/src/features/exceptions/labels.ts` `sinceText` (and `formatWat`, which F-03 owns): `Intl.DateTimeFormat.formatToParts` throws `RangeError: Invalid time value` for a malformed timestamp, so one bad `since` or `as_of` would crash the whole list render. The contract promises RFC 3339 strings, so this is a hardening item. Fix by guarding in `sinceText` or with an error boundary, or leave it and note it in the backend contract tests.
- TECH-1-2 | non-blocking | low | frontend | `frontend/src/features/exceptions/ExceptionsList.tsx:128`: the `limit` prop is read only as the initial value (`useExceptions({ limit: initialLimit })`). A later prop change is ignored. Spec-compliant for the current callers, but F-08 may pass a different limit. Either document it as initial-only or sync it.
- TECH-1-3 | non-blocking | low | integration | `frontend/mock/server.mjs:24` (`M1_OPERATIONS`): the array line is the same line F-05, F-07 and F-08 are likely to append to, so a merge conflict is probable. The integration owner should resolve it at merge time. The change itself is correct.

## Verified
- None. Round 1 has no earlier findings to retest, and the build lists no fixes.

## Notes
- Taste only: list rows use the array index as the React key. That is safe here because rows are append-only, but a `work_id`-based key would be clearer for a later live feed.
- `NextStep` renders the link inside the `<span>` of the callout, which is fine for screen readers. Confirm the e2e focus-outline check covers this link (the builder checked the title link and Show more).
