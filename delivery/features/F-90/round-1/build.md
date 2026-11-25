STATUS: READY
COMMIT: feea1df154f33ef6d7a50de6733928196b4b195c
BUILDER: builder
LANE: full

## Summary
- "Release invoice" joins F-87's controls row only when `actions[]` lists `release_invoice`; otherwise nothing is drawn (no disabled button, no reason, no row).
- Pressing it opens a plain yes/no dialog ("Release this invoice?" / "Keep it"); confirming sends one `POST /api/v1/work/{id}/actions` `{action:'release_invoice', expected_revision}` and nothing else. A 202 reads "Release requested...", never "released"; the result is read from the re-read item.
- Locks: press lock (double click = one POST), a "waiting for the server" lock after a 202 while the item still lists the action at the sent revision, and an uncertain lock after a timeout/5xx. All are held until the revision moves or the server stops listing the action, and they survive a reload (LC-Q22, option 1). The page never sends a second request on its own.
- A read-only "Invoice" block (reference, version, amount, issued, delivered, paid, owed). Null paid/owed read "Unknown", never 0; no arithmetic and no links.
- Live Django was not exercised (no write allowed, and shapes were checked against the contract with ajv on the mock). AC 19 is mock-only.

## Changes
- `src/features/workspace/workItemCommands.ts`: adds `invoice.release` (`action:'release_invoice'` passed by name, no key field, `expected_revision` as loaded; a null revision keeps the "no version" hold).
- `src/features/workspace/useWorkCommand.ts`: `run()` now returns `'sent' | 'refused' | 'unknown' | 'skipped'` (additive; no other behaviour changed). The release needs it to know whether to keep its mark.
- `src/features/work-item/live/releaseMark.ts` (new): per-work-item mark in localStorage (written BEFORE the request, with an in-memory copy), `heldMark(item)`, `useReleaseMark`. An unreadable mark holds the release. It applies only while the item lists the action at the marked revision.
- `src/features/work-item/live/ItemControls.tsx`: release button, dialog, mark handling, reasons beside the button ("Release requested. Waiting for the server." / "Check the page before trying again."), error callout still drawn when the action is gone after a 409 or 403.
- `src/features/work-item/live/model.ts`: `needsPolling` also true while a release mark holds (reads only).
- `src/features/workspace/invoiceAdapter.ts` (new) and one import line in `lines/index.ts`; `LiveInvoice` type in `src/api/types.ts`. Only `/api/v1/projects/{case_id}/billing-invoices/{n}` urls are fetched (dot segments, extra segments, queries, `//`, absolute and encoded forms refused); 404/403 omit the block.
- `mock/invoice-release-live.mjs` (new), registered in `mock/server.mjs` (route and reset).
- Tests: `tests/invoice-release.test.tsx` (50), `e2e/work-item-release-invoice.spec.ts` (desktop 1440 and phone 390).
- Updated shared tests: `tests/work-commands.test.tsx` (the F-87 "release_invoice is ignored" case now expects the new descriptor; 4123 is no longer a no-row item; a type fix for the new `run` return), `tests/rfp-submission.test.tsx` (the word "Delivered" is banned in src except an allow-list; `invoiceAdapter.ts` added, with the reason, because the invoice's own "Delivered" row names the server's `delivered_at`).

## Fixes
None (round 1).

