VERDICT: PASS
COMMIT: c218bf2480b82e3753e88943e25b497f2e959e80
REVIEWER: reviewer-technical
AUTHORITY: delegated technical review

## Findings
- TECH-1-1 | non-blocking | low | backend/builder | Revision 0 is sent as 0 in the UI (useTemplateUpload passes `input.revision` as read) as the spec asks, but the generated schema says minimum 1 and the mock rejects `expected_revision < 1` with a 422. The desktop fixture therefore carries revision >= 1 instead of the spec's 0. This is disclosed in build.md for the backend developer. It is worth settling in D-TEMPLATES-VIEW whether 0 is valid. Only a stub component test covers 0.
- TECH-1-2 | non-blocking | low | builder | Phone fidelity visual is 83.3, below 90. This is recorded openly as an open design-engineer decision, not a technical defect. Desktop passes (95.9). Route this to the design review, not to a code fix.

## Checked, no issue
- Shared edits are additive. `SetupFrame` optional props (`what`, `noun`) default to the old rules text, and the looser state types only widen.
- `mock/server.mjs` is 4 lines: import, M1 list, reset, dispatch.
- `e2e/setup.spec.ts` drops only the Templates reserved-tab row, since the page is no longer reserved. No assertion was weakened.
- `tests/mock-contract.test.ts` changes the 501 example from E-TEMPLATES to E-CONVERSATIONS, which exists in openapi. The assertions are identical, and the new path value, body and persona 403s are additive.
- The `cursor` cast lives only in `api.ts` and the mock parses it defensively.
- 422 `fields[]` is read in `uploadTemplateVersion` outside `call` and filtered by type. Entries are kept and nothing reloads.
- `test_template` is only read. A non-boolean shows the test wording, as spec item 2 allows, and nothing sets it to false. After an upload the 200 body is used only if the reload fails.
- There is no blind retry. A ref guard blocks a double press. 409, 403 and 404 reload once. A network or 5xx error reloads once and compares version and revision. If the reload fails too, the control is locked.
- The mock checks persona, scenario, CSRF, 404, 422, then 409 in order. `can_upload` comes from the data.
