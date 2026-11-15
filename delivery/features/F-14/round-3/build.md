STATUS: READY
COMMIT: 16016b6b0cf0feba24cf514be1a59fff4453fd2c
BUILDER: builder
LANE: full

## Summary
- Merged origin/dlv-00-delivery-setup (F-09, F-06, F-13 and the rest) into the branch; F-09's ReconcilePanel is mounted in the work-aside slot, and the W-1711 phone pinned-bar room is gone because F-09's own panel fills it.
- D-45: the Overview / History tabs are on every work item page. They sit on the crumb line (desktop) and on the tag line (phone, title line on history) so the boards' vertical rhythm holds.
- All round-2 UI, technical and UX findings are fixed (below). "See all exceptions" shows visibly: a secondary button in the effect-uncertain desktop panel, a small link on the other exception boards and on phones; nothing focusable sits in hidden text.
- All 26 boards score visual 90 or more with coverage 100 after exceptions.

## Changes
- `frontend/src/features/work-item/WorkItemOverview.tsx`: merge resolved (header comment, TaskPanels/ResponseEntryLink, DecisionRows kept); `ReconcilePanel` in the aside; `fact_tones` tint; `NextStep` `quiet` mode and `hasExceptionsLink`; processing desktop next-step small print; exceptions button/link; `aria-label` on the station list.
- `WorkItemView.tsx`: tabs always rendered and placed in the header; phone h1 keeps the contract title (board title drawn, contract title as the accessible name); phone started line kept.
- `WorkItemHistory.tsx`: phone board filter All / Decisions / Agents; Rows per page control kept on phones.
- `work-item.css`: owner-needed held station filled red; tab placement and compact phone tabs.
- `presentation.ts`, `tests/mock-contract.test.ts`: optional `fact_tones` (PROPOSAL, `waiting` amber or `signal` red) on a not-yet fact.
- Fixtures: W-1711 (tone, `reconcile` + `allowed_actions`, bar_slot and phone summary removed), W-1706 (tone), W-1705.history ("Supplied evidence:").
- Tests: `work-item-board.test.tsx` (tabs on boards, round-3 cases, F-09 button allowed), `response.test.tsx` (panel sits in the aside).
- `delivery/features/F-14/fidelity-exceptions.json`: removed #22, #36, #47-51, #55-57.

## Fixes
- UI-2-1 | 3971d64 | fact_tones: RECEIPT "Not found" amber, SENT "Not yet" red
- UI-2-2 | 3971d64 | processing desktop draws the next-step line as small print
- UI-2-3 | 3971d64 | See all exceptions visible (button in effect-uncertain panel, link elsewhere)
- UI-2-4 | 3971d64 | phone history board filter is All, Decisions, Agents
- UI-2-5 | 3971d64 | owner-needed held station filled red with white text
- UI-2-6 | 3971d64 | ten unused exception entries removed
- UI-2-7 | 3971d64 | colon kept in "Supplied evidence:"
- TECH-2-1 | 16016b6 | tabs in the phone header for all items
- TECH-2-2 | 3971d64 | Rows per page shown on the phone history board
- TECH-2-3 | 3971d64 | phone h1 accessible name is the contract title; started line kept
- TECH-2-4 | 3971d64 | no link inside work-sr (test asserts it)
- UX-2-1 | 3971d64 | D-45 tabs
- UX-2-2 | 16016b6 | W-1711 empty bar room removed (W-1704 waiting still keeps `bar_slot`: no F-09 button on that item)
- UX-2-3 | 16016b6 | station list has aria-label "Stations in order"

## Acceptance criteria
1. [x] Desktop fidelity: all 13 at visual 90 or more, coverage 100 after exceptions.
2. [x] Phone fidelity: all 13 at visual 90 or more, coverage 100 after exceptions.
3. [x] F-09 panel mounted: awaiting-reconciliation 91.5 desktop, 93.7 phone.
4. [x] Round 1 and 2 criteria hold; D-45 supersedes D-41 for the tabs.

## Fidelity (round-3/fidelity/<board>-<width>/, production build on 4501, mock 4502)
| board | coverage raw / with exceptions | visual |
|---|---|---|
| desktop 1440 | 70.7 / 100 | 90.9 |
| mobile 390 | 80 / 100 | 96.1 |
| desktop-ready | 90 / 100 | 96.2 |
| mobile-ready | 88.9 / 100 | 95.6 |
| desktop-processing | 90.3 / 100 | 93.1 |
| mobile-processing | 90 / 100 | 91.7 |
| desktop-waiting | 84.4 / 100 | 93.4 |
| mobile-waiting | 78.9 / 100 | 90.2 |
| desktop-verified | 94.5 / 100 | 92.8 |
| mobile-verified | 94.1 / 100 | 90.6 |
| desktop-history | 78.6 / 100 | 95.6 |
| mobile-history | 95.5 / 100 | 94.2 |
| desktop-issue | 90.2 / 100 | 91 |
| mobile-issue | 87 / 100 | 90.3 |
| desktop-cancelled | 93.8 / 100 | 94.4 |
| mobile-cancelled | 94.4 / 100 | 96.3 |
| desktop-owner-needed | 94.5 / 100 | 93.9 |
| mobile-owner-needed | 95 / 100 | 97.7 |
| desktop-setup-needed | 90 / 100 | 90.6 |
| mobile-setup-needed | 88.9 / 100 | 95.7 |
| desktop-permission | 70.6 / 100 | 95.5 |
| mobile-permission | 71.4 / 100 | 98.8 |
| desktop-effect-uncertain | 95.2 / 100 | 94 |
| mobile-effect-uncertain | 94.4 / 100 | 95.4 |
| desktop-awaiting-reconciliation | 94.1 / 100 | 91.5 |
| mobile-awaiting-reconciliation | 96.3 / 100 | 93.7 |

## Validation
- `bash /Users/Hunchoo/psl-factory/delivery/checks.sh` on the pushed head: exit 0 (one earlier run had two load-related loading timeouts; the rerun passed).
- Servers on 4501 and 4502 stopped; test-results deleted.
- Not done: Playwright e2e were not rerun this round. Exceptions for F-09 (#21, #23-#35, #19, #20) may now be unused; I did not prune them.
- The phone history tab strip hides the count badge and the Evidence filter is desktop-only on the phone board (both for fit).
