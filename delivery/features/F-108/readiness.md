DECISION: READY
RISK: high
SURFACES: ui, api, security, auth
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-108 (FE-FIN-PAYROLL-IMPORT) connects SCR-09 (import and reconcile) and SCR-18 (restricted payroll matching), about 8 boards, to live API 1.24.0. This fits one PR.
- D-PAYROLL-VISIBILITY (open, revision 1) is NOT a blocker. FE-FIN-PAYROLL-IMPORT has `gate_ids: []` in architecture/model.json. The decision only governs the configurable SCR-13 field-visibility editor. The backend enforces restricted access per person (403 for an admitted reader without the payroll grant, 404 for an invisible record, E-3), so the screens render what the API allows. Only F-44 (SCR-57) is gated, and that is BU totals.
- The build waits on F-85 (lane C, PR #101). That is a delay to the builder start, not a readiness blocker.
- Restricted payroll data and an auth boundary make this high risk. The merge goes to the design engineer's merge batch.
- No questions need the client. Presentation gaps are handled by hiding what the API does not supply (D-182).

## Scope
Outcome: an admitted payroll operator can start a payroll request, upload the two providers' files, see import problems, and run combine, match and aggregate. HR and Finance each see only what they may in matching, and the name-check and HR-question flows work.

Task: FE-FIN-PAYROLL-IMPORT. Build the line adapter mapping in this feature folder against the F-85 spec. Do not change `frontend/src/features/workspace`; if the frame needs a change, name it as a dependency on lane C.

SCR-09 in scope:
- Reads: `GET/POST /projects/{case_id}/payroll/requests`, `requests/{id}/inputs` (`provider_options`, `inputs[]` with `codes`, `replaces_input_id`, accepted and held status, completeness, control total), `start-choices`, `payroll/{kind}/{record_id}/working-rows` (kind is `input` or `run`; counts and codes), `GET /work/{id}/payroll-operations`, `hr-disclosures/snapshots/{id}/rows`.
- Writes: `POST /work` (`finance-payroll/v1`) with the two-step start; the input upload as multipart with `replaces_input_id`; `payroll-operations` actions for combine, match and aggregate; `POST /work/{id}/reviews` with approve, return and revoke (no Reject, which matches the board).
- Error board: show the safe readable explanation and expected sheet from the input options (E-1). Real findings come from the protected working rows.
- "Download template": E-2 says a blank JSON, CSV or XLSX template exists per provider. Wire it to that operation. If the build cannot locate the operation in the 1.24.0 contract, hide the control and list it in the build notes.

SCR-18 in scope:
- Reads: `payroll-operations` `working[]` (private matched, unmatched, conflict and held counts, E-4/E-31), name-checks (`result`, `followup`, `review`, `can_compare`, `can_route_difference`, `configured`, `attestation_sides`), `payroll/reports/{publication_id}` (`by_business_unit`, `eligible_total`, `can_acknowledge`), `payroll/questions`.
- Writes: `name-attestations`, `name-checks` (create and route to HR), `payroll/questions` (closed topics and replies), `aggregate-receipt` and report acknowledgement, and `payroll-operations` with `action: receive_hr` (E-6; offer it only when `can_acknowledge` allows).
- Access: drive every control from the API flags. A Finance reader gets aggregates and questions, never rows. Only the named recipient opens or acknowledges a report. Show 403 as "not admitted" and 404 as "not found", never as an empty shell.

Out of scope (hide, per D-182, and say so in the spec): the per-person HR record text ("Left 30 Sep") and the conflict reason; any match summary not in `working[]`; the "expected X, found Sheet1" wording beyond what E-1 supplies. SCR-37 (F-109), SCR-59 (F-110), SCR-57 (F-107) and the SCR-13 visibility editor are separate features.

Rules the builder must keep:
- No unknown BU share shown as 0. An unmatched row has no zero BU entry (E-5). Do not show staff counts to a recipient.
- No payroll rows or staff names in logs, error text, cache keys, query strings or analytics.
- Do not show a group projection of payroll rows. Group disclosures exclude names and pay (E-26).
- Use idempotency and operation keys on every write, and send the current `revision` or `expected_revision`.

## Risk
High. The screens read and write restricted payroll rows, staff names and match results (restricted-payroll invariant, E-3, E-26, E-30). They rely on per-record 403/404 and on viewer flags, so a client-side leak or a wrongly shown control is a security failure. SURFACES are ui, api, security and auth. No money is moved here: payroll release is F-110 and SCR-37 is F-109. The merge goes to the merge batch. Reviewers should confirm that no restricted data is exposed to non-admitted roles, and that a Finance reader sees aggregates only.
