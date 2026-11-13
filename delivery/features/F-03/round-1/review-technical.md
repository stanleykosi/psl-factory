VERDICT: PASS
COMMIT: 9bb054bba06ab04ae80f40dc97ed5e8a63248cf4
REVIEWER: reviewer-technical
AUTHORITY: reviewer-technical

## Summary
- The overview and history pages match the spec contract: the typed client is used, 403 and 404 show the same no-access board, the id is never rendered, and 401 uses the shell's SignedOutState.
- The polling hook is correct. It runs only while the agent is working and the tab is visible, resumes on visibilitychange, cleans up on unmount, and a failed poll keeps the last good item. The history hook drops stale answers and reloads on a revision change.
- The `server.mjs` change is additive and backwards compatible. Scenarios, personas and CSRF run before the work branch, the fallback fixtures are unchanged, and lookups use `Object.hasOwn` so `__proto__` cannot match. F-02 can add an E-WORK-LIST branch beside it without a conflict.
- The mock-contract tests are appended and no existing test is weakened. The lane is respected: no shell, api, styles, architecture or default-fixture edits.
- Two low, non-blocking points relate to F-04's use of the per-id folder (below). I did not re-run the gate; I relied on checks.md (PASS on this head).

## Findings
- TECH-1-1 | non-blocking | low | frontend | The fixture-directory test in `frontend/tests/mock-contract.test.ts` (the "every fixture in fixtures/work is schema-valid" test) treats every `*.json` that does not end in `.history.json` as an E-WORK-ITEM body and requires `sample: true`. If F-04 adds decision fixtures to `fixtures/work/` (for example `W-1001.decision.json`), this test fails. Fix when F-04 lands: have the test match only `^W-\d+(\.history)?\.json$` or ignore other suffixes. The integration owner should tell F-04 either to use this naming rule or to keep decision fixtures out of this folder.
- TECH-1-2 | non-blocking | low | frontend | `workResponse` in `frontend/mock/server.mjs` looks up `own(workId)` for the item. A request to `/api/v1/work/W-1004.history` therefore returns the history body as an E-WORK-ITEM response. This affects only the dev mock, and only for odd ids. Reject ids that contain "." in the item lookup, or key the item fixtures with a prefix. Because F-04 will add more suffixed files to the same folder, this is worth tightening when the file is merged.
- TECH-1-3 | non-blocking | low | frontend | `frontend/src/features/work-item/useWorkItem.ts` poll catch: any error during a poll, including 401, 403 or 404 (access revoked mid-session), is shown as "We couldn't refresh this item" with the stale item still on screen. The spec assumption (a failed poll keeps the last good data) allows this. A 401 or 403 on a poll could instead move to the signed-out or no-access state, so stale data does not stay visible after access is lost. Consider this for a later round or the architecture revision.

## Verified
None (round 1).
