# The factory floor shows live recorded work per line, with a way into each line's queue

> Tasks: FE-CONNECT-1 (SCR-06). Architecture: package v9, live API 1.22.0 (`contracts/psl-factory.openapi.json`). Design: approved canvas as built in F-08 (no new boards for the reduced floor); screens: SCR-06 (flat and 3D floor, phone and desktop).

## Summary
- `/overview` reads live `GET /overview` and shows one row per factory floor with the lines that have recorded work, "Updated at" from `as_of`, and each line's `total`.
- Everything the live API does not return (four headline totals, station squares, "needs a person" marks, tag label and colour) shows as "Not available yet" or is left out. Nothing is computed or defaulted to 0.
- Every line opens its work in the existing queue at `/my-work?line=<key>` (the SCR-01 screen, which reads `GET /work?line=`).
- States: loading, empty, error with retry, 403 (shown, follows the server), signed out.
- The v7 `/overview` mock, its types and station-work read are removed from this screen; tests cover each state.

## Context
- Page: `frontend/src/features/overview/OverviewPage.tsx` (`OverviewPage`, `FactoryFloor`, `LineRows`). Hook: `useOverview.ts` (calls v7 `api.GET('/api/v1/overview')`, polls every 15 s, 401/403/404 stop polling). Types: `types.ts` (from v7 `@/api/schema`). Identity map: `lines.ts` (`LINE_IDENTITY` keyed by floor name, `tagTone`).
- 3D floor: `src/features/floor/Floor3D.tsx`, `scene.ts` (reads `line`, `stations[]`, `note`, `status`), `support.ts` (`FloorProps`, `describeStation`, `floorLabel`), `StationStrip.tsx`, `stationWork.ts` (v7 station-work read; not valid live).
- Live client: `src/api/client.ts` exports `liveApi` (typed by `src/api/live-schema.d.ts`) and `call`. Use `call(liveApi.GET('/api/v1/overview'))`.
- Live shape, `workspaces_overview`: `{ as_of: date-time, lines: [{ key, title, total }] }`. Backend (`apps/core/factory_api/workspaces.py`, `overview`) groups the signed-in person's discoverable work by line definition, excludes verified and cancelled work, and returns only lines with at least one such item, sorted by title. There is no role check in that handler.
- `/me` `destinations[]` is the same six entries for every account (A-36), so `hasDestination(me, 'overview')` is always true today; keep that check as is.
- Queue: `src/features/my-work/model.ts` already parses `?line=<key>` into the view and sends it as `line` on the work read.

## Contract

### Read: `GET /api/v1/overview`
- Request: no parameters. Same-origin session cookie. No writes, no idempotency or versioning.
- 200: `{ as_of, lines: [{ key, title, total }] }`. `total` is a non-negative integer.
- Permission and tenant rule: the server decides. The client shows what it returns and adds no role or tenant rule.
- Errors, from the error `kind` in `src/api/errors.ts`: `unauthenticated` (401) shows the signed-out state; `forbidden` (403) and `not_found` (404) show the not-open state and stop polling; anything else shows the error state with retry and keeps polling.
- Polling: keep the existing 15 s visible-tab poll and the stale-response drop in `useOverview`.

Fixture (add to the mock and tests):
```json
{ "as_of": "2026-11-23T09:30:00Z",
  "lines": [
    { "key": "commercial/v1", "title": "Costing and commercial submission", "total": 3 },
    { "key": "rfp-response/v1", "title": "RFP response and project handoff", "total": 1 },
    { "key": "pmo-finance/v1", "title": "Invoice preparation and delivery", "total": 4 },
    { "key": "pmo-minutes/v1", "title": "Formal minutes and action handoff", "total": 2 },
    { "key": "future-line/v1", "title": "A line added later", "total": 5 } ] }
```

### Line key to floor map (local, versioned: `FLOOR_MAP_VERSION = 1` in `src/features/overview/lines.ts`)
A-35 is open; PSL keeps this map until the backend gives a group. Floors keep the design's name, subtitle and avatar from `LINE_IDENTITY`.

| Floor | Keys |
|---|---|
| Pre-sale | `rfp-response/v1`, `commercial/v1` |
| Planning | `engagement/v1`, `planning/v1` |
| Release | `delivery-release/v1`, `delivery-go-live/v1` |
| Closing | `delivery-hypercare/v1`, `delivery-handover/v1`, `delivery-archive/v1`, `delivery-closure/v1` |
| Invoices | `pmo-finance/v1` |
| Month-end | `finance-accounts/v1`, `finance-schedules/v1`, `finance-ppe/v1` |
| Cash and BU | `finance-forecast/v1`, `finance-bu/v1`, `finance-ledger/v1` |
| Payroll | `finance-payroll/v1` |
| Other lines (no avatar, subtitle "Not on a floor yet") | every other key, including the PMO lines `pmo-issues/v1`, `pmo-leadership-report/v1`, `pmo-minutes/v1`, `pmo-escalation/v1`, `pmo-weekly-report/v1`, `pmo-emergency/v1`, `pmo-change/v1`, `process-handoff/v1`, and any key not listed |

