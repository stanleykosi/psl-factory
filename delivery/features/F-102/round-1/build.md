STATUS: READY
COMMIT: 2b6411d31a9a565bd8152cc9dd8a9727cdd8afdb
BUILDER: builder
LANE: full

## Summary
- `/work/{id}` on line finance-ppe now reads `GET /work/{id}/assets` through a new `assetsAdapter` (panel key `assets`): stage and finding, register header, assets, changes, closing controls, unclear dates and dated assets, opening proof words, depreciation schedule (held reason or ready rows, totals, scope, "Posted to the ledger"), who may review what as text only.
- Proof ("Open proof", per fact id in `date_attachment_ids` only) and "Open accounting note" (only when the URL is non-null) are drawn by an `Actions` component with no write control.
- "Start schedule" added to the Start work drawer as a form-engine line (`finance-ppe/v1`: register required, prior schedule and ledger mapping optional, null when unchosen).
- Registry change is one import line. No change to workspace frame, useWorkCommand, or the shared APIs.

## Changes
- New: `frontend/src/features/fixed-assets/{labels.ts,assetsAdapter.ts,AssetsActions.tsx}`; `frontend/mock/assets-live.mjs` (ids 3901-3910, no clash with listed ids); `frontend/src/features/start-work/lines/financePpe.ts`.
- Edited: `workspace/lines/index.ts` (one import), `start-work/lines/index.ts` (one form), `mock/server.mjs` (route), `mock/start-live.mjs` (finance-ppe schema, line, source rows), `src/api/types.ts` (`LiveAssets`), `tests/next-config.test.ts` (allow-list `assets-live.mjs`, one line), `tests/start-work-live.test.tsx` (chooser now lists the new line).
- Tests: `tests/assets-live.test.tsx` (31), `tests/start-work-ppe-live.test.ts` (6), `e2e/fixed-assets-live.spec.ts` (18).
- Contract note: entity, provider and category are pattern-limited (no spaces) in contract 1.24.0, so mock values read `PSL-Technologies`.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] 3901 stage, finding, register header, 64 assets, no track/agent card: e2e + unit.
2. [x] Date unclear for 3 assets; dated assets show dates and basis in words: unit + e2e.
3. [x] Open proof only for listed fact ids, exact route; unlisted id 404 in mock: unit + e2e.
4. [x] Null money Unknown, residual "0.00" stays a real zero: unit + e2e.
5. [x] Partial completeness; native source verified shown as returned ("No"): e2e.
6. [x] Held shows reason, no totals; ready shows rows, totals, scope, Posted No: e2e.
7. [x] 3904 no schedule, "No review is open for you.": e2e.
8. [x] Review options text only; no `liveApi.POST` in the feature: unit + e2e.
9. [x] Accounting note link only when URL set: unit + e2e (3905, 3906).
10. [x] 3908 empty sentence and finding: e2e.
11. [x] 3909 404 and 3910 403 both "This record is unavailable.": unit + e2e.
12. [x] csrf_failed: not no-access, session refreshed once, read not repeated: unit page test.
13. [x] 503: header stays, Try again, no auto retry: unit + e2e.
14. [x] Registered for key `assets`, existing Section kinds only; no diff under `features/workspace/` except the one registry import line.
15-16. [ ] Not run: live Django comparison with two accounts (demo db has no fixed-asset case; no data to compare).
17-18. [x] Start body, null ids, same key per attempt, 409, 422, csrf_failed: unit tests on body and mock (the drawer's shared start state machine is unchanged and already tested).
19. [x] No "never reads asset values" or "MANAGEMENT ACCOUNTS" text (tested).
20. [~] Viewed 1440/390 screenshots of the page; the design-fidelity tool was not run (lean mode, no boards drawn for the live-only parts; see held).
21. [x] Tests below.

## Validation
- `bash delivery/checks.sh`: ci PASS.
- tsc clean; eslint `--max-warnings 0` clean; `node --check` on every mock file passes.
- vitest: assets-live 31/31, start-work-ppe-live 6/6, plus next-config, line-adapter, demo-mock, mock-contract, live-work-item, start-work-engine, start-work-live (54), start-work-engine-ui: 505 passed after the one chooser expectation was updated.
- Playwright on mock (ports 4940/4941, desktop 1440 and phone 390, axe wcag2a-22aa): 18/18. Servers stopped.

## Held
- Live check against Django with two accounts (AC15-16): no fixed-asset case in psl_demo5.
- Design fidelity run on SCR-55 boards: not run.
- On phone the wide tables scroll sideways (shared table behaviour), so amounts are in full but not all columns fit; the phone short form is not drawn (D-182).
- 503/network wording comes from the shared panel frame ("We couldn't load this part of the page." with Try again), not "Try again shortly"; the frame is not mine to change.
- The 401 case shows words plus a Sign in link; the page header's own 401 handling is unchanged.
- Review controls, uploads, register capture, corrections: F-102B.
