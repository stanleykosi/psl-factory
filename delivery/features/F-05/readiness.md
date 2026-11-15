DECISION: READY
RISK: high
SURFACES: ui, api, security, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
COMMIT: none (round 0, no head yet)
REVIEWER: readiness
AUTHORITY: PMO readiness (delivery step 1)

## Summary
- F-05 is now FE-M2A in architecture v6 (packages/v6, commit cfcdd94): core Start work only. That means the button in the top bar and phone bar, the line chooser, and drawers without proof fields for invoice, weekly, minutes, issue, change, incident, escalation and leadership. Proof fields and the Finance and payroll drawers are FE-M2A-PROOF, which depends on FE-M2A and FE-M2B-RESPONSE (packages/v6/delivery.md:1198-1230). The split I proposed in v5 is now the architecture's own split.
- The gates are clear:
  - FE-M2A depends only on T-FRONTEND-SHELL (merged, F-01). delivery.md:972-1003 and validation.json:170 both list no unresolved gates.
  - D-LEADERS-START r1 is approved.
  - The client approved SCR-04 and CMP-23 on 13 Nov (design/review.json, canvas 1794581312-b166).
- The five v5 findings are closed by D-START-INTAKE r1. It adds `case_scope`, `case_field`, `case_id` and `case_revision` per line; typed intake kinds with help, placeholder, options, `options_source` and `depends_on`; the new E-LINE-OPTIONS with `case_id` and `case_revision` per option; `subtitle`, `next`, `start_via` and `default_line`; `/me startable_lines` as line keys; and a 422 with `fields[]`.
- D-START-INTAKE is still `proposed`, and the backend developer owns it. The design engineer's recorded choices count as an explicit exception, with limits: decisions-2026-11-13-v3.md item 1 and decisions-2026-11-14-v2.md items (f) and (g). The shapes may change, the frontend builds on the contract mock only, D-START-INTAKE gates T-START and FE-CONNECT-1, and nothing is released.
- Risk is high. This is the write that creates work and sets agents going. It carries CSRF, an idempotency key and a case revision, and F-05 must prove that a double press or a retry never starts the same work twice. F-05 is also the only lane that edits `src/shell/**` and repoints the mock contract to v6.

## Findings
- PMO-0-1 | non-blocking | medium | backend | E-WORK-START says nothing about what a replayed `idempotency_key` returns (handoff.md:3915-4121). Expected: for the mock, the same key with the same body returns the same 201 `work_id` and creates nothing new, and the same key with a different body returns 409. Record this in build.md as a question for the backend developer. Actual: the contract does not say.
- PMO-0-2 | non-blocking | medium | frontend | The contract also does not say which idempotency key goes with which retry. A builder would have to guess. Engineering proposal, binding for this feature:
  - The key is created when the drawer opens.
  - A double press, a network failure, a timeout or a 5xx reuses the key. While a submit is in flight, start is disabled.
  - A definitive 409 or 422 means nothing was written. After one, the next press uses a new key.
  - Closing the drawer discards the key.
- PMO-0-3 | non-blocking | medium | frontend | A 409 on start means the case revision is stale. Expected: keep everything the person typed and reload the revision from where it came from. For `case_scope: project`, that is E-LINE-OPTIONS for the `case_field`, which returns the chosen option's `case_revision`. For `fixed`, that is E-LINES. Show the stale notice, and only resubmit when the person presses start again (no automatic retry). If the chosen option is no longer returned, clear that field and say so.
- PMO-0-4 | non-blocking | medium | integration | The contract repoint is F-05's alone. F-06, F-07 and F-08 all stay on v4 and must not touch `src/shell/**` or `schema.d.ts`. Expected, all in one commit:
  - `frontend/mock/server.mjs:22` OPENAPI_PATH to v6;
  - `package.json` gen:api;
  - a regenerated `src/api/schema.d.ts`;
  - `tests/api-schema-drift.test.ts`;
  - the version comment in `src/api/client.ts`.

  v6 is additive and optional (impact.json; the rationales of D-START-INTAKE, D-RESPONSE-VIEW, D-PROJECT-TAB-ROWS and D-WORK-ACTIONS-VIEW). So every fixture, including those of any lane that merged first, must still pass `tests/mock-contract.test.ts` against v6. Rebase onto whichever lane merged before the repoint.
- PMO-0-5 | non-blocking | medium | frontend | `me.pm.json` and `me.finance_lead.json` still hold display titles in `startable_lines` ("Weekly client update", "Prepare an invoice"). Under D-START-INTAKE (7) they must be line keys that match the E-LINES fixtures. Expected:
  - F-05 rewrites them to keys.
  - F-05 adds a `ceo` persona (`me.ceo.json` and `PERSONAS`) whose E-LINES has no `default_line`.
  - `me.none.json` stays empty, so the button is absent.
