STATUS: READY
COMMIT: 9f9dc026b5e62762de288ca468aa8a4380a649f1
BUILDER: builder
LANE: full

## Summary
- Fixes the blocking TECH-2-1: command locks no longer live in component state. They live in a per-work-item store above the components, so they survive History and back, a failed panel re-read and any remount.
- The shared API is unchanged: `useWorkCommand` args and result, `useWriteLock` (unchanged), `Actions`, `LineContext.state`, `read(ref, ctx)`, `lines/index.ts`.

## Changes
- `workspace/useWriteLock.ts`: new `useScopedWriteLock(scope)` (module-level store with `useSyncExternalStore`; holds the write slot, the pending press, the uncertain locks and the unread marker per scope) and `resetScopedWriteLocks()` (test seam; a full page load clears it in the browser). `useWriteLock` itself is untouched, so `useWorkspaceStep` is unchanged.
- `workspace/useWorkCommand.ts`: uses the scoped store, scope = the item's `workId` or `id` (lines pass their ctx, the controls row passes the item). Lock keys stay `command@revision`, so a lock releases only when a re-read shows a different revision, or on a full page reload.
- `work-item/live/LiveWorkItemView.tsx`: the line `ctx` is now made in `LiveWorkItemView` (it outlives the tab), memoized on the item, and passed to `Overview`, so a line's unread marker still matches after History and back.
- `tests/work-commands.test.tsx`: two page tests.

## Fixes
- TECH-2-1 | 2ce45be7e1fe607e261c2ed8af5836f061f4b228 | locks in a store keyed by work id. Test "a timed-out Resume stays locked after History and back (no new read), and a second press sends nothing": w500 on Resume, History, back, Resume still disabled with "Check the page before trying again.", one POST. Test "switching tabs while a write is running does not allow a second write alongside it". Both fail when the scope is made per mount (the old behaviour) and pass now.

## Acceptance criteria
Unchanged (1, 2, 4 to 22, 33); criterion 15 now also holds across History and back.

## Validation
- Full `npm test` through the lock: 158 files passed; 1 test failed, `tests/cash-forecast.test.tsx` "a 500 re-reads first ..." (90 s timeout under load). It is not in files I touched; run alone the file passes (43 of 43). Likely a fake-timer flake under a loaded machine.
- Affected files (work-commands, live-work-item, line-adapter, workspace-step): 132 passed. `tsc` and eslint (max-warnings 0) clean.
- Playwright work-item-controls and work-item-live, ports 4980/4981, no lock: 32 passed.
- I started no servers I had to stop by PID (Playwright starts and stops its own).
- One attempted `git stash` for an old-code comparison was denied; I did the comparison with a temporary per-mount scope edit instead and restored it.

## Blocked
Nothing blocks.

## Coordinator note (lane C, 24 Nov)
Head moved from the builder's 2ce45be7 to 9f9dc026 only by the coordinator merging origin/main 4a88c26b, which brings F-62 (#106), F-125 (#105), #108 and F-113 (#109). One conflict, in tests/mock-work-live.test.ts: both sides only added tests, and both were kept (20 tests pass). typecheck clean; work-commands, line-adapter and live-work-item: 85 passed. git.base_sha is the merge base 4a88c26b, and the diff from it has 19 files, none protected (D-200).
