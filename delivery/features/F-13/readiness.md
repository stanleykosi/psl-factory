DECISION: READY
RISK: medium
SURFACES: api, contract-change
PRODUCT-ACCEPTANCE: not-required
BLOCKING-DECISIONS: none
COMMIT: none (round 0, no head yet)
REVIEWER: readiness
AUTHORITY: PMO readiness (delivery step 1)

## Summary
- F-13 is FE-CONTRACT-V7 (architecture/packages/v7/delivery.md:1745-1774). It has no gate_ids and no unresolved gates. Its only dependency, T-FRONTEND-SHELL (F-01), is merged. The outcome is one thing you can check: the frontend contract is v7, and every fixture and handler on the base validates against it (A-CONTRACT-V7, model.json:20436-20450). There are no screen changes, so it is small enough for one PR.
- v7 is a proposal the coordinator drafted (D-12, commit 61a7ade). Its new decisions are r1 `proposed`. They count only under the design engineer's recorded exception (architecture/sources/decisions-2026-11-14-v2.md (g); decisions-2026-11-15.md (h)(i)). The limits: the contract mock only, the backend developer may change or refuse any field, and nothing is released.
- **Correction to the brief:** F-06 is not merged. feature.json has state AWAITING_USER_APPROVAL, merge_status not_merged, PR #11 open and human_approval pending, and decision.md:39 still asks the user. The base has no `frontend/mock/exceptions.mjs`. F-02's fidelity round, F-05, F-07 and F-08 are also unmerged. So the base carries **no** proposal-field strip workaround today. The "fold in as they merge" part cannot be binding scope for this PR (PMO-0-1).
- The base points at more than one version. Four files point at v4, and `tests/mock-work-list.test.ts:15` reads **v3** directly. That fifth file was not in the brief, and it is in scope (PMO-0-2).

## Findings
- PMO-0-1 | blocking | medium | integration | The scope has to be fixed at the base SHA the branch starts from. A moving "fold in as they merge" target is not reviewable.
  - Expected: F-13 repoints the base and removes any proposal strip that exists **on its base**.
  - If PR #11 (F-06) merges before F-13 branches, that strip is in scope: `mock/exceptions.mjs` `contractBody` and its comment (lines 7-10, 24-28), `tests/mock-contract.test.ts:37`, and `tests/exceptions-mock.test.ts:30`.
  - Each lane still unmerged when F-13 merges (F-02 fidelity, F-05, F-06 if still open, F-07, F-08) removes its own strip and validates its own fixtures against v7 when it rebases onto F-13. The coordinator checks this at integration.
  - Actual: the brief names F-06 as merged, but it is not.
- PMO-0-2 | blocking | low | frontend | `frontend/tests/mock-work-list.test.ts:15` loads `architecture/packages/v3/openapi.json` directly, so it would keep checking E-WORK-LIST against v3 after the repoint. Expected: read `OPENAPI_PATH` from `mock/server.mjs`, the same way mock-contract.test.ts and mock-decide.test.ts do.
- PMO-0-3 | non-blocking | medium | integration | A-CONTRACT-V7's "given" is "the frontend on the v6 contract", but the base is on v4 because F-05's v6 repoint is unmerged. Going straight from v4 to v7 is acceptable only because both steps were recorded as additive (F-05/readiness.md:35; decisions-2026-11-15.md "every v6 field, required list, enum and parameter is kept"). The builder must prove this with the tests and must not assume it:
  - every fixture on the base passes `tests/mock-contract.test.ts` against v7 **without editing the fixture**;
  - `tsc --noEmit` passes on the regenerated `schema.d.ts` with no edits to app code. A widened enum or union that breaks an exhaustive switch is a contract finding, raised for the architecture. The builder must not patch around it in feature code.
- PMO-0-4 | non-blocking | medium | integration | F-05 changes the same four lines to v6 (worktree f-05: `mock/server.mjs:24`, `package.json:12`, `tests/api-schema-drift.test.ts:16`, `src/api/client.ts:1`). Expected: when F-05 rebases onto F-13, it drops its repoint commit, takes v7 and regenerates `schema.d.ts`. The coordinator owns that conflict, as the brief says.
- PMO-0-5 | non-blocking | low | frontend | The `_kind` stripping in `tests/mock-contract.test.ts:219-235` and `mock/server.mjs:55` is for a mock-only paging marker, not a proposal field. v7 does not and should not declare it. It stays.

## Scope
**Outcome:** the frontend builds, type-checks and runs its mock against `architecture/packages/v7/openapi.json`. Every fixture and handler on the base validates against v7 with no fixture edits. Where v7 now declares a proposal field that a merged lane used to strip, the strip is gone and the field validates.

**In (binding):**
1. `frontend/mock/server.mjs:22`: change `OPENAPI_PATH` to `packages/v7`, and change the header comment at line 1 from "v4" to "v7".
2. `frontend/package.json:12`: point `gen:api` at `../architecture/packages/v7/openapi.json`.
3. `frontend/src/api/schema.d.ts`: regenerate it with `npm run gen:api` only. No hand edits.
4. `frontend/tests/api-schema-drift.test.ts:10,16`: change the test name and path to v7.
5. `frontend/src/api/client.ts:1`: change the version comment to v7.
6. `frontend/tests/mock-work-list.test.ts:15`: read `OPENAPI_PATH` (PMO-0-2).
7. Remove proposal-field strips only where they are on the base and v7 declares the field (PMO-0-1). List each removal in build.md with the v7 schema path that now declares the field.
8. Evidence:
   - `vitest` passes, including mock-contract, mock-decide, mock-work-list and api-schema-drift;
   - `tsc --noEmit` passes;
   - lint and build pass;
   - the existing Playwright suite passes unchanged on the v7 mock.

**Out:**
- Any screen, component, copy or style change.
- New mock handlers, or operations added to `M1_OPERATIONS`.
- New fixtures, and edits to existing fixtures (if one fails, raise it under PMO-0-3).
- Edits to `architecture/**`.
- Unmerged lanes' files and their proposal fields (PMO-0-1).
- `src/shell/**`.
- New npm dependencies.
- The real API.

**Task IDs:** FE-CONTRACT-V7 (R-FRONTEND). **Acceptance:** A-CONTRACT-V7. **Endpoints:** none new. These are the existing mocked operations (E-ME, E-WORK-LIST, E-WORK-ITEM, E-WORK-HISTORY, E-TASK-CLAIM, E-TASK-DECIDE), plus E-EXCEPTIONS if F-06 is on the base.

**Ownership:** the files in items 1-7 only. The integration owner sequences F-13 ahead of the open lanes' rebases.

## Risk
The rating is medium, not low:
- this is a cross-layer contract change that every lane builds on;
- the regenerated `src/api/schema.d.ts` is imported by all typed client code;
- a mistake here (a stale path left behind, as `mock-work-list.test.ts:15` already shows, or a non-additive change from v4 to v7) would quietly weaken the contract check for all features.

It touches no data, money, identity, migration or runtime write, and it changes no screen. That is why the surfaces are only `api` (the mock's routes and response validation) and `contract-change` (the v4 to v7 repoint, consuming the r1 proposals under the recorded exception). `ui` and `dependency` do not apply. Product acceptance is not required: this is conformance work, and the client sees nothing change.

## Questions
None.
