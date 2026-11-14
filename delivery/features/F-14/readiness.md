DECISION: READY
RISK: medium
SURFACES: ui
PRODUCT-ACCEPTANCE: not-required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-14 is FE-WORKITEM only: a design-fidelity rebuild of the merged work item page (F-03) to the SCR-02 boards at 1440 and 390 (D-26). It is conformance work to boards the client already approved (design/review.json lists SCR-02), so product acceptance is not required.
- The gates are met. FE-WORKITEM is in architecture v7 (tasks.csv:19), the frame back-link slot is merged (PR #17, D-28, `usePhoneBack` in `frontend/src/shell/AppShell.tsx`), and no business rule or decision is open. No API change is needed.
- Risk is medium: one large page with about 12 states, in shared code that F-09 also edits. Nothing sensitive. The size is controlled by the scope below, which excludes boards that other features own.
- Order with F-09: F-09 (IMPLEMENTING, held for the design engineer) edits `WorkItemOverview.tsx`. F-14 must branch from the current base and rebase onto F-09 if F-09 merges first, keeping its two additions.
- Run `design.py check` before the spec is written. My role has no shell, so I could not.

## Scope
**Outcome (one):** the work item page and its history page match the SCR-02 boards: 100% element coverage after approved exceptions and visual >= 90 at 1440 and 390, on the contract mock. Missing API data uses mock or proposal data, never omission (the F-02 round 3 rule).

**Boards (scored by the fidelity gate):**
- `SCR-02-desktop` and `SCR-02-mobile`.
- The states boards, each desktop and mobile: ready, processing, waiting, verified, issue, cancelled, owner-needed, setup-needed, permission, effect-uncertain and awaiting-reconciliation.
- `SCR-02-desktop-history` and `SCR-02-mobile-history`, because FE-WORKITEM covers history (A-HISTORY).

**In:**
1. Rebuild `frontend/src/features/work-item/**` and `frontend/src/app/work/[id]/**` (page and history page) to the boards, token variables only, using the existing v7-typed contract and mock.
2. Adopt `usePhoneBack` for the phone back link (as boards draw it), with 40px page titles. D-25 names the back link under the frame bar as the main cause of low phone scores.
3. Where a board draws something the API has no field for, add it as mock or proposal data. Type it locally and mark it PROPOSAL. Hide it when absent, as F-02 did with `suggestions`. List each such field in build.md as a contract proposal. Do not edit `architecture/**` or `src/api/**`.
4. A fidelity exceptions file `delivery/features/F-14/fidelity-exceptions.json`, provisional like F-02's D-17 file. It is proposed by the builder and confirmed by the design engineer.
5. Update existing tests (`tests/work-item.test.tsx`, e2e) so they still pass. Add tests for each new behaviour. Playwright and axe at 390 and 1440 for every state. Keep A-WORKITEM and A-HISTORY.

**Out:**
- Any backend, API, OpenAPI or business-rule change. No new npm dependencies.
- The decision page SCR-03 (F-04). D-26 gives it its own round.
- The Finance-canvas SCR-02 boards (`design/canvas/finance/project/SCR-02-*-returned|evidence-asked|evidence-supplied`). They belong to the Finance features.
- The respond route, `ReconcilePanel` content and the entry button (F-09). F-14 owns everything on the page outside those.
- `NextStep` behaviour (F-06), the shell (`src/shell/**`) and `my-work/**`.

**Order and overlap with F-09 (binding):**
- F-09 adds one `TaskPanels` branch for `task.response && task.you_can_act` (WorkItemOverview.tsx:147-162) and one `ReconcilePanel` mount near line 182. Its readiness PMO-0-6 says differences outside the panel on the awaiting-reconciliation boards are raised against F-03, so they fall to F-14.
- F-14 must keep a clear place for those two additions. It must not rename or move `TaskPanels` exports without the rebase noted in build.md.
- Whichever merges second rebases and re-scores. F-09 is high risk and held for the design engineer, so F-14 will probably be ready first. Then F-09 rebases onto F-14.
- F-09's re-score of its SCR-02-waiting and awaiting-reconciliation boards depends on F-14, because those measured 48-59 on F-03's page (D-25). The coordinator should re-run that score after F-14 merges.

**Size:** about 26 boards is larger than F-02's 9. It is still one PR because it is one page with one component tree. If the builder cannot reach 90 on all states within the round limit, split the remainder (for example, the less common states: cancelled, permission, setup-needed, effect-uncertain) into a second round on the same branch. Do not split before building.

**Task ID:** FE-WORKITEM (R-WORKITEM, D-UPDATES). **Endpoints:** E-WORK-ITEM, E-WORK-HISTORY, read only, on the contract mock.

## Risk
Medium. Many states and two viewports on a page that F-03, F-04, F-06 and F-09 build on, so a regression would be visible but is easy to verify with the fidelity tool, the existing tests and axe. Surfaces are `ui` only: no API, auth, security, data or payment change, and the existing role and permission states (permission, owner-needed) must keep rendering from `allowed_actions` and the API, not from role guesses. Precedent F-02 round 3 (delivery/features/F-02/round-3/build.md) shows the pattern and its limits: frame-owned differences (phone top bar) can hold scores under 90, and those need design-engineer exceptions rather than hacks.

## Questions
None.
