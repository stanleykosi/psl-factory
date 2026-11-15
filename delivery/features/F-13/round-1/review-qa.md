VERDICT: PASS
COMMIT: fe657c6cc1bbe552e569ab0305047dd63e9297ba
REVIEWER: reviewer-qa
AUTHORITY: reviewer-qa

## Summary
- On head fe657c6 in /Users/Hunchoo/psl-factory-worktrees/f-13/frontend, the full unit suite passed (`npx vitest run`: 13 files, 320 tests). The browser suite also passed (`E2E_PORT=4301 MOCK_PORT=4302 npx playwright test`: 83 passed in 5.7m). Frontend e2e, fixtures and app code are unchanged from base abd0b3e, so no screen regressed.
- All 27 mock fixture files and all 49 E-WORK-LIST rows pass v7 validation with no edits. I checked them twice: through the suite, and with my own Ajv 2020 script against the v7 200-response schemas (`_kind` removed). The script is not vacuous: removing `id` from W-1002, or making it a number, fails validation.
- The drift test and the guard test both pass. The guard compares the `gen:api` source, `DRIFT_SOURCE` and `OPENAPI_PATH`, and the same logic fails for a v4 `gen:api` path. The live mock handles v7 routes and all negative paths: 401, 403, persona none, W-1099 404, 409 stale revision, 422 invalid body, csrf_failed, 501 not_mocked.
- Not proved: this feature has no backend lane, so every journey ran against the contract mock, not the Django API or PostgreSQL. Nothing here shows the real API returns v7 shapes. Proposal-only v7 fields (`assistant_agents`, `allowed_actions`, `workspace` and others) are absent from fixtures and screens, as the spec intends.

## Findings
- QA-1-1 | non-blocking | low | frontend | build.md Validation and AC9 report "vitest (419 passed)" and "17 files, 419 tests". On this head, `npx vitest run` gives 13 files and 320 tests, and the gate's checks.log shows the same 13 and 320. The builder's count probably came from a different tree. The result is still a pass, but the recorded evidence should match the head (delivery/features/F-13/round-1/build.md, Acceptance criteria 9 and Validation).

## Verified
- None (round 1, no fixes).

## Evidence
All commands ran from `cd /Users/Hunchoo/psl-factory-worktrees/f-13/frontend` unless stated otherwise.
- HEAD is `fe657c6cc1bbe552e569ab0305047dd63e9297ba` and the tree is clean. `shasum -a 256 architecture/packages/v7/manifest.json` gives f6231d20...b4d624, which matches the spec. `git diff --stat abd0b3e..HEAD -- architecture` is empty.
- AC1:
  - `grep -rnE "packages/v[0-9]+" ... .` prints only v7, in `package.json:12`, `tests/api-schema-drift.test.ts:12` and `src/api/client.ts:1`.
  - `mock/server.mjs:22` builds `'packages', 'v7'` with `join`.
  - `grep -n "v4\|v3"` over the five named files prints nothing.
- AC2: `node -e "import('./mock/server.mjs')..."` prints `/Users/Hunchoo/psl-factory-worktrees/f-13/architecture/packages/v7/openapi.json`.
- AC3 and AC4:
  - `tests/api-schema-drift.test.ts` passes both tests: the regenerated v7 output is byte-equal to `schema.d.ts`, and the single-source guard holds.
  - I did not run `npm run gen:api` in the tree, to stay read-only. The drift test does the same regeneration in a temp dir.
  - I replayed the guard logic with `node -e`. A `gen:api` source of `../architecture/packages/v4/openapi.json` gives `false` (it would fail), and the current script gives `true`.
