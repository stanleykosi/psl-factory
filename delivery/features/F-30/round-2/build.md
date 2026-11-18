STATUS: READY
COMMIT: 48ba8f7a6f3cf40c6e185d87dfe9ff4fbabd4c83
BUILDER: builder
LANE: full

## Summary
- Round 2 fixes UI-1-1 to UI-1-5 and UX-1-1; UI-1-6/1-7/1-8 exceptions and waivers are left pending for the design engineer.
- Full `delivery/checks.sh` passed (exit 0) at this head.

## Changes
- Fixtures: W-2411 tone `uncertain` (waiting tag), W-2412 tone `stopped` (red); BLOCKS fact carries `status: blocked`.
- `WorkItemOverview.tsx`: no "See all exceptions" button above the issue_followup workspace.
- `Workspace.tsx`/`Sections.tsx`/`workspace.css`: pinned phone bar when the only control is "Set an owner"; on the issue line the facts section is a strip under the title on desktop (list on phone), blocked fact tinted from `status`, agent note in the side column.
- `WorkItemView.tsx`: severity from a facts item drawn as a tag beside the status; phone/desktop back link "Project" to /projects/<case_id> on the issue line only (other work items keep "Queue").
- Tests: issue-detail.test.tsx (tag, strip, no exceptions button, side note), e2e phone back link.

## Fixes
- UI-1-1 | 48ba8f7a | fixture tones
- UI-1-2 | 48ba8f7a | exceptions button removed on the issue line
- UI-1-3 | 48ba8f7a | `ws-decide--info` only without steps and without assign candidates
- UI-1-4 | 48ba8f7a | facts strip on desktop
- UI-1-5 | 48ba8f7a | agent note in side column
- UX-1-1 | 48ba8f7a | "← Project" on the issue line
- TECH-1-1 | not changed (non-blocking, documented)

## Validation
- `bash delivery/checks.sh` exit 0. Targeted vitest (workspace, work-item, board, issue, mock-contract, weekly, minutes) green; work-item-board had two load timeouts once and passed alone (81/81). e2e not re-run this round.
- Fidelity (production build, 4831/4830, `round-2/fidelity/scores.txt`), coverage with exceptions 100 on all 8; visual: desktop 74.3 / 88.4 / 85.2 / 87.2, phone 81.9 / 84.6 / 89.9 / 68.5. Desktop default dropped from 79.3 (page is now taller: tab bar plus strip). mobile-verified stays at 68.5: the remaining gap is approved content (item title, long sentence, Next panel, "DONE" bar), so it still needs the one-board floor exception (UI-1-8).
- Not fixed and still pending: UI-1-6, UI-1-7, UI-1-8; UX-1-2..4 (non-blocking).
