DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Re-rated after F-62 merged (156996538, PR #106, `src/features/work-list`) and F-125 (f875e594, guard so live rows show the error card). The earlier NOT-READY gate (unmerged adapter) is cleared.
- One outcome: SCR-01 My work on live GET /work, API 1.24.0+, read-only. Fits one PR. SCR-01 is 9 boards (5 desktop states plus phone), one over the 8-board guide, accepted as one list view. No split needed. If the builder finds the count/limit work spreads, split "counts and rows per page" into a second PR.
- D-185 switches back on what D-182 hid: reference, kind, station, owner, per-tab counts, state filter and rows per page now have live answers (A-6 to A-10). Fewer deviations from the boards than in the r0 note.
- Sequencing: F-88 (Unassigned tab, `?assign=`) may also edit `src/features/my-work`. Land F-88 or F-63 first, and the second rebases. Do not build both at once in the same files.
- Not re-verified here (no shell in this pass): `design.py check`, architecture approval of FE-CONNECT-1, and that `src/features/work-list` is present in the builder's checkout (it was not in the `/Users/Hunchoo/psl-factory/frontend` tree I could read, so that checkout may be stale). The builder confirms all three before the spec and stops if any fails.

## Scope
Task FE-CONNECT-1 (part 2). Route `/my-work` stays. No backend or contract changes.

Endpoints: GET /work (`queue`, `line`, `q`, `project`, `state`, `page`, `limit`), GET /work/counts, GET /lines for the line filter, items open at `/work/{id}` by integer id.

In:
- The 8 live tabs on `queue=needs_me|waiting|mine|active|decisions|exceptions|unassigned|verified`, default `needs_me`. `waiting_on_others` becomes `waiting`, `done` becomes `verified`. New tabs `mine` ("Started by me"), `active`, `decisions`, `exceptions` take labels from the design wording, or the backend's own words if the boards have none.
- Rows through the F-62 adapter (reuse, do not fork; adapter changes go through a small separate change, not copies): title, line title resolved from `lines[]` by key (A-9), state tag with `status_label`, `owner` (null shows "Unassigned"), `reference` (A-6), action kind tag Decide/Do/Fix/Started (A-6), station name with index (A-6), "Started" from `started_at` and "Last updated" from `updated_at` (A-10), sample flag.
- Per-tab counts and the "records you can see" total from GET /work/counts (A-7). Show only counts the response marks complete, or the number actually observed with its coverage wording. An unknown count is never shown as 0.
- State filter via `state` (A-7). Rows per page limited to the values the API accepts: 8, 10, 15, 20, 50 (the board's 10, 20, 50 are valid) (A-8).
- Search (`q`, 120 characters maximum), line filter, project filter.
- "Show more" keeps asking past empty pages until it has rows or `next_page` is null (A-8: up to two empty pages are skipped server-side, an empty page is still possible). Coverage (`limited`, `evaluated`, `deferred`) and `as_of` ("Updated hh:mm") shown honestly.
- Desktop, phone, empty ("caught up"), filter, lead (Unassigned tab) and loading/error states. Access to Unassigned is the server's answer, not a client role check. Keep F-125's guard that live rows show the error card.

Out, hidden and recorded as deviations from the boards (seen by the client at acceptance): the waiting-on filter (no live parameter), agent avatar (only the Assistant persona for the person's own chat; do not invent agents), "While you're free" suggestions (BQ-21, no live source), `payroll_questions`, the in-place assign-PM write (belongs to F-88, SCR-24). Also out: `/role-dashboard` heading, decisions and team sections, `/role-work` actions. These are deferred to a later feature. Station bar: draw it only if the board's index/count are in the row; otherwise show the station name alone and record it.

Dependencies: F-62 merged (done). F-125 merged (done). Coordinate file overlap with F-88 as above.

## Risk
Medium. It is a cross-layer contract change (v7 row shape, queue renames, paging and counts moved to live GET /work and /work/counts) on the main work screen, over shared code from F-62 (`src/features/work-list`) and `src/features/my-work`, with a possible file collision with F-88. It is read-only with no money, identity or data writes, so not high. Product acceptance is required because new tabs and labels, hidden board parts and coverage wording change what the client approved (delivery/connect/screens-a-frame-core.md SCR-01; D-182, D-185); routine batch-delegation under D-184 may apply for board changes already accepted in batch, but the new tab wording and the counts' coverage display are new.
