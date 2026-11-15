VERDICT: CHANGES
COMMIT: 16016b6b0cf0feba24cf514be1a59fff4453fd2c
REVIEWER: reviewer-technical
AUTHORITY: reviewer-technical

## Summary
- All four round-2 findings are fixed in code (tabs in the phone header, Rows per page on the phone board, contract title and started line kept on phones, no link inside `work-sr`).
- The merge is sound. In `WorkItemOverview.tsx` F-09's `TaskPanels`/`ResponseEntryLink`/`responseOf` and the `ReconcilePanel` mount sit in `.work-aside` before the board blocks; the single `Open the decision` link remains for tasks without a response variant. F-09's own tests should still pass (the `response.test.tsx` entry and aside cases rely on exactly these seams).
- `fact_tones` is optional on `WorkItemPresentation` and the phone block, and applies only to a `not_yet` fact; unknown keeps its own tint and the contract words stay in the text, so contract fields win. The mock-contract schema allows only `waiting`/`signal`.
- One new defect: the desktop tabs now overlap the header sub-line on every item that has no `started_by` (all F-03 fixtures and any live item without a started line). Fix before PASS.

## Findings
- TECH-3-1 | blocking | medium | frontend | On desktop the Overview/History tabs are absolutely positioned at the right of the crumb row (`work-item.css` `.work-crumbrow .work-tabs { position: absolute; right: 0; top: -8px }`), but for items without `started_by` the same row also holds the sub-line "revision N" at the right (`WorkItemView.tsx:73-74`, `!started && sub`, `justify-content: space-between`). Measured on the shared build, /work/W-1002 at 1440: tabs box x 1199-1352, y 77-109; "revision 2" box x 1295-1352, y 85-100, so the revision text sits underneath the tab box and is not visible. Affects every non-board item without a started line (W-1001..1006, W-1201 and the live items). Expected: both visible. Fix: give the sub-line room (for example put tabs and sub in one right-hand flex group, or drop the absolute position when `!started`), and add a case for a non-board item without `started_by`. Fidelity boards all have a started line or are hidden-sub boards, so none caught it.

## Verified
- TECH-2-1 | verified | `WorkItemView.tsx`: tabs are in the header for every item; on phones they close the tag line (title line on history), the trailing `{phone && tabs}` is gone. Each viewport renders the strip once (checked all four branches of the header).
- TECH-2-2 | verified | `WorkItemHistory.tsx:229` `{!side && limitControl}`: Rows per page now renders on the phone board; the compact `select` style is in the phone media block. Focusable and visible.
- TECH-2-3 | verified | h1 on phones keeps `item.title` as a `work-sr` span with the board title `aria-hidden`; the phone sub-line now uses `startedLine(item)`. Heading contains no focusable child.
- TECH-2-4 | verified | `NextStep` takes `quiet` inside the `work-sr` wrapper; the exceptions link is drawn visibly (button in the effect-uncertain desktop panel, `work-note` link elsewhere, `NextStep` link on non-board items). Nothing focusable remains in `work-sr`: the quiet station list drops `tabIndex`, `shown === 0` also drops it, and the `quiet` blocks hold no controls. The new aria-label "Stations in order" is on the list, which is fine.

## Notes
- Contract: the exceptions links point at `/exceptions` (F-06), shown only for effect_uncertain, awaiting_reconciliation, owner_needed, setup_needed, followup_needed. `fact_tones` is a PROPOSAL field and is labelled as such in `presentation.ts`.
- Tests: `mock-contract.test.ts` gains tones in the schema and, via the merge, the other features' contract bodies; nothing is skipped or weakened. The phone filter hides Evidence and the count badge on the phone board, as build.md states; the filter's roving `tabIndex` falls back to the first segment when the selected kind (Evidence) is not drawn, which is correct.
- Not run: checks (gate passed on this head). Build.md says Playwright e2e were not rerun and ~14 F-09 fidelity exceptions may be unused; not blocking.
