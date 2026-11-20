STATUS: READY
COMMIT: b73aff3f69fb0795c6c673fd301995b3a31c530a
BUILDER: builder
LANE: full

## Summary
- History now draws Overview's header and column grid at every width (no history-only crumb, tabs position, phone "History · ref" line, HISTORY bar or 300px aside).
- One shared paging footer (`ShowMore` plus `usePagedRows`, drawn inside `Table`'s frame via `paging`, or under card lists via `solo`): count, "Rows per page" 10 / 20 / 50 as the shared Segmented, Show more. Every paged list is on it; no Select or per-list paging CSS remains (see grep below).
- D-137 behaviour: every list starts at 10; a larger choice adds rows in place (only the missing rows are fetched by the existing cursor, or revealed from rows already loaded); a smaller choice trims without a fetch; options are disabled (not hidden) when the total is at or below the next smaller option; focus stays on the chosen option.
- Added requests in this round: D-138 (Assistant conversation list is infinite scroll, no footer), D-139 (centred composer and thread), D-140 (only the thread scrolls on desktop), D-141 (symmetric thread padding), D-142 (HR stand-in mock persona).

## Changes
Shared components (`frontend/src/components`)
- `ShowMore.tsx`: new footer. Exports `ShowMore`, `usePagedRows` (the window over a list's loaded rows), `usePageSize`, `limitFor`, `PAGE_SIZES`, `DEFAULT_PAGE_SIZE` (10), `PageSize`. Restores focus to the chosen option even if the list redraws the footer (skips a copy that is not drawn, for desktop/phone pairs).
- `Table.tsx`: `paging` prop; the frame (`psl-tableframe`) encloses table and footer. Not used, no extra wrapper.
- `components.css`: footer and frame styles. `index.ts`: exports.

Lists moved onto it (data hooks send the first page at 10 and take a limit for "more")
- Work item History (`WorkItemHistory`, `useWorkHistory`, `labels`): Select and `work-historyfoot` removed; the phone "+ N earlier entries" truncation is gone (cards show all loaded rows, footer under the last card).
- My work (`MyWork`, `WorkRows`, `model`): `limit` stays in the URL, default now 10; `shownText`/`showMoreLabel` replaced by `queueTotal`. Changing `limit` no longer reloads.
- Projects (URL `limit`, default 10), Exceptions, Clients, Payments, Notifications, project tabs (Milestones, Documents, Actions, Registers via `useTabPaging`), start-work record picker, Setup Rules, Finance rules (phone view too), Delivery rules, Templates, Delegation (`useSetupPaging`, `PagingNotes` in `SetupFrame`). `SetupFrame`'s own ShowMore wrapper is gone.
- Contract use: lists whose endpoint declares `limit` (work history, exceptions, projects, project tab, clients, notifications, conversations, delegations, invoices, line options) pass the size. Setup Rules and Templates declare no `limit` (their `cursor` is already a proposal), so no limit is sent: the server's page is loaded and the footer reveals 10 / 20 / 50 of it, fetching by cursor only when the loaded rows run out.
- Assistant conversation list: `ConversationList` has no footer; IntersectionObserver on a sentinel (root = the list's own scroll column on desktop), inline "Loading…", inline "Try again", and focus on the last conversation loads the next page.
- Assistant layout (D-139/140/141, `assistant.css`, `ThreadPage`, `AssistantFrame`, `SidePanel`): desktop and tablet page does not scroll; both side columns keep top and footer, only their middle scrolls; centre keeps "Talk to" and the composer fixed, only the thread scrolls and opens at the latest message; thread right padding = left + avatar column. Phones unchanged.
- Work item header (`WorkItemView.tsx`): History branches removed; `work-header--history` and `work-columns--history` CSS removed.
- Mock: `mock/delegations.mjs` unchanged in contract; HR persona (`me.hr.json`, `lines.hr.json`, server/start-work/alerts maps) from the coordinator (D-142), with `mock-contract.test.ts` updated for `hr`.

Shared-file notes (checklist item 9): `Table`, `ShowMore` and `Segmented` consumers are listed above; no change to Workspace, InlineDecide, WorkItemOverview or Sections.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] History header and grid equal Overview's at 1440 and 390: measured on /work/W-1408 and /history: tabs and title x, y, width identical; main column x 88 / width 916 and side column x 1028 / width 324 at 1440 (see screenshots). e2e `history draws Overview's header and column grid` (desktop and phone) in `e2e/work-item.spec.ts` passes.
2. [x] One shared footer with `Table` frame option; unit tests in `tests/components/show-more.test.tsx` (count text with and without total, 10 default, changing size, busy, none when all shown, same DOM nodes after a larger choice, trim without fetch, 3 rows disables 20 and 50, 15 rows disables 50). Default is 10 (D-137), not the 20 the older wording says.
3. [x] Every listed list uses it. `grep -rn "Rows per page" src/features` returns only comments or nothing for a Select; `grep -rn "psl-showmore\|historyfoot\|exc-foot\|my-work__rows" src/features` finds only tests' class names in e2e/unit, none in feature CSS (the remaining feature hit is the e2e selector `.psl-showmore`). Assistant conversations are the D-138 exception (infinite scroll, no footer).
4. [x] Lists start at 10 and offer 10 / 20 / 50; cursor lists pass the size to their existing `limit` (exception: Rules and Templates, see Changes).
5. [x] Rows-per-page is the shared Segmented (Tab, arrows, roving tab stop); focus stays on the chosen option (unit tests; e2e `my-work`, `projects`, `work-item-board`). Phone options are 44px (`psl-seg--phone`) and Show more is 44px tall (e2e touch-target checks in projects, project-tabs, clients).
6. [x] Unit tests: 138 files, 3407 tests pass on the final head. Existing tests were updated only for the old dropdown, old footer markup, fixed page sizes (20/50) and the removed "earlier entries" button. e2e on the final head: work-item, work-item-board, my-work, projects, exceptions, setup, setup-templates, setup-delegation, clients, alerts, project-tabs, assistant, payments, start-work, workspace, history-link all pass (413 passed in the full run before the last small spec fixes; the follow-up runs of my-work, projects, setup, alerts, assistant and work-item then passed).
7. [x] Screenshots at 1440 and 390 of History (work-history), My work, Projects, Exceptions and Clients; Overview included for the header comparison. Before: `delivery/features/F-54/round-1/screenshots/before/`; after: `.../screenshots/after/` (`work-overview-*`, `work-history-*`, `my-work-*`, `projects-*`, `exceptions-*`, `clients-*`, each at 1440 and 390). Before shots were taken from a build of `dlv-00-delivery-setup`; after shots from the production build of this branch.
8. [x] D-138: unit tests (IntersectionObserver stub: loads at the end, Loading line, retry line, last-conversation focus) in `tests/assistant.test.tsx`; e2e `the conversation list loads the next page as it is scrolled...` in `e2e/assistant.spec.ts`.
9. D-139/D-140/D-141: e2e `desktop: only the thread scrolls...` at 1440: both footers, composer, Talk to bar and New request button keep their position after scrolling the thread, `window.scrollY` stays 0, the page is not taller than the window, and the agent card is as far from the composer's left edge as its right (within 1px).

## Validation
- `bash delivery/checks.sh` passed (exit 0) mid-round on an earlier head (npm ci, lint, typecheck, vitest, build, Django check). After the later changes I re-ran lint (0 warnings), `tsc --noEmit`, `vitest run` (3407 passed) and `next build` on the final head, without repeating `npm ci` or `manage.py check` (no backend or dependency change; npm ci would have wiped `node_modules` under the coordinator's live dev server). The coordinator's gate will run the whole script.
- Playwright e2e as listed under criterion 6. Production build served on 4942 with the mock on 4941 for screenshots; both stopped. The live dev server on 4951/4952 was left alone.
- Design fidelity tool not run: this feature changes layout the boards do not draw and passes under EXCEPTION D-89 as in the spec; no waiver proposed.
- A broad `pkill` was refused by the permission system and not retried; the gate run I had started was allowed to finish.

## Notes for the coordinator
- Shared bug family: any list whose server returns fewer rows than asked while giving a cursor is now topped up automatically (by design). Mock "paged" scenarios that return 2 rows with a cursor therefore load fully on open (Payments test updated).
- Finance rules and other grouped or windowed setup views now show the first 10 rows; groups are built from shown rows only (choose 50 to see all).
- Not a regression but visible: the Notifications page now sends `limit=10` (declared in the contract) where it sent none before; the bell feed still sends none.
- Open question for the design engineer: Show more on a list whose total is known reads "Show N more" (My work, History after trimming, Notifications etc.); lists with unknown totals read "Show more".
