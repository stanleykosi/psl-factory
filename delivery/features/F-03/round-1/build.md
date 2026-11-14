STATUS: READY
COMMIT: 9bb054bba06ab04ae80f40dc97ed5e8a63248cf4
BUILDER: builder
LANE: full

## Summary
- `/work/[id]` shows one work item from E-WORK-ITEM. It has a breadcrumb, the title with its CMP-05 state tag, "revision N" and SAMPLE DATA, link tabs, the six separate facts with a Paid note, the station track, the agent card, the human-task panels and the next-step callout. Everything is read-only.
- `/work/[id]/history` shows the E-WORK-HISTORY rows in the order returned. It has the All / Decisions / Agent work / Evidence radio filter, a 10/20/50 rows-per-page select, cursor "Show more", restricted rows (who and when only), WAT times, "As of" and the About history panel.
- Polling (D-UPDATES r2): the item is re-read every 5 s only while `agent.status` is working and the tab is visible. A failed poll keeps the item on screen and shows a warning. On the history view, a new revision reloads history once from the first page.
- States: 403 and 404 show the same no-access board, which never includes the id. 401 shows the shell's signed-out callout. Other errors show the work-item error card with Try again. A history error stays inside the history area.
- Mock: per-id fixtures (W-1002 to W-1006, W-1004 history with 12 rows, W-1001 history) and W-1099 as the reserved 404. History honours `kind`, `limit` and `cursor`, and strips `_kind`. Unknown ids get the unchanged default fixtures.

