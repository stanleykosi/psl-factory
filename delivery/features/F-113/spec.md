# The Delivery tab shows the project's six delivery lines from the live overview

> Tasks: FE-CONNECT-1. Architecture: v9 package, API 1.24.0 (`contracts/psl-factory.openapi.json`, D-10, D-11, D-185). Design: 13 Nov approved canvas (D-173/D-181 exceptions in `design/review.json`); screens: SCR-43 (artboards SCR-43-desktop, SCR-43-mobile).

## Summary
- `/projects/{caseId}/delivery` reads `GET /projects/{case_id}/delivery-overview` and draws the six lines in the fixed order. Each line shows its title, reference, state, last-updated date and a link to its work item.
- A line with no work shows "Not started" with empty reference, date and link. Nothing is counted or derived: no "3 of 6 done", no DLV number, no gate wording, no Tola check or "Next" sentence (DC-3, D-182).
- When closure is not started, the closure row says why using `closure-checklist` (`ready_to_prepare`, `checks[]`).
- Read only. No write, no start-from-overview.
- **This feature does not use the F-85 adapter or anything in `src/features/workspace`.** It is a plain project tab with its own read, so it can be built before F-85 merges. Its only dependency is API 1.24.0 on main.

## Context
- Route `/projects/[caseId]/(tabs)/[tab]` (`src/app/projects/[caseId]/(tabs)/[tab]/page.tsx`) already accepts `delivery` and renders `ProjectTabBody` in `src/features/projects/ProjectJourney.tsx`, which renders `<DeliveryTab />`.
- `src/features/projects/DeliveryTab.tsx` today is a placeholder panel "Delivery is not available yet". The old mock reads (`delivery[]`, `delivery_summary`, `delivery_agent`, `deliveryRowsOf`) are already gone from `model.ts` at API 1.24.0; do not reintroduce them. `mock/proposals/delivery-release.json` still holds their overlay; leave it.
- `model.ts` marks `delivery` in `PROJECT_TABS` but excludes it from `BAR_TABS` because live `tabs[]` has no delivery key (see Questions 1).
- Hooks pattern to copy: `src/features/projects/useProject.ts` (sequence guard, `call(liveApi.GET(...))`, `isJourney`-style response check). States: `ProjectStates.tsx` (`ProjectNoAccess`). Shared components: `Panel`, `Tag`, `EmptyState`, `Breadcrumb` from `@/components`.
- Types come from `src/api/live-schema.d.ts` (`operations['delivery_overview']`, already generated).

## Contract
### GET /api/v1/projects/{case_id}/delivery-overview (operationId `delivery_overview`)
- Request: `case_id` uuid path param. No query, no body.
- Permission: same project access as the journey. 403 and 404 look the same to the user: reuse `ProjectNoAccess`.
- 200: `{ as_of: date-time, lines: [ { key, title, work_id|null, state|null, reference|null, updated_at|null, work_url|null, gate_state, gate_url|null } ] }`. All keys required, no extras.
  - `key` is one of `delivery-release/v1`, `delivery-go-live/v1`, `delivery-hypercare/v1`, `delivery-handover/v1`, `delivery-archive/v1`, `delivery-closure/v1`.
  - `state` is one of ready, waiting, action_needed, owner_needed, setup_needed, verified, cancelled, awaiting_reconciliation, followup_needed, processing, effect_uncertain, or null.
  - `gate_state` is the same list plus `not_started`. `gate_url` is the API link to that line's gate panel (read by F-113B, not here).
- Errors: 401 handled by the existing session client; 403/404 no access; 422, 5xx and network show the error state. Error body `{code, message, fields?}`; show the generic message, never `message` text from the server.
- Idempotency/versioning: a read, no revision.

### Fixed row order and plain words
Draw exactly six rows in the order below, matched by `key`, whatever order the API returns. Numbers 01 to 06 are the position.

