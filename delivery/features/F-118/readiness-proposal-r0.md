DECISION: NOT-READY
RISK: high
SURFACES: ui, api, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- The outcome is clear and fits one PR: SCR-49 closure, about 10 boards, one checklist read and four writes, all supplied by API 1.24.0.
- It is blocked on a dependency: the shared line adapter F-85 (PR #101, state IMPLEMENTING, not merged). Lane D must not change the shared frame.
- Backend answers D-1, D-25, D-26 and D-27 settle the open questions, so no client question is needed. Start once F-85 is on main.
- It moves a project to Closed and records Finance confirmation, so the decision is high risk and its merge goes to the design engineer's batch.
- The project folder has no spec, design review or architecture approval evidence for this feature yet. feature.json shows no approvals, no operation IDs and no acceptance criteria. The spec writer must fill these in.

## Scope
Outcome: closure reads the live closure checklist, Finance confirms milestone notifications, and the closure decision and return are recorded live. Task FE-CONNECT-1, screen SCR-49 (F-40 boards).

In, with DC-1 to DC-5 (ids and tokens, adapter, agent cards, proof path, who can act) as binding:
- `GET /projects/{case}/delivery/{dossier}/closure-checklist` with `report_evidence_id` and `retrospective_id`. This gives the checks context, go_live, hypercare, archive, handover, retrospective, finance and report, plus `recorded_closure_id`. The two extra checks (current scope, PM closure report) are shown.
- Close or return: `POST /work/{id}/reviews` with `kind:"closure"`. It takes `version_id` for the closure document version and `evidence_id` for the eligible decision evidence (D-26). It needs both `expected_revision` and `case_revision`. There is no separate claim.
- Replace the report: `POST /work/{id}/closure-report`.
- Correct sources: `POST /work/{id}/corrections`.
- Finance confirmation: `GET` and `POST /projects/{case}/delivery/{dossier}/finance-confirmation` (D-25, section 12 of backend-answers-2026-11-23.md). It records the reviewed milestone-receipt set, completeness, evidence and note. It is shown and enabled only with current Finance authority. This is "milestone notifications confirmed", not "debts confirmed".
- The "still open after closure" list comes from the protected debt figures on the closure read (D-27). It shows the Finance observation date and the unknown coverage. Unknown stays unknown, never 0, and the list is hidden when the viewer cannot read Finance data.
- Start the line with `GET /projects/{case}/intake-sources` and `POST /work` (`delivery-closure/v1`). Evidence comes from the owning operations (D-1), not from a generic upload.
- State coverage: the blocked, ready, awaiting Head of PMO, returned and closed boards, wherever 1.24.0 supplies the data.

Out:
- Tola step cards and notes (DC-3). Hide them and say so.
- The "blocked before the line starts" state, unless `ready_to_prepare` maps to it. Flag that mapping.
- Any lifecycle claim that the project is read-only. Show only the closure record.
- SCR-33 retrospective authoring (F-119), SCR-45, SCR-46 and SCR-47 (F-114, F-115, F-116). They are only read through the checklist.
- Any change to `frontend/src/features/workspace`. If one is needed, name it as a dependency on lane C.

Dependency: F-85 merged to main. Re-check readiness, or proceed, once it lands. Confirm the F-40 boards are approved at their latest revision, and run `design.py check`.

## Risk
High. Closing a project is hard to undo. Finance confirmation is a data-affecting write gated on Finance authority, and the debt figures are protected (D-25 to D-27, section 12 of backend-answers-2026-11-23.md). Two role gates (Head of PMO and Finance), two revision tokens and a recorded evidence proof raise concurrency and authority risk. The screen changes a flow and adds new copy, so the client must see it.
