VERDICT: PASS
COMMIT: fb9f9fc1ef11f56b9d0416b4b36497a1be123f63
REVIEWER: qa
AUTHORITY: delivery integrated QA

## Summary
- Exercised on head fb9f9fc1 (F-25 merged with F-23, F-26 and F-27). A fresh production build (`next start -p 4797`, `API_ORIGIN=http://127.0.0.1:4796`) ran against the contract mock (`node mock/server.mjs`, MOCK_PORT=4796). A Playwright session ("F-25-qa", timezone Africa/Lagos) drove pages as `pm` and `finance_lead` at 1440, 1024 and 390, plus `ceo` and `none` for the wrong-user cases. I also called the mock endpoints directly with curl. Result: 488 of 488 browser checks passed and 23 direct API calls returned the expected status.
- I re-ran the e2e myself: `E2E_PORT=4797 MOCK_PORT=4796 npx playwright test e2e/project-tabs.spec.ts e2e/projects.spec.ts e2e/money.spec.ts` passed 71 of 71 (1.9 min, build included). The coordinator's merge evidence (`merge-checks.log`: checks.sh exit 0 with 2085 tests; `merge-e2e.log`: 106 of 106) is enough for the rest of the suite. Between 8a307a5e and fb9f9fc1 nothing changed in `features/projects`, `components`, `mock/project-tabs.mjs` or the project fixtures, and the browser journeys here cover the integrated tabs end to end.
- Milestones: values show in returned order. Unknown is never 0 or blank. A change amount sits next to the contract amount and is never added to it. Completion, invoice and paid are separate cells (and separate phone lines). The changed state works. Long values wrap and nothing is cut at any of the three widths. Registers paging and search work. Actions work. Rows link only when they have a work_id. Empty, no-match, 403, no-access and 401 states all behave correctly. Money (F-26) still renders, and Documents still says "Documents come next".
- Not proved: E-PROJECT-TAB has no backend. Every row is mock fixture data under the proposed D-PROJECT-TAB-ROWS contract, so per-record and tenant access are only as good as the mock's persona rules. I tested the 500 and network failures with Playwright `route.fulfill`/`route.abort`, because the mock has no 500 scenario. I sent the 401 and 403 cases through the real mock using the `X-Mock-Scenario` header. I checked long-value wrapping by injecting longer strings into the mock's real response.

## Journeys
Script: `scratchpad/f25-qa3/qa.mjs`, run output `run3.txt` (TOTAL 488 PASS 488 FAIL 0). Each line below ran for pm and finance_lead at 1440, 1024 and 390 unless a width is named.

Milestones, P-0101 `/projects/P-0101/milestones`
- PASS | Order and values | The rows read 1 Kick-off, 2 UAT sign-off, 3 Go-live, 4 Hypercare. The page makes one tab read with `limit=20` and no `q` or `cursor`. Desktop row 1 cells are "₦3,000,000.00 ‖ Done 27 Oct · proof ‖ INV-0398 · Verified ‖ Part paid · ₦500,000.00 owed". Row 2 shows PAID "—" (it has an invoice but no paid record). Row 4's amount is the Unknown tag, with "Not yet · amount set at go-live".
- PASS | Unknown never 0, no sums | The body has no "₦0", "₦0.00", 11,500,000, 8,500,000 or 7,250,000. There is no total row. There is no completion button, link or form.
- PASS | Separate facts on the phone | Each card has an amount · completion line, an invoice line and a separate "Paid: Part paid · ₦500,000.00 owed" line.
- PASS | Links | The only row links are INV-0398 → /work/W-1713 and INV-0412 → /work/W-1001.
- PASS | Changed (cookie `psl_mock_milestones=changed`) | Desktop columns are MILESTONE, CONTRACT AMOUNT, COMPLETION, INVOICE, PAID, CHANGES. Go-live reads "₦4,250,000.00 + the change · change amount Unknown", and no 8,500,000 appears. "CR-0031 · SMS reminders" links to /work/W-1005. On the phone the card shows the "CHANGED · CR-0031" tag, which is a link to /work/W-1005.
- PASS | Invoice with a missing state or the value "unknown" | I deleted `state` from INV-0398 and set INV-0412's `state` to "unknown" in the mock response. The cells read "INV-0398 · Unknown" and "INV-0412 · Unknown".
- PASS | Long values wrap, never cut | I injected a 75-character milestone name, a 39-character invoice reference, a 72-character proof, a 75-character change title and owed ₦123,456,789,012.34. All of them show in full at 1440, 1024 and 390. The phone shows the change as its tag, as the spec says. No td or card element has scrollWidth > clientWidth or `text-overflow: ellipsis`, and the page never scrolls sideways (screenshot `pm@1024-milestones-long.png`).
- PASS | Edge cases on P-0102 | ₦9,500,000.00 and the change ₦750,000.00 show side by side, and 10,250,000 never appears. "USD 1,250,000.50" is not converted. Every paid word shows: Paid, Part paid, Not paid, Not due and Tracked by Finance. `paid.status: unknown` shows Unknown, and an unknown owed amount reads "Part paid · Unknown owed". INV-0502 and CR-0091, which have no work_id, are not links.

