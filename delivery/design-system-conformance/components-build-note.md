STATUS: READY
COMMIT: c144c91c5e0efe44abd04b94a8b796eaafcf358a
BRANCH: ds-components
BUILDER: builder
LANE: frontend

## Summary
- `frontend/src/components/` is the shared React library (D-91 step 2): 40 design-system components plus the audit's foundations (formatters, Money/When, PageTitle, VisuallyHidden, useIsPhone). Import from `@/components`.
- Markup and classes follow each `design/system/project/components/<Name>/` spec and `psl-bundle.css`. `components.css` adds only what the bundle lacks, as `cmp-*` classes (or `psl-*` narrowed by `cmp-*`), so screens still written by hand look the same.
- Tokens (D-92a): `tokens.json` gains spacing 10/14/18/20 (`--space-10px` … `--space-20px`), z-index (`--z-pop/overlay/toast`) and motion (`--motion-fast`, `--motion-station`, `--ease-out`). `gen-styles.mjs` now also writes every named text style as `--text-<name>-size/-line/-weight`. tokens.css is regenerated and the drift test passes. psl-bundle.css is unchanged.
- 75 component tests in `frontend/tests/components/` (22 files): render, states, keyboard, axe with the project's setup. No feature migrated; the components are not used anywhere yet.
- `bash delivery/checks.sh` passes (1631 tests, lint, typecheck, build).

## Components (spec folder · tests in file)
Tests per file: button 7, icon 2, link 1, callout 3, tag 3, count-badge 1, sample-label 1, panel 1, text-field 3, select 3, date-field 4, money-field 5, checkbox-radio 3, segmented-tabs 3, menu 4, search-toolbar 2, file-upload 5, overlays 5, toast-tooltip 3, table 3, lists-and-states 6, domain 7.

| Component | Spec | CMP | Test file |
|---|---|---|---|
| Icon (all 23 icons) | Icon | | icon |
| Button (7 kinds, 4 sizes, busy keeps width and ignores presses, disabled with reason), BusySquares | Button | | button |
| IconButton (aria-label, bare, count) | IconButton | | button |
| Link, RestrictedLink | Link | | link |
| Callout | Callout | CMP-24 | callout |
| Tag, StateTag/STATE_TAGS, PriorityTag | StateTag | CMP-05 | tag |
| CountBadge | CountBadge | CMP-06 | count-badge |
| SampleLabel | SampleLabel | CMP-16 | sample-label |
| Panel | Panel | | panel |
| TextField, TextArea (grows to 240px, count) | TextField, TextArea | | text-field |
| Select (select-only combobox, aria-activedescendant, typeahead) | Select | | select |
| DateField + calendar grid, parseDate | DateField | | date-field |
| MoneyField (null = Unknown, '' = empty, exact digits) | MoneyField | | money-field |
| Checkbox (mixed), RadioGroup (radios, choice cards) | Checkbox, Radio | | checkbox-radio |
| Segmented (Home/End, skips disabled), Tabs (link or button tabs) | Segmented, Tabs | CMP-06 | segmented-tabs |
| Menu, MenuButton, useMenuButton | Menu | | menu |
| SplitButton | SplitButton | CMP-23 | menu |
| SearchField (2 chars, 200ms), ListToolbar, FilterPanel (popover / bottom sheet) | SearchField, ListToolbar | CMP-22 | search-toolbar |
| FileUpload (the one proof field) | FileUpload | CMP-20 | file-upload |
| Drawer (500px; sheet below 720px), BottomSheet (swipe), Dialog (alertdialog) | Drawer, BottomSheet, Dialog | CMP-23 | overlays |
| Toast (status vs alert, 6s, held on hover/focus), Tooltip (300ms) | Toast, Tooltip | | toast-tooltip |
| Table (sort, select-all mixed, bulk bar, totals, empty sentence) | Table | | table |
| ShowMore, Loading/Skeleton/EmptyState/ErrorState/Progress, Breadcrumb, Disclosure, ValidationSummary, PageTitle, VisuallyHidden, When | ShowMore, Loading, Breadcrumb, Disclosure, ValidationSummary | CMP-07 | lists-and-states |
| AgentAvatar, PersonAvatar, AgentChip | Avatar | CMP-18 | domain |
| FactsStrip | FactsStrip | CMP-04 | domain |
| StationTrack, MiniStationBar | StationTrack, MiniStationBar | CMP-02, CMP-03 | domain |
| AgentChecklist | AgentChecklist | CMP-09 | domain |
| PhoneActionBar | PhoneActionBar | CMP-11 | domain |

Not built, because no feature implements them (D-91 domain rule): DecisionPanel (only PhoneActionBar from it), WorkList (My work uses a table), SourceTag, DraftCard, ChatMessage, TopNav, AlertMessage.

## Calls I made (coordinator's D-92 message)
- Callout roles: info and warning have no live role. Problem is `role="alert"` and success `role="status"` only when `announce` is true (the default, for a callout shown after an action). Pass `announce={false}` for a problem that is part of the page as it loads.
- Effect uncertain is amber (waiting) in `STATE_TAGS` (D-92b). Ready to continue is green (done), as the StateTag page draws it.
- 44px on phones (D-92c): small buttons (`cmp-btn-sm`), checkbox/radio rows and link-buttons grow to `control-md` below 720px. Desktop keeps 40px.
- Drawer is the bundle's 500px (D-92d).

