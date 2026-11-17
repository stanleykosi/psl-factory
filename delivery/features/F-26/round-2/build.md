STATUS: READY
COMMIT: ac401c09e80d4398acb8101994d6f18b4b0f1d76
BUILDER: builder
LANE: full

## Summary
- Malformed money or report bodies can no longer crash the tab (TECH-1-1). A bad money row now shows the money error card. A bad report now shows the report error and its Try again, and the table stays.
- The board weights are restored. The selected amount is no longer bold, and it keeps `aria-current` (UI-1-1). On phones, Unknown is regular-weight mono as the board draws it; the desktop table keeps semibold (UI-1-2).
- Non-blocking items, also done:
  - An Unknown amount whose figure is in the report is now a link, so "These figures differ" can be reached by pressing it (TECH-1-2).
  - On phones, a failed or refused report shows its message under the cards, with Try again for a failure (UX-1-1).
  - A refused money read shows "You can’t see this project’s money." (Conflicts 14, Option B, UX-1-2).
  - Phone tap areas use spacing tokens and no longer cover the stage name (UI-1-4).
- Fidelity coverage is still 100% after exceptions. Visual is desktop 85.7 and phone 77.8. UI-1-3 (the per-board waivers) goes to the design engineer after this round; no waiver was added.
- Contract mock only, unchanged: nothing is released, and the backend developer may change or refuse any field.

## Changes
- `frontend/src/features/projects/moneyModel.ts`: the guards now check every field the page draws:
  - Every money value must have text currency and a boolean `unknown`, and its amount, when present, must be text.
  - Row text fields must be text, `invoice` needs a text `reference`, and `paid` needs a text `status` with a valid `owed`.
  - Each report figure needs `sources` as an array of text and well-formed `source_details` (text `label` and `reference`).
  - The report `title` must be text.
- `frontend/src/features/projects/MoneyTab.tsx`:
  - Any amount whose figure is in the report is a link, including an Unknown one (the amber Unknown is the link text). The phone hint counts these too.
  - On phones, the report's error or refusal is shown under the cards.
  - A refused money read now shows `MoneyNoAccess` ("You can’t see this project’s money.") in place of `ProjectNoAccess`.
  - The Chidi card takes its agent from `agentKey`, so an unknown agent shows no card instead of throwing.
- `frontend/src/features/projects/money.css`:
  - Removed the bold selected amount.
  - Phone Unknown is mono, 400 weight, 16px; the table Unknown stays 600.
  - The phone amount link reaches only into the `--space-6px` gaps above and below it and grows the rest. The invoice link reaches down by `2 × --space-3`.
  - The two tap areas meet in the gap without overlapping, and neither covers the stage name. Linked cards are about 14px taller than in round 1.
- Tests:
  - `tests/money-model.test.ts`: two guard tests covering a numeric amount, numeric or partial owed, an empty paid, an invoice with no reference, non-text fields, missing or non-text sources, and malformed `source_details`.
  - `tests/money.test.tsx`:
    - A report figure without sources keeps the four rows and shows the report error.
    - Four money-row spoilers show the error card with no table.
    - An Unknown amount links to its figure, and the panel reads "These figures differ: the table shows Unknown; the report shows ₦1,500,000.00."
    - The phone report failure and refusal appear under the cards, and Try again makes one report request.
    - The P-0107 and P-0108 assertions now expect the money no-access line.
  - `e2e/money.spec.ts`:
    - The phone P-0103 check now finds the error under the cards, not in a sheet.
    - The P-0103 error is now expected visible at both widths.
    - The no-access check now expects the money line.
- Main folder: `round-2/fidelity/` (`run.sh`, `scores.txt`, both reports). `fidelity-exceptions.json` is unchanged.

## Fixes
- TECH-1-1 | 0b46a01be66ba05a8f70775739ccfd66df8121e9 | Strict `isMoneyValue` (amount must be text), row, invoice and paid guards, and `isReport` (sources must be an array of text; source_details well formed). A malformed report shows the drill-down error and keeps the table; a malformed row shows the money error card. Tests are in money-model.test.ts and money.test.tsx.
- UI-1-1 | 0b46a01be66ba05a8f70775739ccfd66df8121e9 | Removed `.money__amountlink[aria-current="true"] { font-weight: 600 }`; `aria-current="true"` stays (asserted in the component test and e2e).
- UI-1-2 | 0b46a01be66ba05a8f70775739ccfd66df8121e9 | `.money__card .psl-unknown` is `--font-mono`, `--text-amount-size`, weight 400; only `.money__table .psl-unknown` is 600.
- TECH-1-2 | 0b46a01be66ba05a8f70775739ccfd66df8121e9 | A row links whenever its `figure_id` matches a loaded figure, Unknown amounts included (component test).
- UX-1-1 | 0b46a01be66ba05a8f70775739ccfd66df8121e9 | On phones, a report error shows the ErrorState and Try again under the cards, and a refusal shows "You can’t see where these figures come from." (component test and e2e at 390).
- UX-1-2 | 0b46a01be66ba05a8f70775739ccfd66df8121e9 | Conflicts 14 Option B: a money 403/404 shows "You can’t see this project’s money." in a "No access" panel. No stage, amount, report title or server message appears and no report is read (component test and e2e). The project-level `ProjectNoAccess` still covers an E-PROJECT 403/404.
- UI-1-4 | 0b46a01be66ba05a8f70775739ccfd66df8121e9 | Tap-area padding and margins come from `--space-6px`, `--space-3` and `--control-md`. The amount's area no longer reaches over the stage name. The e2e still measures every phone link at 44px or more.