## Changes
- `frontend/mock/server.mjs`: small additive handler for E-WORK-ITEM and E-WORK-HISTORY only, beside the generic path. It reads `fixtures/work/*.json` at start. Lookups use own keys only, so `__proto__` cannot match. W-1099 returns 404. The fallback is `E-WORK-ITEM.json` / `E-WORK-HISTORY.json`, unchanged. Paging uses an `o:<offset>` cursor; an invalid limit becomes 20 and an invalid cursor starts at the first page. `_kind` is removed from every response. Scenarios, personas, CSRF and `OPENAPI_PATH` are untouched. F-02's E-WORK-LIST code can sit beside it without a conflict.
- `frontend/mock/fixtures/work/`: `W-1001.history.json`, `W-1002.json`, `W-1003.json`, `W-1004.json`, `W-1004.history.json`, `W-1005.json`, `W-1006.json`. All are `sample: true` and schema-valid. W-1001 is still served by the fallback, so there is no `W-1001.json`.
- `frontend/src/features/work-item/labels.ts`: contract-derived types, plus the mappings to board wording and classes for state, fact, station, agent and step. It also has the `formatWat` helper ("12 Nov 16:40", Africa/Lagos).
- `frontend/src/features/work-item/useWorkItem.ts`: loads the item and runs the polling rule (5000 ms; visibility-aware; stops when the agent stops or the page unmounts).
- `frontend/src/features/work-item/useWorkHistory.ts`: loads history with `kind` and `limit` and appends pages with `cursor`. Answers to an earlier request are dropped, and history reloads when the revision changes.
- `frontend/src/features/work-item/WorkItemView.tsx`: page states, header, tabs and the refresh warning.
- `frontend/src/features/work-item/WorkItemOverview.tsx`: facts, track, agent card, task panels and next step.
- `frontend/src/features/work-item/WorkItemHistory.tsx`: the history view.
- `frontend/src/features/work-item/WorkItemStates.tsx`: the error card and the no-access board.
- `frontend/src/features/work-item/work-item.css`: feature layout built only from tokens. It covers list resets, the selected look for the current link tab, the underlined breadcrumb link (axe link-in-text-block), the outline FACTORY tag, the 2-column grid from 1080px, and the phone layouts (facts in 3x2, stacked history rows, the track scrolling inside its own region).
- `frontend/src/app/work/[id]/page.tsx` and `frontend/src/app/work/[id]/history/page.tsx`: thin server pages. The `<title>` is always "Work item · PSL Factory". There is no `layout.tsx`, so F-04's `decide/**` is not wrapped.
- `frontend/tests/work-item.test.tsx` (new, 43 tests), `frontend/tests/mock-contract.test.ts` (7 tests appended; existing tests unchanged), `frontend/e2e/work-item.spec.ts` (new, 14 tests).
- Not touched: `src/shell/**`, `src/api/**`, `src/styles/**`, the default fixtures, `architecture/**`, `apps/**` and the protected delivery files.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] W-1004 shows six separate facts: unit test "W-1004 (A-WORKITEM)…" asserts the six texts in order (`DRAFTEDEarned12 Nov 10:58` … `SENT—Not yet`, `RECEIPT RECORDEDUnknown`, `VERIFIED—Not yet`), the classes, no value matching `^$|^0$`, and the Paid note. Seen in the browser at http://localhost:3201/work/W-1004 (mock on 3202), and asserted by the e2e "W-1004 shows the A-WORKITEM facts".
2. [x] Unknown or missing facts read "Unknown": a unit test covers all six unknown, and a facts array without `sent` (shows `SENTUnknown`, `psl-fact--unknown`). Never "0", "No" or blank.
3. [x] State tag: a table-driven unit test over all 11 states checks the wording and the `psl-tag--*` class. A separate test checks that the map covers exactly the 11 contract enum values.
4. [x] Station track: a unit test covers the 7 status mappings, the two-digit numbers, and `aria-current="step"` on the current station only. The e2e at 390px asserts page `scrollWidth <= 390` on /work/W-1001, and that the Stations region itself scrolls (`scrollWidth > clientWidth`).
5. [x] Agent card: the W-1003 unit test checks WORKING, "step 3 of 4", `Read: …` sources in `psl-mono`, and "Cannot approve, send or pay.". It finds zero buttons or links in the card and no other approve/send/pay text. The W-1002 test checks "No agent work on this item."
6. [x] Reduced motion: the e2e asserts the current step's `animation-name` is `psl-pulse` with no-preference and `none` with `reducedMotion: 'reduce'` (emulated, and in a new context).
7. [x] Decision link: on W-1001 the link "Open the decision" goes to `/work/W-1001/decide?task=T-2001`, with "Only a Finance Lead can decide." and "You are Finance Lead.". On W-1002 the panel shows "Only a Finance Officer can decide." with no link or button.
8. [x] Next step: W-1005 shows `psl-callout--warning` and zero buttons on the page. Separate tests check success (W-1006), info (W-1003) and warning (W-1002).
9. [x] SAMPLE DATA shows with `NEXT_PUBLIC_API_MODE=live` stubbed: unit test.
10. [x] No access: unit tests stub 403 and 404. Both show the board text and "Back to my queue" linking to /my-work, and `W-1099` is absent from both `textContent` and `innerHTML`. Seen in the browser at /work/W-1099, and covered by an e2e.
11. [x] 401: the sign-in link is `/accounts/login/?next=%2Fwork%2FW-1001` (unit test).
12. [x] A 500 then a 200 shows the card (eyebrow, message, `Reference unexpected_response for support.`, Try again), then the item after Try again. A network error shows `Reference network_error`.
13. [x] History order and format: the 12 W-1004 rows render in fixture order. `2026-11-12T15:40:00Z` renders as "12 Nov 16:40" with a `<time dateTime>`. Tags read PERSON/AGENT/FACTORY with the neutral, agent and outline classes. The events include "Returned v1" and "Approved invoice v2".
14. [x] Restricted rows: the unit test uses a restricted row that carries an event, detail and version. The row reads only `12 Nov 15:20 · PERSON · Bisi Ade · Finance · Restricted · —`, and the secret strings are absent from `innerHTML`.
15. [x] Read-only: a unit test lists every button, input, select, textarea and contenteditable element. The result is exactly 4 filter radios, the rows select and Show more (Try again appears only in the error test). The table has no links.
16. [x] Requests: unit tests check `?kind=decisions&limit=20`, `?kind=all&limit=10`, and `?kind=all&limit=10&cursor=o%3A10`. Show more appends and then disappears. In the browser (e2e), /work/W-1004/history at 10 rows shows 10, then 12 after Show more, then no Show more. Arrow keys move through and choose the filter.
17. [x] Mock: new tests in `mock-contract.test.ts` cover the following. W-1003 is served per id. W-1099 returns 404 for the item and history. ANY-OTHER gets the unchanged defaults. `kind=decisions` returns only decision rows. `limit=10` returns 10 rows plus `next_cursor`, and following it returns the other 2 with no cursor. `limit=7` behaves as 20. A bad cursor starts at the first page. No response has a `"_kind"` key. Scenarios still win. All existing E-WORK-ITEM and E-WORK-HISTORY contract tests still pass.
18. [x] Every file in `fixtures/work/` validates against the E-WORK-ITEM or E-WORK-HISTORY 200 schema with `_kind` stripped (Ajv test). A further test checks the W-1004 given: the six fact statuses, no approv/send/pay in agent steps, 12 rows newest first, exactly one restricted row with no version or detail, and only "Started the line" without `_kind`.
19. [x] Polling (fake timers): W-1003 is re-read at 5000 ms and again at 10000 ms. W-1001 has no second read within 30 s. Polling stops when the agent finishes. A hidden tab stops polling and it resumes on visible. A failed poll keeps the item and shows "We couldn't refresh this item. Showing what we had at …", and the next poll clears it. A revision change on the history view gives exactly one history reload with `?kind=all&limit=20`.
20. [x] Accessibility: axe finds no WCAG 2.2 AA violations on /work/W-1001, /work/W-1003, /work/W-1004/history and /work/W-1099 at 1440x900 and 390x844 (8 tests). The e2e checks a 2px solid focus ring when tabbing to the Overview tab, the filter and Show more, plus a final axe run after paging.
21. [x] Gate: `bash delivery/checks.sh` exits 0.

