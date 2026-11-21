VERDICT: CHANGES
COMMIT: b73aff3f69fb0795c6c673fd301995b3a31c530a
REVIEWER: ux-reviewer
AUTHORITY: UX reviewer

## Summary
- Paging footer behaves as D-137 on every persona and at 390: lists start at 10, 20/50 append in place (same first-row node, no blank, only the extra rows requested), going back trims with no request, options that add nothing are disabled, focus stays on the chosen option, arrow keys work. Phone targets are 44x44.
- History and Overview have the same header and column positions at 1440 and 390 (h1, tabs, main identical), and switching tabs does not move them.
- Assistant: only the thread scrolls, both side footers and the composer stay put, the page does not scroll (doc height = window). Phone infinite scroll and retry work.
- One blocking bug: on the desktop Assistant the conversation list does not load the next page when scrolled to the end in windows about 800px tall or less (UX-1-1).

## Findings
- UX-1-1 | blocking | medium | frontend | D-138 / criterion 8: scrolling the desktop conversation list to its end does not load the next page at window heights of 700 and 800 (it works at 900 and on a phone). The sentinel in `frontend/src/features/assistant/ConversationList.tsx:86` is a 0-height div, and when the list is scrolled fully down it sits at y 708.31 while the scroll column's bottom (the IntersectionObserver root, `.as__listscroll`) is 708, so it never counts as intersecting (measured: scrollTop 77 of max, sentinel top 708.3125, root bottom 708, 10 of 10 conversations stay and no cursor request is sent). Expected: reaching the end always loads the next page. Fix: give the sentinel a 1px or more height, or add a rootMargin (e.g. `0px 0px 48px 0px`) to the observer at line 51, and add a unit or e2e case at a non-integer layout height. The keyboard route (focus on the last conversation) still works.

## Verified
- Round 1, nothing to verify from earlier rounds.

## Notes
- Checked with the live dev server on 4952 as pm, pmo_lead, finance_lead, ceo and hr at 1440 and 390: Projects, Exceptions, Clients, History, Notifications, My work (finance_lead 24 items; pmo_lead exceptions 25). Lists with fewer than 11 rows show "All N showing" with 20 and 50 disabled. Empty lists (pm exceptions, ceo projects) show no footer.
- Infinite-scroll check used intercepted API responses (the mock has only one conversation): phone loaded 10, then failed page showed "Try again", retry loaded 25 in total with no reload.
- The Next dev badge overlaps the left footer note on the Assistant; dev only.
- My work on desktop updates the URL `limit` a moment after the click, as intended; the first race I saw was dev-server compile lag.
