VERDICT: PASS
COMMIT: dab5f01825066cb85627bf0f427f27ef29e7d3ef
REVIEWER: reviewer-technical
AUTHORITY: reviewer-technical

## Summary
- Lighter panel (D-180): read F-61's commits, spec and the four named areas; no suites run (CI did).
- The rfp-submission exception is narrow: only `features/alerts/model.ts` may hold "Delivered", and only for that pattern. "Delivered" appears once, in `DELIVERY_STATE_WORDS`, and `alerts-model.test.ts` asserts it is shown only for state `delivered`.
- The next-config allowlist adds the alerts model, mock and five alerts test helpers and tests. Production code reads `django_url` only in `model.ts` as the fallback link; the widening is acceptable.
- All alert calls go through `src/api/alerts.ts`. No `fetch` or `liveApi` is used elsewhere in `src/features/alerts`.
- A stale revision returns 422 `action_unavailable` (LA-4). The UI shows the server message and keeps the draft but offers no Reload. Non-blocking while LA-4 is open.

## Findings
- TECH-1-1 | non-blocking | medium | frontend | A 422 `action_unavailable` on a stale revision shows the server text only, with no Reload. The draft keeps the old revision, so every Save fails until the person reloads the page by hand. The kind is `invalid` (src/api/errors.ts:25), so AlertSettingsPage.tsx:87 skips the stale branch at line 86. Expected, once backend LA-4 confirms 422 as intended: treat `e.code === 'action_unavailable'` like `stale` and show the Reload notice. Add a unit test for it.
- TECH-1-2 | non-blocking | low | backend | LA-4: the contract's 409 `stale` for `POST /me/alert-preferences` differs from the live 422 `action_unavailable`. Backend or integration should confirm which one is meant and align the spec or the API.

## Verified
None.

## Pre-merge re-confirm (dab5f018)

Scope checked: `git diff --stat 5f61b03c dab5f018` (15 files, all F-113 or main-sync work: `frontend/mock/delivery-overview.mjs`, `frontend/mock/server.mjs`, `frontend/mock/work-live.mjs`, `frontend/src/features/projects/*`, `frontend/tests/delivery-*`, `frontend/tests/mock-work-live.test.ts`, `frontend/tests/projects-*`, `frontend/tests/ledger-source.test.tsx`). None of the 15 files is in F-61's scope.

- `frontend/src/features/alerts/*`: unchanged (no entries in the diff).
- `frontend/src/api/alerts.ts`: unchanged.
- F-61 tests (`alerts-*.test.*`, `frontend/e2e/alerts*.spec.ts`): unchanged.
- F-61 mock block (`frontend/mock/alerts.mjs`, its fixtures, and the alerts route in `frontend/mock/server.mjs`): unchanged. The `server.mjs` hunks add only the F-113 delivery import and route, placed before the F-72 block.

The `work-live` mock and its test changed, but those belong to F-113 (ids 2501 to 2505), not F-61.

Verdict: PASS, unchanged from 5f61b03c. The two non-blocking findings (TECH-1-1, TECH-1-2) still stand as written and are not affected by this change.
