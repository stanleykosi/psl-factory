STATUS: READY
COMMIT: 02d59d8bb2216a7242a02454b957d4a0b0fdde49
BUILDER: builder
LANE: frontend

## Summary
- My work is rebuilt to the SCR-01 boards (FID-1) using the D-WORKLIST-FILTERS proposal fields: Line, Project, State and Waiting on filters, "Show N items", agent mascot avatars, "N records you can see · updated", the caught-up empty view with "Where your work is", board table and phone cards.
- This round also adds "While you're free" (coordinator decision 2), built as the boards draw it. It reads a new optional `suggestions` block, which the mock serves only with the board sample. The block is typed locally and the panel is hidden when the field is absent. This is a field proposal for the architecture (see Contract proposal).
- Fidelity uses the D-17 provisionally approved exceptions file. Coverage is 100% on all 9 boards, and 6 of 9 boards pass with visual ≥ 90. Three are below 90: SCR-01-desktop-filter 83.6, SCR-01-mobile and SCR-01-mobile-lead 81.1, and SCR-01-mobile-empty 73.0. The reasons are given per board below.
- QA-2-2 stays fixed (the row-to-item guard test passes). QA-2-1 is closed: the mock answers `q=` and any other empty optional parameter with 404 invalid_query.

## Changes
- `frontend/src/features/my-work/WorkRows.tsx`: the board table, and phone cards with the state and `waiting_on`. `StartedCards` covers phone Waiting on others; it is a role=list of title links with a "Waiting on {who}" or state tag. `AgentAvatar` shows the mascot image from `public/agents/` with alt text.
- `frontend/src/features/my-work/FilterPanel.tsx`: the filter boards' panel.
  - Line uses checkboxes by key from `filters.lines`, keeps one line at a time, and has "Show all N lines".
  - Project (from E-PROJECTS), State and Waiting on are native selects with the board's arrow.
  - The button reads "Show N items", counted by one debounced list request.
  - On phones the sheet head is "FILTER" plus Clear, with no grab handle and no close button. Esc and the scrim close it.
- `frontend/src/features/my-work/CaughtUp.tsx`: empty Needs me.
  - Tola's image sits beside "Nothing needs you right now", the moving count with the WhatsApp line, and "See what you started".
  - On desktop, "Where your work is" is grouped by `waiting_on`.
  - New `WhileYoureFree` aside: an agent avatar, "While you're free / {Agent} can get these ready. You check each one before it goes anywhere.", and per suggestion the title, detail, an action link and "Not now". "Not now" only hides the suggestion on screen; there is no endpoint.
  - Layout follows the board: two columns on desktop, stacked and centred on phones.
- `frontend/src/features/my-work/MyWork.tsx`:
  - Keeps `suggestions` from the latest response and passes it to `CaughtUp`.
  - Adds the records line, the "My work" tablist name, and the four filters in the URL, query, badge and chips.
  - Hides the toolbar on the caught-up view.
  - Makes the Filter button dark while the panel is open.
