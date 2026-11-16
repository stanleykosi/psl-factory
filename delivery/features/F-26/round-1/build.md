STATUS: READY
COMMIT: 14c685cf577c6e9396a2a9c6ace316cc0998b697
BUILDER: builder
LANE: full

## Summary
- `/projects/<case_id>/money` now shows each contract stage's amount, invoice and paid state exactly as E-PROJECT-TAB sends them: a STAGE / AMOUNT / INVOICE / PAID table at 1440 and one card per stage on phones, with "As of 12 Nov 16:40". Nothing is totalled, rounded or inferred. Unknown is the amber Unknown, never 0 or a dash.
- Pressing an amount (or opening `?figure=<id>`) shows "Where ₦X comes from" with that figure's own sources from E-REPORT. It opens in the aside on desktop and in the shared BottomSheet on phones. It handles "No source recorded", "These figures differ", a report that fails (the table stays, with its own Try again) and a report that is refused.
- Contract mock only: `mock/money.mjs` answers E-PROJECT-TAB (money tab only) and E-REPORT from new fixtures. The other tabs still answer exactly 501. Nothing reaches a backend, nothing is released, and the backend developer may change or refuse any field (D-PROJECT-TAB-ROWS is still a proposal).
- Fidelity coverage is 100% on both boards after the D-104 exceptions. Visual is under 90 on both (desktop 85.7, phone 71.4). That is an **open design-engineer decision**: a signed per-board waiver is needed (see Blocked/open below; there is no D-83 waiver here).

## Changes
- `frontend/src/features/projects/MoneyTab.tsx` (new): the table and cards, amount, invoice and paid cells, the drill-down (aside and BottomSheet), the Chidi card, and the loading, empty, error, no-access and signed-out states. `?figure` comes from `useSearchParams`, inside a Suspense boundary.
- `frontend/src/features/projects/moneyModel.ts` (new): types from `schema.d.ts`, the money and report guards, `amountText` (string formatting only, via `formatAmount`), `PAID_WORDS`/`paidWords`, `invoiceText`, `figureOf`, `valuesDiffer` (an exact comparison of the sent fields) and `figureTitle`.
- `frontend/src/features/projects/useMoney.ts` (new): one E-PROJECT-TAB money read, then one E-REPORT read when `summary.report_id` is sent. Each read is sequence-guarded and has its own retry. There is no polling.
- `frontend/src/features/projects/money.css` (new, tokens only): the board layout (report title inline before the board's sentence, the board's column widths, normal line height, Unknown drawn as amber text as the boards draw it). Phone links are 44px tall: padding grows the tap area and a matching negative margin keeps the card spacing. Targets do not overlap.
- `frontend/src/features/projects/ProjectJourney.tsx`: one import and one branch (`tab === 'money' ? <MoneyTab …/> :`). Nothing else changed.
- `frontend/mock/money.mjs` (new): money-tab and report handler. It runs its own persona and scenario check (scenario wins where declared), persona visibility through `caseVisible`, scripted statuses from `money/index.json` and `reports/index.json`, and 501 for a case with no money fixture.
- `frontend/mock/server.mjs`: one import and one dispatch line placed just before the `M1_OPERATIONS` 501 check. It is not after the persona/scenario block, because non-M-1 operations never reach that block; the handler applies the same scenario rule itself, as `workspace.mjs` does.
- `frontend/mock/projects.mjs`: added an exported `caseVisible(caseId, persona)` helper. `journey()` is unchanged.
- Fixtures (new): `mock/fixtures/projects/money/P-0101, P-0102, P-0103, P-0105, P-0106, P-0107, P-0108.json` and `index.json`; `mock/fixtures/reports/R-0101, R-0102, R-0106.json` and `index.json`. Existing fixtures are byte-for-byte unchanged.
- Tests: new `tests/money.test.tsx` (32), `tests/money-model.test.ts` (11), `tests/mock-money.test.ts`, `e2e/money.spec.ts` (12).
- `tests/mock-contract.test.ts:192`: the 501 case now uses E-PAYROLL-MATCH instead of E-REPORT. The assertion is the same.
- `tests/projects-journey.test.tsx`: the coming-next case for `money` (which now renders the Money tab) became `documents` / "Documents come next" / index 2. The assertion is the same; only the tab under test changed. Whichever of F-25 and F-26 merges second keeps both.
- Main folder: `delivery/features/F-26/fidelity-exceptions.json`, `round-1/fidelity/` (run.sh, scores.txt, both reports).

