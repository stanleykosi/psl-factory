STATUS: READY
COMMIT: 4ebb3c05b15901d845bcbef2d566dc27fa4b7e6a
BUILDER: builder
LANE: full

## Summary
- F-87a only: "Check what happened" (reconcile), Resume, Cancel (with a yes/no dialog), Pause and Continue background work, on the live work item, each shown only when the API lists it. The "Confirm what happened" panel (delivery-observations) is F-93 and is not built.
- One sender, `useWorkCommand`, with the shared lock piece (`useWriteLock`, also used by `useWorkspaceStep`, behaviour unchanged), JSON and multipart bodies, and the uncertain-result lock.
- Carried F-85 lows fixed first in their own commit.
- Shared seams for lanes B and D: `LineAdapter.Actions` slot (`LineActionsProps`), `LineContext.state`, `read(ref, ctx)`, multipart in `useWorkCommand`, one registry file `src/features/workspace/lines/index.ts`. Documented in adapter.ts.

## Changes
- 31901749 (F-85 lows): adapter.ts `makeCommand` body now `{...inputs, action, ...tokens, key}` so descriptor fields win; new optional spec field `action` (null = no action in body). model.ts `safeHref` (http(s) or site path only) used for `output_url`; `lineName` for the breadcrumb; decision rows capitalised (UX-1-2); header gets `work-header--end` (tag right-aligned).
- bbce419c: `workspace/useWriteLock.ts` (shared), `useWorkCommand.ts`, `workItemCommands.ts`, `live/ItemControls.tsx`, `useLiveWorkItem` gains `reload` and `lose`, `LiveWorkItemView` (controls row, PanelView `Actions` in a `PanelBoundary`), `work-item.css` (row; stacks full width, 44px targets on phone), `mock/work-live.mjs` and `server.mjs` (write routes, fixtures, write scenarios), tests `tests/work-commands.test.tsx`, `mock-work-live.test.ts`, `line-adapter.test.tsx`, `e2e/work-item-controls.spec.ts`.
- later commits: `read(ref, ctx)`; `workspace/lines/index.ts` registry (weekly report registration moved there; LiveWorkItemView imports only it); success results shown as toasts (see Blocked/notes).
- src/api: no changes.

## Fixes
- TECH-1-1 | descriptor fields win over inputs, tested | 31901749
- SEC-1-1 | output_url scheme check (javascript:, data:, //host refused), tested | 31901749
- UI-1-1 / UX-1-1 | breadcrumb shows a plain line name | 31901749
- UI-1-2 | state tag right-aligned (verified in screenshot at 1440) | 31901749
- UX-1-2 | decision rows capitalised | 31901749
- Left: TECH-1-2 (history evidence id as text; no evidence route exists), UX-1-3 (same), UX-1-4 (panel loading line; not small enough to do without a board).

## Acceptance criteria (F-87a: 1, 2, 4-22, 33)
1. [x] 4107 -> mock id 4120 (4107/4108 were already F-85 fixtures; used 4120 reconcile, 4121 stopped, 4122 background, 4110 null revision, 4111 none, 4123 adopt/release listed): e2e asserts one button, no radio, no row for 4111.
2. [x] exact body `{"action":"reconcile","expected_revision":5}` captured in e2e; unit test.
4. [x] unit test: failing reload gives "Sent. We couldn't reload...", controls locked until a new read.
5-6. [x] e2e request capture for Resume and Cancel; dialog sends nothing on open or "Keep it".
7. [x] background bodies have no action (unit + e2e).
8. [x] adopt_profile and release_invoice never built (4123).
9. [x] double press sends one; all controls disabled while running (unit).
10. [x] 4110 disabled with reason, no request.
11-14. [x] 409, 403, csrf (session read once, no second send), 422, 429, 503 (30 s fake time) unit tests.
15-16. [x] 500 and dropped connection: re-read, message, lock until revision changes (60 s fake time); reconcile not locked.
17. [x] 401 and 404 hand the page over (unit + page test shows "This record is unavailable.").
18. [x] only POST in the new code is in useWorkCommand; e2e and unit assert zero writes on load.
19. [x] useWorkspaceStep/workspace tests unchanged and passing.
20. [x] tests listed above.
21. Partly. Live Django 8020 / Postgres 55433 as qa-seed: no item lists `reconcile`, so the lookup could not be pressed live. Created by POST /work one item: work_id 1, pmo-weekly-report/v1 on the seeded "Project delivery" project (sample), reference "F-87 live check"; it lists `actions:['background']`, `available_control:['cancel']`, revision 1. Live results: POST /background pause 202 `{"work_id":1,"state":"ready","revision":1}`, continue 202 (same). Revision does not change on a background command (the mock now mirrors this, differs from spec's "revision 8"). POST /actions reconcile on an item that does not list it: 422 `action_unavailable`. Cancel not pressed live (hard to undo).
22. [x] screenshots at 1440 and 390 reviewed (controls row, dialog fits at 390, tag aligned). No board draws the row (LC-Q12).
33. [x] see Validation.

## Validation
- Full `vitest run` via the lock: 3922 of 3923 passed; the one failure (no-success-callouts, D-151) was fixed by showing success as a toast, then re-run with that test plus drift, cash-forecast, workspace-step, line-adapter, live-work-item, mock tests: 155 passed.
- `npm run lint` (max-warnings 0) and `npm run typecheck`: clean. `manage.py check`: no issues.
- Playwright (ports 4980/4981): work-item-controls and work-item-live 30 passed; controls spec re-run after the toast change: 16 passed.
- The full gate script was not run end to end: it does `npm ci` (not allowed here) and I stopped waiting in the lock queue (about 3 hours). Its other steps ran as above; `npm run build` ran as part of the Playwright runs.
- Django on 8020 started by me, stopped by PID. Worktree clean, pushed, HEAD equals COMMIT.

## Notes for the coordinator
- Spec conflict: spec says a success Callout (role status); repo guard D-151 forbids success callouts, so success is a toast and only problems are a Callout.
- Spec says the tag reads "Ready"; the shared STATE_TAGS text is "Ready to continue", which the page and message use.
- `LineActionsProps.reload` returns `Promise<LiveWorkItem | null>` (superset of the briefed `() => void`); forms need the new item.
- `useWorkCommand` takes `{item: {revision}, reload, onAccessLost?}`; lines pass `ctx`.
- Breadcrumb names: a small map of the 25 live line keys in `live/model.ts` (`lineName`), with a words fallback; lane B/D lines added later should extend it.

## Blocked
Nothing blocks.

## Coordinator note (lane C, 24 Nov)
Head moved from the builder's 7374b780 to 4ebb3c05 only by the coordinator merging origin/main 3b7df6cc (F-86). The merge was clean. typecheck: 0 errors. line-adapter, live-work-item and work-commands tests: 79 passed. The tool gate runs next under the D-189 lock.
