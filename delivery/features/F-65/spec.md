# The factory floor shows live recorded work per line, with a way into each line's queue

> Tasks: FE-CONNECT-1 (SCR-06). Architecture: package v9, live API 1.24.0 (`contracts/psl-factory.openapi.json`, `/Users/Hunchoo/psl-factory`, main). Design: approved canvas as built in F-08 (no new boards for the reduced floor); screens: SCR-06 (flat and 3D floor, phone and desktop).

## Changes for 1.24.0
Source: `delivery/connect/backend-answers.md` (A-33 to A-36), `backend-answers-2026-11-23.md`, `contracts/psl-factory.openapi.json` 1.24.0. All D-182 answers by the design engineer stay.
- `GET /overview` is unchanged in 1.24.0 (`{as_of, lines[{key,title,total}]}`). The data D-182 hid is on a second read, `GET /work/counts` (`work_counts`, A-34). The page now makes two reads: the line list from `/overview` and the figures from `/work/counts`.
- A-33 answered: `total` is the person's discoverable work excluding verified and cancelled. The label changes from "recorded work" to "open work" and the footnote is reworded. This is a wording change (Q3).
- A-34 answered by `/work/counts`: four headline totals, per-line station counts and `needs_person` are now built as the board draws them. Replaces "Totals are not available yet" and "no squares" for the success case. "Not available yet" stays only for the case where `/work/counts` fails or a line has no known counts.
- A-35 answered: the backend does not group lines (floor grouping is "a display mapping owned by the frontend"). The local floor map therefore STAYS (`FLOOR_MAP_VERSION = 1`); it cannot be dropped.
- A-36 answered: no role rule, only record scope; a person may get an empty list. No 403 for role is expected; 403 handling stays only for server refusals. The "not open to your role" wording becomes "isn't open to you".
- Counts are sampled: `/work/counts` evaluates at most the 50 most recent authorised items and returns `limited` (true when it did not cover all of them) and `evaluated`. Queue totals are `null` when limited. Figures from it are shown as observed, never as exact totals, never as 0 when unknown.
- The row tag (status label and colour) is still not supplied by any read; it stays neutral "Not available yet" (D-182 Q3 kept).
- The 3D floor can now show real station counts and the "person" mark, from `/work/counts`.
- New questions: 7 to 9.

## Summary
- `/overview` reads live `GET /overview` (line list, `as_of`, open-work `total` per line) and `GET /work/counts` (headline totals, per-line station counts, "needs a person", coverage), and draws the SCR-06 board: eyebrow, four totals, floor rows with station squares, 3D floor.
- Counts are sampled (`limited`, `evaluated`). Every figure from `/work/counts` carries its coverage; when it is limited the figure reads "at least N" and never as a final total. An unknown figure is "Not available yet", never 0.
- Floors still come from the local key-to-floor map (the backend does not group lines); unmapped keys go under "Other lines".
- Every line opens its work at `/my-work?line=<key>` (SCR-01, `GET /work?line=`).
- States: loading, empty, error with retry, partial (counts failed), 403/404, signed out; the v7 `/overview` mock, types and station-work read are removed.

