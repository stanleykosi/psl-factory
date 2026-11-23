DECISION: READY
RISK: high
SURFACES: ui, api, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Re-run under the Lane D rule. The earlier NOT-READY rested only on F-85 being unmerged. That is now a build-start wait, not a blocker.
- Build start waits for F-85 (PR #101) on main. The coordinator holds the builder until then. The spec is written against `/Users/Hunchoo/psl-factory-main/delivery/features/F-85/spec.md`.
- Outcome: SCR-49 closure, about 10 boards, one checklist read and four writes. API 1.24.0 supplies all the data, and backend answers D-1, D-25, D-26 and D-27 settle the open questions. No client question is needed.
- Architecture and design approval are covered by the v9 package and the 13 Nov client design approval, with the D-173/D-181 exceptions in `design/review.json`. The spec writer should run `design.py check` and confirm the F-40 boards are at their latest revision.
- High risk: the feature closes a project and records Finance confirmation. The merge goes to the design engineer's merge batch.

## Scope
Outcome: closure reads the live closure checklist, Finance confirms milestone notifications, and the closure decision and return are recorded live. Task FE-CONNECT-1, screen SCR-49 (F-40 boards). This section binds the spec writer. DC-1 to DC-5 (ids and tokens, adapter, agent cards, proof path, who can act) also bind.

In:
- `GET /projects/{case}/delivery/{dossier}/closure-checklist` with `report_evidence_id` and `retrospective_id`. This gives the checks context, go_live, hypercare, archive, handover, retrospective, finance and report, plus `recorded_closure_id`. The two extra checks (current scope, PM closure report) are shown.
- Close or return: `POST /work/{id}/reviews` with `kind:"closure"`. It takes `version_id` for the closure document version and `evidence_id` for the eligible decision evidence (D-26). It needs both `expected_revision` and `case_revision`. There is no separate claim.
- Replace the report: `POST /work/{id}/closure-report`.
- Correct sources: `POST /work/{id}/corrections`.
- Finance confirmation: `GET` and `POST /projects/{case}/delivery/{dossier}/finance-confirmation` (D-25, section 12 of backend-answers-2026-11-23.md, switched on by D-185). It records the reviewed milestone-receipt set, completeness, evidence and note. It is shown and enabled only with current Finance authority. This is "milestone notifications confirmed", not "debts confirmed".
- The "still open after closure" list comes from the protected debt figures on the closure read (D-27). It shows the Finance observation date and the unknown coverage. Unknown stays unknown, never 0. The list is hidden when the viewer cannot read Finance data.
- Start the line with `GET /projects/{case}/intake-sources` and `POST /work` (`delivery-closure/v1`). Evidence comes from the owning operations (D-1), not from a generic upload.
- State coverage: the blocked, ready, awaiting Head of PMO, returned and closed boards, wherever 1.24.0 supplies the data.
- The line adapter mapping lives in this feature folder, built on F-85's frame.

Out (hide the part and say so, per the D-182 rule):
- Tola step cards and notes (DC-3).
- The "blocked before the line starts" state, unless `ready_to_prepare` maps to it. Flag that mapping in the spec.
- Any lifecycle claim that the project is read-only. Show only the closure record.
- SCR-33 retrospective authoring (F-119), and SCR-45, SCR-46 and SCR-47 (F-114, F-115, F-116). They are only read through the checklist.
- Any change to `frontend/src/features/workspace`. If one is needed, name it as a dependency on lane C.

Do not invent business rules, approvers, attempt counts or amounts.

## Risk
High. Closing a project is hard to undo. Finance confirmation is a data-affecting write gated on Finance authority, and the debt figures are protected (D-25 to D-27). Two role gates (Head of PMO and Finance), two revision tokens and a recorded evidence proof raise concurrency and authority risk. The screen changes a flow and adds new copy, so the client must see it.
