VERDICT: PASS
COMMIT: b839dfaac7756f1b15facc8fb3e7adb2c14fab15
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

## Conflict re-check (b839dfaa)

VERDICT: PASS

Diffed `dab5f018..b839dfaa` over `frontend/mock/server.mjs`, `frontend/tests/next-config.test.ts`, `frontend/src/features/alerts` and `frontend/src/api/alerts.ts`.

1. F-61 alert routing still works. The `ALERT_PATH` import and `createAlertsMock` import are intact. The `ALERT_PATH.test` branch (server.mjs line 317) runs before the new F-71 milestone line (line 380). `ALERT_PATH` matches only the notifications and alert-preferences paths, so the milestone line cannot shadow them. The alerts source and adapter are byte-identical between `dab5f018` and `b839dfaa` (the diff is empty).
2. No F-61 behaviour changed. The only F-61-adjacent edits in the diff are the F-71 additions: the `isMilestoneRequest` import, the milestone route line, and the `isMoneyRequest` comment. The allow-list change is a union. It keeps every F-61 entry (`features/alerts/model.ts`, `mock/alerts.mjs`, `alerts-helpers.ts`, `alerts-model.test.ts`, `alerts.test.tsx`, `alerts-bell.test.tsx`) and adds `money-model.test.ts` and `milestones-model.test.ts`, which exist in the worktree. The `django_url` comment for the alerts adapter is unchanged.
3. Nothing of F-71 was dropped. `isMilestoneRequest` is exported from `frontend/mock/money.mjs` (line 51) and imported and used in server.mjs (lines 54 and 380). The `isMoneyRequest` import and call (line 416) are kept. The fixture regex now also accepts `projects/money/` and `projects/tabs/` paths. The F-71 commit `811465d8` is reachable from `b839dfaa` (it appears in `git log dab5f018..b839dfaa`), so its full change is present.

No blocking findings. Carried-forward round-1 findings are unaffected by this conflict resolution.