## Context
- Page: `frontend/src/features/overview/OverviewPage.tsx` (`OverviewPage`, `FactoryFloor`, `LineRows`). Hook: `useOverview.ts` (calls v7 `api.GET('/api/v1/overview')`, polls every 15 s, 401/403/404 stop polling). Types: `types.ts` (from v7 `@/api/schema`). Identity map: `lines.ts` (`LINE_IDENTITY` keyed by floor name, `tagTone`).
- 3D floor: `src/features/floor/Floor3D.tsx`, `scene.ts` (reads `line`, `stations[]`, `note`, `status`), `support.ts` (`FloorProps`, `describeStation`, `floorLabel`, station-change detection), `StationStrip.tsx`, `stationWork.ts` (v7 station-work read; not valid live).
- Live client: `src/api/client.ts` exports `liveApi` (typed by `src/api/live-schema.d.ts`) and `call`.
- Live `GET /api/v1/overview` (`workspaces_overview`, `apps/core/factory_api/workspaces.py`): `{ as_of, lines: [{ key, title, total }] }`, only lines with at least one discoverable item that is not verified or cancelled, sorted by title. `total` = that count (A-33). No role check (A-36).
- Live `GET /api/v1/work/counts` (`work_counts`, `apps/core/factory_api/work.py`, `counts`): query `line?`, `project?`, `q?`, `verified_month?` (YYYY-MM, default this month). Response `{ as_of, evaluated, limited, verified_month, queues[{key, observed, total|null}], lines[{ key, needs_person, held, open, stopped, verified, verified_this_month, stations[{ key, count, needs_person }] }] }`. It evaluates at most the 50 most recent authorised items; `limited` is true when not all were evaluated; queue `total` is `null` when limited. `stopped` counts cancelled and follow-up-needed items. Station keys: `intake`, `execution`, `decision`, `delivery`, `verified` (every line entry lists all five). A line appears only if one of the evaluated items belongs to it.
- `/me` `destinations[]` is the same six entries for every account, so `hasDestination(me, 'overview')` is always true; keep that check.
- Queue: `src/features/my-work/model.ts` already parses `?line=<key>` and sends it as `line` on the work read.

## Contract

### Reads (both through `call(liveApi.GET(...))`)
- `GET /api/v1/overview` and `GET /api/v1/work/counts`: no parameters sent. Same-origin session cookie. No writes, no idempotency or versioning. Send both on mount and on each 15 s poll, together; each response is dropped if a newer round has started.
- Permission and tenant rule: the server scopes both reads to the signed-in person. The client shows what comes back and adds no role or tenant rule.
- Errors, from `kind` in `src/api/errors.ts`:
  - `/overview` `unauthenticated` (401): signed-out state. `forbidden` (403) or `not_found` (404): not-open state, stop polling. Anything else: error state with retry, keep polling.
  - `/work/counts` failing while `/overview` succeeds (any status, including 503 `read_limited`): partial state. The floor draws with line totals; headline totals show "Totals are not available yet." and each row shows no station squares and "Not available yet" where the squares go. Polling continues. A 401 on either read is signed-out.
- Polling: keep the 15 s visible-tab poll and the stale-response drop.

### Joining the two reads
- The row list is the `/overview` lines. Row figures: `total` from `/overview`; stations and `needs_person` from the `/work/counts` line with the same `key`.
- A row with no counts entry: when `limited` is false, every item was evaluated, so the line has no stations to draw: show the five stations as 0 (known). When `limited` is true, the figures for that row are unknown: show "Not available yet", never 0.
- Headline totals: IN PROGRESS = sum of `open`; NEED A PERSON = sum of `needs_person`; STOPPED = sum of `stopped`; VERIFIED THIS MONTH = sum of `verified_this_month`; all over `lines` in the `/work/counts` response, including lines that do not appear in `/overview`. When `limited` is true each shows "at least N" (phone and desktop). Coverage line under the eyebrow or under the totals: "Counted from the N most recent items you can see" (N = `evaluated`) when limited; "Counted from all N items you can see" when not. Month label for the fourth total uses `verified_month` ("<Mon YYYY>").
- Floor's headline number: sum of its lines' `total` from `/overview`, labelled "open work". It is exact (not sampled) and may differ from the sampled station figures; the footnote says so.