- PMO-0-6 | non-blocking | low | integration | Some lines or fields fall outside this feature: a line with `start_via: finance_import`, and fields of kind `evidence` or `money`. If the mock or a later backend returns one, F-05 must invent nothing. Expected: optional fields of those kinds are not rendered and not sent. A line with a required field of those kinds, or with `start_via` other than `work_start`, opens a drawer that says it can't be started here yet and shows no start button. F-05's own fixtures contain none of these, and the copy goes into build.md for product acceptance.

## Scope
**Binding for the spec writer.**

**Outcome (one, observable):** a person whose `/me startable_lines` is not empty sees Start work, as the CMP-23 split button in the top bar or as "+ Start" on the phone bar. They pick a line, fill its intake in a drawer over the current page, press start, and land on `/work/<work_id>`. A missing or invalid field names itself inline (the validation board). This works at 390px and 1440px on the contract mock (v6), and the F-05 part of A-START, the F-05 part of A-START-INTAKE and A-ACCESSIBILITY pass.

**In:**
1. **Button (CMP-23).**
   - It is mounted in `src/shell/TopNav.tsx` and `src/shell/PhoneBar.tsx` from a component exported by `src/features/start-work/`, and is shown only when `me.startable_lines` is not empty.
   - The main part opens the drawer for E-LINES `default_line`. When there is no `default_line` (CEO/CTO, D-LEADERS-START), it opens the chooser.
   - The chevron, and "+ Start" on the phone, always open the chooser.
   - Nothing is derived from `/me` roles.
2. **Chooser ("Choose a line").**
   - Lines come from E-LINES, grouped by `group`, with `subtitle`, a search over title and subtitle, and "LINES YOU CAN START · n" where n is the items returned.
   - The "Describe it to Tola" link goes to `/assistant`.
   - It has empty, loading and error (Try again) states. A 401 goes to `SignedOutState`, and a 403 or 404 goes through the F-01 `ApiError`.
   - A line that is not returned is never offered.
3. **Drawer.**
   - It renders `intake[]` in the order returned, by kind: text, long_text, date, date_range, period, datetime, integer, choice (fixed `options`), record or records (E-LINE-OPTIONS with `parent` from `depends_on`, `q` search, `limit` 10/20/50, "Show more" on `next_cursor`, and `disabled_reason` shown and not selectable), and display (shown, never sent).
   - It shows `help`, `placeholder` and `required`.
   - It shows the "What happens next" block from `next`, showing only the fields that are present.
   - Value shapes follow the E-LINES `type` description exactly.
   - When a parent value changes, dependent fields are cleared.
