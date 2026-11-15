VERDICT: PASS
COMMIT: fe657c6cc1bbe552e569ab0305047dd63e9297ba
REVIEWER: reviewer-technical
AUTHORITY: reviewer-technical

## Summary
- All five stale references now point at v7 (mock OPENAPI_PATH, gen:api, drift test, client.ts comment, mock-work-list test via the shared OPENAPI_PATH). A grep of frontend/ finds no remaining packages/v3 or v4 path.
- schema.d.ts contains all 48 v7 paths and all 51 operationIds. I could not regenerate it byte for byte, because openapi-typescript is not installed in this worktree or the main checkout. The drift test and the builder's gate run cover that.
- The diff touches only 7 files. src/ changes are schema.d.ts and one comment line in client.ts. mock fixtures, work-list.mjs and e2e are untouched, so screen behaviour is unchanged. Typecheck, the unit suite and the 83 e2e specs passed unchanged, per build.md.
- The new guard test is meaningful. It resolves the gen:api source from package.json, DRIFT_SOURCE and OPENAPI_PATH, and compares them. The builder showed it failing with gen:api set to v4.
- Test edits are limited to the path, name and comment, with no assertion weakened.

## Findings
None.

## Notes
- The guard regex reads only the first `openapi-typescript <path>` argument in the gen:api script. That is enough for the current script.
- I did not re-run vitest or the generator, because node_modules is not installed in the worktree. I judged from the diff and from build.md and the gate evidence there.
