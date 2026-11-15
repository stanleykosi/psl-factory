STATUS: READY
COMMIT: c26c9f34deee37f0078dbc4f852fec363bf35f6c
BUILDER: builder
LANE: frontend

## Summary
- The desktop Overview/History tabs and the header sub-line now sit in one flex group, so "revision N" on items without `started_by` stays visible (TECH-3-1).
- "See all exceptions" is a secondary button: inside the item's own panel on desktop (owner-needed, setup-needed, effect-uncertain), below the content on the phone and under F-09's reconcile panel. The phone button is at least 44px high.
- 15 unused fidelity exceptions removed (47 to 32).
- All 26 SCR-02 boards pass at 100% coverage after exceptions and visual 90 or more.

## Changes
- `frontend/src/features/work-item/WorkItemView.tsx`, `work-item.css`: `.work-crumbright` group holds the sub-line and tabs (no absolute positioning; same row height and tab position as before).
- `frontend/src/features/work-item/WorkItemOverview.tsx`: `inPanel` (desktop, exception state, not awaiting-reconciliation) draws the button in `StatePanel`; elsewhere the link is a `psl-btn--secondary work-exceptions` button; phone `.work-exceptions` has `min-height: 44px`.
- `frontend/e2e/work-item-board.spec.ts`: new test, /work/W-1002 at 1440: the "revision" sub-line and the tabs are both visible and their boxes do not intersect.
- `delivery/features/F-14/fidelity-exceptions.json`: removed #19, #20, #22 to #34 (kept #21).

## Fixes
- TECH-3-1 | c26c9f3 | tabs and sub-line in one group; e2e test added
- UI-3-2 | c26c9f3 | secondary button in the panel (desktop) or below content (phone, F-09 panel)
- UX-3-1 | c26c9f3 | phone button min-height 44px (CSS; height not measured in a browser)
- UI-3-1 | this commit | 15 exceptions removed

## Acceptance criteria
1. [x] Desktop fidelity: 13 of 13 pass (table below).
2. [x] Phone fidelity: 13 of 13 pass.
3. [x] Exceptions limited: file reduced to 32 entries.

## Fidelity (round-4/fidelity/<board>/, production build on 4501, mock 4502)
| board | visual | board | visual |
|---|---|---|---|
| desktop | 90.9 | mobile | 96.1 |
| desktop-ready | 96.2 | mobile-ready | 95.6 |
| desktop-processing | 93.1 | mobile-processing | 91.7 |
| desktop-waiting | 93.4 | mobile-waiting | 90.2 |
| desktop-verified | 92.8 | mobile-verified | 90.6 |
| desktop-history | 95.6 | mobile-history | 94.2 |
| desktop-issue | 91 | mobile-issue | 90.3 |
| desktop-cancelled | 94.4 | mobile-cancelled | 96.3 |
| desktop-owner-needed | 90.4 | mobile-owner-needed | 97.5 |
| desktop-setup-needed | 92.8 | mobile-setup-needed | 95.5 |
| desktop-permission | 95.5 | mobile-permission | 98.8 |
| desktop-effect-uncertain | 94 | mobile-effect-uncertain | 95.4 |
| desktop-awaiting-reconciliation | 92.1 | mobile-awaiting-reconciliation | 93.6 |

All 26: pass true, coverage with exceptions 100. Desktop boards were scored at the desktop code state; the phone boards were re-scored after the last code change (desktop-only `inPanel`), which does not affect desktop.

## Validation
- `bash delivery/checks.sh` on the pushed head: exit 0 (856 tests). An earlier run under heavy machine load had 3 loading timeouts; passed on rerun.
- New e2e test passes on 4501/4502. Other Playwright e2e were not rerun.
- Servers on 4501/4502 stopped; test-results deleted.
