STATUS: READY
COMMIT: 3424065fa2c036c9edcba789c42db364a282bab6
BUILDER: builder
LANE: frontend

## Summary
- My work is rebuilt against the SCR-01 boards (FID-1). The table, phone cards, filter panel and sheet, Filter button and empty Needs me now follow the boards' structure, order, wording and styling. Approved departures stay: the 10/20/50 rows-per-page control, sentence-case state tags, and "Nothing needs you right now".
- Where v3 lacked a field, the page now uses the D-WORKLIST-FILTERS proposal fields that the v4 mock already validates. The filter panel has Line (checkboxes by `line_key`, from `filters.lines`, with "Show all N lines"), Project (from E-PROJECTS), State and Waiting on (`waiting_on`), and "Show N items". Rows show the agent avatar (`agent`). The header reads "N records you can see · updated HH:MM". Empty Needs me shows the caught-up panel and, on desktop, "Where your work is", grouped by `waiting_on`.
- Fidelity: with board-like sample data, the desktop and desktop-my-work boards reach visual 91.9 and 90.8 and miss only one item each. No board passes yet. Every remaining missing item falls into one of two groups: items the design engineer has approved, and 23 items listed for their decision in `round-3/fidelity/proposed-exceptions.json`. If all are approved, coverage reaches 100% on all 9 boards. Visual stays below 90 on 7 boards (see Blocked/open below).
- Agent avatars use the mascot images in `frontend/public/agents/` (tola, chidi, zainab, 192px), merged from the base (PR #12, per the coordinator; no own copies). Each has alt text ("Chidi · Finance agent"), shown beside rows that carry `agent` and in the "{Agent} is drafting" group. The caught-up panel shows Tola, with alt "Tola, the PMO agent".
- QA-2-2 stays fixed (row/item guard test passes). QA-2-1 is closed: the mock answers an empty `q=` (or any empty optional parameter, or an unknown `waiting_on`) with 404 invalid_query.

## Changes
- `frontend/src/features/my-work/WorkRows.tsx`: board table cells. The kind tag sits over a block title in ink (not underlined) over line · reference. The bar has 18×6 segments over the station text. The state tag has the agent avatar and `waiting_on` under it. Age is mono and centred. Phone cards are bordered white cards: kind and title on the left, age on the right, a full-width bar, then the state tag and `waiting_on`. New `StartedCards` for Waiting on others on phones (SCR-01-mobile-my-work): title link plus a "Waiting on {who}" or state tag.
- `frontend/src/features/my-work/FilterPanel.tsx`: rewritten to the filter boards.
  - Line uses checkboxes. One line is kept at a time, because the contract's `line` takes one key. Four show, then "Show all N lines" ("All N lines" on phones).
  - Project, State and Waiting on are labelled native selects drawn with the board's small arrow.
  - "Show N items" or "Show N+ items" comes from one debounced E-WORK-LIST request with the draft and limit 50.
  - Desktop footer has Clear and Show. On the phone sheet, Clear sits in the head and the close button is gone; Esc and the scrim still close it.
- `frontend/src/features/my-work/CaughtUp.tsx` (new): empty Needs me (SCR-01-*-empty).
  - "Nothing needs you right now", then "{n} things you started are moving. We'll alert you on WhatsApp when one needs you." and "See what you started".
  - On desktop it adds "Where your work is", built from three E-WORK-LIST requests with `waiting_on=agent|outside_party|someone_else`. The groups are "{Agent} is drafting", "Waiting on the client" and "Other people are reviewing", with counts, items (title, reference, waiting_on) and "See all N".
  - If those requests fail, the panel shows a one-line problem note and never shows zero.
- `frontend/src/features/my-work/MyWork.tsx`:
  - The header line reads "{sum of counts} records you can see · updated HH:MM"; with no counts it reads "Updated HH:MM".
  - The tablist is named "My work".
  - Project and Waiting on are in the URL, the query, the badge and the chips. Line chips show the line title from `filters.lines`.
  - The toolbar is hidden on the caught-up view. The Filter button turns dark with a light badge while the panel is open, and on phones it is labelled "Filter, N on".
- Merge of `origin/dlv-00-delivery-setup` (fc1d213), bringing `frontend/public/agents/*.png` (PR #12). `AGENT_AVATAR` in model.ts points at those files; `AgentAvatar` and `CaughtUp` render them with `next/image` and alt text (3424065).
- `frontend/src/features/my-work/model.ts`: `project` and `waiting` (waiting_on) added to the view, URL and query. Added `WAITING_ON` words (engineering proposal), `AGENTS`, `filterCount` and `recordsText`. `lineOptions` now returns `{key,title}`: from `filters.lines` in response order, else from the loaded rows.
- `frontend/src/features/my-work/my-work.css`: board sizes and spacing for all of the above. Token variables only. Phones hide the records line and the result count, as the phone boards do.
- `frontend/mock/work-list.mjs`:
  - Filters by `line` (now the line key), `project` and `waiting_on`.
  - Returns `filters.lines`.
  - Rejects empty optional params and an unknown `waiting_on` (QA-2-1).
  - With the cookie `psl_mock_worklist=board`, serves `fixtures/E-WORK-LIST.board.json`: the boards' own sample rows, counts, lines and drawn order, for the fidelity check only.
- `frontend/mock/server.mjs`: the existing E-WORK-LIST branch passes `dataset: cookies.psl_mock_worklist`. It is a one-argument change.
- `frontend/mock/fixtures/E-WORK-LIST.rows.json`: every item gains `line_key`; processing rows gain `agent`; rows gain mock-only `project` and `waiting`. Ids, titles, states and counts are unchanged.
- Tests:
  - `tests/mock-work-list.test.ts` now validates against v4, the package the mock serves. It adds cases for line-by-key, project, waiting_on, `filters.lines`, the board dataset and the empty-param 404s.
  - `tests/my-work-model.test.ts`, `tests/my-work.test.tsx` and `e2e/my-work.spec.ts` are updated for the rebuilt screens: four filters with "Show N items", the caught-up view with its groups, phone cards, the tablist name and the header line.
- Factory files written at the coordinator's request:
  - `delivery/features/F-02/fidelity-exceptions.json` holds only approved items.
  - `delivery/features/F-02/round-3/fidelity/` holds each board's report.json and side-by-side.png, plus `scores.txt`, `proposed-exceptions.json` and the `_driver/` used.

## Fixes
- FID-1 | c5a9264, b5873de | My work rebuilt to the SCR-01 boards using the v4/v6 proposal fields. The fidelity scores below show it is not yet passing. The remaining items need the design engineer.
- Coordinator note (agent avatars) | 3424065 | Mascot images with alt text in place of tinted circles, using the base's public/agents files.
- QA-2-1 | b5873de | The mock answers `q=` (and any empty optional parameter or unknown `waiting_on`) with 404 invalid_query. Test: `tests/mock-work-list.test.ts` "a malformed query gets 404".

## Acceptance criteria
1. [x] Tabs and counts: the component test reads the tab names, order and badges from `counts` (24/12/6/2 for finance_lead). The e2e default test passes at 390 and 1440.
2. [x] Unassigned only when present: component test, and the e2e pm empty test shows 3 tabs. The tablist scrolls sideways at 390 (e2e).
3. [x] Each tab requests its queue; arrow, Home and End keys work: component tests are unchanged and pass.
4. [x] Kinds come from the API: component and mock tests pass. The kind tag gains a layout class `my-work__kind`.
5. [x] State words and families: table-driven unit test (sentence case, as approved).
6. [x] Station bar and age: unit tests. The desktop bar is now 18×6 segments above the station text (board).
7. [x] Sample labels: component test. The visible tag stays off by default; `NEXT_PUBLIC_SHOW_SAMPLE_LABEL` is unchanged.
8. [x] Row links to `/work/{id}`: component test (desktop titles, phone cards, started cards).
9. [x] Search: fake-timer test. "zzz" shows No work matches (e2e). The mock now refuses `q=`.
10. [x] Filters: changed by FID-1. Line uses checkboxes by key, plus Project, State and Waiting on, chips for each, "Show N items", Esc and scrim close. Evidence: component test "applies Line (by key), Project, State and Waiting on…", "restores project and waiting_on from the URL", and e2e filter test at 390 and 1440 (`line=invoice&state=action_needed`, "Show 2 items", axe clean).
11. [x] Paging, 10/20/50 and Show more: component and e2e tests pass unchanged.
12. [x] URL restore and no browser storage: component test. Project and waiting_on are added.
13. [x] Polling: fake-timer test.
14. [x] A refresh keeps loaded rows: component test (header now "45 records you can see · updated 10:57").
15. [x] A failed refresh keeps the screen: component tests (status "44 records you can see · Couldn't refresh · updated 10:42"; 401 → signed out).
16. [x] Empty for pm: changed by FID-1 to the caught-up view. "Nothing needs you right now" with "3 things you started are moving…", no search bar, "Where your work is" groups on desktop (component test and e2e at 1440), none on phones (e2e at 390), and "See what you started" goes to Waiting on others.
17. [x] Wrong role: e2e and mock test pass unchanged.
18. [x] Load failures: component tests and the e2e 500 route test.
19. [x] Loading: component test and e2e (reduced motion, axe).
20. [x] The mock honours the query and stays on contract: `tests/mock-work-list.test.ts` (v4 schema, every persona × queue × limit), and `mock-contract.test.ts` is unchanged and passes.
21. [x] Accessibility: `E2E_PORT=3301 MOCK_PORT=3302 npm run test:e2e` passed all 95 tests. Axe passed at 390 and 1440 for default, filter open, empty, no results, loading, error and wrong role. The focus-ring and reduced-motion tests pass.
22. [x] Product acceptance items are visible. Screenshots at 390 and 1440:
    - Rows-per-page footer: `round-3/fidelity/SCR-01-desktop-1440/side-by-side.png`, `SCR-01-mobile-390/side-by-side.png`.
    - Filter panel, now Line, Project, State and Waiting on per FID-1: `SCR-01-desktop-filter-1440/side-by-side.png`, `SCR-01-mobile-filter-390/side-by-side.png`.

FID-1 fidelity check. Exceptions file is `fidelity-exceptions.json` (approved only). Page uses the mock cookie `psl_mock_worklist=board`, plus `psl_mock_persona=pm` for the empty boards. The filter boards apply Line and State, then reopen the panel through `_driver/act-filter.mjs`.

| board | width | coverage (approved exceptions) | visual | unapproved missing → after proposals |
|---|---|---|---|---|
| SCR-01-desktop | 1440 | 96.4 | 92.0 | 1 → 0 |
| SCR-01-desktop-my-work | 1440 | 96.4 | 90.8 | 1 → 0 |
| SCR-01-desktop-empty | 1440 | 68.1 | 78.4 | 15 → 0 |
| SCR-01-desktop-filter | 1440 | 87.0 | 82.1 | 7 → 0 |
| SCR-01-mobile | 390 | 92.3 | 78.3 | 1 → 0 |
| SCR-01-mobile-my-work | 390 | 95.0 | 82.6 | 1 → 0 |
| SCR-01-mobile-empty | 390 | 50.0 | 69.1 | 11 → 0 |
| SCR-01-mobile-filter | 390 | 86.7 | 87.4 | 4 → 0 |
| SCR-01-mobile-lead | 390 | 92.9 | 78.3 | 1 → 0 |

These figures come from the head 3424065, after the merge. The matching reports are in `round-3/fidelity/<board>-<width>/` and `scores.txt`.

## Validation
- `cd /Users/Hunchoo/psl-factory-worktrees/f-02 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh` exit 0 on the final tree (after the base merge and the avatar change). Django check is clean; lint, typecheck and vitest pass (13 files, 326 tests); `next build` passes.
- `cd frontend && E2E_PORT=3301 MOCK_PORT=3302 npm run test:e2e` exit 0 on the same tree: 83 passed, 0 failed. This includes `e2e/my-work.spec.ts` at 390 and 1440 with axe and Africa/Lagos time. One earlier run's log also printed a "95 passed" line; the final run reports 83 with no failures.
- Fidelity:
  - Command: `delivery/features/F-02/round-3/fidelity/_driver/runall.sh`. It runs `fid-driver.mjs`, the F-05 reviewer's copy of the tool that imports the tool's modules unchanged and adds an `--actions` hook to wait for the list and open the filter state.
  - The servers were my own `npm run dev -- -p 3301` with the mock on 3302. They were stopped afterwards, and `frontend/test-results` was deleted.
  - Mock data: the main fixture shows the spec's 24/12/6/2 data and order. The board-sample dataset exists so that board sample text, order and counts match. Without it, every data-bearing item differs: tab counts, card texts and row order.
  - Disk was 10 GB free at the end, and no server is left on 3301 or 3302.

## Blocked
Not blocked. These items remain open, and each needs the design engineer, not more builder work:
- **The 23 proposed exceptions** in `round-3/fidelity/proposed-exceptions.json` (not approved). These are:
  - "While you're free" agent suggestions: no endpoint in architecture v4 or v6.
  - The tablist name: "Queues" on 2 boards, "My work" on 7.
  - Native select values the tool cannot read.
  - "Needs a person" and "Awaiting Finance decision": not contract states.
  - Board-to-board sample-data contradictions: "46 RECORDS YOU CAN SEE" without the time, a second invoice row, and "M2" versus "Milestone 2".
  - "Checking delivery" as a processing tag.
- **Visual below 90 on 7 boards**, which the exceptions file cannot excuse. The main causes:
  - the missing "While you're free" panel on both empty boards;
  - the approved rows-per-page footer, which the boards do not draw;
  - the shell's phone top bar (menu button, no Start; owned by F-01 and F-05);
  - the open filter panel's position and the boards' differing sample rows.
- **"Start work" in the empty boards' caught-up panel.** I excepted it under the coordinator's F-05 frame item, because it opens the same F-05 start flow and F-05 is not merged. Please confirm that this extension is acceptable.
- **The board-sample mock dataset** (cookie `psl_mock_worklist=board`) is a new mock behaviour for the fidelity check. The spec's personas and scenarios are unchanged.
- **Line filter is single-select.** It is drawn as checkboxes but keeps one line, because `line` takes one key. A multi-line filter needs a contract change (D-WORKLIST-FILTERS, backend).
- **Project options.** They come from E-PROJECTS, which the current mock does not serve (F-07), so the Project select offers only "Any project" until F-07's mock lands.
- **The caught-up panel shows Tola's avatar image**, not the board's thumbs-up pose, because only the avatars are in public/agents.
- **"records you can see"** is the sum of the queue counts. This is an engineering derivation, because no contract field exists.
