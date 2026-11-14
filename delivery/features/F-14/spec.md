# The work item page and its history match the SCR-02 boards at 1440 and 390

> Tasks: FE-WORKITEM (R-WORKITEM, D-UPDATES; acceptance A-WORKITEM, A-HISTORY). Architecture: package `architecture/packages/v7` (openapi info.version `0a4f10a08cfe`, `manifest.sha256` file digest `2a5e21dbd3b4e1402025428553765687f497f15238c23ec844306c2332fc76ae`). The base frontend is still generated from v4 (`frontend/package.json:12`, info.version `fb663ed5d93f`) until F-13 merges. Base: `dlv-00-delivery-setup` at `8930da1`. Design: approved canvas version 1794581312-b166 (design/review.json, design check run by the coordinator: approved). Screens: SCR-02, artboards SCR-02-desktop, SCR-02-mobile, SCR-02-{desktop,mobile}-{ready, processing, waiting, verified, issue, cancelled, owner-needed, setup-needed, permission, effect-uncertain, awaiting-reconciliation, history}. Decision D-26 (design-check sweep of screens merged before the check). Precedent: F-02 round 3 (`delivery/features/F-02/round-3/build.md`, D-17, D-20).

## Summary
- The merged work item page (`/work/[id]`) and its history (`/work/[id]/history`) are rebuilt to the 26 SCR-02 boards: the desktop and phone default, the 11 state boards and history. Build each board's HTML structure, order, wording and styling, using token variables only.
- Each board passes the fidelity tool: coverage 100% after approved exceptions and visual ≥ 90, scored on the contract mock against new board fixtures W-1701 to W-1711 (plus the existing W-1099 for no access).
- When a board draws a value the API has no field for, it is filled from one optional, locally typed `presentation` block, marked PROPOSAL. Only the board fixtures carry it, and the page hides it when it is absent. A value is never left out because the contract lacks it.
- The phone back link moves into the frame slot (`usePhoneBack`) and page titles use the frame's 40px `.shell-title`. Everything F-03 does keeps working: the six facts, Unknown never zero, access, the decision link, history, paging and polling. The F-03 acceptance criteria still hold.
- The page stays read-only. Controls that take effect belong to F-04 (decide), F-09 (respond, reconcile) or have no operation in this scope. They are not faked. They appear in the exceptions file, and the F-09 seams stay clean.

## Context
- Routes: `frontend/src/app/work/[id]/page.tsx` and `frontend/src/app/work/[id]/history/page.tsx` are server components that render `WorkItemView` with `tab`. `frontend/src/app/work/[id]/decide/page.tsx` is F-04 and is not touched.
- Feature code, `frontend/src/features/work-item/` (902 lines):
  - `WorkItemView.tsx` holds `WorkItemHeader` (breadcrumb "My work / line / ref", `.shell-title`, state tag, "revision N"), `WorkItemTabs` (Overview, History), and the loading, error, no-access and signed-out branches.
  - `WorkItemOverview.tsx` exports `FactsStrip`, `StationTrack`, `AgentCard`, `TaskPanels`, `NextStep` and `WorkItemOverview`.
  - `WorkItemStates.tsx` holds `WorkErrorCard` and `NoAccessState`.
  - `WorkItemHistory.tsx` holds the filter radiogroup, rows per page, Show more and restricted rows.
  - `labels.ts` holds `STATE_TAGS`, `FACTS`, `STATIONS`, `AGENT_TAGS`, `nextStepKind` and `formatWat`.
  - The hooks are `useWorkItem.ts` (5 s polling while an agent is working) and `useWorkHistory.ts`. Styles are in `work-item.css`.
