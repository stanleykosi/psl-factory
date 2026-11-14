DECISION: NOT-READY
RISK: high
SURFACES: ui, api, security, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
COMMIT: none (round 0, no head yet)
REVIEWER: readiness
AUTHORITY: PMO readiness (delivery step 1)

## Summary
- F-05 is FE-M2A in architecture v5: the Start work button and the line intake drawers (SCR-04, 17 states). Most gates are met:
  - FE-M2A depends only on T-FRONTEND-SHELL, which is merged (F-01). delivery.md says "Unresolved gates: none".
  - D-LEADERS-START r1 is approved.
  - SCR-04 is in the client approval of 13 Nov (design/review.json, canvas 1794581312-b166).
  - E-LINES and E-WORK-START did not change from v4 (impact.json).
- The gate that is missing is the contract. E-LINES returns only `key`, `title`, `group` and `intake[{name,label,type,required}]`. E-WORK-START requires `case_id` and `case_revision`. Measured against the approved drawers, that leaves a builder guessing in five places (PMO-0-1..5):
  - which case to start on, and where its revision comes from;
  - the type vocabulary for intake fields;
  - where the options for choice fields come from (project, completed milestone, issue, entity, scenario);
  - how a proof file links to the intake;
  - which line counts as "most-used", and when the main button opens the menu instead.
- As drawn, the feature is also too big for one reviewable PR. It covers 16 drawers, proof uploads (E-EVIDENCE-UPLOAD, which F-06 also needs), the restricted payroll drawer and money inputs. I propose splitting it into F-05 (core) and F-05b (proof and Finance drawers); see Scope.
- How to unblock: the architecture adds the start-intake contract as a proposal, the way v4 added D-TASK-DECISION-VIEW for F-04. Then the design engineer records an exception so the frontend can build against that proposal on the mock. After that, F-05 core can come back READY.
- Risk is high. This is the write that creates work and sets agents going. It is CSRF-bound and carries an idempotency key and a case revision. A duplicate or mis-scoped start is hard to undo, and the full scope includes restricted payroll intake and money fields.

## Findings
- PMO-0-1 | blocking | high | backend | E-WORK-START requires `case_id` and `case_revision` (model.json:3601-3632). No read endpoint returns a case revision: E-PROJECTS (model.json:4722-4748) and E-PROJECT (model.json:4884-4940) give `case_id` only. The Finance back-office drawers (accounts, schedules, ppe, forecast, bu, ledger, payroll) have no Project field at all, yet every backend `start()` takes a `case_id` (apps/workflows/factory_*.py). Expected: the contract says which case each line starts on and where the client reads its revision. One way is for E-LINES to return, per line, a case scope (`project` or a fixed studio case) and the revision. Actual: the builder would have to invent both.
- PMO-0-2 | blocking | high | backend | `intake[].type` is a free string with no defined vocabulary, and it carries no options, help text or placeholder (model.json:3444-3472). The approved drawers need choice lists drawn from records: Project, Completed milestone ("Only milestones marked complete, with proof, are listed"), Issue, From issue, Escalate to, Entity, Scenario, Kind. They also need dates and periods, numbers (Months, Control total) and files. The backend starts take record ids (e.g. `factory_ppe.start(... register_id, prior_id, ledger_id ...)`). Expected: a defined type set, plus an options source for each choice field, filtered by grants on the backend. Actual: the frontend would be authoring the contract in its fixtures. Taking project options from E-PROJECTS would also tie F-05 to F-07's mock handler.
- PMO-0-3 | blocking | medium | backend | Proof fields appear on minutes, change, accounts, schedules, ledger and ppe, and payroll has three restricted files. E-EVIDENCE-UPLOAD needs a `case_id` path parameter and is defined for responses (R-RESPONSE). Nothing says how an uploaded evidence id goes into `intake` (an open object, model.json:3616-3619), or whether a proof can be uploaded before the work exists. Expected: a contract statement covering both. F-06 (FE-M2B) owns the first use of E-EVIDENCE-UPLOAD.
- PMO-0-4 | non-blocking | medium | integration | Several board elements have no contract field:
  - the line subtitle on the chooser ("From a completed milestone");
  - the "WHAT HAPPENS NEXT" block (station count, agent, who decides);
  - which line is "most-used";
  - the CEO/CTO behaviour, where the main button opens the menu (CMP-23, D-LEADERS-START).

  The frontend must not derive any of these from `/me` roles. Expected: the same proposal adds them, or they are left out and listed for product acceptance.
- PMO-0-5 | non-blocking | medium | backend | `me.startable_lines` holds display titles (frontend/mock/fixtures/me.pm.json: "Weekly client update"), while E-LINES uses `key`. Expected: the button's visibility uses the same identifier as E-LINES, or simply whether E-LINES returns any items. The proposal should say which.
- PMO-0-6 | non-blocking | medium | integration | Parallel lanes share some files:
  - `frontend/mock/server.mjs` (`M1_OPERATIONS`, the dispatch chain, `PERSONAS`);
  - `me.*.json`;
  - the openapi repoint in server.mjs:22, package.json gen:api, schema.d.ts and the drift test.

  F-05 needs a CEO or CTO persona for D-LEADERS-START. Expected:
  - each lane puts its handler in its own module, as `work-list.mjs` does, and adds one line to `M1_OPERATIONS` and the dispatch;
  - F-05 adds `ceo` to `PERSONAS` and creates `me.ceo.json`;
  - only F-05 repoints the contract, and only if v6 changes E-LINES or E-WORK-START.

  The integration owner should expect small merges in server.mjs.

