STATUS: READY
COMMIT: 41b4925c441959c3a4fc2b7eaf8437fa35791109
BUILDER: builder
LANE: full

## Summary
- Round 2 fixes UI-1-1 to UI-1-6 (D-75): Save is blue and enabled; a blank press sends nothing and shows the message beside the field; empty inputs get the orange border while `billing_contact.set` is false; phone gets a sticky Save bar and no panel chrome; project link is blue; Projects is current on /clients.
- Fidelity (production build, FRAME_FIXTURES=1, persona pm): coverage 100% after exceptions on all four boards. Visual: SCR-35-mobile 92.5 (pass), SCR-35-mobile-detail 86.0 (was 76.7), SCR-35-desktop-detail 80.3 (was 79.3), SCR-35-desktop 85.9 (unchanged).
- The three boards still under 90 are held by approved omissions (Legal name, address, Tax ID, Contacts, Search/Filter row, extra Money panel, OWED column); see the reviewer's gap analysis. Design engineer decision remains open.
- One new exception entry proposed (below), pending design engineer.

## Changes
- `frontend/src/features/clients/BillingContactForm.tsx`: Save disabled only while busy; blank name/email on press sets a client-side field message ("Enter the billing contact name." / "Enter the billing email."), sends no request, focus to the first blank field (reuses the 422 per-field path); `clients__needed` class on both inputs while `!billing_contact.set`; Save wrapped in `clients__bar`; panel classes `clients__formpanel`, `clients__h2--panel`.
- `frontend/src/features/clients/clients.css`: `.clients__needed` signal border; project link no longer forced ink (rule limited to the list table); phone: form panel loses border/head chrome (h2 kept visually hidden), sticky white bottom bar with ink top rule (`.monthend-bar` pattern), page min-height so the bar sits at the screen bottom.
- `frontend/src/shell/destinations.ts`: `/clients` and `/clients/...` map to the Projects destination.
- `frontend/tests/clients.test.tsx`, `frontend/tests/shell.test.tsx`: see below.
- Factory: `fidelity-exceptions.json` (one entry added), `round-2/fidelity/**`.

## Fixes
- UI-1-1 | 41b4925c | Save enabled/blue; blank press shows messages and focuses first blank field (D-75a).
- UI-1-2 | 41b4925c | orange border while contact is not set.
- UI-1-3 | 41b4925c | phone sticky Save bar.
- UI-1-4 | 41b4925c | no panel wrapper on phone (heading kept for screen readers).
- UI-1-5 | 41b4925c | project link keeps link blue.
- UI-1-6 | 41b4925c | Projects current on /clients (D-75b); new `destinationForPath` test.
- UX-1-2 | 41b4925c | same as UI-1-1/UI-1-2 (spec's disabled-until-filled rule replaced by D-75a).
- UX-1-4 | already true | the name input is already linked to the helper by `aria-describedby`.

Test assertions changed (AC-10): in `clients.test.tsx` the test "Save is off until both inputs are non-blank..." is now "a blank input sends nothing...". Removed: `saveButton().disabled === true` for empty and blank-email states. Added: Save is enabled when empty; both inputs carry `clients__needed`; an empty press sends 0 PUTs, shows both messages and focuses the name input; a name-only press sends 0 PUTs, shows only the email message and focuses the email input. The later single-PUT/double-press/reload assertions are unchanged. `shell.test.tsx` adds one test: Projects is current for /clients and /clients/CL-3501, not for /clientsx or /client.

## Left, and why
- UI-1-7 (list row/table offset ~2px per row) and UI-1-8 (panel heads 43px vs 37px): not cheap; the head uses the shared `psl-panel__head` and changing row height risks the other table styling. Left.
- UX-1-3 (double "Set" in list rows): both columns are spec-fixed; left.
- TECH-1-1 (spec fixture row says Tamarind false, acceptance needs true): coordinator should correct the spec row. TECH-1-2 to 1-4: no action requested.
- UI notes on raw spacing values: left.

## Acceptance criteria
1. [ ] Desktop fidelity: coverage 100 after exceptions on both; visual SCR-35-desktop 85.9, SCR-35-desktop-detail 80.3 (< 90). Forced by approved omissions; design engineer decision open.
2. [ ] Phone fidelity: SCR-35-mobile 92.5 pass; SCR-35-mobile-detail 86.0 (< 90), the remaining gap is the omitted Billing address field, the extra Projects/Money panels and the frame's bell/Start (Conflicts 4, 8, 14). Open decision. Rows in `round-2/fidelity/scores.txt`.
10. [x] Save request: changed per D-75a, see above; one PUT with exact body, double press one request (unchanged test).
Other criteria unchanged from round 1 (all [x] there): component tests, mock tests and e2e pass again.

## Validation
- `cd /Users/Hunchoo/psl-factory-worktrees/f-19 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh`: exit 0, 51 files, 1443 tests. (A first run while another gate ran concurrently had two timeouts in `response.test.tsx`; the file passes alone and in the final run.)
- `E2E_PORT=4631 MOCK_PORT=4632 npx playwright test e2e/clients.spec.ts`: 16 passed (axe at 390 and 1440, including the phone sticky bar).
- Fidelity once per board at 1440/390 via `design-fidelity-check` (software-factory branch) after one earlier pass: that pass showed SCR-35-mobile-detail coverage 87.5 because the "Billing contact name" board text had matched the panel heading that the phone no longer draws; fixed by one proposed exception, then re-run: scores above.
- Servers on 4631/4632 stopped by PID; `frontend/test-results` removed; worktree clean and pushed.
- Note: an accidental early gate run started from the project checkout (a chained command failed) was killed by PID before it did anything; main checkout `git status` unchanged by it.

## Blocked
Not blocked. Proposed exception needing design engineer sign-off: `text` "Billing contact name" (Conflicts 7), `approved_by: "builder proposal, pending design engineer"`.
