STATUS: READY
COMMIT: edc476370a1b20444d9807811a9d7b0a6ed2f503
BUILDER: builder
LANE: full

## Summary
- Everything from round 1 is unchanged: the Setup frame, the Rules, Finance and Delivery views, the phone layouts, the reserved tabs, the Set a rule panel with Proof, and the mock.
- QA-1-1 is fixed. If a save's re-read leaves none of the panel's rules editable (for example, the person's right was withdrawn while they were editing), the panel still closes. The outcome now appears in a page-level callout above the list, and that callout takes focus. The callout says it in plain words, for example: "Your role does not allow this. You can no longer change these rules, so the Set a rule panel has closed. Nothing you entered was saved." This works on Rules and on Finance, where a group can lose its only editable rule.
- QA-1-2 is fixed: `/__mock/reset` now restarts evidence ids at EV-1.
- Desktop fidelity was re-run: all three boards still PASS.

## Changes
- `frontend/src/features/setup/SetRulePanel.tsx`:
  - New `onEditorGone(notice)` prop and an `announce` helper. After any outcome that re-read the list (saved, rejected, unconfirmed), it checks whether any of the panel's own rows is still editable (`isEditable`). If one is, the notice stays in the panel as before. If none is, the notice goes to the view with `EDITOR_GONE` appended. A 403, 404 or 409 also gets `NOT_SAVED` ("Nothing you entered was saved."). An uncertain result does not, because whether it saved is unknown.
  - The callout markup moved into an exported `OutcomeNotice`, which focuses itself on every new notice. The panel and both views use it, so the role (`status` for success, `alert` otherwise), the tone classes and the focus behaviour are the same everywhere.
- `frontend/src/features/setup/RulesView.tsx`: a `closedNotice` state. It renders as an `OutcomeNotice` between the not-set banner and the table and aside.
- `frontend/src/features/setup/FinanceRulesView.tsx`: the same, between the count callout and the groups. Opening or closing any "Set … rules" disclosure clears it.
- `frontend/mock/setup.mjs` and `frontend/mock/evidence.mjs`: the evidence id counter moved next to `caseRevisions` in `setup.mjs`, as `nextEvidenceId()`, and `resetSetup()` sets it back to 0. `server.mjs` is untouched.
- Tests:
  - `frontend/tests/setup-rules.test.tsx` gains 2 tests:
    - Rules: every row loses `can_change` on the 403;
    - Finance: the BU totals group's only editable row loses it.
  - `frontend/tests/setup-mock.test.ts` gains 1 test (reset restarts the ids at EV-1).
  - `frontend/e2e/setup.spec.ts` gains 2 tests. Each loads the page editable, sets `psl_mock_setup=readonly`, then saves: one on Rules as admin, one on Finance as finance_lead.

## Fixes
- QA-1-1 | 9f91efe | When a save's re-read leaves the panel no editable rule, the outcome message moves to a page-level callout above the list (Rules and Finance) and takes focus. It explains that the panel has closed and nothing was saved. Unit and e2e cover the readonly-after-load path.
- QA-1-2 | edc4763 | `/__mock/reset` resets the evidence id counter. The first upload after a reset answers EV-1 (mock test).

## Acceptance criteria
1. [x] to 24. and 26. [x]: unchanged from round 1. The full unit suite and all e2e tests pass on this head (see Validation).
- The 403 row of the save outcomes table ("show the API message in the alert and re-read the list (the row will normally lose its editor)", with focus on the callout after every outcome) now also holds when the row losing its editor closes the panel:
  - unit: the alert text is exact, focus is on the alert, the region is gone, 1 PUT and 2 reads, and only one alert;
  - e2e on Rules: the alert is in `.setup-desktop`, it is focused, the panel count is 0, all 10 rows stay, there is 1 PUT, and axe is clean;
  - e2e on Finance: the alert is focused, the panel count is 0, and no "Set …" buttons remain.
25. [ ] Design fidelity: the desktop boards still PASS. The phone boards are unchanged from round 1 (visual below 90, D-08 frame back-link slot; see the round-1 build).

## Validation
- `cd /Users/Hunchoo/psl-factory-worktrees/f-11 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh`: exit 0. Lint 0 warnings, typecheck clean, 16 files / 408 tests passed, build OK.
- `cd frontend && E2E_PORT=4101 MOCK_PORT=4102 npm run test:e2e`: 100 passed. That is the 98 from round 1 plus the 2 new QA-1-1 tests.
- Fidelity, desktop boards: `next start` on 4101 against the mock on 4102, using the approved `F-11/fidelity-exceptions.json`. Reports are in `round-2/fidelity/`.

  | Board | Coverage (with exceptions) | Visual | Result |
  |---|---|---|---|
  | SCR-13-desktop-rules 1440 | 77.6% (100%) | 93.4 | PASS (round-1 review: 93.4) |
  | SCR-13-desktop-finance-rules 1440 | 93.1% (100%) | 96.2 | PASS (96.2) |
  | SCR-13-desktop-delivery-rules 1440 | 90.9% (100%) | 97.1 | PASS (97.9) |

  The delivery delta is only the top-bar persona text. The mock default is finance_lead ("Ada Okafor · Finance Lead"), while the round-1 review run showed Admin. That text is an approved exception, and the delivery view itself is unchanged this round.
- Visual check at 1440, with the right withdrawn after load: on Rules and on Finance, the red callout sits above the list and the panel is gone. The screenshots were deleted afterwards.
- Servers I started on 4101 and 4102 are stopped. `frontend/test-results` is deleted, and the worktree is clean.

### Findings left as they are (all non-blocking in round 1)
- UX-1-1 and AC 25 (phone visual): these wait for the D-08 frame back-link slot in `src/shell`.
- UX-1-2 (phone "← Setup" goes to the reserved Roles tab): left as it is; Roles is a later feature.
- TECH-1-1 to TECH-1-4 and SEC-1-1: not in this round's brief. They are left for a follow-up to keep this round to QA-1-1 and QA-1-2. Note on TECH-1-1: refresh still reads only the first page, and the closed-panel check uses that same re-read, so the check and the view agree.
- SEC-1-2 and SEC-1-3: backend proposals for T-SETUP.

## Blocked
Not blocked.
