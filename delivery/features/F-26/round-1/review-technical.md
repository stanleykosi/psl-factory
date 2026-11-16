VERDICT: CHANGES
COMMIT: 14c685cf577c6e9396a2a9c6ace316cc0998b697
REVIEWER: reviewer-technical
AUTHORITY: delivery technical review

## Summary
- The money rules hold in code and tests. Unknown is never 0 or blank (amount, owed and figure value). Amounts are formatted as text through `formatAmount`, with no floats. The grep for `parseFloat|Number(|.reduce(|toFixed|Math.` finds nothing; the only arithmetic is the sort on the integer `position`. There is no total. Invoice and paid are separate, with one `PAID_WORDS`. "These figures differ" and "No source recorded" are covered, and `as_of` is shown.
- Access: a money 403 or 404 renders `ProjectNoAccess`, shows no stage or amount and makes no report read. A report 403 or 404 shows only the aside line. The wrong-persona (pm on P-0104) and P-0099 cases are tested in the component test, the mock test and the e2e. The frontend has no role logic; `useMe` is read only for the `assistant` link.
- Mock: `money.mjs` and `caseVisible` mirror `journey()` visibility. The scenario header and cookie still win. Other tabs and an unknown money case stay exactly `501 not_mocked`. The `server.mjs` dispatch sits before the M1 501 check, which is justified because non-M1 operations never reach the shared scenario block.
- Shared footprint is the spec's minimum: `ProjectJourney.tsx` changes by one import and one branch, and no existing fixture, `src/api`, `src/components` or `src/shell` file changes. The two test swaps keep identical assertions. One swap is in a file the spec did not list (TECH-1-3).
- One blocking robustness gap: the guards are narrower than the generated schema. A malformed report or amount crashes the whole tab during render instead of showing the report error, so the table disappears (TECH-1-1).

## Findings
- TECH-1-1 | blocking | medium | frontend | **A malformed report or amount crashes the tab instead of showing the error state, so the table disappears.** The spec says "5xx, network or bad shape → the aside shows ErrorState … the table never disappears because the report failed", and that a money body with a bad shape shows the error card.
  - In `moneyModel.ts:42-44`, `isReport` checks only `label` and `value{currency, unknown}`. It does not check that `sources` (required by the schema) is an array, or that `source_details[]` items are objects with string `label` and `reference`.
  - `MoneyTab.tsx:136` then reads `figure.sources.length` while rendering. A figure with no `source_details` and no `sources` throws a TypeError.
  - In `moneyModel.ts:22-24`, `isMoneyValue` does not check that `amount`, when present, is a string. A numeric amount (for example `4250000`) reaches `formatAmount` (`components/format.ts:103`, `value.replace`) and throws while rendering. That applies to row amounts, `paid.owed` and figure values.
  - There is no error boundary under `src/app`, so either crash replaces the whole page. For a report figure, that drops the table the money read authorised.
  - Expected: these bodies fail the guard. The report goes to the aside ErrorState and the money body goes to the error card.
  - Fix: in `isMoneyValue`, require `amount === undefined || typeof amount === 'string'`. Check `paid.owed` with `isMoneyValue` when it is present. In `isReport`, require `Array.isArray(f.sources)` and, when `source_details` is present, an array of objects with string `label` and `reference`.
  - Add one `money-model.test.ts` case per guard, and one component test showing that a report figure with no `sources` keeps the four rows and shows the report error.
- TECH-1-2 | non-blocking | low | frontend | **A row whose amount is Unknown cannot open its figure by press.** In `MoneyTab.tsx:90`, the amount becomes a link only when `figure && text`, so an Unknown row amount with a matching figure is plain text. The spec makes the link depend only on `figure_id` matching a loaded figure. This is the case where a "These figures differ" warning matters most, because the table says Unknown and the report may hold a value. Today it is reachable only by deep link. Fix: render the matched figure's link with the amber `<Unknown />` as its text (and count it in `anyLinked`), or record the narrowing in build.md as an assumption for the design engineer. Neither the P-0101 nor the P-0102 fixtures exercise it.
- TECH-1-3 | non-blocking | low | frontend | **One test swap is in a file the spec's lane did not list.** `tests/projects-journey.test.tsx:73-79,243` swaps the `money` coming-next case for `documents` / "Documents come next" / index 2. The assertion is unchanged and the swap is required, because Money no longer renders `ComingNext`, so nothing is loosened.
  - The spec's lane and Shared files list only `mock-contract.test.ts:192`.
  - F-25 replaces `ComingNext` for `documents`, so this case will fail at the second merge.
  - build.md mentions this. Fix: list `projects-journey.test.tsx` in the merge note for the coordinator as a third shared file, and switch the case to whichever tab still shows coming-next after both features merge (or delete it if none does).

## Verified
- (round 1: no earlier findings)

## Notes
- **What I checked (read-only, no servers started).**
  - Diff `8d20e0aa...14c685cf`: 26 files, all new except `ProjectJourney.tsx` (+1 import, 1 branch), `server.mjs` (+1 import, comment, 1 dispatch line), `projects.mjs` (+`caseVisible`, `journey()` untouched) and the two test swaps.
  - `mock-contract.test.ts:192`: the swap to `E-PAYROLL-MATCH` keeps the identical `toEqual` and `expectValid` assertions.
  - Greps: arithmetic, totals, hex/rgb/hsl in `money.css` and `useMe|roles` are all clean, as build.md claims.
- **Exact comparison in `valuesDiffer` (spec-mandated).** "4250000.00" and "4250000.0" count as different and would show "These figures differ" with two identical formatted values. That is the spec's chosen rule (no number conversion). Worth a backend note that amounts are sent with a fixed scale.
- **The mock answers an unlisted case id with the fallback journey (`case_id` P-0101).** `MoneyTab` takes `journey.case_id`, so an unknown id shows P-0101 money in the mock. This is pre-existing F-07 mock behaviour, and the spec's `journey.case_id` choice is recorded as an assumption. It does not occur against a real backend that 404s.
- **Report 401 replaces the table with the page-level `SignedOutState`.** This is as the spec says, not an exception to "the table stays".
