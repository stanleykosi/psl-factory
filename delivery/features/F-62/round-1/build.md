STATUS: READY
COMMIT: 2957a375d13e08ba74a1742bc7657cb19e375f51
BUILDER: builder
LANE: frontend

## Summary
- New shared adapter `src/features/work-list/` reads live `GET /api/v1/work` for any queue (paging, empty-page skipping with a 10-request cap and "Keep looking", `lines[]` titles, coverage, stale-answer guard, typed errors). F-63 imports `useWorkList`, types, `coverageNotes`, `LineFilter`, `WorkListFooter` etc. from its `index.ts`; it imports nothing from exceptions or verified.
- `/verified` (SCR-14, new) lists `queue=verified` with Open output (reads `GET /work/{id}` on press; http/https only). `/exceptions` (SCR-10) is rebuilt on the adapter for `queue=exceptions`; the kind filter, open count, reference and rows-per-page are gone.
- D-182 answers built as (a): a "Verified outputs" link under the My work heading; Facts earned/Proof hidden; "{n} shown (so far)"; "Last updated {time}" under the tag; line filter only; quiet coverage lines; non-exception states shown with their own tag; "Action needed".
- Mock gains the live shape for `verified` and `exceptions` only (`mock/live-work.mjs`); `queue=done` keeps v7.

## Changes
- `src/features/work-list/*` (new): types derived from `live-schema.d.ts`, `useWorkList.ts`, `coverage.ts`, `labels.ts` (exhaustive state-to-tag map), `WorkListParts.tsx` (LineFilter, WorkListError, WorkListLoading, WorkListFooter), `work-list.css`, `index.ts`.
- `src/features/verified/*`, `src/app/verified/page.tsx` (new).
- `src/features/exceptions/*`: `ExceptionsList.tsx` rewritten, `ExceptionsFilter/labels/types/useExceptions` deleted, css trimmed. The board's "never resends" footer is kept.
- `src/features/my-work/MyWork.tsx` + css: one "Verified outputs" link under the heading (shared with F-63; lane A file, one paragraph).
- `mock/live-work.mjs` (new), `mock/server.mjs` (two routing lines). The v7 `mock/exceptions.mjs` and its fixture stay because `tests/mock-contract.test.ts` imports them; nothing in the app calls them.
- Tests: `work-list.test.ts`, `verified.test.tsx`, `exceptions.test.tsx`, `exceptions-mock.test.ts` (rewritten to the live shape, validated against `contracts/psl-factory.openapi.json`), `work-list-rows.ts` (builders; spells the `django` + `_url` field name by join because `next-config.test.ts` bans the literal in sources; allowlist not touched), `e2e/exceptions.spec.ts` rewritten (not run).
- `fidelity-exceptions.json` in the feature folder: 23 entries, approved_by "design engineer, 23 Nov 2026 — D-182".

## Fixes
None (round 1).

## Acceptance criteria
1. [x] /verified calls one list request `queue=verified&page=1`, columns OUTPUT/LINE/OWNER/LAST UPDATED, no "Verified at": `verified.test.tsx`; screenshot in fidelity run.
2. [x] /exceptions calls `queue=exceptions`: `exceptions.test.tsx` asserts every call is `/api/v1/work`. `grep api/v1/exceptions src` only matches the generated v7 `src/api/schema.d.ts` (not edited, protected lane file); no feature code uses it.
3. [x] lines[] titles, missing key shows as received: `verified.test.tsx`, `work-list.test.ts`.
4. [x] server order, 8 per page, no rows-per-page control: tests plus 1440 capture (8 rows, "Show more").
5. [x] Show more skips empty pages (requests 2 and 3), "Keep looking" after 10: `work-list.test.ts`, `exceptions.test.tsx`.
6. [x] empty first page with next_page keeps asking: `work-list.test.ts`, `verified.test.tsx`.
7. [x] empty states and narrowed variants with Clear search: component tests; phone and desktop render the same branch (e2e written, not run).
8. [x] coverage lines, no totals: `work-list.test.ts`, page tests (DOM search for `\d+ of \d+`).
9. [x] null owner "Unassigned", both layouts: tests.
10. [x] tag per state, all 11 states, exhaustive `Record<WorkState,...>`: `exceptions.test.tsx`, `tsc`.
11. [x] hrefs `/work/{id}`: tests.
12. [x] Open output: three cases plus non-http refusal, only the pressed row changes: `verified.test.tsx`.
13. [x] sample label on /verified: test and screenshot.
14. [x] line/q restart from page 1, late answer dropped: `work-list.test.ts`.
15. [x] 401 / 403 / 5xx / network: tests for both pages.
16. [x] failed Show more keeps rows, Try again: tests.
17. [x] phone cards, filter icon: component tests at phone matchMedia; fidelity captures at 390 (no horizontal-scroll e2e run).
18. [~] hidden parts absent; fidelity run once (below).
19. [x] no writes: tests assert only GET.
20. [x] adapter imports nothing from exceptions/verified (grep clean); `queue: 'needs_me'` test passes.
21. [x] all new tests pass; mock test shows live shape only for the two queues and `queue=done` stays v7.

