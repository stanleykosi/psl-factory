VERDICT: PASS
COMMIT: ac401c09e80d4398acb8101994d6f18b4b0f1d76
REVIEWER: qa
AUTHORITY: delivery integrated QA

## Summary
- I tested the production build of head ac401c09 (`next start -p 4787`, built with `API_ORIGIN=http://127.0.0.1:4786`) against the contract mock (`node mock/server.mjs`, port 4786). Both ran from the worktree. I drove the pages in a scripted Chromium session (timezone Africa/Lagos) at 1440 and 390, as finance_lead and as pm. **129 of 129 journey checks pass.** The script is `scratchpad/f26-qa/qa.mjs` and its output is `qa.out`.
- Every acceptance journey in the brief passes. That covers the board rows, Unknown, two decimals, no totals and "As of". It covers the aside on desktop and the bottom sheet on phones, including an Unknown amount that has a figure, plus "These figures differ" and "No source recorded". It covers a malformed report (the table stays) and a malformed row (the error card shows). It covers report 500 and 403, money 403 and 404, pm on P-0104, P-0099, and money 500, network failure and 401. Every browser request went to the app origin, which forwards `/api/v1` to the mock. Nothing else was contacted.
- E2E: `E2E_PORT=4787 MOCK_PORT=4786 npx playwright test e2e/money.spec.ts e2e/projects.spec.ts` gave **40 passed** (2.3m; 12 money and 28 projects).
- `bash delivery/checks.sh` did **not** exit 0 in my runs, because the machine was overloaded (load average 111 to 585; F-25, F-26 and F-27 vitest suites ran at once).
  - Run 1: 20 files failed, 5 tests failed, 1287 passed, 590 skipped (of 1882).
  - Run 2: 13 files failed, 21 tests failed, 1439 passed, 422 skipped.
  - Every failure was a 10 s hook timeout or a `waitFor` that timed out on "Loading…", in files outside F-26. Re-run with default timeouts, all 13 run-2 files pass: **13 files, 787 tests passed**.
  - The F-26 set (money, money-model, mock-money, mock-contract, mock-projects, all projects*.test.tsx, shell) gives **8 files, 450 tests passed**.
  - Django check: no issues. Lint and typecheck: clean. `next build`: exit 0.
  - See QA-2-1.
- **Not proved:** a real backend. E-PROJECT-TAB `money` and E-REPORT exist only in the contract mock, so access, tenant scoping and the figures are mock scripts, not real rules.
  - The malformed-body, money 500, network and 401 cases came from browser-side route interception, because the mock has no scenario for them. The real app parsed each one.
  - The Unknown-amount-with-figure case also used interception: Stage 4 of P-0102 was given `figure_id` FIG-0102-S1, and Stage 1's `figure_id` was removed. The real R-0102 report was served unchanged.

## Journeys
Each line below is one or more checks from `qa.mjs`, with the evidence it recorded.

- **Board rows, P-0101** | pass | finance_lead and pm, at 1440 and 390.
  - The four stages appear in position order with ₦3,000,000.00, ₦4,250,000.00, ₦4,250,000.00 and Unknown (amber `psl-unknown`).
  - Invoice cells: "Verified 03 Nov" (link `/work/W-1713`, accessible name includes INV-0398), "Awaiting Finance decision", "Held · owner needed".
  - PAID column: "Finance tracks", then "—" (hidden "Not due") three times. Stage 4 shows "Not yet due · amount set at go-live" under its amount. "As of 12 Nov 16:40" appears.
  - Desktop has 4 `tbody tr` and no `tfoot`. Stage 4's Unknown is not a link. pm sees the same rows as finance_lead.
- **Two decimals** | pass | Every ₦ string on P-0101 and P-0102 at both widths ends in `.dd`. P-0102 shows "1,200.00 USD" and "₦9,223,372,036,854,775,807.00" (19 digits, unchanged).
- **No totals** | pass | The panel text at both widths, for both personas, on P-0101 and P-0102, has no total, sum, subtotal, balance, outstanding or %. It has no "₦0", stand-alone "0.00" or "NaN". `grep -nE "parseFloat|Number\(|\.reduce\("` over moneyModel.ts, MoneyTab.tsx and useMoney.ts finds nothing.
- **Desktop aside** | pass |
  - `?figure=FIG-0101-S2` shows "Where ₦4,250,000.00 comes from". The accessible name includes "Stage 2". There are three sources in order (SOW-0198 v2, RULE · stage terms, HB-M2) and none is a link. A reload keeps the figure.
  - Pressing Stage 3 replaces the URL with `?figure=FIG-0101-S3` (history length unchanged) and shows Stage 3's own sources. Focus stays on the amount with `aria-current="true"`, and the live region says "Showing where ₦4,250,000.00 comes from".
  - Pressing Stage 1 shows "Where ₦3,000,000.00 comes from".
  - With no figure selected, the aside shows "Choose an amount to see where it comes from." and the Chidi card ("Ask me" goes to `/assistant?agent=chidi`).