## Acceptance criteria
1. [x] 4140 shows the button; 4143 shows none, no row, no words: unit test and e2e by role/name and absence.
2. [x] Dialog sends nothing; "Keep it" no request; confirm sends exactly `{"action":"release_invoice","expected_revision":9}`: unit and e2e capture; descriptor test (two keys only, inputs cannot add amount or recipient).
3. [x] After 202 the item is re-read; toast "Release requested..." then Processing; never "Released/Sent/Delivered"; polling reaches Verified and the invoice shows issued/delivered: unit (fake timers) and e2e.
4. [x] 4141 stays disabled with "Release requested. Waiting for the server."; 60 s of fake time and 11 s e2e send one POST.
5. [x] Double click = one POST; row disabled while it runs; mid-write poll keeps the lock: unit (deferred POST).
6. [x] Dropped connection, 500, and 503 (non read_limited): words shown, button disabled with "Check the page before trying again.", no retry button, no second POST in 60 s; reload keeps it locked; unlocks on a changed revision or the action gone: unit and e2e.
7. [x] 4144: "Check what happened" stays and sends a reconcile, never a release: unit and e2e.
8. [x] 409 stale_version: re-read, "This changed while you were working. Showing the latest version.", button gone, no repeat.
9. [x] 403: "You can't do this." plus server message; csrf_failed: one session refresh, "Press the button again.", one POST, button usable again.
10. [x] 422 setup_required: server message plus first field message as given.
11. [x] 429 and read_limited say "Try again shortly." with no further sends over 30 s; 404 shows "This record is unavailable."; 401 shows signed-out with `/sign-in?next=`.
12. [x] 4142 null revision: disabled with the reason, no dialog, no request; body keeps null (descriptor test).
13. [x] Only `actions[]` builds it (ready with `actions:[]`, `available_control:['resume']`, role words).
14. [x] Invoice block on 4140 and 4143 as served; "Unknown" for null paid/owed; no `0.00` shown.
15. [x] Non-invoice urls (13 forms) are not fetched; a 404 invoice omits the block and the release still works.
16. [x] `grep release_invoice src`: descriptor, mark/model, adapter comments only; zero POSTs on load and after polling (unit and e2e).
17. [x] F-87 and workspace tests pass (work-commands, line-adapter, live-work-item, mock-work-live); the F-87 e2e (`work-item-controls.spec.ts`) passes.
18. [x] New unit tests for the descriptor, locks (4, 5, 6) and the adapter.
19. [ ] Not done against live Django: no write was allowed. Mock only.
20. [x] 1440 and 390: no overlap of row, dialog and block, row stacks full width with a 44 px target on the phone (e2e bounding-box checks; axe clean). Screenshots saved under the scratchpad.
21. [x] lint, tsc and the unit tests pass (see below).

## Validation
- `npx tsc --noEmit`: clean. `npx eslint . --max-warnings 0`: clean. `node --check` on `mock/server.mjs` and `mock/invoice-release-live.mjs`: ok.
- `npx vitest run` (full): 4500 tests; first run 4498 passed and 2 failed (the "Delivered" source scan and a phone test in `rfp-submission.test.tsx` that passes alone; the scan failure is fixed above, and on base it fails the same way with only the new file present). Re-run of the affected and named files (`invoice-release`, `work-commands`, `no-success-callouts`, `rfp-submission`, `line-adapter`, `live-work-item`, `mock-work-live`, `next-config`, `demo-mock`, `mock-contract`): 567 passed except one load-related flake that passed alone (49/49).
- `tests/invoice-release.test.tsx`: 50 passed. Mock bodies validated against the contract with ajv (items 4140 to 4144, the invoice, the 202 answer; bad bodies refused).
- Playwright (ports 4950 app, 4951 mock; both stopped after): `work-item-release-invoice.spec.ts` plus `work-item-controls.spec.ts`, 34 passed (desktop 1440 and phone 390).

## Decisions and deviations (named for the coordinator)
- Fixture ids: the spec's 4120 to 4124 clash with F-87's 4120 to 4123. Used **4140 to 4144** (ready, pending after 202, null revision, not offered, with reconcile); invoices 812 to 816. F-87's 4123 (adopt_profile and release_invoice listed) now draws a Release button; its old tests were updated.
- "Release requested..." is a toast, not a Callout: D-151 and `tests/no-success-callouts.test.ts` forbid success callouts for an action result. The lasting words are the reason beside the button and the state tag. An error callout is still drawn after the action disappears.
- A 503 that is not `read_limited` is treated as unknown (locks the release), since the prompt's money rule says 5xx locks. The notice then reads "Try again shortly." while the button reads "Check the page before trying again."; the spec's table says "Try again shortly" only for 503 read_limited.
- The shared `PanelView` draws "We couldn't load this part of the page. Try again" for 429/503/network panel failures, not "Invoice details unavailable. Try again"; no "Loading invoice..." line (the shared view has none). Not changed to avoid editing shared code.
- LC-Q22 option 1 (lock across a reload) is built with localStorage, keyed by work id; clearing site data clears it. Two tabs on the same item share the mark.
- Shared bug noted: `makeCommand` with `action: null` deletes any `action` in `fixed` (not hit here: the action is passed by name).

## Blocked
Not blocked. Held: AC 19 (live Django), because no local write is permitted.
