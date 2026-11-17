STATUS: READY
COMMIT: 34c38e4e3da89ce7b0aa08d62d2ef23c6434b6b3
BUILDER: builder
LANE: full

## Summary
- From and To now match what the screen shows. The request names the delegator: whenever From comes from `from_options[]` (one option or a chosen one), `from_person_id` is sent (SEC-1-1). When the backend pairs delegates (`for_person_id`), To lists only the delegates paired with the From shown. With no From list, that means only the unpaired options (SEC-1-2).
- The mock now treats a missing `from_person_id` as the caller, as the overlay contract says. Its pairing uses the same exact match as the page (TECH-1-2).
- The 422 top message uses the form's labels ("Check these fields: To, Ends."). If the backend names a field the form lacks, its own message is kept (UX-1-1). On phones, when an unconfirmed add finds the list changed, the sheet closes so the person can check the list. The warning shows above the cards, and reopening the sheet shows the held form with "Start again" (UX-1-2).
- The phone sheet keeps Add and Cancel in its sticky footer (UI-1-2). The phone bottom bar is the bundle's `psl-actionbar`, and the room under the last card is computed from tokens (UI-1-3).
- All 11 exceptions and the SCR-13-desktop-delegation visual waiver at 84.0 are marked approved by "design engineer, 16 Nov 2026 — D-107". The new panel-head colour-meaning entry is among them (UI-1-1).

## Changes
- Base merge: `origin/dlv-00-delivery-setup` merged at 2d2b1946 (delivery records only; no frontend change).
- `frontend/src/features/setup/DelegationForm.tsx`:
  - `from_person_id = fromPerson.person_id` whenever From comes from `from_options[]`.
  - To pairing as above.
  - `invalidMessage()` maps 422 field keys to their visible labels, in form order.
  - A `frame` prop splits the form into fields, actions and note. Desktop keeps them in the panel; phone puts the buttons in the Drawer footer.
- `frontend/src/features/setup/DelegationView.tsx`:
  - A moved revision after an unconfirmed add closes the sheet, and the phone tree shows the warning while the sheet is closed.
  - The phone Drawer receives the buttons as its `footer`.
  - The bar uses `psl-actionbar`.
  - A 409 whose re-read fails now says the list could not be reloaded (TECH-1-3).
- `frontend/src/features/setup/setup.css`:
  - `.setup-deleg__bar` keeps only its fixed position; padding, ground and rule come from `psl-actionbar`.
  - Bottom room is `calc(var(--space-3) + var(--control-lg) + var(--space-18px) + var(--rule-strong))`.
- `frontend/mock/delegations.mjs`:
  - An absent `from_person_id` means the caller, even with one From option.
  - `delegatesFor` is an exact `for_person_id` match, so the caller takes the unpaired options.
- `frontend/mock/fixtures/delegations/authority.json`: adds an unpaired option (Chika Obi), so the caller path and the "shown From only" listing can be tested.
- Tests:
  - `setup-delegation.test.tsx`: the authority test now expects `from_person_id: 'P-KEMI'` and only Femi in To.
  - New in `setup-delegation.test.tsx`:
    - SEC-1-2 (pairing keys without a From list)
    - the 422 labels
    - the 422 with an unknown field
    - the 409 with a failed re-read
    - the sheet footer
    - the phone sheet closing on a moved list
  - `setup-delegation-mock.test.ts`: new SEC-1-1 caller test; the default no-From add is now refused at `delegate` (the caller has no paired delegate).
  - `e2e/setup-delegation.spec.ts`: label text; the phone uncertain_written test checks that the sheet closes, the warning shows above 3 cards, and reopening shows Start again; axe on both states.
- Factory files:
  - `delivery/features/F-27/fidelity-exceptions.json`: the panel-head entry, D-107 approvals, and `visual_waivers` for SCR-13-desktop-delegation at 84.0.
  - `round-2/fidelity/`.

