DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- The earlier gate (F-70 not merged) is cleared: F-70 is merged (PR #102, main be9d34d9). The split is accepted, so F-71 is now only the Money and Milestones tabs (SCR-12, SCR-38). That is one read-only outcome and a reviewable PR.
- FE-CONNECT-1 is the prescribed task id for connecting an already-built screen under D-180, recorded as the explicit exception. SCR-12 (F-26) and SCR-38 (F-25) are built and DONE on the v7 mock.
- D-182 settles the board conflicts that are only hides (hide what live does not supply). The spec lists them and builds option 1. Product acceptance is recorded under D-184.
- Open backend questions B-16 (paid status values), B-47 (join key) and B-48 (404 without `finance.read`) do not block. The coordinator answers fix the behaviour: show the status as given, never infer paid, and never turn an unknown into 0.

## Scope
Binding for the spec writer. Reads only, on the live client pattern from F-56/F-57 and F-70.

**Money tab (SCR-12), `GET /projects/{case_id}/money` and `?figure=<key>`.**
- One row per contract stage in returned order. Do not invent a `position`.
- Amount comes from `amount`/`currency`. A null amount shows as Unknown with `missing_reason`. Null `paid` or `owed` also shows as Unknown. Unknowns are never 0 and never summed into a known total.
- Per invoice: reference, `status` text exactly as given (B-16), `paid` and `owed` as given.
- Drill-down "where this figure comes from" reads `items[].sources[]` through `?figure=`. Show `as_of` and the `limited` warning.
- Route `/projects/[caseId]/money`. Files: `MoneyTab.tsx`, `moneyModel.ts`, `useMoney.ts`.

**Milestones tab (SCR-38), `/money` joined with `GET /projects/{case_id}/milestones`.**
- Take the milestone rows from `/money` items: name, amount, `due_date`, `completed_at`, invoices, and `changes[]` with a null `additional_amount` shown as Unknown.
- Add the "Recorded completions" section from `/milestones`.
- Join only on `items[].key` and `record_id` if the contract states it (B-47). If it doesn't, show completions as a separate list.
- For a person without `finance.read` (B-48), `/money` returns 404. Show the completions only, plus a plain "not available to your role" note. Show no figures.
- Files: `MilestonesTab.tsx`, `tabsModel.ts` (read only).

**Out of scope.**
- The mark-complete write (SCR-19, F-50, blocked).
- change-milestone-link, commercial-response, and policy-configuration review.
- Ask Chidi with a figure context (B-20).
- The invoice, cash-lot and correction detail routes beyond the drill-down.
- Registers and Actions tabs (SCR-11, SCR-29, which are F-75).

The spec must list every part of the boards that is hidden because live cannot supply it (D-182). Examples are counts, `position`, and anything else absent from the money envelope. The design engineer sees this list. No new question is needed.

## Risk
Medium. Reads only, but it replaces typed v7 mock rows with the live `/money` shapes and the sectioned milestones tab, so `moneyModel.ts` and `tabsModel.ts` must be rebuilt on display-text states. Money display is the hazard. A null amount, `paid` or `owed` rendered as 0, or a paid state worked out from the numbers, would misstate finance. That is why the surfaces include contract-change and the spec must test these cases. Product acceptance is required because the client sees changed columns, hidden fields and new "unknown" and "not available to your role" states.
