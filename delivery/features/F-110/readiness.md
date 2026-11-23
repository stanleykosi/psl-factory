DECISION: READY
RISK: high
SURFACES: ui, api, security, auth, payments, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- SCR-59 has 18 boards and the connection map rates it effort L, so it is split. This file covers part 1 (F-110). Part 2 becomes F-110B and depends on F-110 merging.
- Part 1 is the run read and the working steps: nine stations, inputs and checks, HR snapshot receipt, published aggregate with recipient receipt, and the cancelled-run recovery read. Part 2 holds the review verdicts, publish, withdraw, successor, HR corrections and the recipient acknowledgement.
- D-PAYROLL-VISIBILITY does not block this screen. It gates only the SCR-13 field-visibility editor (task FE-SETUP-PAYROLL-FIELDS). The backend enforces restricted payroll per person (INV-RESTRICTED) whatever is configured, and F-110 lists no decision.
- The backend answers settle E-30, E-31 and E-26, so no business rule is left to guess.
- Waits, which delay the build start but do not block readiness: F-85 shared line adapter (lane C, PR #101) and the earlier payroll parts F-108 (intake) and F-109 (corrections), which supply the inputs this run consumes.
- High risk and restricted payroll, so the merge goes to the design engineer's merge batch.

## Scope
Outcome: an admitted payroll operator sees where a run stands and moves it through combine, match and aggregate on the live payroll operations, and sees what was published and received.

Part 1 (F-110), in scope. Task FE-FIN-PAYROLL-RUN, part 1.
- Reads: `GET /work/{work_id}/payroll-operations` for the stations (`stage`, `finding`, work `state` including awaiting_reconciliation, followup_needed and effect_uncertain), `selected.input_ids[]`, `working[]`, `selected.hr_snapshot_id` and `hr_receipt`. `GET .../payroll/{kind}/{record_id}/working-rows` for counts and the private calculation, only where the caller is admitted. `GET /work/{work_id}/payroll-recovery` (`restart`, `previous_receipt`). `GET .../payroll/reports/{publication_id}` for `by_business_unit`, `eligible_total`, `receipt_id`, `can_acknowledge`.
- Writes: `payroll-operations` with action `working` and stage combine, match or aggregate (E-31), and action `receive_hr` with `snapshot_id` and `evidence_id`. Start the run through `POST /work` (`finance-payroll/v1`).
- Access: work detail, working rows and snapshot rows are for admitted readers only; other readers get 403 or 404 and the screen shows a plain no-access state, with no staff names or pay values in the error. Group recipients never see staff names or individual pay (E-26).

Part 2 (F-110B), out of scope here:
- `POST /work/{id}/reviews` (approve, return, revoke, approve_draft_match, with a fresh independent review for a successor match).
- `payroll-operations` actions `publish`, `withdraw`, `successor` and `restart`.
- `POST /work/{id}/corrections` (ask HR to correct from the match review).
- `POST /work/{id}/aggregate-receipt` (recipient acknowledgement).

Display rules (binding):
- `eligible_total` is a confirmed decimal string on an approved publication (E-30). Show it as returned. Do not build the board's "Gross pay + Unknown" split, because the API has no known/unknown parts. Hide that part (D-182) and say so in the spec.
- Hide "140, 2 held" staff counts beyond what working-rows totals return, and hide "Merge rule F16", which is not on the read.
- Unknown or null money stays unknown, never 0.
- Show `payroll-recovery` (prior receipt) as live data the board does not yet draw only if a board slot exists. Otherwise list it as a design gap for the design engineer.
- E-32 does not affect this screen. SCR-57 reads the match run.

## Risk
High. This is restricted payroll data, with identity-bound access per record (`working-rows`, snapshot rows) and the run that feeds the published pay aggregate for a named recipient. Writes in part 1 (combine, match, aggregate, receive_hr) are hard to undo and need operation keys and evidence ids. The surfaces are ui, api, security, auth, payments and product-decision (new flow and wording the client must see). The effect_uncertain and awaiting_reconciliation states must reconcile before any retry.

## Questions
None blocking. For the batch, with the recommendation first:
1. Where should the recovery read (`previous_receipt`) appear? (a) a note on the station panel (recommended); (b) leave it off until a board draws it.
2. The "Gross pay + Unknown" board wording has no API source. (a) show the confirmed total only (recommended); (b) ask the backend for a split. This conflicts with D-185, which says to build what the API supplies.