- AC5, AC6 and AC7: `npx vitest run tests/api-schema-drift.test.ts tests/mock-work-list.test.ts tests/mock-contract.test.ts tests/mock-decide.test.ts tests/mock-row-item-match.test.ts --reporter=verbose` gives 5 files and 127 passed. The passing tests include:
  - "every fixture in fixtures/work is schema-valid with _kind removed";
  - the 12 tests "W-12xx ... is valid against v7 E-WORK-ITEM";
  - the 401, 403 and 404 tests for all six operations, plus the 409 and 422 tests for claim and decide;
  - "a write without X-CSRFToken gets 403 csrf_failed";
  - "a non-M-1 operation gets 501 not_mocked";
  - "serves the per-id item and 404 for the reserved no-access id".

  `git diff abd0b3e..HEAD -- tests` shows only the path, name and comment changes and the new guard test. No assertion changed.
- Independent fixture check: `node /private/tmp/claude-501/-Users-Hunchoo-psl-factory/a400a30b-92cb-4efc-99c2-4a72d08a67f7/scratchpad/validate.mjs v7` gives "files checked 27 failed 0 | rows checked 49 failed 0". The 27 files are me.{finance_lead,pm,none}, E-TASK-CLAIM, E-TASK-DECIDE, E-WORK-HISTORY, E-WORK-ITEM, E-WORK-LIST and all 19 files in fixtures/work. The same script against v4 also passes 0 of 0, which confirms the change is additive. `git diff --stat abd0b3e..HEAD -- mock/fixtures mock/work-list.mjs e2e` is empty.
- AC8: `npm run typecheck` exits 0. `git diff --stat abd0b3e..HEAD -- src` lists only `src/api/client.ts` (1 line) and `src/api/schema.d.ts`.
- AC9: `npm run lint` exits 0, and `npx vitest run` gives 13 files and 320 passed. I did not re-run `npm run build`, because it writes .next. The gate checks.log on this head shows "Compiled successfully" with 8/8 static pages.
- AC10: `E2E_PORT=4301 MOCK_PORT=4302 npx playwright test --reporter=line` gives 83 passed (5.7m), exit 0. It covered My work, the work item, W-1099 no-access, history, decide, the axe checks and the 390/760/900/1079/1080/1440 layouts. I deleted `test-results` afterwards.
- AC11: I started `MOCK_PORT=4302 node mock/server.mjs` and ran these calls with curl against http://127.0.0.1:4302.

| Request | Result |
|---|---|
| GET /api/v1/me | 200 |
| GET /api/v1/me with `X-Mock-Scenario: 401` | `{"code":"not_signed_in","message":"Sign in to continue."}` |
| GET /api/v1/me with `X-Mock-Scenario: 403` | 403 forbidden |
| GET /api/v1/work?queue=needs_me with cookie `psl_mock_persona=none` | 200 with empty items and zero counts |
| GET /api/v1/work?queue=unassigned as pm | 403 queue_not_open |
| GET /api/v1/work/W-1099 and /api/v1/work/W-1099/history | 404 not_found on both |
| GET /api/v1/assistant/mentions (v7-only path) | 501 not_mocked |
| GET /api/v1/nope (unknown path) | 404 |
| POST /api/v1/tasks/T-1207/claim without CSRF | 403 csrf_failed |
| POST claim with CSRF from /me, `expected_revision` 9 | 409 stale_revision |
| POST claim with an extra field `x` | 422 "Check these fields: x." |
| POST claim at revision 4 | 200 |
| POST decide at stale revision 4 | 409 |
| POST decide with verdict "maybe" | 422 "Check these fields: verdict." |
| POST /__mock/reset | 204 |

  GET W-1002 and GET /me carry none of the v7 proposal fields, so no fixture was enriched. I stopped the mock by its PID on 4302.
- AC12: build.md has "Proposal strips removed: none on base abd0b3e...: frontend/mock/exceptions.mjs absent".
- Cleanup: ports 4301 and 4302 are free, `test-results` is removed, and `git status --porcelain` in the worktree is empty.

## Notes
- I drove the browser through the Playwright suite rather than a separate `F-13-qa` session, because this feature changes no screen. The suite covers every screen the mock serves.
