# The work item can check what happened, resume or cancel, and pause or continue background work, live

> Tasks: FE-CONNECT-1. Architecture: v9 package (revision as pinned in the feature record at branch time); contract `contracts/psl-factory.openapi.json` 1.22.0. Design: approved 13 Nov canvas under the recorded exception in `design/review.json` (delivery may continue on the current design version); screens: SCR-02 (work item, states awaiting-reconciliation, effect-uncertain, cancelled, processing).

## Summary
- On a live work item (`/work/{integer id}`) a small row of buttons appears under the header, one per control the API lists for this person: "Check what happened" (`actions[]` has `reconcile`), "Resume" and "Cancel" (`available_control[]`), "Pause background work" and "Continue background work" (`actions[]` has `background`). A control the API does not list is not drawn.
- "Check what happened" sends only `{expected_revision, action:'reconcile'}` (202), then re-reads the item and shows the state that comes back. No delivered / not delivered choice, no proof, no outcome panel (D-182, LC-Q2).
- Resume and Cancel send `POST /work/{id}/control` (200). Cancel asks a yes/no first because it is hard to undo. `adopt_profile` is not built.
- Pause and Continue send `POST /work/{id}/background` `{expected_revision, enabled}` (202).
- All five go through F-85's `CommandDescriptor` and a press lock, an uncertain lock after a timeout or 5xx, a fresh descriptor per attempt, and a reload on 409. A `null` revision holds the write and says why. The server decides who may act; its 403 and 409 are shown as given.

## Context
Lane C worktree `/Users/Hunchoo/psl-factory-worktrees/lane-c/frontend`.
- Live page: `src/features/work-item/live/LiveWorkItemView.tsx` (`Header`, `Overview`, `PanelView`), `live/useLiveWorkItem.ts` (`state`, `retry`; polling while `needsPolling`), `live/model.ts`. It already holds `item.revision`, `item.case_revision` (nullable), `item.actions[]` and `item.available_control[]` from `GET /work/{id}`, and draws no write today.
- Adapter: `src/features/workspace/adapter.ts` has `CommandDescriptor`, `makeCommand(spec)` (a fresh uuid per call when a key field is set) and `CommandTokens`. `makeCommand` always puts `action` in the body.
- Locking: `src/features/workspace/useWorkspaceStep.ts` (v7 `POST /work/{id}/steps`): one write at a time via a synchronous `writing` ref, a press lock, an uncertain lock after a network or server failure, a fresh idempotency key per attempt, a reload on 409. It is typed to v7 and only the v7 item uses it. It must keep working for `W-xxxx` ids.
- Errors: `src/api/errors.ts` (`ApiError` with `kind` and `fields`; kinds `unauthenticated`, `forbidden`, `csrf`, `not_found`, `stale`, `invalid`, `rate_limited`, `read_limited`, `network`, `server`); `call()` and `liveApi` in `src/api/client.ts`.
- Old v7 reconcile UI (`src/features/response/ReconcilePanel.tsx`, used from `WorkItemOverview.tsx` and `Workspace.tsx`) stays for `W-xxxx` ids and is not touched.
- Mock: `mock/work-live.mjs` currently serves `actions: []`, `available_control: []`.
- Contract 1.22.0:
  - `POST /api/v1/work/{work_id}/actions` body `{expected_revision (int 1..2147483647), action: 'reconcile' | 'release_invoice'}`, `additionalProperties:false`; 202 `{work_id, state, revision}`.
  - `POST /api/v1/work/{work_id}/control` body `{expected_revision, action: 'cancel' | 'resume'}` or `{..., action:'adopt_profile', configuration_id, reason}`; 200 `{work_id, state, revision}`.
  - `POST /api/v1/work/{work_id}/background` body `{expected_revision, enabled: boolean}`, no `action` field; 202 `{work_id, state, revision}`.
  - None of the three bodies has an idempotency or key field. Errors on all: 400, 401, 403 (incl. `csrf_failed`), 404, 409, 413, 415, 422, 429, 500, 503 with `{code, message, fields?}`.

## Contract

### Commands (descriptors)
New file `src/features/workspace/workItemCommands.ts` exports `workItemCommands(item: LiveWorkItem): CommandDescriptor[]`, one per listed control. Each uses `makeCommand`, with `keyField` omitted (no key field exists on these bodies, so `idempotency.field === null` and the body has no key). Tokens are copied from the item as given; a `null` stays `null`.

