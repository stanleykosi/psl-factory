VERDICT: PASS
COMMIT: 3b8d10de03c23bf581a9b941189eb38a74b22681
REVIEWER: reviewer-technical
AUTHORITY: reviewer-technical

## Summary
- The adapter `src/features/work-list/` matches the spec. It types from `live-schema.d.ts` and drops stale answers with a request counter. It skips empty pages up to 10 requests, then shows "Keep looking". A failed page keeps the rows shown and offers Try again.
- It is reusable for F-63. It takes `queue` as a parameter. `index.ts` exports a small surface with a documented header. `grep` finds no import from `features/exceptions` or `features/verified` inside `work-list`. `ROW_TAGS` is a `Record<WorkState, ...>`, so a new state fails the typecheck.
- Unknown counts are never shown as 0. `evaluated` is kept but never rendered. Deferred reads "n more items" or "8 or more". The toolbar shows "{n} shown", with "so far" while pages remain. The shown-count text is hidden when the list is empty and complete.
- Both screens are read-only. Titles link to `/work/{id}` by integer id, not `django_url`. "Open output" reads one item on press and only opens http/https. No `/api/v1/exceptions` call remains in the source. `schema.d.ts` still lists the path as generated output, and `src/api/*` is untouched.
- checks.md shows GATE PASS on this head. I did not run the live backend, because the diff and tests cover the contract.

## Findings
- TECH-1-1 | non-blocking | low | frontend | The first page is not de-duplicated by `id`, only later pages are (`useWorkList.ts` `load` versus `loadMore`). A server repeat inside one page is unlikely, so no change is needed now.
- TECH-1-2 | non-blocking | low | frontend | `window.open` runs after an awaited read in `VerifiedList.tsx` `OpenOutput`. Safari or a popup blocker may suppress the new tab. The spec asks for exactly this read-on-press design, so it is worth checking once against live Django.
- TECH-1-3 | non-blocking | low | frontend | Before "Keep looking", an empty list with `more='keep-looking'` shows "0 shown so far" in the toolbar. The 0 is a real count of loaded rows, not an unknown. Consider hiding it until rows exist.

## Verified

## Delta re-check (2957a375)

VERDICT: PASS

- F-62's own code (`src/features/work-list`, `exceptions`, `verified`) is unchanged since 3b8d10de. It does not read the new 1.26.0 fields (`total`, `total_coverage`, `page_size`, `queue_output_url`). The existing reads stay valid.
- The fixture changes only add the new 1.26.0 fields to the row and page builders (`tests/work-list-rows.ts`, `mock/live-work.mjs`). The values are null, with `total_coverage: 'incomplete'`.
- No assertion was weakened. The only assertion edits in `verified.test.tsx` and `exceptions.test.tsx` change the expected sign-in href to `/sign-in?next=...`. This follows the merged /sign-in links.
- Unknown counts are still never shown as 0. `total: null` is not rendered, and the code that shows counts is untouched.

Findings: none new. TECH-1-1 to TECH-1-3 stand, all non-blocking.
