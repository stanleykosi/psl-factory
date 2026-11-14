DECISION: NOT-READY
RISK: high
SURFACES: ui, api, security, contract-change, external-messaging
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
COMMIT: none (round 0, no head yet)
REVIEWER: readiness
AUTHORITY: PMO readiness (delivery step 1)

## Summary
- Most of the paperwork is in place. FE-M2B is in architecture v5 with no open gates (validation.json:130 `"FE-M2B": []`, delivery.md:1026). Its only dependency, FE-WORKITEM (F-03), is merged. The client approved SCR-10 and SCR-16 on 13 Nov 2026 (design/review.json, canvas 1794581312-b166).
- The contract cannot carry the response form yet. You can't upload proof from a work item: E-EVIDENCE-UPLOAD needs `case_id` and `case_revision`, and E-WORK-ITEM returns neither. E-WORK-ITEM also doesn't say which responses a task accepts, who may have responded, or which version is being answered. A builder would have to guess all of it. F-04 had the same problem in v3 and was rated NOT-READY until v4 added the missing fields.
- Reconcile has the same upload gap, plus one more: E-WORK-ITEM never says whether this person may resume, cancel or reconcile. The UI would show actions the API never granted.
- 8 of SCR-16's 13 states (the RFP outcome and RFP result boards) have no E-RESPONSE action. The enum has no won, lost, pending, unknown or lessons.
- Proposed split. **F-06A, All exceptions (SCR-10), is ready now** and low risk, and it is also the whole of FE-M2B that ready work items need. **F-06B, Record a response plus Reconcile**, waits for a small additive E-WORK-ITEM proposal from the backend developer. **F-06C, the RFP outcome variants**, is parked until the contract has an outcome action. Risk and surfaces above are for the whole of FE-M2B. F-06A alone is `low` and `ui, api`.

## Findings
- PMO-0-1 | blocking | high | backend | You can't upload proof from the work item. E-EVIDENCE-UPLOAD is `POST /api/v1/cases/{case_id}/evidence` and needs `case_revision` (model.json:3804, 3837-3846). E-WORK-ITEM's 200 schema has no `case_id` and no `case_revision` (model.json:2109-2668, `additionalProperties: false`). Both acceptance tests need an upload: A-RESPONSE ("Upload proof, record approved", model.json:8763) and A-RECONCILE ("Record delivered with evidence", model.json:8778). Expected fix: add optional `case_id` and `case_revision` to E-WORK-ITEM, or let E-RESPONSE and E-WORK-ACTION take the file directly. Either is a recorded proposal like D-TASK-DECISION-VIEW. Actual: the frontend would have to treat work_id as case_id, which is a guess.
- PMO-0-2 | blocking | high | backend | The SCR-16 form has nothing to fill it from. The board (design/canvas/project/SCR-16-desktop.dc.html:25-29) shows three things that come from the record:
  - a "Who responded" picker;
  - a "What they did" choice whose options change by variant (UAT: Approved, Asked for changes, Rejected; SOW: signed; team input: estimate or input);
  - a "For which version" picker.

  `tasks[]` has only `kind` (a free string), `title`, `required_role`, `you_can_act` and `revision` (model.json:2261-2532). Which E-RESPONSE `action` values a task accepts is a business rule. It must come from the API, not from the frontend. The same goes for the team-input board's given/missing teams and the "who is blocking review" sentence (screens.md change log, 12 Nov). Expected: an optional `tasks[].response` proposal with the allowed actions, the responders, the version label and the teams' status, plus a documented task `kind` for response tasks. Mock fixtures use `"kind": "decide"` only (frontend/mock/fixtures/work/W-12xx.json).