| id | label | listed by | url | body | success |
|---|---|---|---|---|---|
| `work.reconcile` | Check what happened | `actions[]` has `reconcile` | `/api/v1/work/{id}/actions` | `{action:'reconcile', expected_revision}` | 202 |
| `work.resume` | Resume | `available_control[]` has `resume` | `/api/v1/work/{id}/control` | `{action:'resume', expected_revision}` | 200 |
| `work.cancel` | Cancel | `available_control[]` has `cancel` | `/api/v1/work/{id}/control` | `{action:'cancel', expected_revision}` | 200 |
| `work.background.pause` | Pause background work | `actions[]` has `background` | `/api/v1/work/{id}/background` | `{expected_revision, enabled:false}` | 202 |
| `work.background.continue` | Continue background work | `actions[]` has `background` | `/api/v1/work/{id}/background` | `{expected_revision, enabled:true}` | 202 |

- `makeCommand` gains one optional spec field so the background body carries no `action` (for example `action: null`). Existing callers and `adapter.test.ts` stay unchanged.
- `case_revision` is not sent: it is not in any of the three bodies (schema forbids extra keys).
- `adopt_profile`, `release_invoice` and every other action are never built: `workItemCommands` ignores them even when listed.
- `disabledReason`: set to "We don't have this item's current version yet. Reload and try again." when `item.revision === null`; never invented otherwise. A command with a `disabledReason` is drawn disabled with that text beside it (not as a tooltip only) and is never sent.

