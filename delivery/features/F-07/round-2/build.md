STATUS: READY
COMMIT: ab641e93900ddddcaeaa19d323f33fa9045ef9d0
BUILDER: builder
LANE: full

## Summary
- FID-1: `/projects` and `/projects/<case_id>` are rebuilt to match SCR-22 and SCR-07. The structure, order, wording and styling follow the boards, using design-system classes and tokens.
- **List:** the PROJECTS eyebrow, then Active / Closed / All I can see tabs with counts, a search box with a Filter button and "N PROJECTS", the six board columns, phone cards with the red "need a person · stopped" line, and the full closing note.
- **Project page:** the "PROJECTS / CLIENT" breadcrumb, the full tab bar (Journey, Milestones, Documents, Money, Registers, Actions) with counts, the "PM · route · pieces of work" line, the six-cell facts strip, and "The whole journey, oldest first". Each line in the journey has a status square, its reference and detail, and an upper-case tag. Tola's summary sits beside the journey.
- **Missing fields:** where E-PROJECTS or E-PROJECT (v4/v5) has no field, the page reads optional PROPOSAL fields that the contract mock serves (listed below for the architecture). A body without them still draws every board element, with "Not known" or "—" in place of the missing value.
- **Fidelity check:** three of four boards pass. SCR-07-mobile has 100% coverage but a visual score of 68. The reason is the frame's phone bar and needs a design-engineer exception (see Exception requests). UX-1-1 and QA-1-1 are also fixed.

## Changes
- **Merge:** `origin/dlv-00-delivery-setup` merged first (b80d3b3, no conflicts).
- `frontend/src/features/projects/model.ts`
  - PROPOSAL types for both reads: `ProjectRowView`, `ProjectListView`, `JourneyView`, `JourneyFacts`, `JourneyLineView`.
  - The list tabs (`LIST_TABS`, `?status=closed|all`, Active is the default and is not written to the URL).
  - `ProjectsRequest`: sends `status` for Active and Closed, and none for All I can see.
  - The project tab table `PROJECT_TABS`.
  - Helpers: `clientOf`, `workCounts`/`piecesText`/`linesText` (pieces of work = lines returned; lines = distinct `line` names), and `routeCaseId` (QA-1-1).
- `frontend/src/features/projects/ProjectsList.tsx`
  - Eyebrow; the tablist with roving tabindex, arrows and Home/End, plus a tabpanel; search labelled "Search", with placeholder "Search projects or clients" (phone: "Search projects").
  - Filter button: a secondary button on desktop and a 44px icon button on phones. It opens a small dialog, "Filters come next" (Escape, Close or a click outside closes it and returns focus).
  - The total is "N PROJECTS" when counts are present, otherwise "N shown".
  - Columns NEXT MILESTONE, NEEDS A PERSON (bold signal-ink when > 0, muted 0) and STOPPED. A missing value shows "—".
  - Phone cards add the attention line.
  - The closing note now reads in full: "You see projects your roles cover. Open one for its journey, documents, money and registers."
  - Paging (rows per page, Show more) is unchanged.
- `frontend/src/features/projects/ProjectJourney.tsx`: the header, the tab bar, then a tabpanel.
  - **Journey tab:** the route line (desktop), the phone summary line, `FactsStrip` (psl-facts; earned/current/unknown tones; "Not known" when a fact is missing), the journey section with `JourneyLines`, the "What is next" row (contract `next`, now at the foot of the journey box), and `AgentSummary` (Tola; "Ask me about this project" shows only when /me lists Assistant).
  - **Other tabs:** a "<Tab> comes next" panel with "Open the journey".
  - A 401 on a tab signs in back to that tab.
