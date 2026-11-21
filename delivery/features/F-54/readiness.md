DECISION: READY
RISK: low
SURFACES: ui
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: coordinator (the design engineer asked for it on 20 Nov while viewing /work/W-1408/history: "it should match how overview looks so there is no layout shift. even the table, shouldnt the row per page also be part of the table? it is different accross board which shouldnt be, i dont want the dropdown one.")

## Summary
- The work item's History tab draws a different header from Overview: the Overview / History tabs move from the top right (Overview) to under the title (History), and the state tag moves. The side column is 300px on History and 324px on Overview, so the main column changes width. Switching tabs makes the page jump.
- Paging is drawn three ways. History has a "Rows per page" dropdown floating under the table. My work has 10 / 20 / 50 buttons in its own footer. Projects and Exceptions have their own rows-per-page footer. About 14 other lists (clients, assistant conversations, setup views, alerts, record picker, payments, project tabs) use only the ShowMore bar with a fixed 50 rows and no rows choice.
- D-PAGING r2 (approved by the design engineer, 13 Nov): every list offers 10, 20 or 50 rows per page, default 20, newest first. The design engineer now adds: the paging is part of the table, it looks the same on every list, and it is never a dropdown.
- Merged screens only. No contract, data or authority change. No PSL decision is needed.

## Scope
1. The History tab uses exactly the Overview tab's header and column layout at every width.
2. One shared paging footer, drawn inside the table's frame, used by every paged list: count, rows-per-page 10 / 20 / 50 as buttons (not a dropdown), and Show more.

## Risk
Low. Shared-component change across many merged lists. The risk is an unintended visual or behaviour change, so existing tests and e2e must stay green apart from the deliberate paging change.
