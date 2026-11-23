DECISION: READY
RISK: high
SURFACES: ui, api, auth, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Part 1 only (read and record) of SCR-58, the ledger source reference (original build F-45). Duplicates and recovery are F-104B.
- About 6 boards, within the guideline of about 8, and one outcome: a user reads a ledger source's incumbent reference and records evidence and a verdict on the live API 1.24.0.
- Wait: the shared line adapter F-85 (lane C, PR #101) is not on main. This only delays the build start. The coordinator holds the builder, and the spec is written against `/Users/Hunchoo/psl-factory-main/delivery/features/F-85/spec.md`.
- Backend answer E-29 is settled and supplies the reviewer name and date and the hold code for the independent-reviewer rule.
- Rated from my earlier assessment (`readiness-proposal-r0.md`), not redone. Architecture and design approval are covered by the v9 package and the 13 Nov client approval with the D-173/D-181 exceptions. I did not re-run `design.py check` in this pass.

## Scope
Binding for the spec writer. Task FE-CONNECT-1, screen SCR-58, route `/work/{id}`, line `ledger_sources` (W-4201..W-4213). Lane D builds the adapter mapping in this feature folder and does not change the shared frame. Any frame change is named as a dependency on lane C.

In:
- Reads: `GET /work/{work_id}/incumbent-reference`. Fields: source, observation, `check_id`, `can_observe`, `has_attachment`, lineage ids, `review_options`, `latest_decision`, `verified`. Also the source `outcome` (`reported_posted` or `uncertain`).
- Writes:
  - `POST /work` (`finance-ledger/v1`).
  - `POST /projects/{case_id}/incumbent-evidence`.
  - `POST incumbent-reference` (`found|not_found|unknown|multiple`).
  - Multipart `.../observations`, and `GET .../observations/{check_id}`.
  - Approve or reject, with reason and evidence required.
- Per E-29: show the latest decision's reviewer and date. Show the stable hold code when the independent-reviewer rule blocks the person ("not the capturer, not the observer").

Out:
- Duplicate and reference-correction resolutions, `incumbent-resolutions`, `recheck|restart`, and the lineage display (F-104B).
- Payroll (SCR-59), SCR-53 and SCR-57.

Rules:
- Hide what API 1.24.0 does not supply, and say so (D-182). That covers the month-end link for ledger sources and the "refused, nothing was posted" state.
- Unknown money stays unknown, never 0.
- No invented approvers, attempt counts or amounts.
- Where a write is blocked by an unanswered backend question, build on the best reading of the contract and flag it, or hold it and list it.

## Risk
High. The screen writes evidence and approve or reject verdicts that gate a ledger reference. The independent-review rule is an authority control (`auth`). The reshaped payloads change the contract against the v7 mock (`contract-change`). The duplicate resolution that retires records is in F-104B, which lowers this part's risk but does not remove it. Merge goes to the design engineer's batch. The client must see the changed review flow, so acceptance is required.
