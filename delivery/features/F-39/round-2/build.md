STATUS: READY
COMMIT: c706d6a7df4ca8eef92acd420d371e5ab484f7b3
BUILDER: builder
LANE: full

## Summary
- Fixed the five blocking findings; the desktop NOT ESCALATED page now matches the board layout (quote in the main column, Next panel beside it, no stray decide card).
- Message v1 shows the message as the section item; tones follow the boards.
- Added 3 tests (round 2 describe); two fail on the old code, the message one fails on the old fixtures.

## Changes
- frontend/src/features/work-item/WorkItemOverview.tsx: escalation line hides its decide task card in TaskPanels when already_decided or with no step on the page.
- frontend/src/features/workspace/Workspace.tsx, Sections.tsx: escalation banner tone from status tone (neutral = info, verified = success, else warning).
- frontend/mock/fixtures/work W-3602.approve, W-3602.reject, W-3603, W-3604, W-3604.next, W-3608: message as item text; MESSAGE DRAFTED tone agent; NOT ESCALATED tone neutral.
- frontend/tests/escalation.test.tsx: three new tests.

## Fixes
- UX-1-1 | desktop NOT ESCALATED layout now board-like (consequence of UI-1-1 and UI-1-3) | c706d6a7
- UI-1-1 | extra decide TaskPanels card removed on W-3601/W-3603 | c706d6a7
- UI-1-2 | message sent as item text, no "Nothing here yet." or warning | c706d6a7
- UI-1-3 | not-escalated banner uses the info tone | c706d6a7
- UI-1-4 | MESSAGE DRAFTED agent, NOT ESCALATED neutral | c706d6a7
- UX-1-2 | same change as UI-1-2 (W-3604, W-3608) | c706d6a7
- UI-1-5 | proposed exceptions added (see below) | n/a, record only

## Not done (non-blocking)
- UX-1-3 (notice says "was rejected"), UX-1-4 (shared "Nothing was sent again."), UX-1-5, UX-1-6 (phone button width, crumbs): left; they are shared copy or layout used by other lines. UX-1-4 is listed as a proposed exception.
- fidelity-exceptions.json: new PROPOSED entries (Back to the issue position, 15 DAYS LATE tag, Nothing was sent again., message text tool artefact: the tool skips text inside list items). All marked pending design engineer signature, none signed. Visual waivers re-measured.

## Acceptance criteria
1. [x] Reviewer findings above: verified in screenshots at 1440 (W-3603, W-3604) and in the new tests.

## Validation
- delivery/checks.sh under the shared lock: exit 0 (log /tmp/claude-501/chk39.log); lock released.
- vitest tests/escalation.test.tsx and escalation-mock.test.ts: 34 passed before the new tests; the new tests fail on the old src.
- Fidelity (production build, ports 4937/4936, round-2/fidelity/scores.txt), coverage after exceptions 100 on all 8. Visual: desktop investigating 87.1, decide 77.3, not-escalated 84.4, draft 80.1; mobile investigating 85.0, decide 82.3, not-escalated 75.5, draft 85.3. All below 90, so the D-83 waivers still need the design engineer's signature.
- Servers on 4936 and 4937 stopped.

## Blocked
None.
