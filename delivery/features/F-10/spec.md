# A Finance Lead opens Month-end for October 2026 and sees every task, known cash plus Unknown, and the next action

> Tasks: FE-M3-FINANCE (first part: SCR-36 only). Architecture: built against package v4 (`architecture/packages/v4/manifest.sha256` = `9d4cbc10137ee452d29d240876cf07fbf13d02ac63e9b0fbdddb1256ae568ff0`), which the mock and `src/api/schema.d.ts` load; the extra fields follow the v7 proposal D-MONTH-END-VIEW r1 (`architecture/packages/v7/manifest.sha256` = `f6231d20b4fdeabbdca9bde5986a0a7883536f1a5cafc883848ef62dd6d4b624`, proposal, mock only). E-MONTH-END is the same in v4 and v6. Design: Finance and Payroll canvas version 1794579902-95a3, approved 13 Nov (`design/review.json`); screens: SCR-36. Artboards: `design/canvas/finance/project/SCR-36-desktop.dc.html` (1440 x 900) and `SCR-36-mobile.dc.html` (390 x 844). Decisions: `delivery/OVERNIGHT-DECISIONS.md` D-07 and D-08; readiness PMO-0-3 to PMO-0-6.

## Summary
- New route `/finance/month-end?period=YYYY-MM`. It reads `GET /api/v1/finance/month-end?period=` once and shows the SCR-36 board, element for element, in the board's order, wording and styling, at 1440 and at 390.
  - Desktop: the as-of line, the four-cell strip, the task table, Chidi's note and "Import the missing statement".
  - Phone: the summary line, the task cards and the bottom action, exactly as drawn.
- Every number, label, tone, restriction and link comes from the response. The frontend counts nothing, buckets no states and picks no default month.
- Cash shows the known part plus the word "Unknown" ("₦4.7M + Unknown"). It is never 0 and never blank.
- A restricted row shows its `restricted_label` ("HR only") and has no link, even when a `work_id` is present.
- The v7 proposal fields are typed locally in `src/features/finance/month-end/proposal.ts`. All of them are optional, and the page still works on a pure v4 body. So F-10 does not depend on F-13 (the v7 repoint).
- The mock handler is a new `frontend/mock/finance.mjs`. Its default data is the desktop board's own data, and a `board-phone` scenario serves the phone board's six cards for the fidelity run. Neither shows a SAMPLE DATA tag.

## Context
- **App frame (F-01, merged):**
  - `frontend/src/app/layout.tsx` wraps every route in `AppShell` (`frontend/src/shell/AppShell.tsx`). `AppShell` loads `/me` and shows the frame's loading, signed-out, forbidden and error states before any page renders.
  - `/finance/**` is not one of the `DESTINATIONS` in `frontend/src/shell/destinations.ts`, so no top-bar item is highlighted. That is the same as `/work/[id]` today, and nothing in `src/shell/**` changes.
  - `frontend/src/shell/FrameStates.tsx` exports `LoadingState` and `SignedOutState({pathname})`.
  - `frontend/src/app/not-found.tsx` renders `UnknownPage` (`src/shell/DestinationPage.tsx:30`).
  - The phone breakpoint is `max-width: 719.98px` (`frontend/src/styles/shell.css:41`).
- **API client:**
  - `frontend/src/api/client.ts` exports `api` and `call()`.
  - `frontend/src/api/errors.ts` maps 401 to `unauthenticated`, 403 to `forbidden` and 404 to `not_found`. Anything else is `server`, and a failed fetch is `network`.
  - E-MONTH-END is already typed from v4: `operations["E-MONTH-END"]` in `frontend/src/api/schema.d.ts:2157`, path `/api/v1/finance/month-end` at :348.
  - v4 has `period` required in the query; 200 `{period, tasks[{line, state, where, work_id?}], cash_received{amount?, currency, unknown}}` with `additionalProperties: false`; and errors 401, 403 and 404.
- **Reused read-only (no edits):**
  - `STATE_TAGS`: `frontend/src/features/work-item/labels.ts`
  - `formatAmount` and `formatClock`: `frontend/src/features/decide/format.ts:14,27`
  - `WorkErrorCard`: `frontend/src/features/work-item/WorkItemStates.tsx`
  - Tag classes `psl-tag--waiting|person|agent|done|neutral`: `frontend/src/styles/psl-bundle.css:208-213`
  - `psl-empty`, `psl-panel` and `psl-btn`
