VERDICT: PASS
COMMIT: 5f61b03c833db545052bd88a34ed1a1ac62eb608
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
