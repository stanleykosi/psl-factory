DECISION: READY
RISK: high
SURFACES: ui, api, payments, security, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
COMMIT: none (round 0, no head yet)
REVIEWER: readiness
AUTHORITY: PMO readiness (delivery step 1)

## Summary
- FE-M3-FINANCE as briefed is too big for one PR. It covers 4 screen families and 155 boards on the Finance canvas: SCR-36 (2 boards), SCR-09/18/37 (10), SCR-59 (18) and SCR-53..58 (24+14+14+14+14+12). It also mixes a read page, restricted payroll and seven Finance line screens that have no endpoints of their own. Below I propose a split into nine features.
- **F-10 becomes the first slice: the Month-end checklist (SCR-36), desktop and phone, read from E-MONTH-END on the contract mock. It is READY.**
  - FE-M3-FINANCE depends only on T-FRONTEND-SHELL, which is merged, and validation.json lists `"FE-M3-FINANCE": []`.
  - The client approved SCR-36 on 13 Nov (design/review.json, Finance canvas 1794579902-95a3).
  - The scope gate runs under the recorded early-start exception (manifest.json scope_gate), the same basis as F-01 to F-08.
  - D-API-STYLE and D-AUTH are approved at r2.
- Risk is high:
  - The page shows money ("Cash received ₦4.7M + Unknown"), and Unknown must never show as 0 (INV-UNKNOWN, A-MONTHEND).
  - It shows a restricted payroll row that must never link (INV-RESTRICTED).
  - Most of the board has no contract field, so it is built on a frontend-drafted contract proposal.
  - Under OVERNIGHT-DECISIONS.md it is built and reviewed but not merged until the design engineer checks it.
- Product acceptance is required. The proposal fields, and four navigation interpretations where the board is wrong or silent (PMO-0-3 to PMO-0-5), must be seen by the design engineer.

## Findings
- PMO-0-1 | non-blocking | high | integration | E-MONTH-END (endpoints.csv:19) returns only `period`, `tasks[{line, state, where, work_id?}]` and `cash_received{amount?, currency, unknown}`. Its `additionalProperties` is false, and "amount: absent when unknown". So the contract cannot express the board or A-MONTHEND's "known amount plus Unknown". Per the 14 Nov standing rule, F-10 builds the missing elements from a frontend contract proposal on the mock and lists the fields for the architecture (the backend developer owns them). Proposed fields, all composed by the backend, none derived in the browser:
  - `as_of`: "FROM RECORDS YOU CAN SEE · UPDATED 10:42"
  - `summary{done, waiting, in_progress, total}`: the four-cell strip "2 of 7 / 3 / 2". The frontend must not bucket the 11 states itself.
  - `cash_received` that can carry a known part and an unknown part, e.g. `{known:{amount,currency}, has_unknown:true}`
  - per task: `title` ("Bank statements"), `detail` ("Access Bank statement missing"), `status_label` ("NEEDS FINANCE DECISION", "WAITING ON HR"), and `restricted:true` with `restricted_label` ("HR only"), where `work_id` is absent
  - `agent_note{agent:"chidi", text}`
  - `next_action{label, work_id}`: "Import the missing statement"
- PMO-0-2 | non-blocking | medium | product | The standing rule ("missing API data uses mock data from a contract proposal") is in the coordinator's brief. It is not yet recorded in the project, unlike D-TASK-DECISION-VIEW for F-04. Expected: the coordinator records it in OVERNIGHT-DECISIONS.md or BUILD-DECISIONS.md with its limits: mock only, the shapes may change, it gates FE-CONNECT-1 and the real API, and nothing is released.
- PMO-0-3 | non-blocking | medium | product | Both SCR-36 boards link "Import the missing statement" to SCR-09. Since 13 Nov, SCR-09 is the restricted HR payroll-inputs board ("COORDINATE RESTRICTED PAYROLL / PAY-0010 · STATION 1 OF 9"), which a Finance Lead cannot open. The bank-statement row's "Open" also points to SCR-09. Binding interpretation for this feature: the CTA and that row's Open go to `/work/{work_id}` (the backend's `next_action.work_id` and the row's `work_id`). The work item is where the missing import is asked for. Record this for product acceptance and for the design engineer to fix the board links.
- PMO-0-4 | non-blocking | medium | product | There is no Finance destination. `/me` destinations are only my_work, projects, overview, assistant and setup, and the SCR-36 top bar has no Finance tab. The phone board's "← Finance" has no target. The only drawn entries are SCR-53-verified ("Open month-end") and the Overview "Month-end" line (SCR-06, F-08). Binding: the route is `/finance/month-end?period=YYYY-MM`. "← Finance" uses browser back, with My work as the fallback. A missing or invalid `period` shows the shared not-found state (STATES board). The frontend never picks a default month, because "which month is being closed" is a business rule. Follow-ups: the Overview link (F-08 follow-up) and the SCR-53 link (F-10 split).
- PMO-0-5 | non-blocking | low | product | The phone board shows 6 cards under "2 of 7 done". It has no Payroll card, no cash-received cell and no Chidi note, while the desktop has all three. The fidelity gate scores each board as drawn, so build each breakpoint exactly as drawn and flag the difference for product acceptance. Do not add the missing elements to the phone, and do not drop them from the desktop.
- PMO-0-6 | non-blocking | medium | integration | `frontend/mock/server.mjs:24` (M1_OPERATIONS) and the dispatch block at :226-234 are edited by F-02 and F-05 to F-08. Expected: the handlers go in a new `frontend/mock/finance.mjs`. The server.mjs change is limited to appending `'E-MONTH-END'` and one dispatch line. Rebase on whichever lane merges first. The mock loads the v4 contract (server.mjs:22). Confirm that E-MONTH-END is unchanged in v6, and do not repoint the mock (F-05 owns that).
- PMO-0-7 | non-blocking | low | integration | I cannot run `design.py check` (no shell). The coordinator confirms that it passes for the main canvas 1794581312-b166 and the Finance canvas 1794579902-95a3 before the spec is written.

