DECISION: NOT-READY
RISK: high
SURFACES: ui, api, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: PSL milestone-completion rule (who may press "Mark complete", and whether it starts the invoice draft); no decision ID is assigned yet
REVIEWER: readiness

## Summary
- F-50 is FE-MILESTONE-COMPLETE (SCR-19, 2 boards). Its architecture gates are met: `gate_ids: []` (architecture/packages/v7/delivery.md:2213-2245), and FE-M3-PROJECT-TABS (F-25) and FE-M2A-PROOF part 1 (F-47) are merged. The client approved SCR-19 on 13 Nov (design/review.json:32). D12 stage terms is not a gate for this task, because the amount comes from the signed SOW and not from this form (G-SCR19-5).
- **The whole screen is the milestone-completion write, and that write is held.** `delivery/psl-decisions/PSL-DECISIONS.html:176-180` puts "the milestone-completion write and any automatic start of the invoice draft" on hold until PSL says which PMO role may press "Mark complete" and whether completion starts Chidi's invoice draft. The split "PMO completes, Finance invoices" is settled, but the per-role permission and the auto-start are not.
- The contract also has no write for it. `schema.d.ts` has no completion endpoint, `milestone_id` or `can_complete` (G-SCR19-1 and -2, both blocking, gaps-a-project-setup.md:115-116). F-25 also refused to draw "Mark milestone 3 complete" for this reason (F-25 spec.md:28). A build now would invent the button rule and the write.
- There is no part 1 to carve off. The two boards are the confirm screen, and the read-only milestone list is already F-25's Milestones tab. Proof already uploads through F-47.
- **Unblock by:** (a) PSL answers the two questions below; (b) the backend adds the completion write and the `milestone_id`, `can_complete` and `cannot_complete_reason` fields. Once both are in, this is READY (high risk) with a 2-board outcome. Alternatively the design engineer may say to build it on the contract mock with the button shown only when the mock returns `can_complete`. That needs a recorded exception with limits, and I have not assumed it.

## Scope
Not for a spec yet. When unblocked: **outcome** is the PM opens SCR-19 from "Mark milestone N complete" on SCR-38, sees the milestone and the proof already on record, and presses "Mark complete". The completion is recorded with their name, shown only from the re-read. Boards: `design/canvas/project/SCR-19-{desktop,mobile}.dc.html` (2). Endpoints: E-PROJECT-TAB milestones, E-PROJECT, E-EVIDENCE-UPLOAD, and the new completion write (G-SCR19-1). Out: invoicing, the stage amount (D12 and the contract terms), the SCR-38 link (needs G-SCR38-2), any edit or revoke of a completion.

## Risk
High. This records a fact that later starts the invoice line (money), and it is hard to undo, because a wrong completion needs a correction path that keeps history and that Finance cannot use. SURFACES: ui, api (a new write), contract-change (G-SCR19-1 to -3), product-decision (the permission and auto-start rule). PRODUCT-ACCEPTANCE is required.

## Questions
1. Who may mark a milestone complete: only the project's PM, or anyone in PMO? (PSL)
2. Should marking complete start Chidi's stage invoice draft automatically, or only offer "Start the invoice" for Finance? (PSL)
3. Backend: the completion write, the milestone id and reference, `can_complete` with its reason, `completion.evidence`, and whether a wrong completion can be corrected without losing history.