- `frontend/src/features/my-work/model.ts`: `project` and `waiting` in the view. Adds `WAITING_ON`, `AGENTS`, `AGENT_AVATAR` (the base's `public/agents/*.png`), `filterCount`, `recordsText` and `lineOptions` by key. Adds `Suggestion` and `WorkListWithSuggestions`, typed locally and marked PROPOSAL.
- `frontend/src/features/my-work/my-work.css`: board sizes and spacing, token variables only. This round adds:
  - the caught-up two-column layout and the "While you're free" panel;
  - the phone caught-up layout, centred, with a 150px mascot and 48px buttons;
  - the phone sheet title and spacing, and a desktop chip row as tall as a chip;
  - phone cards at 15px.
- `frontend/mock/work-list.mjs`: filters by `line` key, `project` and `waiting_on`; returns `filters.lines`; rejects empty optional params and unknown `waiting_on` (QA-2-1). With cookie `psl_mock_worklist=board` it serves `E-WORK-LIST.board.json`, which is the boards' rows, counts, lines and drawn order; for pm this includes `suggestions`.
- `frontend/mock/server.mjs`: the E-WORK-LIST branch passes `dataset: cookies.psl_mock_worklist`.
- `frontend/mock/fixtures/E-WORK-LIST.rows.json`: `line_key`, `agent`, and mock-only `project` and `waiting` keys. Ids, titles, states and counts are unchanged. `E-WORK-LIST.board.json` is new; its ids are W-14xx.
- Tests:
  - `tests/mock-work-list.test.ts` validates against v4. `suggestions` is checked separately as the proposal and must be absent outside the board sample.
  - `tests/my-work-model.test.ts`, `tests/my-work.test.tsx` (38 tests: suggestions shown, Not now, absent means no panel, mascot images, the four filters, the caught-up groups) and `e2e/my-work.spec.ts` are updated.
- Factory files:
  - `delivery/features/F-02/round-3/fidelity/` holds each board's report.json and side-by-side.png, `scores.txt`, and `_driver/` (the driver, actions, `runall.sh`, and `prod.sh` for production-build scoring).
  - The earlier `proposed-exceptions.json` is superseded by the coordinator's D-17 file.

## Contract proposal (for the architecture)
E-WORK-LIST 200 gains an optional top-level `suggestions`:

```
suggestions?: Array<{ id: string; agent: 'tola'|'chidi'|'zainab'; title: string; detail: string; action: string; href: string }>
```

These are agent suggestions for a person with nothing in Needs me ("While you're free", SCR-01-*-empty). The person checks each draft before it goes anywhere. A "Not now" dismissal would need its own endpoint; it is not built.

The field is not in v4 or v6. The mock sends it only with `psl_mock_worklist=board`, and the frontend types it locally in `model.ts` (`WorkListWithSuggestions`).

## Fixes
- FID-1 | b5873de, c5a9264, 3424065, 27f8cd8, 02d59d8 | My work rebuilt to the SCR-01 boards. This round adds "While you're free" and closes the spacing and typography differences on the empty, filter and phone views. Scores are below.
- Coordinator note (agent avatars) | fc1d213, 3424065 | The base's `public/agents/*.png` (PR #12) is merged and used with alt text; I kept no copies of my own.
- Coordinator decision 2 ("While you're free") | 27f8cd8, 02d59d8 | Built from the proposed `suggestions` field on the board sample; hidden when the field is absent.
- QA-2-1 | b5873de | The mock answers `q=`, any other empty optional parameter, and an unknown `waiting_on` with 404 invalid_query.

## Acceptance criteria
1. [x] Tabs and counts: component test (24/12/6/2 in `.psl-badge`); e2e default at 390 and 1440.
2. [x] Unassigned only when present: component test; e2e pm shows 3 tabs; the tablist scrolls at 390.
3. [x] Each tab requests its queue; keyboard works: component tests.
4. [x] Kinds come from the API: component and mock tests.
5. [x] State words and families: unit test (sentence case, approved).
6. [x] Station bar and age: unit tests.
7. [x] Sample labels: component test. The tag stays off unless `NEXT_PUBLIC_SHOW_SAMPLE_LABEL=1`.
8. [x] Row links: component tests for table, cards and started cards.
9. [x] Search: fake-timer test; e2e no-results. The mock refuses `q=`.
10. [x] Filters (FID-1: Line by key with checkboxes, Project, State, Waiting on, "Show N items", chips, Esc/scrim): component tests and e2e at 390 and 1440 (`line=invoice&state=action_needed`, "Show 2 items", axe clean).
11. [x] Paging and 10/20/50: component and e2e tests.
12. [x] URL restore and no browser storage: component tests, including project and waiting_on.
13. [x] Polling: fake-timer test.
14. [x] A refresh keeps rows: component test.
15. [x] A failed refresh keeps the screen: component tests.
16. [x] Empty for pm (FID-1: the caught-up view): component and e2e tests. "While you're free" appears when suggestions are present (component test, and the fidelity runs on the board sample). With no suggestions the panel is absent (component test).
17. [x] Wrong role: e2e and mock tests.
18. [x] Load failures: component tests and e2e.
19. [x] Loading: component test and e2e (reduced motion, axe).
20. [x] The mock honours the query and stays on contract (v4), apart from the proposed `suggestions` on the board sample: `tests/mock-work-list.test.ts`; `mock-contract.test.ts` is unchanged and passes.
21. [x] Accessibility: e2e suite, 83 passed, 0 failed, with axe at 390 and 1440 for every state.
22. [x] Product acceptance items: rows-per-page footer in `round-3/fidelity/SCR-01-desktop-1440/side-by-side.png` and `SCR-01-mobile-390/side-by-side.png`; filter panel in `SCR-01-desktop-filter-1440` and `SCR-01-mobile-filter-390`.

### Fidelity (final)
Settings: exceptions are `delivery/features/F-02/fidelity-exceptions.json` (D-17). The page is a production build (`next build` + `next start`, so no dev overlay) on 3301 with the mock on 3302 and the cookie `psl_mock_worklist=board`. The empty boards add `psl_mock_persona=pm`. The filter boards apply Line "Invoice preparation and delivery" and State "Waiting", then reopen the panel.

| board | width | coverage (after exceptions) | visual | pass |
|---|---|---|---|---|
| SCR-01-desktop | 1440 | 100 | 92.2 | yes |
| SCR-01-desktop-my-work | 1440 | 100 | 91.0 | yes |
| SCR-01-desktop-empty | 1440 | 100 | 91.0 | yes |
| SCR-01-desktop-filter | 1440 | 100 | 83.6 | no |
| SCR-01-mobile | 390 | 100 | 81.1 | no |
| SCR-01-mobile-my-work | 390 | 100 | 90.1 | yes |
| SCR-01-mobile-empty | 390 | 100 | 73.0 | no |
| SCR-01-mobile-filter | 390 | 100 | 95.1 | yes |
| SCR-01-mobile-lead | 390 | 100 | 81.1 | no |

The phone top bar is a frame item on every 390 board: the page has a menu button and no orange Start, and its "My work" title sits about 4px lower than the board's. It costs a band of squares at the top of each phone score. On desktop, the missing top-bar Start work (F-05) is excepted, but it still counts in the visual score.

Boards still under 90, and why:
- **SCR-01-desktop-filter (83.6).**
  - The board's table draws two static invoice rows with no kind tag and no footer. With Line "invoice" and State "Waiting", the board sample has one matching row, which shows its kind tag and the approved rows-per-page footer. Adding the board's second row back would push the passing desktop and phone boards' row counts off their boards.
  - The page title from the frame sits about 4px lower than the board's.
  - The remaining panel geometry matches to within a few pixels.
- **SCR-01-mobile and SCR-01-mobile-lead (81.1).**
  - The approved rows-per-page footer is a 100px block where the boards are empty, which alone accounts for most of the gap.
  - Then the frame's phone top bar.
  - Card size, order and type now match the boards. The cards, tabs and search line up within about 6px, and that offset comes from the frame.
- **SCR-01-mobile-empty (73.0).**
  - The approved heading "Nothing needs you right now" wraps to two lines at 22px where "You're all caught up" fits on one.
  - The excepted orange Start work button is absent.
  - The board's Tola image is a design-canvas blob that does not render locally, so the board shows an empty pink area where the page shows the mascot.
  - The page lists the third suggestion where the phone board draws two.
  - The frame's phone top bar.

## Validation
- `cd /Users/Hunchoo/psl-factory-worktrees/f-02 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh`: exit 0 on 02d59d8. Django check is clean; lint, typecheck, vitest (13 files, 328 tests) and `next build` pass.
- `cd frontend && E2E_PORT=3301 MOCK_PORT=3302 npm run test:e2e`: exit 0, 83 passed, 0 failed, on the same tree.
- Fidelity: `round-3/fidelity/_driver/prod.sh` then `runall.sh`; scores are in `round-3/fidelity/scores.txt`. I started my own production servers on 3301 and 3302 and stopped them afterwards. `frontend/test-results` is deleted, and disk had 10 GB free at the end.

## Blocked
Not blocked. These items are open for the design engineer or architecture:
- The 3 boards under 90 visual, for the reasons above. Most of the gap is approved or frame-owned: the rows-per-page footer, the phone top bar and Start work, the heading wording, and the board image that does not render locally.
- The D-17 exceptions are provisional, so the design engineer's confirmation is still needed.
- The `suggestions` field needs architecture adoption (see Contract proposal), and "Not now" needs an endpoint to persist.
- The Line filter keeps one line at a time because the contract's `line` takes one key.
- The Project select offers only "Any project" until F-07's mock serves E-PROJECTS.
- "Records you can see" is the sum of the queue counts, an engineering derivation.
