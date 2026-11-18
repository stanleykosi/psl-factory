DECISION: READY
RISK: high
SURFACES: ui, api, security, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-42 is FE-FIN-PPE part 1, **the source for the October asset schedule (PPE-0006) is approved**. Chidi checks the register, a PPE reviewer approves the register changes, then approves the explained in-service dates, and the item goes to calculation, or is held there when Calculation rules are not set. That is 8 of the 14 boards: investigating, register-review, date-review and calculating, each on desktop and phone (D-64). It is one outcome and one PR. No depreciation, opening, closing or class total appears on any part 1 board.
- The gates are met. FE-FIN-PPE has `gate_ids: []` and "Unresolved gates: none" (architecture/packages/v7/delivery.md:2711-2740). Its only dependency, FE-WORKSPACE-FRAME (F-17), is merged. SCR-55 is in the 13 Nov client approval, which covers the Finance and Payroll canvas (design/review.json:63, 109). The D-89 "+ Start" exception changes only the frame. D-LINE-WORKSPACE (`proposed`) counts only under the recorded exception, on the same terms as F-33: contract mock only, and nothing is released. D-RETURN (open, revision 2, a working assumption) touches part 1 only through the return verdict's re-read.
- **Depends on F-33's branch** (`fe-fin-schedules-income-detail-review`, head d20fd9b2, READY_FOR_ACCEPTANCE, not merged). F-42 reuses F-33's `features/workspace/InlineDecide.tsx`, `proposals.ts` `stepVerdict`, the `steps[].verdict` overlay and its `mock-contract` strip, and the "reviewer not set" hold fixture pattern (D-113: decide in place, controls only from `you_can_act`). None of these is on dlv-00 yet. So the spec is written against F-33's head, and the build starts only after F-33 merges into dlv-00, as with F-35. If F-33 changes in its last round, the spec is re-checked.
- All the policy is NOT SET. That covers `finance.asset_schedule.register`, `.calculation` and `.reviewer` (frontend/mock/fixtures/setup/finance.desktop.json:137-175), plus F07.source_rules, F07.calculation_rules and F07.review_authority, all `UNCONFIGURED` (contracts/ppe-policy-components.json). guide/10 names no depreciation or capitalisation key at all. So every review fixture is sample-marked, and each unset rule is a backend hold with no control. The page never guesses a rule.
- I did not run `design.py check`, because this role has no shell. The spec writer runs it first and stops if it fails.

## Scope
**Outcome (one):** a Finance person opens PPE-0006 "Fixed asset schedule · October". They see what Chidi read: 64 assets, 4 added, 1 disposed, 3 unclear dates, values not read. A PPE reviewer who did not prepare the item then approves, returns or rejects the register changes, and after that the explained in-service dates, both in place. The item then shows as calculating by the factory, or as held when a rule is unset. Contract mock only.

**Boards (8, part 1)**, from `design/canvas/finance/project/`:
- `SCR-55-{desktop,mobile}-investigating`: "CHIDI INVESTIGATING". The 6 stations, the "Register" facts with the unclear-dates tag, the line "Chidi never reads asset values…", and the agent card (4 steps, sources "PPE_REGISTER_OCT.XLSX · 64 ASSETS", "PPE-0005", "VALUES NOT READ", "Started 10:05", "Ask Chidi").
- `SCR-55-{desktop,mobile}-register-review`: "AWAITING FINANCE DECISION". The "Register changes" table (ASSET / CHANGE / COST, with cost as `money` cells: ₦8,400,000.00, ₦14,000,000.00, ₦3,150,000.00). Then "Decide · PPE reviewer" with the basis, Approve register / Return with a note / Reject, and the consequence "3 assets have unclear dates; they go to a date review next."
- `SCR-55-{desktop,mobile}-date-review`: "AWAITING FINANCE DECISION". The "Unclear dates" table (ASSET / REGISTER SAYS / EXPLANATION, all text) and the proof as a `cites` entry ("asset-dates-explanation.pdf · Uploaded · 64 KB", nothing uploaded by this page). Then the Decide panel with Approve dates / Return with a note / Reject.
- `SCR-55-{desktop,mobile}-calculating`: "PROCESSING". The "Calculation" facts (Source REGISTER · APPROVED, Dates APPROVED, Rule F07 CALCULATION RULES) and the `next` sentence, all as returned.

**Boards left for part 2 (6):** `SCR-55-{desktop,mobile}-schedule-review`, `-returned` and `-verified`. Part 2 is the schedule by class with Unknown and its review. It waits on these:
- Calculation rules (F07), NOT SET.
- G-55-2 (blocking): does the furniture correction carry an `opening_balance` money field, or come only from the proof?
- G-55-4 and G-C-1 (blocking): what "Withdraw approval" withdraws.
- G-55-3: the accounting note section.
- D-RETURN, for "Correct and resubmit".
- E-EVIDENCE-UPLOAD of the correction proof.
- The board's compact amounts ("₦42.1M", "₦0.0M"). No endpoint supplies these, and the browser must not round them (F-33 conflict 3 precedent).
- G-C-3, the "Feeds MANAGEMENT ACCOUNTS" link.

Also missing, from both parts: the board where a person writes the date explanation (G-55-1, which needs the design engineer).

**Relation to F-47B:** F-47B (proposed in delivery/features/F-47/readiness.md:13, 34) is the SCR-04 Start work drawer for the fixed-asset line, where the register proof is uploaded at start. Its "lands on `/work/<work_id>`" is this page's investigating state. Neither blocks the other. F-42 opens its fixtures directly, and F-47B needs only that a work id exists. Whichever merges second may point the start's mock `work_id` at W-3901, but that is optional and is listed in its build.md.

