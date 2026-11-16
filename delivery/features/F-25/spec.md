# A project's Milestones, Registers and Actions tabs show their rows, read-only (contract mock only)

> Tasks: FE-M3-PROJECT-TABS (R-PROJECT; acceptance A-PROJECT-TABS frontend half, with A-PROJECT and the F-07 tests kept green). Architecture: package `architecture/packages/v7`, manifest.sha256 `f6231d20b4fdeabbdca9bde5986a0a7883536f1a5cafc883848ef62dd6d4b624`, openapi.json info.version `0a4f10a08cfe`; FE-M3-PROJECT-TABS at `architecture/packages/v7/delivery.md:1471`, "Unresolved gates: none". E-PROJECT-TAB is typed in `frontend/src/api/schema.d.ts:2975` (this feature changes no generated type). Decision consumed: D-PROJECT-TAB-ROWS (proposed, `architecture/build_model.py:501`). Design: client-approved canvas version 1794581312-b166 (`design/review.json`, 13 Nov 2026; SCR-11, SCR-29, SCR-38 at lines 24, 42, 46), republished with "+ Start" as 1794762832-cab1 (D-89, D-90); `design.py check --project .` run for this spec: `EXCEPTION`, passes (design_sha256 `2859ab21…3d82`). Screens: SCR-38 (`default`, `changed`), SCR-11 (`default`; `empty` has no board), SCR-29 (`default`). Model: `delivery/features/F-21/spec.md`, `delivery/features/F-07/spec.md`.

## Outcome
A person on a project opens Milestones, Registers or Actions from the project tab bar and reads that tab's rows from E-PROJECT-TAB: milestones with contract amount, completion, invoice and paid as separate facts (and a change next to the milestone it changes); the issue, change, emergency and RFP registers with their counts and a search; the project's actions with their counts and a search. A row with a `work_id` links to its work item. Nothing is written from these tabs.

## Summary
- Three read-only tab panels mounted on the F-07 project page (`/projects/[caseId]/milestones|registers|actions`), replacing the "coming next" panel for those three tabs only. Documents and Money keep their current panel (Money is F-26).
- Every value comes from E-PROJECT-TAB (and the header from E-PROJECT). Unknown stays "Unknown", never 0 or blank; nothing is totalled or added; completion, invoice and paid are never inferred from one another.
- Built from the shared library (D-91): `Table`, `Tabs`, `ListToolbar`, `PriorityTag`, `Tag`, `Money`, `When`, `Unknown`, `ShowMore`, `EmptyState`, `SampleLabel`. One small general change to `ListToolbar` (Filter becomes optional).
- 8 boards scored with the fidelity tool at visual >= 90 and 100% coverage after approved exceptions. Controls with no contract field (Mark complete, Filter) are left out and listed as exceptions.
- Contract mock only. D-PROJECT-TAB-ROWS is a proposal; the backend developer may change or refuse any field; nothing is released.

## Boards
| Board | File (`design/canvas/project/`) | Page | Mock cookies |
|---|---|---|---|
| SCR-38 default, desktop / phone | `SCR-38-desktop.dc.html`, `SCR-38-mobile.dc.html` | `/projects/P-0101/milestones` | `psl_mock_persona=pm` |
| SCR-38 changed, desktop / phone | `SCR-38-desktop-changed.dc.html`, `SCR-38-mobile-changed.dc.html` | `/projects/P-0101/milestones` | `psl_mock_persona=pm,psl_mock_milestones=changed` |
| SCR-11 default, desktop / phone | `SCR-11-desktop.dc.html`, `SCR-11-mobile.dc.html` | `/projects/P-0101/registers` | `psl_mock_persona=pm` |
| SCR-29 default, desktop / phone | `SCR-29-desktop.dc.html`, `SCR-29-mobile.dc.html` | `/projects/P-0101/actions` | `psl_mock_persona=pm` |

All 8 are live URLs; no driver is needed (no state is reached by pressing anything).

## Conflicts with the boards (pending the design engineer)
Each item is a place where this spec would add, move or remove something a board draws. "Recommend" is what the builder builds if no answer comes before the build; each becomes a `fidelity-exceptions.json` entry with `approved_by: "builder proposal, pending design engineer"` until signed. Items 1 to 8 change what a person sees and need an answer; 9 to 16 are frame or data items to confirm.

