# /my-work shows its existing error state on live rows instead of crashing

> Tasks: none (readiness lists none). Architecture: none; no endpoint, record or contract changes. Design: no new design; screens: the existing /my-work error state (`shell-errorcard`).

## Summary
- With the live `GET /work`, `/my-work` no longer throws at `WorkRows.tsx:11` (`KINDS[kind]` is undefined).
- Rows that do not match the v7 shape are caught where the page loads them. The page then shows its existing "couldn't load" error card.
- Frontend only, inside `frontend/src/features/my-work` plus one test file. No new copy, states, data or endpoints.
- The v7 mock path behaves exactly as before. F-63 connects the page to live rows later.

## Context
- `frontend/src/features/my-work/WorkRows.tsx:11` `KindTag` reads `KINDS[kind]` (from `model.ts:59`, keys `decide|do|fix|started`) and dereferences `.family`. A live row has an unknown or missing `kind`, so it throws and blanks the page.
- `frontend/src/features/my-work/MyWork.tsx` already has `ListState` (`loading | ready | error`). It renders the error card at about line 352 ("We couldn't load your queue. Your work is safe; nothing was changed." with a reference code and "Try again"). It also has a `forbidden` EmptyState.
- Rows enter state in three places: `load` (page 1, about line 110), `refresh` (re-read page 1) and the Show more handler (about line 160). All three take `data.items` from `fetchPage`.
- Existing tests: `frontend/tests/my-work.test.tsx`, `frontend/tests/my-work-model.test.ts`, `frontend/e2e/my-work.spec.ts`.

## Contract
No API change. One client-side rule applies to every list response before its rows reach state.

- **Valid row:** `kind` is a key of `KINDS` (`model.ts`), and nothing else is checked. This is the one field that crashes.
- **Invalid row:** if any item in a response fails the check, treat the whole response as a failed load. Do not render partial rows.
  - On `load`, set `list` to `{ status: 'error', error }`. `error` is an `ApiError` built with the existing helper (`networkError()` in `@/api/errors`, or an existing equivalent), not new copy.
  - On `refresh` and Show more, follow the existing failure paths (`setRefreshFailed(true)` and `setMore('error')`). Rows already on screen stay.
- Add a small pure helper (for example `isV7Row(item)` in `model.ts`) that the three call sites share.

Screen states:
- **Loading, empty, success (v7 rows):** unchanged.
- **Error (live rows):** the existing `shell-errorcard`, unchanged words. "Try again" re-runs `load`, which on live rows lands in the same error state.

Fixture (live-shaped, not a v7 row), as in the unit test:
```json
{ "items": [ { "id": "work-1", "kind": "weekly_report", "title": "Weekly report" } ], "next_cursor": null, "as_of": "2026-11-23T09:00:00Z" }
```

## Lanes
- Frontend lane: `frontend/src/features/my-work/MyWork.tsx`, `model.ts`, and one new or extended test in `frontend/tests/my-work.test.tsx`.
- Backend lane: none.
- Integration owner: runs the live check below. Shared files: none. `WorkRows.tsx` needs no edit, because the guard keeps bad rows out of it.

## Acceptance criteria
1. With a live-shaped `/work` response (fixture above), `MyWork` renders without throwing and shows the existing error card — verify: new vitest case in `frontend/tests/my-work.test.tsx` asserts `role="alert"` with "We couldn't load your queue" and no thrown error; `cd frontend && npx vitest run tests/my-work.test.tsx`.
2. The same guard covers refresh and Show more: a live-shaped row on either path does not throw, and rows already shown stay — verify: two further vitest cases in the same file.
3. The v7 mock behaviour is unchanged — verify: the existing `my-work.test.tsx`, `my-work-model.test.ts` and `e2e/my-work.spec.ts` pass unedited. `git diff` shows no change to existing assertions.
4. No new design and no new words — verify: `git diff` over `frontend/src` adds no new user-visible string, no CSS change and no new component. The error card text matches the existing copy at `MyWork.tsx` (about line 352).
5. Live check — verify: against the local backend on 55433 as `qa-seed`, with lane C's work item 1 (a weekly report) present, open `/my-work`. The page shows the error card, the console has no uncaught error, and the shell stays up. Attach a screenshot of the state shown to the round evidence.
6. Negative: a v7 row with a valid `kind` among live-shaped ones still fails the whole response and shows the error card — verify: vitest case with a mixed list.

## Out of scope
- Mapping live rows into the page, new copy or states, a "not yet connected" message, new data or endpoints. F-63 owns the real connection.
- Any change to the v7 mock path, `WorkRows.tsx` rendering, other features, or shared components in `@/components` or `@/shell`.
- Dropping bad rows and showing the rest.
- Validating fields other than `kind`.
- Files in `delivery/config.json` `protected_paths` stay unchanged.

## Assumptions
- Whole-response failure rather than skipping bad rows: showing partial live data as the v7 page would imply a connection F-63 has not made.
- Checking only `kind`: it is the one field that crashes; other fields are F-63's mapping.
- Reusing `networkError()` for the error object: the card needs an `ApiError` (it prints `error.code`), and the readiness scope forbids new copy.
- The live check uses the error card, not the "not open to your role" EmptyState, because that is the existing state for a failed load.

## Conflicts with the boards
None. The spec adds, moves and removes nothing a board draws; the error card is the existing state. Recommendation: no design action. If the design engineer wants a distinct "not connected yet" state for live data, that belongs to F-63.