- `frontend/src/features/projects/ProjectTabs.tsx`: all six tabs as links with `role="tab"`, `aria-selected`, `aria-controls`, roving tabindex and arrows/Home/End. Counts come from `tab_counts`.
- `frontend/src/app/projects/[caseId]/[tab]/page.tsx` (new): `/projects/<id>/{milestones,documents,money,registers,actions}`. Any other segment goes to `notFound()`.
- `frontend/src/app/projects/[caseId]/page.tsx`: decodes the route segment once (QA-1-1).
- `frontend/src/features/projects/useProject.ts`: types only (`JourneyView`).
- `frontend/src/features/projects/projects.css`
  - The pages' blocks are 20px apart, as on the boards.
  - The table, cards, tabs, facts, journey box, status squares, Tola panel and Filter popover take the board measurements via token variables.
  - Phone layout follows the -mobile boards:
    - hidden: the eyebrow, list tabs, total, note, route line, facts, journey heading, references and Tola;
    - shown: the phone summary line, and the tab strip runs to the edge.
- `frontend/mock/projects.mjs`
  - `status` query (active | closed; anything else is 404 `invalid_query`).
  - `counts` {active, closed, all} over the persona's rows.
  - Exports `PROPOSED_FIELDS` and `contractBody()`, which strips them.
- `frontend/mock/fixtures/projects/`
  - `list.json`: the five SCR-22 board rows are now pm's rows, in board order:
    - Lagoon Health
    - Harmattan Bank (was Harbour Bank)
    - Kora Logistics
    - Ojo Foods · ordering app (P-0106)
    - Sabi Market, closed 09 Nov
  - `list.json` also has a `status` per row and the row PROPOSAL fields. P-0104 Delta Foods is now finance_lead-only and is the pm no-access id.
  - `P-0101.json` (new): the SCR-07 journey: 8 lines with title, reference and detail, plus facts, summary, revision and tab_counts.
  - Other `P-*.json` files: client, pm and tab_counts.
  - `E-PROJECT.json` is unchanged: still the 11-state contract-only body, and still the fallback.
- Tests:
  - `tests/projects.test.tsx` (25), `tests/projects-journey.test.tsx` (31), `tests/projects-model.test.ts` (5) and `tests/mock-projects.test.ts` were rewritten for the board build.
  - `e2e/projects.spec.ts` was rewritten too (28 tests). It adds list tabs, the Filter dialog, the Milestones tab at both widths with axe, an unknown tab, and focus on the Active tab, Filter, project tab and Ask me.
- `tests/mock-contract.test.ts`: **one assertion changed, as spec line 193 allows.**
  - For E-PROJECTS and E-PROJECT, the 200 body is validated after `contractBody()` strips the PROPOSAL fields.
  - The reason: v4 has `additionalProperties: false`.
  - Everything else in the file is unchanged.

### PROPOSAL fields (for the architecture; served by the mock, all optional in the client)
| Read | Field | Board element |
|---|---|---|
| E-PROJECTS query | `status` = active \| closed | Active / Closed / All I can see tabs |
| E-PROJECTS | `counts` {active, closed, all} | tab counts, "5 PROJECTS" |
| E-PROJECTS item | `next_milestone` (string) | NEXT MILESTONE |
| E-PROJECTS item | `needs_person`, `stopped` (integers) | NEEDS A PERSON, STOPPED, the phone "2 need a person · 1 stopped" |
| E-PROJECT | `revision`, `tab_counts` | already in the v6 proposal; tab counts |
| E-PROJECT | `client` | breadcrumb "PROJECTS / LAGOON HEALTH" (the client defaults to the title before " · ") |
| E-PROJECT | `pm`, `route` | "PM Tunde Bello · Route A from RFP-0031" |
| E-PROJECT | `facts` {contract_stages, invoices_verified, waiting_on_people, stopped, next_milestone, paid} | facts strip; phone line |
| E-PROJECT | `summary` {agent, role, paragraphs[]} | Tola's summary |
| E-PROJECT line | `title`, `reference`, `detail` | "Invoice · Milestone 2 INV-0412 / Station 4 of 7 · Finance review" |

The order of lines is also a contract question. The board says "oldest first", but the contract does not promise an order. The page keeps the order the server returns.

### Exception requests (design engineer)
1. **SCR-07-mobile visual score is 68 (needs 90).** Coverage is 100%.
   - The board puts "← Projects" in the phone bar. The frame's phone bar (F-01 `PhoneBar`, not this lane) draws the menu and the brand, so the page carries its own 44px "← Projects" link above the title. That pushes everything down by about 56px.
   - The board's title also wraps onto two lines because of how the board's Google-font instance renders. Ours fits on one line.
   - The fix is a frame option for a back link in the phone bar, or an approved exception.