- **Mock (`frontend/mock/server.mjs`):**
  - It loads v4 (:22).
  - `M1_OPERATIONS` is at :24. At startup the server reads `fixtures/<operationId>.json` for every M1 operation (`createMockServer`, around :195), so E-MONTH-END needs a top-level `fixtures/E-MONTH-END.json`.
  - Scenarios (`X-Mock-Scenario` or the `psl_mock_scenario` cookie) are applied before dispatch, for declared statuses only.
  - Per-module dispatch follows `work-list.mjs`, and F-06's `exceptions.mjs` (`contractBody`, a board cookie) is the pattern to copy.
  - Unknown `/work/<id>` ids get the default work item (`workResponse`, :70-77).
- **Tests:**
  - `frontend/tests/mock-contract.test.ts` expects every M1 operation to answer 200 for every persona and validates the body against v4.
  - The axe helpers (`TAGS`, `expectNoAxeViolations`, `DESKTOP`, `PHONE`) are in `frontend/e2e/work-item.spec.ts:1-15`.
  - Playwright takes `E2E_PORT` and `MOCK_PORT` (`frontend/playwright.config.ts`).
- **Mascots:** `frontend/public/` does not exist on the base. F-02 and F-08 each add the same three files, uncommitted in their worktrees: `frontend/public/agents/{tola,chidi,zainab}.png`. They are 96 px exports of `design/mascots/transparent/{pmo,finance,hr}-avatar.png` (`design/system/project/assets/Mascots/README.md`), with md5 `e07868f1…`, `7fd30793…` and `b6f579d3…`.
- **Nothing exists** under `frontend/src/app/finance/` or `frontend/src/features/finance/`.

## Contract

### GET /api/v1/finance/month-end (E-MONTH-END, read)
- **Request:** `call(api.GET('/api/v1/finance/month-end', { params: { query: { period } } }))`.
  - It is sent only when the URL's `period` matches `^[0-9]{4}-(0[1-9]|1[0-2])$`.
  - A missing, repeated or malformed `period` calls `notFound()` from `next/navigation` (it renders `app/not-found.tsx`), and no request is sent.
- **Permission and tenant rule:** Session plus `finance.read`. A 404 hides what the person may not see (endpoints.csv:19).
  - The frontend never reads `useMe().roles` or `destinations` to decide whether to fetch, what to show or what is restricted.
  - It renders exactly the tasks returned, in the order returned.
- **Idempotency/versioning:** read-only, so it is safe to retry. There is one read per page open and no polling.
  - A request counter drops an answer to a superseded period or retry (pattern: `useWorkHistory`).
- **Types:** in `frontend/src/features/finance/month-end/proposal.ts`, with no edit to `src/api/**`.
  - `MonthEndBase = operations['E-MONTH-END']['responses'][200]['content']['application/json']`.
  - `MonthEndProposal` lists the D-MONTH-END-VIEW r1 fields with the exact v7 names and types, all optional:
    - `as_of?: string` (date-time)
    - `coverage?: string`
    - `summary?: {done?, waiting?, in_progress?, total?: number}`
    - `cash_received_detail?: {known?: {amount?: string; currency: string; unknown: boolean}; has_unknown: boolean; unknown_note?: string}`
    - `agent_note?: {agent: 'tola'|'chidi'|'zainab'; text: string}`
    - `next_action?: {label: string; work_id?: string}`
  - `MonthEndTaskProposal` adds, all optional:
    - `title?`, `detail?`, `status_label?`
    - `tone?: 'neutral'|'person'|'agent'|'stopped'|'uncertain'|'verified'|'restricted'`
    - `restricted?: boolean`, `restricted_label?: string`
  - `MonthEnd = Omit<MonthEndBase,'tasks'> & MonthEndProposal & { tasks: (MonthEndBase['tasks'][number] & MonthEndTaskProposal)[] }`.
  - When F-13 regenerates `schema.d.ts` from v7, these intersections stay valid. The file header names D-MONTH-END-VIEW r1 and says the fields are a proposal and mock only.

### Display rules (`frontend/src/features/finance/month-end/model.ts`; pure functions, unit-tested)