- **Phone sheet** | pass |
  - 4 cards. "Paid · Finance tracks" appears on Stage 1 only. "Tap an amount to see where it comes from" is plain text. The three amount links are at least 44px tall, and the page does not scroll sideways (scrollWidth 390 or less).
  - Pressing Stage 2 opens the dialog with the same title and three sources.
  - Esc and Close each close it, remove `figure` from the URL and return focus to the amount.
  - A deep link opens the sheet on load, and closing it focuses the matching amount.
- **Unknown amount with a figure** | pass | At 1440 and 390, the Unknown (amber) is a link. Pressing it shows "Where ₦2,400,000.00 comes from" with its sources, and "These figures differ: the table shows Unknown; the report shows ₦2,400,000.00."
- **These figures differ** | pass | P-0102 `?figure=FIG-0102-S1` at both widths: the title comes from the figure ("Where ₦2,400,000.00 comes from"), with "These figures differ: the table shows ₦2,500,000.00; the report shows ₦2,400,000.00." For FIG-0102-S6 the panel shows "Where this figure comes from", "Amount: Unknown" and "…the table shows ₦500,000.00; the report shows Unknown".
- **No source recorded** | pass |
  - FIG-0102-S5 (empty `sources`) and the unmatched deep link FIG-0102-S2 both show "No source recorded". The unmatched one is titled "Where this figure comes from". Stage 2's amount (figure id with no matching figure) is plain text.
  - FIG-0102-S3 lists its `sources[]` strings.
  - The `work_id` source links to `/work/W-1713`. The `document_id` source is text.
- **Paid and invoice are separate** | pass | P-0102: Stage 2 has no `paid` and reads PAID "Unknown", while its invoice reads "Awaiting Finance decision". Other rows show "Part paid · ₦1,250,000.00 owed", "Not paid · owed Unknown", and the reference-only invoice "INV-0503".
- **Malformed report** | pass | With `sources` removed from figures[0] of R-0101, at 1440 and 390, the four rows stay and every amount is plain text. The page shows "We couldn’t load where these figures come from." with Try again.
- **Malformed row** | pass | Stage 2's amount sent as the number 4250000 at both widths: the card shows "We couldn’t load this project’s money.", with no table or cards, no stage text and no E-REPORT request. A body without `money` shows the same card.
- **Report 500 (P-0103)** | pass | At 1440 and 390, the 4 rows show with plain amounts. The page shows "We couldn’t load where these figures come from. Your work is safe; nothing was changed." with Try again visible. One press makes exactly one more E-REPORT request and no E-PROJECT-TAB request.
- **Report 403 (P-0106)** | pass | At 1440 and 390, with and without `?figure`: the rows show, amounts are plain, and the page says "You can’t see where these figures come from." There is no Try again (the spec gives a refusal no retry), and no words from the R-0106 body appear ("Ojo secret", "SOW-OJO", the report title).
- **Money 403/404** | pass | P-0107 (mock 403) and P-0108 (mock 404) as finance_lead, at 1440 and 390: the page shows "You can’t see this project’s money.". The body text has no stage name ("Atlas claims build"), no ₦, no 7,100,000, no report title and no server message. There are 0 E-REPORT requests. The project title from E-PROJECT (200) stays in the header, as designed.
- **Wrong user and P-0099** | pass | pm on P-0104, pm on P-0099 and finance_lead on P-0099, at 1440 and 390: E-PROJECT returns 404 and the page shows "You can’t open this project" (ProjectNoAccess). The page makes no money request and no E-REPORT request, and shows no ₦ or stage text. Reading the money endpoint directly also returns 404.
- **Money 500, network failure, 401, empty** | pass |
  - A 500 shows the money error card with Try again, and the server message ("boom-secret") is hidden. Try again then loads the table.
  - A network abort shows the same card.
  - A 401 shows the signed-out callout, linking with `next=/projects/P-0101/money`.
  - P-0105 shows "No contract stages yet", with no table, aside, cards or E-REPORT request.
