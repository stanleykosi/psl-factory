DECISION: NOT-READY
RISK: medium
SURFACES: ui, api, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Gate missing: F-70 (project page and tab bar rewire) is still being specified and is not merged. F-71 only swaps the tab bodies, so it cannot be built or verified until F-70 has merged. The tab keys and the `/projects/{case_id}/{tab}` envelope come from F-70.
- Too big for one reviewable PR: four tabs on three different live shapes (the sectioned tab envelope, `/money` with `sources[]` and `changes[]`, and a join of `/money` with the milestones tab). The connection map rates SCR-12, SCR-11 and SCR-38 at M each and SCR-29 at S to M.
- Money tabs show amounts and paid state. Unknown must stay unknown (null amount with `missing_reason`, never 0). The paid status word is an open backend question (B-16), so those cells must be shown as given.
- Architecture and design status could not be confirmed as a gate. FE-CONNECT-1 exists in `architecture/build_model.py` as a task for the first feature (My work, work item, decide) and does not name these screens. The spec writer must confirm that FE-CONNECT-1 covers SCR-11/12/29/38 under D-180, or record that D-180 is the explicit exception.
- Proposed split below. Each part is independent of the other once F-70 is merged.

## Scope
Proposed split. The spec writer follows this as binding once F-70 has merged.

**F-71a: Money and Milestones tabs (SCR-12, SCR-38), `GET /projects/{case_id}/money`.**
- Money tab: one row per contract stage in returned order (live has no `position`; do not invent one). Amount is shown from `amount`/`currency`. A null amount renders as Unknown with `missing_reason`, never as 0. Per-invoice reference, `status` text as given, `paid` and `owed` as given (null stays Unknown). Drill-down "where this figure comes from" from `items[].sources[]` using `?figure=<key>`. Show `as_of` and the `limited` warning.
- Milestones tab: join `/money` items (name, amount, `due_date`, `completed_at`, invoices, `changes[]` with `additional_amount` null shown as Unknown) with the "Recorded completions" section of `GET /projects/{case_id}/milestones`. Join key per B-47 is unconfirmed, so join on `items[].key` and `record_id` only if the contract states it. Otherwise show completions as a separate list. A person with `milestone.complete` or `delivery.read` but without `finance.read` gets a 404 from `/money` (B-48). Show completions only and a plain "not available to your role" note, with no invented figures.
- Out: mark-complete write (SCR-19, F-50 is blocked), change-milestone-link, commercial-response, Ask Chidi with a figure context (B-20).

**F-71b: Registers and Actions tabs (SCR-11, SCR-29), `GET /projects/{case_id}/{tab}` for `registers` and `actions`.**
- Registers: render the permitted sections returned (Issues, Escalations, Changes, Emergency changes, Bid requests) with `q`, `state`, `owner`, `severity` and the shared `page`. Sections are identified by `title` until B-12 is answered, in one small mapping table that is easy to swap. Per-register counts, owner role and age are not available: omit them, never show 0. Rows link through `api_url` or the matching existing detail route.
- Actions: map the "Project actions" section (title, state text, owner name from `detail` or "Owner needed", `due` null shown as Unknown). Drop the summary counts, the "From <meeting>" line and the owner role and flags, since live cannot supply them.
- Out: all writes (record, update or close issues, assign or complete actions, create actions), because they need an `evidence_id` (B-37) and are not drawn.

Both parts: use the live client pattern set by F-56/F-57. Reads only. They need no change to the design canvas beyond dropping the fields the live API cannot fill. Those omissions are a product choice and must be listed in the spec for the design engineer.

## Risk
Medium. Both parts are read-only and cross a contract: the live `{case_id, tab, sections[], as_of}` envelope replaces typed v7 arrays, and the tab models and tag mapping (`STATE_TAGS`, `tabsModel.ts`, `moneyModel.ts`) must be rebuilt on display-text states. The money display carries the main hazard. A null amount, `paid` or `owed` rendered as 0 would be a financial misstatement, and the paid status must not be worked out from the numbers (B-16). Product acceptance is required because the client sees changed columns, dropped counts and fields (age, owner role, meeting origin, position) and new states (limited, unavailable to your role).
