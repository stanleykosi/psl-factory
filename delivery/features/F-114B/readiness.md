DECISION: READY
RISK: high
SURFACES: ui, api, auth, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- READY as part 2 of SCR-45 (task FE-DELIVERY-RELEASE). D-17 is answered in API 1.25.0: the PMO Lead confirms with `confirm_and_complete` on POST /work/{id}/go-live-milestone, using `milestone.can_confirm` and the evidence ids from GET /work/{id}/go-live-replies. The 1.25.0 contract in the lane-d worktree contains `confirm_and_complete`, `can_confirm` and the reply corrections shapes.
- Build-start waits (not blockers): F-114 (part 1, owns the page `/work/{id}/go-live`, the adapters and the mock `frontend/mock/go-live.mjs`), F-85 (shared frame) and F-87 (the `Actions` slot and `useWorkCommand`). The coordinator holds the builder until all three are on main.
- Two outcomes, one PR: (1) the PMO Lead confirms and completes the go-live milestone; (2) a recorded client reply is corrected or withdrawn. Both extend F-114's page.
- High risk: marking a milestone complete gates hypercare and handover, and a withdrawal or correction changes recorded client acceptance evidence. Merge goes to the design engineer's batch.
- Document review (`POST /work/{id}/reviews`) was named for F-114B in F-114 but is not in this feature's outcome. It is held out to keep one PR (see Scope). The coordinator should confirm or open a part 3.

## Scope
Outcome: on the go-live page the PMO Lead can confirm and complete the milestone, and staff can correct or withdraw a recorded client reply, through live API 1.25.0 or later (builders use the 1.25.0 contract; the spec follows F-114's conventions: revision pair, error words, no double submit, refetch after 2xx).

In:
- `POST /work/{id}/go-live-milestone` with `action: confirm_and_complete`. Show the control only when `milestone.can_confirm` is true in the replies read. The evidence ids (decision and proofs) come from that read, nothing preselected, and the button stays off when the list is empty (PSL answer 1 and D-1). Show the milestone name and state from `milestone` only. Replaces F-114's read-only "Milestone" row with the action where the read allows it. No `draft_mapping` / `record_completion` pair unless the 1.25.0 contract still requires it; the spec writer takes the exact request from the contract.
- Correcting or withdrawing a reply, from `corrections[]` in the replies read (F-114 reads it but does not use it) and the matching command on `POST /work/{id}/go-live-replies`. Offer only what `corrections[]` supplies for that reply (roles, previous ids, reasons). `withdrawn` rows stay read-only history. Nothing is sent to the client.
- Mock fixtures and tests for: can_confirm true, can_confirm false, empty evidence list, 409, a correctable reply, a withdrawn reply.
- Form wiring uses F-87's `Actions` slot and `useWorkCommand`. Lane D adds its own `XxxActions.tsx` and does not touch `src/features/workspace`.

Out:
- `POST /work/{id}/reviews` (document review), pending the coordinator's confirmation above.
- Anything F-114 owns (sign-off, record_reply, successor, decline panel).
- `POST /setup/{case}/policy-configurations/{id}/review`.
- Inventing the milestone choice, approvers or evidence. If `can_confirm` is false, show the reason the read gives or nothing. Unknown stays unknown.
- Hypercare "RUNNING" or archive "STARTED" rows. Agent steps (D-182).

Rules for the builder: allowed actions come from the reads, not the viewer's role in the client (DC-5). A 404 reads "This record is unavailable." Say in build.md what board parts were hidden.

## Risk
High: confirming the milestone is irreversible in effect (it unlocks hypercare and handover) and uses a PMO Lead authority check on the server; correcting or withdrawing a reply alters recorded acceptance evidence. Surfaces: ui, api, auth (`can_confirm` and role-limited corrections), contract-change (new 1.25.0 fields), product-decision (D-17 answer, acceptance wording). Product acceptance is required because the client-facing outcome flow changes. Sources: backend-answers D-17, F-114 readiness and spec, `contracts/psl-factory.openapi.json` 1.25.0.