- **Endpoint statuses (direct)** | pass | P-0101/money 200, R-0101 200, R-0103 500, R-0106 403, P-0107/money 403, P-0108/money 404, P-0099/money 404, P-0101/milestones 501, pm P-0104/money 404.
- **Requests go only to the mock** | pass | All browser requests went to `http://localhost:4787`.
  - `/api/v1` is rewritten to `API_ORIGIN`. The rewrite is fixed at build time: my first build without `API_ORIGIN` proxied to the default 127.0.0.1:4010 and failed with ECONNREFUSED, which confirms no other backend is wired in. I rebuilt with `API_ORIGIN=http://127.0.0.1:4786`.
  - The e2e config passes the same variable to its own build.

## Totals
- `qa.mjs`: 129 checks, 129 pass, 0 fail. The first run had 5 failures, all from my script:
  - one 400 ms wait too short for "Loading sources…" under load;
  - two from a route edit that gave two rows the same figure;
  - two from a leak pattern that matched the allowed project title "Atlas Insurance".
  I fixed the script, not the app, and the re-run is clean.
- E2E money + projects: 40 passed.
- checks.sh: exit 1 on both runs under load (run 1: 20 of 86 files and 5 tests failed, 590 skipped; run 2: 13 files and 21 tests failed, 1439 passed, 422 skipped). Re-run of the 13 failed files: 787 of 787 passed. F-26 set: 450 of 450 passed. Lint, typecheck, Django check and build: clean.

## Findings
- QA-2-1 | non-blocking | low | pmo | `delivery/checks.sh` (gate) | I could not reproduce a whole-suite exit 0. Two full runs failed only on timeouts (10 s hook timeouts in the `*-mock` suites; `waitFor` on "Loading…") in files F-26 does not touch, at load averages of 111 to 585 with three features' vitest runs at once. Each failed file passes when re-run, and the builder's run at this head was exit 0 (86 files, 1882 tests). | Fix: run the gate on ac401c09 once the other builds are idle, to confirm exit 0 before merge. No code change.
- QA-2-2 | non-blocking | low | frontend | `MoneyTab.tsx:343-349` | Confirms TECH-2-2. On a phone, P-0103 `?figure=FIG-0101-S1` shows 2 "Try again" buttons: one under the cards and one in the open sheet. Both re-read only E-REPORT. | Fix: as TECH-2-2 (render the inline error only when no sheet is open), or accept.

## Verified
Each round-2 fix that QA can test end to end, retested in the browser on head ac401c09.
- TECH-1-1 | verified | A malformed report (figure without `sources`) keeps the 4 rows and shows the report error with Try again at 1440 and 390. A malformed row (numeric amount) and a body without `money` show the money error card with no table and no report read.
- TECH-1-2 | verified | An Unknown amount whose figure is in the report is a link. Pressing it shows the figure's sources and "These figures differ: the table shows Unknown; the report shows ₦2,400,000.00." at 1440 and 390.
- UX-1-1 | verified | At 390, P-0103 shows the report error and Try again under the cards (visible). One press makes exactly one more E-REPORT request. P-0106 shows the refusal line under the cards.
- UX-1-2 | verified | P-0107 (403) and P-0108 (404) show "You can’t see this project’s money." (approved in D-108), with no stage, amount, report title or server message and no report read.
- UI-1-4 | verified | At 390 the three amount links measure at least 44px tall, and the page does not scroll sideways.
- UI-1-1, UI-1-2 | verified by UI review | These are visual weight fixes. They are outside the QA lens, and the change to `aria-current` behaviour is covered above.

## Notes
- Housekeeping:
  - My servers (mock PID 22427, app PID 22428 and its children) were stopped by PID before the e2e run, which starts and stops its own on the same ports. Ports 4786 and 4787 were free afterwards.
  - `frontend/test-results` was deleted, and the worktree is clean at ac401c09.
  - Scratch files are in /private/tmp/claude-501/-Users-Hunchoo-psl-factory/984b2492-735a-4d33-833d-007cd38fd896/scratchpad/f26-qa/. Disk had 9.8 GB free.
- The brief says "a report 500/403 shows the error with Try again". The spec (Contract, E-REPORT errors; criterion 19) gives a 403 a refusal line with no retry, and the build follows the spec. I tested it against the spec.
