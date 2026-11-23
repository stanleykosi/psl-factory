# The work item shows its station track, six facts, agent activity, reference, who started it and paged history

> Tasks: FE-CONNECT-1. Architecture: v9 package (revision as pinned in the feature record at branch time); contract `contracts/psl-factory.openapi.json` 1.24.0. Design: approved 13 Nov canvas under the recorded exception in `design/review.json`; screens: SCR-02 (work item, overview and history artboards).

## Summary
- Reverses the F-85 hiding (D-185): `/work/[id]` reads `item.tracking_url` and draws the station track with who holds each station, the six facts, the reference, "started by" and the intake date.
- Facts are `true`, `false` or `null`; `null` is drawn as Unknown, never as "No", "Not yet" or 0. A station nobody holds is shown as unassigned or not recorded, never given an invented owner.
- Agent activity is only what the API supplies: `current_activity.label` and `progress`. No steps are built.
- `/work/[id]/history` shows an actor-kind tag on every row (person or agent), keeps the Decisions, Agent work and Evidence filters, and pages older events with the `next_before` cursor ("Older events").
- Read only. No write, no new endpoint, no counts, no amount.

## Context
Lane C worktree `/Users/Hunchoo/psl-factory-worktrees/lane-c/frontend`. F-91 builds after F-85 merges (and rebases on F-87 if that has merged).
- Live page (F-85): `src/features/work-item/live/LiveWorkItemView.tsx` (`Header`, `Overview`, `History`, `PanelView`), `live/useLiveWorkItem.ts` (polling via `needsPolling`), `live/useLiveHistory.ts`, `live/model.ts` (`historyLine`, `historyCaption`, `HISTORY_FILTERS`, `words`, `activityOf`), `work-item.css`. F-87 adds a controls row and the `LineAdapter.Actions` slot in the same file; do not move or restyle them.
- Existing components to reuse, none to duplicate: `StationTrack` in `src/components/StationTrack.tsx` (CMP-02; types `Station`, `StationStatus`), `FactsStrip` and `FactValue` in `src/components/FactsStrip.tsx` (CMP-04), `FACTS` and `STATIONS` and `ACTOR_TAGS` in `src/features/work-item/labels.ts`, the v7 wrapper `StationTrack`/`FactsStrip` in `WorkItemOverview.tsx` (work-track and work-facts classes, the "Paid is a separate Finance fact" note), `Segmented`, `Tag`, `Callout`, `Button`, `formatDayTime`, the `work-hcard` history rows.
- 1.24.0 reads used (viewer: `python3 /Users/Hunchoo/psl-factory-main/delivery/connect/oa.py live GET <path> 3`):
  - `GET /api/v1/work/{work_id}` now also carries `reference` (string or null), `started_at`, `verified_at` (date-time or null), `station {key, index, count, name}` or null, `agent` (string or null), `action_kind` and `tracking_url` (string or null; the path `/api/v1/work/{work_id}/tracking`).
  - `GET {tracking_url}` (typed `/api/v1/work/{work_id}/tracking`), required fields: `work_id`, `as_of`, `next_step`, `blocker`, `owner|null`, `station` and `stations[]` `{key: intake|execution|decision|delivery|verified, name, position, status: recorded|current|pending|unknown, owner|null}`, `started_at`, `started_by`, `verified_at|null`, `facts {drafted, reviewed, approved, sent, receipt, verified}` each boolean or null, `worker_history_url`, `decision_history_url`, `evidence_history_url`, `can_record_delivery_observation`, `delivery_observation_url|null`, `uncertain_effects[]`, `last_activity|null`. Delivery-observation fields belong to F-87 and are not used here.
  - `GET /api/v1/work/{work_id}/history?kind=worker|decision|evidence&before=<int>` returns `{items[<=30] {at, station, status, actor_kind: person|worker, entry_id, task_id?, actor?, reason?, evidence_id?|null}, as_of, next_before: int|null}`.
- The F-85 mock `mock/work-live.mjs` serves the 1.22.0 shape; F-91 extends it.

