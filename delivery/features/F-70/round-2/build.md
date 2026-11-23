STATUS: READY
COMMIT: ed72928f9f4da97ba1a1f0b9b64981109cc1a14f
BUILDER: builder
LANE: full

## Summary
- Round 2 fixes the one blocking QA finding: the Documents-tab e2e step expected a UUID URL, but tab links keep the id the page was opened with (P-0101). The expectation now says so.
- The full unit run and the whole projects e2e spec were run on this head.

## Changes
- `frontend/e2e/projects.spec.ts`: one expectation (line ~228).

## Fixes
- QA-1-1 | Documents-tab e2e now expects /projects/P-0101 after clicking the first tab | ed72928f9f4da97ba1a1f0b9b64981109cc1a14f

## Acceptance criteria
Unchanged from round 1; no product code changed this round.

## Validation
- `npx playwright test e2e/projects.spec.ts` against own servers (app 4970, mock 4971, production build): 28 passed.
- `npx vitest run`: 155 files, 3692 tests passed.
- Servers stopped; worktree clean and pushed.

## Not fixed
- UX-1-1 (non-blocking): fixing it needs `src/components/Tabs.tsx` (shared): when the selected key matches no tab, the first tab should keep tabIndex 0. Passing a different `selected` from ProjectTabs would wrongly mark Journey selected. Left for the coordinator or lane A.
- QA-1-2 (non-blocking): live populated list/journey still unproved; needs live-lead credentials.
