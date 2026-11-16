STATUS: READY
COMMIT: de541608e755eb9de9b2625187c08abc297a3fb1
BUILDER: builder
LANE: full

## Summary
- "Edit your update" on W-2209 now opens with the saved words and the saved cites, and an unchanged send carries all eight inputs (QA-2-1).
- The shared step form pre-fills any `records` field from a `value` list of `{value, label}` (general, not weekly-specific).
- An uncertain item reloaded with no `reconcile` now says "We are checking what happened. Nothing was sent again." with a Reload button (QA-2-3).
- Contract mock only (D-LINE-WORKSPACE proposed): no real send, delivery or idempotency claim. QA-2-2 left as instructed.

## Changes
- `frontend/mock/fixtures/work/W-2209.json`: the four `*_cites` fields carry their saved records as `value: [{value, label}]` (values match E-LINE-OPTIONS: MS-0002, MTG-0141, ISS-0233, MTG-0140, ACT-0412, CR-0031).
- `frontend/src/features/workspace/StepForm.tsx`: initial form values also take a `records` field's `value` when it is a non-empty list of `{value, label}` strings; other shapes are ignored.
- `frontend/src/features/workspace/Workspace.tsx`: the no-reconcile sentence and Reload for `state: effect_uncertain` with no `reconcile` (not shown when the in-session uncertain notice is already up).
- Tests: `tests/weekly-returned-received.test.tsx` (23 tests), `tests/weekly-mock.test.ts`, `tests/mock-contract.test.ts`.
- Contract note: the generated type says a step field's `value` is a string, so the list is a proposal (BACKEND-HANDOFF priority 2, F-21 UX-1-1). `mock-contract.test.ts` checks the list's shape and strips it before the schema check (`CONTRACT_BODY['E-WORK-ITEM']`), as it does for the other proposal fields; `weekly-mock.test.ts` does the same. No file under `frontend/src/api/**` changed.

## Fixes
- QA-2-1 | de541608e755eb9de9b2625187c08abc297a3fb1 | fixture cites as `value` lists; form pre-fills records fields; test asserts the chips and all eight inputs
- QA-2-3 | de541608e755eb9de9b2625187c08abc297a3fb1 | checking sentence and Reload on load when an uncertain item has no reconcile

Left: QA-2-2 (mock `server.mjs` fallback for unknown ids, read-only here).

## Acceptance criteria
5. [x] Edit opens the form with the saved words and cites; one POST with the eight inputs (cites as saved), `expected_revision` 6, UUID key, no note or evidence: component test.
11. [x] The "checking" sentence shows on a fresh page without reconcile; reconcile present still shows the ReconcilePanel only: two component tests.
Others unchanged from round 2.

## Validation
- `bash delivery/checks.sh`: exit 0 (load about 22): 79 files, 1676 tests passed. A first attempt stopped at typecheck on a test type error, fixed before commit.
- `E2E_PORT=4750 MOCK_PORT=4751 npx playwright test e2e/weekly.spec.ts e2e/weekly-returned-received.spec.ts e2e/workspace.spec.ts`: 79 passed.
- No fidelity re-run: the boards show only the closed page; the cites live inside the Edit form (not drawn on a board) and the new sentence appears only for an uncertain item with no reconcile, which no scored board (W-2209, W-2211) has. Round 2 scores stand.
- Servers stopped, test-results deleted.

## Verified
- QA-2-1 | fixed | `weekly-returned-received.test.tsx`: the four pickers show the saved record labels; an unchanged send's `inputs` equal all eight keys including `status_cites: ['MS-0002','MTG-0141']`, `risks_cites: ['ISS-0233']`, `timeline_cites: ['MTG-0140']`, `next_steps_cites: ['ACT-0412','CR-0031']`
- QA-2-3 | fixed | component tests on W-2212 with `reconcile` removed (sentence, only a Reload button, no radiogroup, no POST) and with it present (no sentence)

## Blocked
Not blocked.
