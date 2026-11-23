DECISION: NEEDS-INFO
RISK: high
SURFACES: ui, api, auth, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none assigned (open: who holds the completion write, and whether completion starts the invoice draft)
REVIEWER: readiness

## Summary
- Most of the r1 blockers are cleared. PSL decided on 23 Nov (BUILD-DECISIONS.md on main) that the PMO Lead reviews the project and confirms the exact milestone before completion is recorded. Contract 1.24.0 has the write and options read the screen needs.
- B-28 to B-31 are answered. The write takes the milestone name, current revision and typed evidence (an existing native proof, or a checked private PDF). The options read returns `can_complete`, `can_attach_pdf` and `hold` (`baseline_required`, `proof_required`, `name_in_use`). The write returns the new milestone id.
- The invoice-draft question is not answered. B-30 says only that the service queues a Finance handoff that may appear later in the department handoffs. No PSL decision or backend answer says whether the invoice draft starts automatically.
- The "who" is only half enforced. The decision names the PMO Lead, but the backend answer for the sibling go-live flow (backend-answers.md:1139) says completion checks the configured `PM` authority and that backend work is still needed to route the decision to the PMO Lead and keep it on the exact milestone record. Nothing says the plain completions write does this. If `can_complete` is true for a PM who is not the PMO Lead, the screen would contradict PSL.
- Risk stays high: the completion is recorded as fact, can feed billing, and has no revoke path in the contract.

## Scope
Not for a spec yet. When unblocked, the outcome is: the PMO Lead opens SCR-19 from the Milestones tab, sees the exact milestone and proof on record, and confirms completion. Covers FE-MILESTONE-COMPLETE, `GET` and `POST /api/v1/projects/{case_id}/milestones/completions` (and `GET .../milestones/{milestone_id}` for the re-read). Binding rules for the spec writer:
- The button shows only when `can_complete` is true; `hold` gives the reason in plain words. The UI never encodes a role rule of its own.
- Evidence is an existing proof from `proofs[]` or a PDF upload, shown only when `can_attach_pdf` is true.
- The completion appears only after the re-read. No invoice or "draft started" claim until the invoice question is answered; at most show the Finance handoff as read from the project's department handoffs.
- Out: invoicing, stage amounts, edit or revoke, the SCR-38 link.
Boards: `design/canvas/project/SCR-19-{desktop,mobile}.dc.html`.

## Risk
High. A completion is an irreversible, billing-adjacent write (queues a Finance handoff, contract 1.24.0 milestones/completions, backend-answers.md B-28 to B-31). Surfaces: ui and api for the screen and write, auth because the PMO Lead rule must be enforced server-side, contract-change for the 1.24.0 options and write, product-decision for the open invoice rule. Not READY, because building before the authority is confirmed would invent an approver.

## Questions
1. Backend: for `POST milestones/completions`, does `can_complete` (and the write) require the PMO Lead's confirmation on the exact milestone, as PSL decided on 23 Nov, or does it still accept the project's PM as in the go-live flow?
2. PSL: when a milestone is marked complete, should the stage invoice draft start automatically, or should Finance be offered "Start the invoice" after the handoff?