### Send and lock: `useWorkCommand`
New `src/features/workspace/useWorkCommand.ts`, used by the live page. It takes `{ item, reload }` where `reload()` re-reads `GET /work/{id}` and returns the new item or null.
- Share the locking with `useWorkspaceStep`: the synchronous `writing` ref, the one-write-at-a-time rule, and the uncertain lock are factored into a small shared piece used by both hooks. `useWorkspaceStep` behaviour and its tests do not change.
- Press lock: while one command runs, every control in the row is disabled and a second press sends nothing (a double click makes one request).
- Request: `liveApi.POST(url, { body: descriptor.body(inputs) })` through the shared client, which adds `X-CSRFToken`. A new descriptor (so any key, were there one) is made for each attempt; a manual Try again after an uncertain failure never reuses a descriptor that failed with an unknown result without a reload in between.
- Success (the status in `successStatuses`): re-read the item, then tell the result from the re-read, never from the 202/200 alone: "Done." plus the new state tag from the re-read item. Reconcile says "Checked. This item is now: {state tag words}." using the reloaded `state` and `status_label`. If the re-read fails, say "Sent. We couldn't reload the item; reload the page to see its state." and keep every control locked until a read succeeds.
- Errors (words come from `ApiError`; the server's `message` is shown for 403 non-csrf, 409 and 422 as given):
  - `unauthenticated` or `not_found`: replace the page with the existing signed-out or "This record is unavailable." state (same as a failed read).
  - `forbidden` (403, not csrf): show "You can't do this. {server message}", re-read, no retry.
  - `csrf` (403 `csrf_failed`): refresh the session once (`refreshSession()`), say "Press the button again". No automatic second send.
  - `stale` (409): re-read the item, say "This changed while you were working. Showing the latest version." and keep the new item; the press is not repeated. Applies to the server's `stale_version`, `conflict`, `idempotency_conflict` and `action_unavailable`-style 409s alike; show the server's own message under it when it has one.
  - `invalid` (422, incl. `setup_required`, `action_unavailable`): show the server's `message` and the first `fields[].message` as given; no retry. The item is re-read.
  - `rate_limited`, 503 `read_limited`: "Try again shortly." No automatic retry.
  - `network` or `server` (timeout, 5xx, dropped connection): uncertain. For `work.resume`, `work.cancel` and the two background commands: re-read the item; lock that command and say "We couldn't confirm that this happened. Check the page before trying again." The command unlocks only when the re-read shows a different `revision` than the one that was sent, or after the person reloads the page. For `work.reconcile` the same message is shown, but it is not locked (it is a lookup and sends nothing to the client); the person may press it again after the re-read.
- Null token: if `item.revision` is `null`, no request is made and the command shows its `disabledReason`.
- Never any timer, effect or loop that sends: a write happens only from a press.

### Screen: the control row
In `LiveWorkItemView.tsx` `Overview`, a "Controls" row sits directly under the header sub-line (above "Why it is stuck"), drawn only when `workItemCommands(item)` is non-empty. It uses the existing `Button` (`kind="secondary"`, `size="sm"`); Cancel uses the existing danger/dark variant if one exists in `Button.tsx`, else `secondary`. On phone the buttons stack full width. No heading text is drawn above the row.
- Cancel opens the existing `Dialog` with: title "Cancel this work?", body "This stops the work. It can't be started again from here.", buttons "Cancel this work" and "Keep it". Nothing is sent until "Cancel this work" is pressed. The dialog's confirm is also under the press lock.
- Result and error text appears in one `Callout` (role status for success, alert for errors) directly under the row, replaced by the next result, cleared when a new press starts.
- Polling: the page keeps its existing polling; while a command runs, a poll result that arrives does not clear the lock or the notice.

States of the row:
- Loading: the row is absent until the item has loaded (no skeleton).
- Empty: `actions` and `available_control` contain none of the five: no row, no heading, no gap.
- Pressing: pressed button shows "Working..." and all buttons are disabled.
- Success: Callout with the result words above, new state tag from the re-read.
- Error: Callout with the mapped words above; buttons enabled again unless an uncertain lock applies, in which case the locked button is disabled with the sentence "Check the page before trying again." beside it.

### Fixture examples (mock; builder adds to `mock/work-live.mjs`, ids are free numbers)
- `4107` awaiting reconciliation: `state:'awaiting_reconciliation'`, `actions:['reconcile']`, `revision:5`. Reconcile answers 202 `{work_id:4107, state:'awaiting_reconciliation', revision:6}`; a header or scenario switch gives the other outcome `{state:'ready'}`.
- `4108` stopped: `state:'action_needed'`, `available_control:['resume','cancel']`, `revision:3`. Resume answers 200 `{state:'ready', revision:4}`; Cancel answers 200 `{state:'cancelled', revision:4}`.
- `4109` processing with background: `state:'processing'`, `actions:['background']`, `revision:7`. Both enabled values answer 202 with `revision:8`.
- `4110` null revision: `revision:null`, `actions:['reconcile']`, `available_control:['cancel']`.
- `4111` nothing listed: both arrays empty (same as today's `4101`).
- Scenarios the mock supports for each write (follow the existing F-85 scenario mechanism): 403 `forbidden`, 403 `csrf_failed`, 409 `stale_version` (then the GET returns a higher revision), 422 `setup_required`, 429, 503, a 500 and a dropped connection.

### Idempotency and versioning
- `expected_revision` is the item's `revision` as loaded, sent as given. It is never defaulted, bumped or 0. The three bodies carry no key field; duplicate presses are prevented by the press lock, the uncertain lock and the revision check, not by a key (see Assumptions).
- After every success the item is re-read, so the next press carries the new `revision`.

### Permission and tenant rules
- Whether a person may reconcile, resume, cancel or change background work is the server's answer: the buttons are shown only when the API lists them for this person, and a 403 or 409 is shown as given. The client has no role check and no rule about which state allows which control.
- Every call uses the `work_id` of the loaded item only; there is no input for an id. A 404 gives the existing one-wording "This record is unavailable."

## Lanes
- Frontend lane (owner, all of this feature): `frontend/src/features/work-item/live/**`, `frontend/src/features/workspace/workItemCommands.ts`, `workspace/useWorkCommand.ts`, `workspace/adapter.ts` (additive `makeCommand` change only), the shared locking piece extracted from `workspace/useWorkspaceStep.ts` (behaviour unchanged), `frontend/mock/work-live.mjs` and the mock server routes for the three writes, tests under `frontend/src/**` and `frontend/e2e/work-item-controls.spec.ts`.
- Backend lane: none. No backend, contract or migration change. Backend questions LC-7 and LC-8 are in `delivery/connect/backend-questions.md`.
- Integration owner: lane C coordinator. Shared files and who owns them: `src/features/workspace/*` (lane C owns the frame and adapter; the change here is additive and lands after F-85 merges, with other lanes rebasing via `git merge origin/main`), `src/api/*` (shared; no edits expected), `src/components/*` (used as is), `src/features/response/*` (v7 reconcile; not touched).
- Build order: F-85 must be merged first (this spec builds on its `CommandDescriptor`, `makeCommand`, `LiveWorkItemView`).
- Protected paths in `delivery/config.json` stay unchanged.

## Acceptance criteria
1. `/work/4107` (mock) shows a "Check what happened" button and no Resume, Cancel or background button; `/work/4111` shows no controls row, no heading and no empty gap — verify: open both pages; `frontend/e2e/work-item-controls.spec.ts` asserts the buttons by name and the absence of the row.
2. Pressing "Check what happened" sends exactly one `POST /api/v1/work/4107/actions` with body `{"action":"reconcile","expected_revision":5}`: no `outcome`, no `evidence_id`, no `case_revision`, no key — verify: e2e captures the request body; unit test on `workItemCommands`.
3. After the 202 the item is re-read and the page shows the returned state: with the mock returning `ready` the tag reads "Ready" and the Callout reads "Checked. This item is now: Ready."; with `awaiting_reconciliation` the tag stays and the Callout says so. No outcome panel, no delivered / not delivered choice and no proof upload appears anywhere — verify: e2e on both mock outcomes; DOM has no radio or file input.
4. If the re-read after a 202 fails, the page says "Sent. We couldn't reload the item; reload the page to see its state." and all controls stay disabled — verify: unit test of `useWorkCommand` with a failing reload.
5. `/work/4108` shows Resume and Cancel. Resume sends one `POST /api/v1/work/4108/control` `{"action":"resume","expected_revision":3}`; after the 200 and re-read the tag shows the new state — verify: e2e with request capture.
6. Pressing Cancel opens the dialog "Cancel this work?" and sends nothing; "Keep it" closes it with no request; "Cancel this work" sends one `POST .../control` `{"action":"cancel","expected_revision":3}` and the re-read shows "Cancelled" — verify: e2e counts requests at each step.
7. `/work/4109` shows "Pause background work" and "Continue background work". Pause sends `{"expected_revision":7,"enabled":false}` and Continue `{"expected_revision":7,"enabled":true}` to `POST /api/v1/work/4109/background`, and neither body has an `action` key — verify: e2e request capture; unit test on the descriptor `body()` output.
8. `adopt_profile` and `release_invoice` are never drawn or sent, even when the mock lists them in `available_control` or `actions` — verify: unit test on `workItemCommands` with those values listed.
9. A double click on any button sends one request; while a command runs every control in the row is disabled; a poll result arriving mid-write does not clear the lock or the notice — verify: unit test with fake timers and a deferred POST; e2e counts requests.
10. `/work/4110` (null `revision`) draws the buttons disabled with "We don't have this item's current version yet. Reload and try again."; pressing sends no request; no body contains 0 or null for `expected_revision` — verify: e2e and unit test.
11. A 409 `stale_version` re-reads the item (revision now higher), shows "This changed while you were working. Showing the latest version.", does not repeat the press, and the next press carries the new revision — verify: e2e with the 409 scenario, request capture of both presses.
12. A 403 `forbidden` shows "You can't do this." with the server message and re-reads, with no retry; a 403 `csrf_failed` does not show "no access", refreshes the session once and says "Press the button again", with no second send — verify: unit tests count POST and session calls; e2e on the forbidden scenario.
13. A 422 `setup_required` shows the server's `message` as given and the first field message when present; the item is re-read — verify: e2e with the 422 scenario.
14. A 429 and a 503 each say "Try again shortly." and send nothing further by themselves — verify: unit test counts requests over 30 s of fake time.
15. After a dropped connection or 500 on Resume, Cancel or a background command the item is re-read, the message "We couldn't confirm that this happened. Check the page before trying again." appears, that button is disabled with the sentence "Check the page before trying again.", and no second request is sent by the page; it unlocks only when a re-read shows a different `revision` or the page is reloaded — verify: unit test with fake timers (no request over 60 s); e2e drops the connection.
16. After a dropped connection or 500 on "Check what happened" the same message shows, the button stays enabled, and nothing is sent until the person presses again — verify: unit test.
17. A 404 on a write replaces the page with "This record is unavailable."; a 401 shows the signed-out state with a link to `/sign-in?next=` the current path — verify: unit tests with a mocked client.
18. No write is made by page load, polling or navigation: the only POSTs to `/work/{id}/actions`, `/control` and `/background` come from a press — verify: `grep -rn "liveApi.POST" frontend/src/features/work-item frontend/src/features/workspace` shows them only in `useWorkCommand` (plus F-85's existing upload and proposal calls); e2e asserts zero POSTs on load.
19. The v7 item path is unchanged: `useWorkspaceStep` tests still pass and `/work/W-xxxx` pages (including `ReconcilePanel`) behave as before — verify: `npm test` and `frontend/e2e/workspace.spec.ts`, `work-item.spec.ts` pass without edits.
20. `workItemCommands` and `useWorkCommand` have unit tests for the table in Contract: ids, urls, bodies, null-token hold, and the locking cases in criteria 9, 15 and 16 — verify: `npm test` lists them.
21. Against live Django (8020, Postgres 55433, account live-lead), on an item whose `GET /api/v1/work/{id}` lists `reconcile`, pressing "Check what happened" returns 202 and the page then shows the state `GET` returns; a person for whom the API lists no controls sees no row — verify: compare the page with `oa.py live GET /api/v1/work/{id} 3` before and after; record the JSON of the 202.
22. Viewport check at 1440 and 390: the controls row has no overlap, stacks full width on the phone, shows no empty gap when absent, and the Cancel dialog fits at 390 — verify: screenshots against the SCR-02 artboards for the parts that remain.
23. `npm run lint`, `npm run typecheck` and `npm test` pass; `api-live-schema-drift.test.ts` still passes — verify: `delivery/checks.sh`.

## Out of scope
- Release invoice (F-90), weekly-report `correct` and `/reviews` (F-89), invoice information requests, milestone proof, draft stop, corrections, coordination retry, `adopt_profile`, access request.
- A delivered / not delivered / unknown choice, any proof or file on reconcile, an outcome-and-proof panel, checks-made or "sent at" facts (LC-Q2, backend LC-8).
- Deciding in the client which state allows which control, who may act, how many checks, or when to remind; deriving whether background work is running (backend LC-7).
- Any new endpoint, new page, new state or new copy beyond what is written above; any change to the v7 `ReconcilePanel` or the `W-xxxx` pages; backend, migrations, contract edits.
- Reasons or notes on Cancel (the contract has none for cancel/resume).

## Assumptions
- No key field exists on the three bodies, so "a fresh key per attempt" is met by building a new descriptor per attempt and by the locks and revision check, not by a sent key. Reason: contract 1.22.0 bodies are `additionalProperties:false`.
- Background Pause and Continue are both shown whenever `background` is listed, because the page cannot read the current setting. Reason: no field serves it (LC-Q13, backend LC-7).
- Reconcile is not locked after an uncertain failure; Resume, Cancel and background are. Reason: reconcile is a backend lookup that sends nothing to the client; the others change the item.
- The client adds no rule about which state allows which control (for example no extra lock while `awaiting_reconciliation`). Reason: the API lists what the person may do; the server answers 409/422 otherwise.
- "Unlocks when the re-read shows a different `revision`" is the meaning of "reconciled" for resume, cancel and background. Reason: the backend returns no reconcile token for these; a changed revision is the only readable proof that the item moved.
- Cancel confirmation wording ("Cancel this work?") is mine. Reason: it is a hard-to-undo action and no board draws it (LC-Q12).
- The new state words come from the existing `STATE_TAGS`; the success line quotes them rather than composing outcome sentences. Reason: no outcome text is served.

## Conflicts with the boards
Entered in `delivery/connect/questions-batch.md` under "## Lane C" as LC-Q12 and LC-Q13; recommendations first below. The design approval rests on the recorded exception, so the design engineer decides these once before build.
1. The awaiting-reconciliation board (SCR-02-desktop-awaiting-reconciliation) draws a "Confirm what happened" panel with "It arrived", "It didn't arrive", "I can't tell yet", proof upload and "Record and continue". This spec replaces it with one "Check what happened" button and no panel. Already decided by D-182 (LC-Q2); recorded so the design engineer knows the board is not matched.
2. No approved board draws Resume, Cancel or Pause/Continue buttons on SCR-02 (the cancelled board shows the result only). This spec adds a controls row under the header, shown only for listed controls, plus a Cancel confirmation dialog. Recommendation: LC-Q12 option 1 (the row, as written here).
3. Pause and Continue are two buttons because live does not say which applies. Recommendation: LC-Q13 option 1.
4. The effect-uncertain board's "Checked 2 times; next check at 11:10" and "Sent at" facts have no live source and are not drawn (same as F-85's hidden parts).

## Coordinator note (lane C, 23 Nov): F-85 low findings carried into F-87
F-85 passed every review with non-blocking findings. F-87 fixes these first, in its own commit, because it already changes `makeCommand` and the work item header:
- TECH-1-1: `body()` spreads `inputs` last, so an input could override `action`, the revision tokens or the idempotency key. Make the descriptor's own fields win (spread inputs first) and test it.
- SEC-1-1: `output_url` is put in an anchor `href` with no scheme check. Allow only http(s) or a same-origin path; otherwise show no link.
- UI low: the breadcrumb shows raw identifiers such as WEEKLY_REPORT; show the line's plain name (from `GET /lines` or the line label map), never the key.
- UI low: the state tag is not right-aligned as on the SCR-02 board.
- TECH-1-2 (history evidence id as text) and the UX lows in delivery/features/F-85/round-1/review-ux.md: fix if small, otherwise list them in build.md.
