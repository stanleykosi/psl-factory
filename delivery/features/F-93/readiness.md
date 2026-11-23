DECISION: READY
RISK: high
SURFACES: ui, api, auth, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- One observable outcome, sized for one PR: the "Confirm what happened" panel on a live work item, recording an outcome, reason and proof through `POST /work/{id}/delivery-observations`.
- LC-Q19 is closed. D-187 (23 Nov 2026) accepted the recommended option of LC-Q17 to LC-Q22: "Confirm what happened" with plain sublines, a required Reason box and proof always shown.
- F-85 and F-87 are build-order dependencies, as recorded for F-86, F-88 and F-91. They are not readiness blockers. Build order is F-85, then F-87, then F-93.
- The panel departs from the approved board on wording, fields and proof under the recorded design exception. That is a changed flow and copy, so the client must see the result.
- No backend, contract or migration change is needed (contract 1.24.0).

## Scope
Binding source: criteria 3 and 23 to 32 of `delivery/features/F-87/spec.md`, including the "Contract: The Confirm what happened panel" section and Conflicts item 1. A new F-93 `spec.md` is written from those criteria.

- Task: FE-CONNECT-1. Contract 1.24.0.
- Endpoints:
  - `GET {tracking_url}`: `can_record_delivery_observation`, `delivery_observation_url`, `uncertain_effects[]`.
  - `POST {proofs_url}`: `{kind:'pdf_copy', upload_id, case_revision}`.
  - `POST {delivery_observation_url}`: 201.
  - `GET {delivery_observation_url}`: read after an uncertain result.
- In scope:
  - `DeliveryObservationPanel.tsx` and `workspace/deliveryObservation.ts`.
  - The `work.observe` descriptor.
  - Mock items 4112 to 4115 and their scenarios.
  - Panel tests and `e2e/work-item-controls.spec.ts` cases.
  - The two live checks against Django (criterion 32).
- Rules:
  - The panel is gated only by the tracking flag, a same-origin URL for this `work_id`, and at least one effect.
  - The page does no role check and never invents who may record an outcome. The server checks recovery authority, and its 403 and 409 are shown as given.
  - One panel per effect, and `effect` is copied as served.
  - No outcome is preselected. Reason is required and proof is always shown and required. A null `case_revision` or null `revision` holds the button.
  - An uncertain POST is settled by reading the observations list, with no automatic retry. The proof upload must not duplicate on retry.
  - The page says nothing about resend, reminder or verification. The footer reads "Your choice is recorded with your name."
- Out of scope: lookup, resume, cancel and background controls (F-87); release invoice (F-90); the `pmo_lead_note` proof; a history list; any backend, contract or migration change.
- Depends on F-87's `useWorkCommand`, shared locking, Actions slot and `makeCommand` change. The builder starts from F-87 merged.

## Risk
High because it writes a business record about invoice delivery (money) that cannot be undone from the page. The POST has no idempotency key, so uncertain results must be settled by reading the list (`useWorkCommand`). It depends on server-side recovery authority (`auth`). It adds a new contract call, a proof upload step, and a product-decision copy change from D-187.
