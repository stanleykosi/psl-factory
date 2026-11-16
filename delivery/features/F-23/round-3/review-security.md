VERDICT: PASS
COMMIT: a3f43067bf20e8474e3a6bb54d273597154d6f28
REVIEWER: reviewer-security
AUTHORITY: delivery security review

## Summary
- An unknown date is never shown as a real date. The short "13 Nov" form is used only after `dateText` has accepted the value: it must not be `unknown: true`, and it must be a valid `YYYY-MM-DD` date.
- The fixtures now carry dates as typed `{date, unknown}` cells instead of the text "13 Nov" and "Unknown". So the frame decides what Unknown means, not a fixture string. This is stricter than round 2.
- The contract-test guard is stricter, not weaker. Any `date_format` must equal `day_month` before the test strips it. A new test confirms that `date_format` and `items[].values` appear only in W-23xx fixtures.
- The DRAFTED tag changed from `neutral` to `agent` tone. That is display only.

## Findings
None.

## Verified
- No security findings were open from round 2. SEC-2-1 (non-blocking) is unchanged and carries forward: this round does not touch `WorkItemOverview.tsx`.

## Impact assessment of the round-3 changes
- **`Sections.tsx:58-60` `DateText`.** The `short` path needs `value.date && dateText(value) !== null`. `dateText` (`labels.ts:88-91`) returns null for `unknown: true`, a missing date or a malformed date, so those cases still fall through to the `Unknown` component. A cell with `unknown: true` and a stray `date` therefore still reads Unknown. `formatDayMonth` also returns UNKNOWN on bad input. A date column with no cell still draws `<Unknown />` (`Sections.tsx:176`).
- **`proposals.ts` `columnDayMonth`.** It compares `date_format === 'day_month'` exactly, so any other value falls back to the full date. Nothing from the data reaches the markup apart from the formatted date.
- **`mock-contract.test.ts`.** The `date_format` stripping runs only after `expect(...).toBe('day_month')`. Fixtures that do not carry the field are not stripped, so the "validate with no stripping" rule from AC 26 still holds. No assertion was removed or relaxed.
- **Tests.** `minutes.test.tsx` now checks that the unknown due date renders with the `psl-unknown` class, not as plain text. It also checks the date with and without `day_month`.
- **No other changes.** Nothing in this round touches confirm sets, locks, decision links, the prefill, restricted handling, requests or dependencies.
