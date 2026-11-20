# F-54 One paging footer inside the table, and History laid out like Overview

Task: FE-PAGING-CONSISTENCY (coordinator-defined, at the design engineer's request on 20 Nov; see readiness.md). No endpoint, contract or data change. Rules: D-PAGING r2 (10 / 20 / 50 rows per page on every list, default 20, newest first) plus the design engineer's 20 Nov direction: the paging is part of the table, identical on every list, never a dropdown. Design check passes under EXCEPTION D-89 as for F-53; this decision supersedes the boards' separate paging footers and the History tab's separate header.

## Rules
- Use and extend shared components in `frontend/src/components` only. Build ONE shared paging footer (extend `ShowMore`, or a new shared component that replaces it, plus a `Table` option to draw it inside the table frame). Every list uses it; no list draws its own paging markup or CSS.
- The footer, left to right: the count ("20 of 74 showing", "All 74 showing", or "20 showing" where the total is unknown), then "Rows per page" with 10 / 20 / 50 as a segmented button group (the shared Segmented look, not a Select), then the Show more button when there is more. At phone width it wraps; every target is at least 44 by 44 px.
- Changing rows per page keeps the current filter and sort, reloads from the first page and keeps keyboard focus on the chosen option. Where a list keeps the choice in the URL today (My work `limit`), keep doing so.
- Lists drawn as cards on phones (History, My work) put the same footer directly under the last card, in the same frame style.
- Don't change wording, data or behaviour beyond paging and the History layout.

## Acceptance criteria
1. The work item History tab (/work/[id]/history) uses the same header as Overview at 1440 and at 390: same breadcrumb row, title line, state tag and Overview / History tabs in the same position. The column grid is identical (same main column width and side column width and gap). — verify: screenshots of /work/W-1408 and /work/W-1408/history at 1440 and 390 attached to build.md, plus an e2e that measures the tabs' and main column's bounding boxes on both tabs and asserts they are equal (within 1px).
2. One shared paging footer exists in `frontend/src/components` with count, 10 / 20 / 50 segmented rows-per-page, and Show more, and `Table` can draw it inside its frame (the table's border encloses the footer). It has unit tests for: count text with and without a total, default 20, changing rows per page, Show more busy state, and no Show more when all rows show.
3. Every paged list uses that footer and nothing else: work item History, My work, Projects, Exceptions, Clients, assistant Conversations, project tabs (TabParts), Setup Rules, Templates, Delegation, Finance rules, Delivery rules (and SetupFrame), Notifications, the start-work record picker and Payments. No "Rows per page" Select remains, and no list keeps its own paging CSS. — verify: `grep -rn "Rows per page" src/features` shows no Select; `grep -rn "psl-showmore\|historyfoot\|exc-foot\|my-work__rows" src/features` shows no per-list paging styles; a lint or unit check is optional.
4. Lists that paged client-side at a fixed 50 now offer 10 / 20 / 50 with default 20 (D-PAGING r2). Lists paged by cursor pass the chosen size to the existing `limit` parameter they already send; no contract change.
5. Keyboard: the rows-per-page buttons are reachable by Tab and work with arrow keys like the shared Segmented; after a change, focus stays on the chosen option. On phones every target is at least 44 by 44 px. — verify: component test plus e2e at 390 on History and My work.
6. All existing unit tests and e2e pass. Update tests only where they asserted the old dropdown, the old footer markup or the fixed 50; never weaken another assertion. — verify: checks.sh plus the e2e for work-item, my-work, projects, exceptions, setup, payments, assistant, alerts and start-work.
7. Before and after screenshots at 1440 and 390 of History, My work, Projects, Exceptions and one ShowMore list (Clients) attached to build.md.

## Out of scope
Numbered pages. Any change to data, contract, authority or wording beyond the paging footer.