Fixtures (add to the mock and tests):
```json
// GET /overview
{ "as_of": "2026-11-23T09:30:00Z",
  "lines": [
    { "key": "commercial/v1", "title": "Costing and commercial submission", "total": 3 },
    { "key": "rfp-response/v1", "title": "RFP response and project handoff", "total": 1 },
    { "key": "pmo-finance/v1", "title": "Invoice preparation and delivery", "total": 4 },
    { "key": "pmo-minutes/v1", "title": "Formal minutes and action handoff", "total": 2 },
    { "key": "future-line/v1", "title": "A line added later", "total": 5 } ] }
// GET /work/counts (not limited)
{ "as_of": "2026-11-23T09:30:02Z", "evaluated": 15, "limited": false, "verified_month": "2026-11",
  "queues": [{ "key": "needs_me", "observed": 4, "total": 4 }],
  "lines": [
    { "key": "commercial/v1", "needs_person": 2, "held": 0, "open": 3, "stopped": 0, "verified": 1, "verified_this_month": 1,
      "stations": [ {"key":"intake","count":1,"needs_person":0}, {"key":"execution","count":1,"needs_person":0},
                    {"key":"decision","count":1,"needs_person":2}, {"key":"delivery","count":0,"needs_person":0}, {"key":"verified","count":1,"needs_person":0} ] },
    { "key": "pmo-finance/v1", "needs_person": 1, "held": 1, "open": 4, "stopped": 1, "verified": 0, "verified_this_month": 0, "stations": [ "... five stations" ] } ] }
```
Also a limited variant (`"limited": true, "evaluated": 50`, queue `total: null`) and a variant where `commercial/v1` is missing from `lines`.

### Line key to floor map (local, versioned: `FLOOR_MAP_VERSION = 1` in `src/features/overview/lines.ts`)
Unchanged from the previous spec: the backend does not group lines (A-35). Floors keep the design's name, subtitle and avatar from `LINE_IDENTITY`.

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
| Other lines (no avatar, subtitle "Not on a floor yet") | every other key, including `pmo-issues/v1`, `pmo-leadership-report/v1`, `pmo-minutes/v1`, `pmo-escalation/v1`, `pmo-weekly-report/v1`, `pmo-emergency/v1`, `pmo-change/v1`, `process-handoff/v1`, and any key not listed |

Rules: floors in the order above, "Other lines" last. A floor with no returned line is not drawn. Unmapped keys are never dropped. A test checks every key in the 26-key `/work/counts` `line` enum (`contracts/psl-factory.openapi.json`) lands on exactly one floor.

