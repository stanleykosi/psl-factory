DECISION: READY
RISK: low
SURFACES: contract-change
PRODUCT-ACCEPTANCE: not-required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Main b8542c79 fails `npx tsc --noEmit` at tests/shell-live.test.tsx:95 because live-schema.d.ts (API 1.24.0) now requires `positions` on /me and `url` and `available` on destinations[].
- Conformance-only hotfix. It brings frontend fixtures and tests up to the already-generated 1.24.0 types. It adds no behaviour.
- The mock-live-* Ajv fixture tests are likely affected and are in scope.
- The new behaviour behind these fields belongs to F-67 and stays out.

## Scope
In:
- Update the mock /me fixture and the related live-shape fixtures to the 1.24.0 shapes. /me gets `positions`. Each destinations[] entry gets `url` and `available`.
- Update the frame tests (tests/shell-live.test.tsx and the mock-live-* Ajv tests) to match.
- Make only the minimal non-test code change the regenerated types force.
- Done when `npx tsc --noEmit` and the affected tests pass on the branch.

Out:
- Any use of `positions`, `url` or `available` in the UI, such as navigation or availability handling (F-67).
- Hand-editing live-schema.d.ts, and any backend change.
- Weakening or skipping tests or schema validation to get green.

Task IDs and endpoints: no new process IDs. The only endpoint is GET /me, with destinations[] and the live-shape fixtures.

## Risk
Low. The change is limited to fixtures and tests, plus any type-forced adjustment, against an already-generated contract. It has no data, auth or money impact. SURFACES is `contract-change` because the work aligns the frontend with API 1.24.0. PRODUCT-ACCEPTANCE is not-required because it only conforms to the approved contract.