Registers
- PASS | Default | One request with `register=issues&limit=20`. The register tabs read "Issues 3 / Changes 2 / Emergencies 0 / RFPs 1". There is no Filter button. Rows show ISS-0233 "PM · Tunde Bello", "Engineering (recorded by PM)", "Fix in testing", 2d, 4d and Unknown, with "3 ISSUES". Every link is /work/W-n.
- PASS | Switching register | Changes sets `?register=changes` and requests `register=changes` without a cursor. Emergencies shows "No emergencies on this project yet." RFPs shows RFP-0044. Issues removes `register` from the URL. `?register=x` reads as Issues.
- PASS | Search | "zzzz" sets `?q=zzzz`, requests `q=zzzz` and shows "No issues match “zzzz”." with Clear search. Clear search removes `q` and brings the rows back. "android" shows ISS-0233 only.
- PASS | Paging, P-0102 Issues | 20 rows and Show more. One press sends `cursor=o20` and shows 25 rows, and the URL never carries the cursor. Show more is gone after the last page. Changing register starts again from page one.

Actions
- PASS | Default | The header text reads "9 ACTIONS · 3 OVERDUE · 1 WITHOUT OWNER". Owners show as Client · Lagoon Health, Engineering (recorded by PM), No owner and Tunde Bello. Due shows Unknown where it is not known. States show OPEN, OVERDUE and DONE, and rows show "From Weekly sync · 10 Nov". The footer reads "Actions come from confirmed minutes." on desktop; the phone board draws no footer. Nothing says "recorded with your name". Links go only to /work/W-n.
- PASS | Search | "qqqq" shows "No actions match “qqqq”." with Clear search. No page scrolls sideways at any width.

States and access
- PASS | Empty, P-0106 | The milestones, registers and actions tabs each show their one empty sentence once. There is no table, no count text and no invented 0.
- PASS | 403 on every tab, P-0103 | The panel says "No access to this tab". The header (Kora Logistics) stays. No INV-, ISS-, milestone name or ₦ appears in the panel.
- PASS | 403 after a first page | Registers loaded, then I searched with the tab read set to `X-Mock-Scenario: 403`. The earlier rows are gone from the whole page.
- PASS | Project no access | P-0099, and P-0104 opened as pm (a finance-only project): "You can't open this project … not even its name". No tab request is made and no project name shows.
- PASS | 401 keeps the path | Registers opened with `?register=changes&q=sms` and the tab read set to 401. The sign-in link is `/accounts/login/?next=%2Fprojects%2FP-0101%2Fregisters%3Fregister%3Dchanges%26q%3Dsms`.
- PASS | 500 and network failure | A 500 shows "We couldn’t load this tab. Your work is safe; nothing was changed." after one request, with no automatic retry in 2.5 s. Retry against a network abort sends exactly one more request and shows the error card again. Retry against the mock sends one request and the rows come back.
- PASS | Wrong user | `ceo` and `none` see no milestone name or amount on P-0101/milestones. `none` gets F-07's "No sections are open to your role yet" and makes no project request.

Tabs together
- PASS | Money (F-26) | It renders "Lagoon Health · billing by contract stage" with Stage 1 at every width and persona. Documents shows "Documents come next". Journey renders. Registers is the selected project tab on /registers.
- PASS | Requests go only to the mock | Every browser request stayed on localhost:4797, which `next.config.ts` rewrites to the mock on 4796. Responses carried the mock's cookie and scenario behaviour (the changed file, persona 404s, `X-Mock-Scenario`).

Direct API calls (curl to 127.0.0.1:4796)
- PASS | Expected statuses | 200 for pm and finance_lead milestones, registers and actions. 404 `invalid_query` for `register=x`, `register` on milestones, `limit=7`, `q=`, `cursor=zz` and `cursor=o999`. 403 for P-0103. 404 for P-0099, for P-0104 as pm, and for P-0101 as none or ceo. 200 (empty) for P-0104 as finance_lead. 501 for documents. 200 for money (F-26). 401 with the scenario cookie. 404 for an unknown tab. 200 for P-0102 page 2 (`cursor=o20`).

E2E
- PASS | `npx playwright test e2e/project-tabs.spec.ts e2e/projects.spec.ts e2e/money.spec.ts` (E2E_PORT=4797, MOCK_PORT=4796) | 71 passed, 0 failed.

## Totals
- Browser checks: 488 run, 488 passed, 0 failed (pm and finance_lead × 1440, 1024 and 390, plus the ceo, none and P-0104 cases).
- Direct API calls: 23, all as expected.
- E2E: 71 of 71.

## Findings
None.

## Verified
- Round-3 `## Fixes` within the QA lens: UI-2-1 and TECH-2-1 (wrap, not cut) | verified | no clipped cell and no ellipsis at 1440, 1024 or 390 with long injected values (see Journeys).
- UX-2-1 (empty sentence h2) | verified | P-0106 empty states render under the h1; the e2e axe and heading cases pass.
- UI-2-2, UI-2-3, UI-2-4, UI-3-1 and UI-3-2 are fidelity, waiver and line-height items for the UI review. They are carried forward by impact: they change no journey, value or state.

## Notes
- QA-side setup, not product: my scratch files are in `scratchpad/f25-qa3/`. I stopped servers 79080 (mock) and 79082/79120 (app) by PID, deleted `frontend/test-results`, and left the worktree clean.
