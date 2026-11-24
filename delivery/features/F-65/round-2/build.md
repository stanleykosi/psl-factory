STATUS: READY
COMMIT: 56da681b4e7a5d64fe233e978feb7512dfc27b48
BUILDER: builder
LANE: frontend

## Summary
- Round 2 makes two phone fixes on the F-65 factory floor; desktop is unchanged.
- The "FACTORY FLOOR · UPDATED …" line now sits above the title on phone, with the time kept.
- Station-square digits on phone use the design system's smallest text token (`--text-label-size`, 11px) instead of 10px; blank 0 squares are unchanged.

## Changes
- `frontend/src/features/overview/OverviewPage.tsx`: the phone branch renders the eyebrow before the title; the old bottom-of-page copy is removed.
- `frontend/src/features/overview/overview.css`: phone `.overview__sq` font-size is `var(--text-label-size)`.
- `frontend/tests/overview.test.tsx`: the phone test now expects the Updated line before the title.

## Fixes
- UI-1-1 | 56da681b | phone eyebrow with the updated time moved above the title, as on desktop
- UI-1-2 | 56da681b | phone station-square digits use the smallest text token (11px); blank 0 squares kept

## Acceptance criteria
1. [x] Phone eyebrow above the title: `tests/overview.test.tsx` phone case checks the eyebrow precedes the h1's header with the text "FACTORY FLOOR · UPDATED 23 Nov 10:30 WAT".
2. [x] Desktop unchanged: the desktop branch was not edited; desktop tests pass.

## Validation
- `tsc --noEmit`: clean.
- `tests/overview.test.tsx`, `overview-floor.test.tsx`, `overview-floor-reject.test.tsx`, `overview-imports.test.ts` run singly: 50 passed.
- Fidelity re-run of SCR-06-mobile-390: NOT RUN. The job was queued behind other lanes' heavy jobs through the lock and was cancelled by its PID at the coordinator's handover. The round-1 phone result stands (coverage 100% with exceptions, visual 60.6); no round-2 report exists. Re-queue `heavy-lock.sh run lane-a -- <build, next start 4986 against mock 4987, fidelity.mjs --cookies psl_mock_overview=floors --exceptions F-65/fidelity-exceptions.json --out round-2/fidelity/SCR-06-mobile-390>` to finish it.
- No servers of mine are running; worktree clean; branch pushed (head equals origin).
