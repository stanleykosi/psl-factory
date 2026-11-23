DECISION: READY
RISK: high
SURFACES: ui, api, auth, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Part 2 of SCR-54 income schedules: correct and resubmit returned rows, settle held duplicates, and export the schedule as an accounting adjustment, all on live API 1.25.0 or later.
- Build-start waits, not blockers: F-101 (part 1), F-85 (shared adapter, lane C) and F-87 (`Actions` slot and `useWorkCommand`). The coordinator holds the builder until all three are on main.
- No client decision blocks it. D-187 accepted the recommended options in the part 1 specs, and the 13 Nov design approval with the D-173/D-181 exceptions covers SCR-54. The v9 package covers the line.
- High risk: the export creates ledger-bound adjustments and duplicate settlement changes records that are hard to undo. The merge goes to the design engineer's batch.
- About 7 boards (the `export` boards, the duplicate-settlement board, the correct-and-resubmit form and their mobile twins), which fits one PR.

## Scope
Binding for the spec writer. Task FE-CONNECT-1, line `income_schedules` (W-2701 to W-2712), screen SCR-54, route `/work/{id}`. Build on F-101's adapter (`incomeSchedulesAdapter.ts`) and read mapping. Add a `IncomeSchedulesActions.tsx` form component under F-87's `LineActionsProps` shape and register it once F-87 is on main. Do not edit `src/features/workspace`, and never put revision tokens or the idempotency key in `inputs` to `makeCommand` until TECH-1-1 lands.

In (all on `POST /work/{work_id}/finance-schedule`, read from `GET` of the same path):
- Correct and resubmit: `{action, schedule_id, return_id, row_key, relationship}`, driven by `returned{review_id, rows[]}`. Use the current `expected_revision` and `case_revision` from the read.
- Settle a duplicate: `{decisions[], evidence_id, reason}` for each held duplicate (row `duplicate_state`, `duplicate_resolution_evidence_id`).
- Export as an adjustment: `{kind additive|reclassification, evidence_id}`, offered only when `can_export` is true. Show `exports[]` (id, kind, `adjustment_id`) afterwards.
- `GET/POST /projects/{case_id}/accounting-adjustments/{adjustment_id}` and the source mappings, where the contract supplies them. Check the exact shapes in `/Users/Hunchoo/psl-factory-worktrees/lane-d/contracts/psl-factory.openapi.json`.
- The inventory kind stays read only as in F-101, with no actions.

Rules:
- Evidence ids: choose from the read's `evidence[]` (or the action's own upload or proof field), nothing preselected, and the button stays off when the list is empty. Never invent an evidence id. Use F-85's `fileToEvidence` only where nothing else exists, and flag it.
- Send each write once with no automatic retry. After a network failure, 5xx or 503, re-read before offering another press, because the effect may be uncertain. 409 re-reads and keeps the person's input.
- Show only what the read supplies (D-182). "Posted to the ledger: NO" stays hidden unless a field exists. Say so in build.md.
- Unknown money stays unknown, never 0, and the page does no arithmetic on amounts.
- Any change to `frontend/mock/finance*` or payments fixtures is named in build.md for lane B.
- Questions for the batch (presentation only): none expected. Any board conflict is listed in the spec with 2 or 3 options, recommendation first.

Out: the review decision and reads (F-101), changes to the shared frame (lane C), new business rules, any invented approver, backend or contract edits.

## Risk
High. The export creates accounting adjustments that feed the ledger and the duplicate settlement decides which source rows count, so both are money-adjacent and hard to undo, and each needs evidence and revision checks (`finance-schedule` write, `accounting-adjustments`). The change also moves from the v7 mock to live bodies (contract-change) and depends on server-side role checks (auth). Source: lane D rules, connection map `### SCR-54`, F-101 readiness-proposal-r0.md.