| # | key | row title (from `title`) | opens |
|---|---|---|---|
| 01 | delivery-release/v1 | Release gates | `/work/{work_id}` |
| 02 | delivery-go-live/v1 | Go-live acceptance | same |
| 03 | delivery-hypercare/v1 | Hypercare | same |
| 04 | delivery-handover/v1 | Handover to Support | same |
| 05 | delivery-archive/v1 | Archive | same |
| 06 | delivery-closure/v1 | Closure | same |

The board draws Archive as 04 and Handover as 05; readiness Scope fixes handover before archive, so this spec follows readiness (see Questions 2).

State tag text (shown in capitals on the tag, from `state`, falling back to `gate_state` only when `state` is null and `gate_state` is not `not_started`):

| value | tag text | tone |
|---|---|---|
| not_started or state null | NOT STARTED | neutral |
| ready | READY | neutral |
| processing | IN PROGRESS | neutral |
| waiting | WAITING | neutral |
| action_needed | ACTION NEEDED | caution |
| owner_needed | NEEDS AN OWNER | caution |
| setup_needed | SET-UP NEEDED | caution |
| followup_needed | FOLLOW-UP NEEDED | caution |
| awaiting_reconciliation | CHECKING WHAT HAPPENED | caution |
| effect_uncertain | RESULT UNCERTAIN | stopped |
| verified | VERIFIED | done |
| cancelled | CANCELLED | neutral |

A value outside this list shows "UNKNOWN" (neutral), never a guess.

### Row fields
- Reference: `reference`, or empty (a dash is not drawn; leave the slot empty) when null.
- Date: `updated_at` as "Updated 25 Mar" (day and short month, local format used by the other projects tabs). Null leaves it empty, never "today" or 0.
- Link: when `work_id` and `work_url` are set the row is a link "Open" to `/work/{work_id}`. Build the href from `work_id`, not from `work_url`. Null `work_id` means no link.
- `as_of` is shown once under the list as "Checked <date time>".
- Nothing else is shown per row: no gate label ("RELEASE READY · 25 MAR"), no `detail` sentence except the closure reason below.

### Closure hold reasons (row 06 only)
Shown only when the closure row has `work_id` null (not started). Source: `GET /projects/{case_id}/delivery/{dossier_id}/closure-checklist` (operationId `closure_checklist`; response `ready_to_prepare`, `checks[] {key, title, status, summary, finding}`).
- `dossier_id` is not in the overview. Take it from `GET /work/{release_work_id}/release-register` `dossier_id` for the release row's `work_id`. If the release row has no `work_id`, or either read fails or returns 403, show no reason (no error banner for this read; the overview itself still shows).
- If `ready_to_prepare` is true: no reason line; the row stays "NOT STARTED".
- If false: list the `title` of each check whose `status` is `held`, `unknown` or `unavailable`, with its `finding` when not null, under the row as "Closure waits on: ...". Use the API text as sent; do not rewrite it, and do not invent an order. Other statuses (`current`, `closed`, `recorded`) are not listed.
- Two reads (release-register, then checklist) happen only for this case, after the overview has drawn.

### Screen states
- **Loading:** the six row skeletons in order, tab panel `aria-busy`.
- **Empty:** not a separate state; every project returns six lines. If `lines` is empty or has unknown/duplicate keys the response is treated as invalid and shows the error state.
- **Error:** Panel "Delivery can't be shown right now" with "Try again" that re-reads once; no polling, no auto retry. No access: `ProjectNoAccess`.
- **Success:** the six rows, `as_of` line. Mobile (SCR-43-mobile): same rows stacked, reference and date under the title, "Open" below.

### Fixture examples (for mock 4991 and tests)
Add a mock answer for `delivery_overview` (project fixture `P-0101`): lines 1 to 4 `verified/ready` with references `REL-0091`, `GLV-0104`, `HYP-0062`, `ARC-0130` and `updated_at` set; handover `action_needed` `HND-0048`; closure `{work_id:null,state:null,reference:null,updated_at:null,work_url:null,gate_state:"not_started",gate_url:null}`. A second project with all six `not_started`. A third (`P-0099`) answers 403.