## Scope
**Outcome (one, observable):** a Finance Lead opens Month-end for October 2026 and sees:
- the as-of line;
- the four-cell strip (done of total, waiting, in progress, and cash received as the known amount "+ Unknown", never 0);
- every month-end task the backend returns, each with its detail, where it is and its state tag;
- Open links to each task's work item, and "HR only" with no link on the restricted payroll row;
- Chidi's note, and the "Import the missing statement" action.

This works at 1440px and at 390px on the contract mock. A-MONTHEND's read half and A-ACCESSIBILITY pass.

**Boards in scope (the spec; every element on each):**
- `design/canvas/finance/project/SCR-36-desktop.dc.html`
- `design/canvas/finance/project/SCR-36-mobile.dc.html`

The fidelity gate is 100% of board elements and visual >= 90 on both. The two approved deviations are PMO-0-3 (link targets) and PMO-0-4 (back link). The board's static nav links and the Chidi `/_blob/` image are replaced by the app frame and the existing agent avatar.

**In:**
1. The route `src/app/finance/month-end/page.tsx`, with `period` from the query (PMO-0-4). It renders inside the existing AppShell. It uses the existing loading, empty, error, 401, 403 and 404 frame states.
2. `src/features/finance/month-end/**`: the data hook (generated client, `GET /api/v1/finance/month-end?period=`), the strip, the desktop table, the phone cards, the agent note and the action.
   - Money is shown only from the returned amount object, in the board's compact form (₦4.7M). The full value goes in the accessible name.
   - `unknown` or `has_unknown` renders the word "Unknown", never 0 and never blank.
   - State tags use the tone from the existing `STATE_TAGS` (`src/features/work-item/labels.ts`, import only) and the backend's `status_label` text.
   - Restricted rows show `restricted_label` and no link, whatever the person's role. The frontend never decides restriction from the line name or the role.
3. A proposal type `src/features/finance/month-end/proposal.ts` for the PMO-0-1 fields, documented in build.md as the field list for the architecture.
4. Mock: `frontend/mock/finance.mjs` and `frontend/mock/fixtures/finance/month-end.2026-10.json`, plus variants for all-known cash, cash fully unknown, a restricted row, and a period with no tasks. All are `sample: true`. The fixtures validate against the v4 contract once the proposal keys are stripped. A contract test proves both the strip and the validation.
5. Tests in F-10's own files:
   - `frontend/tests/finance-month-end*.test.ts(x)`: the Unknown-never-0 cases, no link on restricted rows, the summary taken as returned, and the period handling.
   - `frontend/e2e/finance-month-end*.spec.ts`: Playwright and axe at 390px and 1440px.

**Out (proposed split; each is its own feature with its own readiness check):**
- **F-10B Payroll import and match (restricted)**, SCR-09 and SCR-18. Boards: `SCR-09-desktop`, `SCR-09-mobile`, `SCR-09-desktop-error`, `SCR-09-mobile-error`, `SCR-18-desktop`, `SCR-18-mobile`, `SCR-18-desktop-permission`, `SCR-18-mobile-permission`.
  - Endpoints: E-PAYROLL-MATCH, plus a read for the payroll import result. E-IMPORT is a bank or accounting POST that returns only `receipt` and `findings[]`.
  - It needs an HR Lead mock persona, which means a shared change to `me.*.json` and PERSONAS.
  - The Finance permission board shows BU totals that E-PAYROLL-MATCH (403 for Finance) does not return.
  - The SCR-09 vs E-IMPORT mismatch must be settled first.
  - Risk high. Surfaces: ui, api, security, auth, data and contract-change.