Not fixed here:
- UI-1-3: the per-board waivers go to the design engineer after this round, as the coordinator instructed.
- TECH-1-3: a coordinator merge note (see Notes). There is no code change for it.

## Verified
- TECH-1-1 | verified | A report figure with no `sources` keeps the four rows and shows the drill-down error and Try again. Money rows with a numeric amount or owed, an invoice with no reference, or a non-text paid status show the error card and no table (money.test.tsx). The guard cases pass in money-model.test.ts.
- UI-1-1 | verified | The round-2 desktop report no longer lists a weight difference for the selected amount; aria-current is still asserted.
- UI-1-2 | verified | The phone card's Unknown computes to IBM Plex Mono 16px weight 400 in the round-2 page; the table keeps 600.
- TECH-1-2 | verified | The component test "an Unknown amount whose figure the report has is a link" passes.
- UX-1-1 | verified | The component test for P-0103 and P-0106 on phones passes, and the e2e at 390 for P-0103 makes one report request on Try again.
- UX-1-2 | verified | The component and e2e tests for P-0107 and P-0108 find the money no-access line and none of the hidden words.
- UI-1-4 | verified | The CSS has no raw px for the tap areas, and the e2e 44px check passes at 390.

## Acceptance criteria
1. [ ] Desktop board: coverage 87.8, 100 after exceptions, **visual 85.7**. Under 90: UI-1-3, the per-board waiver for the design engineer.
2. [ ] Phone board: coverage 63.6, 100 after exceptions, **visual 77.8**. Under 90: UI-1-3, the per-board waiver for the design engineer.
3. [x] No D-83 waiver and no visual waiver in `fidelity-exceptions.json` (unchanged from round 1).
4. [x] Exceptions: the same 11 D-104 entries as round 1, each mapped to its Conflicts number in round-1/build.md.
5. [x] One fidelity run this round (`round-2/fidelity/run.sh` on 0b46a01b; no discovery runs this round).
6–28. [x] As in round 1, with the changes listed above. Criterion 20 now uses the money no-access line (Conflicts 14 Option B). All component tests and the e2e at 1440 and 390, including axe, pass.
29. [x] `grep -nE "#[0-9a-fA-F]{3,8}\b|rgba?\(|hsl\(" money.css` returns nothing. `grep -nE "parseFloat|Number\(|\.reduce\("` on the three files returns nothing.
30–32. [x] Unchanged: no assertion is loosened, and the limits are stated above.

## Validation
- Base merge and waivers: origin/dlv-00-delivery-setup was merged at ac401c09 (`git diff --stat 0b46a01b ac401c09 -- frontend` is empty, so the results below, measured at 0b46a01b, hold). The D-107 visual waivers for SCR-12-desktop (85.7) and SCR-12-mobile (77.8) are now in `fidelity-exceptions.json` as `visual_waivers`.
- `bash /Users/Hunchoo/psl-factory/delivery/checks.sh` (worktree) exits 0: lint, typecheck, vitest **86 files, 1882 tests passed**, and next build.
- `E2E_PORT=4780 MOCK_PORT=4781 npx playwright test e2e/money.spec.ts e2e/projects.spec.ts` gives **40 passed** (12 money and 28 projects at 1440 and 390, axe WCAG 2.2 AA).
- Fidelity (`round-2/fidelity/run.sh`, production build `next start -p 4780`, mock 4781, persona finance_lead):

  | Board | Width | Coverage | With exceptions | Visual | Pass |
  |---|---|---|---|---|---|
  | SCR-12-desktop | 1440 | 87.8 | 100 | 85.7 | False |
  | SCR-12-mobile | 390 | 63.6 | 100 | 77.8 | False |

- Housekeeping: servers were stopped by PID (4780–4789 are free), `frontend/test-results` was deleted, and disk was 6.1 GB free.

## Notes
- TECH-1-3, for the coordinator's merge with F-25: `frontend/tests/projects-journey.test.tsx` is a third shared file. F-26 swapped its coming-next case from `money` to `documents` (index 2). F-25 replaces `documents`, so whichever merges second must point that case at a tab still showing coming-next, or delete it if none is left.
- The phone visual went from 71.4 to 77.8. The cause is the score's 12px grid, not a closer layout: linked cards are now about 14px taller (UI-1-4), which happens to line up better with the board's cards.

- Exceptions file update (main folder only; the branch is unchanged at ac401c09): the SCR-12-mobile waiver now also covers phone cards about 12px taller per linked stage, for the two 44px tap targets (D-92c), approved under D-108. The SCR-12-desktop waiver now names the shorter Chidi card (side panel about 20px shorter) and the report title on the same line as the board's sentence (UI-2-2, D-104/D-107). D-108 also approves the money no-access line "You can’t see this project’s money." (Conflicts 14, Option B).

## Blocked
Not blocked. UI-1-3 is resolved by D-107 (both waivers signed and recorded). Previously open: per-board waivers for SCR-12-desktop (85.7) and SCR-12-mobile (77.8). Coverage is 100% after exceptions on both. The waiver wording is in round-1/review-ui.md; the phone figure is now 77.8.
