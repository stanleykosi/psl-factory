DECISION: NOT-READY
RISK: high
SURFACES: ui, api, product-decision, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: PSL milestone-completion rule (who may press "Mark complete", and whether it starts the invoice draft); no decision ID is assigned yet
REVIEWER: readiness

## Summary
- F-78 is FE-MILESTONE-COMPLETE with SCR-19 (replaces F-50, BLOCKED 19 Nov). Architecture gates are empty (`gate_ids: []`, model.json:22051), and the Milestones tab (F-25) and proof upload (F-47) are merged.
- Live 1.22.0 now has the write: `POST /api/v1/projects/{case_id}/milestones/completions` (201) with `GET` options and `GET .../milestones/{milestone_id}`. So the F-50 "endpoint missing" blocker is gone.
- The PSL decision is not settled anywhere. I searched OVERNIGHT-DECISIONS.md, COORDINATOR-HANDOFF.md:158 (still lists it as waiting), model.json (no decision ID) and the connect docs. Both questions are still open: who may press "Mark complete", and whether it auto-starts Chidi's invoice draft.
- The live contract also leaves the screen's gaps open: no `can_complete` or reason (B-31), `name` is free text with no milestone id (B-28), no API way to create `kind=completion` evidence (B-29), and no returned invoice handoff id (B-30). The 403/404 on the options read stands in for permission, which would be a guess at the rule.

## Scope
Not for a spec yet. When unblocked: the PM opens SCR-19 from the Milestones tab, sees the milestone and the proof on record, and presses "Mark complete" (`POST .../milestones/completions` with case `revision`, `evidence_id`, `name`). The completion shows only from the re-read. Boards: `design/canvas/project/SCR-19-{desktop,mobile}.dc.html`. Out: invoicing, stage amount, any edit or revoke, the SCR-38 button link until the design is reconciled.
Unblock by: (a) PSL answers the two questions below; (b) backend answers B-28 to B-31. Alternative, only with a recorded exception and limits from the design engineer: build on the contract mock and show the button only when the mock returns `can_complete`. I have not assumed that exception. No read-only slice exists: the SCR-19 screen is the confirm step, and the read is already F-25's Milestones tab.

## Risk
High. The completion is a fact that queues the Finance handoff (money) and is hard to undo (no correction or revoke path in live). Writing it without the permission rule would invent an approver. Sources: contracts/psl-factory.openapi.json:78823, connect/screens-b-projects-setup-clients.md SCR-19, F-50/readiness.md.

## Questions
1. PSL: who may mark a milestone complete, only the project's PM or anyone in PMO?
2. PSL: should completion start Chidi's stage invoice draft automatically, or only offer "Start the invoice" to Finance?
3. Backend: B-28 (milestone id and name), B-29 (how completion evidence is created), B-30 (handoff id), B-31 (`can_complete` with a reason), and how a wrong completion is corrected.