| Element | Source | Rule when a field is absent or unusable |
|---|---|---|
| Eyebrow | static `FINANCE / MONTH-END` (desktop only) | n/a |
| Heading | `period` from the response: desktop "Month-end · October 2026", phone "Month-end · Oct" (en-GB month names, no time zone) | an unparseable period shows "Month-end · {period}" |
| As-of line (desktop) | `{coverage} · UPDATED {formatClock(as_of)}`, e.g. "FROM RECORDS YOU CAN SEE · UPDATED 10:42" (Africa/Lagos). Coverage text as returned. | missing `coverage`: "UPDATED 10:42" only. Missing `as_of`: coverage only. Both missing: the line is not rendered. |
| DONE cell | `"{summary.done} of {summary.total}"` | either one missing: "Unknown" |
| WAITING and IN PROGRESS cells | `summary.waiting`, `summary.in_progress` | missing: "Unknown". Never 0 and never counted from `tasks`. |
| CASH RECEIVED cell | see the cash rules below | |
| Phone summary line | `<strong>{done} of {total}</strong> done · {waiting} waiting` | a missing value shows "Unknown" in its place |
| Task title | `title ?? line` | n/a |
| Task detail (desktop, under the title) | `detail` | not rendered |
| Where it is | `where` (required) | n/a |
| State tag text | `status_label ?? STATE_TAGS[state].text.toUpperCase()` | n/a |
| State tag tone | `tone`, mapped: neutral to `psl-tag--neutral`; person and stopped to `--person`; agent to `--agent`; uncertain and restricted to `--waiting`; verified to `--done` | `tone` missing: `STATE_TAGS[state].tone` |
| Last cell (desktop) | `restricted === true`: plain text `restricted_label ?? 'Restricted'`, no link, whatever `work_id` says. Otherwise, if `work_id` is present: `<Link href="/work/{encodeURIComponent(work_id)}">Open</Link>`. | otherwise the cell is empty |
| Agent note (desktop aside) | `agent_note`: avatar `/agents/{agent}.png` (alt `""`, 36 px round), then "<strong>Chidi</strong> · Finance agent", a line break and `text`. Names: tola "Tola · PMO agent", chidi "Chidi · Finance agent", zainab "Zainab · HR agent". | not rendered |
| Next action | `next_action` with a `work_id`: a primary block link (`label`) to `/work/{work_id}` (D-07). Desktop: below the note in the aside. Phone: in a bottom bar, `position: sticky; bottom: 0`, white with a 2 px ink top border, as drawn. | no `next_action`, or no `work_id`: not rendered, and on the phone the bar is not rendered either |

**Cash rules** (`cashView(body) → {text, description, unknown}`). `known` means `known.unknown === false` and `known.amount` matches `^-?[0-9]+\.[0-9]{2}$`.
1. If `cash_received_detail` is present:
   - known and `has_unknown`: "{compact} + Unknown"
   - known and not `has_unknown`: "{compact}"
   - otherwise: "Unknown"
2. Otherwise, from v4 `cash_received`:
   - `unknown === false` with a valid amount: "{compact}"
   - otherwise: "Unknown"
3. **Compact form:** use the integer digits of the decimal string (BigInt or string arithmetic, never `parseFloat`). Pick B (≥10⁹), M (≥10⁶) or K (≥10³) and round to one decimal, half away from zero. Drop a trailing ".0". If rounding reaches 1000 of a unit, step up to the next unit.
   - Prefix "₦" for NGN, otherwise "{currency} ". The sign goes first.
   - Amounts below 1,000 use `formatAmount`.
   - Examples: `4712500.00` gives ₦4.7M, `5000000.00` gives ₦5M, `4750000.00` gives ₦4.8M, `999950000.00` gives ₦1B, `-1250.00` gives -₦1.3K, and USD `1200.00` gives USD 1.2K.
