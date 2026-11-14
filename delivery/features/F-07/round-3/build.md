STATUS: READY
COMMIT: 2892f009b88a0dfb1a2ec1df5f33b966f7ba0a7c
BUILDER: builder
LANE: full

## Summary
- UI-2-1: the phone Filter icon button now draws only the bundle's 2px inset ring. Its computed border is 0 and the button is 44x44.
- TECH-2-1: the PROPOSAL fields now use the architecture v7 shapes (D-PROJECTS-VIEW): `next_milestone {name, due}`, `pm {name, role, is_you}`, `facts[] {label, value, money, unknown}`, `agent_summary {agent, text}`, `work_count`, `line_count`, `total`, and the line fields `station`, `status_label` and `tone`. Every one is read through a type guard, so a value in an unexpected shape shows as "—" or "Not known" and never throws.
- TECH-2-2: the Active tab (the default) sends no `status`. Closed sends `status=closed` and All I can see sends `status=all` (v7 enum). The mock treats an absent status as Active.
- UX-2-1: the "N PROJECTS" count now shows the result of the current search (v7 `total`). Searching "lagoon" reads "1 PROJECTS", and the tab badges keep the whole-tab counts. No board shows "1 of 4", so that wording was not used.
- The fidelity check was re-run on the four boards. Three pass, and SCR-07-mobile is unchanged at 68, accepted under D-08.

## Changes
- **Merge:** `origin/dlv-00-delivery-setup` merged (5b85ddb, no conflicts). This brings `architecture/packages/v7/` into the worktree.
- `frontend/src/features/projects/projects.css`: removed `border: 2px solid var(--ink)` from `.projects__iconbtn` (phone).
- `frontend/src/features/projects/model.ts`
  - PROPOSAL types follow v7. `client` is dropped, because v7 has no such field; the breadcrumb takes the client from the title.
  - New guards:
    - `textOf` and `countOf`
    - `nextMilestoneText` ("UAT sign-off · due 14 Nov", or "· due not known")
    - `pmNameOf`
    - `factsOf`, `factText` and `findFact` (money goes through `formatAmount`; unknown is never shown as 0)
    - `lineDetail` (falls back to "Station i of n · name" from `station`)
    - `agentSummaryOf` (Tola is "PMO agent", Chidi is "Finance agent"; blank lines split paragraphs)
  - `workCounts(journey)` uses `work_count` and `line_count` when they are sent.
  - `buildProjectsQuery` sends `status` only when the tab is not Active.
- `ProjectsList.tsx`
  - Cells, counts, badges and the phone attention line all go through the guards.
  - The count beside search is `total`. Without `total`, the tab count is used only when no search is active; otherwise it shows "N shown".
- `ProjectJourney.tsx`
  - The facts strip renders the facts array in the order the response sends it. Without facts, the six board labels show "Not known". Tones are keyed by label and are presentation only.
  - The PM/route line, the phone line, line reference and detail, and the agent summary all go through the guards.
- `ProjectTabs.tsx`: tab counts go through `countOf`.
- `frontend/mock/projects.mjs`
  - Accepts `status` values active, closed and all; an absent status means active.
  - Adds `total` (rows matching status and q).
  - `PROPOSED_FIELDS` now lists the v7 names.
- `frontend/mock/fixtures/projects/*.json`: converted to the v7 shapes. The values are unchanged, so the boards render the same.
- Tests:
  - `mock-projects.test.ts` now validates every 200 body and every journey fixture in full against the v7 openapi. The v6 check without the PROPOSAL fields stays.
  - New tests cover the status default, `total` with search, and the guards (projects-model).
  - New tests feed wrong-shaped and v7-shaped bodies to both pages.
  - Request expectations no longer include `status=active`.
  - The e2e search test now checks "1 PROJECTS".

## Fixes
- UI-2-1 | e830045 | `.projects__iconbtn` border removed. At 390 the computed style is `border 0px`, `box-shadow inset 0 0 0 2px rgb(31,36,39)`, size 44x44.
- TECH-2-1 | 2892f00 | Proposal fields are aligned to v7 D-PROJECTS-VIEW and type-guarded. Unit tests and component tests cover a `next_milestone` string, a `pm` string, a `facts` object, the old `summary`, string counts and an object title. None of them throw or print "[object Object]". The mock bodies validate against the v7 openapi.
- TECH-2-2 | 2892f00 | Active sends no `status`. A backend without the parameter answers Active exactly as before. Closed and All I can see still send the parameter.
- UX-2-1 | 2892f00 | The result count follows the search ("1 PROJECTS" for "lagoon"; Active badge still 22). Covered by a component test and e2e.

