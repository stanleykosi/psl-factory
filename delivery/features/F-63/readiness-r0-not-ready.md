DECISION: NOT-READY
RISK: medium
SURFACES: ui, api, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- The scope is sound and fits one PR once trimmed: SCR-01 My work on live GET /work, with the `/role-dashboard` heading deferred.
- It cannot start yet. The shared work-list adapter it must reuse comes from F-62. F-62 is READY but not built or merged, so the dependency is not integrated.
- Stacking on F-62's branch is not a recorded exception with limits. If the coordinator wants it, record that exception (stacked on F-62's head, rebased after F-62 merges, F-63 not merged before F-62), and this note becomes READY with the scope below.
- SCR-01 is 9 boards, one over the 8-board guide. It is accepted as one list view. Anything extra, including `/role-dashboard`, stays out.
- Backend questions A-6 to A-10 are open. Per D-180 they do not block: build on the best reading and flag them. Unknown counts are never shown as 0.
- Not re-verified in this note: `design.py check` and architecture approval of FE-CONNECT-1. The builder confirms both before the spec and stops if either fails.

## Scope
Task FE-CONNECT-1 (part 2). Endpoints: GET /work (`queue`, `line`, `q`, `project`, `page`), GET /lines for the line filter, and open an item at `/work/{id}` by integer id. No backend or contract changes. Route `/my-work` stays.

In:
- The 8 live tabs on `queue=needs_me|waiting|mine|active|decisions|exceptions|unassigned|verified`, default `needs_me`. Renames: `waiting_on_others` becomes `waiting`, `done` becomes `verified`. New tabs `mine` ("Started by me"), `active`, `decisions` and `exceptions` need a label from the design wording.
- Search (`q`, 120 characters maximum), line filter (`line` key, titles from `lines[]`, A-9 reading) and project filter (`project` UUID).
- Rows through the F-62 adapter: title, line title, state tag from `state` with `status_label`, `owner` (null shows "Unassigned" on that tab), `updated_at` as "Last updated" (A-10 reading, not age), sample flag.
- "Show more" that keeps asking past empty pages (A-8 reading, fixed 8 rows). `limited`, `evaluated` and `deferred` coverage, and `as_of` ("Updated hh:mm"), shown honestly.
- Desktop, phone, empty ("caught up") and loading or error states for the 9 boards.
- Lead view: the same list, the Unassigned tab and its access as the server returns them. The access rule is the server's, not a client role check.

Out, hidden and not zero (recorded deviations from the approved boards, seen by the client at acceptance): per-tab counts and the "34 records you can see" total (A-7), reference (A-6), Decide/Do/Fix tag (A-6), station bar (A-6), agent avatar, state and waiting-on filters, "rows per page" (A-8), "While you're free" suggestions, `payroll_questions`, and the assign-PM write (F-36 moved paths). Also out: `/role-dashboard` heading, decisions and team sections, `/role-work` actions. These are deferred to a later feature.

Dependency: F-62's adapter must be merged first. Do not copy or fork it. If the adapter needs changes for SCR-01, make them in F-62, not here.

## Risk
Medium. It is a cross-layer contract change (v7 row shape, queue renames and paging to live GET /work) on the main work screen, built on code shared with F-62. It is read-only, with no money or data writes, so it is not high. Product acceptance is required because hidden counts, tags, filters and the station bar change what the client approved (delivery/connect/screens-a-frame-core.md, SCR-01; delivery/features/F-62/readiness.md).
