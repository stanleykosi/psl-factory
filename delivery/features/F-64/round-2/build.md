STATUS: READY
COMMIT: 9b921ea707826cf3528dcc32da1c10f17e26ed90
BUILDER: builder
LANE: full

## Summary
- The four blocking UI findings of round 1 are fixed: stale compare as a real table, phone stale card as on the board, phone not-yours strip without an empty cell, done "What happens next" panel as a complementary landmark.
- UI-1-5 done (title no longer drawn twice). UI-1-6 not done (see below).
- origin/main (F-72, ae0525fb) merged into the branch; conflicts in mock/server.mjs and tests/next-config.test.ts resolved keeping both sides.

## Changes
- src/features/decide/LiveStates.tsx, decide.css, DecideView.tsx; tests/decide.test.tsx (4 new tests: table semantics, phone stale card, phone strip, done aside, title once). The phone replaced line keeps its muted ink without the board's 0.75 opacity, because axe flags the faded text as low contrast (found by the e2e run, fixed in ec939861).

## Fixes
- UI-1-1 | fa18b1b4 | the stale compare is a real table (table, column headers "VERSION n · REPLACED" and "VERSION m · CURRENT", row headers, the changed row tinted, board padding); the tool no longer lists the table or headers as missing
- UI-1-2 | fa18b1b4 | on a phone: one grey "Invoice v2 · amount / REPLACED" line, then one current card with "Amount" and "To" rows and their unchanged/changed tags; no tool-listed missing items on the mobile stale board (100% with exceptions)
- UI-1-3 | fa18b1b4 | phone not-yours strip: the Waiting cell spans the remaining columns, no empty cell (visual 85.8 to 92.6). The Add comment bar is already pinned to the bottom by the existing phone CSS; not changed
- UI-1-4 | fa18b1b4 | the done "What happens next" panel is an aside with its heading as the name (complementary landmark); the tool no longer lists it
- UI-1-5 | fa18b1b4 | the sub-line is left out when the work title equals the task label; it still shows when they differ
- (contrast, from my own e2e run) | ec939861 | phone replaced line: opacity removed so it passes axe contrast

## Merge of origin/main 15699653 (F-62, F-125, F-72, D-199)
One conflict, mock/server.mjs: both hooks kept. F-64's decide hook runs first and owns work ids 17 to 19, the task routes and queue=decisions; F-62's work-list item hook owns only its own ids (301 to 320, 401 to 420); lane C's work-live handler keeps every other integer id. No id overlaps. Checked singly after the merge: tsc clean; decide, mock-live-decide, exceptions-mock, work-item, live-work-item and mock-work-live tests 163 passed. No full suite (D-199, the gate runs on GitHub Actions).

## Not done
- UI-1-6 (extra elements: "0 / 2000" counter, "Open the work item" under the comment, shorter footnote): left as is. Removing the counter drops the limit cue and the other two are copy the spec added; for the design engineer to confirm.

## Acceptance criteria
Unchanged from round 1 (all met; criterion 14 still [~] for the visual score).

## Validation
- Run on 26a75c1c (the merge): tsc clean; decide, mock-live-decide, next-config, no-success-callouts and document-review tests 124 passed; eslint clean on mock, decide and decide.test. Full vitest through the heavy lock on 26a75c1c: 158 files, 3754 tests passed. The only change after that is one CSS line (ec939861).
- Playwright decide specs through the lock on ec939861: e2e/decide.spec.ts and e2e/decide-board.spec.ts, 19 passed (the first run on 26a75c1c had one phone-stale axe contrast failure, fixed by ec939861).
- Fidelity re-run once on the changed boards (done, stale, not-yours at 1440 and 390; production build on the mock; reports in round-2/fidelity/), run on fa18b1b4 before the F-72 merge:
| Board | Coverage with exceptions | Visual |
|---|---|---|
| done 1440 | 97.7 | 70.5 |
| done 390 | 97.1 | 64.3 |
| stale 1440 | 92.9 | 69.1 |
| stale 390 | 100 | 74.5 |
| not-yours 1440 | 95.5 | 78.6 |
| not-yours 390 | 94.7 | 92.6 |
Left un-excepted: the amount "₦4,250,000.00" on not-yours 1440 and 390 and stale 1440 (tool false negative as in round 1; the mock's stale data also gives a different current amount than the board's sample), and the done "Sat 21 Nov, 10:47 WAT, by Ada Okafor" line (the mock's own decision time and name, not the board's sample). Visual stays under 90 on five boards (D-182 removals); needs a design-engineer waiver.
- Servers started for the fidelity run were stopped by the script by their recorded PIDs; 3000/3001 untouched.

## Blocked
Not blocked.

## Pending live evidence
- The main coordinator will prove the live decision journey on psl_demo (seeded report template and a pending PMO Lead review). Pending.