2. **SCR-22-mobile "← Home"** is drawn in the phone bar, which is frame-owned. Requested as an exception (in `exceptions-requested.json`).
3. **Start work and More ways to start** (both desktop boards) are frame items owned by F-05.
4. **"Tunde Bello · PMO" on the SCR-07-desktop run** is a limitation of the fidelity tool. It sets `--cookies` with the page's directory as the cookie path (`/projects`). As a result, `/api/v1/me` on `/projects/P-0101` answers with the default persona (Ada Okafor). The project page itself is the same for both personas.
5. **SCR-22-desktop fidelity was run on `/projects?status=all`.** The board selects Active but draws the closed Sabi Market row and "5 PROJECTS". The built Active tab shows the 4 active rows and "4 PROJECTS". Please either correct the board or confirm that Active excludes closed projects.
6. **"AWAITING FINANCE DECISION"** (the board's tag on Invoice · Milestone 2) is not a label in the state enum. That line is `waiting` (W-1001), so it reads "WAITING" with a white square. Tag words come only from STATE_TAGS (criterion 6).
7. **Tabs other than Journey** open a "<Tab> comes next" panel until FE-M3-PROJECT-TABS builds them.
8. **The Filter button** opens "Filters come next". The contract has no project filters.
9. **Elements not on the boards are kept**, because the spec or the contract needs them:
   - Rows per page and Show more (D-PAGING).
   - "What is next" (the contract's required `next`; now a quiet row at the foot of the journey box).
10. **Phone journey:** as on SCR-07-mobile, there is no visible state tag, only the coloured square and the detail line. The tag text is kept for screen readers.
    - Please confirm. A colour-only square is a WCAG 1.4.1 risk for sighted people who cannot tell the colours apart.

### Fidelity (final, production build on 3701 against the mock on 3702, persona pm, `--exceptions round-2/fidelity/exceptions-requested.json`)
| Board | Page | Width | Coverage | Visual | Result |
|---|---|---|---|---|---|
| SCR-22-desktop | /projects?status=all | 1440 | 95.7% (100% with exceptions) | 92.1 | PASS |
| SCR-22-mobile | /projects | 390 | 88.9% (100% with exceptions) | 91.6 | PASS |
| SCR-07-desktop | /projects/P-0101 | 1440 | 93.6% (100% with exceptions) | 90.9 | PASS |
| SCR-07-mobile | /projects/P-0101 | 390 | 100% | 68.0 | FAIL (exception request 1) |

`report.json` and `side-by-side.png` for each run are in `delivery/features/F-07/round-2/fidelity/<board>-<width>/`. The round-1 baseline for SCR-22-desktop was 59.6% coverage and 82.3 visual.

## Fixes
- FID-1 | 3f1e58c, f6e7943, 1db0f9a, ab641e9 | List, project header and facts, PM and route line, journey lines, Tola's summary and the full project tab bar rebuilt to the SCR-22 and SCR-07 boards; PROPOSAL fields in the mock; tests rewritten
- UX-1-1 | f6e7943 | Lines now link by their title (unique on the board data). When two link names still repeat, a visually hidden ", <reference or state>" is added (test: "Zulu line, Verified" and "Zulu line, INV-5").
- QA-1-1 | f6e7943 | The route segment is decoded once (`routeCaseId`) before the client encodes it, so `/projects/P%2F..` sends the id once-encoded (unit test).

## Acceptance criteria
1. [x] **List reads E-PROJECTS.**
   - One GET, `?limit=20&status=active`.
   - Six board columns, with cells equal to the mock in order, and P-0101 linked.
   - e2e at 390 and 1440.
2. [x] **Board elements.** Every SCR-22 and SCR-07 element is drawn.
   - Bodies without the PROPOSAL fields still draw them, with "—" or "Not known". Tested for both the list and the journey.
   - The spec's round-1 rule of showing only contract fields is replaced by FID-1 and the coordinator's note.
3. [x] **Search.**
   - Debounce 300 ms. The request is `?limit=20&status=active&q=lagoon` and the URL is `?q=lagoon`.
   - No empty q is ever sent. No match leads to Clear search (component test and e2e).
4. [x] **Paging.**
   - Show more sends `cursor=o20`, then "All 22 showing" with focus on row 21.
   - `?limit=10` and `?limit=7` work, as do the radio arrows (component test and e2e).
5. [x] **Journey reads E-PROJECT and keeps order.** One GET, server order kept, `/work/<id>` links. e2e: P-0101, line 7, then /work/W-1001, "Lagoon Health · Milestone 2 invoice".
6. [x] **State tags come from STATE_TAGS.** A table-driven test covers all 11 states. Tags are upper-cased by CSS. No tag is taller than 30px.
7. [x] **Journey empty.** P-0105 shows "No work on this project yet.", the tabs and "What is next".
8. [x] **No grant: 404/403 reveals nothing.**
   - No tablist, no breadcrumb, no name or code.
   - pm on P-0104 does not show "Delta Foods".
   - P-0099 in e2e.
9. [x] **Wrong user.** Without the projects destination, or with persona none, no request is sent (component test and e2e).
10. [x] **Signed out.** 401 leads to `next=/projects`, `/projects/P-0101` or `/projects/P-0101/milestones`. A 403 on the list shows not open.
11. [x] **Load failures.** 500, 404 invalid_query, network failure and a malformed 200 all show the error card and Try again. A failed Show more shows the inline callout.
12. [x] **Loading and stale responses.** A late q response is ignored, as is a late case_id response.
13. [x] **Sample label rule.** Unchanged, and tested.
14. [x] **The mock honours the query.**
    - Persona × limit walks.
    - q; `status` and counts; invalid limit, cursor, q and status.
    - P-0099, plus P-0104 for pm.
    - Contract parts are schema-valid.
    - The board rows and the P-0101 board journey.
    - The fallback has all 11 states. E-PROJECT-TAB is still 501.
15. [x] **Accessibility.**
    - axe WCAG 2.2 AA is clean at 390 and 1440 for: list default, no results, error, loading, journey, empty, no access, the Milestones tab, not open, and the Filter dialog with All I can see.
    - No horizontal scroll.
    - Focus rings on: the Active tab, search, Filter, a row link, the radio, Show more, the breadcrumb, the Journey tab, a line link, Ask me, Back to projects, a phone card and the "← Projects" link.
    - 44px targets at 390: search, Filter, radios, Show more, cards, the back link, the Journey tab, and every journey row (the link covers its row).
    - Reduced motion is respected.
16. [x] **Frame tests stay green.** `shell.test.tsx` and `e2e/frame.spec.ts` pass unchanged.
17. [x] **Product acceptance items are listed.** See PROPOSAL fields, Exception requests and Fidelity above.

## Validation
- `df -h /System/Volumes/Data`: 12 to 14 GB free throughout.
- `cd /Users/Hunchoo/psl-factory-worktrees/f-07 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh` gave **exit 0** on 1db0f9a and again on ab641e9.
  - Django check passed.
  - npm ci, lint (0 warnings) and typecheck passed.
  - vitest: 17 files, 415 tests passed.
  - next build passed, with `/projects/[caseId]/[tab]` dynamic.
- `cd frontend && E2E_PORT=3701 MOCK_PORT=3702 npm run test:e2e` on 1db0f9a: **111 passed**, 0 failed. This includes frame, decide, my-work, work-item and the 28 projects tests.
- On ab641e9, which only changes the size of the status squares in CSS:
  - checks.sh: **exit 0** (415 vitest tests);
  - `E2E_PORT=3701 MOCK_PORT=3702 npx playwright test e2e/projects.spec.ts`: **28 passed**.
- Fidelity: see the table above. `next start` and the mock ran on 3701 and 3702 and were stopped afterwards.
- `frontend/test-results` was deleted. No AI attribution appears in commits (the user's CLAUDE.md rule). `git status --porcelain` is empty.
- Pushed to `origin/fe-m3-projects-projects-shows-the-projects-a-person-can`, head ab641e9.

## Blocked
Not blocked.
