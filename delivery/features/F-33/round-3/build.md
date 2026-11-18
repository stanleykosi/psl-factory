STATUS: READY
COMMIT: d20fd9b2ccee7be267936cc2758358989ecdedbb
BUILDER: builder
LANE: full

## Summary
- The returned and rejected quote is now the problem callout (signal tint and ink). The tone is set from data on the income line only: a `stopped` station, or a `stopped` or `uncertain` status tone. Every other line's banner is unchanged.
- Chidi's card now carries its own footer row, "Started 11:20" and "Ask Chidi", through an optional `foot` on `AgentCard` (`psl-agent__foot`). The Ask Chidi link is no longer drawn under the main column.
- In the Decide panel, the note label is "Note" followed by the muted regular `psl-opt` text "(needed to return or reject)". The steps' consequences are the panel's small print, muted at the hint size (13px).
- Starting an inline decide clears earlier step and decision notices, so the decide always shows its own outcome or "result not confirmed".
- The W-2702 fixture family's Reject step now sends a `consequence` as returned text. New fixture W-2712 answers every decide with `work_state: effect_uncertain`, so QA can see that state in a browser.

## Changes
- `frontend/src/features/workspace/Workspace.tsx`
  - `bannerTone(workspace, item)`: a new income-line branch. The issue line and all other lines keep their exact expressions.
  - `LineAgent` builds the card footer (started time, plus the workspace's `assistant` link).
  - `splitAsk` moves that one link out of `WorkspaceLinks` on the income line only, and only while the agent is working.
  - `onDeciding` clears `flow` notices and `decided` when a decide is sent.
- `frontend/src/features/work-item/WorkItemOverview.tsx`: `AgentCard` takes an optional `foot`, rendered as `psl-agent__foot` inside the card. Without it the card renders exactly as before.
- `frontend/src/features/workspace/InlineDecide.tsx`
  - Note label is `Note <span className="psl-opt">(needed to …)</span>`.
  - Consequences sit in `.ws-idecide__after`.
  - Calls `onDeciding()` before each decide.
- `frontend/src/features/workspace/workspace.css`: the `.ws-idecide__after` muted hint-size rule, and the footer link (weight 600; 44px tall on a phone). Tokens only.
- Fixtures:
  - Reject step consequence "Rejecting stops this schedule: it isn't used for October's accounts." (backend sample text) on W-2702, W-2705, W-2707, W-2708 and W-2703.next. W-2711's malformed step carries it too; it is not drawn.
  - New W-2712 with `W-2712.approve|return|reject.json`, each `state: effect_uncertain`, status "DECISION NOT CONFIRMED" (`uncertain`).
  - The mock serves `<id>.<verdict>.json` and answers `work_state` from its state, so no server change was needed.
- Tests: `tests/income-schedule.test.tsx` (+7 tests, 44 in total) and `tests/income-schedule-mock.test.ts` (12 items, the W-2712 sidecars, and a W-2712 decide test).
- Factory files: `fidelity-exceptions.json` has the SAMPLE DATA authority fixed and 8 per-board waivers with round-3 scores. Fidelity output is in `round-3/fidelity/`.

## Fixes
- UI-2-1 | d20fd9b2 | The returned and rejected quote is the `problem` callout. On the income line the tone comes from a stopped station or a stopped/uncertain status tone, never from the words. A test shows W-2703 and W-2702.reject draw `psl-callout--problem` and W-2704 draws none. A regression test shows other lines unchanged: weekly W-2209 is warning, issue W-2412 is problem, issue W-2414 is success, and minutes W-2304 and document review W-2901 have no banner.
- UI-2-2 | d20fd9b2 | "Started 11:20" and "Ask Chidi" are in the card's `psl-agent__foot`. There is one Ask Chidi link, with href `/assistant`, 44px tall on a phone. The fidelity side-by-side matches the board's footer.
- UI-2-3 | d20fd9b2 | The note label is "Note" plus the muted regular `psl-opt` "(needed to return or reject)", as in F-16. The approve and reject consequences are muted at 13px (`--text-hint-size`, `--ink-muted`).
- TECH-2-1 | d20fd9b2 | A decide clears the step notice and the previous decision notice when it is sent. Tests:
  - a step's done notice, then Approve, shows "Schedule v1 is approved" and the step notice is gone;
  - the same sequence on W-2712 shows "Schedule v1: result not confirmed".

  Both fail on the round-2 source.
- UX-2-2 | 0d01b4b6 | The Reject step sends its own `consequence` as returned text in the fixture, and the page draws it like the Approve one. A test shows that a Reject step with no consequence draws none: the frontend composes no wording.
- UI-2-4, UI-2-6 | (factory file) | Each of the 8 waivers now names that board's own remaining gaps. Both returned waivers name: the green "Correct and resubmit" (F-22 rule), the white stopped station in the joined strip, and on the phone the outlined stopped segment. The phone waivers no longer share one sentence.
- UI-2-5 | (factory file) | The SAMPLE DATA exception cites design decision 14 Nov 2026 (c), restated in D-92 (`authority`), instead of Conflicts 11.
- QA request | 0d01b4b6 | W-2712 lets QA see `effect_uncertain` on approve, return or reject at `/work/W-2712` on the mock. Its mock test confirms each decide answers 200 with `work_state: effect_uncertain` and that the re-read is `effect_uncertain`.

## Acceptance criteria
Unchanged from round 1 and still met. Criteria 9, 14 and 19 are strengthened:
- 9 and 14: an unsettled effect is never an outcome, and W-2712 shows this in the browser.
- 19: fidelity was rerun this round (below).

## Validation
- `npx vitest run tests/income-schedule.test.tsx tests/income-schedule-mock.test.ts tests/mock-contract.test.ts`: 349 passed.
- The round-3 tests run against the round-2 `src` (stash): 6 fail (UI-2-1, UI-2-2, UI-2-3, UX-2-2, and both TECH-2-1 tests). The other-lines banner regression and the W-2712 flow pass on both, as intended.
- `npx vitest run` on workspace, workspace-step, issue-detail, minutes, minutes-end, work-item, work-item-board, document-review, decide and the weekly tests: 11 files, 446 passed.
- `bash /Users/Hunchoo/psl-factory/delivery/checks.sh`, run under the shared lock with load 13.5: exit 0.
  - Django check found no issues.
  - Lint, typecheck and build succeeded.
  - 102 test files, 2320 tests passed. No flakes.
- `cd frontend && E2E_PORT=4881 MOCK_PORT=4880 npx playwright test e2e/income-schedule.spec.ts e2e/workspace.spec.ts e2e/response.spec.ts e2e/finance-month-end.spec.ts`: 105 passed (2.7 min).
- Fidelity: one run this round, on a production build (`API_ORIGIN=http://127.0.0.1:4880 FRAME_FIXTURES=1`, fresh mock, persona finance_lead), using `round-3/fidelity/run.sh`.

| Board | Coverage | With exceptions | Visual |
|---|---|---|---|
| SCR-54-desktop-investigating 1440 | 83.3 | 100 | 88.1 |
| SCR-54-desktop-review 1440 | 88.9 | 100 | 76.9 |
| SCR-54-desktop-returned 1440 | 75 | 100 | 73.3 |
| SCR-54-desktop-verified 1440 | 87.1 | 100 | 76.1 |
| SCR-54-mobile-investigating 390 | 77.8 | 100 | 84.5 |
| SCR-54-mobile-review 390 | 75 | 100 | 80.9 |
| SCR-54-mobile-returned 390 | 71.4 | 100 | 83 |
| SCR-54-mobile-verified 390 | 66.7 | 100 | 85.1 |

All 8 boards have per-board D-83 waivers (each at least 70), pending the design engineer.

## Open
- UI-2-7 and the frame's phone History link (42x24) go to a frame follow-up.
- UX-2-1: the hold's "See all exceptions" button comes from the shared frame, which draws it for every exception state (`setup_needed` included). It was left as is; the frame owner should confirm.
- E-TASK-DECIDE has no idempotency key (round-1 security note, for the backend).
- All exceptions and waivers are "builder proposal, pending design engineer".