Rules: floors appear in the order above, "Other lines" last. A floor with no returned line is not drawn (the API omits lines with no recorded work, so an absent floor is not shown as 0). Unmapped keys are never dropped. The map is data in one file with a test that every key in the fixture lands on exactly one floor.

### Screen: `/overview`
Each floor row shows: avatar and name, subtitle, then its lines. One line per returned key: `title`, the number `total` with the label "recorded work", and a link "Open work" to `/my-work?line=<key>` (URL-encode the key). A floor's headline number is the sum of its lines' `total`, labelled "recorded work". Where the board draws the tag, show a neutral "Not available yet" tag. Where it draws the station track, draw no squares and no "needs a person" marks.

Header: eyebrow "FACTORY FLOOR · UPDATED <as_of> WAT" (use `When`). Where the board draws the four totals (desktop) or the two-figure summary (phone), show one short line "Totals are not available yet." No numbers. A footnote under the rows says: "The number on each line is the work recorded for that line that you can see."

Do not use the words "open", "in progress" or "needs a person" for `total` (A-33).

| State | What shows |
|---|---|
| Loading | `LoadingState` under the page title |
| Empty (`lines: []`) | `EmptyState` "No lines to show yet." with "Lines appear here when work you can see starts." View switch hidden |
| Error | `ErrorState` "We couldn't load the factory floor." with "Try again"; text names last load time when there was one and the error `code` as reference |
| 403 or 404 | `EmptyState` "The factory floor isn't open to your role." with the server's message. No retry button. Polling stopped |
| Signed out (401) | `SignedOutState` for `/overview` |
| Success | rows as above |

Kept as is: the "All exceptions · everyone's" section and its link to `/exceptions`; the Flat / 3D floor switch and its hints for reduced motion, no WebGL and phone.

### 3D floor
Keep `Floor3D` working. Add a small adapter in `src/features/overview/` that turns each floor into the shape the scene needs: one machine per returned line (name = line title, count = `total`), with `needs_person` fixed false and a neutral tag. The scene and the strip must show no "PERSON" mark and no "no person needed" wording for these. Pressing a machine opens a strip with the count and an "Open work" link to `/my-work?line=<key>` instead of the v7 station-work read (`useStationWork`). The flat view must stay reachable and the page must fall back to flat on failure, reduced motion, narrow window or no WebGL, as today.

## Lanes
- Frontend lane owns: `frontend/src/features/overview/*`, `frontend/src/features/floor/*` (only to remove the v7 station-work read and accept the adapted shape), the overview tests listed below, and the mock handler for `/api/v1/overview`.
- Backend lane: none. No backend change.
- Integration owner: checks the live server against the shape (`oa.py live GET /api/v1/overview`) and runs the live smoke in Acceptance.
- Shared files: `src/api/live-schema.d.ts` and `src/api/client.ts` (read only, owned by the API layer, no edits); `src/features/my-work/*` (read only; if `/my-work?line=` does not yet read live `GET /work`, that is its own feature, leave it).

## Acceptance criteria
1. Page reads the live operation. verify: `grep -rn "liveApi.GET('/api/v1/overview')" frontend/src/features/overview` finds the call; no `api.GET('/api/v1/overview')` and no import of the v7 overview type remain in `src/features/overview` or `src/features/floor`.
2. Success with the fixture. verify: a test renders `/overview` and sees "UPDATED" with the `as_of` time and "WAT", floor rows Pre-sale (4), Invoices (4), Other lines (7), and a line titled "Costing and commercial submission" with 3 and "recorded work".
3. Unmapped key is kept. verify: test shows "A line added later" with 5 under "Other lines"; a map test asserts every fixture key lands on exactly one floor and a floor with no lines is not rendered.
4. Nothing is invented. verify: test asserts the page contains no "IN PROGRESS", "NEED A PERSON", "STOPPED" or "VERIFIED THIS MONTH" figures, no "needs a person" text, no "Stopped"/"Waiting" tag, no station squares, and that "Totals are not available yet." and "Not available yet" show.
5. Drill-down. verify: test clicks "Open work" on the commercial line and the link's href is `/my-work?line=commercial%2Fv1`; opening it in the running app lists work for that line only.
6. Empty. verify: with `lines: []` the page shows "No lines to show yet." and no Flat/3D switch.
7. Error with retry. verify: a 500 shows "We couldn't load the factory floor." and "Try again"; pressing it with a later 200 shows the rows. A network failure shows the same state.
8. 403 and 404. verify: a 403 shows "The factory floor isn't open to your role." with the server's message, no "Try again", and no further `/overview` request after 20 s of fake time. Wrong user and wrong tenant are covered by the server answering 404 or an empty list; the test feeds both and shows the not-open state and the empty state.
9. Signed out. verify: a 401 shows the signed-out state with a sign-in link for `/overview`.
10. Loading. verify: before the response resolves the page shows `LoadingState` and no rows.
11. Polling. verify: with fake timers a second request goes out after 15 s while visible, an older response arriving late is dropped, and a 403 stops polling.
12. 3D floor on reduced data. verify: test with WebGL stubbed shows the 3D view for the fixture with one machine per line, no "PERSON" mark, and the pressed machine's strip shows the count and an "Open work" link; with reduced motion, the flat view shows and the hint appears.
13. Phone. verify: at 390 px width the page shows the title, rows, the "Updated" line under the rows and no 3D switch; at 1440 px the eyebrow shows above the title.
14. Live smoke. verify: against the local live backend (account `live-lead`), `/overview` shows the same line titles and totals as `curl -b <session> /api/v1/overview`; an account with no work shows the empty state.
15. The mock matches the live shape. verify: the mock handler for `/api/v1/overview` returns exactly `{as_of, lines[{key,title,total}]}` and the existing contract-drift test (`tests/api-live-schema-drift.test.ts`) passes; v7-only overview tests (`tests/mock-overview.test.ts`, `tests/overview*.test.tsx`, `tests/floor*.test.ts*`) are rewritten to the live shape, not deleted without replacement.