- Frame: `usePhoneBack({label, href})` in `frontend/src/shell/AppShell.tsx:32` (D-28, PR #17). It throws outside `AppShell`, so tests that render `WorkItemView` must render it inside `AppShell` with a stubbed E-ME, as `tests/shell.test.tsx:256` does. `.shell-title` is 40px on desktop and 26px on phones (`src/styles/shell.css:33,43`).
- Reusable pieces:
  - `DecisionRows` and `AmountValue` (`src/features/decide/DecisionContent.tsx:51,67`) render a task's Amount, Basis, To and Version from `tasks[].decision`.
  - The agent mascots are `public/agents/{chidi,tola,zainab}.png`, already used by My work.
- Mock:
  - `frontend/mock/server.mjs:66-77` (`workResponse`) already serves `fixtures/work/<id>.json` and `<id>.history.json` for any plain `W-\d+` id. W-1099 answers 404 and any other id falls back to the default fixture. New board fixtures therefore need **no server change**.
  - `tests/mock-contract.test.ts:219` validates every `fixtures/work` file against the schema with `_kind` stripped. The E-WORK-ITEM and history entry schemas have `additionalProperties: false`.
  - Ids W-10xx to W-16xx are used by base or open lanes (F-02 W-14xx, F-06 W-15xx, F-09 W-16xx). **W-17xx is free.**
- Neighbours on the same files:
  - F-09 (IMPLEMENTING, held) adds a `responseOf(task) ? <ResponseEntryLink/> : "Open the decision"` branch inside `TaskPanels` and a `<ReconcilePanel id item/>` mount in `WorkItemOverview`'s `.work-columns` (see `psl-factory-worktrees/f-09/frontend/src/features/work-item/WorkItemOverview.tsx:149-195`).
  - F-06 adds a "See all exceptions" link inside `NextStep` for exception states.
  - F-13 repoints the types to v7. Its additions to E-WORK-ITEM (`allowed_actions`, `reconcile`, `tasks[].response`) are absent from today's generated types.
- Board measurements before this work: F-03's page scored 48 to 59 on SCR-02 waiting and awaiting-reconciliation (D-25).

## Contract

### Endpoints (read only, unchanged)
| Operation | Request | 200 | Errors | Permission and tenant |
|---|---|---|---|---|
| E-WORK-ITEM `GET /api/v1/work/{work_id}` | path id | WorkItem (v4 types; v7 is additive) | 401 → frame signed-out callout with `next`; 403 and 404 → `NoAccessState`, which shows nothing about the item; 5xx or network → `WorkErrorCard` with Try again | Backend decides per record (INV-ACCESS). The page never infers access or authority from `me.roles`. |
| E-WORK-HISTORY `GET /api/v1/work/{work_id}/history?kind&limit&cursor` | `kind` ∈ all/decisions/agent_work/evidence, `limit` ∈ 10/20/50, `cursor` | `{items, next_cursor?, as_of}` | same as above, shown in the history area | same; restricted rows show when, actor kind, actor and "Restricted" only |

No POST, PUT or DELETE is sent from either page. Versioning: the history re-reads from page 1 when the item's `revision` changes (unchanged).

### PROPOSAL: board presentation (D-WORKITEM-VIEW, typed locally)
Typed in a new `frontend/src/features/work-item/presentation.ts` and marked `// PROPOSAL (D-WORKITEM-VIEW)`. It is read with a safe cast from the E-WORK-ITEM body, as F-02 did with `WorkListWithSuggestions`. The builder finalises the field names and lists each one in build.md as a contract proposal. Shape sketch:

```ts
type WorkItemPresentation = {
  back_label?: string;                       // phone history back link, e.g. "Invoice"
  facts?: Partial<Record<FactName, string>>; // visible detail per fact: "v2", "Ada", "To client 06 Nov", "Never"
  stations?: (string | null)[];              // visible detail per station index: "Approved 10:47", "Held · no reviewer"
  agent?: { role?: string; summary?: string; message?: string };   // "Finance agent", phone one-liner, card text
  panel?: {                                  // the board's state card (right column / phone block)
    title: string; body: string[]; quote?: string; note?: string;
    rows?: { label: string; value: string }[];
    links?: { label: string; href: string; primary?: boolean }[];  // navigation only
  };
  preview?: { /* issue board invoice preview: bill-to, number, lines, amount, tax note, template label */ };
  history_counts?: { all: number; decisions: number; agent_work: number; evidence: number };
};
// History entries may carry `lines?: string[]` (PROPOSAL): extra detail lines ("Note: …", "Used: …").
```

Rules:
1. **Contract first.** Use a contract field wherever one exists, never the proposal:
   - The header sub-line comes from `started_by` (name and role), `started_at` and `revision`, e.g. "Started by Tunde Bello (PMO) · Mon 10 Nov 14:05 · revision 2".
   - The decision rows come from `tasks[].decision` via `DecisionRows`.
   - Agent step times come from `agent.steps[].at`, and the amount from `amount`.
2. **Hide when absent.** With no `presentation`, every element renders exactly as the F-03 page does today. That covers W-1001 to W-1006, W-12xx and any live response.
3. **Unknown wins.** A fact whose contract status is `unknown`, or which is missing, reads "Unknown" whatever `presentation.facts` says (INV-UNKNOWN). It never reads blank, 0 or "No".
4. **Contract words stay in the accessible text.** Where the board shows a proposal detail instead of a mapped contract word, the contract word stays readable to screen readers. This applies to the fact status (Earned, In progress, Not yet, Unknown) and the station status (`STATIONS[...]`), so F-03's assertions on text still pass.
5. **Links are navigation only.** A `panel.links[].href` renders only when it is an app path starting with a single `/`. Absolute, protocol-relative (`//`) and `javascript:` hrefs are dropped.
6. **State tags use contract words.** The tag shows `STATE_TAGS[state]` (CMP-05), as with D-17. The board-only wordings are exceptions: AWAITING FINANCE DECISION, AGENT WORKING, WAITING ON CLIENT, APPROVED · READY TO SEND.
7. The mock sends `presentation` and `lines` only in W-17xx fixtures. The schema test strips them before validating, the same way it strips `_kind`, and validates them separately against the local type (see AC 17).

### Board fixtures (frontend/mock/fixtures/work/)
| Board (desktop and mobile) | URL | Cookie | Contract state and key data (from the board) |
|---|---|---|---|
| SCR-02-*(default) | /work/W-1701 | `psl_mock_persona=finance_lead` | `waiting`, INV-0412, a Finance Lead task with `you_can_act: true` and `decision` (₦4,250,000.00, "Contract stage 2 of 4 · terms v1", accounts@lagoonhealth.example, v2 changed: PO number), Chidi done |
| -ready | /work/W-1702 | `psl_mock_persona=pm` | `ready`, PLN-0160 Kora Logistics phase 2 plan, 6 stations, Tola |
| -processing | /work/W-1703 | `psl_mock_persona=pm` | `processing`, Chidi `working` step 3 of 4 with sources (this item polls) |
| -waiting | /work/W-1704 | `psl_mock_persona=pm` | `waiting`, REL-0077 release to UAT, Tola waiting |
| -verified, -history | /work/W-1705, /work/W-1705/history | `psl_mock_persona=finance_lead` | `verified`, all six facts earned; `W-1705.history.json` has the board's 7 entries with `_kind` |
| -issue | /work/W-1706 | `psl_mock_persona=finance_lead` | `ready` (approved, ready to send), invoice `preview` |
| -cancelled | /work/W-1707 | `psl_mock_persona=finance_lead` | `cancelled`, INV-0410 duplicate, link "Open INV-0412" → /work/W-1701 |
| -owner-needed | /work/W-1708 | `psl_mock_persona=pm` | `owner_needed`, INV-0419, station 4 `stopped` |
| -setup-needed | /work/W-1709 | `psl_mock_persona=pm` | `setup_needed`, PLN-0151 Ojo Foods |
| -permission | /work/W-1099 | `psl_mock_persona=finance_lead` | 404 (existing) |
| -effect-uncertain | /work/W-1710 | `psl_mock_persona=finance_lead` | `effect_uncertain`, `sent` unknown, Chidi waiting |
| -awaiting-reconciliation | /work/W-1711 | `psl_mock_persona=finance_lead` | `awaiting_reconciliation`, `sent` unknown |

Board sample text is copied exactly. Where boards of the same item disagree (for example "M2 invoice" on some phone boards and "Milestone 2 invoice" on the rest), the fixture follows the desktop board and the phone difference goes in the exceptions file.

### Screen states
- **Loading:** the frame `LoadingState`. The phone back link is "← Queue" to /my-work.
- **Error (5xx or network):** `WorkErrorCard` with "Reference <code> for support." and Try again.
- **No access (403/404):** the SCR-02-*-permission board: NO ACCESS tag, "You can't open this work item", the two guidance paragraphs as each board words them, and "Back to my queue" to /my-work. The id and title never appear.
- **Signed out (401):** the frame callout with `next`.
- **Success:** each state board as drawn. Section order follows each board, and phone boards order sections differently per state (for example, processing puts the agent before the stations). Keep that order in one per-state layout map in `WorkItemOverview.tsx`, not scattered conditions.
- **Phone disclosures:** "See his steps" (default phone board) shows and hides the agent steps, and "Preview the invoice" (issue phone board) shows and hides the preview. They only change what is on screen and send no request. Each has `aria-expanded`.
- **History:**
  - Desktop shows tabs Overview and History with counts from `history_counts`, the filter with counts, the WHEN / WHAT HAPPENED / VERSION table with the actor tag, event, `detail` and `lines`, and the "About history" aside.
  - Phone shows the HISTORY eyebrow, the "History · <ref>" title, a stacked list, and "← <back_label or 'Work item'>" to /work/{id}.
  - The rows-per-page control and Show more stay, as F-03 requires.
  - When `history_counts` is present, the phone button reads "+ N earlier entries", with N = the filter's count minus the rows loaded. Otherwise it reads "Show more".

### Controls the boards draw, and how each is built
| Control | Built as |
|---|---|
| Open the decision (desktop default and phone "Review and decide") | The existing link to `/work/{id}/decide?task={tid}`, shown only when `you_can_act` (F-03 AC 7). The desktop board's Note field and Approve v2 / Return / Reject buttons, and the phone wording "Review and decide", are exceptions: the decision is taken on SCR-03 (F-04), with its version and stale checks. |
| Fix it in Setup, Open Setup | link → `/setup` from `panel.links` |
| Ask Chidi | link → `/assistant` from `panel.links` |
| Open INV-0412 | link → `/work/W-1701` from `panel.links` |
| See in Verified outputs | link → `/my-work?queue=done` from `panel.links` |
| See all exceptions | F-06's link inside `NextStep`. F-14 does not add it; on the base it is an exception until F-06 merges. |
| Record the client's response, the reconcile choices, Record and continue | F-09 (`ResponseEntryLink`, `ReconcilePanel`). Exceptions here. |
| Issue and send INV-0412, Tell the PMO Lead, Ask for access, Change the reminder, Documents tab, "This attempt is recorded in the audit history." | No operation or page in this scope, and a dead button would claim an effect. Exceptions with the reason. |
| Start work, signed-in name, top-bar items | Frame items (F-05, `src/shell`). Exceptions as in D-17. |

## Lanes
- **Frontend lane (builder)** owns:
  - `frontend/src/features/work-item/**`: restructure freely, add `presentation.ts`, a state panel, the invoice preview and the phone disclosures. Restyle `work-item.css` with token variables only.
  - `frontend/src/app/work/[id]/page.tsx` and `frontend/src/app/work/[id]/history/page.tsx`. Change them only if needed; metadata titles never name the item.
  - New fixtures `frontend/mock/fixtures/work/W-1701.json` to `W-1711.json` and `W-1705.history.json`. Existing fixtures are unchanged.
  - Tests: `frontend/tests/work-item.test.tsx` (wrap in `AppShell`, update assertions only where listed in build.md), a new `frontend/tests/work-item-board.test.tsx`, `frontend/tests/mock-contract.test.ts` (only the strip and proposal check in the fixtures test), `frontend/e2e/work-item.spec.ts` and a new `frontend/e2e/work-item-board.spec.ts`.
  - Factory files: `delivery/features/F-14/fidelity-exceptions.json` (provisional, proposed by the builder, confirmed by the design engineer) and `delivery/features/F-14/round-<N>/fidelity/**` (reports, `scores.txt`, the driver scripts).
- **Shared, read only (import, do not edit):** `frontend/src/shell/**` (call `usePhoneBack`; do not export its context), `frontend/src/api/**`, `frontend/src/styles/**`, `frontend/src/features/decide/**` (import `DecisionRows` and `AmountValue`), `frontend/src/features/my-work/**`, `frontend/mock/server.mjs`, `frontend/mock/work-list.mjs`, `frontend/package.json`, the lock file, `playwright.config.ts`, `vitest.config.ts`, `architecture/**`, `design/**`, and the protected `delivery/checks.sh`, `delivery/config.json` and `delivery/merge-policy.json`.
- **F-09 seams (binding):**
  - Keep the `TaskPanels({ id, tasks })` export name and props.
  - Inside it, the `you_can_act` branch that renders "Open the decision" stays one expression, so F-09 can wrap it with its `responseOf(task)` ternary.
  - `WorkItemOverview` keeps one marked slot, `{/* F-09: ReconcilePanel mounts here */}`, in the place the awaiting-reconciliation boards draw the panel. Nothing else of F-14 sits inside that slot.
  - `NextStep`'s markup is not edited (F-06 adds to it). F-14 places and styles it from outside.
- **Backend lane:** none. No `apps/`, API, OpenAPI or business-rule change.
- **Integration owner:**
  - Whichever of F-14 and F-09 merges second rebases and re-scores. F-09 most likely rebases onto F-14.
  - After F-14 merges, the coordinator re-runs F-09's SCR-02 waiting and awaiting-reconciliation scores.
  - If F-13 (v7 types) merges first, replace the local casts with the generated fields where they overlap (`reconcile`, `allowed_actions`) and note it in build.md.
- **Ports:** app 4501, mock 4502. E2E: `cd frontend && E2E_PORT=4501 MOCK_PORT=4502 npx playwright test e2e/work-item.spec.ts e2e/work-item-board.spec.ts`. Score with a production build (`next build` then `next start -p 4501`, mock on 4502), as F-02 round 3 did, so no dev overlay shows. Delete `frontend/test-results` afterwards and check `df` before long runs.
- **Review routing:**
  - Technical (medium → sonnet).
  - UI with the fidelity gate on all 26 boards (haiku).
  - UX (sonnet).
  - Then QA (opus).
  - No security review (surfaces: ui). Product acceptance is not required. The design engineer confirms the exceptions file (PMO checks it is marked provisional).

## Acceptance criteria
1. **Desktop fidelity.** Each of the 13 desktop boards passes at 1440: report.json has `pass: true`, `scores.coverageWithExceptions` = 100 and `scores.visual` ≥ 90. The boards are SCR-02-desktop and SCR-02-desktop-{ready, processing, waiting, verified, issue, cancelled, owner-needed, setup-needed, permission, effect-uncertain, awaiting-reconciliation, history}, each with the URL and cookie from the fixture table. — verify, per board:
   ```
   node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs \
     --playwright <worktree>/frontend/node_modules/playwright/index.mjs \
     --board /Users/Hunchoo/psl-factory/design/canvas/project/SCR-02-desktop-waiting.dc.html \
     --page http://localhost:4501/work/W-1704 --width 1440 \
     --cookies psl_mock_persona=pm \
     --exceptions /Users/Hunchoo/psl-factory/delivery/features/F-14/fidelity-exceptions.json \
     --wait-ms 500 --out /Users/Hunchoo/psl-factory/delivery/features/F-14/round-<N>/fidelity/SCR-02-desktop-waiting-1440
   ```
   The command exits 0. `round-<N>/fidelity/scores.txt` lists all 13 boards with their scores.
2. **Phone fidelity.** The same holds for the 13 `SCR-02-mobile*` boards at `--width 390`, with `--out …/SCR-02-mobile-<state>-390`. — verify: the same command shape, exit 0, and the rows in `scores.txt`.
3. **Exceptions are limited and explained.** Every entry in `delivery/features/F-14/fidelity-exceptions.json` has `role`, `name`, `reason` and `approved_by` (`"builder proposal, pending design engineer"` until confirmed). Each falls into one of these categories:
   - frame items;
   - controls owned by F-04, F-05, F-06 or F-09;
   - effects with no operation in scope (the Controls table);
   - contract state words (Contract rule 6);
   - disagreements between boards.

   No entry may cover a value that a contract field or the presentation block can supply. — verify: file content, and build.md maps each entry to its category.
4. **Phone back link in the frame slot.** At 390, /work/W-1701, /work/W-1099 and the loading state show the phone bar link "← Queue" to /my-work in place of Menu. /work/W-1705/history shows "← Invoice" to /work/W-1705. A history page with no `back_label` shows "← Work item". `main` contains no back link of its own. At 1440 the phone bar is not shown. — verify: e2e at both widths, plus a component test rendered inside `AppShell`.
5. **Titles.** The item `h1` uses `.shell-title`, with a computed `font-size` of 40px at 1440 and the board's phone size at 390. There is one `h1` per page, including no access. — verify: e2e reading `getComputedStyle`.
6. **The six facts (A-WORKITEM) still hold.** The F-03 facts tests pass unchanged on W-1004: six boxes, Earned with times, Sent "Not yet", Receipt recorded "Unknown", Verified "Not yet", the Paid note, and never blank or 0. On W-1705 the visible fact details are the board's ("v2", "Ada", "10:47", …), and each box's accessible text still contains its contract status word. — verify: existing and new component tests.
7. **Unknown wins over presentation.** A fixture whose `sent` is `unknown` but whose `presentation.facts.sent` is "Delivered" shows "Unknown" for Sent. W-1710's Sent reads "Unknown". — verify: component test with a crafted fixture.
8. **Stations.**
   - Each station shows its number, its name, and the `presentation.stations[i]` detail, or the `STATIONS` word when the detail is absent.
   - The current station has `aria-current="step"`, and the effect-uncertain station keeps its amber look.
   - At 390 there is no sideways page scroll on any W-17xx page (`document.documentElement.scrollWidth <= 390`).
   - The existing station e2e tests pass.

   — verify: component tests and e2e.
9. **Header from the contract.** W-1701 shows the breadcrumb (My work / Prepare an invoice / INV-0412), the title, the state tag `STATE_TAGS.waiting`, and "Started by Tunde Bello (PMO) · Mon 10 Nov 14:05 · revision 2", all from `started_by`, `started_at` and `revision`. A fixture without `started_by` shows only "revision N". — verify: component test.
10. **Decision summary, right person only.**
    - W-1701 (`you_can_act: true`) shows the rows Amount ₦4,250,000.00, Basis, To and Version, all from `tasks[].decision` through `DecisionRows`, plus "Only a Finance Lead can decide.", "You are Finance Lead." and the link "Open the decision" to `/work/W-1701/decide?task=<task id>`.
    - Wrong user: W-1002 (`you_can_act: false`) has no link or button in its task panel.
    - The page has no Approve, Return or Reject control and no Note field.

    — verify: component tests on both fixtures.
11. **The agent card never offers a decision.**
    - On every W-17xx fixture and on W-1003, the agent card shows the name, the role ("Finance agent" or "PMO agent"), the mascot image with alt text, and the board message. Steps and times appear where drawn.
    - The card contains no button or link whose name matches /approve|send|pay/i.
    - "Cannot approve, send or pay." stays.

    — verify: a table-driven component test over the fixtures.
12. **State panels.** Each state fixture shows its board's panel heading and body:
    - W-1702 "Ready to begin";
    - W-1703 "Drafting the invoice";
    - W-1704 "Waiting on the client";
    - W-1705 "Verified" and "Verified doesn't mean paid";
    - W-1706 "Issue and send · Finance", with the invoice preview marked "TEST TEMPLATE · NOT PSL'S REAL INVOICE";
    - W-1707 "Cancelled", with the quoted reason;
    - W-1708 "Stopped · owner needed";
    - W-1709 "Setup needed";
    - W-1710 "Awaiting reconciliation", with the Sent at / Checks / If not found rows.

    `NextStep` is still rendered with `item.next_step` and its mapped callout kind on every state. W-1005 keeps its warning callout. — verify: a table-driven component test, plus the F-03 next-step test unchanged.
13. **Navigation links only, and safe.**
    - The panel links go to: W-1708 "Fix it in Setup" → /setup; W-1709 "Open Setup" → /setup; W-1703 "Ask Chidi" → /assistant; W-1707 "Open INV-0412" → /work/W-1701; W-1705 "See in Verified outputs" → /my-work?queue=done.
    - A crafted panel with hrefs `https://x.example`, `//x.example` and `javascript:alert(1)` renders none of those links.

    — verify: component tests.
14. **Read only, no effects.**
    - Opening and using the overview and history of every W-17xx and W-10xx fixture (including clicking the phone disclosures, the filter, rows per page and Show more) sends only GET requests to E-WORK-ITEM and E-WORK-HISTORY.
    - The only `<button>` elements are the disclosures (with `aria-expanded`), the history controls and Try again.

    — verify: a component test recording the method and URL of every stubbed `fetch` call.
15. **No role guesses.** W-1708 and W-1709 render identically for the stubbed personas finance_lead and pm. Their text comes from the record, not from `me.roles`. — verify: a component test comparing `container.innerHTML` under both E-ME stubs.
16. **No access, signed out and error states (F-03 AC 10 to 12 hold).**
    - W-1099, a 403 and a 404 show the permission board with "Back to my queue" to /my-work, and the requested id is absent from `document.body.textContent`.
    - A 401 shows the signed-out callout with `next=/work/W-1001`.
    - A 500 then 200 sequence shows the error card, and Try again then shows the item.

    — verify: the existing tests, run inside `AppShell`.
17. **Mock fixtures are valid and proposals are contained.**
    - Every `fixtures/work` file validates against the generated E-WORK-ITEM or E-WORK-HISTORY 200 schema once `_kind`, `presentation` and entry `lines` are stripped.
    - `presentation` validates against a JSON schema written in the test from the local type.
    - Only W-17xx files contain `presentation` or `lines`.
    - The existing fixtures are byte-for-byte unchanged (`git diff --stat` shows no edits to them).
    - An unknown id (W-1799) still falls back to the default fixture.

    — verify: `tests/mock-contract.test.ts`.
18. **History (A-HISTORY) on the boards.**
    - /work/W-1705/history at 1440 shows tabs Overview and History 7, the filter (All 7, Decisions 2, Agent work 2, Evidence 1), the columns WHEN / WHAT HAPPENED / VERSION, and 7 rows newest first. Each row has the WAT time, the actor tag, the actor, the event, the detail lines and the version, plus the "About history" aside.
    - At 390 it shows the HISTORY eyebrow, "History · INV-0412" and the stacked rows.
    - Without `history_counts`, there are no count badges and the button reads "Show more".
    - The F-03 history tests pass: order, "12 Nov 16:40", restricted rows hiding event, detail and version, read-only controls, kind, limit and cursor requests, and the empty filter.

    — verify: component tests, plus the existing e2e (10 rows, then 12 after Show more, then no Show more).
19. **Updates (D-UPDATES) unchanged.** W-1703 (agent working) re-reads every 5 s while visible and stops when hidden. The other W-17xx items never poll. — verify: the existing polling tests, plus one fake-timer test on W-1703.
20. **Accessibility at both widths.** Every W-17xx URL, /work/W-1099 and /work/W-1705/history has:
    - no axe violations at 390 and 1440;
    - no sideways page scroll;
    - visible focus outlines on the tabs, links, disclosures and history controls;
    - no animation on the current agent step with `reducedMotion: 'reduce'`.

    — verify: `cd frontend && E2E_PORT=4501 MOCK_PORT=4502 npx playwright test e2e/work-item-board.spec.ts e2e/work-item.spec.ts` with `timezoneId: 'Africa/Lagos'`. Record the output in build.md.
21. **Tokens only.** `grep -nE "#[0-9a-fA-F]{3,8}\b|rgba?\(|hsl\(" frontend/src/features/work-item/work-item.css` returns nothing. Colours, font families, radii and spacing come from `var(--…)` tokens. — verify: the command.
22. **F-09 seams.**
    - `grep -n "export function TaskPanels({ id, tasks }" frontend/src/features/work-item/WorkItemOverview.tsx` matches.
    - The "Open the decision" link is one JSX expression inside `TaskPanels`.
    - `grep -n "F-09: ReconcilePanel mounts here"` matches exactly once.
    - `NextStep`'s returned markup is identical to the base: `git diff 8930da1 -- frontend/src/features/work-item/WorkItemOverview.tsx` shows no change inside `NextStep`.
    - build.md has a short rebase note for F-09.

    — verify: the commands and build.md.
23. **Existing suites pass.** `tests/work-item.test.tsx`, `tests/decide*.test.tsx`, `tests/my-work*.test.tsx`, `tests/shell.test.tsx`, `e2e/work-item.spec.ts` and `e2e/decide.spec.ts` pass. Every changed assertion in the F-03 tests is listed in build.md with its reason; only the visible wording and wrappers move, not the behaviour. The F-03 acceptance criteria in `delivery/features/F-03/feature.json` still hold. — verify: `delivery/checks.sh` and build.md.
24. **build.md evidence.** build.md contains:
    - the contract proposal list (each `presentation` field and `lines`, with the boards that need it);
    - `scores.txt` for all 26 boards;
    - `side-by-side.png` paths for each board;
    - per board under 90, the measured gap and its cause, following the readiness split rule.

    — verify: file content.

## Out of scope
- Any backend, `apps/`, OpenAPI, `architecture/**` or `src/api/**` change. No new npm dependencies, and no edits to `mock/server.mjs` (per-id fixtures already load).
- The decision page SCR-03 and any decision taken on the work item page: no Approve, Return or Reject buttons, no Note field, no E-TASK-CLAIM or E-TASK-DECIDE (F-04, D-26's own round).
- The respond route, `ResponseEntryLink`, `ReconcilePanel` content and the reconcile choices (F-09). F-14 leaves only the seams.
- The "See all exceptions" link and any other `NextStep` behaviour (F-06). Also excluded: the shell, top bar and Start work (`src/shell/**`, F-05), and `my-work/**`.
- The Finance-canvas SCR-02 boards (`design/canvas/finance/project/SCR-02-*-returned|evidence-asked|evidence-supplied`).
- Issue and send, reminders, access requests, "Tell the PMO Lead", a Documents tab or page, and audit logging of access attempts. There is no operation for them in scope, and they are not drawn as dead controls.
- Deriving board wording from `me.roles` or the line name in the frontend, client-side access checks, and showing board-only state words in place of the contract's words.
- Changing the polling interval, history paging or the restricted-row rule, or removing the rows-per-page control the boards don't draw.

## Assumptions
- Board data comes from new W-17xx fixtures, not a cookie dataset. The mock already serves per-id files, and the existing W-10xx/W-12xx fixtures and F-03 tests stay untouched.
- One `presentation` block, not many fields on contract objects. This keeps the proposal in one place that is easy to remove, and stripping it keeps the strict schema test meaningful.
- The decision buttons and Note on SCR-02-desktop are exceptions, and "Open the decision" stays. Reasons: F-03 AC 7 and F-09's acceptance rely on it, and deciding needs F-04's version and stale-version checks. **The approver may escalate this to the design engineer.**
- State tags keep the CMP-05 contract words. This follows D-17 for My work.
- The breadcrumb keeps "My work / line / ref". The boards disagree among themselves ("QUEUE /", "MY WORK /", or a "REF · CLIENT" eyebrow), and D-17 accepts contradictions between boards as exceptions.
- The issue board is a `ready` item, read as the "approved, ready to send" step (design log 12 Nov). Its preview is proposal data with the TEST TEMPLATE label (memory: test templates until PSL supplies real ones).
- Personas follow the board's signed-in user: pm (Tunde Bello) for the PMO boards, finance_lead (Ada Okafor) otherwise. The Bisi Adeyemi boards (issue, permission) use finance_lead, and the frame's name is an exception.
- "See in Verified outputs" goes to `/my-work?queue=done`. Verified is My work's Done/Verified tab (design log 12 Nov), and `done` is the base contract's queue name.
- The phone history back label comes from `presentation.back_label`, with "Work item" as the fallback. The board says "← Invoice", and the noun is not in the contract.
- **Awaiting-reconciliation boards:** most of what they draw is F-09's panel. If visual stays under 90 with that area as an exception, build.md shows the gap is confined to that region, and the coordinator re-scores after F-09 merges (readiness Order). **The approver may escalate this carve-out.**
- Tests render `WorkItemView` inside `AppShell` with a stubbed E-ME, rather than exporting the phone-back context, because `src/shell/**` is read only.
- Ports 4501/4502 are not used by any other feature's spec.
