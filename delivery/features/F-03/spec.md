# Open one work item and read its history

> Tasks: FE-WORKITEM. Architecture: package v3, manifest digest `2f74232fcac4f8fdd2cf0b4e61bf917863172c871890fb8331b61602fc3e04e5` (`architecture/packages/v3/manifest.sha256`). Design: approved canvas version 1794581312-b166 (design/review.json); screens: SCR-02 (all states incl. history and permission), STATES-desktop / STATES-mobile.

## Summary
- `/work/[id]` shows one work item from `GET /api/v1/work/{work_id}`. It has a header, a state tag, the six separate facts, the station track, the agent checklist, the current human tasks and the next step. Everything is read-only.
- `/work/[id]/history` shows the item's history from `GET /api/v1/work/{work_id}/history`. It has the All / Decisions / Agent work / Evidence filter, 10/20/50 rows with cursor "Show more", restricted entries and times in WAT.
- The open item re-fetches every 5 s only while its agent is working and the page is visible (D-UPDATES r2). History re-fetches when the item's revision changes.
- The contract mock serves per-id fixtures for E-WORK-ITEM and E-WORK-HISTORY, and honours `kind`, `cursor` and `limit`. Unknown ids fall back to today's default fixtures so F-02 and F-04 keep working.
- Values the boards show but the v3 contract does not carry are left out, never invented. Each one is listed under "Contract gaps" for the architecture revision.

## Context
- **App frame (F-01, merged a41d472):** `frontend/src/shell/AppShell.tsx` loads `/me` and provides `useMe()`. It renders 401 (`SignedOutState`), 403 (`ForbiddenState`) and other errors (`LoadErrorState`) for `/me` only. Persona `none` gets `NoSectionsState`, so a work page never renders for it. `frontend/src/shell/FrameStates.tsx` has `LoadingState`, `SignedOutState`, the error-card classes (`shell-errorcard`, `shell-eyebrow`, `shell-reference`) and the `psl-empty` pattern. `frontend/src/shell/SampleLabel.tsx` shows the build-level SAMPLE DATA label.
- **API client:** `frontend/src/api/client.ts` exports `api` and `call()` (openapi-fetch, typed from `frontend/src/api/schema.d.ts`, generated from `architecture/packages/v2-reviewed/openapi.json`). `frontend/src/api/errors.ts` exports `ApiError` with `kind`: unauthenticated, forbidden, not_found, stale, invalid, server or network. `frontend/src/api/types.ts` holds the derived types. v3 and v2-reviewed are byte-identical for E-WORK-ITEM and E-WORK-HISTORY (checked), so the generated types are current.
- **Mock:** `frontend/mock/server.mjs` serves one fixture per operation (`fixtures[route.operationId]`, near line 98). It ignores `work_id`, `kind`, `cursor` and `limit`. Scenarios come from the `X-Mock-Scenario` header or the `psl_mock_scenario` cookie (401/403/404). Fixtures:
  - `frontend/mock/fixtures/E-WORK-ITEM.json`: W-1001, state waiting, task T-2001 for Finance Lead.
  - `frontend/mock/fixtures/E-WORK-HISTORY.json`: 3 rows, out of time order.
- **Tests:**
  - `frontend/tests/mock-contract.test.ts` validates mock answers with Ajv against the OpenAPI file.
  - `frontend/tests/shell.test.tsx` shows the jsdom, `fetch`-stub and axe conventions.
  - `frontend/e2e/frame.spec.ts` with `frontend/playwright.config.ts` (ports from `E2E_PORT`/`MOCK_PORT`) runs axe in Chromium at 390 and 1440.
- **Design system:** `frontend/src/styles/psl-bundle.css` already has `psl-tag--person|waiting|agent|done|neutral`, `psl-facts`/`psl-fact--earned|current|unknown`, `psl-track`/`psl-station--done|person|agent|waiting|stopped|todo|verified`, `psl-agent`, `psl-steps`/`psl-step--done|now|next|wait|stopped`, `psl-avatar--chidi|tola|zainab`, `psl-callout--info|warning|problem|success`, `psl-crumb`, `psl-tabs`, `psl-seg`, `psl-table`, `psl-showmore`, `psl-mono`, `psl-pulse`, plus a `prefers-reduced-motion` block. `tokens.css` and `psl-bundle.css` are drift-tested (`tests/styles-drift.test.ts`): do not edit them.
- **No route** exists today under `frontend/src/app/work/`.