## Fixes
None (round 1).

## Acceptance criteria
1. [ ] Desktop board: `SCR-12-desktop` at 1440 on `?figure=FIG-0101-S2` gives coverage 87.8, 100 after exceptions, **visual 85.7 < 90**, `pass: false`. Open design-engineer decision (below).
2. [ ] Phone board: `SCR-12-mobile` at 390 gives coverage 63.6, 100 after exceptions, **visual 71.4 < 90**, `pass: false`. Open design-engineer decision (below).
3. [x] No D-83 waiver: `fidelity-exceptions.json` has no visual waiver. The two gaps are named here for a signed per-board waiver.
4. [x] Exceptions are limited and explained. There are 11 entries, all `approved_by: "design engineer, 16 Nov 2026 — D-104"`, each with role, name, category and reason. None covers a value the data cannot supply:
   - Conflicts 1: "REPORT · LAGOON HEALTH · PROJECT MONEY" (eyebrow not built)
   - Conflicts 3: "Where ₦4,250,000 comes from" (two decimals)
   - Conflicts 4: "Not yet due · amount set at go-live" (under the amount)
   - Conflicts 5: "—" (PAID not_due reads "—" plus hidden "Not due")
   - Conflicts 15: "← Project" (frame back link "← Projects")
   - Conflicts 7 and 8: the four stage names and "Unknown" on phones. The words are on the page inside the card list, which the tool reads as one pattern.
   - Conflicts 8: "Tap an amount to see where it comes from" is plain text, not a link.
5. [x] One recorded fidelity run (`round-1/fidelity/run.sh` on the pushed head). While building, discovery runs went to the scratchpad only (an empty exceptions file, to list the gaps and measure layout changes). None of them is the scored run.
6. [x] Board rows from data: `money.test.tsx` "four stages in position order…" checks exact cells, the note under Stage 4's amount and "As of 12 Nov 16:40". The e2e checks the same at 1440 and 390.
7. [x] Unknown is not zero: Stage 4 and every P-0102 unknown case (`unknown:false` with no amount, unknown owed, unknown figure value) render the `psl-unknown` "Unknown". The panel text is checked against `₦0`, a lone `0.00` and `NaN` (component and e2e). In `money-model.test.ts`, unknown or unreadable values give no text.
8. [x] No total or computation: exactly 4 rows, no `tfoot`, no total/sum/balance/outstanding/%. `grep -nE "parseFloat|Number\(|\.reduce\(" moneyModel.ts MoneyTab.tsx useMoney.ts` returns nothing. The only arithmetic is the sort on the integer `position`.
9. [x] Exact decimals: "₦4,250,000.00", "1,200.00 USD", and a 19-digit amount reads "₦9,223,372,036,854,775,807.00" (model test, and P-0102 Stage 7 in the component test).
10. [x] Invoice and paid are separate (P-0102):
    - Paid absent reads Unknown.
    - "Part paid · ₦1,250,000.00 owed" and "Not paid · owed Unknown".
    - `not_due` shows "—" with hidden "Not due".
    - Changing only `invoice_status` leaves PAID unchanged.
    - A status outside the enum shows its raw value.
    - All paid words come from one `PAID_WORDS`.
11. [x] Invoice cell: "Verified 03 Nov" links to `/work/W-1713` with ", INV-0398" hidden. A reference alone ("INV-0503") is text. Neither present shows "—" with hidden "No invoice".
12. [x] Deep link: the aside is named "Where ₦4,250,000.00 comes from, Stage 2 · UAT amount". It lists the three board sources in order with their references, and none is a link. A reload keeps it (e2e 1440 and 390).
13. [x] Press: Stage 3 replaces the URL with `?figure=FIG-0101-S3` (`history.length` unchanged) and shows FIG-0101-S3's own sources. Focus and `aria-current="true"` stay on the pressed amount, and the live region says "Showing where ₦4,250,000.00 comes from" (e2e 1440). A keyboard focus ring is checked (`outline-style` is not none).
14. [x] The title comes from the figure: P-0102 FIG-0102-S1 shows "Where ₦2,400,000.00 comes from" and "These figures differ: the table shows ₦2,500,000.00; the report shows ₦2,400,000.00." (component and e2e).
15. [x] No source, never empty: Stage 4 is plain Unknown. An unmatched `figure_id` is plain text. `?figure=` with an unmatched id, and a figure with `sources: []`, both show "Where this figure comes from"/"No source recorded". A `sources[]`-only figure lists the strings. A `work_id` source links to `/work/W-1713`, and a `document_id` source is text.
16. [x] Phone sheet:
    - Four cards. The hint is a `<p>`.
    - "Paid · Finance tracks" appears on Stage 1 only.
    - Linked amounts and invoice links are at least 44×44 (boundingBox).
    - Pressing Stage 2 opens the dialog with the same title and sources.
    - Esc and Close remove `figure` and return focus to the amount.
    - The deep link opens the sheet on load.
    - Checked in the e2e at 390 and the component test.
