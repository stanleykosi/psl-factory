DECISION: NOT-READY
RISK: high
SURFACES: ui, api, auth, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: LC-Q19
REVIEWER: readiness

## Summary
- The outcome is one observable thing and is sized for one PR: the "Confirm what happened" panel on a live work item. It records an outcome, reason and proof through `POST /work/{id}/delivery-observations`.
- Dependency not merged: F-87 (and F-85 under it) must land first. F-93 needs F-87's `useWorkCommand`, the shared locking, the Actions slot and the `makeCommand` change. Neither is merged.
- Design gate open: LC-Q19 is unanswered. The approved SCR-02 board promises a resend, a reminder and checked-6-times facts, and it has no Reason box. The backend does none of that (A-13, answers section 10). The design engineer must pick option 1, 2 or 3 first.
- Delivery runs under the recorded design exception, and this panel departs from the board on wording, fields and proof. That is a changed flow and copy, so the client must see the result.
- Once F-87 is merged and LC-Q19 is decided, this is READY as scoped below. No backend change is needed.

## Scope
Binding source: criteria 3 and 23 to 32 of `delivery/features/F-87/spec.md`, including the "Contract: The Confirm what happened panel" section and the Conflicts section item 1. F-87's coordinator note moves these criteria to F-93.

- Task: FE-CONNECT-1. Contract 1.24.0.
- Endpoints:
  - `GET {tracking_url}`: the flag `can_record_delivery_observation`, `delivery_observation_url` and `uncertain_effects[]`.
  - `POST {proofs_url}`: `{kind:'pdf_copy', upload_id, case_revision}`.
  - `POST {delivery_observation_url}`: 201.
  - `GET {delivery_observation_url}`: read after an uncertain result.
- In scope:
  - A new `DeliveryObservationPanel.tsx` and `workspace/deliveryObservation.ts`.
  - The `work.observe` descriptor.
  - Mock items 4112 to 4115 and their scenarios.
  - Panel tests, and `e2e/work-item-controls.spec.ts` cases for the panel.
  - The two live checks against Django (criterion 32).
- Rules:
  - The panel is gated only by the tracking flag, a same-origin URL for this `work_id`, and at least one effect. The page does no role check and never invents who may record an outcome.
  - The backend decides recovery authority. Its 403 and 409 are shown as given.
  - One panel per effect, and `effect` is copied as served.
  - No outcome is preselected. Proof is always required. A null `case_revision` or null `revision` holds the button.
  - An uncertain POST is settled by reading the observations list. There is no automatic retry.
  - The page says nothing about resend, reminder or verification.
- Out of scope: the lookup, resume, cancel and background controls (F-87); release invoice (F-90); the `pmo_lead_note` proof; a history list; any backend, contract or migration change.
- Build order: F-85, then F-87, then F-93.
- Before build:
  - Record the LC-Q19 answer. Option 1 is recommended and is what the spec assumes: short sublines that promise nothing, a required Reason box, an always-shown proof picker, and the footer "Your choice is recorded with your name."
  - If the answer is 2 or 3, this feature changes or holds.
  - Write an F-93 `spec.md` from the criteria above, since none exists yet.
- To re-check as READY once the gates clear: F-87 merged, and the design engineer's LC-Q19 answer recorded in the feature folder or the brief.

## Risk
High because it writes a business record about money (invoice delivery) that cannot be undone from the page. It depends on server-side recovery authority (`auth`), it has no idempotency key, and uncertain results must be settled by reading the list (`delivery-observations`; `useWorkCommand`). It is a new contract call and carries a product decision on copy, and it adds a proof upload step that must not duplicate on retry. The surfaces are ui, api, auth, contract-change and product-decision.

## Questions
Not NEEDS-INFO, because the question is already filed. The block is LC-Q19 in `delivery/connect/questions-batch.md`, for the design engineer, plus F-87 not yet merged.
