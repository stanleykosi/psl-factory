DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-62a is 6 boards (SCR-14 and SCR-10, desktop, phone, empty) plus one shared adapter over GET /work. That fits one PR; SCR-01 has moved to F-63.
- Both screens are read-only and use one endpoint with a different queue. No money or data writes.
- Live GET /work cannot fill several design parts (A-8, A-9, A-37 to A-41). D-180 says build on the best reading and flag, so these are not blocking. The rules below are binding.
- Not re-verified in this note: `design.py check` and architecture approval of FE-CONNECT-1 (task exists in architecture/model.json). The builder confirms both at the start of the spec and stops if either fails.

## Scope
Task FE-CONNECT-1 (part 1). Endpoints: GET /work (`queue=verified|exceptions`, `line`, `q`, `project`, `page`), GET /work/{id} only where named below. No backend or contract changes.

In:
- Shared work-list adapter: `queue`, `page`/`next_page`, "show more" that keeps asking past empty pages (A-8 reading: fixed 8 rows, skip empties), line titles from `lines[]` (A-9 reading), `limited`/`evaluated`/`deferred` coverage and `as_of` shown, unknown is never zero.
- SCR-14 Verified outputs on `queue=verified`: title, line, owner, `updated_at` labelled "Last updated" (not "Verified at"), open the output through `output_url`, open the item at `/work/{id}` by integer id.
- SCR-10 All exceptions on `queue=exceptions`: tag from `state` (`action_needed` shown as blocked, `awaiting_reconciliation` included), `status_label` as "what is being done", `owner` (null shows "Unassigned"), `updated_at` as "Last updated", open at `/work/{id}`. Include the `blocker` text only if the row carries it.
- Desktop, phone and empty states for both. Route `/exceptions` stays; add the Verified route.

Out, hidden (not zero, not invented) until A-37 to A-41 are answered: Facts earned and Proof columns, reference column, exception-kind filter chip, open-exceptions count in the heading, "6 of 28" totals, month filter, "Leads only" wording (access-based now), and any extra per-row detail read. Each hidden part is a recorded deviation from the approved board; the client sees it at acceptance. Out of scope: SCR-01 and everything in F-63, corrections and recovery writes.

## Risk
Medium: a cross-layer contract change (v7 row shape, paging and queue renames to live GET /work) in code shared with F-63, with read-only access. Surfaces ui, api, contract-change. Product acceptance is required because hidden or relabelled parts change what the client approved (screens-a-frame-core.md, SCR-10 and SCR-14).