**Task and endpoints:** FE-FIN-PPE (R-FINANCE), acceptance A-WORKSPACE (frontend half). All of these are typed in frontend/src/api/schema.d.ts:
- E-WORK-ITEM `GET /api/v1/work/{work_id}`, proposed `line_key` `fixed_assets` and `screen` "SCR-55". It covers `stations`, `agent`, `tasks[]` (two decide tasks on one item: register and dates), table `cells[].money` (:1767), `cites` (:1830), `facts` and `next`.
- E-TASK-CLAIM and E-TASK-DECIDE (:117), verdict approve, return or reject, with a note for return and reject. `revoke` is part 2.
- E-WORK-STEP is not used in part 1, and E-EVIDENCE-UPLOAD is not used either.

**Reuse, not rebuild:** the F-17 frame, plus F-33's InlineDecide over F-16 `useDecision`, routed per step `task_id`, so two tasks on one item work. Also `components/format.ts` `formatAmount` and `UNKNOWN`, the `assistant` link, and the `Sections` table and `cites` renderers.

**Mock seam:** the month-end row "Fixed asset schedule" points at `W-1604`. That id is the response tests' no-grant fixture (tests/response.test.tsx:791, tests/response-mock.test.ts:257), and month-end tests pin the link. So follow F-33 option (b): new ids from the F-42 block, `W-3901` upward, and `T-39xx`, with W-1604 and the month-end row unchanged.

**Fixtures the spec must add beyond the 4 boards:** register review where the person cannot act (`prepared_by_you`); "Who reviews assets" not set (`setup_needed`, no task, no reviewer named anywhere); Calculation rules not set (`setup_needed` at station 4, with no calculating claim and no figures); an Unknown cost cell; and the return and reject sidecars, drawn as the backend's re-read only. No board draws the returned register, so it gets no correction step in part 1. Every fixture is `sample: true`.

**Out:** part 2 (above); any depreciation, opening, additions, disposals, closing or class total; the useful life, which date starts depreciation (F07), capitalisation; the explain-dates step and any upload; Setup editing (SCR-13); backend, OpenAPI, `schema.d.ts` regeneration, `architecture/**`, `src/shell/**`.

## Binding rules for the spec
1. **Money.** Cost is the backend's `money.amount` decimal string with its currency, formatted by the shared formatter with no float. `unknown` or a missing amount shows "Unknown", never 0, blank or a dash. The page computes no total, count ("64", "4", "3"), difference or depreciation. The diff contains no `parseFloat`, `Number(`, `reduce(` or `compactAmount`.
2. **Policy unset is a hold.** No fixture names a real reviewer or rule. The unset reviewer and unset calculation rules each show the backend's `setup_needed` status and facts ("NOT SET"), with no decide control and no calculation shown as started. "Depreciation starts from these dates" and "Rule F07…" appear only as the backend's text, and the frontend chooses no date.
3. **Agent work is not a decision.** Chidi's steps and "VALUES NOT READ" render as agent work, from data. The guarantee that Chidi never reads values is the backend's (G-55-6), and it is not frontend copy. "Approved" and "calculating" appear only from the re-read state.
4. **Authority.** Decide buttons show only when that task's `you_can_act` is true. Refusals come from `cannot_act_reason`. The page has no role, person or `/me` rule. 403 and 404 look the same. Writes use CSRF, `expected_revision` as read, and claim-then-decide. On an uncertain failure, re-read first and never resend automatically.
5. **Fidelity and quality (D-64, D-83, D-91, D-92c).** One fidelity run per round over the 8 boards. Coverage is 100% after exceptions, and visual is at least 90 or has a signed D-83 waiver of at least 70. Axe runs at 390 and 1440. Phones have 44px targets. The phone shows the desktop data in one column, and the Note opens in a Drawer (D-111, F-33). Tokens and components only. Opus builder (high risk).

## Risk
High. This is a Finance approval of the register and dates that the asset schedule is built on, and the register-change rows carry money (₦14,000,000.00 disposal). A wrong control would make a Finance source look approved without the human decision. The rules at stake are the ones the product guards most closely: Unknown shown as 0, a browser-computed figure, an invented reviewer or rule, and an agent claim read as approval. The work stays contained: two decide tasks on the F-17 frame through F-33's inline Decide, on the mock, with nothing calculated or posted.

The SURFACES are these:
- ui: 8 boards.
- api: E-WORK-ITEM and E-TASK-CLAIM/DECIDE.
- security: an authority-bearing approval write.
- contract-change: `fixed_assets` line, `steps[].verdict`, two tasks per item.
- product-decision: all asset rules and F07 unset, plus D-RETURN open.

PRODUCT-ACCEPTANCE is required, because this is a new Finance flow, it involves money, and the client has not seen it working.

## Questions
None for part 1. These go to the backend developer and Finance, and they hold part 2 or the real transition:
1. Are register, dates and schedule three tasks on one work item, created in order, and is the date review skipped when no date is unclear (gaps-f-finance-workspaces.md:112)?
2. With Calculation rules (F07) NOT SET, is the item `setup_needed` at station 4 (gaps-f-finance-workspaces.md:113)?
3. Does a returned register review give the preparer a correction task (D-RETURN), and what does it ask for?
4. G-55-2 and G-55-4 (part 2): is the opening balance a money field, and what does "Withdraw approval" withdraw?