## Contract

### GET /api/v1/work/{work_id} (E-WORK-ITEM)
- **Request:** `call(api.GET('/api/v1/work/{work_id}', { params: { path: { work_id } } }))`. No body. Session cookie.
- **200:** `{ id, title, line, reference, state, revision, stations[], facts[], tasks[], agent, next_step, sample }`. `additionalProperties: false` throughout.
  - `state` is one of 11 values.
  - `stations[].status` is one of: done, current_person, current_agent, waiting, stopped, not_started, verified.
  - `facts[]` holds `{name: drafted|reviewed|approved|sent|receipt_recorded|verified, status: earned|current|not_yet|unknown, at?}`.
  - `tasks[]` holds `{id, kind, title, required_role, you_can_act, revision}`.
  - `agent` is `{status: working|done|waiting|stopped|none, name?, steps?[{text, status (free string), source?}]}`.
- **Errors:**
  - 401 shows the shell's `SignedOutState` with `pathname`.
  - 403 and 404 both show the SCR-02 permission view. The backend hides records the person may not see (INV-ACCESS); the UI never says which code it got.
  - Network and other errors show the work-item error card with Try again.
- **Permission and tenant rule:** the backend decides (case.read plus the line's read permission). The UI shows only what came back and never infers access from `/me` destinations. `you_can_act` is the only input that decides whether the decision link shows.
- **Idempotency/versioning:** read-only. `revision` is shown as "revision N" and drives the history re-fetch.

### GET /api/v1/work/{work_id}/history (E-WORK-HISTORY)
- **Request:** query `kind` (all|decisions|agent_work|evidence; the UI always sends it, default `all`), `limit` (10|20|50; the UI always sends it, default 20) and `cursor` (only for "Show more", taken from the previous `next_cursor`).
- **200:** `{ items[{at, actor_kind: person|agent|factory, actor, event, version?, detail?, restricted}], next_cursor?, as_of }`. Rows render in the order returned (newest first, D-PAGING r2). The UI does not re-sort.
- **Errors:** as above. A history error does not take over the page: the header and tabs stay, and the history area shows the error card with Try again.
- **Read-only:** no control on the history view edits, deletes or annotates anything (INV-AUDIT).

### Mock behaviour (owned by F-03, integration decision on PMO-0-3)
- **Per-id fixture files:** `frontend/mock/fixtures/work/<id>.json` (E-WORK-ITEM 200 body) and `frontend/mock/fixtures/work/<id>.history.json` (`{ "as_of": ..., "items": [...] }`). Each history item may carry one mock-only field, `"_kind": "decision" | "agent_work" | "evidence"`. The mock strips it before responding.
- **E-WORK-ITEM:**
  - Takes `work_id` from the path.
  - Serves `work/<id>.json` when present.
  - Answers 404 `{code:"not_found", message:"We could not find that record."}` for the reserved no-access id `W-1099`.
  - Otherwise serves `E-WORK-ITEM.json` unchanged (fallback).
- **E-WORK-HISTORY:**
  - Takes `work_id` from the path. Uses `work/<id>.history.json` when present, otherwise `E-WORK-HISTORY.json`. Answers 404 for `W-1099`.
  - Filters by `kind`: `all` or absent returns everything; the others match `_kind` (`decisions` matches `decision`). Items without `_kind` appear only under `all`.
  - Pages with `limit`, default 20; a value outside 10/20/50 is treated as 20. `cursor` is an opaque offset string the mock created (e.g. `"o:20"`); an unrecognised cursor starts from the first page. `next_cursor` is present only when more rows remain.
- **Scenarios** (`X-Mock-Scenario`, `psl_mock_scenario`) still win over fixtures, as today. Personas and CSRF behaviour are unchanged.
- **Unchanged:** the default `E-WORK-ITEM.json` and `E-WORK-HISTORY.json` contents, and `OPENAPI_PATH`.
- **Required fixtures** (all `sample: true`, all schema-valid; `_kind` stripped):

| id | state | purpose |
|---|---|---|
| W-1001 | waiting | item served by the fallback, unchanged. New `W-1001.history.json`: the default 3 rows re-ordered newest first, `_kind` added. Task T-2001, Finance Lead, `you_can_act: true` |
| W-1002 | action_needed | matches the list row (Harbour Bank receipt, RCP-0117). `agent.status: "none"`. Task with `required_role: "Finance Officer"`, `you_can_act: false` |
| W-1003 | processing | matches the list row (Delta Foods weekly update). `agent.status: "working"`; steps done, done, current (`status: "working"`), next (`status: "next"`), with `source` on the done steps. Station 3 `current_agent`. `tasks: []` |
| W-1004 | ready | the **A-WORKITEM given** (Lagoon Health invoice approved, not sent): drafted, reviewed and approved `earned` with `at`, sent `not_yet`, receipt_recorded `unknown`, verified `not_yet`. Agent `done`; no step text or status contains approve, approval, send or pay. `next_step` names the send step. History has **12 rows**: at least one return, one approval, one agent draft, one evidence row, one `restricted: true` row (`event: "Restricted"`, no `version`, no `detail`), newest first, each with a `_kind` except the factory "Started the line" row |
| W-1005 | effect_uncertain | sent `unknown`. Station 6 `waiting`. `next_step` from the effect-uncertain board in plain words, no action |
| W-1006 | verified | all six facts earned. Last station `verified`. `agent.status: "done"` |
| W-1099 | (none) | always 404 for item and history |

### Screen states (SCR-02)
- **Loading:** `LoadingState` from `@/shell/FrameStates` in the page body.
- **Error (item):** a work-item error card using the `shell-errorcard` classes with:
  - eyebrow `ERROR · COULDN'T LOAD`;
  - text "We couldn't load this work item. Your work is safe; nothing was changed.";
  - `Reference <code> for support.`;
  - a Try again button that re-fetches.
- **401:** `SignedOutState pathname="/work/<id>"`.
- **No access (403/404):** the SCR-02 permission board.
  - Eyebrow "NO ACCESS".
  - h1 "You can't open this work item".
  - The board's two paragraphs: "It belongs to a project or line you don't have access to. Nothing about it is shown here, not even its name or amount." and "If your work needs it, ask the PMO Lead for access to the project. If someone sent you this link, ask them what they need from you."
  - Link "Back to my queue" to `/my-work`.
  - The id, title or any other item value never appears, and neither does the document title. Page `<title>` is "Work item · PSL Factory".
- **Success (Overview, `/work/[id]`):**
  1. **Breadcrumb** (`psl-crumb`): "My work" (link `/my-work`) / `line` / `reference` (mono).
  2. **h1** `title`, with the CMP-05 state tag on one line. Wording and class:

     | state | wording | class |
     |---|---|---|
     | ready | Ready to continue | person |
     | processing | Processing | agent |
     | waiting | Waiting | waiting |
     | owner_needed | Owner needed | person |
     | setup_needed | Setup needed | person |
     | action_needed | Action needed | person |
     | effect_uncertain | Effect uncertain | waiting |
     | awaiting_reconciliation | Awaiting reconciliation | waiting |
     | verified | Verified | done |
     | cancelled | Cancelled | neutral |
     | followup_needed | Stopped: invoice follow-up needed | person |

  3. **Sub-line** "revision N". A `SAMPLE DATA` label (`psl-sample`) shows whenever `sample` is true, independent of `NEXT_PUBLIC_API_MODE` (INV-SAMPLE).
  4. **Facts strip** (`psl-facts`, a list with an accessible name "Facts"): the six facts in contract order, labelled DRAFTED, REVIEWED, APPROVED, SENT, RECEIPT RECORDED, VERIFIED.
     - earned: `psl-fact--earned` (verified fact when earned: `psl-fact--verified`), showing "Earned" plus `at` when present.
     - current: `psl-fact--current`, "In progress".
     - not_yet: "—" with accessible text "Not yet".
     - unknown: `psl-fact--unknown`, the literal word "Unknown".

     Never blank, never "0", never "No". A missing fact name renders as Unknown. Below the strip: "Paid is a separate Finance fact and is not part of this line."
  5. **Station track** (`psl-track`, ordered list): two-digit number, name, one-line status.
     - done: "Done"
     - current_person: "Needs a person"
     - current_agent: "Agent working"
     - waiting: "Waiting"
     - stopped: "Stopped"
     - not_started: "Not started"
     - verified: "Verified"

     Classes map to `psl-station--done|person|agent|waiting|stopped|todo|verified`. The current station has `aria-current="step"`. Below 720px the stations show as a vertical list with the status on the right, as on the approved mobile boards (design engineer, 14 Nov 2026); the page does not scroll sideways.
  6. **Agent at work** (CMP-09/18), shown when `agent.status` is not `none`:
     - Avatar: `psl-avatar--chidi|tola|zainab` by lower-cased name, otherwise a neutral initial avatar. Name (or "Agent" if absent) and the line "Cannot approve, send or pay."
     - Status tag: WORKING (agent class), DONE (done class), WAITING (waiting class) or STOPPED (person class).
     - When working, "step n of m" is derived from the steps: n is the 1-based index of the first step whose status is not done.
     - Steps map to classes: `done` → done; `working|current|now` → now; `waiting` → wait; `stopped` → stopped; anything else → next.
     - Each step's `source`, when present, appears as "Read: <source>" in `psl-mono`.
     - The current step pulses only under `prefers-reduced-motion: no-preference`.
     - The card contains no button or link labelled or acting as Approve, Send or Pay.

     When `agent.status` is `none`: the text "No agent work on this item."
  7. **Current human task:** one panel per `tasks[]` entry, showing the title and "Only a <required_role> can decide."
     - `you_can_act: true`: add "You are <required_role>." and a link (`psl-btn`) "Open the decision" to `/work/<id>/decide?task=<task id>` (F-04's future route; it may 404 until F-04 lands).
     - `you_can_act: false`: no link and no button.
     - `tasks: []`: the panel is absent.
  8. **Next step:** `next_step` in a CMP-24 callout.
     - Warning for effect_uncertain, awaiting_reconciliation, owner_needed, setup_needed, action_needed and followup_needed.
     - Success for verified.
     - Info otherwise.

     There are no action buttons in any state.
  9. **Tabs** (links in a `nav` labelled "Work item"): Overview (`/work/<id>`) and History (`/work/<id>/history`), with `aria-current="page"` on the current one. No Documents tab and no counts.
- **Success (History, `/work/[id]/history`):** the same header (items 1 to 3) and tabs.
  - **Filter:** segmented control (`psl-seg`, radio semantics) All / Decisions / Agent work / Evidence, sending `kind`.
  - **Rows per page:** a labelled select with 10 / 20 / 50, sending `limit`. Changing the filter or rows-per-page resets to the first page.
  - **Table** (`psl-table` on desktop, stacked rows at 390px):
    - When: day-month and time in Africa/Lagos, e.g. "12 Nov 16:40", with an `<time dateTime>` attribute.
    - Actor-kind tag: PERSON (neutral), AGENT (agent), FACTORY (neutral outline).
    - Actor.
    - What happened: `event`, with `detail` beneath.
    - Version (or "—").
  - **Restricted rows** (`restricted: true`) show when, the actor-kind tag, the actor and the word "Restricted". `event`, `detail` and `version` are never rendered, even if present.
  - **"Show more"** (`psl-showmore`) appears only when `next_cursor` is present. It appends the next page.
  - **Footer:** "As of <as_of in WAT>", plus the board's "About history" text without the CSV link.
  - **Empty:** `psl-empty` with "Nothing recorded for this filter yet."
- **Updates:**
  - While the last item response has `agent.status === "working"` and `document.visibilityState === "visible"`, re-fetch the item every 5000 ms.
  - Stop when the agent is no longer working, the tab is hidden or the page unmounts. Resume on `visibilitychange` back to visible, if still working. Never poll otherwise.
  - A failed poll keeps the last good data on screen and shows a warning callout: "We couldn't refresh this item. Showing what we had at <time WAT>." The next poll tries again.
  - On the history view, when a fetched item `revision` differs from the one the history was loaded for, reload history from the first page with the current filter and limit.
- **Fixture example** (W-1004 facts):
  ```json
  [{"name":"drafted","status":"earned","at":"2026-11-12T09:58:00Z"},{"name":"reviewed","status":"earned","at":"2026-11-12T15:12:00Z"},{"name":"approved","status":"earned","at":"2026-11-12T15:40:00Z"},{"name":"sent","status":"not_yet"},{"name":"receipt_recorded","status":"unknown"},{"name":"verified","status":"not_yet"}]
  ```

### Contract gaps (omitted, for the architecture revision; PMO-0-1, PMO-0-2)
1. Amount with `unknown=true` (A-WORKITEM "unknown amount", INV-UNKNOWN). The schema has no amount field. Only fact-level Unknown is shown.
2. "Started by <person> (<role>) · <date>" in the header.
3. Per-station detail and time ("Done · Mon 14:05", "Approved 10:47", "Waiting 2h · you", "Chidi · working").
4. The state wordings that need the task or line ("Awaiting Finance decision", "Waiting on client", "Approved · ready to send", "Returned by reviewer", "Evidence asked of you", "Agent working"). The generic CMP-05 wording for the contract state is used instead.
5. Agent role ("Finance agent"), the agent task title ("Drafting the invoice"), per-step times, run start time, "Ask <agent>", and alert/next-check times.
6. The decision-panel content on the default board (amount, basis, recipient, version change, note, Approve/Return/Reject); it belongs to F-04 and to E-TASK-* or an extended contract.
7. History filter counts and the tab count; the Documents tab and count; "Download history (CSV)"; "Ask for access" on the permission board (no endpoint).
8. A history entry kind/category field: the mock uses a private `_kind`. The real filter semantics are the backend's.
9. Who "only a <role>" refers to when a decision has separation rules (preparer cannot decide own work): not in `tasks[]`.

## Lanes
- **Frontend lane (F-03 builder) owns:**
  - `frontend/src/app/work/[id]/page.tsx`, `frontend/src/app/work/[id]/history/page.tsx`, and an optional `frontend/src/app/work/[id]/layout.tsx`;
  - `frontend/src/features/work-item/**` (components, hooks, formatters, and a feature stylesheet if needed);
  - `frontend/mock/fixtures/work/**`;
  - `frontend/tests/work-item*.test.ts(x)`;
  - `frontend/e2e/work-item.spec.ts`.
- **Shared files** (minimal, additive edits; the integration owner, who is the coordinator, merges them):
  - `frontend/mock/server.mjs`: F-03 adds only the E-WORK-ITEM and E-WORK-HISTORY selection described above, as a small per-operation handler beside the existing generic path. F-02 adds E-WORK-LIST handling and F-04 the E-TASK-* handling in the same file.
  - `frontend/tests/mock-contract.test.ts`: F-03 appends tests and does not change existing ones.
- **Not touched by F-03:**
  - `frontend/src/app/work/[id]/decide/**` (F-04);
  - `frontend/src/app/my-work/**`, `frontend/src/features/my-work/**` and `E-WORK-LIST.json` (F-02);
  - `E-TASK-*.json` (F-04);
  - `frontend/mock/fixtures/E-WORK-ITEM.json` and `E-WORK-HISTORY.json` (content unchanged);
  - `frontend/src/shell/**`, `frontend/src/api/**` and `frontend/src/styles/**`. Import from them; do not edit them.
  - `architecture/**`, `apps/**` and `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json` (protected).
- **Backend lane:** none.
- **Ports:** app 3201, mock 3202. Run e2e as `E2E_PORT=3201 MOCK_PORT=3202 npx playwright test e2e/work-item.spec.ts`. For local dev: `MOCK_PORT=3202 npm run dev -- -p 3201`.

## Acceptance criteria
1. **W-1004 (A-WORKITEM)** shows the six facts as separate boxes: Drafted, Reviewed and Approved Earned with times; Sent "Not yet"; Receipt recorded "Unknown"; Verified "Not yet". No box is empty or reads 0, and the Paid note is present. — verify: unit test renders the W-1004 fixture and asserts six list items, the exact texts, and no fact text matching `^$|^0$`. Also open http://localhost:3201/work/W-1004 with the mock on 3202 and look.
2. **Unknown or missing facts** always read "Unknown". — verify: unit test with every fact `unknown`, and with a facts array missing `sent`, asserts "Unknown" for each and never "0", "No" or blank.
3. **The state tag** shows the CMP-05 wording and colour class for all 11 states. — verify: a table-driven unit test over the 11 enum values asserts the text and the `psl-tag--*` class from the Contract table.
4. **The station track** shows every station from `stations[]` in order, with number, name and mapped status. The current one has `aria-current="step"`. At 390px the stations are a vertical list with the status on the right and nothing scrolls sideways (design engineer, 14 Nov 2026). — verify: unit test for the 7 status mappings. The e2e at 390px asserts `document.documentElement.scrollWidth <= 390` on /work/W-1001.
5. **The agent card never offers a decision.**
   - W-1003 shows WORKING, "step 3 of 4", sources in mono, and "Cannot approve, send or pay.", with no element whose accessible name matches /approve|send|pay/i other than that sentence.
   - W-1002 shows "No agent work on this item."

   — verify: unit tests on W-1003 and W-1002, querying `getAllByRole('button')` and `getAllByRole('link')` inside the card.
6. **Reduced motion:** the current agent step pulses only when motion is allowed. — verify: the e2e runs with `reducedMotion: 'reduce'` and asserts the current step's computed `animation-name` is `none`.
7. **Decision link only when the person can act:**
   - W-1001 (`you_can_act: true`) shows "Only a Finance Lead can decide.", "You are Finance Lead." and a link "Open the decision" to `/work/W-1001/decide?task=T-2001`.
   - W-1002 (`you_can_act: false`, wrong user) shows "Only a Finance Officer can decide." with no link or button in the task panel.

   — verify: unit tests on both fixtures.
8. **Next step:** `next_step` appears in a callout of the mapped kind. effect_uncertain (W-1005) shows a warning callout and no action button anywhere on the page. — verify: unit test on W-1005 asserting the `psl-callout--warning` class and zero buttons outside the tabs and Try-again controls.
9. **Sample label:** "SAMPLE DATA" shows on the item when `sample: true`, even with `NEXT_PUBLIC_API_MODE=live`. — verify: unit test with the env stubbed to `live`.
10. **No access (403/404):** a 404 or a 403 shows "You can't open this work item" with "Back to my queue" to /my-work. Neither the id nor any title appears. — verify: open http://localhost:3201/work/W-1099 and see the permission view. Unit tests with fetch stubbed to 403 and to 404 assert that the requested id string is absent from `document.body.textContent`.
11. **401:** a 401 on the item shows the shell's signed-out callout with a sign-in link whose `next` is `/work/W-1001`. — verify: unit test.
12. **Server or network error:** shows the work-item error card with "Reference <code> for support." and Try again. Clicking Try again re-fetches and then shows the item. — verify: unit test where the first fetch returns 500 and the second returns 200.
13. **History (A-HISTORY):** /work/W-1004/history lists rows in the order returned (newest first), each with when in WAT, a PERSON/AGENT/FACTORY tag, actor and event. The list includes a return and an approval. — verify: unit test against the W-1004 history fixture asserts the row order equals the fixture order, and that `2026-11-12T15:40:00Z` renders as "12 Nov 16:40".
14. **Restricted history rows:** a restricted row shows only when, the actor-kind tag, the actor and "Restricted". Its event, detail and version strings never appear. — verify: unit test with a restricted item that does carry `event`, `detail` and `version` asserts those strings are absent.
15. **History is read-only:** the history view contains no input or button that edits or deletes an entry. Its only controls are the filter, the rows-per-page select, Show more and Try again. — verify: unit test enumerating the controls.
16. **Filter and paging requests:** choosing "Decisions" sends `kind=decisions&limit=20`. Choosing 10 rows sends `limit=10`. "Show more" sends `cursor=<next_cursor>` and appends rows. Show more is absent when the response has no `next_cursor`. — verify: unit test inspecting the stubbed `fetch` request URLs. In the browser, /work/W-1004/history with 10 rows shows 10 rows, then 12 after Show more, and no Show more after that.
17. **Mock: per-id selection with fallback.**
    - Per-id: GET `/api/v1/work/W-1003` returns W-1003 and `/api/v1/work/W-1099` returns 404.
    - Fallback: GET `/api/v1/work/ANY-OTHER` returns the unchanged `E-WORK-ITEM.json`, and the existing E-WORK-ITEM and E-WORK-HISTORY contract tests still pass.
    - History parameters: `?kind=decisions` returns only decision rows; `?limit=10` returns 10 rows plus `next_cursor`, and following it returns the remaining 2 with no `next_cursor`; `?limit=7` behaves as 20.
    - No response contains `_kind`.

    — verify: new tests in `frontend/tests/mock-contract.test.ts`.
18. **Every fixture is schema-valid:** every file in `frontend/mock/fixtures/work/` (with `_kind` stripped) validates against the v3 E-WORK-ITEM or E-WORK-HISTORY 200 schema. — verify: a new test iterating the directory with the existing Ajv setup.
19. **Polling (D-UPDATES r2):**
    - With W-1003 (agent working) and fake timers, the item is fetched again after 5000 ms.
    - With W-1001 (agent done), no second fetch happens within 30 s.
    - With `visibilityState` hidden, polling stops, and it resumes on visible.
    - A failed poll keeps the item on screen and shows "We couldn't refresh this item."
    - A changed `revision` on the history view triggers one history reload from the first page.

    — verify: unit tests with `vi.useFakeTimers()`.
20. **Accessibility (A-ACCESSIBILITY):** axe reports no WCAG 2.2 AA violations, and keyboard focus shows the focus ring on the tabs, filter and Show more. Pages and states checked:
    - /work/W-1001, /work/W-1003, /work/W-1004/history and /work/W-1099;
    - at 390x844 and 1440x900.

    — verify: `E2E_PORT=3201 MOCK_PORT=3202 npx playwright test e2e/work-item.spec.ts`, following the `frontend/e2e/frame.spec.ts` helpers.
21. **Gate:** `delivery/checks.sh` passes (lint, typecheck, vitest, next build). — verify: the gate run.

## Out of scope
- **Owned by other features:**
  - The decision panel, claim, approve/return/reject, the stale-version reload and anything under `/work/[id]/decide` (F-04). F-03 only links there.
  - The My work list, its polling and its fixtures (F-02).
  - Reconcile, resume, record a response, upload evidence, resend or send actions, and the "See all exceptions" link target (FE-M2 / SCR-10).
- **Not built at all:**
  - The Documents tab, SCR-08 document review, the CSV download, "Ask for access", "Ask Chidi", the notification bell and alerts.
  - Highlighting My work in the top bar for /work routes (shell change; not required by the board).
  - Server-sent events, WebSockets or any push channel; polling lists from this page.
- **Out of bounds for F-03:**
  - Any edit to `openapi.json`, `schema.d.ts`, `src/api/**`, `src/shell/**`, the design tokens or bundle CSS, or the default E-WORK-ITEM / E-WORK-HISTORY fixture contents.
  - Repointing the mock to v3.
  - Any backend, Django, `apps/**` or real-API wiring (FE-CONNECT-1).
  - Inventing amounts, dates, role names, agent roles or per-station times not in the payload.

## Assumptions
- **Route shape:** History is a sub-route `/work/[id]/history` with link tabs rather than client-side tabs. This makes it linkable and leaves `/work/[id]/decide` free for F-04.
- **Decision link:** `/work/<id>/decide?task=<task id>`. F-04's readiness proposes `src/app/work/[id]/decide/**` and a work item can have more than one task. The coordinator confirms with F-04.
- **followup_needed wording** is "Stopped: invoice follow-up needed", the only CMP-05 wording for it. Its class (orange, needs a person) follows CMP-05's colour rule.
- **State colours:** ready, setup_needed and owner_needed are orange; waiting, effect_uncertain and awaiting_reconciliation are amber; processing is blue; verified is green; cancelled is grey. These are taken from the boards' tag tints. action_needed is orange by the "needs a person" rule.
- **Station status texts** ("Needs a person", "Agent working", "Not started", and so on) come from the CMP-02 state names, because the contract carries no per-station detail.
- **Agent step status is a free string:** working, current and now count as current; done, waiting and stopped map directly; anything else counts as still to come. This is the safest reading that never shows an unknown status as done.
- **Agent avatars:** chosen by name (Chidi, Tola, Zainab), with a neutral initial avatar otherwise. The contract has no agent id.
- **Fact "not yet"** is shown as "—" with the accessible text "Not yet", as on the boards. A fact absent from the payload is shown as Unknown (INV-UNKNOWN).
- **403 and 404 render the same permission view** because the board and INV-ACCESS say nothing about the item may be revealed.
- **Times** use the en-GB format in Africa/Lagos (WAT), as the history board states "Times are WAT"; the same format applies to fact `at` and `as_of`.
- **A failed poll** keeps the last good data and shows a warning rather than the full error card, so a brief outage does not hide work the person is reading.
- **Mock design:** history category uses a mock-only `_kind` stripped on output; the mock cursor is an offset string; an invalid limit falls back to 20 and an invalid cursor to the first page. The contract declares no 422 for history, and the typed client cannot send other limits.
- **W-1099 is the reserved no-access id** in the mock. It gives a real 404 path without breaking the fallback other lanes rely on.
- **W-1004 is used for the A-WORKITEM given** with state `ready` ("Ready to continue"), the closest contract state to "approved, ready to send". The contract has no "approved" state.