Left as is:
- UI-2-2 (title size, frame-owned, `src/shell/**`, a later frame task).
- UX-2-2 (phone access to closed projects; owned by product).
- Line `tone` and `status_label` are typed but not rendered. Spec criterion 6 keeps tag words and colours from STATE_TAGS until the contract moves to v7 (F-13).

## Acceptance criteria
1. [x] **List reads E-PROJECTS.** One GET, `?limit=20` (no status for Active). Six columns; cells come from the mock through `nextMilestoneText`. Covered by component tests and e2e.
2. [x] **Board elements.** A body without the PROPOSAL fields, or with the wrong shapes, still draws every element with "—" or "Not known". Tested for the list and the journey.
3. [x] **Search.** Debounced `?limit=20&q=lagoon`, no empty q, and the total reads "1 PROJECTS". Covered by component tests and e2e.
4. [x] **Paging.** Show more sends `?limit=20&cursor=o20` and ends with "All 22 showing". `?limit=10` and `?limit=7` behave as before.
5. [x] **Journey order and links.** Unchanged and tested. e2e: P-0101 line 7 opens W-1001.
6. [x] **State tags from STATE_TAGS.** Unchanged (table test).
7. [x] **Empty journey.** P-0105 behaves as before.
8. [x] **No access.** 404/403 names nothing: P-0099, and P-0104 for pm.
9. [x] **Wrong user.** No request is sent.
10. [x] **Signed out.** 401 leads to `next=`.
11. [x] **Load failures.** Covered as before.
12. [x] **Stale responses.** Covered as before.
13. [x] **Sample label.** Covered as before.
14. [x] **Mock honours the query.** Status default, all, closed, invalid; `total`; counts. The v6 contract part and the full v7 body are both schema-valid.
15. [x] **Accessibility.** axe and focus e2e are green at 390 and 1440. The Filter button is 44px.
16. [x] **Frame tests.** `frame.spec.ts` and `shell.test.tsx` are green; `src/shell/**` is untouched.
17. [x] **Product items.** Listed above and in round-2/build.md.

## Validation
- `cd /Users/Hunchoo/psl-factory-worktrees/f-07 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh` gave **exit 0**:
  - Django check passed.
  - npm ci, lint (0 warnings) and typecheck passed.
  - vitest: 17 files, **419 tests** passed.
  - next build passed.
- `cd frontend && E2E_PORT=3701 MOCK_PORT=3702 npm run test:e2e`: **111 passed** (7.1 min).
- **Fidelity:** production build on 3701 and the mock on 3702, persona pm. The cookie was rewritten to `path=/` through a scratchpad Playwright shim; the tool itself was not changed. Run with `--exceptions delivery/features/F-07/fidelity-exceptions.json`. Reports are in `delivery/features/F-07/round-3/fidelity/<board>-<width>/`.

| Board | Page | Coverage | Visual | Result |
|---|---|---|---|---|
| SCR-22-desktop 1440 | `/projects?status=all` | 95.7% (100% with exceptions) | 92.1 | PASS |
| SCR-22-mobile 390 | `/projects` | 88.9% (100% with exceptions) | 91.6 | PASS |
| SCR-07-desktop 1440 | `/projects/P-0101` | 95.7% (100% with exceptions) | 91.0 | PASS |
| SCR-07-mobile 390 | `/projects/P-0101` | 100% | 68 | FAIL, accepted by D-08 (in-page back link) |

- The first SCR-07-desktop run scored 84.4 because Google Fonts could not be reached and the board was drawn with fallback fonts. Two re-runs with the fonts loaded both scored 91.0, and the report on disk is from the passing run.
- 3701 and 3702 were stopped afterwards; only those listeners were killed. `frontend/test-results` was deleted. Disk had 11 GB free.
- Commits carry no AI attribution (the user's CLAUDE.md rule). `git status --porcelain` is empty. Pushed head is 2892f00.

## Blocked
Not blocked.
