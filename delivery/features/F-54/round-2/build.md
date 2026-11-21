STATUS: READY
COMMIT: a656fac3d2c609b92eb41f22c1d13802484a50bb
BUILDER: builder
LANE: full

## Summary
- Round-1 blocking findings fixed: the conversation list keeps loaded pages after a send, start or end (TECH-1-1); Projects and Payments pass the total (TECH-1-2, QA-1-1); the infinite-scroll sentinel now fires at window heights 500, 700, 800 and 900 (UX-1-1).
- The non-blocking findings are done too, except TECH-1-4 which is accepted (see below).
- The footer now owns the one "couldn't load more" notice; every per-list notice and wrapper style is gone.
- D-143 and D-144: focus is the control's own edge turning blue in place, set centrally in the design bundle; no stylesheet in src sets an outline with the focus colour, and a test enforces it.

## Changes
- `components/ShowMore.tsx`: `usePagedRows` stops the automatic top-up after a page that adds no rows, reverts the selected size after a failed larger choice, passes `failed`; the footer shows "We couldn't load more. Choose Show more to try again." (role alert) and keeps the pending focus per footer instance (a ref, no module global). `limitFor` documents that the contract allows only 10, 20 or 50.
- Lists: Projects and Payments pass `total`; MyWork, Projects, Clients, Payments, Exceptions, Notifications, project tabs, record picker and Setup lose their own failure callouts and wrappers (`.my-work__foot`, `.projects__foot`, `.ptabs__foot`, `.clients__more`, `.payments__more`, `RowsFailed`, `PagingNotes` failed text). `projects/model.ts` comment says 10.
- `assistant/useConversationList.ts`: a refresh merges page 1 at the top and keeps the later pages and their cursor. `ConversationList.tsx`: sentinel is 1px tall (`.as-list__end`) with a 48px bottom `rootMargin`.
- `mock/exceptions.mjs`: hr is refused (403) like pm; `tests/mock-contract.test.ts` follows.
- Focus (D-143/D-144): `design/system/project/components/bundle.css` (the source of `styles/psl-bundle.css`, regenerated with `npm run gen:styles`) has one central rule: every `:focus-visible` control gets `outline: none` and a 2px inset edge in `var(--focus)` (the design system already draws button and chip borders as inset shadows, so this replaces the edge colour in place and nothing moves); text fields, selects, wrapped fields, the drop zone, checkboxes and radios change their own `border-color`; the composer box changes only on `:has(textarea:focus)`; links in running text get a 2px blue underline; the edge has no transition. `components.css` and the feature stylesheets lose every `outline … var(--focus)` and focus `outline-offset` rule (alerts, assistant, clients, floor, payments, response, setup, start-work, work-item, workspace).
- Tests: `tests/focus-rules.test.ts` fails if any stylesheet under `src` sets an outline with `var(--focus)` / `var(--focus-on-strong)` or an `outline-offset` on a focus state.

## Fixes
- TECH-1-1 | fixed | `useConversationList.refresh` merges page 1 into the loaded rows and keeps `next`; unit tests in `tests/conversation-list-merge.test.tsx` (pages 1+2 loaded, refresh, rows and cursor kept; page-1-only refresh takes the new cursor). Commit "Footer owns the failure notice; stop empty top-ups; per-footer focus; totals ...".
- TECH-1-2 | fixed | Projects `total` (response total or tab count) and Payments `body.total` go to `usePagedRows`; the footer reads "10 of N showing" and applies the inactive rule. Projects e2e/unit tests use "Show N more".
- QA-1-1 | fixed | same change as TECH-1-2 (Projects with `total: 15` disables 50; 74 reads "10 of 74 showing").
- UX-1-1 | fixed | sentinel is 1px with `rootMargin: 0px 0px 48px 0px`; e2e `...(D-138, window 500/700/800/900px)` in `e2e/assistant.spec.ts` passes at all four heights.
- TECH-1-3 | fixed | `asked` ref in `usePagedRows`; unit test "does not ask again after a page that added no rows".
- TECH-1-4 | accepted | the contract's `limit` is only 10, 20 or 50, so a request can load a few more rows than are shown (for example 30 missing rows ask for 50); the extra rows wait unseen until the person asks for them. Noted in `limitFor`.
- TECH-1-5 | fixed | pending focus is a ref per `ShowMore`; the module-level variable is gone.
- TECH-1-6 | fixed | `projects/model.ts` comment.
- TECH-1-7 | fixed | one shared notice in the footer, wording "We couldn't load more. Choose Show more to try again."; the per-list callouts, wrappers and their CSS are removed; unit and e2e tests follow.
- QA-1-2 | fixed | after a failed larger choice the selected option returns to the size shown (unit test "a larger choice that fails goes back").
- QA-1-3 | fixed | the mock answers 403 for hr on E-EXCEPTIONS.

## Acceptance criteria
9. [x] Text-field focus and D-144: computed outline is none and the edge is the focus colour for an input (clients detail), the search (My work), the composer (box blue on textarea focus, unchanged when a button inside has focus; the button shows its own edge), a button, a tab, a checkbox (border), a table row link and a link (underline). Box size and position are identical before and after for fields (e2e `text-focus.spec.ts`). Screenshots at 1440 in `delivery/features/F-54/round-2/screenshots/focus/`: focus-field, focus-search, focus-composer, focus-button, focus-tab, focus-checkbox, focus-table-row, focus-link. Contrast: blue #2459D6 on white is about 6:1.
   - Exception (documented): filled dark or coloured controls (primary, dark and confirm buttons, selected segmented options and tabs, the dark top bar, the send button) show the edge in `--focus-on-strong` (white), because a blue edge on a dark or blue fill cannot be seen. Plain text buttons and links use the underline.
   - Inset edges are used for borderless controls (rows, cards, tabs, chips, icon buttons) as the spec allows; there is no outline and no offset anywhere.
   - Because the edge is a 2px inset shadow with `!important` and no transition, a control that already used an inset shadow as its resting edge (secondary button) shows the blue edge in the same place.

## Validation
- `npm run lint` clean, `tsc --noEmit` clean, `vitest run`: 140 files, 3415 tests pass.
- e2e (production build, my own ports): assistant, text-focus, work-item, work-item-board, my-work, projects, exceptions, setup (all), alerts, clients, project-tabs, payments, start-work, workspace, history-link, frame, conformance: all pass in the last runs (a first run had focus-helper failures from the old outline assumptions and a transition on the edge; fixed by removing the transition and having the old specs read the edge, then re-run: 330 passed, then the two remaining specs fixed and re-run green).
- The old e2e focus helpers that read `outlineStyle`/`outlineWidth` now read the edge (outline, else a focus-coloured inset shadow, border or underline) so their assertions keep their meaning.
- Not re-run on the final head: the full `checks.sh` (npm ci would wipe node_modules under the live dev server); its steps (lint, typecheck, vitest) were run directly, `next build` last ran in the e2e web server on this head's sources.

## Notes for the coordinator
- `psl-bundle.css` is generated from `design/system/project/components/bundle.css`; the focus change was made in that source (the styles-drift test requires it) and regenerated.
- Round-1 items D-138 to D-142 are unchanged from the round-1 build.md.