17. [x] Chidi: the card reads "Chidi · Finance agent" and "Ask me about any figure here.", with "Ask me" linking to `/assistant?agent=chidi` (no figure or report id). If `/me` has no `assistant`, there is no link; if the report has no `agent`, there is no card.
18. [x] Report 500 (P-0103): the four rows stay and amounts are plain. The aside shows the agreed sentence, and Try again makes exactly one more `/api/v1/reports/R-0103` request and no money read (component test with recording fetch, and e2e).
19. [x] Report 403 (P-0106): rows show and amounts are plain. The aside says "You can’t see where these figures come from." None of the report body's title, labels or references, and not the server message, is in the DOM.
20. [x] Money 403/404 (P-0107/P-0108): `ProjectNoAccess` shows in the panel. No stage, amount, ₦, report title or server message appears, and no E-REPORT request is made (component and e2e).
21. [x] pm on P-0104 and P-0099: E-PROJECT returns 404, so no money or report request is made and no ₦ shows (component and e2e with `psl_mock_persona=pm`). A 401 on the money read, or on the report read, gives Sign in with `next=/projects/P-0101/money`.
22. [x] A money read failure (500, network, no `money`, a malformed row) shows the error card and Try again, with no partial table and no report read. Try again re-reads money (then the report).
23. [x] Empty (P-0105): "No contract stages yet" / "Stages appear here once the SOW is signed.", with no table and no aside.
24. [x] No role logic: the grep finds only `useMe` in MoneyTab.tsx, used for the `assistant` destination in the Chidi card. finance_lead and pm see identical rows (component test).
25. [x] Mock matches the contract (`mock-money.test.ts`):
    - Every money and report fixture validates in full.
    - P-0107 → 403. P-0108, P-0099, pm on P-0104, pm on P-0107, `none` on R-0101 and an unknown report → 404. R-0103 → 500. R-0106 → 403.
    - milestones, documents, registers and actions on P-0101, and P-0109 money, return exactly `501 not_mocked`.
    - The scenario header and cookie still win.
26. [x] Contract not extended: `git diff --stat 7ec99296..HEAD` shows no change in `src/api/**`, `src/components/**`, `src/shell/**`, `apps/**`, `architecture/**` or `design/**`. Proposals are listed below.
27. [x] Shared-file footprint: `ProjectJourney.tsx` diff is one import and one branch (below). `model.ts`, `projects.css`, `ProjectTabs.tsx`, `ProjectStates.tsx` and `useProject.ts` are unchanged, and existing fixtures are unchanged.
28. [x] Accessibility and layout: axe (wcag2a/aa, 21a/aa, 22aa) passes with no violations and there is no sideways scroll at 1440 and 390 for:
    - P-0101 with and without `?figure`
    - P-0102 with and without `?figure`
    - P-0103 and P-0105
    - the sheet, and the no-access states
    The table has a caption and an aria-labelled region, and the column headers are `th scope="col"`. Phone targets are 44px.
29. [x] Tokens only: the hex/rgb/hsl grep on `money.css` returns nothing.
30. [x] The new unit tests run under `npm test` in checks.sh. The e2e output is below. Existing tests pass; two cases were swapped, not loosened (listed above).
31. [x] No overclaim: the e2e asserts every API request goes to the app origin, which proxies to the mock on 4781. Limits are stated in the summary.
32. [x] This file records the evidence.

