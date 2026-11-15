VERDICT: CHANGES
COMMIT: 07d078ef95aed97f36a412c6214ee8bc778ab9d0
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead)

## Summary
- The feed rules hold: one read when the frame is ready, one per open, a single in-flight guard, no timer, a 5-minute-gated visibility refresh, and nothing more after a GET 401. Mark-read is one POST through the shared client (CSRF), only for unread alerts.
- `needs_you` is a local `AlertWithNeed` PROPOSAL type; `schema.d.ts` is untouched; the reading rule and "known" rule match the spec.
- Shell edits are contained: the bell only renders once destinations exist, and the 10+ test files only add a stub answer for the bell's read. Two changed assertions in `alerts.test.tsx` and one in `setup-rules.test.tsx` are accounting changes and do not weaken them.
- One blocking gap: on phone, after Open (a route change), focus does not return to the bell, because the phone bar remounts on every path change.
- Not run: I did not run the app or tests (gate passed); this is a code read.

## Findings
- TECH-1-1 | blocking | medium | frontend | Focus does not return to the trigger after a route change on phone. Spec: "On any close focus returns to the trigger that opened it" and "Opening an alert ... or any route change closes the drawer". `AppShell.tsx` renders `<PhoneBar key={pathname} ...>`, so the phone bell button that `opener.current` holds is unmounted when Open navigates. The close effect then calls `.focus()` on a detached element, which does nothing, and focus drops to `body`. Desktop is fine because `TopNav` is not keyed. Neither `tests/alerts-bell.test.tsx` (phone case, line 458, uses Escape) nor the e2e covers Open or a footer link on phone. Expected: remember which bar opened it (not the element) and focus the bell that exists after the change, e.g. look it up by a `data-` hook or `aria-controls` match in the visible bar; add a phone test for Open and for "Alert settings" that checks `document.activeElement` is the new bell.
- TECH-1-2 | non-blocking | low | frontend | Stale read state can overwrite a mark-read. `AppShell` calls `feed.refresh()` on open. If the person clicks Open on an unread alert before that read returns, the POST succeeds and `markRead` updates local state, then the earlier response (read:false, old `unread_count`) replaces it, so the badge is too high until the next open. Cheap guard: drop or re-apply a response that arrives after a local mark-read (keep a set of ids marked this session and re-apply it in `refresh`). `useAlertsFeed.ts:33-47`.
- TECH-1-3 | non-blocking | low | frontend | "A 401 anywhere stops further requests" is met only for the GET. A 401 on the mark-read POST in `useOpenAlert` (`AlertParts.tsx`) is swallowed, so the next open still sends a GET. Pass the error to the feed (an `onError` or a shared `stopped` flag) so it stops there too.
- TECH-1-4 | non-blocking | low | frontend | `AlertsDrawer` sets `--alerts-top` once on mount from `.shell-topbar`. If the viewport crosses 720px while open (rotate, resize), `phone` flips but the offset stays stale (0 when the bar is hidden). Rare; recompute on resize or set the offset in CSS only.

## Notes on the focus points asked
- Shell changes: `TopNav` moves `.shell-navend` after the name (the spec's Conflicts item 1) and `PhoneBar` puts the bell in the existing `.sw-phoneslot`; both bars render unchanged when `bell` is undefined (no `/me`, loading, no sections). The shell.css selectors are scoped under `.shell-bellwrap` or `:has(.shell-bellwrap)`, so pages without a bell keep their layout. `inert` on the skip link, phone bar and `main` is applied only while open.
- Fetch: matches the spec; `enabled` is `destinations.length > 0`, so no read while `/me` loads, errors or is signed out (AC 8). A response without an `items` array is treated as a load error, not "no alerts".
- Mark read: guarded against double click by `opening`; the work opens whether or not the POST worked; `onRead` runs only after the server accepted it. `NotificationsPage` behaviour is unchanged by the extraction.
- Focus trap: Tab and Shift+Tab wrap inside the panel; Escape handled on `document`; Close takes focus on open. Fine apart from TECH-1-1.
- Test changes: `bell-feed.ts` answers only the exact `GET /api/v1/notifications` with an empty list, so the tests that use it keep their own call counts and queues. No test was skipped or loosened. In `alerts.test.tsx`, the loading gate now expects 2 held calls (page plus bell) and the bare-scenario URL list gains one `''` for the bell, so the page's two reads must still appear; both stay tight (count and values). The `setup-rules` read-only check now excludes `.shell-bell` as well as the menu button, which matches the intent (no editing controls). The `shell.test` rename "has no bell" to "has no account menu" and the new button list follow the spec's intent.
- Docs: the `TopNav` comment is updated. No `AGENTS.md` change was needed.

## Verified
None (round 1).