### Screen: `/overview`
Each floor row: avatar and name, subtitle, headline number with "open work", then its lines. Each line: `title`, its `total` with "open work", a station track (five squares in order Intake, Execution, Decision, Delivery, Verified; each shows its `count`; a square with `needs_person` > 0 is drawn in the board's "needs a person" colour and reads "needs a person" to assistive tech), and a link "Open work" to `/my-work?line=<key>` (URL-encoded key). Tag: neutral "Not available yet" where the board draws it (no read supplies it).

Header: eyebrow "FACTORY FLOOR · UPDATED <as_of> WAT" (use `When`; `as_of` from `/overview`). Desktop: the four totals as drawn (IN PROGRESS, NEED A PERSON, STOPPED, VERIFIED THIS MONTH); phone: the two-figure summary as drawn, from the same sums. Coverage line as above. Footnote: "Open work is work you can see that isn't verified or cancelled. Station figures come from your most recent items and can be lower than the total."

| State | What shows |
|---|---|
| Loading | `LoadingState` under the title |
| Empty (`/overview` `lines: []`) | `EmptyState` "No lines to show yet." with "Lines appear here when work you can see starts." View switch hidden; no totals |
| Error | `ErrorState` "We couldn't load the factory floor." with "Try again"; names last load time if any and the error `code` |
| 403 or 404 | `EmptyState` "The factory floor isn't open to you." with the server's message. No retry. Polling stopped |
| Signed out (401) | `SignedOutState` for `/overview` |
| Partial (counts failed) | floor rows with totals; "Totals are not available yet."; "Not available yet" in place of squares |
| Success, limited | as Success with "at least N" totals and the "most recent items" coverage line |
| Success | rows, totals and squares as above |

Kept as is: "All exceptions · everyone's" and its link to `/exceptions`; the Flat / 3D switch and its hints for reduced motion, no WebGL, phone.

### 3D floor
Keep `Floor3D`. A small adapter in `src/features/overview/` turns each floor into the scene's shape: one machine per returned line (name = line title), stations from the `/work/counts` line (name = station label, `count`, `needs_person` true when > 0). Where counts are unknown for the line, the machine has no stations and a neutral tag; no "PERSON" mark and no "no person needed" wording is shown for it. A pressed station or machine opens a strip with the count, the "needs a person" wording only when `needs_person` > 0, and an "Open work" link to `/my-work?line=<key>` instead of the v7 read (`useStationWork`). Flat view reachable; fall back to flat on failure, reduced motion, narrow window or no WebGL.

## Lanes
- Frontend lane owns: `frontend/src/features/overview/*`, `frontend/src/features/floor/*` (remove the v7 station-work read, accept the adapted shape), the mock handlers for `/api/v1/overview` and `/api/v1/work/counts`, and the overview tests listed below.
- Backend lane: none. Integration owner: checks both live reads against these shapes (`oa.py live GET /api/v1/overview`, `... /api/v1/work/counts`) and runs the live smoke.
- Shared files (read only, API layer): `src/api/live-schema.d.ts`, `src/api/client.ts`. `src/features/my-work/*` read only; if `/my-work?line=` does not yet read live `GET /work`, that is its own feature.

## Acceptance criteria
1. Page reads both live operations. verify: `grep -rn "liveApi.GET('/api/v1/overview')\|liveApi.GET('/api/v1/work/counts')" frontend/src/features/overview` finds both; no `api.GET('/api/v1/overview')` and no v7 overview type remain in `src/features/overview` or `src/features/floor`.
2. Success with the fixtures. verify: a test renders `/overview` and sees "UPDATED", the `as_of` time with "WAT", floor rows Pre-sale (4 open work), Invoices (4), Other lines (7), and the line "Costing and commercial submission" with 3 and "open work".
3. Headline totals. verify: with the not-limited fixture the four totals equal the sums of `open`, `needs_person`, `stopped`, `verified_this_month` over the counts lines, and the coverage line reads "Counted from all 15 items you can see". With `limited: true, evaluated: 50` each total reads "at least N" and the line reads "Counted from the 50 most recent items you can see". No total ever shows a bare number when limited.
4. Station squares. verify: the commercial line draws five squares with counts 1,1,1,0,1 and the Decision square marked "needs a person"; a line with all `needs_person` 0 has no marked square.
5. Unknown is not 0. verify: in the limited variant where `commercial/v1` is missing from counts, its row shows "Not available yet" and no squares with 0; in the not-limited variant the same absence shows five 0 squares. When `/work/counts` returns 503, the page shows rows, totals line "Totals are not available yet.", and no "0" in any total.
6. Unmapped key is kept. verify: "A line added later" with 5 under "Other lines"; a map test puts all 26 enum keys on exactly one floor; a floor with no lines is not rendered.
7. Tag. verify: no row shows "Stopped", "Waiting" or "Verified" as a tag; "Not available yet" shows in the tag place.
8. Drill-down. verify: clicking "Open work" on the commercial line gives href `/my-work?line=commercial%2Fv1`; in the running app it lists work for that line only.
9. Empty. verify: `/overview` with `lines: []` shows "No lines to show yet.", no Flat/3D switch, no totals.
10. Error with retry. verify: a 500 on `/overview` shows "We couldn't load the factory floor." and "Try again"; pressing it with a later 200 shows rows. A network failure shows the same state.
11. 403 and 404. verify: a 403 shows "The factory floor isn't open to you." with the server's message, no "Try again", no further `/overview` request after 20 s of fake time; a 404 shows the same. A user whose scope is empty (server returns `lines: []`) sees the empty state; wrong tenant is covered by the server answering 404 or empty.
12. Signed out. verify: a 401 on either read shows the signed-out state with a sign-in link for `/overview`.
13. Loading. verify: before the responses resolve the page shows `LoadingState` and no rows.
14. Polling. verify: with fake timers both reads go out again after 15 s while visible; an older response arriving late is dropped; a 403 stops polling.
15. 3D floor. verify: with WebGL stubbed the 3D view shows one machine per line with its stations; a PERSON mark appears only on stations with `needs_person` > 0; the pressed station's strip shows the count and an "Open work" link; a machine without counts has no PERSON mark; with reduced motion the flat view shows and the hint appears.
16. Phone. verify: at 390 px the page shows the title, the two-figure summary, rows, the "Updated" line and no 3D switch; at 1440 px the eyebrow shows above the title with the four totals.
17. Live smoke. verify: against the local live backend (account `live-lead`), line titles and totals match `curl -b <session> /api/v1/overview`, and totals and squares match `/api/v1/work/counts`; an account with no work shows the empty state.
18. Mocks match the live shapes. verify: mock handlers return exactly the two shapes above; `tests/api-live-schema-drift.test.ts` passes; the v7-only tests (`tests/mock-overview.test.ts`, `tests/overview*.test.tsx`, `tests/floor*.test.ts*`) are rewritten to the live shapes, not deleted without replacement.

## Out of scope
- Any backend change, new endpoint or write; moving the floor map to the backend, renaming floors, new avatars.
- Computing totals, tags or station counts from `total` or from `/work` rows. Computing a status tag from `stopped` or `needs_person` (see Q8).
- A client-side role rule for `/overview` beyond the existing nav check on `/me`.
- SCR-10 exceptions, SCR-14 verified outputs, connecting `/my-work` itself to live `GET /work`, a new queue screen, `GET /projects/{id}/delivery-overview`, queue `observed` figures, and the `project`, `q`, `verified_month` options of `/work/counts` (no month picker).

## Assumptions
- A-33 now answered: `total` is open (not verified, not cancelled); wording "open work".
- Headline totals come from `/work/counts` line sums, not `queues`, because the board's four figures map to line fields (`open`, `needs_person`, `stopped`, `verified_this_month`) and queue totals are null when limited.
- A floor with no returned line is not drawn; absence is never shown as 0 (except the not-limited counts case in "Joining the two reads", where it is known).
- Station labels are the backend keys capitalised (Intake, Execution, Decision, Delivery, Verified); the board's names are not in the API.
- `needs_person` per station means "at least one item needs a person" for the mark; the number is shown only in the strip.
- PMO lines and `process-handoff/v1` have no floor in the design, so they sit under "Other lines".
- 404 is treated like 403, as the hook does.
- The neutral "Not available yet" tag keeps the tag position without implying a status.
- Link target is `/my-work?line=<key>` (SCR-01 queue, `model.ts` parses it).

## Questions for the design engineer
Q1 to Q6 from D-182 keep your earlier answers; where 1.24.0 supplies the data, those answers apply to the failure case only (counts unavailable): Q1 totals, Q2 squares, Q5 3D stations, Q6 strip. Q3 (tag) and Q4 (floors, "Other lines") stand as answered. New, presentation only:
7. Totals and squares are sampled from the 50 most recent items. (a) Recommended: show "at least N" and a coverage line "Counted from the 50 most recent items you can see" when limited. (b) Show the number plain with a small "(sample)" mark. (c) Hide the four totals when limited.
8. The row tag is still not supplied, but `stopped` and `needs_person` are now known per line. (a) Recommended: keep the neutral "Not available yet" tag until the backend gives a status. (b) Derive the tag in the page: "Stopped" if `stopped` > 0, "Waiting" if `needs_person` > 0, else none. (c) Hide the tag column.
9. The floor number (exact, open work) and the station squares (sampled) can disagree. (a) Recommended: show both with the footnote saying station figures come from recent items. (b) Show the floor number only when station figures are not limited. (c) Show the sum of station counts as the floor number, with the same "at least" rule.

## Conflicts with the boards
- Partial and limited states are not drawn: "Totals are not available yet.", "at least N", the coverage line and "Not available yet" in place of squares (Q1, Q2, Q7).
- Row tag: neutral "Not available yet" instead of the coloured Stopped/Waiting/Verified tag (Q3, Q8).
- Floors: only floors with returned lines; a ninth "Other lines" floor no board draws (Q4).
- The 3D floor draws machines per line, with stations only where counts exist (Q5).
- The station strip links to the queue instead of listing the station's work inline (Q6, D-165).
- Station track shows five fixed stations (Intake to Verified); the board's eight station names per floor are not in the API.
- New text no board draws: "open work", "Open work" link, footnote, coverage line, "Not available yet".