## Fixes
- SEC-1-1 | 34c38e4e | From taken from `from_options[]` (including a single option) is always sent as `from_person_id`. The mock treats an absent value as the caller. The test that locked in the omission now expects `P-KEMI`, and a mock test shows that a single-option add without the field is recorded from the caller (`{name: 'Ada Okafor', is_you: true}`). Shown to fail on the old code: reverting the form line fails the authority test (1 of 35), and the round-1 mock fails 2 of 12 mock tests.
- SEC-1-2 | 34c38e4e | Pairing keys present and no From list: To lists only the unpaired options (new component test). The mock uses the same rule (TECH-1-2).
- TECH-1-3 | 34c38e4e | A 409 whose re-read fails shows "This changed while you were working, and we couldn’t reload the list. Reload the page before adding again." It no longer claims the list was reloaded.
- UX-1-1 | 34c38e4e | The 422 top message reads "Check these fields: To, Ends." When the backend names a field the form does not have, its message is kept.
- UX-1-2 | 34c38e4e | Phone: after `uncertain_written` the sheet closes and the warning shows above the cards. Reopening shows Add held and "Start again".
- UI-1-1 | 34c38e4e | Exception "ADD A DELEGATION", category colour meaning (D-92b/D-93), approved per D-107.
- UI-1-2 | 34c38e4e | Phone sheet: Add delegation and Cancel (and Start again) sit in the Drawer footer. The fields and note scroll in the body.
- UI-1-3 | 34c38e4e | The bar is `psl-actionbar` with a fixed-position modifier, and the bottom room is a token `calc`.
- Not changed: TECH-1-1 (the mock's "no `can_add` → 403" step is still unreachable with the spec's fixtures). It remains a check-order question for the backend developer: should a view-only caller get 403 before the 422/409 checks?

## Acceptance criteria
1. [x] Fidelity, under the D-107 waiver:
   - SCR-13-desktop-delegation @1440: coverage 83.3, 100 with exceptions, visual 84.0. That equals the signed waiver; the tool's own pass flag is False because the tool does not read waivers.
   - SCR-13-mobile-delegation @390: coverage 80, 100 with exceptions, visual 98.6, PASS.
2. [x] Exceptions: 11 entries, each mapped to a Conflicts item or D-92b, all approved by D-107. The waiver at 84.0 is recorded in `visual_waivers`.
3. to 24. [x] As in round 1, re-run on this head: component, mock and e2e suites pass. Changed evidence:
   - AC 6: the `authority` scenario now sends `from_person_id: 'P-KEMI'`; `single` still sends none.
   - AC 7: To lists only the delegates paired with the From shown, including a single From option; with no From list, only the unpaired options.
   - AC 12: the top message uses labels.
   - AC 14 and AC 17: on phones a moved list closes the sheet; Start again is in the reopened sheet.

## Validation
- `bash /Users/Hunchoo/psl-factory/delivery/checks.sh` (started at load 5.4): exit 0. 85 files and 1871 tests passed; lint, typecheck and build passed. No re-run was needed.
- `cd frontend && E2E_PORT=4801 MOCK_PORT=4802 npx playwright test e2e/setup-delegation.spec.ts e2e/setup.spec.ts`: 26 passed (1.0m).
- `npx vitest run tests/setup-delegation*.test.* tests/mock-contract.test.ts`: 322 passed.
- Fidelity, on a production build (app 4801, mock 4802 with `MOCK_DELEGATIONS_SCENARIO=default`, frozen page on 4803, `round-2/fidelity/run.sh`):
  - The first run warned "Google Fonts could not be reached; the board was drawn with fallback fonts". It scored desktop 81.1; the diff shows the board's own nav text offset.
  - That run is kept in `round-2/fidelity/fonts-unreachable/`.
  - I confirmed the fonts were reachable again and re-ran once, with no font warning: desktop 84.0, phone 98.6 (`round-2/fidelity/scores.txt`).
- Servers on 4801, 4802 and 4803 were stopped by the PID on each port after checking its cwd. `frontend/test-results` is gone and the worktree is clean. Pushed with no force: ab5a4f0f..34c38e4e.

## Verified
- SEC-1-1 | verified | authority test (`from_person_id: 'P-KEMI'`) and mock caller test pass on 34c38e4e; both fail on the round-1 code.
- SEC-1-2 | verified | the "pairing keys without a From list" component test passes.
- UX-1-1 | verified | component and e2e (desktop panel and phone sheet) show "Check these fields: To, Ends.".
- UX-1-2 | verified | component test and e2e @390: the sheet closes, the warning shows above 3 cards, and reopening shows Start again; axe is clean.
- UI-1-1 | verified | entry present in `fidelity-exceptions.json`, approved per D-107.
- UI-1-2 | verified | component test: the footer holds exactly Add delegation and Cancel, with the note in the body; e2e: footer buttons are at least 44px.
- UI-1-3 | verified | `setup.css` uses `psl-actionbar` and a token `calc`; no px literal; phone fidelity is unchanged at 98.6.
- TECH-1-3 | verified | component test: a 409 with a failed re-read shows the "couldn’t reload" sentence and not the stale one.

## Blocked
None.
