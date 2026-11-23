# The work item releases an invoice live, only when the server offers it, and never repeats a release

> Tasks: FE-CONNECT-1. Architecture: v9 package (revision as pinned in the feature record at branch time; the record holds no baseline yet, so the coordinator pins it); contract `contracts/psl-factory.openapi.json` 1.24.0. Design: approved 13 Nov canvas under the recorded exception in `design/review.json` (13 Nov client approval of version 1794581312-b166 covers the invoice states); screens: SCR-02 (work item: ready, processing, awaiting-reconciliation, effect-uncertain, verified, permission).

## Summary
- On a live work item (`/work/{integer id}`), a "Release invoice" button appears in F-87's controls row only when `GET /work/{id}` `actions[]` contains `release_invoice`. Otherwise nothing is drawn: no disabled button, no reason.
- Pressing it (after a plain yes/no confirmation) sends one `POST /api/v1/work/{id}/actions` `{expected_revision, action:'release_invoice'}` through F-85's `CommandDescriptor` and F-87's `useWorkCommand`. A 202 means "release requested", never "released".
- The result is read from the re-read item: the page polls as it does for `state === 'processing'`, and the button stays gone or locked until the server stops offering it or the revision moves.
- After a timeout or 5xx the release is locked with "We couldn't confirm that this happened. Check the page before trying again." No second request is sent by the page; the person uses F-87's "Check what happened" when the server lists `reconcile`.
- The invoice panel (`panels[]` key `invoice`) is read from `GET /projects/{case_id}/billing-invoices/{invoice_id}` and shown as one compact read-only block: reference, version, issued, delivered, amount, paid, owed. A value the API returns as `null` shows "Unknown", never 0.

## Context
Lane C worktree `/Users/Hunchoo/psl-factory-worktrees/lane-c/frontend`.
- Live page: `src/features/work-item/live/LiveWorkItemView.tsx` (`Header`, `Overview`, `PanelView`, which draws each `item.panels[]` through `adapterFor(panel.key)`), `live/useLiveWorkItem.ts` (polling), `live/model.ts`. It holds `item.revision`, `item.case_id`, `item.actions[]`, `item.panels[{key,url,contract_path}]`.
- Adapter: `src/features/workspace/adapter.ts` (`PanelRef`, `LineContext`, `LineAdapter`, `CommandDescriptor`, `makeCommand`, `registerLineAdapter`, `adapterFor`, `readPanel`, `isPanelUrl`). Reference adapter: `src/features/workspace/weeklyReportAdapter.ts`.
- Locking and the controls row: F-87 builds `src/features/workspace/useWorkCommand.ts` (press lock, uncertain lock, a fresh descriptor per attempt, reload on 409, "Check what happened") and `src/features/workspace/workItemCommands.ts` (`workItemCommands(item)`; F-87 explicitly ignores `release_invoice`). This feature adds the release descriptor there and reuses the row, `Callout` and `Dialog`. The v7 `src/features/workspace/useWorkspaceStep.ts` is untouched.
- Errors: `src/api/errors.ts` (`ApiError` kinds `unauthenticated`, `forbidden`, `csrf`, `not_found`, `stale`, `invalid`, `rate_limited`, `read_limited`, `network`, `server`); `call()`, `liveApi`, `refreshSession()` in `src/api/client.ts`.
- Mock: `mock/work-live.mjs` and the mock server routes (F-85/F-87 scenario mechanism).
- Contract 1.24.0 (unchanged from 1.22.0 for these operations):
  - `GET /api/v1/work/{work_id}`: `actions[]` enum `background | reconcile | release_invoice`; `revision` (nullable); `panels[{key,url,contract_path|null}]`; `state` (11 values incl. `processing`, `awaiting_reconciliation`, `effect_uncertain`, `verified`).
  - `POST /api/v1/work/{work_id}/actions` (`operationId work_action`): body `{expected_revision (int 1..2147483647), action: 'reconcile' | 'release_invoice'}`, `additionalProperties:false`; 202 `{work_id, state, revision}`; errors 400, 401, 403 (incl. `csrf_failed`), 404, 405, 409, 413, 415, 422, 429, 500, 503 with `{code, message, fields?}`. There is no idempotency or key field and no amount, recipient or condition field.
  - `GET /api/v1/projects/{case_id}/billing-invoices/{invoice_id}` (`workspaces_billing_invoice`): `{id, reference, version, issued_at|null, delivered_at|null, currency, amount (string), paid|null, owed|null, preparation_id, issue_id|null, delivery_id|null, payments_url|null, corrections_url}`; errors 400, 401, 403, 404, 405, 409, 422, 500, 503.
