STATUS: READY
COMMIT: bad2bb2d
BUILDER: builder
LANE: full

## Summary
- Round 2 fixes the UI review's six blocking items and the technical review's main finding, all scoped to the RFP line.
- Review, edit and reject fixtures (W-3402, W-3403 and their next sidecars) now return "Accept selected" as secondary and no Tola note or Before review checklist. W-3401 and W-3404 (default view) keep them.
- Desktop: Tola's note sits in the side column right after Progress. The review panel names Tola once.
- Phone: tags in the stacked table keep their natural width. Desktop hides only the team-input task panel.
- Fidelity: one run, all 8 boards at 100% coverage with exceptions, visual 70.5 to 74.7, so waivers (unsigned) stay.

## Changes
- `frontend/mock/fixtures/work/W-3402*.json`, `W-3403*.json`: `accept_selected` emphasis secondary; `agent_note` and `before_review` removed.
- `frontend/src/features/workspace/Workspace.tsx`: on rfp_response (desktop) the note renders after the first `figures` section in the side column (`noteAfter`); end of column if none.
- `frontend/src/features/workspace/Sections.tsx`: "Suggested by <agent>" back to the original rule (hidden when the item has any tag), so the panel shows Tola once. This also removes the round-1 change that applied to all lines (TECH-1-2).
- `frontend/src/features/work-item/WorkItemOverview.tsx`: desktop RFP page hides only tasks with `response.variant === 'team_input'` (TECH-1-1).
- `frontend/src/features/workspace/workspace.css`: `justify-items: start` on `.ws-table--stack td[data-label]` (shared rule; affects the tag width in other stacked tables, which are left-aligned values already).
- `frontend/src/features/rfp/RfpFrame.tsx`: on the requirements page, Team input with no actionable task is plain text, not a self-link (TECH-1-4).
- `frontend/tests/rfp-requirements.test.tsx`: new tests for note order, scoped task panel, fixtures, phone tag CSS, one Tola.
- `delivery/features/F-37/fidelity-exceptions.json`: "Status" exception relabelled (review boards: missing Status control, Conflicts 4; edit/reject: shared form label, Conflicts 12); visual waivers updated to round 2 scores. All "builder proposal, pending design engineer".

## Fixes
- UI-1-1 | Accept selected is secondary in the review, edit and reject fixtures | bad2bb2d
- UI-1-2 | Tola's note moved to directly after Progress in the side column | bad2bb2d
- UI-1-3 | review, edit and reject fixtures no longer return the note or Before review checklist | bad2bb2d
- UI-1-4 | one Tola in the review panel; Status exception relabelled honestly (missing control on review boards) | bad2bb2d
- UI-1-5 | phone stacked-table tags at natural width (justify-items: start) | bad2bb2d
- TECH-1-1 | desktop RFP page hides only the team-input task panel | bad2bb2d
- TECH-1-2 | "Suggested by" rule restored to the original, no longer widened for all lines | bad2bb2d
- TECH-1-4 | Team input is plain text when no actionable task exists on the requirements page | bad2bb2d

Left: TECH-1-3, TECH-1-5 (non-blocking, behaviour correct, no change), UX-1-1 to UX-1-5 (shared drawer, validation wording, phone card and selection carry-over; they touch shared code outside this line and are low).

## Acceptance criteria
1. [x] Frame, rows, review/edit/reject flows: `npx vitest run tests/rfp-requirements.test.tsx` passes (34 tests, including 4 new that failed before the code change: note order, scoped task panel, phone tag width, one Tola).
2. [x] Fidelity (17): coverage 100% with exceptions on all 8 boards; visual under 90, at or above 70, waivers proposed (unsigned). Scores in `round-2/fidelity/scores.txt`.

## Validation
- `bash delivery/checks.sh` under the shared lock: rc=0.
- Full e2e: 813 passed, 0 failed (30.2 min).
- Fidelity, one run, production build (app 4995, mock 4994; frozen server for the register boards): desktop 74.7, mobile 70.7, desktop-review 70.5, desktop-edit 70.7, desktop-reject 71.2, mobile-review 73.4, mobile-edit 73.4, mobile-reject 72.0. Coverage with exceptions 100% on all.
- Demo left running: mock on 4994, app on 4995 (FRAME_FIXTURES build). The F-30 and F-31 stacked tables were not re-looked at beyond their passing tests and e2e.