- PMO-0-3 | blocking | high | backend | Reconcile has no grant field. E-WORK-ACTION permission reads "Operator authority on the line; reconcile needs the line's recovery authority" (model.json:4253). E-WORK-ITEM carries no work-level allowed actions. The SCR-02 awaiting-reconciliation board offers "It arrived / It didn't arrive, allow one resend / I can't tell yet" with "Record and continue" (SCR-02-desktop-awaiting-reconciliation.dc.html:17). A not-delivered answer authorises one resend to the client. F-04 kept to a rule: never offer an action the API did not grant. Expected: an optional `allowed_actions` (resume, cancel, reconcile) on E-WORK-ITEM, in the same proposal as PMO-0-1.
- PMO-0-4 | blocking | medium | backend | The RFP outcome states have no contract. SCR-16 rfp-outcome, rfp-outcome-lost, -pending, -unknown, rfp-won, rfp-lost, rfp-pending and rfp-unknown (screens.md:39) record won, lost, pending or unknown, plus lessons. E-RESPONSE `action` is `approved | changes_requested | signed | rejected | estimate | input` (model.json:4042-4049). The backend has a separate `rfp.outcome` (architecture/sources/flow-audit.md:28). Expected: park these states as F-06C until the architecture adds an outcome action or endpoint. Do not build them by stretching `rejected` or `input` to mean something else.
- PMO-0-5 | non-blocking | medium | backend | The backend and the contract describe different response flows. `provide_information` needs the task to be of kind `factory_information`, claimed by the actor, and the evidence kind to be in `context['missing']`. It also takes a `case_revision` (apps/workflows/factory.py:865-875). E-RESPONSE describes no claim step and has a different action vocabulary. This is for T-RESPONSE, not the frontend, but the PMO-0-2 proposal should say whether the frontend calls E-TASK-CLAIM first.
- PMO-0-6 | non-blocking | low | integration | SCR-10 shows a few things E-EXCEPTIONS can't supply: the reference under each title, a search box, a Filter button and the "4 OPEN" count (SCR-10-desktop.dc.html:30, 44). E-EXCEPTIONS rows are `work_id, what, title, doing, who_acts, since` with `cursor`/`limit` only (model.json:4481-4568). Expected in F-06A: omit them, invent nothing, list them in build.md for product acceptance. Show the count only as the number of rows loaded ("N shown"), never as a total.

## Scope
**Binding for the spec writer: F-06A only, until PMO-0-1 to PMO-0-3 are closed by an architecture revision or a recorded exception.**

**Outcome (F-06A, one, observable):** a Lead opens `/exceptions` and sees every exception they are allowed to see. Each row shows the kind, how long it has waited (`since`), the work title linked to `/work/<work_id>`, what is being done and who acts. The person can choose 10, 20 or 50 rows per page and "Show more", and sees "As of <as_of WAT>". This works at 390px and 1440px on the contract mock.

**In (F-06A):**
1. Route `frontend/src/app/exceptions/page.tsx`. Components go in `frontend/src/features/exceptions/**`. Export the list component so F-08's Overview can embed it or link to it.
2. E-EXCEPTIONS read with `limit` (10, 20 or 50; default 20) and `cursor`. Rows appear in the order returned. Kind tags: effect_uncertain is amber "Send uncertain"; owner_needed, setup_needed, blocked and followup_needed are orange or red, as on the board. The footer sentence is "The factory never resends...". Times are in Africa/Lagos.
3. Board states plus the shared patterns: default, empty (SCR-10 empty), loading, error with Try again, 401 through `SignedOutState`, and 403 (non-Leads) as a no-access view. No action buttons anywhere on the list.
4. Link from the work item page. In `frontend/src/features/work-item/WorkItemOverview.tsx` (`NextStep`, line 164), add one link, "See all exceptions" → `/exceptions`, shown only for effect_uncertain, awaiting_reconciliation, owner_needed, setup_needed and followup_needed. That is the only F-03 edit allowed: an import and a few lines, listed in build.md. F-03's spec already names this link target as FE-M2's (F-03/spec.md:250).
5. Mock: an E-EXCEPTIONS handler in `frontend/mock/server.mjs`, added beside the F-03/F-04 handlers. Fixtures in `frontend/mock/fixtures/exceptions/` are paged by `limit`/`cursor` the same way as F-03's history. They cover at least 25 rows, so the 20-row page shows "Show more", plus one empty scenario. All `sample: true` where the schema allows, and schema-valid. Each `work_id` points to an existing per-id work fixture (W-1005 for effect_uncertain) or to new fixtures from **W-1501 up** for owner_needed, setup_needed, blocked and followup_needed.
6. Tests: component tests for the kind mapping, the order, paging requests, empty, 403 and 401; mock-contract tests, appended only; Playwright plus axe at 390px and 1440px for default and empty.

**Out (F-06A):** Record a response (SCR-16), reconcile, resume and cancel (E-WORK-ACTION), evidence upload. Search, filter, reference and total count (PMO-0-6). Overview page composition (F-08). Any top-bar highlight for /exceptions (a shell change). New npm dependencies. Any edit to openapi.json, `src/api/**` or `src/shell/**`. The mock stays on v4: v5 changed only tasks (impact.json `configuration_changed: false`).

