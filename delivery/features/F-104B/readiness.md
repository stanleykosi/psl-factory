DECISION: READY
RISK: high
SURFACES: ui, api, auth, data-migration, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Part 2 of SCR-58, the ledger source reference (original build F-45). It covers duplicate and reference-correction resolutions, recheck and restart, and the lineage display, all on live API 1.25.0 or later.
- About 6 boards, within the guideline of about 8. One outcome: a person resolves a duplicate or corrects a rejected or uncertain reference, and a reviewer confirms, returns or withdraws it.
- Build-start waits (not blockers): F-104 (part 1), F-85 (shared adapter, lane C) and F-87 (`useWorkCommand` and the `Actions` slot). The coordinator holds the builder until all three are on main.
- D-187 accepted every recommended option in the part 1 specs, so F-104B inherits them: hide what the API does not supply (D-182), no pre-selected answers, evidence chosen from the read's lists, and no invented reviewers or amounts.
- Rated from the part 1 files and the lane D context. I confirmed `incumbent-resolutions` is in the live contract. I did not re-run `design.py check` or re-read `design/review.json`. The v9 package and the 13 Nov approval cover this screen, as in part 1.

## Scope
Binding for the spec writer. Task FE-CONNECT-1, screen SCR-58 part 2, route `/work/{id}`, line `ledger_sources` (W-4201..W-4213).

In:
- `GET /projects/{case_id}/incumbent-resolutions` (`claims[]`, `resolutions[]`).
- `POST /projects/{case_id}/incumbent-resolutions` with `reference_correction` or `duplicate_alias`, and the confirm, return or withdraw review. The review uses `ledger_resolution` and `ledger_resolution_review` evidence.
- `recheck` and `restart` through `POST /work/{work_id}/incumbent-reference`, with the action values taken from the generated types.
- The lineage display, shown only where the API supplies it. This includes the rejected board's "Correct" button and the "re-check reopens it" sentence on verified. Part 1 hid both.
- The adapter mapping and the form (`XxxActions.tsx` on F-87's `adapter.Actions` slot) live in this feature folder. The shared frame stays unchanged. Any frame change is a dependency on lane C.

Out:
- Everything part 1 owns: the read, the observe and review writes, the hold line, the reviewer name and date, and the `captureLedgerSource` and `startLedgerWork` client functions.
- Payroll (SCR-59), SCR-53, SCR-57, month-end, and the "refused, nothing was posted" state.
- Any amount, any posting to QuickBooks, and any call to QuickBooks.

Rules:
- Hide what API 1.25.0 does not supply, and say so (D-182).
- Unknown money stays unknown, never 0.
- No invented approvers, attempt counts, evidence ids or reasons.
- Use the exact proof or evidence route of each action. Where an action has none, the person chooses from the read's evidence list (nothing preselected, button off when empty).
- Neither revision tokens nor the idempotency key go inside `inputs` to `makeCommand`.
- Reuse part 1's mapper and keys. Do not duplicate or edit part 1's files except through its exported functions.
- About 8 boards at most. If the draw exceeds that, the spec writer proposes a part 3.

## Risk
High. Resolutions retire or alias ledger references, which is hard to undo, and the confirm, return and withdraw review is an authority control. The independent-review rule is the same as in part 1, so the `data-migration` surface reflects record retirement and lineage change, not a schema migration. The new payloads change the contract against the v7 mock (`contract-change`). The merge goes to the design engineer's batch, and the client must see the changed duplicate and recovery flows.
