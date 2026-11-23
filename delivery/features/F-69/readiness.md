DECISION: READY
RISK: high
SURFACES: ui, api, auth, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none

REVIEWER: readiness

## Summary
- F-69 is now SCR-50 Emergency change only: 5 boards (record, refused, review, retro, report). That fits one PR, so the size blocker in readiness-r0-not-ready.md is cleared.
- SCR-50 is client-approved in design/review.json. Backend answers D-28 to D-30 settle the contract questions.
- F-85 (work item page, shared line adapter, evidence picker) is on main as e2f44656, PR #101. Other feature records cite that sha.
- I did not run `design.py check` or re-read the task rows in this pass. I relied on the r0 review, which found the gates met. The spec writer should confirm both.
- SCR-51 Escalation is excluded and gets its own feature.

## Scope
Binding for the spec writer. Task FE-EMERGENCY-ESCALATION, part 1, frontend only, on F-85's shared work item page and line adapter. Do not add a new workspace frame.

In:
- Reads `GET /work/{id}/emergency`: `stage`, `critical_production`, `p1`, `options[]`, `decisions[]`, `recorded_authorizations[]`, `recorded_outcomes[]`, `outcome_impact`.
- `outcome_impact.customers_affected` is a non-negative number or null, and `side_effects` is text or null. Null shows as "unknown", never zero (D-29).
- Authoriser and recorder names and times come from the decision and outcome history (D-30).
- Writes `POST /work/{id}/emergency` actions: `authorize`, `capture_outcome` (`implemented_at` required), `record_review`, `retrospective_decision` (its return action covers "return"), `reconcile_retrospective`.
- Report board: `POST /work/{id}/reviews`, plus `GET/POST .../emergency-outcomes/{id}/followups` for the follow-up change list.
- The refused board renders from the recorded `reject` verdict.

Out:
- "Return with a note" on `record_review` does not exist (D-28). Do not invent it. Use the retrospective return action for the retro and the document review verdict for the report.
- The CTO pre-authorisation decision control stays in FE-DECIDE-VARIANTS.
- The emergency-intake start flow and authority recovery (`/projects/{case}/emergency-intake`, `/authority-recoveries`), unless the existing Start work drawer already covers them.
- All of SCR-51.

Role gates come from the server (`options[]`). The UI must not name approvers or grant authority. Show receipts or outcomes only when the read supplies them. A job claim is not a verified output.

## Risk
High because the line records authorisations and outcomes for emergency production changes. Showing null customers affected as zero, or misreading reject as return, would misstate a business record. Surfaces: ui, api and contract-change for the new reads and commands; auth for the role-gated decisions; product-decision because the flow is new to the client. Sources: architecture/packages/v9/tasks.csv and delivery/connect/screens-d-delivery-issues-escalation.md.
