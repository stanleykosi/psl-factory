DECISION: READY
RISK: high
SURFACES: ui, api, security, auth, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- SCR-37 (payroll corrections and the HR Lead decision, restricted, 2 boards) is one outcome: HR Lead approves, returns or rejects a correction to a payroll disclosure, and the named Finance reader confirms receipt of the HR export. Task FE-FIN-PAYROLL-CORRECTIONS (v9 tasks.csv:66).
- D-PAYROLL-VISIBILITY (open, model.json:1751) does not block this screen. The v9 task lists no decision dependency. The decision covers which fields are configurable and who edits visibility (SCR-13 and SCR-57), not the correction flow. The backend enforces restricted access per person and per action (INV-RESTRICTED holds whatever is configured), so SCR-37 only renders what the API returns and admits.
- The API 1.24.0 supplies the data (E-17, E-18, E-26, E-31). Item shapes are untyped in the contract, but E-17 gives the fields, so the builder works from those and from sample responses.
- Waiting on F-85 (shared line adapter, PR #101) only delays the build start. It is not a blocker. Write the spec against F-85's spec.
- High risk: restricted payroll data and an approval write. Merge goes to the design engineer's batch.

## Scope
Outcome: on SCR-37 an authorised HR Lead sees the waiting correction requests and decides each one, and the named Finance recipient opens the HR export rows and confirms receipt.

In:
- Reads: `GET /projects/{case_id}/hr-disclosures` (`needs[]`, `disclosures[]`, `actions[]`, `proofs{}`), `.../hr-disclosures/{contract_id}` (`corrections[]`, `decisions[]`, `snapshots[]`, `questions[]`, `fields[]`, `entity`, `period`, `current_approval_id`), `.../snapshots/{id}/rows`, and `GET /projects/{case_id}/hr` for handoff metadata.
- The project-level list of waiting corrections comes from the authorised HR handoff read, `GET /projects/{case_id}/department-handoffs` (E-18). Each request is decided by opening its original disclosure.
- Item fields per E-17: needs has id, reference, version, entity, period, purpose and fields. Disclosures has id, need_id, latest_decision and created_at. Decisions has id, verdict and created_at. Corrections has id, snapshot_id, decision and successor_id.
- Writes: `POST hr-disclosures {action: decide_correction, revision, request_id, verdict approve|return|reject, successor_id, operation_key, evidence_id}`. Also `{action: correction}` to request a correction, and `POST /work/{id}/department-handoff/finance-acknowledgement {action: receive, snapshot_id, operation_key, evidence_id}`.
- Access: only the named Finance recipient opens snapshot rows. The HR role sees handoff metadata only. Correction reviews, private exports and questions keep separate permissions. Show only what the API admits and handle 403 and 404 as "not available to you". Do not infer access in the client.
- Each write uses an `operation_key`. Show the result from the server response, not an optimistic claim. Unknown values are never shown as 0.

Out (hide per the D-182 rule, and name it in the spec):
- The masked staff reference (`S-●●●41`), because no masking rule is stated. Show only what the API returns.
- The "3 corrections · 2 waiting" counts, unless derived from the read with explicit coverage.
- The "Approved 02 Nov" text, unless `decisions[].created_at` supplies it.
- HR field visibility proposals (`/setup/{case_id}/hr-field-visibility`) and scope clarification tasks. These belong to SCR-13 and D-PAYROLL-VISIBILITY.
- Name differences route through `payroll/name-checks/{id}`, which is SCR-09/SCR-18 (F-108), not this feature.
- The adapter frame (lane C owns it). Group-recipient projections are server-side only (E-26). The client must not request or render staff names, individual pay or raw payroll input for group recipients.
- Payroll run stations (E-31, SCR-59, F-110).

## Risk
High. This feature shows restricted payroll data (bank account, home address, date of birth, pay fields) and writes an approval verdict that is hard to undo. Both fall under INV-RESTRICTED and the access rules in screens-e-finance-payroll.md (SCR-37). Surfaces are ui, api, security and auth. The contract-change surface is there because item shapes are untyped, so the builder must pin them against real responses and flag any gap.

## Questions
None. If the build finds the masking rule, the counts or the decided-at text missing from the API, hide that part and list it as a presentation question for the batch.
