DECISION: READY
RISK: high
SURFACES: ui, api, security, auth, payments, external-messaging, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-110B is SCR-59 part 2: the totals-review and publish boards (4 of 18 with mobile) plus the decision cards on the part 1 boards. It follows F-110's binding board split.
- Build-start waits, not blockers: F-110 merging (the panel, client and mock folder `src/features/payroll-run/` that this part extends), F-108, F-85 and F-87 (the `Actions` slot and `useWorkCommand`).
- All four operations are in the lane-d contract (API 1.25.0): `POST /work/{id}/reviews`, `payroll-operations` (publish, withdraw, successor, restart), `POST /work/{id}/corrections` and `POST /work/{id}/aggregate-receipt`. No backend change is needed.
- Wherever the API does not supply a board part, hide it (D-182). That covers "Gross pay + Unknown", per-recipient rows and staff counts. Unknown money stays unknown, never 0.
- High risk: it publishes payroll totals to named recipients and handles withdrawal, restricted payroll and recipient receipts. The merge goes to the design engineer's merge batch.

## Scope
Outcome: an admitted payroll reviewer or operator decides on each review card, publishes totals, withdraws or replaces them, restarts a cancelled run, asks HR to correct, and a recipient acknowledges their own receipt, all on the live API.

Task FE-FIN-PAYROLL-RUN, part 2. The spec follows F-110's spec as binding (reads, display rules, no-leak rule for `working-rows`, 403/404 no-access wording, uncertain-effect lock, tokens never null or 0).

In scope:
- Decision cards on the input, combine and match review boards: `POST /work/{id}/reviews` with approve, return, revoke and approve_draft_match. A successor match needs a fresh independent review.
- SCR-59-totals-review: the decision with Withdraw approval. It is drawn only once a publication exists, from the report read (`eligible_total` as returned, `by_business_unit`, version).
- SCR-59-publish: `payroll-operations` action `publish`.
- `payroll-operations` actions `withdraw`, `successor` and `restart`. `restart` uses `payroll-recovery.restart`, and "Start a corrected run" appears only when that read supplies it.
- `POST /work/{id}/corrections` ("Ask HR to correct") from the match review.
- `POST /work/{id}/aggregate-receipt`, enabled only when the report says `can_acknowledge`.
- Evidence ids and proofs follow the lane D rule. Use the action's own proof field, or a list the read supplies. Nothing is preselected, the button is off when the list is empty, and no id is invented.

Out of scope:
- Anything F-110 owns (stations, HR receipt, report and recovery reads).
- `working-rows` listing and corrections intake (F-108, F-109).
- Reconcile and resume (F-87).
- Changes to `src/features/workspace`. Forms are `PayrollRunActions.tsx` registered through the F-87 `Actions` slot.
- Any recipient list or "Gross pay + Unknown" split (hidden). Staff names and individual pay never appear (E-26).

The spec writer must read the 1.25.0 request bodies for these four operations directly from the contract. It must flag any write the backend answers leave unsettled, built on the best reading, rather than guess business rules, approvers or counts.

## Risk
High. These writes publish and withdraw payroll aggregates and record independent approvals. Independence rules, revision tokens, and uncertain effects that must reconcile before any retry make them hard to undo. The surfaces are ui, api, security and auth (restricted payroll, per-record access), payments, external-messaging (the published totals reach named recipients) and product-decision (new flows and wording the client must see). `payroll-operations` bodies carry no idempotency key, so only `expected_revision` and `case_revision` guard them, as in F-110.

## Questions
None blocking. Both for the batch, recommendation first:
1. Does a board draw the "Start a corrected run" and successor entry points? (a) Draw them on the follow-up and totals-review boards, shown only when the read supplies `restart` or the successor option (recommended). (b) Leave them off until a board draws them.
2. The totals-review table is unreadable before a publication exists. (a) Show the board only once `publication_id` is set (recommended). (b) Show an empty shell, which has no source.
