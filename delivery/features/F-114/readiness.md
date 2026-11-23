DECISION: READY
RISK: high
SURFACES: ui, api, auth, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- READY as part 1 only. SCR-45 has 10 boards and three write paths plus the milestone mapping (effort L), which is too big for one PR. Part 1 is sign-off and client replies. Milestone completion and document review move to F-114B, which depends on F-114 merging.
- Backend answers settle the data: D-15 (two distinct signature evidence ids, never the same id twice), D-16 (signer source system, id and version come from the retained external signature or register) and D-1 (proof is uploaded through the sign-off proofs operation, which owns the evidence).
- Waits: F-85 (lane C, PR #101) must be on main before the builder starts. This delays the start and is not a blocker. Write the spec against `/Users/Hunchoo/psl-factory-main/delivery/features/F-85/spec.md`.
- High risk: this records client acceptance and signatures, and acceptance gates the milestone, hypercare and handover. The merge goes to the design engineer's batch.
- D-17 (milestone routing to the PMO Lead) needs backend work that has not happened. That is why the milestone is out of part 1.

## Scope
Outcome: go-live acceptance records both signatures and the accepted, changes-requested and declined outcomes through the live API 1.24.0.

In (part 1, task FE-DELIVERY-RELEASE):
- `GET/POST /work/{id}/go-live-signoff`. Read `version_id`, `receipts[]`, `proofs[]` (kind `signature`) and `prior_acceptance_id`. Write "Signed" with `expected_revision` and `case_revision` (DC-1), `pm_signature_id` and `client_signature_id` as two distinct evidence ids (D-15), and signer details for both PM and Client (D-16). Both `mode` values are in scope (`fresh_signatures`, `metadata_binding`).
- `GET/POST /work/{id}/go-live-replies` with `record_reply`, covering outcomes `changes_requested` and `declined`. Include channel, party, recorder role and attestation, and show `withdrawn` replies as read-only history.
- `POST .../go-live-replies/successor`, to prepare v2 after changes.
- The decline panel from `go-live-replies/decline`: `issues[]`, `new_candidates[]`, `review_options[]`, `rules`, and the actions `link_decline_issue`, `prepare_new_candidate` and `review_remediation`.
- The read-only "what this unlocks" list, built from the `milestone`, `linked_issues[]` and `reviewed_handoffs[]` reads. Do not draw "Hypercare can be evaluated: RUNNING" as one read. Show only the parts the reads supply.

Out (F-114B):
- `POST /work/{id}/go-live-milestone` (`draft_mapping` then `record_completion`). D-17 says the PMO Lead confirms the milestone, and the backend must still route that decision.
- `POST /work/{id}/reviews` (document review).
- `POST /work/{id}/corrections`.
- The `POST /setup/{case}/policy-configurations/{id}/review` response rules (Setup).

Rules for the builder:
- Hide board parts the API does not supply, per D-182: Tola's agent card and steps (DC-3), the single "Signed / Changes / Declined" form with one proof, and any attempt counts or amounts. Say what was hidden in the build notes.
- Proof upload goes through the sign-off proofs operation (D-1), not generic `/cases/{id}/files`. Use the evidence ids the line read lists. Never submit the same id for both signers.
- If signer source details are missing, show "needs reconciliation" and do not submit. Do not invent values.
- Allowed actions come from the line read (`actions[]`, `can_record`, `can_correct`, `roles[]`), per DC-5.
- Build the line adapter in this feature's folder. Do not change the shared frame in `frontend/src/features/workspace`. Any frame change is a dependency on lane C.
- Client replies are recorded by staff. Nothing is sent to the client.

## Risk
High, because a signed acceptance is identity and evidence data that is hard to undo and gates the milestone and later stages. It also has a cross-layer contract: two distinct evidence ids, signer binding and a revision pair, per `backend-answers.md` D-15, D-16, D-1 and `screens-d-delivery-issues-escalation.md` SCR-45. Surfaces are ui, api, auth (the allowed actions are role-dependent), contract-change and product-decision (acceptance wording and outcomes). Product acceptance is required because this is a new client-visible flow that the client must see.