## Scope
**Outcome (one, observable, once PMO-0-1..3 are in the contract):** a person who may start work presses Start work in the top bar, or "+ Start" on the phone bar. They choose a line they may start, fill its intake in a drawer over the current page, and press start. They then land on the new work item at `/work/<work_id>`. A missing field shows the validation board. This works at 390px and 1440px on the contract mock, and A-START (frontend half) and A-ACCESSIBILITY pass.

**Proposed split (too big for one PR as drawn):**
1. **F-05, core (FE-M2A part 1):**
   - The CMP-23 split button in `TopNav.tsx` and `PhoneBar.tsx`. It is shown only when the person can start something (PMO-0-5). The leaders' behaviour follows D-LEADERS-START as the contract exposes it.
   - The "Choose a line" step from E-LINES: search, grouped list, "LINES YOU CAN START · n", the "Describe it to Tola" link to `/assistant`, the empty state, and loading and error states.
   - A generic drawer that renders `intake` by type (no file type here).
   - Submit to E-WORK-START with the CSRF header, a stable `idempotency_key` per drawer session, and `case_revision`. A double press or a retry after a network failure reuses the key and makes no second start.
   - Error handling: a 422 names its fields inline (validation board); a 409 reloads the case and keeps what was typed; a 403 or 404 goes through the F-01 `ApiError`.
   - On a 201, go to `/work/<work_id>` (F-03's route).
   - Drawers: invoice (default and validation), weekly, minutes without proof, issue, change without proof, incident, escalation and leadership.
2. **F-05b (FE-M2A part 2, after F-06 merges its E-EVIDENCE-UPLOAD handler and upload control):** proof fields, plus the Finance and payroll drawers (accounts, schedules, ppe, forecast, bu, ledger, payroll). Payroll is restricted (INV-RESTRICTED), and accounts carries a Control total money input (INV-UNKNOWN: an empty value is unknown, never 0).

**Out, for both:**
- SCR-23 (Log a received RFP).
- Assistant drafts that start work (FE-M4/T-ASSISTANT).
- Any backend or `apps/api` work (T-START).
- Edits to openapi.json by the frontend.
- The real API (FE-CONNECT-1).
- New npm dependencies.
- A visible SAMPLE DATA tag: per decisions-2026-11-14 (c) it shows only with `NEXT_PUBLIC_SHOW_SAMPLE_LABEL=1`, and the data stays `sample: true`.

**Ownership (disjoint from F-06, F-07 and F-08):**
- `frontend/src/features/start-work/**`. No new page route: the drawer opens over the current page, from a component that the shell mounts.
- `src/shell/**`: F-05 must add the button. The approved boards place CMP-23 in the top bar on every page and as "+ Start" on the phone bar. The edits are limited to mounting `features/start-work` in `TopNav.tsx` and `PhoneBar.tsx` and changing the assertion at `frontend/tests/shell.test.tsx:127` ("has no Start work…"). The other lanes do not touch these files.
- Mock: `frontend/mock/start-work.mjs` (E-LINES and E-WORK-START handlers, body validated against the request schema), `frontend/mock/fixtures/E-LINES.<persona>.json`, `me.ceo.json`, and the started work items from `frontend/mock/fixtures/work/W-1401.json` up. Plus one line each in server.mjs `M1_OPERATIONS`, the dispatch and `PERSONAS` (PMO-0-6).
- F-05 does not edit E-PROJECTS or E-EVIDENCE-UPLOAD handlers. Those belong to F-07 and F-06.

**Task IDs:** FE-M2A (R-START; D-LEADERS-START r1).
**Endpoints:** E-LINES and E-WORK-START (F-05); E-EVIDENCE-UPLOAD (F-05b).
**Acceptance:** A-START on the frontend side: a missing field returns 422, and a line without permission is absent. Plus A-ACCESSIBILITY.

## Risk
I rated it high:
- E-WORK-START is the write that creates a work item and sets agents going (JR-01). It carries CSRF, an idempotency key and a case revision (INV-REVISION). A duplicate start, or a start on the wrong case, is hard to undo.
- The full FE-M2A includes restricted payroll intake (INV-RESTRICTED), a money input that must never turn unknown into 0 (INV-UNKNOWN), and proof uploads (REC-EVIDENCE, append-only).

Surfaces:
- `ui`: SCR-04 and CMP-23 across both shell bars.
- `api`: the first E-WORK-START and E-LINES writes and reads.
- `security`: CSRF, never offering a line the API did not return, and payroll scope.
- `contract-change`: PMO-0-1..3 need a contract revision, which F-05 then consumes and may need to repoint to.

Excluded surfaces:
- `auth`: the feature uses the existing session.
- `dependency`: no packages are added.
- `payments`: no money moves at start.

## Notes
- Unblock path for the coordinator. The backend developer, as contract owner, drafts a start-intake proposal in architecture v6 covering PMO-0-1..3, and ideally PMO-0-4 and PMO-0-5. The design engineer records that the frontend may build against it on the mock, with the same limits as D-TASK-DECISION-VIEW: the shapes may change, it gates FE-CONNECT-1, and nothing is released. Then re-run readiness for F-05 core.
- I did not run `design.py check`; my role is read-only. SCR-04 boards live only in design/canvas/project; I found none in the Finance canvas folder.
- The mock still reads v4 openapi.json. E-LINES, E-WORK-START and E-EVIDENCE-UPLOAD are the same in v5, so no repoint is needed unless v6 changes them.

## Questions
None.
