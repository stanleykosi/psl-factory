STATUS: READY
COMMIT: cab10c70cdbf110a59387b6e5bd6c0fb0efa470f
BUILDER: builder
LANE: full

## Summary
- Fixes the blocking TECH-1-1: a failed panel re-read no longer unmounts a line's `Actions`, so its uncertain lock survives the failed read and "Try again".
- Also fixes TECH-1-2 to TECH-1-7 and UX-1-1; one commit on top of 4ebb3c05.
- Shared API for lanes B and D is unchanged except one additive prop, `LineActionsProps.onAccessLost`.

## Changes
- `live/LiveWorkItemView.tsx` PanelView: keeps the last good readback; a failed re-read draws the warning with Try again above it and leaves sections and `Actions` mounted. `commands` memoized. `onAccessLost` (the page's `lose`) passed to `Actions`. The line ctx is memoized on the item, so it is a new object per read.
- `workspace/adapter.ts`: `LineActionsProps.onAccessLost` (doc example updated); a body with `action: null` has no `action` whatever the inputs say.
- `workspace/useWorkCommand.ts`: refuses any url failing `isPanelUrl` before a request; the "Sent. We couldn't reload" notice is an error (stays as a Callout); the unread lock compares against the latest item (ref updated in an effect), not the item from the press.
- `workspace/useWriteLock.ts`: unused `unlock` removed.
- `live/ItemControls.tsx`: Cancel uses the `reject` button kind; a locked button shows its normal label, not "Working...".
- Tests: `tests/work-commands.test.tsx`, `e2e/work-item-controls.spec.ts`.

## Fixes
- TECH-1-1 | cab10c70cdbf110a59387b6e5bd6c0fb0efa470f | lock lives with the mounted Actions, which now survives a failed panel re-read. Test "a line command that timed out stays locked when the panel re-read fails and Try again is pressed": line POST 500, panel read 500, Try again, still locked, then panel reads again, still locked, one POST total. It fails on the old PanelView (the form unmounts, no "Go" button) and passes now.
- TECH-1-2 | cab10c70cdbf110a59387b6e5bd6c0fb0efa470f | onAccessLost passed to lines
- TECH-1-3 | cab10c70cdbf110a59387b6e5bd6c0fb0efa470f | sender refuses non-API urls (https, //host, dot segments, other paths), tested
- TECH-1-4 | cab10c70cdbf110a59387b6e5bd6c0fb0efa470f | unreadable notice is an error Callout
- TECH-1-5 | cab10c70cdbf110a59387b6e5bd6c0fb0efa470f | unread lock by latest read; test with a poll landing mid-write then a failed re-read
- TECH-1-6 | cab10c70cdbf110a59387b6e5bd6c0fb0efa470f | added: poll mid-write (deferred POST), page test for the 500 lock sentence beside a disabled Resume, e2e for 403 and 422
- TECH-1-7 | cab10c70cdbf110a59387b6e5bd6c0fb0efa470f | no action key with action: null; unused unlock removed
- UX-1-1 | cab10c70cdbf110a59387b6e5bd6c0fb0efa470f | locked button shows its label
- Left: UX-1-2 (callout after a dropped connection shows beside the new tag; the spec mandates the message; unchanged). Reviewer note on the 409-with-failed-reload wording left as is.

## Acceptance criteria
Unchanged from round 1 (criteria 1, 2, 4 to 22, 33); criterion 9, 12, 13, 15 now also covered by the added tests above. Criterion 21 live part: still no live item lists reconcile (round 1 notes stand).

## Validation
- Full `npm test` through the lock on this head: 158 files, 3815 tests passed.
- `npx eslint src/features tests e2e` files changed: max-warnings 0; `tsc --noEmit` clean.
- `npx playwright test e2e/work-item-controls.spec.ts` (4980/4981, no lock): 18 passed.
- I started no servers this round. In round 1 I used pkill by pattern once on my own vitest run and once on my own queued gate wrapper (before the new rule); nothing of anyone else's was targeted.

## Blocked
Nothing blocks.
