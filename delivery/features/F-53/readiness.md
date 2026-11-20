DECISION: READY
RISK: low
SURFACES: ui
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: coordinator (the design engineer asked for it: "yeah do that", 20 Nov)

## Summary
- F-53 is design-system conformance, part 2. An audit of main (1ada84b2) found 34 places in feature code that draw raw HTML controls or tables instead of the shared components in frontend/src/components: 22 buttons, 7 inputs, 3 tables, 1 select, 1 textarea, in about 20 files across response, rfp, workspace, my-work, assistant, work-item, start-work, setup, projects and finance/payments.
- Most of them carry design-system classes, so they look right, but they skip the components' behaviour (focus, 44px phone targets, busy and disabled states, accessible labels). Three are off-system: the WorkItemOverview table (no class), the ResponseForm radio, checkbox, datetime and select, and the assistant chips and @-mention button.
- It touches merged screens only. No contract, data or authority change. No PSL decision is needed.

## Scope
Replace each raw control or table with the matching shared component, or extend a shared component when it lacks an option a screen needs. Then add a lint rule that fails the build on a raw <button>, <input>, <select>, <textarea> or <table> in feature or app code outside src/components.

## Risk
Low. Mostly mechanical swaps. The risk is an unintended visual or behaviour change on merged screens, which is why the existing tests and e2e must stay green and the visible result must match.