## Out of scope
- Any backend change, any new endpoint, and any write.
- Computing totals, station counts, tags or "needs a person" from `total` or from `/work`.
- A client-side role rule for `/overview` beyond the existing nav check on `/me`.
- SCR-10 exceptions, SCR-14 verified outputs, connecting `/my-work` itself to live `GET /work`, and a new queue screen.
- Moving the key-to-floor map to the backend, renaming floors, or new avatars.

## Assumptions
- Meaning of `total` (A-33): the backend code counts the person's discoverable work except verified and cancelled, one count per line. We still word it "recorded work" until the backend answers.
- A line with no such work is absent from the response; a floor with no returned lines is not drawn, so absence is never shown as 0.
- Floor sum: a floor's headline number is the sum of its lines' `total`; lines never overlap in the response, so this is a plain sum of known values.
- PMO lines (issues, minutes, escalation, weekly and leadership reports, emergency, change) and `process-handoff/v1` have no floor in the design, so they sit under "Other lines".
- The neutral "Not available yet" tag keeps the board's tag position and avoids a colour that would imply a status.
- 404 is treated like 403 (not-open state), as the existing hook does.
- A-36 (roles) is not answered: no client role rule; the server's 403 decides.
- The link target is `/my-work?line=<key>`, because `model.ts` already parses it and that is the SCR-01 queue.

## Questions for the design engineer
1. The four headline totals (IN PROGRESS, NEED A PERSON, STOPPED, VERIFIED THIS MONTH) and the phone's two-figure summary; the live API returns none (A-34). (a) Recommended: keep the board's place but show one line "Totals are not available yet." (b) Hide the whole block until the backend adds them. (c) Show the four labels with "Not available yet" under each.
2. Station squares and "needs a person" marks on each row; the live API has no stations. (a) Recommended: remove the squares and show each line as a title, a number and an "Open work" link. (b) Draw one square per line with its `total`, in the neutral colour only. (c) Hide the station track and keep only the floor's sum.
3. The tag on each row (Stopped, Waiting, Verified and so on). (a) Recommended: a neutral "Not available yet" tag. (b) Hide the tag column. (c) Replace it with the recorded-work count as a tag.
4. The eight floors are rebuilt from our own key-to-floor map, and PMO lines have no floor. (a) Recommended: a ninth "Other lines" floor, shown last, with no avatar. (b) Add a "PMO" floor with a new subtitle and an existing avatar. (c) Show one flat list of lines with no floors.
5. The 3D floor has no stations to show. (a) Recommended: one machine per line with its total, neutral colour, strip with an "Open work" link. (b) Keep the 3D switch but show one block per floor with the floor's sum. (c) Hide the 3D view for this release and show flat only.
6. Strip opened from a square in the flat view lists the station's work (design D-165). (a) Recommended: remove it; "Open work" goes to the queue for that line. (b) Keep a small inline strip showing the line's count and the same link.

## Conflicts with the boards
The spec removes or changes parts the SCR-06 boards draw. Each is listed with its question above.
- Four totals block and the phone summary: replaced by "Totals are not available yet." (Q1).
- Station track with squares, counts and orange "needs a person" squares: removed (Q2).
- Row tag with colour and label: neutral "Not available yet" (Q3).
- Eight floors with fixed rows: only floors with returned lines; a new "Other lines" floor that no board draws (Q4).
- 3D floor: machines are lines, not stations (Q5).
- Station press opens the station's work inline: replaced by the link "Open work" (Q6).
- New text no board draws: "recorded work" label, "Open work" link, the footnote on what the number means, and the "Not available yet" wording.
