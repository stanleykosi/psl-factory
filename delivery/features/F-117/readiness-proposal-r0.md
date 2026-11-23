DECISION: NOT-READY
RISK: high
SURFACES: ui, api, contract-change, external-messaging
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none

REVIEWER: readiness

## Summary
- One outcome: SCR-48 (line `delivery_handover`) reads the live handover, records Support's reply with gaps, and publishes the approved version, shown with its separate receipt.
- All backend answers exist (D-1, D-22, D-23, D-24 and section 12 "Publish to Support"), so no client question blocks it.
- The only gate that fails: F-85, the shared line adapter (lane C, PR #101), is not on main. Lane D features must not change the frame and cannot build on a missing one.
- Start the spec once F-85 merges. The scope below is already settled and the size is one PR (SCR-48, 8 boards).
- The publish write sends to Support and cannot be undone, so merge goes to the design engineer's batch.

## Scope
Outcome: the PM opens a handover work item, sees the live state, records Support's reply, and publishes the approved version. Builds on API 1.24.0 per D-185, in `frontend/`, with the line's own adapter mapping in this feature folder (DC-2). Task FE-CONNECT-1.

In:
- Reads: `GET /work/{id}`; `GET /work/{id}/support-publication` (`can_publish`, approved version; D-22); `GET /work/{id}/support-replies` (`receipts[]`, `roles[]`, `channels[]`, `can_record`, `proofs[]`); `GET /work/{id}/support-receipt` (`receipts[]`, `can_acknowledge`, and the exact handover title, version and sections when the viewer is the real recipient; D-24); `GET /work/{id}/history`.
- Writes:
  - `POST /work/{id}/support-publication` for Publish to Support. Show the button only when `can_publish` is true. Publish the exact approved version, and treat the Support receipt as a separate record.
  - `POST /work/{id}/support-replies` with `status` received or gaps, `party`, `channel`, `responded_at`, `role`, `evidence_id`, `note`, `receipt_id`, `previous_id`, and the structured `gaps[]` (D-23). Both revisions go in (DC-1).
  - `POST /work/{id}/support-receipt` (Support's own acknowledgement).
  - `POST /work/{id}/corrections` for "draft v2".
  - `POST /work/{id}/actions` `{action:"reconcile"}` (202) for an uncertain delivery.
- Start: `POST /work` with `delivery-handover/v1`.
- Evidence: use the path the owning operation offers (D-1). If the support-replies proof path is unclear, build on the best reading of the contract and flag it. Do not invent one.

Out:
- Tola's step cards and findings (DC-3; hide and say so).
- "Review needed? NO" facts line.
- A handover document summary or attachments for the PM. D-24 gives it only to the real Support recipient, so hide it for others.
- The document review (`POST /work/{id}/reviews`) belongs to another screen unless the boards for SCR-48 draw it.
- Any change to `frontend/src/features/workspace`.

Rules: unknown stays unknown, never 0. Don't invent approvers, attempt counts or publisher identity.

## Risk
High because Publish to Support is an irreversible send to another party, with an uncertain-delivery and reconcile path. The reply record is also checked by role and can replace an earlier record (`previous_id`). Both writes need two revisions, so they are contract-sensitive. Surfaces: ui, api, contract-change (v7 to live shapes, DC-1/DC-2), external-messaging (publication and receipt). Merge goes to the design engineer's batch per the lane D rules.

Dependencies: F-85 (PR #101) must be merged first. The spec writer should confirm the design gate (`design.py check`) at spec time, since this record has no architecture or design baseline filled in yet.
