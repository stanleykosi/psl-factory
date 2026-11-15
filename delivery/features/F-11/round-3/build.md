STATUS: READY
COMMIT: 604e1b0a0f8fb3ac2cee49124f70370b1343e6de
BUILDER: builder
LANE: full

## Summary
- The branch now includes origin/dlv-00-delivery-setup, which carries the frame's phone back-link slot (PR #17, D-23/D-28). It was merged in with merge 2c8d98c, with no rebase and no force. The new merge-base is b7f7166. No protected path changed against either the old base (3c0e57e) or the new one.
- The three Setup phone views now put "← Setup" (to /setup/roles) inside the frame's phone bar through `usePhoneBack`, and the page-local link under the bar is gone. The finance and delivery boards also draw a mono "RULES" note at the right of that bar, so the slot gained an optional `note` field. Desktop is unchanged.
- Phone fidelity now matches the boards: rules 66.0 → 99.8, finance 78.9 → 99.1 and delivery 83.7 → 99.7 visual. All six SCR-13 boards PASS at 100% coverage with exceptions. One new exception is requested and needs coordinator approval (see the table).
- TECH-2-1 is fixed. The view now decides whether the panel stays open after a re-read, and Rules stops showing a stale "panel has closed" callout once the panel is back. SEC-2-1 is covered: a new test checks that an uncertain result never says "Nothing you entered was saved".

## Changes
- frontend/src/shell/PhoneBar.tsx, frontend/src/shell/AppShell.tsx, frontend/src/styles/shell.css: `PhoneBack` gains an optional `note`, shown as a mono 12px `.shell-phonenote` at the right of the bar while the slot is set. This is additive, so pages that don't pass a note are unchanged. The boards draw "RULES" there, and without it the label would have been dropped.
- frontend/src/features/setup/SetupFrame.tsx: the page-local `PhoneBack` component is replaced by a `useSetupPhoneBack(note?)` hook, which calls `usePhoneBack({ label: 'Setup', href: '/setup/roles', note })`.
- frontend/src/features/setup/RulesView.tsx, FinanceRulesView.tsx, DeliveryRulesView.tsx: each view calls the hook inside the Setup gate, with no note on Rules and 'RULES' on Finance and Delivery, and drops the old `<PhoneBack>`. In setup.css the unused `.setup-back*` rules are removed.
- frontend/src/features/setup/SetRulePanel.tsx: new `staysOpen(page)` prop. `announce` hands the outcome to the view only when the view says the panel will not render after the re-read. Rules passes "any row editable" and Finance passes "this group still has an editable row" (TECH-2-1).
- RulesView.tsx: the page callout shows only while the panel is closed (TECH-2-1, the stale-notice half).
- Tests:
  - tests/setup-rules.test.tsx: the phone back link is checked in the bar, and the finance bar note reads RULES. Three new tests:
    - SEC-2-1: a 500 whose re-read leaves every rule read-only. The page callout has EDITOR_GONE and not NOT_SAVED.
    - TECH-2-1: a re-read that makes a different rule editable keeps the panel, and its alert stays inside it with no page callout.
    - TECH-2-1: Show more brings the panel back and the stale callout goes.

    Both TECH tests fail against the round-2 code.
  - tests/shell.test.tsx: one test that the note renders and is cleared when the page changes.
  - e2e/setup.spec.ts: the phone test checks "Back to Setup" in the bar with no Menu, no Setup link in the page, and RULES on finance and delivery.

## Fixes
- FID-2-1 | 604e1b0 | "← Setup" is now in the frame phone bar through `usePhoneBack`, with the "RULES" note where the board draws it, and the page-local link is removed. Phone visual 99.8 / 99.1 / 99.7.
- TECH-2-1 | 604e1b0 | The view decides whether the panel stays open (`staysOpen`), and Rules hides the closed-panel callout while the panel is shown.
- SEC-2-1 | 604e1b0 | Unit test: an uncertain (500) result with every rule read-only says the panel closed but never "Nothing you entered was saved".

## Fidelity
I ran fidelity.mjs from /Users/Hunchoo/software-factory/packages/design/fidelity/ against a production `next start` on 4601 and the mock on 4602, at head 604e1b0. The cookies were the same as round 2: admin + desktop, finance_lead + desktop for desktop-finance, and admin + mobile for the phone boards. I used `--exceptions round-3/fidelity/exception-requests.json`, which is the approved F-11 list plus one requested entry:

- **Requested, pending coordinator:** link "← Setup". The frame gives every back link the accessible name "Back to <label>" (frame-phone-back build note; the technical review found WCAG 2.5.3 holds). The tool therefore lists the same link, with the same text and href, as "Back to Setup". The name belongs to the shared frame, not to F-11.
- Without this entry the phone boards are 92.9% / 87.5% / 66.7% coverage with exceptions. The only missing item is this link, and visual is unchanged.

| Board | Coverage raw (with exceptions) | Visual | Tool |
|---|---|---|---|
| SCR-13-desktop-rules 1440 | 77.6% (100%) | 93.4 | PASS |
| SCR-13-desktop-finance-rules 1440 | 93.1% (100%) | 96.2 | PASS |
| SCR-13-desktop-delivery-rules 1440 | 93.9% (100%) | 97.9 | PASS |
| SCR-13-mobile-rules 390 | 7.1% (100%) | 99.8 | PASS |
| SCR-13-mobile-finance-rules 390 | 87.5% (100%) | 99.1 | PASS |
| SCR-13-mobile-delivery-rules 390 | 66.7% (100%) | 99.7 | PASS |

Reports are in round-3/fidelity/: one folder per board with report.json, report.html and side-by-side.png, plus a .log per board, results.txt and exception-requests.json. The page, board and diff PNGs were pruned.

## Acceptance criteria
18. [x] Phone: at 390 with the mobile scenario, the frame bar shows "← Setup" linking to /setup/roles, with no Menu. The h1 is "Rules · 6 not set" over 6 cards. Finance shows "25 values Not set.", 3 groups and "+ 4 MORE LINES · OPEN ON DESKTOP" with RULES in the bar. Delivery shows 4 rows. There is no side scroll and axe is clean. Evidence: e2e/setup.spec.ts phone tests pass.
- Every other criterion is unchanged from round 2. All 42 tests in e2e/setup.spec.ts and e2e/frame.spec.ts pass, and so do all 419 unit tests.

## Validation
- `bash /Users/Hunchoo/psl-factory/delivery/checks.sh`: exit 0 (lint, typecheck, 419 vitest tests in 17 files, build).
- `E2E_PORT=4601 MOCK_PORT=4602 npx playwright test e2e/setup.spec.ts e2e/frame.spec.ts`: 42 passed.
- Ran the TECH-2-1 tests against the round-2 SetRulePanel and RulesView: both fail there and pass now.
- Servers on 4601 and 4602 are stopped, frontend/test-results is deleted, and the worktree is clean. Pushed 604e1b0 to origin.

## Blocked
None.
