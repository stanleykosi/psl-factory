DECISION: READY
RISK: high
SURFACES: ui, api, auth, contract-change, external-messaging, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none

REVIEWER: readiness

## Summary
- F-121 is SCR-51 Escalation only: 6 boards (investigating, decide, not-escalated, draft, review, received). That fits one PR. It is the SCR-51 half of the split in F-69/readiness-r0-not-ready.md.
- F-85 (shared work-item page and line adapter) is merged on main: F-85 feature.json records merge_status merged, merge_sha e2f44656.
- Backend answers D-31 (reject = declined, return = rework, reason visible to the eligible reviewer) and D-32 (the draft read gives an exact preview and permitted recipients) settle the open contract questions.
- The SCR-51 boards exist in design/canvas/project (desktop and mobile). The F-69 readiness reviews recorded SCR-50 and SCR-51 as client-approved. I did not re-run `design.py check` or re-read design/review.json in this pass. The spec writer must confirm both.
- I did not read the src/features code, because no shell was available. The spec writer should confirm the line adapter's extension points.

## Scope
Binding for the spec writer. Task FE-EMERGENCY-ESCALATION part 2, frontend only. Build on F-85's shared work-item page and line adapter, with no new workspace frame. Line key `escalation`.

In:
- Read `GET /work/{id}/escalation`: `stage`, `direction`, `target`, `client_decisions[]`, `history[]` (role, verdict, time, and the reason where the server supplies it to the eligible reviewer), `document_version_id`, `receipts[]`, `jobs[]`, `next_action`, `can_request_communication_review`.
- The draft read supplies the message preview and permitted recipients (D-32). Show exactly what it returns.
- Writes:
  - `POST /work/{id}/escalation` `decide_client_action`. approve = escalate, reject = decline, return = rework (D-31).
  - `request_communication_review` with `version_id`.
  - `check_original_delivery`.
  - `recover_delivery` (`job_id`, `operation` cancel or retry, `reason`).
  - `POST /work/{id}/reviews` with `kind:"document"` for approve and send, or return.
- Send stays a separate step from review.
- Receipts show only when `receipts[]` or `receipt_ids` exist. A job or send claim is not a verified output.

Out:
- Raising an escalation (register `classify` then `request`, then `POST /work`). It needs proof ids and belongs with the Start work drawer.
- Tola's findings facts (15 days late and so on) and investigation steps. They have no live source. Omit them unless a read supplies them, and never fabricate them.
- Any invented approver, role or authority. Role gates and eligible verdicts come from `client_decisions[]`. The UI must not name approvers or grant authority.
- The design shows only escalate and decline. `direction` (de-escalate) and `target` (PMO or CTO) exist live, so render them from the read without inventing copy for them. Flag any wording that needs client input.

## Risk
High because the line records a client-escalation decision and sends a message outside the company. Misreading reject as return, or treating a job claim as a delivered receipt, would misstate a business record (connect map SCR-51, D-31, D-32). Surfaces are ui, api and contract-change for the new reads and commands, auth for the server-gated decisions, external-messaging for the send and receipts, and product-decision because the flow is new to the client. Product acceptance is required.
