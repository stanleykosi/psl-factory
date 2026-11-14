STATUS: READY
COMMIT: df180ca0716d9a70e19bc82f5df57cce37e99aeb
BUILDER: builder
LANE: full

## Summary
- Round 2 fixes UI-1-1, UI-1-2, UX-1-1 and UX-1-2, and removes the doubled "Paid is tracked separately" line on desktop done.
- Layout and accessibility only. `useDecision.ts`, claim/decide calls, CSRF, `expected_revision`, 409/stale, uncertain effects, note rules, error mapping, `you_can_act` gating and Unknown amounts are untouched. `src/shell` and `src/features/work-item` have no diff. No existing test was changed or weakened.
- Fidelity (all 10 boards, tool re-run on the real build): scores unchanged or better. The pass/fail pattern is the same as round 1 (5 pass, 5 waived by D-56). Done boards rose to 95.2 (desktop) and 94.9 (phone).

## Changes
- `frontend/public/agents/chidi-done.png` (new, 268x380 from `design/mascots/transparent/finance-done.png`).
- `DecideStates.tsx`:
  - DoneView uses Chidi's done pose.
  - The Paid line is shown once on desktop (it stays as its own line on phones, as that board draws it).
  - A visually hidden `role="status"` line ("Your decision was recorded.") is added.
  - StaleView moves focus to its heading, and on phones renders the agent note inside the current version card (`useIsPhone`).
- `DecisionContent.tsx`: `DecideHeader` takes `focusHeading` and focuses the h1 (`tabIndex=-1`) on arrival.
- `DecideView.tsx`: the 5xx error card and the 401 view get a visually hidden h1 ("Decision").
- `decide.css`:
  - `.psl-callout.decide-next` uses `--action-tint` / `--action-ink`. The `psl-callout--success` class stays because `decide.test.tsx:194` asserts it.
  - The phone stale current card shows the Amount in mono, the marks as small muted type, and the agent as a card section with a top rule.
- `tests/decide-board.test.tsx`: 2 new tests (focus + status + done pose; 5xx h1). The Paid assertion now checks the sentence appears exactly once on desktop.

## Fixes
- UI-1-1 | 040b5e7 | next-step card on the blue agent surface with Chidi's done pose
- UI-1-2 | 040b5e7 | phone stale: agent note inside current card, mono Amount, small muted marks
- UX-1-1 | 040b5e7 | focus moves to done/stale heading; polite status line; test added
- UX-1-2 | 040b5e7 | h1 on 5xx error card and 401 view
- Paid shown twice on desktop done | df180ca | shown once on desktop

UX-1-3 left as is (D-55). The mock-fixture eyebrow-time note is unchanged.

## Acceptance criteria
1. [x] Done boards: the card is `--action-tint` with the done pose (see `round-2/fidelity/SCR-03-*-done-*/side-by-side.png`; test checks `chidi-done.png`).
2. [x] Phone stale: agent inside the current card, mono Amount, muted marks (side-by-side).
3. [x] Focus on the done heading and polite status: unit test `moves focus to the done heading...` passes.
4. [x] 5xx and 401 each have an h1: unit test (5xx); the 401 h1 is the same wrapper.
5. [x] Paid once on desktop: test counts 1.
6. [x] No test weakened: `decide.test.tsx` and `e2e/decide.spec.ts` have no diff.

### Fidelity (round-2/fidelity/<board>-<width>/report.json + side-by-side.png)
| board | width | coverage | with exceptions | visual | tool pass |
|---|---|---|---|---|---|
| SCR-03-desktop | 1440 | 91.3 | 100 | 91.1 | true |
| SCR-03-mobile | 390 | 70 | 100 | 85.0 | false (D-56 waiver) |
| SCR-03-desktop-done | 1440 | 96.4 | 100 | 95.2 | true |
| SCR-03-mobile-done | 390 | 89.5 | 100 | 94.9 | true |
| SCR-03-desktop-stale | 1440 | 82.1 | 100 | 88.2 | false (D-56 waiver) |
| SCR-03-mobile-stale | 390 | 58.3 | 100 | 78.9 | false (D-56 waiver) |
| SCR-03-desktop-not-yours | 1440 | 90.9 | 100 | 91.4 | true |
| SCR-03-mobile-not-yours | 390 | 66.7 | 100 | 84.7 | false (D-56 waiver) |
| SCR-03-desktop-own | 1440 | 81.3 | 100 | 91.6 | true |
| SCR-03-mobile-own | 390 | 50 | 100 | 77.8 | false (D-56 waiver) |

Notes: one earlier run was scored while Google Fonts was unreachable (it lowered phone not-yours and done scores); the table is from the clean re-run. Own boards are in `design/canvas/finance/project/`. Done and stale scored from frozen pages driven through the real UI (scripts from round 1, scratch copies, base on 4603).

## Validation
- `bash delivery/checks.sh` from the worktree: exit 0 (43 files, 1126 tests, next build).
- `E2E_PORT=4601 MOCK_PORT=4602 npx playwright test e2e/decide.spec.ts e2e/decide-board.spec.ts`: 41 passed. `test-results` deleted.
- Fidelity servers on 4601 to 4603 stopped afterwards.

## Blocked
Not blocked.
