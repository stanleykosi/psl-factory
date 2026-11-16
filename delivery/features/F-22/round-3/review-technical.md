VERDICT: PASS
COMMIT: de541608e755eb9de9b2625187c08abc297a3fb1
REVIEWER: reviewer-technical
AUTHORITY: delivery technical review

## Summary
- The StepForm records prefill is general and narrow. It reads `value` only for a non-restricted `records` field, keeps only `{value, label}` string pairs, and ignores any other shape. Text and long_text behaviour is unchanged.
- The list-valued `value` is a contract proposal. It is shape-checked and stripped before the schema check in `mock-contract.test.ts` and `weekly-mock.test.ts`. Nothing under `src/api` changed.
- The "We are checking what happened" sentence shows only for `state: effect_uncertain` with no `reconcile`, and only when the in-session uncertain notice is not already up. It has a Reload button and no send control. Tests cover both the absent and present reconcile cases.
- The unchanged-send test now asserts all eight inputs with the saved cites. Still contract mock only.

## Findings
- TECH-3-1 | non-blocking | frontend/tests/weekly-mock.test.ts:24 | `savedRecords = buildSavedRecords()` is an indirection that adds nothing: a plain function would do, and it duplicates `savedRecordsStripped` in mock-contract.test.ts. | Optional tidy: use one plain function, or share it from a test helper.

## Verified
- QA-2-1 | verified | StepForm.tsx initial values and the W-2209 fixture `value` lists. The test checks the four pickers' labels and the full eight-key `inputs` body.
- QA-2-3 | verified | Workspace.tsx notice and the two W-2212 component tests (reconcile removed: sentence, only a Reload button, no radiogroup, no POST; reconcile present: no sentence).
