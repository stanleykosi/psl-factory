DECISION: READY
RISK: medium
SURFACES: ui, api
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- READY: SCR-53 intake and investigation boards (quarantined, units, investigating, owner-needed, setup-needed, returned) on live API 1.24.0, one reviewable PR. F-106 owns review and publish.
- Waits on F-85 (lane C, PR #101) for the shared line adapter. This delays the build start only. Write the spec against `/Users/Hunchoo/psl-factory-main/delivery/features/F-85/spec.md`.
- Backend answers E-19 and E-20 settle the open questions. Architecture and design approval come from the v9 package and the 13 Nov client approval with the D-173/D-181 exceptions (lane D context). No decision blocks this feature.
- Money is not moved and nothing is posted to the ledger. Writes are evidence-backed intake and a unit confirmation on a quarantined file.
- New flow for the client, so product acceptance is required.

## Scope
Outcome: a person uploads a management-accounts extract, sees it quarantined with its findings, confirms units, and watches the investigation. They see the owner-needed, setup-needed and returned holds.

In:
- Task FE-FIN-ACCOUNTS-INTAKE.
- `POST /work` (`finance-accounts/v1`).
- `GET/POST /projects/{case_id}/accounting-intake`: `case_revision`, `idempotency_key`, `reference`, `evidence_id`, and `context{entity, period, currency, accounting_basis, extracted_at, completeness, control_total, source_evidence_id}`. A null control total means unknown and is never shown as 0.
- `POST .../accounting-intake/{receipt_id}` (confirm units: major, thousands or millions_currency, with `evidence_id` and `note`).
- `GET .../accounting-mappings/{mapping_id}` for rows, `has_more_rows`, `ledger_posted`, `unit`, `status` and `findings` (`?after_row`). Show `ledger_posted` always.
- `GET /work/{id}/accounting` and `POST .../accounting/corrected-extract` (multipart) for the returned state.
- `POST /work/{id}/accounting` with `recheck_reviewers` and `reassess`, only where `can_recheck_reviewers` and `can_reassess` allow it.
- Display: `state`, `next_action`, `finding`, `calculated_at`, `setup_missing[]`, and `predecessor_id`/`successor_id`/`correction` for earlier versions.
- `findings` and `finding_details` render by stable code with the original message and line or field where known (E-20). Legacy unclassified messages stay readable as text.

Out:
- Review stations, claim and decision, publish, delivery jobs, reconcile and recovery. These belong to F-106.
- Changes to the shared frame in `frontend/src/features/workspace`. If one is needed, name it as a dependency on lane C.

Hide, per the D-182 rule, and say so in the spec:
- The "Row 88: period is 2026-09" table (only finding strings exist).
- The "3 accounts new since September" detail.
- Reviewer names and the reason nobody can review, for the owner-needed board.

Never invent amounts, approvers or counts. Unknown money stays unknown.

## Risk
Medium. It adds an evidence upload and a units confirmation that changes how a finance extract is read, across several states and a cross-layer contract (`frontend/` against the contract in `contracts/psl-factory.openapi.json`). It posts nothing, moves no money, and shows no restricted payroll data or external messages. Writes carry `case_revision` and an idempotency key. Merge route: the F-105 PR can merge under D-180/D-184 once its reviews pass. F-106 carries the publish risk.
