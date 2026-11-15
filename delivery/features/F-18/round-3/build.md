STATUS: READY
COMMIT: 9d0fc66882834dc35d0116738d46c0bb5f12da58
BUILDER: builder
LANE: frontend

## Summary
- Lean round (D-64): fixes UI-2-1 and UX-2-1 only.
- Phone recorded states use the reviewer's CSS: Lessons heading 14/700, archive line margin 0, 12px rhythm, follow-up heading 15/700 with no top padding.
- On W-2113 the "It goes only if you send it" note is hidden when neither Send nor Edit is offered.

## Changes
- `frontend/src/features/rfp/rfp.css`: five phone rules from UI-2-1 plus the follow-up heading override.
- `frontend/src/features/rfp/FollowupCard.tsx`: `showNote={status === 'drafted' && (canSend || canEdit)}`.

## Fixes
- UI-2-1 | 9d0fc66 | phone spacing and headings
- UX-2-1 | 9d0fc66 | note hidden when no action is offered

## Acceptance criteria
1. [x] Phone fidelity (production build, mock 4622, cookie pm, exceptions, 390): coverage 100 after exceptions on both. rfp-lost 70.2 -> 83.1, rfp-unknown 86.2 -> 86.9, as predicted. Both stay under 90 for the forced reasons in round-2/review-ui.md (titles, spec-required fields, wording exceptions, UI-1-8, shell); they go to the design engineer with UI-1-7. Other boards not re-run.
2. [x] Other criteria unchanged from round 2.

## Validation
- `bash delivery/checks.sh` passes.
- `E2E_PORT=4621 MOCK_PORT=4622 npx playwright test rfp`: 30 passed.
- Fidelity output: `round-3/fidelity/SCR-16-mobile-rfp-lost-390` and `-unknown-390` (report.json, side-by-side.png only). My servers on 4621/4622 stopped by PID.
