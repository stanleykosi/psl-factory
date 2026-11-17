VERDICT: PASS
COMMIT: ac401c09e80d4398acb8101994d6f18b4b0f1d76
REVIEWER: reviewer-technical
AUTHORITY: delivery technical review

## Summary
- TECH-1-1 is fixed. The money and report guards now match what the page draws. A numeric amount or owed value, an invoice without a reference, a paid status that is not text, or a figure without a `sources` string array is treated as a bad body instead of crashing the page. A bad row shows the money error card. A bad report shows the report error while the table stays.
- TECH-1-2 is fixed. An Unknown amount whose figure is in the report is now a link, so "These figures differ: the table shows Unknown; …" can be reached by pressing it.
- The money rules still hold. The arithmetic grep (`parseFloat|parseInt|Number(|.reduce(|toFixed|Math.|BigInt`) finds nothing in `moneyModel.ts`, `MoneyTab.tsx` or `useMoney.ts`. There is no total. The colour grep on `money.css` is clean. `useMe` is still read only for the Chidi link. Round 2 changes nothing in `src/api`, `src/components`, `src/shell`, `mock/**`, `apps`, `architecture` or `design`.
- No test is weakened. Two e2e assertions now expect more: the phone report error must be visible, and the money no-access line is checked. Their leak-word checks are unchanged.
- There are two non-blocking notes on code changed in this round (TECH-2-1, TECH-2-2).

## Findings
- TECH-2-1 | non-blocking | low | pmo | **The money no-access state now uses the spec's Option B, and no design-engineer approval for it is recorded.** `MoneyTab.tsx:268-278,309` shows "You can't see this project's money." instead of `ProjectNoAccess` (the UX-1-2 fix). Spec Conflicts 14 recommended building readiness rule 6 as written, and criterion 20 names `ProjectNoAccess`. D-104 ("the rest as the spec") and D-107 do not mention Option B. The no-leak behaviour is unchanged and tested: no stage, amount, report title or server message appears, and the report is not read. Fix: have the design engineer confirm Option B in a D-entry, or note it in build.md as a UX-review change awaiting that sign-off.
- TECH-2-2 | non-blocking | low | frontend | **On phones, a deep link to a figure while the report has failed shows the report error twice.** At `MoneyTab.tsx:343`, a failed report renders `explanation` under the cards. When `?figure=` is set, the BottomSheet (`:345-349`) renders the same `explanation` again, so there are two ErrorStates and two "Try again" buttons, one behind the sheet. Both retry the same report read, so nothing is wrong, just repeated. Fix: render the inline copy only when no sheet is open (`report.status === 'error' && selectedId === undefined`), or leave it as is.

## Verified
- TECH-1-1 | verified | The fix is in `moneyModel.ts:22-84`.
  - `isMoneyValue` requires `amount` to be text when it is sent. `isMoneyRow` checks `amount_note`, `invoice_status` and `figure_id` as optional strings, `invoice` as an object with a string `reference`, and `paid` as an object with a string `status` and a valid `owed`.
  - `isReport` requires every figure to have a `sources` array of strings and well-formed `source_details`, each with string `label` and `reference`.
  - `money-model.test.ts` has a negative case for each guard plus positive controls.
  - `money.test.tsx` covers the "round 2" cases:
    - A figure without `sources` keeps the 4 rows with plain amounts, and the aside shows the report error and Try again.
    - Four spoiled rows each show the money error card and no table.
  - `agentKey` now guards the Chidi lookup, so an unexpected agent name no longer breaks the card.
  - Evidence is from reading the code and the diff `14c685cf..ac401c09`; checks.md records the suite on this head. I ran no servers.
- TECH-1-2 | verified | At `MoneyTab.tsx:86-104`, the link depends only on a matched figure, and its content is `<Value>` (the amber Unknown for an unknown amount, never 0 or blank). `anyLinked` was changed to match. The component test "an Unknown amount whose figure the report has is a link" asserts the href, the `psl-unknown` text inside the link, `aria-current`, and the exact differ sentence.
- TECH-1-3 | carried | There is no code change, which is correct for a merge note. `projects-journey.test.tsx` is untouched in round 2. The coordinator still needs to list it as a third shared test file for the F-25 merge.

## Notes
- **Impact of the other round-2 changes.**
  - UI-1-1, UI-1-2 and UI-1-4 change CSS only. The tap-area values now come from tokens; the remaining raw px in `money.css` are layout widths, not colours, so criterion 29 still holds.
  - UX-1-1 adds an inline report error or refusal under the phone cards. Its Try again re-reads only E-REPORT (tested), and the refusal shows nothing from the report body (tested).
  - None of these touches amount handling, the invoice/paid split or the access paths.