## Spec gaps and conflicts (spec vs bundle.css or preview)
1. Table README: the current row is an "orange left edge on signal-tint", but the bundle's `tr.is-current` is only the edge, with no tint. I followed the bundle.
2. AgentChecklist preview: the done-step tick is drawn with `stroke="#FFFFFF"`, a literal colour. I used `currentColor` with `--on-strong` (`cmp-steptick`).
3. Several preview helpers are inline styles the bundle doesn't have. I added them as cmp classes: agent panel text `action-ink`, read-only panel head rule `rule-soft`, restricted file row border, filter-panel head/body/foot, sheet title, Restricted link gap.
4. MiniStationBar preview uses `i.t` for "not started". The bundle has no `.t` rule; the base `rule-soft` grey applies, so it looks right.
5. IconButton count: the preview puts the badge outside the button in a wrapper. The bundle positions `.psl-iconbtn .psl-badge` inside the button. I followed the bundle (badge inside, `aria-hidden`; the label says "Filter, 2 on").
6. Tabs preview uses `<nav role="tablist">`. jsx-a11y rejects an interactive role on `nav`, so it's a `div role="tablist"` (as ProjectTabs does). Classes are unchanged.
7. DateField preview puts `aria-selected` on day `<button>`s, which ARIA doesn't allow. Days are `role="gridcell"` spans inside `role="row"` wrappers (`display: contents`). The classes and look are the bundle's.
8. The bundle has no focus rule for inputs wrapped in a `.psl-input` box (money, date). I added `.cmp-wrapped:focus-within` so the ring sits on the box, as the spec draws it.
9. ListToolbar's "Clear all" is drawn as `<a class="psl-link">`, but it's an action. It's a `<button>` styled as the link (`cmp-linkbutton`).
10. Checkbox spec wants 44px rows on phones; the bundle has 36px. Fixed in components.css under D-92c.
11. Select spec: lists longer than ~15 should get a search box. Not built (no caller needs it yet). RecordPicker remains the searchable picker.
12. Literal sizes left, each marked in components.css: the phone breakpoint (`719.98px`, since tokens can't be used in `@media`), 18px BottomSheet title and 26px phone page title (no text-style token at either size), and 1px for screen-reader-only text.

## What the migration must watch for
- Colour changes: features map `effect_uncertain` to amber already, but `ready` to orange (work-item/labels.ts). StateTag makes Ready to continue green, and the agent DONE tag blue (feature: green). Re-run fidelity on the screens that show them.
- Callout roles change: 16 warning callouts lose `role="alert"`. Decide per caller whether a problem is shown after an action (`announce`).
- Busy now means three squares plus a label; a busy button stays enabled-looking but ignores presses. Callers that pass `disabled` while submitting will look different.
- Small buttons outside the top bar become 44px on phones (`cmp-btn-sm`); expect height changes on phone boards.
- `Select` replaces native `<select>`: the value is a string or undefined, and the label is a `<span>`, not `<label for>`, so tests that use `getByLabelText` must switch to `getByRole('combobox', { name })`.
- `DateField` takes and returns ISO dates and shows "17 Nov 2026". It replaces `<input type="date">`; the value is '' while the typed text is invalid.
- `MoneyField` value is a string, '' for empty and null for Unknown; never pass 0 for unknown. Show amounts with `Money` (`sign={false}` in tables whose header says ₦).
- `FileUpload` refuses wrong types and files over 10 MB itself and calls `onFile` only for good files; `state` is the caller's upload state. Both ProofField copies map onto it.
- `Drawer` portals into document.body, focuses the first field and returns focus to the opener on unmount. Drop DrawerFrame's and AlertsDrawer's own traps; the alerts drawer becomes 500px (D-92d).
- `Tabs`/`Segmented` add Home/End. Link tabs keep their hrefs; the "Rows per page" segmented bars are still a D-PAGING exception to ShowMore.
- FactsStrip writes "RECEIPT RECORDED" (the spec), where the work-item boards print "RECEIPT", and "Not yet" where the feature draws "—". The boards decide which wins.
- `cmp-*` classes need `components.css`, which every component imports through `internal.ts`. VisuallyHidden imports it itself.
- One feature test, `tests/setup-templates.test.tsx` ("success (AC 8) … moves focus to the row"), failed once in a full gate run under load and passed alone and in the next full run. Treat it as flaky, not as caused by this branch (no setup code was touched).

## Validation
- `npm ci` in the worktree's frontend/ (disk 7.7 GB free before, 7.8 GB after).
- `npx vitest run tests/components`: 22 files, 75 tests, all pass.
- `bash /Users/Hunchoo/psl-factory/delivery/checks.sh` (worktree): exit 0. Django check, lint (0 warnings), typecheck and build all pass; 1631 tests.
- No dev-server or fidelity run: no screen uses the components yet. Fidelity belongs to the migration rounds.
