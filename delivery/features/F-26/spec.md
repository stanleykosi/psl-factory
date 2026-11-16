# A project's Money tab: each contract stage's amount, invoice and paid state as the backend sends them, and where each amount comes from (contract mock only)

> Tasks: FE-M3-REPORT (R-PROJECT, R-REPORTS; acceptance A-PROJECT and A-REPORT, frontend half). Architecture: package `architecture/packages/v7`, manifest sha256 `f6231d20b4fdeabbdca9bde5986a0a7883536f1a5cafc883848ef62dd6d4b624`; FE-M3-REPORT at `architecture/packages/v7/delivery.md:1502`, no unresolved gates; E-PROJECT-TAB and E-REPORT typed in `frontend/src/api/schema.d.ts:285` and `:631` (this feature changes no generated type). Design: approved canvas version 1794581312-b166; `python3 /Users/Hunchoo/software-factory/packages/design/design.py check --project .` run before writing this spec: `EXCEPTION`, `passes: true` (D-89 frame change only). Screens: SCR-12, 2 artboards: `SCR-12-desktop`, `SCR-12-mobile` (`design/canvas/project/`). Decision consumed: D-PROJECT-TAB-ROWS (proposed, recorded exception `architecture/sources/decisions-2026-11-15.md` items (g), (i)). Readiness: `delivery/features/F-26/readiness.md` (READY, risk high). Shape: `delivery/features/F-21/spec.md`.

## Outcome
A person who may see a project opens `/projects/<case_id>/money`. They read each contract stage's amount, invoice state and paid state exactly as the backend returns them, and press an amount to see the sources of that figure (`?figure=<id>`, linkable and reloadable). Reads only. Nothing on the page calculates, totals, rounds, infers or decides.

## Boards
| Board | Width | Page scored | How reached |
|---|---|---|---|
| `SCR-12-desktop` | 1440 | `/projects/P-0101/money?figure=FIG-0101-S2` | live URL (deep link opens the panel for Stage 2) |
| `SCR-12-mobile` | 390 | `/projects/P-0101/money` | live URL (no figure selected; the phone board draws no sheet) |