4. **Full value:** `description` is "Known so far {formatAmount(known)}; the rest is not known yet." when the cell shows "+ Unknown", "{formatAmount(...)}" when the amount is fully known, and "Not known yet." when it is Unknown. It goes in a visually hidden span referenced by `aria-describedby` on the cell value, so the visible name stays the board's text.
5. **Cell colour:** amber (waiting tint and ink) when the text contains "Unknown", otherwise white with ink text. DONE stays green (#22764A on white), WAITING amber and IN PROGRESS white with #626B6F, as drawn.
6. `unknown_note` is not rendered (no board element).

### Screen states

| State | What the person sees |
|---|---|
| Loading | `LoadingState` from the frame |
| 401 | `SignedOutState` with `pathname` = `/finance/month-end?period=2026-10` (the current path and query) |
| 403 or 404 | `MonthEndNoAccess`, the same view for both (INV-ACCESS). It has the `psl-tag--neutral` tag "NO ACCESS", the h1 "You can’t open this month-end checklist", the line "It is for people who work on Finance for this month. Nothing about it is shown here." and a `psl-btn--dark` link "Back to my queue" to `/my-work`. It shows no amounts, counts or task names. |
| `server` or `network` | `WorkErrorCard` with "We couldn’t load the month-end checklist. Your work is safe; nothing was changed." Try again re-reads. |
| Empty (`tasks: []`) | The heading, as-of line and strip as returned. In place of the table or cards: `psl-empty`, "No month-end tasks you can see for October 2026." The agent note and the next action render only if returned. |
| Success | The board (above), at both breakpoints |

### Layout (both boards, as drawn)
- **Desktop (≥720 px):**
  - Main column max 1320 px, padding 28/28/56, gap 20.
  - The eyebrow; the h1 (Archivo 800 34 px) and the as-of line (Plex Mono 12 px, #4A5357), space-between.
  - `<section aria-label="Facts earned">`: the strip, a 4-column grid with 2 px ink borders. Labels are Mono 11 px with 0.06em letter-spacing, and values are Archivo 700 16 px.
  - Then the flex row:
    - The table section (flex 999 1 600px, a white 2 px frame, `overflow-x: auto`, table min-width 760). Header cells: TASK, WHERE IT IS, STATE and an empty one. Body cells have 10/14 padding and a 1 px #D5D9D3 bottom rule.
    - The `<aside>` (flex 1 1 320px, max 420): the note box (#E9EEFB, 2 px #2459D6 border, text #16388F) and the 50 px primary link.
  - The board's fixed top nav is the app frame's.
- **Phone (<720 px):**
  - A page back link "← Finance", just under the frame's phone bar (D-08). It is an `<a href="/my-work">` (fallback), and on click it calls `router.back()` when `window.history.length > 1` (PMO-0-4). Phone only.
  - The h1 (22 px), the summary line (14 px) and one card per returned task: white, 2 px ink border, padding 12, gap 6. Each card has the title and tag on one line (space-between) and then `where` (13 px #4A5357).
  - The cards have no detail, no Open link, no strip, no cash cell and no agent note, as drawn (PMO-0-5).
  - Then the bottom action bar.
- **CSS:** in `frontend/src/features/finance/month-end/month-end.css`, using `tokens.css` variables where a token equals the board hex. No edit to `tokens.css`, `psl-bundle.css` or `shell.css`.

### Mock (`frontend/mock/finance.mjs`, `export function monthEnd({ url, persona, cookies })`)
- **Personas:** finance_lead gets 200. pm and none get 403 `{code:'forbidden', message:'Month-end is for Finance.'}`.
- **Period:** `2026-10` is served. Any other value, including a missing or malformed one, gets 404 with `SCENARIO_BODIES[404]`. (The frontend never sends the malformed ones.)
- **Cookie `psl_mock_month_end`:**
  - absent: `fixtures/E-MONTH-END.json`
  - `board-phone`: `fixtures/finance/month-end.board-phone.json`
  - `known`: `fixtures/finance/month-end.known.json`
  - `unknown`: `fixtures/finance/month-end.unknown.json`
  - `empty`: `fixtures/finance/month-end.empty.json`
  - `contract`: the default body passed through `contractBody`
  - any other value: the default
- `export function contractBody(body)` strips the proposal keys:
  - top level: `as_of`, `coverage`, `summary`, `cash_received_detail`, `agent_note`, `next_action`
  - per task: `title`, `detail`, `status_label`, `tone`, `restricted`, `restricted_label`
- **`server.mjs` change, exactly:** one import line, `'E-MONTH-END'` appended to `M1_OPERATIONS`, and one dispatch line, `if (route.operationId === 'E-MONTH-END') { const r = monthEnd({ url, persona, cookies }); return send(res, r.status, r.body); }`. Nothing else, and v4 stays.
- Fixtures carry no `sample` key (v4 `additionalProperties: false`). They are mock files only.

**Default fixture `fixtures/E-MONTH-END.json`** (the desktop board's data):
```json
{
  "period": "2026-10",
  "as_of": "2026-11-14T09:42:00Z",
  "coverage": "FROM RECORDS YOU CAN SEE",
  "summary": { "done": 2, "waiting": 3, "in_progress": 2, "total": 7 },
  "cash_received": { "currency": "NGN", "unknown": true },
  "cash_received_detail": {
    "known": { "amount": "4712500.00", "currency": "NGN", "unknown": false },
    "has_unknown": true,
    "unknown_note": "One Access Bank statement is not imported."
  },
  "tasks": [
    { "line": "Bank statements", "title": "Bank statements", "detail": "Access Bank statement missing", "where": "2 of 3 accounts imported", "state": "waiting", "status_label": "WAITING", "work_id": "W-1601" },
    { "line": "Management accounts", "title": "Management accounts", "detail": "Accounting preparation and reviewed reports", "where": "In review · Finance reviewer", "state": "action_needed", "status_label": "NEEDS FINANCE DECISION", "tone": "person", "work_id": "W-1602" },
    { "line": "Income detail and schedules", "title": "Income detail and schedules", "detail": "Income detail and schedule inventory", "where": "Verified 05 Nov", "state": "verified", "status_label": "DONE", "tone": "verified", "work_id": "W-1603" },
    { "line": "Fixed asset schedule", "title": "Fixed asset schedule", "detail": "Asset schedule and reviewed accounting note", "where": "Waiting for register review", "state": "waiting", "status_label": "WAITING", "work_id": "W-1604" },
    { "line": "Cash forecast", "title": "Cash forecast", "detail": "Reviewed cash forecast and actual follow-up", "where": "Published 06 Nov", "state": "verified", "status_label": "DONE", "tone": "verified", "work_id": "W-1605" },
    { "line": "Business-unit totals", "title": "Business-unit totals", "detail": "Reviewed BU exception and event aggregates", "where": "Waiting for payroll matching", "state": "waiting", "status_label": "WAITING", "work_id": "W-1606" },
    { "line": "Payroll", "title": "Payroll", "detail": "Restricted payroll and BU staff-cost receipt", "where": "Restricted · HR's work", "state": "waiting", "status_label": "WAITING ON HR", "tone": "restricted", "restricted": true, "restricted_label": "HR only" }
  ],
  "agent_note": { "agent": "chidi", "text": "One Access Bank statement isn't imported, so October's cash received for that account is Unknown, not 0. Import it to complete the month." },
  "next_action": { "label": "Import the missing statement", "work_id": "W-1601" }
}
```

**Variants**, each in `fixtures/finance/`, a copy of the default with these changes:
- `board-phone`: the first six tasks only. Summary, cash, note and action unchanged.
- `known`: `cash_received {amount:"4712500.00", currency:"NGN", unknown:false}`; `cash_received_detail {known:{...same}, has_unknown:false}`; no `agent_note`; no `next_action`.
- `unknown`: `cash_received_detail {has_unknown:true}`, with no `known`.
- `empty`: `tasks: []`; `summary {done:0, waiting:0, in_progress:0, total:0}`; `cash_received_detail {has_unknown:true}`; no `agent_note`; no `next_action`.

Each variant, after `contractBody`, validates against the v4 200 schema. Each one, as served, validates against the v7 200 schema (`architecture/packages/v7/openapi.json`, read by the test only).

## Lanes
- **Frontend lane (all of the build):**
  - `frontend/src/app/finance/month-end/page.tsx`: a server component. It awaits `searchParams`, validates `period`, calls `notFound()` or renders `<MonthEndView period>`, and sets metadata `{ title: 'Month-end · PSL Factory' }`.
  - `frontend/src/features/finance/month-end/**`: `proposal.ts`, `model.ts`, `useMonthEnd.ts`, `MonthEndView.tsx`, `MonthEndStates.tsx`, `month-end.css`.
  - `frontend/mock/finance.mjs`, `frontend/mock/fixtures/E-MONTH-END.json`, `frontend/mock/fixtures/finance/**`.
  - `frontend/tests/finance-month-end*.test.ts(x)`, `frontend/e2e/finance-month-end*.spec.ts`.
  - `delivery/features/F-10/fidelity-exceptions.json`.
- **Backend lane:** no work in F-10. T-FINANCE (the real E-MONTH-END and the D-MONTH-END-VIEW fields) belongs to the backend developer. build.md lists the proposal fields for them.
- **Integration owner (shared files; keep each touch minimal and rebase on whichever lane merges first):**
  - `frontend/mock/server.mjs`: the 3 lines above (F-02 and F-05 to F-08 touch the same lines).
  - `frontend/tests/mock-contract.test.ts`, entries only:
    - `QUERY['E-MONTH-END'] = '?period=2026-10'`
    - a per-persona expected status, `{ 'E-MONTH-END': { pm: 403, none: 403 } }`
    - a contract-body strip, `{ 'E-MONTH-END': contractBody }`
    - If F-06 has merged first, add to its `PERSONA_STATUS` and `CONTRACT_BODY` maps. Otherwise introduce them in F-06's exact shape (F-06 diff of this file).
  - `frontend/public/agents/{tola,chidi,zainab}.png`: byte-identical copies of F-02's and F-08's files (md5 as in Context). Identical add/add merges cleanly. Do not re-export them.
- **Read-only imports:** `src/features/work-item/labels.ts`, `src/features/work-item/WorkItemStates.tsx`, `src/features/decide/format.ts`, `src/shell/FrameStates.tsx`, `src/api/{client,errors,schema}.ts`. Edit nothing outside the paths above, and list every touched path in build.md.

## Acceptance criteria
Run the app with `cd frontend && MOCK_PORT=4002 npm run dev -- -p 4001`, signed in as the default mock persona (finance_lead). "The page" means `http://localhost:4001/finance/month-end?period=2026-10`.

1. **Desktop board.** At 1440 x 900 the page shows, in this order:
   - "FINANCE / MONTH-END"
   - the h1 "Month-end · October 2026" and "FROM RECORDS YOU CAN SEE · UPDATED 10:42"
   - the strip DONE "2 of 7", WAITING "3", IN PROGRESS "2", CASH RECEIVED "₦4.7M + Unknown"
   - the 7 rows in fixture order, with the board's titles, details, where-text and tags. "NEEDS FINANCE DECISION" uses `psl-tag--person`, DONE uses `--done`, and WAITING and WAITING ON HR use `--waiting`.
   - Chidi's note with `/agents/chidi.png`, and "Import the missing statement"

   — verify: open the page; `frontend/e2e/finance-month-end.spec.ts` asserts the texts and their order.
2. **Phone board.** At 390 x 844 with cookie `psl_mock_month_end=board-phone`, the page shows:
   - "← Finance", the h1 "Month-end · Oct" and "2 of 7 done · 3 waiting"
   - six cards with title, tag and where-text
   - "Import the missing statement" pinned at the bottom
   - no strip, no table, no Chidi note and no Open links

   — verify: e2e at PHONE.
3. **Design fidelity.** The design-fidelity check passes on `SCR-36-desktop.dc.html` at 1440 (default data) and `SCR-36-mobile.dc.html` at 390 (`board-phone`): 100% of board elements after the approved exceptions, and visual ≥ 90. The approved exceptions in `delivery/features/F-10/fidelity-exceptions.json` are only:
   - "Start work" and "More ways to start" (frame, F-05, D-04(a))
   - the Open and CTA link targets (PMO-0-3 and D-07)
   - "← Finance" moved under the phone bar (D-08 and PMO-0-4)
   - the board's `/_blob/` image replaced by `/agents/chidi.png`

   — verify: reports in `delivery/features/F-10/round-<N>/fidelity/` for both boards.
4. **Unknown is never 0.**
   - Default data: "₦4.7M + Unknown".
   - `psl_mock_month_end=unknown`: the cell reads exactly "Unknown".
   - `known`: "₦4.7M", in a white cell.
   - In every case no "₦0", "0" or empty value is in the cash cell, and the full value is exposed through `aria-describedby` ("Known so far ₦4,712,500.00; the rest is not known yet." on the default data).

   — verify: `frontend/tests/finance-month-end.test.tsx` covers the `cashView` table: all the Contract examples, a malformed amount ("4.7M" or "") giving "Unknown", `known.unknown: true` with an amount giving "Unknown", and detail absent with v4 `unknown: true` giving "Unknown". e2e checks the three scenarios.
5. **Restricted rows never link.**
   - The Payroll row shows "HR only" and contains no `<a>`.
   - A unit test renders a restricted task that also carries `work_id: "W-9"`, and asserts it has no link and that no `/work/W-9` href appears anywhere on the page.
   - A restricted task with no `restricted_label` shows "Restricted".
   - A non-restricted task with no `work_id` has an empty last cell.

   — verify: `finance-month-end.test.tsx`, and an e2e locator on the Payroll row.
6. **Links go to work items.** Each of the six other rows' "Open" has `href="/work/W-1601"` … `"/work/W-1606"` in order. "Import the missing statement" has `href="/work/W-1601"` on both breakpoints. No href on the page contains `SCR-`, `.dc.html` or `claude.ai`.

   — verify: e2e, with an href list assertion.
7. **Counts are taken as returned.** A unit test serves a body whose `summary` is `{done: 5, waiting: 0, in_progress: 9, total: 4}` (deliberately inconsistent with `tasks`) and asserts the strip shows "5 of 4", "0" and "9". A body with no `summary` shows "Unknown" in all three cells and "Unknown done · Unknown waiting" on the phone.

   — verify: `finance-month-end.test.tsx`.
8. **v4-only body (no F-13 dependency).** With `psl_mock_month_end=contract`:
   - the page renders without errors
   - there is no as-of line
   - the counts are "Unknown" and the cash is "Unknown"
   - rows show `line` and the `STATE_TAGS` text in upper case ("WAITING", "ACTION NEEDED", "VERIFIED")
   - the six rows with `work_id` link; the Payroll row (no `work_id`) has no link and no text
   - no note and no action

   — verify: e2e and a unit test over `contractBody(defaultFixture)`.
9. **Period handling.**
   - `/finance/month-end` with no period, `?period=2026-13`, `?period=Oct`, `?period=2026-10&period=2026-11` and `?period=` each show "This page doesn’t exist." with no request to `/api/v1/finance/month-end` (assert there is no such request in the network log).
   - `?period=2026-09` shows the no-access view (mock 404).
   - The frontend source sets no default period: `grep -rn "new Date" frontend/src/features/finance frontend/src/app/finance` finds only `formatClock` call sites.

   — verify: e2e and unit tests of the period validator.
10. **Wrong user.** With cookie `psl_mock_persona=pm` (and separately `none`), the page shows "You can’t open this month-end checklist" and "Back to my queue", and no "₦", no task title and no count appears. Scenario 403 and scenario 404 render identical DOM in `main`.

    — verify: e2e, plus a unit test comparing the 403 and 404 renders.
11. **Signed out.** With `psl_mock_scenario=401`, the frame's signed-out state is shown (the frame's `/me` 401 path). With `/me` succeeding and month-end answering 401 (unit test with a mocked client), the page shows `SignedOutState` and the sign-in link's `next` is `/finance/month-end?period=2026-10`.

    — verify: `finance-month-end.test.tsx`.
12. **Load failure.** If the month-end read returns 500 or the network fails (unit test), the error card shows "We couldn’t load the month-end checklist. Your work is safe; nothing was changed." with "Reference <code> for support." Try again re-reads, and on success the board shows. An answer that arrives after a retry has started is ignored.

    — verify: `finance-month-end.test.tsx`.
13. **Empty.** `psl_mock_month_end=empty` shows the strip ("0 of 0", "0", "0", "Unknown" cash) and "No month-end tasks you can see for October 2026.", with no table, cards, note or action.

    — verify: e2e at both viewports.
14. **Mock contract.**
    - `npm test` passes, including the new mock tests: finance_lead gets 200; pm and none get 403 with the declared error shape; `2026-09` and a missing period get 404.
    - Every served variant, after `contractBody`, validates against v4 E-MONTH-END. As served, it validates against v7 E-MONTH-END.
    - The generic `mock-contract.test.ts` loop covers E-MONTH-END.
    - `architecture/packages/v4/openapi.json`, `src/api/schema.d.ts` and `OPENAPI_PATH` are unchanged.

    — verify: `cd frontend && npm test`; `git diff --stat <base> -- architecture frontend/src/api` is empty.
15. **Accessibility (A-ACCESSIBILITY).**
    - axe with `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa` and `wcag22aa` reports no violations at 1440 and at 390, for these scenarios: default, `board-phone`, `unknown`, `empty`, `contract`, pm (no access) and invalid period.
    - Tabbing reaches every Open link, "Import the missing statement" and "← Finance" (on the phone), each with a visible focus outline.
    - The table has a header row. The avatar is decorative (`alt=""`).

    — verify: `cd frontend && E2E_PORT=4001 MOCK_PORT=4002 npx playwright test e2e/finance-month-end.spec.ts`.
16. **Back link.** On the phone, "← Finance" opened from `/my-work` (navigate there, then to the page) returns to `/my-work` via history. Opened directly in a fresh tab, its href `/my-work` is followed. It is hidden at 1440.

    — verify: e2e.
17. **No sample tag, no debug identifiers.** No "SAMPLE DATA" text appears at either breakpoint (the build has no `NEXT_PUBLIC_SHOW_SAMPLE_LABEL`). No work id (`W-16xx`), state key (`action_needed`) or process ID is visible as text on the page.

    — verify: e2e text assertions.

## Out of scope
- The other Finance screens and the F-10B to F-10J split: SCR-09, -18, -37, -53 to -59; payroll import and match; the "Open month-end" link on SCR-53; the Overview "Month-end" link (F-08 follow-up).
- E-IMPORT (POST) and any upload or import UI. "Import the missing statement" only navigates to the work item.
- Any edit to `architecture/**`, `openapi.json` or `src/api/schema.d.ts`, the v4 to v6 or v7 mock repoint (F-05 and F-13), and regenerating types.
- `src/shell/**`: no Finance top-bar item, no `/me` destination, no phone-bar back-link slot (the D-08 follow-up) and no Start work control.
- Edits to `src/features/{work-item,decide,my-work,exceptions,overview,projects,start-work,floor}/**`, `me.*.json`, other lanes' fixtures, and new `fixtures/work/W-16xx.json` items. Open goes to the default sample work item in the mock.
- Showing payroll detail, BU staff costs or any restricted value. Deciding restriction from the line name, `state` or the person's role.
- Counting or bucketing task states in the browser, totalling cash, or computing "done of total".
- A month picker, a default month, previous or next month navigation, and polling or live updates.
- Adding the strip, cash cell, Payroll card, detail lines, Open links or Chidi note to the phone, or dropping any of them from the desktop (PMO-0-5).
- Rendering `unknown_note`. New npm dependencies. Edits to `tokens.css`, `psl-bundle.css` or `shell.css`. `delivery/checks.sh`, `delivery/config.json` and `delivery/merge-policy.json` stay unchanged.

## Assumptions
- **The proposal fields copy v7 D-MONTH-END-VIEW r1 names and types, not readiness PMO-0-1's draft names.** v7 now exists, so F-13 can switch to it without renames. Example: `cash_received_detail{known, has_unknown}` rather than a reshaped `cash_received`.
- **Tone mapping.** The v7 `tone` enum has no "waiting" value, so absent `tone` falls back to `STATE_TAGS[state].tone`; `uncertain` and `restricted` map to amber and `stopped` to red. This keeps the board's colours, and the backend developer should confirm the mapping.
- **The phone renders every task returned (including the restricted one, as "Payroll" with no link).** The default-data phone view therefore has 7 cards. The phone fidelity run uses the `board-phone` scenario (the phone board's own six rows, as in D-04(f)). Hiding returned records on one breakpoint would be a frontend filtering rule.
- **Phone cards have no Open link because the board draws none.** Phone users reach tasks only through the work items. This is flagged for the design engineer with PMO-0-5, as a likely board gap.
- **The cash cell is amber only while it shows Unknown.** The board shows only the Unknown case, and amber is the design system's waiting tone.
- **Compact money rounds to one decimal, half away from zero, with B/M/K units.** The board shows only "₦4.7M". The full value is always available to assistive technology.
- **The full cash value uses `aria-describedby`, not the accessible name.** This keeps the board text as the name the fidelity check matches. Readiness said "accessible name"; the intent, exposing the full value, is met.
- **A missing count shows "Unknown"** (INV-UNKNOWN), not "–" or 0.
- **403 and 404 share one month-end no-access view.** This follows INV-ACCESS and the F-03 `NoAccessState` precedent. The frame's `ForbiddenState` wording ("Your account can’t use PSL Factory") would be wrong here.
- **An invalid period is a 404 page and sends no request.** The contract pattern also allows `2026-13`; the frontend rejects that because it cannot name the month.
- **"← Finance" uses `router.back()` when history exists and `/my-work` otherwise**, as PMO-0-4 and D-07 say. The design engineer is to name the real target.
- **The mock answers pm and none with 403, and any period other than 2026-10 with 404.** The contract declares both, and the mock has one month of data.
- **No polling.** D-UPDATES r2 covers only an open work item whose agent is working.
- **The mascot files are copied byte-identical from F-02 and F-08** so the three lanes merge cleanly. Re-exporting them would create conflicting binaries.
- **The as-of time is shown in Africa/Lagos via `formatClock`.** This is the project's convention for every clock time.
