DECISION: NOT-READY
RISK: high
SURFACES: ui, api, auth, contract-change, external-messaging, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none

REVIEWER: readiness

## Summary
- The design (SCR-50 and SCR-51) is client-approved in design/review.json, and the backend answers D-28 to D-32 settle the open contract questions. The gates are met.
- Size is the blocker. FE-EMERGENCY-ESCALATION is 11 boards: SCR-50 has 5 (record, refused, review, retro, report) and SCR-51 has 6 (investigating, decide, not-escalated, draft, review, received). That is over the ~8-board limit for one PR.
- Both lines add their own read and command shapes (`/work/{id}/emergency` and `/work/{id}/escalation`) on F-85's shared work-item page and line adapter, so one PR would be too much to review.
- Proposed split: F-69a is SCR-50 (5 boards) and F-69b is SCR-51 (6 boards). Each is READY on its own once it has its own feature.
- I did not check F-85's merge state (e2f44656 / PR #101) in git. Confirm it is on main before F-69a starts.

## Scope
Binding for the spec writer of each half. Task FE-EMERGENCY-ESCALATION, Frontend only. The CTO emergency pre-authorisation decision stays in FE-DECIDE-VARIANTS (per the task title), so F-69a renders the refused board from the recorded `reject` verdict and does not build the CTO's decision control.

**F-69a, SCR-50 Emergency change (5 boards).**
- Reads `GET /work/{id}/emergency`: `stage`, `critical_production`, `p1`, `options[]`, `decisions[]`, `recorded_authorizations[]`, `recorded_outcomes[]` and `outcome_impact`. `outcome_impact` carries `customers_affected` (a non-negative number, or null) and `side_effects` (text, or null). Null means there is no confirmed value and must show as "unknown", never zero (D-29). Authoriser and recorder names and times come from the decision and outcome history (D-30).
- Writes `POST /work/{id}/emergency` actions: `authorize`, `capture_outcome` (`implemented_at` required), `record_review`, `retrospective_decision` (the return action covers "return"), `reconcile_retrospective`. Also `POST /work/{id}/reviews` for the report, plus the follow-up change list `GET/POST .../emergency-outcomes/{id}/followups`.
- "Return with a note" on `record_review` does not exist (D-28). Do not invent it. Use the retrospective return action for the retro, and the document review verdict for the report.
- Out of scope: the emergency-intake start flow and authority recovery (`/projects/{case}/emergency-intake`, `/authority-recoveries`), unless the spec writer finds the existing Start work drawer already covers them. Each needs its own approval of the board. The CTO decision control is also out of scope.

**F-69b, SCR-51 Escalation (6 boards).**
- Line key `escalation` on the shared work-item page. Reads `GET /work/{id}/escalation`: `stage`, `direction`, `target`, `client_decisions[]`, `history[]` (role, verdict, time and, per D-31, the reason visible to the eligible reviewer), `document_version_id`, `receipts[]`, `jobs[]`. The draft read supplies the exact message preview and permitted recipients (D-32).
- Writes: `decide_client_action` (approve = escalate, reject = decline, return = rework, per D-31), `request_communication_review`, `POST /work/{id}/reviews` (document), `check_original_delivery` and `recover_delivery`.
- Tola's findings facts (15 days late and so on) have no live source. Show them only if a read supplies them, and otherwise omit them. Do not fabricate them.
- Out of scope: raising an escalation (the register `classify` then `request` flow). It needs proof ids and belongs with the Start work drawer.

Binding for both:
- Use the existing adapter, not a new workspace frame.
- Role gates come from the server (`options[]`, `client_decisions[]`). The UI must not name approvers or grant authority.
- Send is a separate step from review.
- A job or send claim is not a verified output. Show receipts only when `receipt_ids` or `receipts[]` exist.

## Risk
High because both lines record authorisations and outcomes for emergency production changes, and escalation sends a message outside the company. A wrong null-versus-zero display of customers affected, or a misread verdict (reject versus return), would misstate a business record. Surfaces: ui, api and contract-change for the new reads and commands, auth and security for the role-gated decisions, external-messaging for the SCR-51 send and receipts, and product-decision because the flows are new to the client. Files: architecture/packages/v7/tasks.csv (FE-EMERGENCY-ESCALATION) and delivery/connect/screens-d-delivery-issues-escalation.md.