## Validation
- `cd /Users/Hunchoo/psl-factory-worktrees/f-03 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh` exited 0. Django check: no issues. Lint: 0 warnings. Typecheck clean. Vitest: 7 files, 139 tests passed. `next build` compiled, with routes `ƒ /work/[id]` and `ƒ /work/[id]/history`.
- `E2E_PORT=3201 MOCK_PORT=3202 npm run test:e2e` (the full Playwright suite: frame.spec.ts plus work-item.spec.ts): 38 passed. The first run of work-item.spec.ts found axe `link-in-text-block` on the breadcrumb link; this was fixed by underlining it, and both runs above are after the fix.
- I looked at the pages in the browser with `MOCK_PORT=3202 npm run dev -- -p 3201`: W-1004, W-1003 and W-1004/history at 1440; W-1001 and W-1004/history at 390; W-1099. Screenshots were compared with the SCR-02 boards. I stopped only my own processes on 3201 and 3202.
- Setup notes: I ran `npm ci` in the worktree. Playwright 1.65 needed `npx playwright install chromium` (headless shell v1254), which went into the user cache.
- All of this ran against the contract mock only; there was no real API or backend.

## Contract gaps (omitted, not invented; for the architecture revision; PMO-0-1, PMO-0-2)
1. Amount with `unknown=true` (A-WORKITEM "unknown amount", INV-UNKNOWN): there is no amount field in E-WORK-ITEM. Only fact-level Unknown is shown.
2. Header "Started by <person> (<role>) · <date>".
3. Per-station detail and time ("Done · Mon 14:05", "Approved 10:47", "Waiting 2h · you", "Chidi · working", "Next · Tola"). The generic CMP-02 status words are used.
4. Task- and line-specific state wordings ("Awaiting Finance decision", "Agent working", "Approved · ready to send", and others). The generic CMP-05 wording is used.
5. Agent role ("Finance agent"), the agent task title ("Drafting the invoice"), the agent's narrative line, per-step times, run start time, "Ask <agent>", the alert and next-check times, and the mascot images. A tinted initial avatar is used.
6. The decision-panel content on the default board (amount, basis, recipient, version change, note, Approve/Return/Reject). This belongs to F-04 / E-TASK-*. F-03 shows only the title, role and link.
7. History filter counts, the tab count, the Documents tab and count, "Download history (CSV)", "Ask for access" on the permission board, and the board line "This attempt is recorded in the audit history." (no contract evidence that it is recorded).
8. History entry kind/category: the mock uses a private `_kind`. The real filter semantics belong to the backend.
9. Who "only a <role>" refers to when separation rules apply (preparer cannot decide own work): this is not in `tasks[]`.
10. Effect-uncertain detail ("Sent at", "Checks 2 · next at 11:10", "If not found …", "See all exceptions"): not in the contract. `next_step` carries the plain-words summary.
11. Facts "Unknown" amount and verified-output link ("See in Verified outputs"): not in the contract.

## Notes for the coordinator
- **Decision link:** `/work/<id>/decide?task=<task id>`, as in the spec Assumptions. It uses the route id, URL-encoded. F-04 must confirm.
- **W-1001 history:** "the default 3 rows re-ordered newest first, `_kind` added". `_kind: "agent_work"` is added only to the Chidi "Drafted invoice" row. The person "Started the line" row and the factory Restricted row have no evidence for a category, so they appear only under All.
- **Copy not on the boards:**
  - The history error card reads "We couldn't load this item's history. Your work is safe; nothing was changed." The spec defines only the item error text.
  - A failed "Show more" keeps the rows and shows a warning: "We couldn't load more entries. Choose Show more to try again."
  - Agent steps carry screen-reader-only state words (Done / In progress / Waiting / Stopped / To do).
- **Signed-out link on History:** a 401 on the History view sends the person back to `/work/<id>/history`. On Overview it sends them to `/work/<id>`, as in the spec.
- **Shared file:** `server.mjs` is the only shared file changed. The change is additive: one export (`NO_ACCESS_WORK_ID`), helper functions, and a 3-line branch before the generic fixture return. The import line now also brings in `readdirSync`.

## Blocked
None.