The `loading` state in `design/screens.md:35` has no board: it is the shared loading state, with no fidelity target. Persona for both: `finance_lead` (the mock default; the desktop board's signed-in person is "Ada Okafor · Finance Lead").

## Conflicts with the boards (pending the design engineer)

Each item is a place where this spec adds, moves or removes something a board draws. "Recommend" is what this spec builds if no answer comes; every item is `pending design engineer` and becomes one entry in `fidelity-exceptions.json` with `approved_by: "builder proposal, pending design engineer"`.

1. **Page title and eyebrow.** The desktop board's h1 is "Lagoon Health · billing by contract stage" under the eyebrow "REPORT · LAGOON HEALTH · PROJECT MONEY"; the phone h1 is "Lagoon Health · billing". The project page's h1 is E-PROJECT `title` ("Lagoon Health · patient app") in the shared F-07 header (`ProjectJourney.tsx` `ProjectView`), which F-25 also keeps for every tab. E-PROJECT has no report title or eyebrow field. **Recommend:** keep the shared h1 and breadcrumb unchanged; show E-REPORT `title` (fixture: "Lagoon Health · billing by contract stage") as the Money panel's h2 at both widths when the report loads; do not build the eyebrow (the frontend composes no title; contract proposal 5). Exceptions: h1 text, eyebrow, phone h1 wording.
2. **Desktop board shows the panel already open on Stage 2.** No field says which figure to open on load, and opening the first one would be a guess. **Recommend:** nothing is selected on load; the aside then shows "Choose an amount to see where it comes from." (new neutral copy) above the Chidi card; `?figure=<id>` opens a figure; the desktop board is scored on `?figure=FIG-0101-S2`.
3. **Amounts drawn without decimals** ("₦3,000,000", "Where ₦4,250,000 comes from"). The shared formatter (`components/format.ts` `formatAmount`, rendered by `Money` in `components/Values.tsx`) always writes two decimals and never rounds ("₦3,000,000.00"), the rule F-14, F-16 and F-18 already follow. **Recommend:** keep the shared format everywhere on the page, panel title included. Exception per amount string.
4. **Stage 4's note sits in the INVOICE column on desktop** ("Not yet due · amount set at go-live"). In the contract it is `amount_note`, a fact about the amount; the phone board draws it under the amount. **Recommend:** at both widths show `amount_note` under the amount in the AMOUNT cell; the desktop INVOICE cell for a stage with no invoice fields shows "—" (see 5). Exception: desktop cell position.
5. **"—" in the PAID and INVOICE columns.** The contract has an explicit `paid.status` (`paid`, `part_paid`, `not_paid`, `not_due`, `finance_tracks`, `unknown`) but the board draws "—" for three stages. The frontend cannot tell "no value is due" from "the value is missing" without a field (readiness rule 1, D-94 split). **Recommend:**
   - PAID: `paid.status: not_due` shows "—" with visually hidden text "Not due"; `paid` absent shows "Unknown" (amber, `Unknown` component), never "—"; every other status shows its fixed words (Contract, paid words). The board fixture P-0101 sends `not_due` for stages 2 to 4 (sample data; the real value is the backend's).
   - INVOICE: neither `invoice_status` nor `invoice` sent shows "—" with visually hidden text "No invoice" (an invoice is a record that exists or not; the contract has no unknown form for it). Backend question recorded in build.md: confirm that an absent `invoice` means "no invoice yet" and that an unknown paid state is always sent as `paid.status: unknown`, never by omission.
6. **Invoice status as a link.** The board draws "Verified 03 Nov" as plain text. Readiness rule 3 makes the invoice a link to its work item when `invoice.work_id` exists. **Recommend:** the `invoice_status` text itself is the link (`/work/<work_id>`), with `invoice.reference` in the link's accessible name only (visually hidden ", INV-0398"); no extra visible text. Exception: link colour and underline.
7. **The phone board has no PAID line.** Paid is a separate Finance fact (INV-FACTS) and should not vanish at one width. **Recommend:** the phone card adds one muted line "Paid · <words>" under the invoice line, omitted only when the status is `not_due` (where desktop shows "—"). Exception: extra line on the stage 1 card ("Paid · Finance tracks"). Alternative for the design engineer: follow the board and drop paid on phones.
8. **Phone drill-down.** The phone board draws the amounts as plain text, "Tap an amount to see where it comes from" as a link to `#`, and no sheet. **Recommend:** each amount with a matched figure is a standalone link, 44px tall (D-92c); the sentence is plain text (it has no destination); pressing an amount opens the shared `BottomSheet` with the same content as the desktop aside (title, sources, Chidi card); closing returns focus to the pressed amount. Exceptions: the sentence is not a link; amount link styling.
9. **Sources.** The board's source rows ("Signed SOW v2, stage table, row 2 · SOW-0198 v2"; "Stage terms v1, active since 30 Jun · RULE · stage terms"; "Milestone 2 completion, recorded by Tunde Bello · HB-M2") are backend `label` plus `reference` strings in the fixture, so they match without a structured version field (G-SCR12-1 stays a proposal). No document page exists in `frontend/src/app`, so a `document_id` source is text, not a link; a `work_id` source is a link to `/work/<work_id>`. The board fixture's three sources carry no `work_id`, matching the plain board text. Not a difference unless the design engineer wants document links.
10. **Chidi card wording.** The board says "I can explain any figure here. Ask me". "Ask me" can only be a plain link to `/assistant?agent=chidi` (G-SCR12-2 not built), which carries no figure; the card must not promise an explanation the backend does not give (D-100). **Recommend:** "Ask me about any figure here." with "Ask me" as the link; name and role from `AGENTS[report.agent]` ("Chidi · Finance agent"); the card shows only when E-REPORT sends `agent` and `/me` lists `assistant` (as `AgentSummary` in `ProjectJourney.tsx`). Exception: card sentence. Alternative: keep the board's words once G-SCR12-2 lands.
11. **"As of" line added.** Neither board draws a time. Readiness rule 5 requires E-PROJECT-TAB `as_of`. **Recommend:** "As of 12 Nov 16:40" (`When show="daytime"`) under the table at both widths. Exception: extra text.
12. **"These figures differ" line.** Shown only when the opened figure's value differs from its row's amount (readiness rule 5); no board draws it. Not on either scored page.
13. **The explanatory sentence.** "Every figure links to the record it came from. Unknown amounts are shown as Unknown, never as 0." is board copy on desktop only; the phone board omits it. **Recommend:** follow the boards (desktop only). Note for the design engineer: a stage with no source (Stage 4 in the board fixture) has no link, so "Every figure links" is not literally true for that row; the copy is the board's.
14. **No access inside the tab.** Readiness rule 6 says a 403 or 404 on the Money read shows the existing `ProjectNoAccess`. In the tab panel its sentence "Nothing about it is shown here, not even its name" contradicts the project title still visible above it. **Recommend:** build rule 6 as written (no stage, no amount, no report title in the DOM); Option B for the design engineer: a money-specific line "You can't see this project's money." in the panel. No board draws either.
15. **Frame items.** Top bar, signed-in name, "+ Start", breadcrumb "Projects / Lagoon Health", the phone back link (the page's "← Projects" vs the board's "← Project"), tab counts from `tab_counts` (Money has none, as drawn). Exceptions, as F-07.

## Summary
- `/projects/<case_id>/money` shows a STAGE / AMOUNT / INVOICE / PAID table (cards on phones) from E-PROJECT-TAB `money[]`, in `position` order, with "As of …".
- An Unknown amount, owed value or figure value reads "Unknown" in amber, never 0, ₦0, blank or a dash. There is no total, sum, balance, percentage or "outstanding" figure anywhere.
- Invoice and paid are separate cells from separate fields; paid words come from one fixed table; nothing is inferred from the invoice.
- Pressing an amount opens "Where ₦X comes from" with the figure's own sources from E-REPORT (aside on desktop, BottomSheet on phones); a missing source reads "No source recorded"; a report failure keeps the table.
- Contract mock only: E-PROJECT-TAB (`money`) and E-REPORT are unimplemented in the backend; the backend developer may change or refuse any field; nothing is released.

## Context
- Page: `frontend/src/app/projects/[caseId]/[tab]/page.tsx` already routes `money` to `ProjectJourneyPage` (`frontend/src/features/projects/ProjectJourney.tsx`), which today renders `ComingNext` for every tab but Journey (`ProjectView`, line ~198). The header, `ProjectTabs` (`ProjectTabs.tsx`, `PANEL_ID`), the E-PROJECT read (`useProject.ts`), `ProjectNoAccess` (`ProjectStates.tsx`), the 401 and error handling (`SignedOutState`, `LoadingState` from `src/shell/FrameStates`, `WorkErrorCard` from `features/work-item/WorkItemStates`) are F-07's and are reused unchanged.
- Types: `operations['E-PROJECT-TAB']` and `operations['E-REPORT']` in `frontend/src/api/schema.d.ts`; client `api.GET` / `call` in `src/api/client`, `ApiError` in `src/api/errors`.
- Shared library (D-91..D-93, `frontend/src/components/README.md`): `Table`, `Panel`, `BottomSheet`, `useIsPhone`, `Money`, `Unknown`, `When`, `formatAmount`, `groupDigits`, `Link`, `AgentAvatar`, `AGENTS`, `agentKey`, `EmptyState`, `Loading`, `ErrorState`, `Callout`, `VisuallyHidden`.
- Mock: `frontend/mock/server.mjs` (dispatch; E-PROJECT-TAB and E-REPORT fall to `501 not_mocked` because neither is in `M1_OPERATIONS`), `frontend/mock/projects.mjs` (persona visibility from `fixtures/projects/list.json`; `P-0099` is the no-access id). P-0101 "Lagoon Health · patient app" lists invoice work items W-1713 (INV-0398, verified), W-1001 (INV-0412, waiting) and W-1714 (INV-0419, owner needed), which the money fixture reuses.
- Tests asserting 501 today: `frontend/tests/mock-contract.test.ts:192` (E-REPORT, changes here) and `frontend/tests/mock-projects.test.ts:209` (E-PROJECT-TAB `milestones` and E-DOCUMENT; unchanged by F-26, since milestones stays 501).

## Contract

### E-PROJECT GET `/api/v1/projects/{case_id}` (unchanged)
Read once by `useProject` as today. F-26 adds no request. The Money tab is in the tab bar for everyone who can open the project; the frontend has no role rule.

### E-PROJECT-TAB GET `/api/v1/projects/{case_id}/money` (read; new consumer)
- **Request:** `api.GET('/api/v1/projects/{case_id}/{tab}', { params: { path: { case_id, tab: 'money' } } })`. No `q`, `cursor` or `limit` (four to a handful of stages; no paging control on the board). One read per tab open; a late answer for an earlier case is ignored (`useProject` pattern). No polling, no retry except the person's "Try again".
- **200:** read `money[]`, `summary.report_id`, `as_of`. `items` is ignored (v5 untyped). If `money` is absent or a row fails the guard (`position` integer, `stage` text, `amount` object with `currency` and boolean `unknown`), the tab shows the error card; nothing partial is drawn and nothing is read from `items`.
- **Rows** in ascending `position`; no other re-ordering, no grouping, no extra rows.

| Cell | Shows (backend composes; frontend formats only) |
|---|---|
| STAGE | `stage` as sent |
| AMOUNT | `amount.unknown === true` or `amount.amount` missing: "Unknown" (amber `Unknown`). Else `amount.currency === 'NGN'`: `formatAmount(amount.amount)` ("₦4,250,000.00"); other currency: `formatAmount(amount.amount, { sign: false })` then a space and the code ("1,200.00 USD"). String handling only (`formatAmount`/`groupDigits`); never `Number()`, `parseFloat` or arithmetic. `amount_note` under it, muted, when sent. The amount is a link only when the row's `figure_id` matches a loaded `figures[].id` (Drill-down). |
| INVOICE | `invoice_status` as sent; if absent, `invoice.reference`; if both absent "—" (hidden "No invoice"). Linked to `/work/<invoice.work_id>` when sent (reference in the accessible name). `invoice.state` and `invoice.at` are not re-worded (the composed `invoice_status` carries them). |
| PAID | `paid` absent: "Unknown" (amber). Else the words for `paid.status` from the fixed table below, then " · <owed> owed" when `paid.owed` is sent (owed unknown: " · owed Unknown", amber). Never derived from INVOICE. |

**Paid words** (presentation only, one constant `PAID_WORDS` in `moneyModel.ts`): `paid` "Paid", `part_paid` "Part paid", `not_paid` "Not paid", `not_due` "—" (hidden "Not due"), `finance_tracks` "Finance tracks", `unknown` "Unknown" (amber). A status outside the enum shows its raw value as text.

- **as_of:** "As of 12 Nov 16:40" (`When show="daytime"`, Africa/Lagos) under the table/cards. Missing or unreadable: "As of Unknown".
- **Errors:** 401 → `SignedOutState` with `pathname` `/projects/<id>/money`. 403 and 404 → `ProjectNoAccess` in the tab panel; no stage, amount, report title or server message appears and E-REPORT is not called (Conflicts 14). 5xx, network or bad shape → `WorkErrorCard` "We couldn't load this project's money. Your work is safe; nothing was changed." with "Try again" (re-reads E-PROJECT-TAB only).
- **Permission and tenant:** backend decides (`case.read` plus `finance.read`, endpoints.csv row E-PROJECT-TAB; 404 hides records). The frontend sends no persona, role or tenant hint and reads nothing from `/me` for this decision.
- **Idempotency/versioning:** read-only; none.
- **Empty:** `money: []` → `EmptyState` "No contract stages yet" / "Stages appear here once the SOW is signed." (assumption copy), no table header, no total, no drill-down aside.

### E-REPORT GET `/api/v1/reports/{report_id}` (read; new consumer)
- **Request:** only when E-PROJECT-TAB returned `summary.report_id`; one read per tab load, after the money read; `report_id` URL-encoded. Without `report_id`, no request; every amount is plain text and the aside shows "No source recorded" for any `?figure=`.
- **200:** `title`, `agent`, `figures[]` (`id`, `label`, `value`, `sources`, `source_details[]`). Guard: `figures` is an array of objects with `label` and `value{currency, unknown}`; failing it is a report error (below).
- **Errors:** the table never disappears because the report failed (readiness rule 6). 401 → page-level `SignedOutState` as above. 403 or 404 → the aside (or sheet) shows "You can't see where these figures come from." with no sources, no figure label, no retry; amounts are plain text. 5xx, network or bad shape → the aside shows `ErrorState` "We couldn't load where these figures come from. Your work is safe; nothing was changed." with "Try again" (re-reads E-REPORT only); amounts are plain text until it succeeds.
- **Permission:** "Report read; figures limited to visible records" is the backend's. A figure the backend omits is not reconstructed from the row.

### Drill-down (reads join; nothing is derived)
- A row's amount is a link (`<Link href="/projects/<id>/money?figure=<figure_id>" replace scroll={false}>`) only when `figure_id` matches a `figures[].id` in the loaded report. No `figure_id`, no match, report loading, failed or refused: plain text.
- `?figure=<id>` selects a figure on load and on press. The panel:
  - **Title:** "Where <value> comes from", with `<value>` formatted from the **figure's own** `value` (not the row), and the figure `label` as visually hidden text (stages 2 and 3 share an amount). Figure value unknown: "Where this figure comes from", then "Amount: Unknown" (amber).
  - **Sources:** an `<ol>` of `source_details[]` in the order sent: `label`, then `reference` in mono. `work_id` → link to `/work/<work_id>`; `document_id` → text (no document route); `kind` `rule`/`record`/`evidence` without a link id → text. No guessed links, no added versions or dates.
  - No `source_details` but non-empty `sources[]`: each string as a text item. Neither: "No source recorded". An id with no matching figure (deep link): title "Where this figure comes from" and "No source recorded". Never an empty panel.
  - **Differ:** when the selected figure's row exists and `value` differs from the row's `amount` (compare `unknown`, `currency` and the `amount` string exactly, no number conversion), show `Callout kind="warning"` "These figures differ: the table shows <row amount>; the report shows <figure value>." Both values formatted as above; neither hidden.
  - **Chidi card:** Conflicts 10.
- **Desktop (≥720px, `useIsPhone()` false):** the aside sits beside the table (board layout), a labelled region (`aria-labelledby` its title); with no selection it shows the prompt of Conflicts 2. Pressing an amount keeps focus on the amount, marks it `aria-current="true"`, and a polite live region says "Showing where <value> comes from".
- **Phone:** stage cards (Conflicts 7 and 8); the hint "Tap an amount to see where it comes from" as plain text when at least one amount is linked; a selected figure opens `BottomSheet` (`title` = the panel title, `returnFocus` = the pressed amount); closing (button, Esc, scrim, swipe) replaces the URL without `figure` and returns focus. A deep link opens the sheet on load and closing focuses the matching amount.

### Screen states
| State | Shows |
|---|---|
| Loading (project or money) | shared `LoadingState` / `Loading` (no board, no fidelity target) |
| Report loading | table/cards drawn, amounts plain text, aside/sheet shows `Loading` "Loading sources…" |
| Empty | Contract, Empty |
| Error | money: error card; report: aside error, table kept |
| No access | money 403/404: `ProjectNoAccess`; report 403/404: aside line |
| Signed out | `SignedOutState` with `next` |
| Success | table/cards, as-of, aside/sheet per selection |

No animation is added; nothing pulses.

### Fixtures (new; existing fixtures byte-for-byte unchanged)
All 200 bodies validate against the generated E-PROJECT-TAB and E-REPORT schemas with no stripping (`additionalProperties: false`). Visibility metadata lives in a separate index file, not in the bodies.

| File | Case | Content |
|---|---|---|
| `mock/fixtures/projects/money/P-0101.json` | board | 4 rows: S1 "Stage 1 · kick-off" 3000000.00 NGN, invoice `{reference: INV-0398, work_id: W-1713, state: verified}`, `invoice_status` "Verified 03 Nov", paid `finance_tracks`, figure FIG-0101-S1; S2 "Stage 2 · UAT" 4250000.00, INV-0412/W-1001, "Awaiting Finance decision", paid `not_due`, FIG-0101-S2; S3 "Stage 3 · go-live" 4250000.00, INV-0419/W-1714, "Held · owner needed", paid `not_due`, FIG-0101-S3; S4 "Stage 4 · hypercare" `{currency: NGN, unknown: true}`, `amount_note` "Not yet due · amount set at go-live", no invoice, paid `not_due`, no `figure_id`. `summary.report_id` R-0101; `as_of` 2026-11-12T15:40:00Z |
| `mock/fixtures/reports/R-0101.json` | board | title "Lagoon Health · billing by contract stage", agent `chidi`; FIG-0101-S2 value 4250000.00 with the board's three sources (document SOW-0198 v2 with `document_id`, rule "RULE · stage terms", record HB-M2), S1 and S3 with their own sources |
| `money/P-0102.json` + `reports/R-0102.json` | edges | a row with no `figure_id`; a row whose `figure_id` has no figure; a figure with neither `source_details` nor `sources`; a figure with `sources[]` strings only; a figure whose value differs from its row; a figure with unknown value; a source with `work_id`; a row with `paid` absent; `part_paid` with owed known; `not_paid` with owed unknown; a USD row; a row with `amount.unknown: false` and no `amount` (reads Unknown) |
| `money/P-0103.json` | report fails | `report_id` R-0103; the mock answers E-REPORT 500 `{code: server_error, message}` |
| `money/P-0106.json` | report refused | `report_id` R-0106; E-REPORT 403 |
| `money/P-0105.json` | empty | `money: []`, `items: []`, no `report_id` |
| `money/P-0107.json`, `P-0108.json` | money refused | the mock answers 403 (P-0107) and 404 (P-0108) for the money tab while E-PROJECT is 200 |
| `mock/fixtures/reports/index.json` | — | `report_id` → `case_id` and scripted status, for visibility and the scripted errors |

Mock rules: money and report bodies are served only to personas whose `list.json` row includes the case (else 404, as E-PROJECT); P-0099 → 404; `X-Mock-Scenario`/`psl_mock_scenario` still win; a case with no money fixture and every non-money tab keep the exact current `501 not_mocked`. These are mock scripts, not access rules.

## Lanes
- **Frontend lane (builder)** owns:
  - New files: `frontend/src/features/projects/MoneyTab.tsx` (table, cards, aside/sheet), `moneyModel.ts` (types from `schema.d.ts`, guards, `PAID_WORDS`, amount text, figure join, differ check), `useMoney.ts` (E-PROJECT-TAB `money` then E-REPORT, sequence-guarded, separate retries), `money.css` (imported by `MoneyTab.tsx` only; tokens only).
  - Mock: new `frontend/mock/money.mjs` (E-PROJECT-TAB `tab === 'money'` and E-REPORT only), its fixtures under `frontend/mock/fixtures/projects/money/` and `frontend/mock/fixtures/reports/`, and the smallest dispatch change in `frontend/mock/server.mjs` (route those two cases to `money.mjs` after the persona/scenario block; everything else unchanged). `projects.mjs` may gain one exported visibility helper (additive).
  - Tests: new `frontend/tests/money.test.tsx`, `money-model.test.ts`, `mock-money.test.ts`, `frontend/e2e/money.spec.ts`; in `frontend/tests/mock-contract.test.ts:192` swap E-REPORT for another operation that still answers 501 (no assertion loosened).
  - Factory files: `delivery/features/F-26/fidelity-exceptions.json`, `round-<N>/fidelity/**`, `round-<N>/build.md`.
- **Backend lane:** none. Recorded in build.md, not blocking: E-PROJECT-TAB `money` and E-REPORT unimplemented; D-PROJECT-TAB-ROWS proposed; contract proposals G-SCR12-1 to G-SCR12-3, figure `as_of`, report title/eyebrow fields; the questions of Conflicts 5 and readiness proposal 4 (finance_tracks meaning, who may read Money, 403 vs 404).
- **Integration owner:** the coordinator (Shared files).
- **Read only:** `src/shell/**`, `src/components/**` (no new shared component), `src/api/**` including `schema.d.ts`, `features/work-item/**`, `features/my-work/**`, `features/projects/model.ts`, `projects.css`, `ProjectTabs.tsx`, `ProjectStates.tsx`, `useProject.ts`, `src/styles/**`, `package.json`, lock file, `playwright.config.ts`, `vitest.config.ts`, `architecture/**`, `design/**`, `apps/**`, and the protected `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json`.

## Shared files (F-25 builds in parallel)
- `frontend/src/features/projects/ProjectJourney.tsx`: F-26's only change is **one import** (`MoneyTab`) and **one branch** in `ProjectView`'s tab panel: `tab === 'money' ? <MoneyTab caseId={journey.case_id} base={base} /> : …` ahead of the existing fallback. No other line in the file changes (`ComingNext`, `JourneyTab`, `ProjectView`'s signature, imports order otherwise untouched). F-25 replaces `ComingNext` for the other four tabs; whichever merges second keeps both branches.
- `frontend/src/features/projects/model.ts`, `projects.css`, `ProjectTabs.tsx`: not touched (`PROJECT_TABS` keys and shape unchanged; `features/work-item/**` imports them).
- `frontend/mock/server.mjs`: one dispatch block for E-PROJECT-TAB (`money` only) and E-REPORT. F-25 adds its own tabs to the same operation; the second to merge keeps both and keeps non-handled tabs at 501.
- Tests asserting 501: `mock-projects.test.ts:209` is untouched by F-26 (milestones stays 501 here; F-25 changes it); `mock-contract.test.ts:192` changes here. The second to merge keeps both features' cases.
- Hook: F-26 writes its own `useMoney` and does not wait for a generic `useProjectTab`; a later cleanup may merge them.
- Merge rule (readiness): whichever is ready first merges; the second syncs from `dlv-00-delivery-setup`, resolves by keeping both, reruns `delivery/checks.sh` and both features' e2e at 390 and 1440.

## Ports and commands
- App 4780, mock 4781: `cd frontend && E2E_PORT=4780 MOCK_PORT=4781 npx playwright test e2e/money.spec.ts`, `timezoneId: 'Africa/Lagos'`. Score on a production build (`next build`, `next start -p 4780`, mock on 4781). 4782 to 4789 are free for this feature if a second server is needed. Check `df` first (stop under 3 GB) and delete `frontend/test-results` after.
- Review routing: technical (sonnet); security (opus: money visibility and the 403/404 leak checks); UI (opus, the fidelity gate on 2 boards); UX (sonnet); QA (opus). Product acceptance not required. High risk (money). One fidelity run per round (D-64).
- Size: about 900 to 1,300 lines including fixtures and tests. One PR.

## Acceptance criteria
Fidelity command (swap `--board`, `--page`, `--width`, `--out`):
```
node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs \
  --playwright <worktree>/frontend/node_modules/playwright/index.mjs \
  --board /Users/Hunchoo/psl-factory/design/canvas/project/SCR-12-desktop.dc.html \
  --page "http://localhost:4780/projects/P-0101/money?figure=FIG-0101-S2" --width 1440 \
  --cookies psl_mock_persona=finance_lead \
  --exceptions /Users/Hunchoo/psl-factory/delivery/features/F-26/fidelity-exceptions.json \
  --wait-ms 500 --out /Users/Hunchoo/psl-factory/delivery/features/F-26/round-<N>/fidelity/SCR-12-desktop-1440
```

### Fidelity (2 boards)
1. **Desktop board.** `SCR-12-desktop` at 1440 on `/projects/P-0101/money?figure=FIG-0101-S2`: `report.json` `pass: true`, `scores.coverageWithExceptions` = 100, `scores.visual` >= 90. — verify: the command, exit 0; `round-<N>/fidelity/scores.txt` lists board, width, coverage, visual, pass.
2. **Phone board.** `SCR-12-mobile` at 390 on `/projects/P-0101/money`, same thresholds. — verify: same command with `--width 390`; row in `scores.txt`.
3. **No D-83 waiver.** D-83 covers line screens only; a board under 90 needs a signed per-board waiver from the design engineer, not a builder note. — verify: `fidelity-exceptions.json` has no visual waiver unless signed.
4. **Exceptions are limited and explained.** Each entry has `role`, `name`, `category`, `reason`, `approved_by` (`"builder proposal, pending design engineer"` until confirmed) and maps to a Conflicts number; none covers a value the data can supply (an amount, a status, a source). — verify: file content; build.md maps each to a Conflicts number.
5. **One fidelity run per round** (D-64). — verify: build.md.

### Money rules
6. **Board rows from data.** `/projects/P-0101/money` (finance_lead) shows four stages in `position` order with "₦3,000,000.00", "₦4,250,000.00", "₦4,250,000.00", "Unknown"; "Verified 03 Nov", "Awaiting Finance decision", "Held · owner needed"; PAID "Finance tracks" then "—" three times; "Not yet due · amount set at go-live" under Stage 4's amount; "As of 12 Nov 16:40". — verify: `tests/money.test.tsx`; page at 1440 and 390.
7. **Unknown is not zero.** For every unknown amount, unknown owed and unknown figure value (P-0101 S4, P-0102 edges including `unknown: false` with no `amount`): the text is "Unknown" with the amber `psl-unknown` class; `document.body.textContent` of the Money panel contains no "₦0", "0.00" or "NaN" and the unknown cells are not "—" or empty. — verify: `tests/money.test.tsx`, `tests/money-model.test.ts`.
8. **No total, no computation.** No row, footer, heading or text on the tab shows a sum, total, balance, percentage, count of money or "outstanding"; P-0101 renders exactly four stage rows and no footer row. `moneyModel.ts`, `MoneyTab.tsx` and `useMoney.ts` contain no `parseFloat`, `Number(`, `+amount`, `reduce(` over amounts or arithmetic on amount strings. — verify: component test (row count, no `tfoot`); `grep -nE "parseFloat|Number\(|\.reduce\(" frontend/src/features/projects/{moneyModel.ts,MoneyTab.tsx,useMoney.ts}` returns nothing on amount values (any hit explained in build.md).
9. **Exact decimals.** `formatAmount` output is used for every amount: "4250000.00" → "₦4,250,000.00"; a USD row reads "1,200.00 USD"; a 19-digit amount renders every digit unchanged. — verify: `tests/money-model.test.ts`.
10. **Invoice and paid are separate (INV-FACTS).** P-0102: a row with `paid` absent reads "Unknown" in PAID whatever its INVOICE says; `part_paid` with owed reads "Part paid · ₦… owed"; `not_paid` with unknown owed reads "Not paid · owed Unknown"; `not_due` reads "—" with accessible text "Not due"; changing only `invoice_status` in a test body never changes the PAID cell. The words come from one `PAID_WORDS` constant. — verify: `tests/money.test.tsx`, `tests/money-model.test.ts`.
11. **Invoice cell.** "Verified 03 Nov" is a link to `/work/W-1713` whose accessible name includes "INV-0398"; a row with only `invoice.reference` shows the reference; a row with neither shows "—" with accessible text "No invoice". — verify: component test.

### Drill-down
12. **Deep link opens the figure.** `/projects/P-0101/money?figure=FIG-0101-S2` at 1440 shows the aside titled "Where ₦4,250,000.00 comes from" (accessible name includes the figure label) with three sources in order: "Signed SOW v2, stage table, row 2" with "SOW-0198 v2", "Stage terms v1, active since 30 Jun" with "RULE · stage terms", "Milestone 2 completion, recorded by Tunde Bello" with "HB-M2"; none of the three is a link. A reload keeps it. — verify: e2e and component test.
13. **Press to select.** Pressing Stage 3's amount replaces the URL with `?figure=FIG-0101-S3` (no new history entry), updates the aside to FIG-0101-S3's own sources, keeps focus on the pressed amount with `aria-current="true"`, and announces "Showing where ₦4,250,000.00 comes from". — verify: e2e at 1440.
14. **Title comes from the figure.** In P-0102 the differing figure's panel title uses the figure's value, not the row's, and the warning reads "These figures differ: the table shows <row>; the report shows <figure>." with both values. — verify: component test.
15. **No source, never empty.** P-0101 Stage 4 (no `figure_id`) shows "Unknown" as plain text, not a link. P-0102: an unmatched `figure_id` is plain text; `?figure=<unmatched id>` shows "Where this figure comes from" and "No source recorded"; a figure with no sources shows "No source recorded"; a figure with `sources[]` only lists those strings; a source with `work_id` links to `/work/<id>`; a `document_id` source is text. — verify: component tests.
16. **Phone sheet.** At 390, P-0101 shows four cards, the hint "Tap an amount to see where it comes from" as plain text, and "Paid · Finance tracks" on Stage 1 only; each linked amount is at least 44px tall; pressing Stage 2's amount opens a `BottomSheet` with the same title and sources; Esc and the close button close it, remove `figure` from the URL and return focus to that amount; `?figure=FIG-0101-S2` opens the sheet on load. — verify: e2e at 390.
17. **Chidi card.** With finance_lead, the card shows "Chidi · Finance agent", the agreed sentence (Conflicts 10) and "Ask me" linking to `/assistant?agent=chidi`; with a `/me` that lacks `assistant` (component test) the link is absent; with no `agent` in the report the card is absent. The link carries no figure or report id. — verify: component test.

### Errors and access
18. **Report failure keeps the table.** P-0103 (E-REPORT 500): the four rows show; amounts are plain text; the aside shows "We couldn't load where these figures come from. Your work is safe; nothing was changed." and "Try again", which makes exactly one more E-REPORT request and no E-PROJECT-TAB request. — verify: component test with a recording `fetch`; e2e.
19. **Report refused.** P-0106 (E-REPORT 403): rows show, amounts plain, the aside says "You can't see where these figures come from." and no figure label, source label or reference from the report body appears in the DOM. — verify: component test.
20. **Money refused or hidden.** P-0107 (403) and P-0108 (404) show `ProjectNoAccess` in the tab panel; no stage name, amount, report title or server `message` appears in `document.body.textContent`; no E-REPORT request is made. — verify: component test with a recording `fetch`; e2e.
21. **Wrong user, wrong tenant.** Persona `pm` opening `/projects/P-0104/money` (a project not in pm's rows) gets 404 from E-PROJECT and shows `ProjectNoAccess` with no stage or amount in the DOM and no E-REPORT request; `/projects/P-0099/money` the same. A 401 on the money read shows the signed-out callout with `next` `/projects/<id>/money`. — verify: e2e with cookie `psl_mock_persona=pm`; component test for 401.
22. **Money read failure.** A 500 or network failure on E-PROJECT-TAB shows "We couldn't load this project's money. Your work is safe; nothing was changed." with "Try again"; a body without `money` or with a malformed row shows the same card and no partial table. — verify: component tests.
23. **Empty.** P-0105 shows "No contract stages yet" and no table, total or aside. — verify: component test.
24. **No role logic.** `MoneyTab.tsx`, `moneyModel.ts` and `useMoney.ts` read nothing from `/me` except the `assistant` destination for the Chidi link; the same fixture renders the same rows for finance_lead and pm. — verify: `grep -n "useMe\|roles" frontend/src/features/projects/{MoneyTab.tsx,moneyModel.ts,useMoney.ts}`; component test with two personas.

### Mock and contract
25. **Mock matches the contract.** `tests/mock-money.test.ts`: every money and report 200 body validates against the generated schema with no stripping; P-0107 403, P-0108 404, P-0099 404, pm on P-0104 404, R-0103 500, R-0106 403; `GET /api/v1/projects/P-0101/milestones` (and the other non-money tabs) still answers exactly `501 {code: not_mocked, message: "Not available in the mock yet."}`; `X-Mock-Scenario: 403` still wins. — verify: the test.
26. **Contract not extended.** `git diff --stat` shows no change in `frontend/src/api/**`, `apps/**`, `architecture/**`, `design/**`, `src/components/**`; every wanted field is a contract proposal in build.md (G-SCR12-1, G-SCR12-2, G-SCR12-3, figure `as_of`, report title/eyebrow) with the backend questions of Conflicts 5. — verify: `git diff --stat`; build.md.
27. **Shared-file footprint.** `git diff` of `frontend/src/features/projects/ProjectJourney.tsx` is one import line and one branch; `model.ts`, `projects.css`, `ProjectTabs.tsx`, `ProjectStates.tsx`, `useProject.ts` are unchanged; existing fixtures are byte-for-byte unchanged. — verify: `git diff --stat` and `git diff frontend/src/features/projects/ProjectJourney.tsx`.

### Quality
28. **Accessibility and layout.** For P-0101 (with and without `?figure`), P-0102, P-0103 and P-0105 at 1440 and 390: no axe violations (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`), no sideways page scroll at 390 (the desktop table may scroll inside its own box as drawn), visible focus rings, the table has a caption or accessible name, column headers are `th` with `scope`, 44px standalone targets on phones (D-92c, D-95). — verify: `e2e/money.spec.ts`.
29. **Tokens only.** `grep -nE "#[0-9a-fA-F]{3,8}\b|rgba?\(|hsl\(" frontend/src/features/projects/money.css` returns nothing. — verify: the command.
30. **New tests run; nothing weakened.** `money.test.tsx`, `money-model.test.ts` and `mock-money.test.ts` run under `npm test` in `delivery/checks.sh`, covering criteria 6 to 25; `e2e/money.spec.ts` runs with the ports above and its output is in build.md. `tests/projects*.test.tsx`, `mock-projects.test.ts`, `mock-contract.test.ts`, `e2e/projects*.spec.ts` and `shell.test.tsx` pass with no assertion removed or loosened (the one E-REPORT 501 case is swapped, not deleted). — verify: `delivery/checks.sh`; `git diff` on those files.
31. **No overclaim.** Every e2e request goes to the mock (4781). The PR description and build.md state the limits: contract mock only, D-PROJECT-TAB-ROWS is a proposal, the backend developer may change or refuse any field, nothing released; they do not claim real money data, real access rules or a working backend. — verify: build.md; recorded requests.
32. **build.md evidence.** Lists the `design.py check` result, commands and results, both scores, every exception with its Conflicts number, every contract proposal and backend question, and the shared-file diff. — verify: file content.

## Out of scope
- The Milestones, Documents, Registers and Actions tabs, their mock handlers and tab counts (F-25); a generic `useProjectTab`.
- Any total, subtotal, sum, balance, percentage, "outstanding", ageing, colour-by-threshold or chart, even when no stage is Unknown (G-SCR12-4).
- Any write or Finance action: raising, verifying or sending invoices, recording receipts or allocations, payment exceptions, approvals. The page offers none.
- Inferring paid from invoice, invoice from milestone, or any status from text.
- The eyebrow, a composed page title, a figure-context assistant conversation (G-SCR12-2), document links (no route), structured source versions (G-SCR12-1).
- FE-LEADERSHIP-REPORT (SCR-52) and report-based work items; a standalone `/reports/<id>` page.
- Backend, OpenAPI, `schema.d.ts`, `architecture/**`, `design/**`, `src/components/**` (no new shared component), `src/shell/**`, new npm dependencies.
- SampleLabel: neither response has a `sample` field, so none is shown.

## Assumptions
- Nothing is selected on load (Conflicts 2). Reason: no field names a default figure; picking one is a guess.
- `?figure` changes use `replace`, not `push`. Reason: the selection is a view of the same page; Back leaves the tab, matching the tab links.
- Rows render in ascending `position`. Reason: `position` is the contract's order field; readiness says the order is `position`.
- `not_due` reads "—", absent `paid` reads "Unknown", absent invoice reads "—" (Conflicts 5). Reason: it keeps the board's dashes only where the contract states a value; backend asked to confirm.
- Non-NGN amounts read "<digits> <code>". Reason: `formatAmount` only knows ₦; showing the code as sent invents no symbol.
- A body without `money` is an error, not a fallback to untyped `items`. Reason: reading untyped rows would mean guessing their shape on a money screen.
- E-REPORT 403/404 shows a short no-access line in the aside and keeps the table; E-PROJECT-TAB 403/404 shows `ProjectNoAccess` (Conflicts 14). Reason: readiness rule 6 asks for both "no access names nothing" and "the table does not disappear because the explanation failed"; the money read authorised the table, the report read only the sources. The approver may escalate.
- `MoneyTab` takes `journey.case_id`, not the route id. Reason: it keeps the `ProjectView` signature (and the shared file) unchanged; the backend returns the requested case.
- New neutral copy: "Choose an amount to see where it comes from.", "No contract stages yet" / "Stages appear here once the SOW is signed.", "Loading sources…", "You can't see where these figures come from.", the two error sentences, "These figures differ: …", "Ask me about any figure here." Reason: sources are silent; none is a business rule; the design engineer may reword.
- Mock scripts (P-0107 403, P-0108 404, R-0103 500, R-0106 403, persona rows) are test cases, not access rules. Reason: who may read Money is the backend's (readiness proposal 4).
- Ports 4780 (app) and 4781 (mock). Reason: the coordinator assigned 4780 to 4789; no other spec uses 478x.
