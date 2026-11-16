VERDICT: PASS
COMMIT: a3f43067bf20e8474e3a6bb54d273597154d6f28
REVIEWER: reviewer-technical
AUTHORITY: delivery technical review

## Summary
- Reviewed 0d6dabf7..a3f43067 (frontend). The round-3 code change is three source lines in `Sections.tsx` and `proposals.ts`, plus fixtures and tests. The dlv-00 merge touched no frontend source, as the builder states.
- Date cells are restored as `date` cells. The "13 Nov" form comes from a fixtures-only column option, not from text, so INV-UNKNOWN holds: an unknown date still draws the amber Unknown, never 0 or blank.
- The `columns[].date_format` proposal is read in one typed reader, validated on its own and stripped in the contract test. It is guarded to W-23xx fixtures.
- No findings.

## Findings
None.

## Verified
- UI-2-1 (technical side) | verified | `CellValue` passes `short={columnDayMonth(column)}` only for `date` columns. `DateText` shortens only when the date exists and parses (`dateText !== null`). Otherwise it falls back to `Unknown`. Without the option the full date shows, as before, so F-17/F-21/F-22 date cells are unchanged. `formatDayMonth` is the shared component helper, not a local copy.
- Proposal hygiene | verified | `columnDayMonth` accepts only `"day_month"`. `mock-contract.test.ts` asserts the value and deletes the key before the schema check. `schema.d.ts` and `openapi.json` are untouched.
- TECH-2-1 | verified | The new test checks both `items[].values` and `columns[].date_format`, requires at least one carrier of each, and limits both to `W-23xx` files. The `links`/`items_default` guard is retained.
- DRAFTED tone | verified | The change is in fixtures only (tone `agent`). The frame maps the tone through the existing `tagTone`, with no new frame code.
- Task-card correction | verified | The builder's note that W-2009 (F-17) and W-2208 (F-21) lose their card is accurate for the round-2 rule. Both are behaviour fixtures that keep the `task_id` decision link, and their suites pass in `checks.sh`. TECH-2-2 stays non-blocking.
- Scope | verified | No change to `src/api`, `architecture`, `design`, `apps` or protected paths in this diff.