## Lanes
- **Frontend lane (owns all):** `src/features/projects/DeliveryTab.tsx`, new `src/features/projects/deliveryModel.ts` (key order, state words, response check, row building), new `src/features/projects/useDeliveryOverview.ts`, `src/features/projects/projects.css` additions (or a new `delivery.css` imported by `DeliveryTab.tsx`), mock handler and fixtures under `mock/` for this one operation, and tests under `tests/`.
- **Backend lane:** none. API 1.24.0 already serves the endpoint. A backend gap goes back as a question, not a frontend workaround.
- **Integration owner:** only the acceptance run against Django 8030.
- **Shared files:** `src/features/projects/model.ts` and `ProjectJourney.tsx` are shared with other project-tab features; change only what a Question's answer requires (tab bar entry), as a one-line edit. `src/features/workspace` is lane C's and must not change. No frame change is needed.

## Acceptance criteria
1. `GET /projects/{uuid}/delivery-overview` is requested exactly once when `/projects/{uuid}/delivery` opens — verify: network log on Next 4990 (proxied to Django 8030) shows one request, 200.
2. Six rows appear in the order release, go-live, hypercare, handover, archive, closure, even when the fixture returns them shuffled — verify: unit test on `deliveryModel.ts` with shuffled lines; page shows 01 to 06 in order.
3. A started row shows title, reference, state tag and "Updated <date>", and "Open" goes to `/work/{work_id}` — verify: mock 4991 project P-0101, click Open on Release gates, URL is `/work/<id>`.
4. A not-started row shows NOT STARTED with no reference, no date and no link, and no "0" or "Unknown" placeholder text in those slots — verify: second fixture project (all six `not_started`); page text contains no link in any row.
5. Every `state` value in the contract maps to the table's tag text; an unlisted value shows UNKNOWN — verify: unit test over all 11 states plus null plus a made-up value.
6. The page does not show "of 6 done", a DLV file number, gate wording such as "RELEASE READY", or a Tola check or "Next" sentence — verify: page text search on the P-0101 fixture finds none.
7. With closure not started and `ready_to_prepare: false`, the closure row lists the title (and `finding`) of each held, unknown or unavailable check and nothing from current/closed/recorded checks — verify: component test with a checklist fixture.
8. With `ready_to_prepare: true`, or when release-register or closure-checklist fails (403, 500, network), no closure reason shows and the six overview rows still show — verify: component test for each.
9. The closure checklist is not requested when the release row has no `work_id` or when closure has a `work_id` — verify: test asserts no checklist call.
10. 403 and 404 on the overview show the same no-access panel with no project name or server message — verify: open `/projects/<P-0099 id>/delivery` on mock 4991.
11. A 500 or network failure shows the error panel; "Try again" re-reads once and recovers — verify: component test with a failing then succeeding mock.
12. A response with the wrong shape (missing key, five lines, duplicated key, unknown key) shows the error state, not a partial list — verify: unit test on the response check.
13. The page makes no POST/PUT/PATCH/DELETE and contains no start, edit or assign control — verify: grep `DeliveryTab.tsx`, `useDeliveryOverview.ts` for non-GET calls; none.
14. Mobile width (390px) shows the six rows stacked without horizontal scroll — verify: browser at 390px on Next 4990.
15. `src/features/workspace/**` and every path in `delivery/config.json` `protected_paths` have no changes — verify: `git diff --stat origin/main` lists neither.
16. New tests exist for the model, the hook (race: a late answer for an earlier project is ignored) and the tab states, and `src/api/live-schema.d.ts` is unchanged — verify: `git diff --stat`, test files present.

## Out of scope
- SCR-44 release gates, planning-exit, release-register page, client-testing (F-113B). The "Open" link only goes to `/work/{id}`; the gate checks behind `gate_url` are not drawn here.
- Any write, including starting a delivery line (`POST /work`) from the overview.
- Counting done lines, "3 of 6 done", a DLV file reference, gate wording and tone, Tola's check and "Next" sentence (D-182; no source).
- The line sub-navigation on the board (Overview, Release, Go-live ...) as working links; those pages belong to F-113B to F-119.
- Changes to the shared workspace frame, F-85, or adding a `delivery` key to the API's `tabs[]`.
- Inventing states, approvers, dates or counts; unknown stays empty or "Unknown", never 0.