1. **"Mark milestone 3 complete" (SCR-38 desktop and phone).** No field says which milestone may be completed or by whom (G-SCR38-2, G-SCR19-2); SCR-19 is FE-MILESTONE-COMPLETE. Recommend: **not drawn**, exception `no field`. Do not derive it from `/me` or from "first not-yet milestone".
2. **"Filter" (SCR-11 and SCR-29, desktop and phone).** E-PROJECT-TAB has only `register`, `q`, `cursor`, `limit` (G-SCR11-1, G-SCR29-1). Recommend: **not drawn**; search only, exception `no field`. Option B: a Filter button opening F-07's "Filters come next" panel (`ProjectsList.tsx`, `tests/projects.test.tsx:197`). Readiness asked for omission, so B needs the design engineer's call.
3. **Invoice cell text.** The board says "INV-0398 · verified" and "INV-0412 · awaiting Finance decision". The row carries `invoice.state` (an enum) and no human status text (G-SCR38-1). Recommend: `reference · <StateTag word>` from `STATE_TAGS` (`components/Tag.tsx:59`), e.g. "INV-0398 · Verified", "INV-0412 · Waiting". When the backend adds `invoice.status_label`, that text replaces the word. The wording and case differences are an exception `no field`.
4. **Changed board drops INVOICE and PAID (and the proof text).** `SCR-38-desktop-changed` draws MILESTONE, CONTRACT AMOUNT, COMPLETION, CHANGES and "Done 27 Oct" without proof. Recommend: **keep all five default columns and add CHANGES as a sixth** when any returned row has a non-empty `changes`, with the same completion text as default. Reason: completion, invoice and paid are separate facts (INV-FACTS); they should not disappear because a change exists. Extra columns are an exception. Option B: follow the board (the column set switches when any row has changes). G-SCR38-4 asks the same.
5. **Changed amount wording and the change sentence.** The board's amount cell reads "₦4,250,000.00 + the change · change amount Unknown until a SOW amendment is signed", and the footer "CR-0031 added work to milestone 3. The original ₦4,250,000.00 stands; the change's amount is Unknown until a SOW amendment with it is signed, and it isn't guessed." Recommend: the cell shows `<contract amount> + the change · change amount <Unknown tag | change amount>` composed only from returned values (never a sum); the clause "until a SOW amendment is signed" and the footer sentence are **not composed** by the frontend, because they state when an amount becomes known. They come only with a backend note (G-SCR38-3: `changes[].amount_note`, and a proposal `summary.note` for the sentence). Until then both are an exception `no field`.
6. **Changed phone board.** `SCR-38-mobile-changed` draws a different page: "← Project", "MILESTONES" in the top bar, h1 "Milestones", no tab bar, one card for milestone 3 with "CHANGED · CR-0031" and "Amount UNKNOWN". Recommend: the same phone list as the default board, header and tab bar kept, with milestone 3's card carrying a "CHANGED · CR-0031" tag (a link when the change has `work_id`) and the amount line of item 5. "Amount Unknown" alone is not drawn, because it reads as if the SOW amount were unknown. Exceptions `frame item` and `extra element`.
7. **Phone milestone cards leave out PAID.** `SCR-38-mobile` shows amount, completion and invoice only. Recommend: **show the paid line on the phone card too** (INV-FACTS: the phone must not hide a Finance fact the desktop shows). Extra element, exception.
8. **Rows that open their work item.** SCR-11 and SCR-29 draw rows as plain text; screens.md says "They open one to follow it up", and readiness asks that a row opens its work item when it has a `work_id`. Recommend: in Registers the WHAT text, in Actions the ACTION text, and in Milestones the invoice reference are links to `/work/<work_id>` only when the row carries `work_id`; plain text otherwise. The CHANGES reference is a link as drawn (SCR-31), again only with `work_id`. Link colour and underline differ from the board, exception `extra element`.
9. **SCR-11 header.** The board draws eyebrow "REGISTERS · LAGOON HEALTH", h1 "Issues, changes and RFPs" and no PM/route line; the phone draws h1 "Issues · 3" and "← Project". Recommend: **keep the F-07 project header on every tab** (breadcrumb "Projects / Lagoon Health", h1 = project `title`), as SCR-38 and SCR-29 draw it. Exception `frame item`.
10. **Register selector on the phone.** `SCR-11-mobile` draws no selector, so Changes, Emergencies and RFPs could not be reached on a phone. Recommend: the same register tabs as desktop, as the phone strip (`Tabs strip`). Extra element, exception.
11. **AGE "—" on a closed issue.** The board draws "—" for ISS-0221; the row simply has no `age_seconds`. The frontend cannot tell "closed" from "not known" without reading the state text, which readiness forbids. Recommend: absent `age_seconds` shows **"Unknown"** (INV-UNKNOWN, readiness binding rule), exception `no field`; contract proposal: a backend signal that age does not apply (e.g. `age_applies: false`), after which "—" is drawn as on the board (the D-94 "split by reason" pattern).
12. **"Changing an owner or due date is recorded with your name." (SCR-29).** No edit is drawn or exists (G-SCR29-2). Recommend: keep "Actions come from confirmed minutes." and **leave out the second sentence**, exception `no field`. Ask design whether it stays.
13. **Static rule sentences.** SCR-11 "Severity is set by the PM. Closing an issue needs QA and the PM; there is no separate approval." and SCR-38 "Milestones and amounts come from the signed SOW. Completing a milestone is the PM's fact; invoicing and payment are Finance's, and each is shown separately." Recommend: keep both as drawn (static copy restating source rules), listed in build.md for the backend developer to confirm (G-SCR11-3). The SCR-38 sentence also shows in the changed state (the changed board draws only the change sentence of item 5): extra element, exception.
14. **"As of" time.** No board draws `as_of`. AGENTS.md asks that counts carry their timestamp. Recommend: a muted "As of 12 Nov 16:40" line under each table (`When show="daytime"`, the boards' format), as F-26 does for Money. Extra element, exception. Option B: not shown.
15. **More rows than drawn.** SCR-29 desktop draws 7 of the 9 actions it counts, the phone 5; the fixture returns all 9 (a fixture that counts 9 and returns 7 with no cursor would contradict itself). Extra rows are an exception `sample data`.
16. **Frame items** (as F-07, F-14, F-22): top bar, signed-in name and role, "+ Start", phone back link and phone title ("← Projects" / "← Project", "Lagoon Health" versus the full title), tab counts on the phone tab bar, and the PM/route line position (drawn above the tab bar, rendered at the top of the panel as the Journey tab does). Exception `frame item`.

## Context
- Page and route: `frontend/src/app/projects/[caseId]/[tab]/page.tsx` mounts `ProjectJourneyPage` (`frontend/src/features/projects/ProjectJourney.tsx`). `ProjectView` draws the breadcrumb, `PageTitle`, `ProjectTabs` and one `role="tabpanel"`; the non-journey branch is `ComingNext` (`ProjectJourney.tsx:186-199`). Access and errors for E-PROJECT: `ProjectPage` (`:202`), `ProjectNoAccess` (`ProjectStates.tsx`), `SignedOutState`, `LoadingState` (`src/shell/FrameStates.tsx`), `WorkErrorCard` (`features/work-item/WorkItemStates`).
- Tab list: `PROJECT_TABS` in `features/projects/model.ts:31`, imported by `features/work-item/WorkItemView.tsx`. **Its shape and keys do not change.** Helpers reused: `textOf`, `pmNameOf`, `countOf`, `routeCaseId` (`model.ts:108-185`). Read hook model: `useProject.ts` (sequence guard, no polling).
- List patterns to copy: `ProjectsList.tsx` (URL state with `router.replace(..., { scroll: false })`, `SearchField` pause, `ShowMore` with `hasMore`, `useIsPhone` table/cards switch).
- Shared library (`frontend/src/components/`, D-91..D-93): `Table` (`Table.tsx:29`), `Tabs` (href tabs, `strip`), `ListToolbar` (`ListToolbar.tsx:20`, Filter currently required), `PriorityTag` (`■■■ High`, `Tag.tsx:39`), `Tag` and `STATE_TAGS`, `Money`/`When`/`Unknown` (`Values.tsx`), `formatAmount`/`groupDigits`/`formatDayMonth` (`format.ts`), `ShowMore`, `EmptyState`/`Loading`/`Skeleton` (`Loading.tsx`), `SampleLabel`, `CountBadge`.
- Contract: E-PROJECT-TAB `GET /api/v1/projects/{case_id}/{tab}` (`architecture/packages/v7/endpoints.csv:16`); E-PROJECT (`:15`) for `title`, `pm`, `route`, `tab_counts`. Gap notes: `delivery/backend-handoff/gaps-a-project-setup.md:66-78` (SCR-11), `:127-138` (SCR-29), `:167-179` (SCR-38).
- Mock: E-PROJECT-TAB answers 501 today (`frontend/mock/server.mjs:42` `M1_OPERATIONS` lacks it; asserted by `frontend/tests/mock-projects.test.ts:209`). E-PROJECT and visibility: `frontend/mock/projects.mjs`, rows and personas in `frontend/mock/fixtures/projects/list.json` (P-0101 Lagoon Health, visible to `pm` and `finance_lead`; P-0099 is the no-access id). `fixtures/projects/P-0101.json` already has `tab_counts {milestones 4, documents 6, registers 6, actions 9}`, `pm`, `route`.
- Tests that see the old panel: `frontend/tests/projects-journey.test.tsx:240-254` ("Milestones come next" case).

## Contract
Read-only. No write, no CSRF, no idempotency key. Every rule below is display only; the backend decides access, values and order.

### E-PROJECT `GET /api/v1/projects/{case_id}` (unchanged, already read by F-07)
Header (`title`, breadcrumb client), tab counts (`tab_counts`), and for Milestones and Actions the line "PM <pm.name> · <route>" (each part only when present, joined by " · "; hidden on phones as the Journey line is). A 401/403/404/5xx here keeps F-07's page states; the tab read is not made.

### E-PROJECT-TAB `GET /api/v1/projects/{case_id}/{tab}` (proposal rows, D-PROJECT-TAB-ROWS)
| | |
|---|---|
| Request | `tab` = `milestones`, `registers` or `actions`. Query: `limit: 20` always; `register` on the registers tab only (default `issues`); `q` only when the settled search has text (trimmed, never empty); `cursor` only for "Show more" |
| URL state | Registers: `?register=` (omitted for `issues`) and `?q=`; Actions: `?q=`. Unknown `register` values fall back to `issues`. Cursors are never written to the URL |
| 200 | Read the typed array named by the tab (`milestones[]`, `registers[]`, `actions[]`), `summary`, `next_cursor`, `as_of`. `items` is ignored. Rows show in returned order; nothing is sorted, filtered, counted or summed in the browser |
| Paging | `next_cursor` present: `ShowMore` with `hasMore` ("20 showing", "Show more"); its result is appended. Changing register or search starts again from page one. A late answer for an earlier view is ignored (sequence guard, as `useProject`) |
| 401 | `SignedOutState` with `next` = the tab's path (and query) |
| 403, 404 | Inside the tab panel: an `EmptyState` (level 2) "No access to this tab" / "It holds records you don't have access to. Nothing from it is shown here." No row text, milestone name, amount or reference from any earlier answer stays on screen. The header and tab bar stay (they came from E-PROJECT, which the person may read) |
| 5xx, network | `WorkErrorCard` in the panel: "We couldn't load this tab. Your work is safe; nothing was changed." with Retry (one new request per press; no automatic retry) |
| Permission, tenant | case.read plus the tab's read permission, decided by the backend per record. A row or field the response omits is not drawn. Nothing is derived from `/me` beyond F-07's Projects-destination check |
| Idempotency, versioning | Reads only; no polling |

### Milestones (SCR-38)
| Column | Shows (from `milestones[]`) |
|---|---|
| MILESTONE | `<position> · <name>` |
| CONTRACT AMOUNT | `contract_amount`: `Money` (₦, two decimals, from the decimal string) when `amount` is present and `unknown` is false; the amber `Unknown` tag when `unknown` is true or `amount` is absent. Currency other than NGN shows `<CODE> <grouped amount>` (`groupDigits`), never converted |
| COMPLETION | `done`: "Done <dd Mon>" from `completion.at` (`formatDayMonth`; "Done" alone when `at` is absent) then " · <proof>" when `proof` is present, or " · proof" when only `evidence_id` is present (not a link; evidence is not opened from here). `not_yet`: "Not yet". Then " · <amount_note>" when the row has `amount_note` (the board's "Not yet · amount set at go-live") |
| INVOICE | `invoice` present: `reference · <STATE_TAGS word of invoice.state>` (word omitted when `state` is absent); the reference links to `/work/<invoice.work_id>` when present (Conflicts 3, 8). `invoice` absent: "—" |
| PAID | `paid` absent: "—" (no Finance record; Unknown is its own status). `paid.status` words: `paid` "Paid", `part_paid` "Part paid", `not_paid` "Not paid", `not_due` "Not due", `finance_tracks` "Tracked by Finance", `unknown` the `Unknown` tag. Then " · <owed> owed" when `owed` is present (`owed.unknown` shows the `Unknown` tag before "owed"). Never inferred from the invoice |
| CHANGES (only when any row has non-empty `changes`; Conflicts 4) | Per change: `reference · title` (link to `/work/<work_id>` when present); a row without changes "—". The milestone's amount cell then reads `<contract amount> + the change · change amount <Unknown tag | Money>` (Conflicts 5); the two amounts are never added |
Footer: the SCR-38 static sentence (Conflicts 13). Phone: one card per milestone in the same order: name; "amount · completion"; invoice line; paid line; a "CHANGED · <reference>" tag per change (Conflicts 6, 7). Empty: "No milestones on this project yet."

### Registers (SCR-11)
- Register tabs (`Tabs`, label "Register", each an href to `?register=`): Issues, Changes, Emergencies, RFPs, each with its `CountBadge` from `summary.registers.<key>` when present (no badge when absent, never 0 invented). The selected tab is the URL's register.
- `ListToolbar` without Filter (Conflicts 2): search label "Search", placeholder "Search <register word> by title or reference" desktop, "Search <register word>" phone; result text "<n> ISSUES" (or CHANGES, EMERGENCIES, RFPS; singular for 1) from `summary.registers` for the chosen register, empty when absent. The frontend does not count rows for it.
- Columns (the Issues set for all four registers, G-SCR11-2): ISSUE `reference` (mono), WHAT `title` (link when `work_id`, Conflicts 8; `SampleLabel` when `sample`), SEVERITY `PriorityTag` for `high|medium|low` (nothing when absent), OWNER (owner text below), STATE `state` as given (plain text, no colour), AGE from `age_seconds` ("<n>d" from one day, "<n>h" from one hour, "<1h" below; absent → `Unknown`, Conflicts 11).
- Owner text (Registers and Actions): absent → "No owner" (signal-ink, bold, as drawn); else `[role, name]` joined by " · ", then " (recorded by PM)" when `recorded_by_pm`. `outside_party` adds no visible text (the role carries "Client").
- Footer: the SCR-11 static sentence (Conflicts 13). Phone: one card per row: reference, `PriorityTag`, title, "<state> · <owner>".
- Empty register: `EmptyState` "No <register word> on this project yet." With `q` and no rows: "No <register word> match "<q>"." with a "Clear search" button that clears `q`.

### Actions (SCR-29)
- `ListToolbar` without Filter: placeholder "Search actions"; result text from `summary.actions`: "<total> ACTIONS · <overdue> OVERDUE · <without_owner> WITHOUT OWNER", each part only when its count is present.
- Columns as drawn: ACTION (`title`, link when `work_id`; second line "From <from.meeting> · <dd Mon of from.at>", "From <meeting>" without `at`, nothing without `from`), OWNER (owner text), DUE (`due.unknown` true or `due` absent → `Unknown` tag; else "dd Mon"), STATE (`Tag`: `open` "OPEN" tone `waiting`, `overdue` "OVERDUE" tone `person`, `done` "DONE" tone `done`, matching the board's colours). Footer "Actions come from confirmed minutes." (Conflicts 12).
- Phone: one card per action: title with its state tag; "<owner> · due <date | Unknown>".
- Empty: "No actions on this project yet."; with `q`: "No actions match "<q>"." plus "Clear search".

### Screen states (all three tabs)
- **Loading:** the tab bar stays; the panel shows `Loading` with a `Skeleton`, announced politely. **Empty:** as above, never a blank grid. **Error / no access / signed out:** as the E-PROJECT-TAB table. **Success:** the rows, footers and "As of" line (Conflicts 14). **Unknown:** the amber `Unknown` tag, never 0, blank or "-".
- Reduced motion: nothing on these tabs animates.

### Fixtures (`frontend/mock/fixtures/projects/tabs/`, new; every body validates against the generated 200 schema)
| File | Shows |
|---|---|
| `P-0101.milestones.json` | SCR-38 default: Kick-off ₦3,000,000.00 done 27 Oct (evidence, no proof label), INV-0398 `verified`, `part_paid` owed ₦500,000.00; UAT sign-off ₦4,250,000.00 done 11 Nov "client UAT sign-off", INV-0412 `waiting`, no `paid`; Go-live ₦4,250,000.00 `not_yet`; Hypercare `unknown: true` with `amount_note` "amount set at go-live" |
| `P-0101.milestones.changed.json` | the same plus `changes: [{reference "CR-0031", title "SMS reminders", amount {unknown: true}, work_id}]` on Go-live |
| `P-0101.registers.json` | rows for all four registers: issues ISS-0233 (high, "PM · Tunde Bello", "Fix in testing", 2d), ISS-0229 (medium, Engineering `recorded_by_pm`, "Waiting on Engineering", 4d), ISS-0221 (low, "Closed by QA and PM", no `age_seconds`); 2 changes, 0 emergencies, 1 RFP; `summary.registers {issues 3, changes 2, emergencies 0, rfps 1}` |
| `P-0101.actions.json` | the board's 7 actions plus 2 more (Conflicts 15): owners Client · Lagoon Health (`outside_party`), Engineering (`recorded_by_pm`), none, Tunde Bello; one `due.unknown`; `summary.actions {total 9, overdue 3, without_owner 1}` |
| `P-0102.*.json` | edge cases: 25 issues (paging at 20, `next_cursor`), a `sample` row, an owner with no role, a known change amount, every `paid.status` including `unknown` and an `owed.unknown`, a milestone with no `invoice`, done without `at`/proof/evidence, a non-NGN amount, an action with no `from` and no `due` |
| `P-0103.*.json` | none: the handler answers 403 for every tab of P-0103 while E-PROJECT answers 200 |
| `P-0106.*.json` | empty arrays and no `summary` |

The mock never adds or computes a value; fixtures copy the boards' wording as the backend would return it.

## Shared files (F-26 builds the Money tab in parallel)
F-25 keeps its work in new files. Where both features touch a file, F-25's change is the smallest listed here; whichever merges second syncs from dlv-00-delivery-setup and keeps both.
| File | F-25 change | F-26 |
|---|---|---|
| `frontend/src/features/projects/ProjectJourney.tsx` | one import and one branch: `tab === 'journey' ? <JourneyTab/> : hasTabContent(tab) ? <ProjectTabContent caseId journey base tab/> : <ComingNext/>`. `ComingNext` stays (Documents still uses it). Nothing else in the file changes | adds its Money branch |
| `frontend/src/features/projects/model.ts` | **unchanged**. `PROJECT_TABS` keeps its shape (WorkItemView imports it) | adds money types in its own file |
| `frontend/mock/server.mjs` | add `'E-PROJECT-TAB'` to `M1_OPERATIONS` and one dispatch line to `projectTab()` from the new `mock/project-tabs.mjs`, placed after the scenario and persona handling. `projectTab()` answers 501 `not_mocked` for `documents` and `money` | answers `money` (and E-REPORT) from its own module; the merge routes `money` to F-26's handler |
| `frontend/tests/mock-projects.test.ts` | `:209` case: E-DOCUMENT and the `documents` tab still answer 501; the milestones path moves to the new mock test | changes the same case for money |
| `frontend/tests/projects-journey.test.tsx` | `:241-243` case: the `milestones` row becomes `documents` ("Documents come next", index 2); no other assertion loosened | changes the `money` row |
| `frontend/src/components/ListToolbar.tsx` | Filter becomes optional: when `onFilterToggle` is not given, no Filter button or panel is drawn. Existing callers and `tests/components*` unchanged and green | not touched |
| Read hook | F-25 owns the generic `useProjectTab(caseId, tab, query)` in `features/projects/useProjectTab.ts` | may keep its own `useMoney`; a later cleanup can merge them |

## Lanes
- **Frontend lane (builder, Sonnet; D-64)** owns:
  - New: `frontend/src/features/projects/tabsModel.ts` (types from `operations['E-PROJECT-TAB']`, URL parse/search, pure text helpers: owner, age, due, completion, invoice, paid, change amount, currency), `useProjectTab.ts`, `ProjectTabContent.tsx` (switch and shared states), `MilestonesTab.tsx`, `RegistersTab.tsx`, `ActionsTab.tsx`, `project-tabs.css` (tokens only).
  - Mock: new `frontend/mock/project-tabs.mjs` (reads `fixtures/projects/list.json` for visibility itself; P-0099 and invisible cases 404; P-0103 403; `limit` in 10/20/50, `register` only on registers and in its enum, a non-empty `q`, cursor `o<n>`, else 404 `invalid_query` as `projects.mjs`; `q` matches `title` or `reference` case-insensitively; `psl_mock_milestones=changed` selects the changed milestones file; mirrors the page's rows into `items`); new fixtures under `frontend/mock/fixtures/projects/tabs/`.
  - Edits as listed under Shared files only.
  - Tests: `frontend/tests/project-tabs.test.tsx`, `project-tabs-model.test.ts`, `mock-project-tabs.test.ts`, `frontend/e2e/project-tabs.spec.ts`.
  - Factory files: `delivery/features/F-25/fidelity-exceptions.json`, `round-<N>/fidelity/**`, `round-<N>/build.md`.
- **Read only (import, do not edit):** `src/shell/**`, `features/work-item/**`, `features/decide/**`, the Journey tab code, `src/api/**` (including `schema.d.ts`), `src/styles/**`, other `src/components/**` files, `frontend/package.json` and lock file, `playwright.config.ts`, `vitest.config.ts`, `mock/projects.mjs`, existing fixtures, `architecture/**`, `design/**`, `apps/**`, and protected `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json`.
- **Backend lane:** none. Recorded in build.md, not blocking: E-PROJECT-TAB is unimplemented; contract proposals G-SCR38-1 (`invoice.status_label`), G-SCR38-2/G-SCR19-2 (`milestone_id`, `reference`, `can_complete`, `cannot_complete_reason`), G-SCR38-3 (`changes[].amount_note`, `summary.note`), G-SCR11-1/G-SCR29-1 (filters), G-SCR11-2 (columns for the other registers), age-applies signal (Conflicts 11), G-SCR29-2 (owner/due edit). Questions: is `age_seconds` computed at response time; does `paid` absent mean "nothing recorded" (the board's "—"); what `finance_tracks` means for this person; do `summary` counts reflect `q`; do the tab reads hide names and figures on 403/404; is the SCR-11 footer rule true.
- **Integration owner:** the coordinator. Merge rule under Shared files; the second merger reruns `delivery/checks.sh` and both features' e2e at 390.
- **Ports:** app **4790**, mock **4791** (no other spec uses 479x). `cd frontend && E2E_PORT=4790 MOCK_PORT=4791 npx playwright test e2e/project-tabs.spec.ts`, `timezoneId: 'Africa/Lagos'`. Fidelity on a production build (`next build`, `next start -p 4790`, mock on 4791). Check `df` first (stop below 3 GB) and delete `frontend/test-results` after.
- **Review routing:** technical (sonnet), security (sonnet: read only, access states), UI (opus: the fidelity gate on 8 boards), UX (sonnet), QA (opus: Unknown and separate-facts rules on money). Medium risk; product acceptance not required. One fidelity run per round (D-64).
- **Size:** about 1,200 to 1,600 lines (three panels, fixtures, mock, tests). One PR. If it grows past that, the phone boards move to a follow-on first.

## Acceptance criteria
Fidelity command for one board (swap `--board`, `--page`, `--width`, `--cookies`, `--out`):
```
node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs \
  --playwright <worktree>/frontend/node_modules/playwright/index.mjs \
  --board /Users/Hunchoo/psl-factory/design/canvas/project/SCR-38-desktop-changed.dc.html \
  --page "http://localhost:4790/projects/P-0101/milestones" --width 1440 \
  --cookies psl_mock_persona=pm,psl_mock_milestones=changed \
  --exceptions /Users/Hunchoo/psl-factory/delivery/features/F-25/fidelity-exceptions.json \
  --wait-ms 500 --out /Users/Hunchoo/psl-factory/delivery/features/F-25/round-<N>/fidelity/SCR-38-desktop-changed-1440
```

### Fidelity (8 boards)
1. **Desktop boards at 1440.** `SCR-38-desktop`, `SCR-38-desktop-changed`, `SCR-11-desktop`, `SCR-29-desktop` each give `report.json` `pass: true`, `scores.coverageWithExceptions` = 100 and `scores.visual` >= 90 on the pages and cookies of the Boards table. — verify: the command per board, exit 0; `round-<N>/fidelity/scores.txt` lists board, width, coverage, visual, pass.
2. **Phone boards at 390.** The four `-mobile` boards pass at `--width 390` with the same thresholds. — verify: same, rows in `scores.txt`.
3. **Exceptions are limited and explained.** Each `fidelity-exceptions.json` entry has `role`, `name`, `category`, `reason`, `approved_by` (`"builder proposal, pending design engineer"` until signed) and maps to a Conflicts number; none covers a value the data can supply. A board below 90 visual for a Conflicts reason gets a per-board waiver proposal for the design engineer (D-83 is for line screens and does not apply). — verify: file content; build.md maps each entry to its Conflicts number.
4. **One fidelity run per round** (D-64). — verify: build.md.

### Page behaviour
5. **Tabs replace "coming next" for three tabs only.** `/projects/P-0101/milestones`, `/registers` and `/actions` show their tab content in the existing tab panel with the F-07 header and the tab selected; `/documents` still shows "Documents come next"; `/money` shows whatever F-26 or the current panel draws; `/projects/P-0101` (Journey) is unchanged. — verify: `tests/project-tabs.test.tsx`; `tests/projects-journey.test.tsx` passes with only the `:241-243` row changed.
6. **One read per view.** Opening a tab makes one E-PROJECT and one `GET /api/v1/projects/P-0101/<tab>` request with `limit=20` (and `register=issues` on Registers), no `q` when search is empty, no `cursor`; no polling (fake timers advanced 60 s, count unchanged). — verify: component test with a recording `fetch`.
7. **Milestones default.** The four P-0101 milestones show, in returned order: "1 · Kick-off", "₦3,000,000.00", "Done 27 Oct · proof", "INV-0398 · Verified", "Part paid · ₦500,000.00 owed"; "2 · UAT sign-off", "Done 11 Nov · client UAT sign-off", "INV-0412 · Waiting", "—"; "3 · Go-live", "Not yet", "—", "—"; "4 · Hypercare" with the `Unknown` tag and "Not yet · amount set at go-live". No total row, no sum anywhere. — verify: component test; page at 1440 and 390.
8. **Unknown is never 0.** On P-0102 an unknown contract amount, an unknown change amount, an `owed.unknown`, `paid.status: unknown`, an unknown due date and an absent `age_seconds` each read "Unknown" (amber tag); `document.body.textContent` has no "₦0" and no "0.00" that the fixture did not send. — verify: component test and `tests/project-tabs-model.test.ts`.
9. **Facts stay separate (INV-FACTS).** A milestone with `invoice` and no `paid` shows "—" under PAID (never "Paid" or "Not paid"); a `not_yet` milestone with an invoice still shows "Not yet"; every `paid.status` shows its own word; nothing reads `invoice.state` to decide paid. — verify: model tests over every `paid.status` and an invoice/paid mismatch fixture row.
10. **Changed milestone.** With `psl_mock_milestones=changed`, a CHANGES column appears (Conflicts 4) with "CR-0031 · SMS reminders" linking to `/work/<work_id>`; Go-live's amount reads "₦4,250,000.00 + the change · change amount Unknown"; INVOICE and PAID stay. On P-0102 a known change amount shows next to the contract amount and never added to it (no third figure). The phone card shows the "CHANGED · CR-0031" tag. — verify: component test; page at 1440 and 390.
11. **No completion control.** No "Mark milestone … complete" button or link and no form exist on any milestone fixture. — verify: component test (`queryByRole('link'|'button', { name: /complete/i })` is null).
12. **Registers default.** Tabs read "Issues 3", "Changes 2", "Emergencies 0", "RFPs 1" from `summary.registers`; the toolbar shows search and "3 ISSUES" and no Filter; the Issues rows show reference, title, `PriorityTag` ("■■■ High" and so on), owner "PM · Tunde Bello" / "Engineering (recorded by PM)", state text as given and "2d", "4d", "Unknown". The footer sentence shows. — verify: component test; page at both widths.
13. **Register switch and search use the URL.** Choosing Changes navigates to `?register=changes` and requests `register=changes` with no cursor; Issues removes `register` from the URL. Typing "android" and pausing sets `?q=android` and requests `q=android`; clearing removes both; an unknown `?register=x` reads as Issues. Keyboard: arrows, Home and End move along both tab bars. — verify: component test and e2e (URL and recorded requests).
14. **Empty and no match.** Emergencies (0 rows) shows "No emergencies on this project yet."; a search with no rows shows the no-match sentence and "Clear search", which clears `q`; P-0106 shows each tab's empty sentence with no count text and no "0" invented where `summary` is absent. — verify: component test and e2e.
15. **Paging.** On P-0102 Issues, 20 rows and "Show more" show; pressing it sends one request with the returned `cursor` and appends the next rows, and focus stays on the control; changing register or search starts from page one; the URL never carries a cursor. — verify: component test and e2e.
16. **Actions default.** The header text reads "9 ACTIONS · 3 OVERDUE · 1 WITHOUT OWNER"; rows show title with "From Weekly sync · 10 Nov", owners "Client · Lagoon Health", "Engineering (recorded by PM)", "No owner", "Tunde Bello", due "13 Nov" or "Unknown", and state tags OPEN, OVERDUE, DONE; the footer reads "Actions come from confirmed minutes." and nothing about changing owners. — verify: component test; page at both widths.
17. **Rows link only with `work_id`.** Register titles, action titles, invoice references and change references link to `/work/<work_id>` when the row has one and are plain text otherwise; no link opens evidence. — verify: component test over fixtures with and without `work_id`.
18. **Access.** P-0103 (tab answers 403) and a tab 404 show "No access to this tab" in the panel with the header kept and no milestone name, amount, reference or title from the fixture in `document.body.textContent`; a 403 after a successful first page (search) removes the earlier rows. P-0099 shows F-07's `ProjectNoAccess` and makes no tab request. A tab 401 shows the sign-in link with `next=%2Fprojects%2FP-0101%2Fregisters` (query kept when present). A persona with any role gets the same columns and controls for the same fixture; nothing is read from `/me` beyond the Projects destination. — verify: component tests with a recording `fetch`; e2e for P-0103; `git diff` shows no new `/me` use in `features/projects`.
19. **Server and network errors.** A 500 or network failure on the tab read shows the error card with Retry; Retry sends exactly one new request; no automatic retry. — verify: component test.
20. **Static and data text.** Register `state`, owner `role`, `amount_note`, meeting names and references appear exactly as the fixture sends them; the frontend adds no state colour to register states and composes none of the backend sentences of Conflicts 3, 5 and 12. — verify: component test; `grep -n "awaiting Finance decision\|SOW amendment\|recorded with your name" frontend/src/features/projects` returns nothing.

### Quality
21. **Accessibility and layout.** For the three tabs on P-0101, P-0102 and P-0106 at 1440 and 390: no axe violations (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`), one `h1`, the table `caption`s name the tables, no sideways page scroll (the table frame may scroll itself), visible focus, 44px targets on phones (D-92c; in-sentence links exempt, D-95), loading and result counts announced politely. — verify: `e2e/project-tabs.spec.ts`.
22. **Tokens only.** `grep -nE "#[0-9a-fA-F]{3,8}\b|rgba?\(|hsl\(" frontend/src/features/projects/project-tabs.css` returns nothing. — verify: the command.
23. **Shared component change is general.** `ListToolbar` without `onFilterToggle` draws no Filter button; with it, behaviour is unchanged; existing component tests pass unchanged. — verify: a new case in `tests/project-tabs.test.tsx` or the components test; `delivery/checks.sh`.
24. **Contract not extended.** `git diff --stat` shows no change in `frontend/src/api/**`, `apps/**`, `architecture/**`, `design/**` or `features/projects/model.ts`; every fixture validates against the generated E-PROJECT-TAB 200 schema with no stripping; every wanted field the schema lacks is a contract proposal in build.md. — verify: `tests/mock-project-tabs.test.ts`; `git diff --stat`; build.md.
25. **Mock matches the contract.** `mock-project-tabs.test.ts` runs every fixture through the handler: valid bodies for milestones, registers and actions; 404 for P-0099, an invisible case, a bad `limit`, a `register` on another tab, an empty `q`, a bad cursor; 403 for P-0103; 501 for `documents`; the changed cookie switches the milestones file; `q` and cursor slice the rows; the X-Mock-Scenario header still wins. — verify: the test.
26. **Existing behaviour kept.** `tests/projects*.test.*`, `mock-projects.test.ts`, `work-item*.test.tsx`, `shell.test.tsx`, component tests and `e2e/projects.spec.ts` pass; the only edited assertions are those listed under Shared files; no existing fixture changes. — verify: `delivery/checks.sh`; `git diff` on those files.
27. **New tests run.** `project-tabs.test.tsx`, `project-tabs-model.test.ts`, `mock-project-tabs.test.ts` and `e2e/project-tabs.spec.ts` exist and run in `delivery/checks.sh`, covering criteria 5 to 20. — verify: file presence and the run output in `round-<N>/build.md`.
28. **build.md evidence and limits.** build.md lists the commands run and results, the 8 scores, each exception with its Conflicts number, the ListToolbar change, every contract proposal and backend question, the static footer sentences for confirmation, and the mock limits below; the PR and build.md claim no real backend. Every e2e request goes to the mock (4791). — verify: file content; recorded requests.

## Mock limits (binding on the PR description and build.md)
- D-PROJECT-TAB-ROWS is `proposed` with no recorded approval; F-25 consumes it only under the recorded exception (`architecture/sources/decisions-2026-11-15.md` items (g), (i)): **contract mock only**.
- **The backend developer may change or refuse any field** of the milestones, registers and actions rows and `summary`. The frontend never extends the contract locally.
- **Nothing is released.** The figures are sample data; the PR does not claim real milestones, real Finance payment data or a working backend.

## Out of scope
- Money tab and E-REPORT drill-down (F-26); Documents tab content (no approved list board); SCR-19 milestone completion (FE-MILESTONE-COMPLETE); SCR-08 document review; SCR-30 and SCR-31 detail pages (rows link to the generic `/work/[id]`).
- Any write: completing a milestone, starting an invoice, editing an owner or due date, closing an issue, setting severity.
- Filters (Conflicts 2), the "Mark milestone complete" control, the invoice status text, the change-amount clause and change sentence, and an age-applies signal: contract proposals only.
- Totals, sums of amount and change, counts worked out in the browser, sorting, colouring register states, inferring paid from the invoice.
- Backend, OpenAPI, `schema.d.ts` regeneration, `architecture/**`, `design/**`; `src/shell/**`, the Journey tab, `PROJECT_TABS`' shape, `features/work-item/**`; new npm dependencies; a new table or tab component.

## Assumptions
- Register tabs use `Tabs` with hrefs, not `Segmented` as readiness suggested. Reason: SCR-11 draws a second tab strip (`role="tab"` with counts), and links keep the register in the URL as readiness asks.
- `register` is always sent on the registers tab, default `issues`. Reason: the board opens on Issues; an omitted register would leave the default to the backend.
- `limit` is fixed at 20 with no "Rows per page" control. Reason: the boards draw none here; 20 is the contract default.
- `paid` absent shows "—"; `paid.status: unknown` shows "Unknown". Reason: the schema has an explicit `unknown` status, so absence means no Finance record yet, which is what the board's "—" draws. Listed as a backend question.
- Paid words ("Paid", "Part paid", "Not paid", "Not due", "Tracked by Finance") are frontend labels for the enum. Reason: only "Part paid" is drawn; the others are plain names, not rules. The approver may escalate "Tracked by Finance".
- "· proof" when completion has `evidence_id` but no `proof` label. Reason: matches the board's Kick-off cell without inventing a document name.
- `amount_note` follows the completion text ("Not yet · amount set at go-live") as both boards place it.
- Age is "<n>d", "<n>h", "<1h" from `age_seconds`. Reason: the board draws "2d" and "4d"; finer steps are display only.
- `outside_party` adds no visible mark. Reason: the board's "Client · Lagoon Health" comes from `role` and `name`.
- Result counts come from `summary` as returned, whether or not they reflect `q`. Reason: the frontend counts nothing; listed as a backend question.
- A 403/404 on the tab read keeps the project header and shows a panel-level no-access state. Reason: E-PROJECT already granted the header; the copy is neutral frontend wording, not a rule.
- Changed state is chosen by a mock cookie `psl_mock_milestones=changed` on P-0101. Reason: the board keeps the same project title, and the mock has a precedent for dataset cookies (`psl_mock_worklist`).
- Non-NGN amounts show the currency code with grouped digits. Reason: `Money` always prints ₦; no conversion is allowed.
- Neutral sentences ("No access to this tab", empty and no-match sentences, the error-card line) are frontend copy in the F-07 style. Reason: sources are silent; none is a business rule.
- Ports 4790/4791 and fixture files under `fixtures/projects/tabs/`. Reason: no other spec uses 479x; the projects fixture loader reads only `P-*.json` at its top level.