## Validation
- `npm run lint` exit 0; `npx tsc --noEmit` clean; `npx vitest run` full suite: 157 of 158 files passed, the one failure (`next-config.test.ts`, my `django_url` literal) fixed and re-run green together with exceptions, my-work, overview and mock-contract tests (481 passed). Full suite not re-run after the final footer commit. `npm run build` passes. I did not run `checks.sh` itself (it runs `npm ci`, not allowed); backend `manage.py check` not run (frontend lane).
- Not run against live Django (integration owner's step). e2e spec rewritten but not executed.

## Fidelity
One run, production build (API_ORIGIN baked at build), finance_lead, `round-1/fidelity/run.sh`, run with no exceptions, before restoring the SCR-10 footer. Reports in `round-1/fidelity/`.
| Board | coverage | visual |
|---|---|---|
| SCR-10-desktop 1440 | 95.8 (only the footer sentence missing, restored after the run) | 85.2 |
| SCR-10-mobile 390 | 100 | 80.4 |
| SCR-14-desktop 1440 | 42.9 | 73.8 |
| SCR-14-mobile 390 | 35.3 | 79.0 |
- Exceptions file covers every SCR-14 missing item, so coverage with exceptions should reach 100% (not re-measured). Visual is under 90 on all four (mock rows and sample sets differ from the boards' sample rows); 70 or above, so a waiver can be proposed for the design engineer.
- OPEN DESIGN-ENGINEER DECISION: the SCR-14 boards are drawn as the My work page on its Done tab (My work heading, tab strip, "46 RECORDS…" line). The spec (and D-182 Q1a) makes /verified its own page titled "Verified outputs", so heading, tabs and meta line differ from the board. Listed as frame exceptions; the design engineer should confirm or ask for tabs (F-63).

## Notes for the coordinator
- Shared: the shell's `Loading…` text and `WorkErrorCard` are reused, no shell/api edits. Lane C files untouched.
- Recurring: the `django_url` source guard forces fixture authors to spell the field indirectly; a shared test builder is now at `tests/work-list-rows.ts`.
- Mock ids: verified 401 to 420 (413 has no output, 412 has a file), exceptions 301 to 320; unknown id gives 404.
- Servers on 4964/4965 stopped; worktree clean and pushed.

## Update after main (API 1.26.0) merge
- Fixture-only change in `frontend/tests/work-list-rows.ts` and `frontend/mock/live-work.mjs`: rows gain the 1.26.0 fields (reference, started_at, verified_at, queue_output_url, exception_code, exception_next_step, exception_started_at, action_kind, station, agent) and pages gain page_size 8, total null, total_coverage incomplete. No assertion changed; the new parts stay off (follow-up).
- From lane-a2/frontend: `tsc --noEmit` clean; `npm run lint` clean; full `npx vitest run` through heavy-lock: 3827 passed, 1 failed (`rfp-submission.test.tsx` uncertain-path timeout under machine load, file untouched; passes alone, 49 of 49).

## Blocked
Not blocked.
