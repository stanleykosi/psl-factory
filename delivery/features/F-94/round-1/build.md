STATUS: READY
COMMIT: 551a0f647a08ccc11bebc71377bf51b9987c357c
BUILDER: builder
LANE: frontend

## Summary
- "Start work" now lists "Prepare an invoice" (`pmo-finance/v1`). Its drawer is built from the served `request_schema`: a "Start from" choice, then the controls of that mode.
- Completion mode: Billing coverage and Milestone handoff (both required, from intake-sources `coverage_id`, `handoff_id`). Preparation mode: Billing preparation (required), Invoice (optional, offered under the chosen preparation via `parent_id`), Due date (optional date). Empty optionals send null, as the schema requires. Reference is required.
- Engine change: the engine reads an `intake` that is a `oneOf` whose branches each fix a `mode` const. Any other `oneOf`, or a branch leaf the engine cannot draw (array, object), still makes the line "Not available here yet".
- Money: the form asks for and shows no amount (the schema and the source labels carry none), so there is nothing to show as unknown and nothing is calculated. Nothing hidden for lack of data.

## Changes
- engine/schema.ts: `oneOf` + `format`; `modesOf` turns the branches into one `mode` choice leaf plus branch leaves tagged `when`. plan.ts: `mode`, `date`, `valueLabels` on a field; `activeFields`. body.ts: body and required checks use only the chosen mode's fields. controls.tsx: choice value words; text control can be a date input. engine.tsx: draws active fields. config.ts: `valueLabels`.
- lines/pmoFinance.ts (new) and lines/index.ts: the line config and registration.
- mock/start-live.mjs: the line, its oneOf schema (ajv-validated start), project list, source rows (invoice under preparation 32).
- Tests: tests/start-work-invoice.test.ts (8), start-work-live.test.tsx (chooser list), e2e/start-work-invoice.spec.ts (3 tests x 1440/390), e2e/start-work.spec.ts (radio count 9; the old "no Invoice" assertion replaced). The radio count was already stale on main (F-102 added a line).

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Line listed and startable: unit test and e2e chooser.
2. [x] Both modes build the right body, nulls for empty optionals, valid against the served schema: unit tests, e2e bodies.
3. [x] Nothing chosen: no request, "Start from is required." (e2e).
4. [x] Unreadable oneOf shapes stay unavailable: unit test.
5. [x] No money shown or computed: no amount in the form or the mock rows.

## Validation
- `tsc --noEmit` clean; `eslint . --max-warnings 0` clean; `node --check` mock/start-live.mjs and mock/server.mjs.
- Full vitest: 4565 tests (199 files); one stale assertion in start-work-live fixed and rerun green (54/54). next-config, demo-mock, mock-contract, start-work-live, start-work-engine, line-adapter all in that run.
- Playwright on 4920/4921: start-work-invoice 6/6, start-work-lines 8/8, start-work 10/10 (1440 and 390), axe clean on the completion form. No listeners left.
- Live shapes checked read-only on psl_demo5 as ada.okafor: `GET /api/v1/lines` serves the schema as mocked (title "Prepare an invoice"). Source fields coverage_id, handoff_id, preparation_id, invoice_id read from backend intake_sources.py; I did not read live source rows.

## Held
- Fidelity tool not run (no board for this drawer known to me; open for the design engineer).
- Labels (Start from, Billing coverage, Milestone handoff, Billing preparation, Start invoice) are mine from field names. Source labels come from the server (they end in "#id").
- Not checked against a signed-in live Django response for rows.

## Blocked
Not blocked.