## Assumptions
- Row order is release, go-live, hypercare, handover, archive, closure, as in readiness Scope (the API `lines[]` order is not relied on).
- Date shown is `updated_at` only; the API has no other date, so "SIGNED 02 APR" style dates are not drawn.
- State words and tones in the table are my plain-language mapping; the API gives only keys. Tone for `effect_uncertain` uses the existing stopped/red tone.
- `dossier_id` for closure reasons comes from the release line's `release-register`, the only GET that returns it for this project; no better source exists in 1.24.0.
- A failed closure reason read is silent, because the reason is secondary and the main list is still true.
- "Try again" is one manual re-read; the project reads in this app do not poll.
- The unlinked row for a null `work_id` has no disabled "Open" button, to avoid an unexplained dead control.

## Questions
1. Tab bar entry. Live `tabs[]` has no delivery key, so `model.ts` keeps Delivery out of the bar (`BAR_TABS`), yet the SCR-43 board draws a Delivery tab (after Journey). Options: (a) show a Delivery tab for every project the user can open, always linking to `/projects/{id}/delivery` (recommended: the overview now exists for every project; one-line change in `model.ts` `visibleTabs`/`BAR_TABS`); (b) leave it out of the bar and reach it only by a link from the journey; (c) ask backend to add `delivery` to `tabs[]`. Without (a) or (c) a user cannot find the page.
2. Row order. The SCR-43 board draws 04 Archive, 05 Handover to Support, 06 Closure, while readiness fixes release, go-live, hypercare, handover, archive, closure. Options: (a) follow readiness and the API's key list (handover 04, archive 05), recommended because the API and its docs order them that way and the board's own note says hypercare, archive and handover run side by side; (b) follow the board (archive 04, handover 05) and update readiness. Either way this is a swap of two rows.
3. Board parts hidden because the API gives nothing (recommend hide, as D-182): the "DELIVERY · 3 OF 6 DONE" header tag, "DLV-0052" file number, the descriptive gate text per row ("RELEASE READY · 25 MAR", "SUPPORT LISTED 2 GAPS"), and the whole "Checked where delivery stands" Tola card with its "Next" line and "Ask Tola" button. Options: (a) hide all (recommended); (b) keep the Tola card shell with only "Checked <as_of>"; (c) ask backend for these. The header "Journey / Delivery ..." line-subnav (Overview, Release, Go-live ...) also stays unlinked until those screens are built (recommend hide the strip; alternative show it as plain text).
4. Row state wording. Board rows carry sentences, ours carry a fixed tag from the API state (table above). Options: (a) the table as written (recommended); (b) title-case words ("Action needed"). Confirm the wording of NEEDS AN OWNER, CHECKING WHAT HAPPENED and RESULT UNCERTAIN.
5. The board sentence "Hypercare, archive and handover run side by side after go-live. Closure needs all of them, a saved retrospective and Finance's confirmation." is static wording, not data. Options: (a) keep it as a static note (recommended: it states a rule the checklist enforces, no data needed); (b) hide it with the other board-only text.

## Conflicts with the boards
- SCR-43-desktop: removes "DELIVERY · 3 OF 6 DONE", "DLV-0052", the per-row gate sentences and dates ("RELEASE READY · 25 MAR", "SIGNED 02 APR", "DAY 10 OF THE WINDOW"), the Tola card, "Next" and "Ask Tola". Recommendation: accept (no API source).
- SCR-43-desktop/mobile: adds a state tag taken from the API state in place of the gate sentence, and a closure "waits on" list from `closure-checklist` in place of "NEEDS HYPERCARE, HANDOVER, RETROSPECTIVE". Recommendation: accept; the closure list is the real checklist rather than a fixed sentence.
- SCR-43-desktop: moves rows 04 and 05 (Question 2) and the Delivery tab needs a tab-bar change (Question 1). Recommendation: as in those questions.
- SCR-43-mobile: removes the "DLV-0052 · 3 OF 6 DONE" header line and the "Open the handover" button. Recommendation: accept; per-row "Open" links replace the button.
