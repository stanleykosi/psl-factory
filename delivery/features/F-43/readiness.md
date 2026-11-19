DECISION: READY
RISK: high
SURFACES: ui, api, security, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Re-check (18 Nov)
- The only blocker was F-33 not being merged. F-33 is merged (PR #64, DONE), along with F-41, F-42 and F-47. Conflicts are approved (D-118).
- Confirmed on dlv-00 in /Users/Hunchoo/psl-factory/frontend/src: `features/workspace/InlineDecide.tsx` (Decide panel, uses `stepVerdict`), `stepVerdict` in `features/workspace/proposals.ts:105` (reads the `steps[].verdict` overlay), and the hold pattern fixtures from F-33.
- Correction to the original scope: F-42 added `scheduleLine()` in `features/workspace/labels.ts:71-72`. It is a set of line keys (`income_schedules`, `fixed_assets`) that routes to the Decide panel. F-43 should extend it by adding `cash_forecast`, not add a parallel check. The spec writer should read how Workspace.tsx uses it.
- All other gates, scope, conflicts and binding rules below are unchanged. Every "unmerged F-33" statement below is now resolved.

## Summary
- FE-FIN-FORECAST covers 14 SCR-56 boards. The first outcome, **F-43 part 1**, is the management forecast FC-0014 from Chidi's investigation to a verified delivery: **investigating, review, uncertain and verified, desktop and phone (8 boards, D-64)**. Part 2 is group-rows and group-review (4 boards). Part 3 is actuals (2 boards). Both are held on open decisions and gaps (see Scope).
- Formerly NOT-READY for one reason only: the build reuses F-33's work (the inline Decide panel, `stepVerdict`, the `steps[].verdict` overlay, the "policy not set" hold fixture and the money rules). That is now merged. Every other gate is met, so no new decision is needed.
- Gates met. FE-FIN-FORECAST has `gate_ids: []` and "Unresolved gates: none" (architecture/packages/v7/delivery.md:2742-2771). It depends on FE-WORKSPACE-FRAME (F-17, merged). SCR-56 is in the client-approved list (design/review.json:64, 13 Nov, covering the Finance and Payroll canvas), and the D-89 "+ Start" exception is recorded. Milestone M-7 lists D-LINE-WORKSPACE, D-RECEIPT-ALLOCATION, D-RETURN and D-DECISION-VARIANTS (architecture/model.json:22962-22967). Part 1 handles them as F-33 did. D-LINE-WORKSPACE runs under the recorded exception (decisions-2026-11-15.md (g), (i)). D-RETURN is the working assumption for the Return verdict. D-RECEIPT-ALLOCATION and D-DECISION-VARIANTS gate only the actuals, which part 1 leaves out.
- Money: each amount is shown as the backend's decimal string. The page computes no forecast, total, closing balance or variance, and does no rounding. Unknown shows as "Unknown", never 0. Two policy keys are NOT SET: `finance.cash_forecast.preparer` and `.inclusion`, both `holds_work: true` (frontend/mock/fixtures/setup/finance.desktop.json:196-238). So every fixture is sample-marked and one hold fixture shows the backend's `setup_needed`. No Setup key exists for the forecast reviewer, so `required_role` appears only as the sample fixtures return it (backend question).
- F-47B is the Start work drawer for the forecast (main canvas `SCR-04-*-forecast`). F-43 is the work-item page that a start lands on. Neither blocks the other: F-43 opens its fixtures directly (W-40xx) and F-47B's start reaches `/work/<id>` with `line_key: cash_forecast`. I did not run `design.py check` (this role has no shell). The spec writer runs it first; F-33's spec recorded `EXCEPTION, passes: true` on 18 Nov.

## Scope
**Outcome (one):** a Finance person opens FC-0014 "Cash forecast · base case, Nov–Apr". They see what Chidi read and accepted, and the six-month forecast with Unknown months. A forecast reviewer who did not prepare it approves, returns with a note, or rejects it in place. After delivery, an uncertain delivery to the CEO is recorded through the existing reconcile panel, and the verified forecast shows its stated limits. Contract mock only; nothing is sent, published or posted.

**Boards (8):** `design/canvas/finance/project/SCR-56-{desktop,mobile}-{investigating,review,uncertain,verified}.dc.html`.
- Investigating: status "CHIDI INVESTIGATING". Sources facts (Opening balances, Assumptions workbook, Payroll estimate, each ACCEPTED). Agent card: 4 steps, sources ("3 BANK ACCOUNTS · 31 OCT", "9 INVOICES · ₦31.4M", "FC-0013"), "Started 08:40", "Ask Chidi" (G-C-4, the existing `assistant` link). Agent text is shown as returned, never as a decision.
- Review: "AWAITING FINANCE DECISION". `table` "Forecast · 6 months" (MONTH, OPENING, IN, OUT, CLOSING) with January IN and CLOSING as `money.unknown`, and the section note in amber (D-63). The F-33 inline Decide panel shows "Decide · " + `required_role`, the basis as returned, and the steps Approve forecast, Return with a note and Reject, each with `verdict`.
- Uncertain: `state: effect_uncertain`, "EFFECT UNCERTAIN". The `reconcile` facts (Sent 14 NOV 09:00, Confirmation UNKNOWN), and "Record what happened" through the existing F-17 reconcile panel (E-WORK-ACTION `reconcile`, `expected_revision`, CSRF).
- Verified: "VERIFIED". Facts are CALCULATED, REVIEWED, DRAFTED, PUBLISHED, "RECEIPTS 2 of 2" and VERIFIED, all backend text. The limit sentence "The forecast never moves cash or authorises a payment." and `next` are shown as returned.

**Task and endpoints:** FE-FIN-FORECAST part 1 (R-FINANCE, A-WORKSPACE). E-WORK-ITEM, E-TASK-CLAIM and E-TASK-DECIDE through the F-16 `useDecision` (via F-33's panel), and E-WORK-ACTION `reconcile`. All are in frontend/src/api/schema.d.ts (:54, :96, :117, :201; `reconcile` and `allowed_actions` at :1542-1561). No generated type changes.

**Extra fixtures (no board):** a hold where the preparer or inclusion rule is NOT SET (`setup_needed`, a "NOT SET" fact, the backend's `next`, no Decide panel, no reviewer anywhere). Also: prepared by you, not your role, an Unknown amount, two verdicts, and a malformed verdict, the same set as F-33. Ids `W-4001…` with tasks `T-40xx` (night log 06:16). The month-end row "Cash forecast" stays on `W-1605`, the response fixture that `tests/response.test.tsx:196-246` and `e2e/finance-month-end.spec.ts:104` pin (as F-33 Conflicts 8).

**Conflicts the spec must settle (recommendations; approved in D-118):**
1. **Compact amounts on the review table** ("₦22.6M", desktop and phone). Recommend the full returned amount ("₦22,600,000.00"), with no `compactAmount` and no browser rounding (F-33 Conflicts 3, D-113). Option B: show a short form only if the backend sends `money.display_short`. D-63 allows compact figures where a line's own task opts in, but rounding a figure someone is approving breaks the money rule.
2. **"Cancel delivery" on the uncertain board.** What it does to an uncertain delivery is an open backend question (gaps-f-finance-workspaces.md:137). The workspace also has no cancel control today. Recommend: not drawn in part 1 (listed difference). The fixture's `allowed_actions` sends only `reconcile`. No resend control appears unless `reconcile.resend` is returned (INV-RESEND). The board draws no retry button.
3. **"Record actuals" on the verified board** opens a form no board draws (G-56-5) and belongs to part 3. Recommend: not drawn, and `next` is shown as returned.
4. **Note label "needed to return, reject or withdraw"**: withdraw is not offered, so the label reads "Note (needed to return or reject)" (F-33 Conflicts 7). The basis sentence's empty audience (G-56-9) is shown exactly as returned.
5. The usual F-33 layout items: desktop wording at both widths, the phone Drawer for Return and Reject, frame items, signed-in persona and sample data. Each goes in `fidelity-exceptions.json`. Visual waivers cite D-83.

**Out (named):**
- **Part 2, group version** (`SCR-56-*-group-rows`, `-group-review`, 4 boards). Held on G-56-1 (no multiple-choice field kind, blocking), G-56-2 (FC-0015 created as separate work), G-56-3 (`group_reviewer` NOT SET; a sample reviewer must never appear), G-56-4 and D-PAYROLL-VISIBILITY (the Payroll row), and G-C-7 (delivery to the Group CFO).
- **Part 3, actuals** (`SCR-56-*-actuals`, 2 boards). Held on D-RECEIPT-ALLOCATION and D-DECISION-VARIANTS (the Kola Foods part-payment match must not allocate a receipt or erase the shortfall), G-56-5 to -8, and D-PAYROLL-VISIBILITY (the Payroll actual).
- Publishing or sending the forecast (G-C-7), per-recipient reconcile (G-C-5), Withdraw (`revoke`), and "Correct and resubmit" after a return. D-RETURN is open, and no SCR-56 board draws a returned state, so a return re-reads and shows whatever comes back.
- The Start work forecast drawer (F-47B). Any change to `useDecision`, the decide mock, `server.mjs`, the response fixtures or `W-1605`. Backend, OpenAPI, `schema.d.ts`, `architecture/**`, `design/**`, `src/shell/**`.

**Binding rules for the spec:**
1. Money comes as `{amount: "<decimal string>", currency, unknown}`, formatted by `formatAmount` with no float. No `parseFloat`, `Number(`, `reduce(` or arithmetic on an amount, and no closing balance, total or variance computed by the page. Unknown is the word "Unknown", never "₦0", "0.00", blank or a dash.
2. Any unset policy key is a hold. The page draws the backend's `setup_needed` and invents no preparer, reviewer or inclusion rule. Every fixture is `sample: true`.
3. Controls come only from `tasks[].you_can_act` and the steps and `allowed_actions` sent. The page does not read `/me` and has no separation-of-duties logic. 403 and 404 look the same.
4. Writes send CSRF and `expected_revision`. A failed or uncertain write re-reads first, never says "approved" or "recorded" from the click, and never resends on its own. "Verified" appears only from the re-read `state`.
5. One fidelity run per round over the 8 boards. Coverage is 100% after exceptions, visual at least 90 or a D-83 waiver with visual at least 70. Axe runs at 390 and 1440. High risk: Opus for the first build, plus security and QA on Opus (D-64).
6. Extend `scheduleLine()` (labels.ts) with `cash_forecast` for the Decide panel routing; do not duplicate it.

## Risk
High. This is an approval write on a money figure (E-TASK-DECIDE through F-33's panel) plus a reconcile record on an uncertain internal delivery (E-WORK-ACTION). Both are hard to undo and are audit-bearing. The forecast table carries Unknown amounts that must never read as 0. SURFACES: ui (8 SCR-56 boards); api (the decide, claim and reconcile writes); security (authority only from `you_can_act`, CSRF, 403 and 404 alike, policy holds with no invented approver); contract-change (consumer of F-33's `steps[].verdict` overlay and the G-C-1, G-C-2 proposals). I did not tick payments, because the forecast moves no cash and the actuals are out. I did not tick external-messaging, because the page sends nothing; delivery is the backend's and is held by G-C-7. PRODUCT-ACCEPTANCE is required because the forecast review, its wording and the uncertain-delivery record are new to the client.

## Questions
None for the client in part 1. For the backend developer (these hold the real writes, not this mock build): which role or Setup key decides the management forecast review (there is no `finance.cash_forecast.reviewer`; only the preparer, inclusion and group reviewer keys exist); what "Cancel delivery" does while the effect is uncertain, and which state follows; whether publishing is automatic or a step, and who the "RECEIPTS 2 of 2" are (gaps-f-finance-workspaces.md:136-138); and G-C-1, G-C-5, G-C-7 and G-56-9.