4. **Case.** For `case_scope: project`, `case_id` and `case_revision` come from the option chosen in `case_field`. For `fixed`, they come from the line. If neither resolves, start stays disabled. The frontend never guesses a case.
5. **Submit.**
   - The request is E-WORK-START with the CSRF header and the body `{line, case_id, case_revision, intake, idempotency_key}`.
   - Key handling follows PMO-0-2 and the 409 follows PMO-0-3.
   - A 422 maps `fields[].name` to inline messages, and anything unmatched goes in a summary at the top of the drawer.
   - A 403 or 404 shows the `ApiError` view inside the drawer and keeps what was typed.
   - A 201 closes the drawer and routes to `/work/<work_id>` (F-03's route).
6. **Drawers covered by fixtures:** invoice (default and validation), weekly, minutes without proof, issue, change without proof, incident, escalation and leadership. Each must match its SCR-04 desktop and mobile board, minus the proof field.
7. **Mock.**
   - `frontend/mock/start-work.mjs` handles E-LINES, E-LINE-OPTIONS and E-WORK-START. It validates the start body against the v6 request schema with the existing `ajv`, and answers:
     - 422 with `fields[]` for missing required intake;
     - 409 for a stale `case_revision`;
     - 403 for a line the persona was not given;
     - the replay behaviour in PMO-0-1.
   - Fixtures: `frontend/mock/fixtures/start-work/**` (E-LINES per persona, options per line and field, at least 25 project options so "Show more" appears, and an incomplete milestone with a `disabled_reason`). Started work items go in `frontend/mock/fixtures/work/W-14xx.json`. Plus the `me.*.json` changes from PMO-0-5.
   - In `server.mjs`, one line each in `M1_OPERATIONS`, the dispatch and `PERSONAS`.
8. **Tests.**
   - Component tests: button visibility, default_line versus menu (pm versus ceo), rendering by kind, parent narrowing, case resolution, the 422 mapping, 409 keeping values, 403, and double press or network retry reusing one key (exactly one work created in the mock).
   - Mock contract tests for every new fixture against v6.
   - Update `tests/shell.test.tsx:127` ("has no Start work…"), which must now assert the button is shown or hidden by `startable_lines`.
   - Playwright and axe at 390px and 1440px for the chooser, one drawer, validation and the CEO menu.

**Out:**
- Proof and evidence fields and E-EVIDENCE-UPLOAD.
- Money fields.
- The Finance and payroll drawers (accounts, schedules, ppe, forecast, bu, ledger, payroll) and `finance_import` lines. These are FE-M2A-PROOF.
- SCR-23 (Log a received RFP).
- Assistant drafts that start work (FE-M4).
- Backend and `apps/api` work (T-START, T-BACKEND-ROLES).
- The real API (FE-CONNECT-1).
- Any edit to `openapi.json` or `architecture/**`.
- New npm dependencies.
- A visible SAMPLE DATA tag, which still follows `NEXT_PUBLIC_SHOW_SAMPLE_LABEL` (decisions-2026-11-14 (c)).

**Ownership (disjoint from F-06, F-07 and F-08):**
- Owns:
  - `frontend/src/features/start-work/**`
  - `frontend/mock/start-work.mjs`
  - `frontend/mock/fixtures/start-work/**`
  - `frontend/mock/fixtures/work/W-14xx*.json`
  - `frontend/mock/fixtures/me.ceo.json`
  - `frontend/tests/start-work*.test.ts(x)`
  - `frontend/e2e/start-work.spec.ts`
- Only F-05 edits these, and each change is listed in build.md:
  - `src/shell/TopNav.tsx` and `src/shell/PhoneBar.tsx`, limited to mounting the button, plus `tests/shell.test.tsx`;
  - the contract repoint (PMO-0-4);
  - `me.pm.json` and `me.finance_lead.json`;
  - one line each in `server.mjs`.
- Does not touch:
  - the E-PROJECTS or E-PROJECT handlers and fixtures (F-07);
  - the exceptions files (F-06);
  - the overview files (F-08);
  - `src/features/work-item/**` and the existing work fixtures.

**Task IDs:** FE-M2A (R-START; D-LEADERS-START r1; D-START-INTAKE r1 under the recorded exception).

**Endpoints:**
- E-LINES (GET /api/v1/lines)
- E-LINE-OPTIONS (GET /api/v1/lines/{line_key}/fields/{field}/options)
- E-WORK-START (POST /api/v1/work)
- E-ME (startable_lines)

All on the contract mock.

**Acceptance:**
- A-START, frontend half: a valid start returns 201 and goes to the work item, a missing field shows the 422 inline, and a line without permission is absent.
- A-START-INTAKE, every part except evidence and money: fields by kind, options from E-LINE-OPTIONS narrowed by parent, the case from the project or the fixed line, the CEO menu with no `default_line`, and a 422 per field.
- A-ACCESSIBILITY.

## Risk
I rated it high:
- E-WORK-START is the write that creates a work item and starts agents (JR-01). It is CSRF-bound and carries an idempotency key and a case revision (INV-REVISION, handoff.md:3915-3947). A duplicate start, or a start on the wrong case, is hard to undo.
- The case now comes from a chosen option or a fixed line (D-START-INTAKE r1), so wrong case resolution is a real failure mode.
- The feature also edits the shared shell (`src/shell/TopNav.tsx`, `PhoneBar.tsx`) and repoints the shared contract types for every lane.

Surfaces:
- `ui`: SCR-04 and CMP-23 on both bars.
- `api`: E-LINES, E-LINE-OPTIONS and E-WORK-START.
- `security`: CSRF, never offering a line or option the API did not return, and nothing derived from roles.
- `contract-change`: the consumer side of the D-START-INTAKE proposal and the v4 to v6 repoint.

Excluded surfaces:
- `payments`: money fields and payroll are out.
- `auth`: the feature uses the existing session.
- `dependency`: no packages are added.

Product acceptance is required:
- this is a new flow for the client;
- minutes and change are built without their approved proof field;
- the "can't start here yet" copy (PMO-0-6) has no board.

## Notes
- I did not run `design.py check`, because my role is read-only. The approval in design/review.json covers SCR-04 and CMP-23. The SCR-04 boards are in design/canvas/project.
- Replaces readiness-v5-not-ready.md. PMO-0-1 to PMO-0-5 there are closed by D-START-INTAKE r1. Its PMO-0-6 (shared mock files) is carried into the ownership above.

## Questions
None.