## Validation
- Base merge: the coordinator merged dlv-00 into the branch at 14c685cf (delivery records only); `git diff --stat 5742605e 14c685cf -- frontend` is empty, so every result below, measured at 5742605e, holds for this head.
- `python3 …/design/design.py check --project .` gives `status: EXCEPTION`, `passes: true` (D-89 frame change only).
- `bash /Users/Hunchoo/psl-factory/delivery/checks.sh` (worktree) exits 0: Django check, npm ci, lint, typecheck, vitest **86 files, 1873 tests passed**, and next build.
- `E2E_PORT=4780 MOCK_PORT=4781 npx playwright test e2e/money.spec.ts e2e/projects.spec.ts` gives **40 passed** (12 money and 28 projects, at 1440 and 390, Africa/Lagos).
- Recorded fidelity run (`round-1/fidelity/run.sh`, production build `next start -p 4780`, mock 4781, persona finance_lead):

  | Board | Width | Coverage | With exceptions | Visual | Pass |
  |---|---|---|---|---|---|
  | SCR-12-desktop | 1440 | 87.8 | 100 | 85.7 | False |
  | SCR-12-mobile | 390 | 63.6 | 100 | 71.4 | False |

- Housekeeping: servers were stopped by PID (4780/4781 are free), `frontend/test-results` was deleted, and disk was 5.6 GB free at the end.

Shared-file diff (`ProjectJourney.tsx`):
```
+import { MoneyTab } from './MoneyTab';
-        {tab === 'journey' ? <JourneyTab journey={journey} /> : <ComingNext tab={tab} base={base} />}
+        {tab === 'journey' ? <JourneyTab journey={journey} /> : tab === 'money' ? <MoneyTab caseId={journey.case_id} base={base} /> : <ComingNext tab={tab} base={base} />}
```
`server.mjs`: `+import { isMoneyRequest, moneyRoute } from './money.mjs';` plus one comment and one dispatch line before the 501 check. F-25 extends the same operation: keep both, and keep unhandled tabs at 501.

Contract proposals and backend questions (non-blocking, nothing extended locally):
- E-PROJECT-TAB `money` and E-REPORT are unimplemented (mock only). D-PROJECT-TAB-ROWS is still proposed.
- G-SCR12-1: structured source versions (document `version`, rule `component`/`rule_version`, record `case_id`).
- G-SCR12-2: E-CONVERSATION-NEW `context:{kind:'report_figure', report_id, figure_id}`. Until then "Ask me" is a plain link.
- G-SCR12-3: state in the contract that a row without `figure_id` has no drill-down ("No source recorded").
- Figure `as_of` on E-REPORT, if a cached report can drift from the money row.
- An optional report title and eyebrow on E-PROJECT/E-REPORT.
- Conflicts 5: confirm that an absent `invoice` means "no invoice yet", and that an unknown paid state is always sent as `paid.status: unknown`, never by omission.
- Readiness 4: does `finance_tracks` mean "tracked by Finance, not shown to this person"? Who may read Money? Should PMO get 403 or 404?

Notes for reviewers:
- In Chromium, a visually hidden span adds a space to accessible names: "Verified 03 Nov , INV-0398" and "Where ₦4,250,000.00 comes from , Stage 2 · UAT amount". The e2e matches these with an optional space.
- The amber Unknown keeps the `psl-unknown` class. In the table and cards it is drawn as plain amber semibold text, as both boards draw it.
- With nothing chosen, the aside head is "Choose an amount to see where it comes from.". When no report is loaded it is "Where these figures come from" (new neutral copy).

## Blocked
Not blocked. Open design-engineer decision: both SCR-12 boards are under visual 90 at 100% coverage after exceptions, and each needs a signed per-board waiver (there is no D-83 for this screen).
- **Desktop, 85.7.** The approved D-104 choices cause the remaining gap:
  - The project title stays the h1 instead of "…billing by contract stage", about 110 cells.
  - Stage 4's note sits under the amount, so that row is taller and the table's bottom edge moves.
  - The report title is added before the board's sentence.
  - The shared frame header sits about 6px lower than the board.
- **Phone, 71.4.**
  - The approved report-title line and the approved Stage 1 Paid line push every card down by about 50px, roughly half a card, which the square-by-square score punishes. By eye, the cards match the board's spacing (`round-1/fidelity/SCR-12-mobile-390/side-by-side.png`).
  - The two-decimal amounts also differ from the board.

Unblock: the design engineer signs both waivers or chooses a different layout.