**F-06B, Record a response and reconcile (after the architecture revision):** route `frontend/src/app/work/[id]/respond/**` (`?task=<id>`) and `frontend/src/features/response/**`. Covered states: SCR-16 default, validation, success, sow-signed and team-input. A reconcile panel lives in `frontend/src/features/exceptions/ReconcilePanel.tsx` and is mounted by one conditional line in F-03's `WorkItemOverview` for awaiting_reconciliation. In `TaskPanels` (WorkItemOverview.tsx:147-162), one branch sends response-kind tasks to `/respond` with their own wording instead of "Open the decision". Handlers: E-EVIDENCE-UPLOAD, E-RESPONSE (422 without proof or attestation, 409 on revision) and E-WORK-ACTION. Fixtures from W-1501 up continue after F-06A's. Acceptance tests are A-RESPONSE and A-RECONCILE (frontend half).

**F-06C (parked):** the eight RFP outcome and result states (PMO-0-4).

**Ownership (all of F-06):**
- Owns `frontend/src/app/exceptions/**`, `frontend/src/app/work/[id]/respond/**`, `frontend/src/features/exceptions/**`, `frontend/src/features/response/**` and `frontend/mock/fixtures/exceptions/**`.
- Also owns `frontend/mock/fixtures/work/W-15xx*.json`, `frontend/tests/exceptions*.test.ts(x)`, `frontend/tests/response*.test.ts(x)`, `frontend/e2e/exceptions.spec.ts` and `frontend/e2e/response.spec.ts`.
- Shared files, additive only: `frontend/mock/server.mjs` (only its own handlers) and `frontend/tests/mock-contract.test.ts` (appended tests).
- Does not touch: F-05's Start work files, F-07's projects files, F-08's overview, floor and reports files, `decide/**`, `my-work/**`, `src/shell/**`, `src/api/**` or `architecture/**`.

**Task IDs:** FE-M2B (R-EXCEPTION for F-06A; R-RESPONSE for F-06B). **Endpoints:** E-EXCEPTIONS for F-06A; E-RESPONSE, E-EVIDENCE-UPLOAD and E-WORK-ACTION for F-06B, all on the contract mock. **Acceptance:** A-ACCESSIBILITY for F-06A. A-RESUME is mapped to E-EXCEPTIONS but belongs to backend T-EXCEPTIONS. A-RESPONSE and A-RECONCILE apply to F-06B.

## Risk
Taken as a whole, FE-M2B is high risk. Recording a response stores sworn proof: the staff member confirms an outside party's approval or SOW signature, and the record "can't be edited later" (SCR-16-desktop.dc.html:37-40, INV-AUDIT, REC-EVIDENCE). Reconcile chooses between "it arrived" and "allow one resend" to a client after an uncertain send (E-WORK-ACTION, INV-RESEND, model.json:4229-4253). Both are hard to undo. So the surfaces are:
- `security`: attestation, CSRF on three writes, and the missing grant (PMO-0-3);
- `external-messaging`: the resend;
- `contract-change`: PMO-0-1 to PMO-0-3 change E-WORK-ITEM.

`payments` is excluded because the short-payment verdicts stay parked under D-DECISION-VARIANTS and nothing here moves money. F-06A alone is low risk: it is a read-only, grant-filtered list with no writes.

## Notes
- Product acceptance is required. The design engineer should see the omitted SCR-10 elements (PMO-0-6) and, for F-06B, the attestation and reconcile copy.
- Per sources/decisions-2026-11-14.md (c), no SAMPLE DATA tag is shown unless NEXT_PUBLIC_SHOW_SAMPLE_LABEL=1. Per the 13 Nov decisions, the PM records the Engineering Lead's and Support's part with proof, because they don't log in. F-06B's responder list must come from the API, not from a hard-coded role list.
- If the design engineer records an explicit exception to build F-06B against a frontend-drafted proposal on the mock (as with F-04 and D-TASK-DECISION-VIEW), re-run readiness with that exception and its limits. Without it, F-06B stays NOT-READY.
- I did not run `design.py check`, because my role is read-only.

## Questions
None. The gaps are contract work for the backend developer, not client decisions.