- **F-10C Payroll corrections (restricted)**, SCR-37. Boards: `SCR-37-desktop`, `SCR-37-mobile`. The HR Lead decision (`payroll.hr_correction`) has no endpoint, so it is NOT-READY until the architecture adds the read and the decision, or an exception for a write proposal is recorded. Risk high.
- **F-10D Payroll run**, SCR-59, 18 boards (`SCR-59-{desktop,mobile}-{input-review, combine-review, match-held, match-review, totals-review, publish, receipts, verified, followup}`). Restricted, with receipts and follow-up. Risk high.
- **F-10E Management accounts**, SCR-53, 24 boards, split in two:
  - E1, intake and investigation: `quarantined`, `units`, `investigating`, `owner-needed`, `setup-needed`, `returned`;
  - E2, reviews and publication: `reviews`, `drafting`, `publishing`, `uncertain`, `verified`.

  `uncertain` depends on the reconcile work (the later F-06B). E2 adds the "Open month-end" link here.
- **F-10F Income schedules**, SCR-54, 14 boards: investigating, held, review, returned, verified, export, withdrawn.
- **F-10G Fixed asset schedule**, SCR-55, 14 boards: investigating, register-review, date-review, calculating, schedule-review, returned, verified.
- **F-10H Cash forecast**, SCR-56, 14 boards: investigating, review, group-rows, group-review, uncertain, verified, actuals.
- **F-10I BU totals**, SCR-57, 14 boards (source-review, investigating, held, result-review, publish, receipts, verified), and **F-10J Ledger source**, SCR-58, 12 boards (investigating, duplicate, observe, review, rejected, verified).

Notes on the split:
- The SCR-53 to SCR-59 features are line screens shown on the work item (`/work/{id}`). Each needs a typed line-detail block on E-WORK-ITEM from the architecture, or an exception. Each needs one agreed mount point in `src/features/work-item/**`, which is F-03's code.
- All of them carry money, reviews and publication, so they are risk high.
- Their start drawers (SCR-04 Finance forms) are FE-M2A-PROOF, not F-10.
- SCR-02, -03, -20 and -32 on the Finance canvas belong to other features.

Also out of F-10: E-IMPORT (POST), any openapi.json edit, the v4 to v6 mock repoint, nav or `/me` destination changes, backend work (T-FINANCE, T-PAYROLL), and new npm dependencies.

**Ownership (disjoint from F-02 and F-05 to F-08):**
- `frontend/src/app/finance/**`
- `frontend/src/features/finance/**`
- `frontend/mock/finance.mjs`
- `frontend/mock/fixtures/finance/**`
- `frontend/tests/finance*.test.ts(x)`
- `frontend/e2e/finance*.spec.ts`

The only shared touch is the server.mjs registration (PMO-0-6). Imports from `src/features/work-item/labels.ts` and `src/features/decide/format.ts` are read-only. No edits to `src/shell/**`, `src/api/**`, `src/features/{work-item,decide,my-work,exceptions,overview,projects,start}/**`, `frontend/mock/fixtures/me.*.json` or other lanes' fixtures. List every touched path in build.md.

**Task IDs:** FE-M3-FINANCE (R-FINANCE), first part. **Endpoints:** E-MONTH-END (read, contract mock). **Acceptance:** A-MONTHEND read half ("Cash received shows known amount plus Unknown"), and A-ACCESSIBILITY. The import-quarantine half of A-MONTHEND goes with E-IMPORT in F-10E1. A-PAYROLL goes with F-10B.

## Risk
I rated it high:
- The page shows a cash total. A-MONTHEND and INV-UNKNOWN (handoff.md:789-807) make a 0 or blank in place of Unknown a money error.
- The current contract cannot carry "known plus Unknown" (endpoints.csv:19), so the money shape is a frontend proposal (`contract-change`).
- It also lists restricted payroll work. INV-RESTRICTED (handoff.md:871-889) and JR-06 require that the row never links or exposes payroll detail, so `security` reviews that the frontend renders only what is returned.

Surfaces:
- `ui`: SCR-36 on desktop and phone.
- `api`: the first read of E-MONTH-END.
- `payments`: cash received.
- `security`: the restricted row.
- `contract-change`: the consumer side of the PMO-0-1 proposal.

There is no `auth` (no sign-in or role logic) and no `data-migration`. There is no `product-decision`, because the interpretations in PMO-0-3 to PMO-0-5 go to product acceptance rather than deciding a business rule.

## Questions
None. The design engineer should still fix the SCR-36 links (PMO-0-3) and say where the Finance back link and the month-end entry point go (PMO-0-4). Neither blocks this slice.
