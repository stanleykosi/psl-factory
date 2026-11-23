DECISION: READY
RISK: high
SURFACES: ui, api, auth, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Both r2 questions are now answered. D-187 (B31) says completion is "Handoff only, Finance starts it". LB-2 is settled for the build: the control is gated on the server's `can_complete`.
- Ordering: this feature builds on the Milestones tab that F-71 is building (READY, spec at delivery/features/F-71/spec.md). F-78 may be specced now. Its build must start only after F-71 merges, and it branches from main after that.
- API 1.24.0 gives the options read (`can_complete`, `can_attach_pdf`, `hold`) and the completions write that returns the new milestone id. PSL's 23 Nov decision names the PMO Lead as the confirmer.
- Open item LB-2 stays open on the backend: whether POST milestones/completions enforces PMO Lead authority. The spec and PR must flag it. The UI invents no role check.
- Risk stays high because the completion is a recorded fact that queues a Finance handoff and has no revoke path.

## Scope
The outcome: from the Milestones tab, an authorised user opens SCR-19, sees the exact milestone and the proof on record, and confirms completion. The completion shows only after the re-read. Covers task FE-MILESTONE-COMPLETE, `GET` and `POST /api/v1/projects/{case_id}/milestones/completions`, and `GET .../milestones/{milestone_id}` for the re-read. Binding rules for the spec writer:
- Dependency: F-71 (Milestones tab) merges first. SCR-19 is entered from that tab and reuses its milestone list and row.
- The control shows only when the options read gives `can_complete: true`. `hold` (`baseline_required`, `proof_required`, `name_in_use`) is shown as plain-word reasons. The server decides authority. The UI never infers a role.
- The write takes the milestone name, current revision and typed evidence: an existing proof from `proofs[]`, or a private PDF, offered only when `can_attach_pdf` is true.
- D-187: completion only queues the Finance handoff. The screen never starts or drafts an invoice, and never offers "Start the invoice". It may show the Finance handoff as read from the project's department handoffs, with no claim that an invoice exists.
- Flag LB-2 in the spec and the PR: PMO Lead enforcement on the write is unconfirmed server-side.
- Out: invoicing, stage amounts, edit or revoke, the SCR-38 link, any role logic in the UI.
Boards: `design/canvas/project/SCR-19-{desktop,mobile}.dc.html`. Build against API 1.24.0 (D-185).

## Risk
High. A completion is an irreversible, billing-adjacent write that queues a Finance handoff (contract 1.24.0, backend-answers B-28 to B-31). Surfaces: ui and api for the screen and write. auth because authority rests on the server's `can_complete` and LB-2 is unconfirmed. contract-change for the 1.24.0 options and write. product-decision for D-187 and the PSL PMO Lead rule. The UI adds no authority, so the residual risk is the backend gap, which is flagged and not hidden.
