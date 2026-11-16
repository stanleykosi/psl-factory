STATUS: READY (with the open items listed under "Open decisions")
COMMIT: ec66d08c05e776c207a1da0627cdad6ec7ee7c62
BRANCH: ds-migrate-3
BUILDER: builder
LANE: 3 (setup, alerts, finance month-end, overview, floor)

## What changed
- Setup (rules, finance, delivery, templates, Set a rule, upload panel), alerts (bell drawer, Notifications, Alert settings), Month-end, Overview and the floor now use `@/components`: Button, Callout, Tag, SampleLabel (TEST TEMPLATE), Panel, Tabs (+CountBadge), Table, ShowMore, SearchField, ListToolbar + FilterPanel (+RadioGroup, Checkbox), Select, DateField, TextField, TextArea, FileUpload, Segmented, Drawer (500px, sheet below 720px), PageTitle, Breadcrumb, EmptyState, ErrorState, Loading/Skeleton, AgentAvatar, Link/RestrictedLink, VisuallyHidden, When, Unknown, formatters.
- Deleted private copies: `setup/ProofField.tsx`, `setup/icons.tsx`, setup date/size formatters (`lagosDay`, `lagosStamp`, `formatSize`), `alerts` mascot-image helper and the drawer's own focus trap/scrim/animation, `overview` avatar table, month-end `Image` avatar. `.setup-sr`, `.alerts-sr`, `.overview__sr` classes gone (VisuallyHidden/`cmp-sr`).
- Colour meaning: Setup panels and the upload panel are ink-bordered (blue only on agent panels); month-end count strip has neutral boxes with coloured numbers (no green DONE fill); restricted tags are neutral, uncertain is amber on Overview; NEW tag is neutral; unread tint stays on rows.
- Dates "17 Nov 2026" / "14:30 WAT" everywhere in the lane; money unchanged (board shows "₦4.7M").
- Rule-save and template-upload guards unchanged (`useRuleSave`, `useTemplateUpload`, double-submit refs, uncertain-effect lock, 409/422/network paths). Buttons use `busy`, not `disabled`, while submitting.
- Alerts drawer = shared `Drawer`: 500px, full height under the scrim, sheet on phones; Close is the icon button (44px on phones via a lane rule).
- Shared files touched: none outside the lane. `alerts/useIsPhone.ts` is kept as a one-line re-export of `useIsPhone` because `shell/AppShell.tsx` and `clients/ClientsList.tsx` still import it: delete it after those lanes move.

## Validation
- `bash delivery/checks.sh`: exit 0 (lint 0 warnings, typecheck, 1630 unit tests, build).
- e2e for the lane (alerts, alerts-bell, finance-month-end, overview, setup, setup-templates): 137 tests, all pass (129 in the full run; the 8 that needed edits re-run and pass).
- Servers on 4921/4922 stopped by PID; test-results and .next removed.

## Tests changed (reason; none weakened)
Unit:
- alerts-model: meta times end in " WAT", older days carry the year, `agentImage` removed with the function (AgentAvatar replaces it).
- alerts: "Loading…" text replaces `role=status` wait (the result count is a status now); `.psl-resultcount`; Filter button name "Filter 1 on" and no `aria-haspopup`; Esc fired on the panel; error text has no "ERROR · COULDN'T LOAD" eyebrow; "Last loaded 15 Nov 2026 11:00 WAT"; NEW tag is neutral; avatar class order.
- alerts-bell: Esc on the dialog; scrim is `.psl-scrim`; footer is `.psl-drawer__foot`; Open buttons are `psl-btn` (secondary = outlined); focus lands inside the dialog (Drawer focuses its panel, not Close); phone tabs: arrows move focus, click/Enter chooses; grab is `.psl-sheet__grab`; removed "drawer top offset" test (the drawer is now full height by D-92d).
- alerts-settings: Select/combobox instead of `<select>`; `aria-busy` instead of `aria-disabled` while saving; stale (warning) callout has no `role=alert`, found by text.
- finance-month-end: state words from StateTag (sentence case), restricted tag neutral, "Month-end counts" region, "UPDATED 10:42 WAT".
- overview: `.cmp-sr`, avatar alt "" (decorative), uncertain amber, ISO-style date "14 Nov 2026 16:40 WAT", error card text, `h1` inside `header`.
- setup-rules/setup-templates: tabs are `role=tab` with `aria-selected`; Select/DateField ("14 Nov 2026") / FileUpload ("choose a file"); version text "since 1 Oct 2026"; warning outcome callouts found by text (no `role=alert`); sizes "18 B" (component formatter); `formatSize`/`lagosDay`/`lagosStamp` tests removed with the functions; proof: a second file needs Remove first; new test: `.exe` refused by the field with no request; template note counter shows only while no error.
e2e: same reasons (status-wait helper, tabs, Select, drawer 500px/full height, WAT/year text, Try again outside the alert).