## Contract

### Tracking read (live)
- After `GET /work/{id}` succeeds and `item.tracking_url` is not null, read it once through `call(liveApi.GET(...))` with the typed path (do not follow the URL string blindly: use the typed `/api/v1/work/{work_id}/tracking` call with `item.id`). Hook `useLiveTracking(item)` in `live/useLiveTracking.ts` unless F-85 already exports one; reuse that.
- Re-read tracking on every item re-read: on each poll of `useLiveWorkItem` (same cadence and same visibility rule) and on Try again. Polling rules are F-85's (`needsPolling`: `current_activity.watching` or `state === 'processing'`); no new rule is added, because the progress status vocabulary has no enum in the contract (A-17).
- `tracking_url === null`: no track, no facts strip, no started line, no heading, no gap (nothing is invented from the item fields).
- Tracking read fails: the rest of the page stays; in place of the track and facts one `Callout` "We couldn’t load where this work is held." with Try again (404/403 on tracking use the same sentence; 401 uses the signed-out state; 429/503 add "Try again shortly."). A failed poll keeps the last good tracking.

### Page parts and their source (presentation only; nothing here decides access)
| Part | Source | Rule |
|---|---|---|
| Reference | `item.reference` | Shown next to the id in the breadcrumb current item ("INV-0412"); null keeps "Work {id}". Never invented. |
| Started line | `tracking.started_by`, `tracking.started_at` | "Started by {name} · {formatDayTime(started_at)}" in `work-sub`, after "With {owner}". |
| "With" | `item.owner` | unchanged from F-85 (null shows nothing). |
| Station track | `tracking.stations[]` in `position` order, through the existing `StationTrack` component | See station mapping below. |
| Six facts | `tracking.facts` through the existing `FactsStrip` (`facts` prop of `FactValue`), in the order drafted, reviewed, approved, sent, receipt (`receipt_recorded`), verified | `true` is `earned`; `false` is `not_yet`; `null` is `unknown`. `at` is passed only for `verified`, from `tracking.verified_at` when not null; the other facts carry no time and show "Earned" alone. The paid note stays out (amount and Finance facts are out of scope). |
| Agent activity | `item.current_activity.label`; else `item.progress.status` with "Updated {time}" | F-85's `activityOf`, unchanged, now drawn in the agent area of the board. No steps, no numbered list, no source line. |
| Output | `item.output_url` | unchanged from F-85. |

Station mapping (`StationStatus` of the shared component; a pure function `stationsOf(tracking, item)` in `live/model.ts`, unit tested):
- `recorded` -> `done`; the `verified` key with `recorded` -> `verified`.
- `current` -> `waiting` by default; `person` when `key` is `intake` or `decision`; `agent` when `key` is `execution` and `item.current_activity?.watching === true`; `stopped` when `item.state` is one of `action_needed`, `owner_needed`, `setup_needed`, `effect_uncertain`, `awaiting_reconciliation`, `followup_needed`, `cancelled`.
- `pending` -> `todo`.
- `unknown` -> `todo` with the text "Unknown" (never "Not started", never "Done").
- Station `text` (the one-line status) is the holder: `owner` when not null; otherwise "Unassigned" for `pending` and `current`, "Not recorded" for `recorded` and `unknown`. The `name` is the API's `name`. Nothing else is written into a station.
- Stations are drawn in `position` order; a response with an empty `stations[]` draws no track.

### Agent activity states
- Working (`current_activity.watching` true): label as the activity line, the track's execution station shows `agent`.
- Idle with `progress`: `progress.status` with its time.
- Neither: no agent area, no heading.
- The agent name `item.agent` and `tracking.last_activity` are not drawn (see LC-Q24).

