STATUS: READY
COMMIT: 006cd6e40c6a770b60b31665d70c94d955523cd2
BUILDER: builder
LANE: full

## Summary
- The Delivery tab now reads GET /projects/{case_id}/delivery-overview (API 1.25.0) and draws the six lines in fixed order (release, go-live, hypercare, handover, archive, closure), numbered 01 to 06, with reference, state tag, "Updated <day month>" and an "Open" link to /work/{work_id}.
- Not-started rows are empty; no counts, DLV number, gate wording or Tola text. Read only (GET only).
- Closure not started: the release-register then closure-checklist are read and held/unknown/unavailable checks are listed as "Closure waits on:". Failures are silent.
- Questions built on the recommended option: Q1 (a) a Delivery tab after Journey for every project; Q2 (a) handover 04, archive 05; Q3 (a) board-only parts hidden, no sub-nav strip; Q4 (a) the table wording; Q5 (a) the board's static sentence is drawn under the rows (commit 78d3f98f), desktop width only, hidden at phone width as SCR-43-mobile does not draw it.
- Mock 4991 serves the overview, release-register and closure-checklist (not in v7).

## Changes
- `frontend/src/features/projects/deliveryModel.ts` (new): key order, state words, response check, rows, hold reasons.
- `frontend/src/features/projects/useDeliveryOverview.ts` (new): read with sequence guard, silent closure reasons.
- `frontend/src/features/projects/DeliveryTab.tsx`, `delivery.css`: the tab and its states (skeleton with aria-busy, error panel with Try again, ProjectNoAccess).
- `frontend/src/features/projects/ProjectJourney.tsx` (shared, one line): passes `caseId` to `DeliveryTab`.
- `frontend/src/features/projects/model.ts` (shared, separate commit 878ef056): `visibleTabs` inserts Delivery after Journey. Tests `projects-model.test.ts` and `projects-journey.test.tsx` updated for the new tab.
- `frontend/mock/delivery-overview.mjs` (new), `mock/server.mjs` (3 lines): P-0101 shuffled lines, closure not started, checklist with held checks; P-0099 403; others all not started. No `mock/finance*` or payments fixtures touched.
- Tests: `tests/delivery-model.test.ts`, `tests/delivery-tab.test.tsx`.
- `src/api/live-schema.d.ts`, `src/features/workspace`, F-85 adapter: untouched.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] one overview request: component test asserts exactly one overview read.
2. [x] order with shuffled lines: model test and tab test (fixture is shuffled).
3. [x] started row fields and Open to /work/2501: tab test.
4. [x] not-started rows: all-not-started project test, no links.
5. [x] 11 states, null and made-up value: model test.
6. [x] banned text absent: tab test.
7. [x] closure reasons only held/unknown/unavailable with finding: tab and model tests.
8. [x] ready_to_prepare true, register 403, checklist 500, network: no reason, six rows stay.
9. [x] no checklist call when release has no work or closure has work: tab test.
10. [x] 403 and 404 show ProjectNoAccess, no server text: tab test. Not checked in a browser on 4990.
11. [x] 500, network, wrong shape show the error panel; Try again re-reads once: tab test.
12. [x] wrong-shape check (five lines, none, duplicate, unknown key, missing field): model test.
13. [x] GET only: test asserts every request is GET; no write calls in the new files.
14. [ ] 390px browser check not run (see Validation).
15. [x] no workspace or protected-path changes (only files listed above).
16. [x] model, hook race and tab-state tests exist; live-schema unchanged.

## Validation
- `npx vitest run tests/delivery-model.test.ts tests/delivery-tab.test.tsx tests/projects-journey.test.tsx tests/projects-model.test.ts`: 4 files, 86 tests pass (re-run after the Q5 change; lint clean).
- `npm run lint`: exit 0.
- `npx tsc --noEmit`: only failure is tests/shell-live.test.tsx (lane A, known on main).
- Full `vitest run` and `next build`: not completed (machine load, coordinator told me not to rerun the full suite); `checks.sh` not run in full, and I did not run it because it calls `npm ci`.
- Not done: dev-server look at 4990/390px and the design-fidelity run (SCR-43 desktop/mobile). Both are open for the reviewer or a next round; no waiver is proposed.

## Notes
- Q5 sentence: shown at desktop width only (useIsPhone, below 720px hidden), per the mobile board.
- The 403/404 panel is the full-page ProjectNoAccess, as the spec says, so a heading repeats the frame inside the tab.
- effect_uncertain uses the existing amber waiting tag (no red tag exists).