## Fidelity (before = last recorded, after = this branch, production build, FRAME_FIXTURES=1; each feature's own exceptions)
| Board | Before | After | Notes |
|---|---|---|---|
| F-08 SCR-06 desktop 1440 | 94.1, 100% cov | 93.6, 96.9% cov | Segmented's "Flat"/"3D floor" not read by the tool (see open 1); title kept at the board's 40px |
| F-08 SCR-06 mobile 390 | 89.8 | 92.1, 100% cov | up |
| F-10 SCR-36 desktop | 97.8 | 91.4, 100% cov | D-92 colour: count strip no longer fills DONE green / WAITING amber |
| F-10 SCR-36 mobile | 97.3 | 90.4, 100% cov | same strip is desktop-only; phone drop is the 44px/tag-size and card height of Tag/Table |
| F-11 SCR-13 desktop rules | 93.4 | 88.5, 100% cov | D-92 colour: Set a rule panel head no longer solid blue; Select/DateField/FileUpload look |
| F-11 desktop finance rules | 96.2 | 97.2, 96.6% cov | Breadcrumb text (open 2) |
| F-11 desktop delivery rules | 97.9 | 94.3, 97% cov | Breadcrumb text (open 2) |
| F-11 mobile rules / finance / delivery | 99.8 / 99.1 / 99.7 | 97.8 / 94.9 / 93.7 | cov 93.3 / 88.9 / 75% with exceptions: frame links "Start" (shell, + Start from D-90) and "Back to Setup" (requested exception) |
| F-12 SCR-15 desktop | 97.8 | 95.7, 100% | NEW tag neutral (D-92 colour) |
| F-12 SCR-15 mobile | 92.9 | 92.3, 100% | same |
| F-12 SCR-15 desktop settings | 96.4 | 97.1, 100% | |
| F-12 SCR-15 mobile settings | 97.6 | 97.8, 100% cov | |
| F-20 SCR-34 desktop | 95.9 | 95.6, 100% | SampleLabel dashed amber (D-92 colour) |
| F-20 SCR-34 mobile | 78.8 (waived D-78) | 80.1 | still under 90, waived |
| F-15 bell | no board | screenshots at 1440/390 checked | drawer 500px |
Not all drops are from D-92: F-10 mobile, F-11 mobile and F-11 desktop delivery are the library's Tag/Table/Breadcrumb/Select look against the boards; I kept the board's page-title sizes by lane CSS (Overview 40px, month-end and Setup phone 22/20px, settings phone 24px) rather than take the system's single title size, because the boards are the spec. Say if you want the system size instead.

## Open decisions / library findings
1. `Segmented` options carry no accessible name beyond the text, and the fidelity tool reads radio names only from labels: the two Overview View switch items ("Flat", "3D floor") count as missing (F-08 desktop 96.9%). Fix is an `aria-label` on each option in the component, or an exception.
2. `Breadcrumb` renders links and aria-hidden separators, so the tool no longer finds the single board text "SETUP / RULES / FINANCE" (finance and delivery desktop). Needs a library change or an exception.
3. `Table` cannot hold an expanding row, so the Templates list keeps its own `psl-table` with the inline upload panel row.
4. FileUpload types: template upload is limited client-side to .docx, .xlsx, .pdf (my call; the server still checks) and the proof field to the library default (PDF PNG JPG EML, 10 MB). A person can no longer replace a chosen proof without pressing Remove.
5. Tag/State: "HOLDS WORK" and "NOT SET" stay as the board words in orange (person) tags; the rules list's plain "Not set" stays amber text as the board draws it.
6. `Tabs` (button tabs) move focus with the arrows but choose on Enter/click (alerts drawer on phones; the old drawer chose on arrow).
7. Esc closes the Drawer only while focus is inside it (library behaviour; the old drawer listened on the document).
8. Fidelity exception files: F-08's "FACTORY FLOOR · UPDATED 14 Nov 16:40 WAT" request now reads "UPDATED 14 Nov 2026 16:40 WAT".
9. Phone frame links "Start" and "Back to Setup" are shell-owned and still missing from the F-11/F-20 phone exceptions lists.

## Where pages now differ from their boards because of the design system
- Dates/times: "1 Oct 2026", "10:42 WAT", "AS OF 12 NOV 2026 10:40 WAT" (boards: "01 Oct", "10:42").
- Colour: Set a rule / upload panel head ink not blue; month-end strip neutral; NEW tag grey; restricted tags grey; "Effect uncertain"-type tags amber on Overview; TEST TEMPLATE dashed amber label.
- Controls: Select (listbox) and DateField (text + calendar) replace native select/date; proof drop zone states the types and size; Filter button shows "Filter 2 on"; shared ShowMore text ("50 showing"); error cards lose the "ERROR · COULDN'T LOAD" eyebrow; avatars 32/20px (were 36/24); Notifications result count hidden on phones.
- Alerts drawer: 500px full-height drawer with a scrim over the top bar (was 420px under the bar), icon Close.
- Month-end: tag words from the state list in sentence case when the backend sends no label.