### History read (live)
- `GET /api/v1/work/{id}/history` with `kind` one of `worker`, `decision`, `evidence` (no `kind` for all) and `before` (the `next_before` of the previous page). Tabs: All, Decisions (`decision`), Agent work (`worker`), Evidence (`evidence`). No counts.
- Row: time (`at`), the actor tag from `actor_kind` (`person` -> PERSON, `worker` -> AGENT, using `ACTOR_TAGS`; no FACTORY value because the contract has none), `actor` when present, then `station` and `status` as words (`historyLine` in `live/model.ts`, extended with `actorKind` and `entryId`), `reason` when present, an evidence link only when `evidence_id` is not null. The row sentence is composed only from those fields. Unknown stations and statuses are shown as raw text; an absent `actor` shows the tag alone. No version column and no "Restricted" marks (no source).
- Paging: when `next_before` is not null the page ends with an "Older events" button; pressing it calls the same filter with `before=next_before`, appends the 30 rows, replaces the cursor and keeps the scroll position and the focus on the first new row. Rows are keyed by `entry_id`; a row whose `entry_id` is already shown is not drawn twice. When `next_before` is null the button is gone. Changing the filter clears the rows and the cursor and reads page one. An answer to an earlier filter or page is dropped.
- Caption: "Showing the latest {n} changes. As of {as_of}." while `next_before` is not null (n = rows loaded); "Showing all changes. As of {as_of}." once it is null; `as_of` is that of the first page of the current filter.
- States: loading (first page), empty ("No changes recorded yet."), error on first page (mapped message with Try again, filter kept), error on older events (the rows stay, a `Callout` beside the button with the mapped message and the button reads "Try again"; no automatic retry), success.
- Replaces F-85's `historyCaption`/`HISTORY_LIMIT` rule ("exactly 30 rows"); update `live/model.ts` and its tests.

### Idempotency and versioning
All reads. No writes, no idempotency keys, no revision tokens used. A null token in the loaded item stays null.

### Permission and tenant rules
Every read is made as the signed-in person; a tracking or history answer of 404 is "This record is unavailable." on the page (same words as F-85) and stops polling. Tracking may serve a station owner's name to a person who may see the work; the UI shows what is sent and never looks up a person.

### Fixture examples (mock, numeric ids; builder-owned numbers, shapes are the contract)
- `4102` processing: `tracking_url` set; stations intake `recorded` (owner "Tunde Bello"), execution `current` (owner "Tola"), decision `pending` (owner null), delivery `pending`, verified `pending`; `facts {drafted:null, reviewed:false, approved:false, sent:false, receipt:false, verified:false}`; `started_by:"Tunde Bello"`.
- `4101` verified: all stations `recorded`; facts all `true`; `verified_at` set; history 31 rows with `next_before: 9001` on page one and `null` on page two.
- `4103` decision waiting: decision `current`, owner "Ada Okafor"; `facts.reviewed:null`.
- `4104` stuck: `state:"setup_needed"`, execution `current` -> `stopped`; one station `unknown`; `reference:null`.
- `4105`: `tracking_url:null` (no track, no facts). `4107`: tracking answers 503 (callout; rest of page loads). `4106`: 404 for any caller.
- History rows include `actor_kind:"worker"` with no `actor`, an unknown station "recheck_queue", and a row with `evidence_id:null`.

## Lanes
- Frontend lane (owner, all of this feature): `frontend/src/features/work-item/live/**` (including `useLiveTracking.ts`, `model.ts`, `useLiveHistory.ts`, `LiveWorkItemView.tsx`), `frontend/src/features/work-item/work-item.css` (additions only), `frontend/src/api/types.ts` (live tracking and history types if not already generated from `live-schema.d.ts`), `frontend/mock/work-live.mjs` and `frontend/mock/**` fixtures, tests under `frontend/src/**`, `frontend/tests/live-work-item.test.tsx`, `frontend/e2e/work-item*.spec.ts`.
- Backend lane: none. No backend change.
- Integration owner: lane C coordinator. Shared files: `LiveWorkItemView.tsx` is also edited by F-87 (controls row, `Actions` slot); keep F-91 edits to the `Header`, a new `Tracking` block at the top of `Overview`, and `History`, and rebase on F-87 before the PR. `src/components/*` (`StationTrack`, `FactsStrip`) are used as they are; if a variant is needed ask first (see LC-Q25).
- Protected paths in `delivery/config.json` stay unchanged.