- Answers: `delivery/connect/backend-answers-2026-11-23.md` section 2 ("Invoice work uses the original draft, review and delivery receipt"; a field stays empty where the source did not record it); `backend-answers.md` A-12 (null is unknown), A-14 (amounts and currency come from the invoice panel). D-185 (build as drawn what 1.24.0 supplies) and D-186 (lane D owns Finance line workspaces).

## Contract

### The release command (descriptor)
Added to `workItemCommands(item)` (F-87's file), one new entry:

| id | label | listed by | url | body | success |
|---|---|---|---|---|---|
| `invoice.release` | Release invoice | `actions[]` has `release_invoice` | `/api/v1/work/{id}/actions` | `{action:'release_invoice', expected_revision}` | 202 |

- Built with `makeCommand`, `keyField` omitted (the body has no key field; `idempotency.field === null`). `expected_revision` is the item's `revision` as loaded, never defaulted, bumped or 0. `case_revision`, an amount, a recipient or any other field is never sent (the schema forbids extra keys).
- F-87's "ignores `release_invoice`" rule is replaced by this entry; its test for that case is changed to expect the new descriptor, and `adopt_profile` stays ignored.
- `disabledReason` (item `revision === null`): "We don't have this item's current version yet. Reload and try again." drawn beside the disabled button; never sent. This is the only time a disabled release button appears.
- A fresh descriptor per attempt; a descriptor that failed with an unknown result is never reused without a re-read in between.

### Send and lock (via F-87's `useWorkCommand`, no new locking code)
- Confirmation first. Pressing "Release invoice" opens the existing `Dialog`: title "Release this invoice?", body "This sends the invoice onward and can't be undone from here.", buttons "Release invoice" and "Keep it". Nothing is sent until the confirm button is pressed. The dialog's confirm is under the same press lock. No amount, recipient or condition line is drawn in the dialog (the server owns them; none is served on this operation).
- Press lock: while the release runs, every control in the row is disabled and a second press sends nothing (a double click makes one request). A poll arriving mid-write does not clear the lock or the notice.
- Success 202: re-read the item (`reload()`), never trust the 202 alone. Show the Callout "Release requested. The invoice is being sent; this page will update." and then the state words from the re-read (`STATE_TAGS`). Never "Released", "Sent" or "Delivered" from the 202.
  - If the re-read still lists `release_invoice` at the same `revision` as the one sent, the release stays locked (button disabled, text "Release requested. Waiting for the server.") until a re-read shows a different `revision` or no longer lists `release_invoice`. The page does not offer the press again on its own.
  - If the re-read fails: "Sent. We couldn't reload the item; reload the page to see its state." and every control stays locked until a read succeeds.
- Polling: the page keeps its existing polling (`state === 'processing'` or `current_activity.watching`). After a 202 the page also polls while `release_invoice` is still listed at the sent revision, at the existing interval, until the lock clears or the page is hidden. Polling only reads.
- Errors (words from `ApiError`; the server's `message` is shown as given for 403 non-csrf, 409 and 422):
  - `unauthenticated` or `not_found`: replace the page with the existing signed-out or "This record is unavailable." state.
  - `forbidden` (403, not csrf): "You can't do this. {server message}", re-read, no retry. The control disappears if the re-read no longer lists the action.
  - `csrf` (403 `csrf_failed`): `refreshSession()` once, say "Press the button again". The release is not auto-resent (see Assumptions).
  - `stale` (409, including `stale_version`, `conflict`, `idempotency_conflict`, `action_unavailable`): re-read, "This changed while you were working. Showing the latest version." plus the server's message when it has one. The press is not repeated; the next press carries the new revision, and only if the re-read still lists `release_invoice`.
  - `invalid` (422, including `setup_required`, `action_unavailable`): show the server's `message` and the first `fields[].message` as given, re-read, no retry. No client-written reason such as "not approved yet".
  - `rate_limited`, 503 `read_limited`: "Try again shortly." Nothing is sent by the page.
  - `network` or `server` (timeout, 5xx, dropped connection): uncertain. Re-read the item, lock `invoice.release`, and say "We couldn't confirm that this happened. Check the page before trying again." The button stays disabled with "Check the page before trying again." beside it. It unlocks only when a re-read shows a different `revision` or no longer lists `release_invoice`, or the person reloads the page (and the server still offers it). There is no retry or "Try again" button on a release. When the item lists `reconcile`, F-87's "Check what happened" is the person's way to settle it.
- A write happens only from a press: no timer, effect, poll or navigation sends a release.

### Invoice panel (read only): `invoiceAdapter`
New `src/features/workspace/invoiceAdapter.ts`, registered with `registerLineAdapter` for `panels[].key === 'invoice'`, next to `weeklyReportAdapter.ts`.
- `read(panel)`: `readPanel` on `panel.url` (accepted only when `isPanelUrl` and it matches `/api/v1/projects/{case_id}/billing-invoices/{invoice_id}`; any other url is not fetched and the block is omitted).
- Drawn by `PanelView` as one panel titled "Invoice", rows in this order, each a label with its value:
  | Label | Source | When the value is missing |
  |---|---|---|
  | Reference | `reference` | always present |
  | Version | `version` shown "v{version}" | always present |
  | Amount | `currency` + `amount` as the server's string, no client arithmetic or rounding | always present |
  | Issued | `issued_at` (existing date formatter) | "Not issued yet" when `null` |
  | Delivered | `delivered_at` | "No delivery recorded" when `null` |
  | Paid | `paid` with `currency` | "Unknown" when `null` |
  | Owed | `owed` with `currency` | "Unknown" when `null` |
- `null` never becomes 0, "None" or a computed difference. Paid and owed are separate facts; "Verified doesn't mean paid" (board, SCR-02 verified) stays in the existing verified note where F-85/F-91 draw it, not here.
- No links to `payments_url` or `corrections_url`, and no payment, correction or reminder control: those are lane D (Finance line workspaces, D-186). `preparation_id`, `issue_id`, `delivery_id` are not shown.
- The block is read again when the item's `revision` changes (existing `PanelView` effect), so it reflects a release after the re-read.
- States: loading (a short "Loading invoice..." line inside the panel), error (404/403 on the panel: the panel is omitted; 429, 503 and network: "Invoice details unavailable. Try again" with the existing retry), empty (no `invoice` panel in `panels[]`: nothing drawn), success (table above).
- The six-facts strip and station track on the boards are F-91's (work item tracking); this feature does not draw them.

### Screen: where the control sits
In `LiveWorkItemView.tsx` `Overview`, F-87's controls row (directly under the header sub-line, above "Why it is stuck") also draws "Release invoice" when `workItemCommands(item)` contains `invoice.release`. Existing `Button`, `kind="primary"`, `size="sm"` is not used: use `kind="secondary"` like the other row buttons so the row stays one style (see LC-Q20). On phone the buttons stack full width. The row, result Callout (role status for results, alert for errors) and dialog are F-87's; this feature adds no new layout.
- Loading: the row is absent until the item has loaded.
- Empty: `release_invoice` not listed: no button, no gap, no text about why.
- Pressing: the pressed button reads "Working..." and all row buttons are disabled.
- Success: Callout "Release requested..." then the new state tag from the re-read.
- Error: Callout with the mapped words; the button is enabled again unless the uncertain lock or the "waiting for the server" lock applies.

### Fixture examples (mock; ids are free numbers, builder adds to `mock/work-live.mjs`)
- `4120` ready to release: `state:'ready'`, `actions:['release_invoice']`, `revision:9`, `case_id:'C-4120'`, `panels:[{key:'invoice', url:'/api/v1/projects/C-4120/billing-invoices/812', contract_path:'/api/v1/projects/{case_id}/billing-invoices/{invoice_id}'}]`. Invoice 812: `{id:812, reference:'INV-0412', version:2, issued_at:null, delivered_at:null, currency:'NGN', amount:'1250000.00', paid:null, owed:null, preparation_id:77, issue_id:null, delivery_id:null, payments_url:null, corrections_url:'/api/v1/work/4120/corrections'}`. Release answers 202 `{work_id:4120, state:'processing', revision:10}`; the next GET returns `state:'processing'`, `actions:[]`, `revision:10`; two polls later `state:'verified'`, `actions:[]`, `revision:11`, and the invoice has `issued_at`, `delivered_at` set and `paid:'0.00'`, `owed:'1250000.00'`.
- `4121` pending after 202: the release answers 202 but the next GET still returns `actions:['release_invoice']` at `revision:9` (exercises "Waiting for the server").
- `4122` null revision: `revision:null`, `actions:['release_invoice']`.
- `4123` not offered: `actions:[]`, same panel (no release button; invoice block drawn with `paid:null`, `owed:null` showing "Unknown").
- `4124` offered together with `reconcile`: `state:'awaiting_reconciliation'`, `actions:['reconcile','release_invoice']`.
- Scenarios (follow the F-85/F-87 mechanism) for the release POST: 403 `forbidden`, 403 `csrf_failed`, 409 `stale_version` (then the GET returns `revision:10` without the action), 422 `setup_required` with a `fields[]` message, 429, 503, 500, dropped connection (after which the GET still shows `revision:9`), and 404.

### Idempotency and versioning
`expected_revision` is the loaded `revision`, and the server's 409 is the only duplicate guard it offers besides the client's locks. Because the body has no key, "a fresh idempotency key per attempt" is met by a fresh descriptor and by the press lock, the "waiting for the server" lock and the uncertain lock, not by a sent key.

### Permission and tenant rules
Who may release, in which state, for which amount, and under what conditions is the server's answer only: the button exists only when `actions[]` lists `release_invoice`, and a 403, 409 or 422 is shown as given. The client has no role check, state rule, amount rule or threshold. Every call uses the loaded item's `work_id`; there is no id input. A 404 on the item or the panel gives the one wording "This record is unavailable." (no existence leak).

## Lanes
- Frontend lane (owner, all of this feature): `frontend/src/features/workspace/workItemCommands.ts` (add `invoice.release`), `frontend/src/features/workspace/invoiceAdapter.ts` (new) and its registration, `frontend/src/features/work-item/live/**` (the dialog and invoice panel wiring only), `frontend/mock/work-live.mjs` and the mock server routes for the release scenarios and the billing-invoice read, tests under `frontend/src/**` and `frontend/e2e/work-item-release-invoice.spec.ts`.
- Backend lane: none. No backend, contract or migration change.
- Integration owner: lane C coordinator. Shared files: `src/features/workspace/*` (lane C owns the frame and adapter; F-85 and F-87 must be merged first and are not rebuilt here; if either is unmerged the builder waits), `src/api/*` (shared, no edits expected), `src/components/*` (used as is), `src/features/response/*` and `useWorkspaceStep.ts` (v7, not touched). Lane D owns every Finance line panel; the `invoice` panel here is the SCR-02 readback only, and lane D may later replace `invoiceAdapter.ts` with a fuller one by the same key.
- Protected paths in `delivery/config.json` stay unchanged.
- Merge: money-moving; the merge goes to the design engineer (D-184). Payments and security reviewers are mandatory.

## Acceptance criteria
1. `/work/4120` (mock) shows a "Release invoice" button; `/work/4123` (`actions:[]`) shows none, no disabled placeholder, no explanation text, no gap — verify: open both pages; `frontend/e2e/work-item-release-invoice.spec.ts` asserts by role and name and the absence in the DOM.
2. Pressing "Release invoice" on `/work/4120` opens the dialog "Release this invoice?" and sends nothing; "Keep it" closes it with no request; confirming sends exactly one `POST /api/v1/work/4120/actions` with body `{"action":"release_invoice","expected_revision":9}` and no other key (no amount, case_revision, key) — verify: e2e counts requests at each step and captures the body; unit test on the `invoice.release` descriptor `body()`.
3. After the 202 the item is re-read and the page shows "Release requested..." and the returned state (processing), never the words "Released", "Sent" or "Delivered" before the re-read shows `verified`; the page then polls and, with the mock moving to `verified`, shows the Verified tag and the invoice block with Issued and Delivered filled — verify: e2e through the `4120` sequence.
4. On `/work/4121` (202 but the item still lists the action at revision 9) the button stays disabled with "Release requested. Waiting for the server." and no second POST is sent however long the page stays open — verify: unit test with fake timers over 60 s counts one POST; e2e.
5. A double click on the confirm button sends one request; while it runs every control in the row is disabled; a poll result arriving mid-write does not clear the lock or the notice — verify: unit test with a deferred POST and fake timers.
6. After a dropped connection or a 500 on the release, the item is re-read, the message "We couldn't confirm that this happened. Check the page before trying again." appears, the button is disabled with "Check the page before trying again.", there is no retry button, and no second request is sent; it unlocks only when a re-read shows a different `revision` or no longer lists `release_invoice` — verify: unit test (no request over 60 s), e2e with the connection-drop scenario, then a mocked revision change.
7. On `/work/4124` the "Check what happened" button remains available after an uncertain release lock, and pressing it sends `{"action":"reconcile","expected_revision":...}`, never a release — verify: e2e request capture.
8. A 409 `stale_version` re-reads the item, shows "This changed while you were working. Showing the latest version.", does not repeat the press, and the button is gone when the re-read no longer lists the action — verify: e2e with the 409 scenario.
9. A 403 `forbidden` shows "You can't do this." with the server's message, re-reads, no retry; a 403 `csrf_failed` is not shown as no-access, refreshes the session once, says "Press the button again" and sends no second POST — verify: unit tests count POST and session calls.
10. A 422 `setup_required` shows the server's `message` as given plus the first field message when present, re-reads, and the page adds no reason of its own — verify: e2e with the 422 scenario; text equals the mock's message.
11. A 429 and a 503 say "Try again shortly." and send nothing further by themselves; a 404 replaces the page with "This record is unavailable."; a 401 shows the signed-out state with a link to `/sign-in?next=` the current path — verify: unit tests with a mocked client and 30 s of fake time.
12. `/work/4122` (null `revision`) draws the button disabled with "We don't have this item's current version yet. Reload and try again."; pressing sends no request; no body contains 0 or null for `expected_revision` — verify: e2e and unit test.
13. The release button never appears from anything but `actions[]`: a mock item with state `ready` and `actions:[]`, and one with `available_control:['resume']` and no `actions`, show no release button; `release_invoice` listed makes it appear whatever the state or role words — verify: unit test on `workItemCommands` with those inputs.
14. The `invoice` panel on `/work/4120` shows Reference "INV-0412", "v2", Amount "NGN 1250000.00" exactly as served, Issued "Not issued yet", Delivered "No delivery recorded", Paid "Unknown", Owed "Unknown"; none of these shows 0, "0.00" or a computed value when the server sent `null` — verify: component test with the fixture; e2e on `/work/4123`.
15. A panel `url` that is not a `/api/v1/projects/{case_id}/billing-invoices/{id}` path is not fetched and the block is omitted; an `invoice` panel returning 404 omits the block and leaves the release control (when offered) working — verify: unit tests on `invoiceAdapter` and `PanelView`.
16. No write is made by page load, polling or navigation: the only `POST .../actions` with `release_invoice` comes from the dialog confirm — verify: `grep -rn "release_invoice" frontend/src` shows only the descriptor, tests and mock; e2e asserts zero POSTs on load and after polling.
17. v7 and the other F-85/F-87 behaviour is unchanged: `useWorkspaceStep` tests, `/work/W-xxxx` pages, F-87's controls (reconcile, resume, cancel, background) and their tests pass, apart from the one F-87 test updated for `release_invoice` — verify: `npm test`, `frontend/e2e/workspace.spec.ts`, `work-item.spec.ts`, F-87's e2e.
18. New unit tests exist for `invoice.release` (id, url, body, null-token hold), the locking cases in criteria 4, 5 and 6, and `invoiceAdapter` — verify: `npm test` lists them.
19. Against live Django (8020, Postgres 55433, account live-lead or the account holding Finance authority), on an item whose `GET /api/v1/work/{id}` lists `release_invoice`, confirming sends 202 and the page then shows the state `GET` returns; a person for whom the API does not list it sees no button; a 403 or 422 from the live server appears as the server wrote it — verify: compare the page with `python3 /Users/Hunchoo/psl-factory-main/delivery/connect/oa.py live GET /api/v1/work/{id} 3` before and after; record the 202 JSON. If no local item lists the action, record that and verify by the mock only; do not create or change records to force it.
20. Viewport check at 1440 and 390: the controls row with "Release invoice", its dialog and the invoice block have no overlap; the row stacks full width on the phone; no empty gap when absent — verify: screenshots against the SCR-02 artboards for the parts that remain.
21. `npm run lint`, `npm run typecheck` and `npm test` pass; `api-live-schema-drift.test.ts` still passes against 1.24.0 — verify: `delivery/checks.sh`.

## Out of scope
- The Finance line workspaces (lane D, D-186): payments, short payment, reminders, corrections, invoice preparation, draft stop, milestone proof, invoice information requests; `payments_url` and `corrections_url` links.
- Weekly report correct and review (F-89); reconcile and the other F-87 controls (only their coexistence is tested here); `background`, resume, cancel, `adopt_profile`; coordination retry; access request.
- Any amount, recipient, threshold, approver or "ready because..." rule decided or displayed by the client; a client-side amount line in the confirm; a retry or "Try again" button on an uncertain release.
- The six-facts strip, station track and tracking history (F-91); delivery observations (`delivery-observations`, the "Confirm what happened" choices on the awaiting-reconciliation board).
- Any backend, contract or migration change; any new endpoint or page.

## Assumptions
- No key field exists on the action body, so duplicate protection is the locks plus `expected_revision`. Reason: the 1.24.0 body is `additionalProperties:false`.
- A 202 is "release requested", never "released". Reason: the response carries only `{work_id, state, revision}`; success is read from the re-read item and later `verified`.
- After `csrf_failed` the release is not auto-resent even if the shared frame resends other writes once (D-185 A-3). Reason: this is the only money-moving action, so a second send needs a person's press.
- The release stays locked after a 202 while the re-read still lists the action at the sent revision. Reason: nothing else tells the page whether the first request took effect.
- "Reconciled" for an uncertain release means a changed `revision` or the server no longer listing `release_invoice`, as F-87 defines it; a page reload also clears the in-memory lock and the server then decides what to offer (see LC-Q22).
- The confirmation dialog wording ("Release this invoice?") is mine and carries no amount. Reason: it is irreversible, no board draws it, and readiness forbids a client-side amount line (LC-Q20).
- The invoice block shows the server's `amount`, `paid` and `owed` strings unchanged with `currency`. Reason: no arithmetic or formatting rule is documented; formatting could change money values.
- The panel title "Invoice" and the missing-value words ("Not issued yet", "No delivery recorded", "Unknown") are mine; the "Unknown" wording follows the boards' "Unknown, never No".
- Release button style is `secondary` like the other row buttons. Reason: avoid inventing an emphasis the boards do not draw.

## Conflicts with the boards
Entered in `delivery/connect/questions-batch.md` under "## Lane C" as LC-Q20, LC-Q21 and LC-Q22; recommendations first.
1. No SCR-02 board draws a "Release invoice" button or its confirmation (the ready board has no invoice; verified and awaiting-reconciliation boards show invoices already issued). This spec adds the button to F-87's controls row and a plain confirm dialog, only when the server lists the action. Recommendation: LC-Q20 option 1.
2. The verified, effect-uncertain and awaiting-reconciliation boards show the invoice through the six facts and numbered steps (Issue, Deliver) which are F-91's. This spec adds one compact "Invoice" block that no board draws as such, because 1.24.0 serves the readback and the facts strip is not part of this feature. Recommendation: LC-Q21 option 1.
3. The effect-uncertain board's "Sent at 11:02 · no reply", "Checked 2 times; next at 11:10" and the awaiting-reconciliation "Confirm what happened" choices are not drawn here (reconcile is F-87; observations are another feature).
4. A release locked after an uncertain result survives only until reload; whether it should survive reload is LC-Q22.
