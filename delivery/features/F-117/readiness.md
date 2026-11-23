DECISION: READY
RISK: high
SURFACES: ui, api, contract-change, external-messaging
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- One outcome: SCR-48 (line `delivery_handover`) reads the live handover, records Support's reply with gaps, and publishes the approved version, with Support's receipt shown as a separate record.
- All backend answers exist (D-1, D-22, D-23, D-24 and section 12 "Publish to Support"), so no client question blocks it.
- Build-start wait: F-85 (shared line adapter, lane C, PR #101) is not yet on main. Under the lane D rule this delays the builder only and is not a readiness blocker. Write the spec against `/Users/Hunchoo/psl-factory-main/delivery/features/F-85/spec.md`.
- Size is one PR (SCR-48, about 8 boards).
- Publish to Support is an irreversible send to another party, so merge goes to the design engineer's batch.

## Scope
This section is binding for the spec writer. It is unchanged from `readiness-proposal-r0.md`.

Outcome: the PM opens a handover work item, sees the live state, records Support's reply, and publishes the approved version. It builds on API 1.24.0 per D-185, in `frontend/`. The line's own adapter mapping lives in this feature folder (DC-2). Task FE-CONNECT-1. Screen SCR-48.

In:
- Reads:
  - `GET /work/{id}`.
  - `GET /work/{id}/support-publication` (`can_publish`, approved version; D-22).
  - `GET /work/{id}/support-replies` (`receipts[]`, `roles[]`, `channels[]`, `can_record`, `proofs[]`).
  - `GET /work/{id}/support-receipt` (`receipts[]`, `can_acknowledge`, and the exact handover title, version and sections only when the viewer is the real recipient; D-24).
  - `GET /work/{id}/history`.
- Writes:
  - `POST /work/{id}/support-publication`. Show the button only when `can_publish` is true. Publish the exact approved version. Treat the Support receipt as a separate record.
  - `POST /work/{id}/support-replies` with `status` received or gaps, `party`, `channel`, `responded_at`, `role`, `evidence_id`, `note`, `receipt_id`, `previous_id` and the structured `gaps[]` (D-23). Both revisions go in (DC-1).
  - `POST /work/{id}/support-receipt` (Support's own acknowledgement).
  - `POST /work/{id}/corrections` for "draft v2".
  - `POST /work/{id}/actions` `{action:"reconcile"}` (202) for an uncertain delivery.
- Start: `POST /work` with `delivery-handover/v1`.
- Evidence: use the path the owning operation offers (D-1). If the support-replies proof path is unclear, build on the best reading of the contract and flag it. Do not invent one.

Out (hide per D-182 and say so):
- Tola's step cards and findings (DC-3).
- The "Review needed? NO" facts line.
- A handover document summary or attachments for the PM. D-24 gives these only to the real Support recipient.
- The document review (`POST /work/{id}/reviews`), unless the SCR-48 boards draw it.
- Any change to `frontend/src/features/workspace`. If a frame change is needed, name it as a dependency on lane C.

Rules: unknown stays unknown, never 0. Do not invent approvers, attempt counts or publisher identity.

## Risk
High, because Publish to Support is an irreversible external send with an uncertain-delivery and reconcile path. The reply record is also checked by role and can replace an earlier record through `previous_id`. Both writes need two revisions, so they are contract-sensitive. Surfaces are ui, api, contract-change (v7 to live shapes, DC-1/DC-2) and external-messaging (publication and receipt). Merge goes to the design engineer's batch. The v9 architecture and the 13 Nov design approval (with the D-173/D-181 exceptions in `design/review.json`) cover this screen. The spec writer should still confirm `design.py check` passes.