## Acceptance criteria
1. `/work/4102` (mock: Next 4980, mock 4981) shows the station track with five stations in order, the holder under each ("Tunde Bello", "Tola", "Unassigned"), and the execution station marked as the current one — verify: open the page; `frontend/e2e/work-item-tracking.spec.ts` asserts the list items and `aria-current="step"`.
2. A future station whose `owner` is null reads "Unassigned" and no name; a `recorded` station with null owner reads "Not recorded"; an `unknown` station reads "Unknown" and is not drawn as done — verify: unit test `stationsOf`.
3. The six facts strip shows `true` as earned, `false` as "Not yet", and `null` as "Unknown"; on `/work/4102` the Drafted box reads Unknown and no box reads "No" or 0 — verify: e2e on 4102 and 4103; unit test mapping `{drafted:null}`.
4. Only the Verified box shows a time, taken from `verified_at`; the other earned facts show no time — verify: e2e on `/work/4101`.
5. Reference shows beside the id when `reference` is a string; `/work/4104` (`reference:null`) shows "Work 4104" only — verify: e2e on both.
6. "Started by {name} · {date}" shows from tracking; with `tracking_url:null` (`/work/4105`) no started line, no track, no facts strip, no empty heading or gap, and the rest of the page loads — verify: e2e on 4105.
7. When tracking answers 503 (`/work/4107`) the page shows the title, tag and next step plus "We couldn’t load where this work is held." with Try again; Try again re-reads tracking only — verify: e2e; network panel shows one extra `GET .../tracking`.
8. Tracking is re-read on each item poll while `current_activity.watching` is true, and is read once otherwise; a failed poll keeps the last good track — verify: unit test `useLiveTracking` with fake timers.
9. A 404 or 403 on a tracking poll shows the F-85 unavailable or no-access state and stops polling; a 401 shows the signed-out state — verify: unit test with a mocked client.
10. The agent area shows `current_activity.label` or `progress.status` with its time, and nothing else: no numbered steps, no "Read:" lines, no agent name; with neither it draws no heading — verify: e2e on 4102 and 4101; grep that no step list is built.
11. History rows (`/work/4101/history`) show the PERSON or AGENT tag from `actor_kind`, the actor when present, station and status words, reason, and an evidence link only when `evidence_id` is not null; a `worker` row with no `actor` shows the AGENT tag alone — verify: unit test on `historyLine`; e2e.
12. An unknown station ("recheck_queue") shows as raw text with underscores read as spaces and is not dropped — verify: unit test.
13. The tabs call history with `kind=decision`, `worker`, `evidence`; All sends no `kind`; no counts and no version column are drawn — verify: unit test and network panel.
14. With `next_before` set, "Older events" is shown; pressing it requests `before=<next_before>` with the same `kind`, appends rows (31 to 60 total on 4101), no row is drawn twice (same `entry_id`), and the button is gone when `next_before` is null — verify: e2e on 4101 and unit test on the merge.
15. Changing the filter after paging resets to the first page, and a slow answer for the earlier filter or page never replaces the rows — verify: unit test with delayed mock responses.
16. A failed "Older events" keeps the rows already shown, shows the mapped message with Try again, and makes no automatic second request — verify: unit test counts calls.
17. Caption reads "Showing the latest N changes. As of …" while more pages exist and "Showing all changes. As of …" when `next_before` is null; empty history reads "No changes recorded yet." — verify: unit and e2e.
18. A history 404 shows "This record is unavailable."; a 401 shows the signed-out state with `?next=` the history path; a 403 `csrf_failed` is not shown as no access — verify: unit tests.
19. Nothing on the page sends a write because of this feature; no new `liveApi.POST` appears in files this feature adds or changes — verify: `git diff` grep of `POST` in the diff; e2e asserts no request other than GET.
20. Against live Django (8020, account live-lead) for a real work id, the station names, owners, six facts, `started_by` and first history page equal `GET /api/v1/work/{id}/tracking` and `/history` — verify: compare the page with `oa.py live GET` output; a fact that is null in the JSON reads Unknown on the page.
21. Viewport check at 1440 and 390: track, facts strip, history rows and "Older events" match the SCR-02 artboards for the parts drawn, with no overlap, track scrolling sideways on the phone, and no empty gap or heading where a part is absent — verify: screenshots at both widths reviewed against `design/screens.md` SCR-02 artboards.
22. `live-schema.d.ts` matches contract 1.24.0 (`api-live-schema-drift.test.ts` passes) and the page imports no v7 `WorkItem`, `stations` or `facts` types — verify: `delivery/checks.sh`; `grep -rn "api/schema'" frontend/src/features/work-item/live` is empty.

