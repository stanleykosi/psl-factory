VERDICT: PASS
COMMIT: ea088f9b0606c0e8e5fdfa1d047cd46619a96d13
REVIEWER: reviewer-technical
AUTHORITY: reviewer-technical

## Summary
- three and @types/three are pinned exactly at 0.187.0. The only static reference to three is scene.ts, which only Floor3D imports. Floor3D is reached solely through a dynamic import() after 3D is chosen, so three stays out of the first bundle.
- Polling skips a tick while a request is in flight, drops responses older than one already shown, and stops on 401/403/404. Try again is an explicit user action and bypasses the in-flight guard, which is acceptable because the sequence check drops the older response.
- The fallback (reduced motion, no WebGL, narrow width, failure) keeps the full flat rows and sr counts. In 3D mode the flat list stays in an sr-only block, so every count is still available.
- Floor3D disposes on unmount: observer, listener, geometries, materials and textures, the renderer, and forceContextLoss. It removes its own canvas, and removes the context-lost listener first so the teardown does not trigger onFailure.
- One lockfile hunk is outside three and its deps (TECH-1-1, non-blocking). I re-ran 4 of the 7 F-08 vitest files (41 tests passed). The builder's checks.md shows the full suite passing on this head.

## Findings
- TECH-1-1 | non-blocking | low | frontend | `frontend/package-lock.json` adds `"peer": true` to `node_modules/eslint-plugin-import` (hunk at about line 3913). This is npm-version metadata, not three or one of its dependencies. The brief expects a lockfile change limited to three and its deps. It is harmless and `npm ci` passes, but ideally revert that one line.

## Notes
- Late-response handling in useOverview.ts: an error response newer than the one shown replaces good data, and the error card keeps `lastAsOf`. That matches AC9.
- scene.ts `update()` runs once per poll with an unchanged `lines` reference. `diffCounts` returns no moves, so it renders once and starts no rAF loop, as the builder claims.
- The `decide.spec.ts` change in the diff comes from the base merge (PR #10), not F-08.
- server.mjs changes are exactly the seam described.