## Out of scope
- Amount, currency and the invoice block (A-14; line features, LC-Q21 in F-90); the "Paid" note.
- The delivery observation write and `can_record_delivery_observation`, `delivery_observation_url`, `uncertain_effects[]` (F-87).
- Per-filter history counts, a version column, "Restricted" rows, a sentence field, a limit control (no source).
- Agent steps, the agent mascot card with numbered steps, `item.agent` name, `tracking.last_activity`, and any step derived from history or panels.
- `action_kind` tags, `exception_*` fields, `proofs_url`, `queue_output_url`, and the My work list (lane A).
- Following `worker_history_url`, `decision_history_url`, `evidence_history_url` strings; the typed history path is used.
- Any write, any backend, migration or contract change, any other D-185 item.
- Checklist facts of specialist lines (they stay in their own panels).

## Assumptions
- Current-station kind uses the station `key` and the item `state` because the API gives the holder's name but not whether it is a person or an agent. Reason: the track needs a status class and the contract has none; the rule only chooses a colour and never states a holder.
- `true` fact is drawn "earned", `false` "not yet". Reason: the strip has no "No" and v7 used the same words; the API does not say a `false` fact failed.
- Only Verified carries a time. Reason: the tracking read has no times for the other facts.
- "Older events" appends below; rows are keyed and de-duplicated by `entry_id`. Reason: the cursor is by entry id, so a repeat is possible if a new event arrives between pages.
- No new polling rule for `progress`. Reason: its status is free text; A-17 says to also use state and next action, which `needsPolling` already covers through `state`.
- The `worker` actor kind uses the AGENT tag word and no FACTORY tag. Reason: the contract has two kinds only.
- Tracking is a separate read after the item read, so a tracking failure never hides the item. Reason: the read is its own endpoint.
- The mock fixture numbers are free (4101 to 4107). Reason: no live fixtures exist.

## Conflicts with the boards
The design engineer decides once before the build; entered in `delivery/connect/questions-batch.md` as LC-Q23 to LC-Q26.
1. History: the boards draw per-filter counts, a version column and "Restricted" entries; the API has none of the three. Recommendation: leave them out (LC-Q23).
2. Agent card: the boards draw the agent mascot, its name and numbered steps with the record each read; the API gives one activity line. Recommendation: one line, no steps, no name (LC-Q24).
3. Station track: the boards write a detail in each station ("Chidi drafted v2", "Needs your decision"); the API gives the owner's name only, and whether the holder is a person or an agent is a colour choice by station key. Recommendation: owner name as the detail, colour by the mapping above (LC-Q25).
4. Header: the boards draw the amount and a byline with the invoice version; those stay out. Reference, "started by" and date are added in the sub-line. Recommendation: leave the amount to the line's own panel (LC-Q26).
5. Facts strip: the boards write the dates inside earned boxes ("10 Nov"); only Verified has a time. Recommendation: Verified shows its time, the rest say "Earned" (covered by LC-Q25).
6. History "Older events": no board draws paging beyond "show more"; the button uses the existing show-more pattern. No question needed.

## Coordinator note (lane C, 23 Nov)
LC-Q24: build the agent card with the served `item.agent` name and picture, the activity line or progress, and `tracking.last_activity`; leave out only the numbered steps. D-185 says served data is built as the board draws it. The batch answer overrides this note.
