# Money and Milestones tabs on the live project API

Re-specified against 1.24.0 (D-185).

> Tasks: FE-CONNECT-1 (explicit D-180 exception for connecting built screens). Architecture: live contract `contracts/psl-factory.openapi.json` 1.24.0 (main b8542c79); connection map `delivery/connect/screens-b-projects-setup-clients.md` (cross-cutting facts, SCR-12, SCR-38). Design: approved canvas as recorded in `design/screens.md`; screens: SCR-12 (Money tab), SCR-38 (Milestones tab, default and changed states).

## Summary
- The Money tab (`/projects/[caseId]/money`) reads `GET /projects/{case_id}/money` through `liveApi`. It shows one row per item in the order returned, each with amount, invoices, and paid and owed as given. The drill-down reads `items[].sources[]` through `?figure=<key>`.
- The Milestones tab (`/projects/[caseId]/milestones`) shows the contract stages from `/money` numbered by `stage_position`, with a "Done <date> · Proof" line that opens the recorded completion through `milestone_id`. It also shows a "Recorded completions" section from `GET /projects/{case_id}/milestones`. A person without `finance.read` sees the completions plus a plain "not available to your role" note and no figures.
- 1.24.0 switched on: the position number (`stage_position`), the milestone link (`milestone_id`), source references (`sources[].reference`), `state_code` on tab rows, and the one-completion read `GET /projects/{case_id}/milestones/{milestone_id}`. Each replaces a D-182 hide.
- Unknown money is never 0 and never summed. A null `amount`, `paid`, `owed` or `additional_amount` reads Unknown. The invoice `status` is shown exactly as given, and a paid state is never worked out from the numbers (B-16).
- The mock moves to the live shape (UUID ids, P-nnnn still accepted). A new Ajv test validates every served mock body against the live contract.
- Read-only. Mark-complete (SCR-19), change-milestone-link, commercial-response, Ask Chidi with a figure (B-20) and the invoice, cash-lot and correction detail pages are out.

## Context
Frontend, all in `frontend/` of the lane-b worktree. Today both tabs are still on the v7 mock operations:
- `src/features/projects/MoneyTab.tsx`, `moneyModel.ts` and `useMoney.ts` read `E-PROJECT-TAB` (`money[]`, sorted by `position`) and then `E-REPORT` (`figures[]`) through `api`.
- `src/features/projects/MilestonesTab.tsx` and `tabsModel.ts` read `E-PROJECT-TAB` `milestones[]` through `useProjectTab.ts`. `ProjectTabContent.tsx` mounts it. Registers, Actions and Documents share `tabsModel.ts`, `useProjectTab.ts` and `TabParts.tsx`, and they are F-75/F-74, not this feature.
- F-70 (merged, `be9d34d9`) already moved the project page, journey, tab bar and `tabs[]` onto `liveApi` and `src/api/live-schema.d.ts`. Follow `useProject.ts` and `model.ts` there: `call(liveApi.GET(...))`, a guard such as `isJourney`, and `ApiError` and `UNEXPECTED_MESSAGE` for a body that fails the guard.
- Mock: `mock/money.mjs` serves `E-PROJECT-TAB` money and `E-REPORT` from `mock/fixtures/projects/money/P-nnnn.json` and `mock/fixtures/reports/R-nnnn.json`. `mock/project-tabs.mjs` serves the four list tabs from `mock/fixtures/projects/tabs/P-nnnn.<tab>.json`. `mock/projects.mjs` already accepts both UUID and P-nnnn ids (`idOf`, `normaliseProjectPath`, `uuidOf`).
- Tests that cover the old shapes: `tests/money.test.tsx`, `money-model.test.ts`, `mock-money.test.ts`, `project-tabs.test.tsx`, `project-tabs-model.test.ts`, `mock-project-tabs.test.ts`. The pattern to copy is `tests/mock-live-projects.test.ts`.

Live shapes (contract 1.24.0; `src/api/live-schema.d.ts` on main already carries `milestone_id` and `stage_position` on the money item, so lane A does not need to regenerate it):
- `GET /api/v1/projects/{case_id}/money[?figure=<key>]` returns `{items[], limited, as_of, finance_url}`. Each item is `{key, label, amount (decimal string | null), currency, due_date (date | null), milestone_id (int | null), stage_position (int >= 1 | null), completed_at (date-time | null), contract_stage (bool), missing_reason (string | null), invoices[], sources[], changes[]}`. B-18/B-49: contract stages come in native stage order, `stage_position` is the signed stage position, and `milestone_id` is the exact milestone record where a native link exists (null otherwise).
  - `invoices[]` is `{id, reference, version, currency, paid (string | null), owed (string | null), status (text), at, api_url}`. It is not capped, and a stage may hold several.
  - `sources[]` is `{label, django_url, at | null, kind | null, record_id | null, reference | null, api_url | null}`. `reference` is the original reference where recorded (B-19).
  - `changes[]` is `{link_id, version_id, reference, number, note, plan_id, additional_amount (always null), api_url}`, at most 12.
  - Items with `contract_stage: false` are invoices outside any stage (key `invoice-<id>`). Stage keys are the contract stages.
- `GET /api/v1/projects/{case_id}/milestones` returns `{case_id, tab, sections[], as_of}`. The one section is titled "Recorded completions" and carries a `key`, `page`, `has_more`, `total`, `counts` (null here). Its items are `{title (milestone name), state: "Completion recorded", state_code: "recorded", detail (who recorded it, null possible), at, due, severity, owner, reference, record_id (milestone id), django_url, api_url}`. 25 rows a page. Find the section as the tab's only section, never by its title text. The tab itself is visible to people with `commercial.read`, `delivery.read` or `milestone.complete`. `/money` needs `finance.read` and answers 404 otherwise (B-48).
- `GET /api/v1/projects/{case_id}/milestones/{milestone_id}` returns `{id, name, completed_at, evidence_id, proof_version}` for a permitted reader, with the usual 403/404. It carries no file link; the checked proof files are attached through the completion write (F-78) and have no download route in this contract.
- B-16: `/money` invoice `status` is only Draft, Issued or Delivered. Delivered is not paid. Payment status (issued, part-paid, overdue, paid, voided, unknown) lives on `GET /projects/{case_id}/invoices/{issue_id}/payments`, which this feature does not call.

## Contract

### Reads (no writes, no new endpoints, no contract change)

**Money tab, `GET /projects/{case_id}/money`**
- One request when the tab opens. Never polled and never retried automatically.
- Rows are `items[]` in the order returned. Do not sort or total. A contract-stage row with a non-null `stage_position` shows it as the number before the label (SCR-12 board); a null `stage_position` or a `contract_stage: false` row shows no number. Never invent a number from the array index. Every item is drawn, so a `contract_stage: false` row (an invoice outside a stage) appears as its own row under its `label`, in place.
- AMOUNT: `amount` as a decimal string, shown as `<currency> <grouped amount>`. The currency code is the item's `currency`, so use `formatAmount(value, { sign: false })` and put the code in front. Do not assume ₦. A null or non-numeric `amount` shows the existing `Unknown` component with `missing_reason` as the note under it. A known amount shows no note.
- INVOICE column: for each invoice, `reference` followed by `status` text exactly as given. Several invoices stack one per line, in order. No invoices shows a dash with the hidden text "No invoice". The invoice reference is plain text, because the invoice detail page is out of scope.
- PAID column: per invoice, `Paid <amount>` and `Owed <amount>`, each shown as `Unknown` when null. No status word such as "Part paid" or "Paid" is composed. The only status wording is the invoice's own `status`. The tab never compares `paid` to `amount`, and never adds across invoices or stages.
- The `limited` flag, when true, shows a warning Callout above the table: "Some figures may be incomplete." When false, nothing shows.
- Footer: "As of <as_of>" (`When` with `show="daytime"`).
- Drill-down "where this figure comes from": an amount that has sources or a known amount is a link `…/money?figure=<key>`, as today (`replace`, `scroll={false}`, `aria-current`). The side panel (desktop) or bottom sheet (phone) issues `GET …/money?figure=<key>` and lists the matching item's `sources[]` in order. Each source shows `label`, then `reference` when present (as on the board, for example "SOW-0198 v2" when the backend records it), then `kind` as plain text when present, then `at` when present. No source is a link, because `django_url` points at a retired Django page and the matching live detail routes are out of scope. An item with no sources shows "No source recorded". The panel head is the item's `label`.
- A `?figure=` the live API cannot resolve (404) shows "That figure isn't available." in the panel and leaves the table as is. The key in the URL is passed through `encodeURIComponent`.
- The Money tab hides `finance_url` (the retired Django Finance page).

**Milestones tab, two independent reads on open**
- (a) `GET …/money` for the milestone rows. Draw only items with `contract_stage: true`, in the order returned. Columns: MILESTONE (`stage_position` number when non-null, then `label`), CONTRACT AMOUNT (as on the Money tab; each `changes[]` entry adds " + the change · change amount Unknown", and `additional_amount` is always null, so it is always Unknown), COMPLETION, INVOICE, PAID (as on the Money tab), CHANGES (reference and `note` per change; the column appears only when some row has a change, matching the board's "changed" state).
  - COMPLETION: `completed_at` set shows "Done <date>". Null shows "Not completed". When `due_date` is set, "Due <date>" is added under it. When `completed_at` is set and `milestone_id` is non-null, a "Proof" button follows (the board's "Done on <date> · proof"). Pressing it issues `GET …/milestones/{milestone_id}` once per press and shows, inline (phone: in the card), the recorded name, "Completed <date>" and "Proof version <proof_version>". 403 or 404 shows "Proof isn't available to your role." and an error shows "We couldn't load the proof." with Try again. No "Proof" button when `milestone_id` is null, and no proof file link, because the contract has no download route. The tab never infers a link by name or date.
  - The `limited` Callout and the "As of" line are the same as on the Money tab.
- (b) `GET …/milestones` for the "Recorded completions" section. Each row shows `title`, `state`, `at` and "Recorded by <detail>". Without `detail` it shows "Recorded by: not shown". `state_code` is read for logic only and never shown. "Show more" requests `?page=<page+1>` and appends. Each row has the same "Proof" button, using the row's `record_id` for `GET …/milestones/{record_id}`, as above.
- Join (B-47, B-49): a table row is linked to a completion only through `items[].milestone_id`. A recorded completion is the same one when its `record_id` equals that `milestone_id`. Where the loaded completions page holds a match, the row's COMPLETION cell adds "Recorded by <detail>" (nothing when `detail` is null). A row with a null `milestone_id` or no match is never matched by name or date. The completions section still stands under the table as its own list and is not merged into rows, because people without `finance.read` see it alone.
- Phone: one card per milestone in the returned order, then the completions list.
- Page note under both: "Milestones and amounts come from the signed SOW. Completing a milestone is the PM's fact; invoicing and payment are Finance's, and each is shown separately." (existing board text, kept).

### Screen states

| State | Money tab | Milestones tab |
|---|---|---|
| Loading | `LoadingState` | `LoadingState` until both reads settle |
| Empty | `items: []` shows `EmptyState` "No contract stages yet / Stages appear here once the SOW is signed." | No `contract_stage` items shows "No milestones on this project yet." above the completions section. No completions shows "No completions recorded yet." under the heading. |
| Error | 5xx or network: `WorkErrorCard` "We couldn't load this project's money. Your work is safe; nothing was changed." with Try again. Body fails the guard: the same card, with nothing partial drawn. | A failed read gets its own card with Try again, and the other section still shows. |
| No access | 403 or 404: `MoneyNoAccess`, "You can't see this project's money." No figure and no server message. | `/money` 403 or 404: the completions section only, plus the note "Contract amounts, invoices and payments aren't available to your role." No figure and no column. `/milestones` 403 or 404 with `/money` ok: the table only and no completions heading. Both refused: only the "not available to your role" note. |
| Signed out | 401 shows `SignedOutState` with the tab's path (existing behaviour). | Same. |
| Success | table or cards, `as_of`, optional `limited` callout | table, completions, `as_of`, proof inline on press |

A late response for an earlier case or an earlier try is ignored (the sequence guard, as in `useProject.ts`).

### Hooks and files
- Money: keep `MoneyTab.tsx`, `moneyModel.ts`, `useMoney.ts`. `useMoney` takes `(caseId)` and returns `{money, figure, retryMoney, retryFigure}`. It no longer reads `E-REPORT`. `moneyModel.ts` has the live types from `@/api/live-schema`, `isMoney(body)`, `amountText(amount, currency)` (null returns `undefined`, the caller renders `Unknown`), and `invoiceLines(item)`. Remove `figureOf`, `valuesDiffer`, `paidWords` and the v7 types.
- Milestones: keep `MilestonesTab.tsx`. Add `useMilestones.ts` (the two list reads plus an on-demand `readProof(milestoneId)`, each with its own state, reusing `useMoney`'s money read or a shared `readMoney`), and `milestonesModel.ts` (live types, `isCompletions(body)`, `isCompletion(body)` for the detail read, the stage filter, `completionText`, the `milestone_id` join, change text). Remove the milestone-only parts of `tabsModel.ts` (`MilestoneRow`, `Paid`, `Change`, the `milestones` entry of `ROW_CHECKS` and `TabRows`). Leave Registers, Actions and Documents untouched for F-75/F-74.
- `ProjectTabContent.tsx` is edited only to pass the right props to `MilestonesTab`.

### Mock (`frontend/mock`)
- `money.mjs` serves `GET /api/v1/projects/{case_id}/money` in the live shape, with `?figure=<key>` (404 `not_found` for an unknown key). Remove the `E-REPORT` handling. Fixtures `fixtures/projects/money/P-nnnn.json` become the live body. `fixtures/reports/` is deleted when nothing else reads it.
- `project-tabs.mjs` serves `GET /api/v1/projects/{case_id}/milestones` in the live `{case_id, tab, sections[] (with key, page, has_more, total, counts), as_of}` shape, each item with `state_code`, from `fixtures/projects/tabs/P-nnnn.milestones.json`, with `?page`. The other three tabs keep their v7 behaviour. F-75 converts them, so edit only the milestones branch.
- Case ids: UUID in every body (`uuidOf`), with P-nnnn still accepted in requests, as F-70 does. P-0099 stays the no-access id. `money/index.json` keeps its scripted answers (P-0107 403, P-0108 404 for money). Add a scripted 404 on the milestones tab for one persona to cover the `/milestones` refusal. `money.mjs` also serves `GET …/milestones/{milestone_id}` (`{id, name, completed_at, evidence_id, proof_version}`, 404 for an unknown id and for the no-access persona).
- The `psl_mock_milestones=changed` cookie now selects a money fixture that has a change on one stage (the live place for changes). Remove the v7 `…milestones.changed.json`.
- Fixtures must include, in the live shape:
  - stages with `stage_position` 1, 2, 3, one stage with `stage_position: null`, one completed stage whose `milestone_id` equals a `record_id` in the milestones fixture, and one completed stage with `milestone_id: null`;
  - a source with `reference` and one with `reference: null`;
  - a stage with `amount: null` and `missing_reason`;
  - an invoice with `paid: null` and `owed: null`;
  - an invoice with a real `paid` and `owed`, and a stage with two invoices;
  - a `contract_stage: false` invoice row;
  - a change with `additional_amount: null`;
  - an item with sources, and one with `sources: []`;
  - one body with `limited: true` and one with `items: []`;
  - one persona or id for which `/money` is 404 while `/milestones` has completions.

Example `/money` item (fixture):
```json
{"key":"uat","label":"UAT sign-off","amount":null,"currency":"NGN","due_date":"2026-12-12","completed_at":null,
 "contract_stage":true,"missing_reason":"The reviewed stage terms do not state an amount.",
 "invoices":[{"id":412,"reference":"INV-0412","version":1,"currency":"NGN","paid":null,"owed":null,"status":"Awaiting Finance decision","at":"2026-11-20T09:00:00Z","api_url":"/api/v1/projects/00000000-0000-4000-8000-000000000101/billing-invoices/412"}],
 "sources":[],"changes":[{"link_id":7,"version_id":31,"reference":"CHG-0007","number":2,"note":"Extra reporting scope","plan_id":9,"additional_amount":null,"api_url":"/api/v1/projects/00000000-0000-4000-8000-000000000101/change-versions/31"}]}
```
That row shows: amount Unknown with the reason, "INV-0412 · Awaiting Finance decision", Paid Unknown, Owed Unknown, and "change amount Unknown".

## Lanes
- Frontend lane (lane-b worktree, ports 4970/4971): `src/features/projects/{MoneyTab,moneyModel,useMoney,MilestonesTab,useMilestones,milestonesModel,money.css}`, the milestone parts of `tabsModel.ts` and `project-tabs.css`, `ProjectTabContent.tsx`, `mock/money.mjs`, `mock/project-tabs.mjs` (milestones branch only), the money and milestones fixtures, and the tests below. Commands run from `frontend/`.
- Backend lane: none. No contract or Django change. Backend questions B-16, B-47, B-48 and B-49 are answered by this spec's reading (show as given, no join, completions-only for a refused person); the backend may answer later.
- Integration owner: runs the live smoke in the acceptance list (Django 8010, PG 127.0.0.1:55433, Next 4970).
- Shared files: `src/api/*` (including `live-schema.d.ts`) and `src/shell/*` are lane A's, so they are not edited. `src/features/workspace/*` is lane C's. `mock/server.mjs` is shared with the other lanes, and the money route there needs a change only if the path matcher no longer reaches `money.mjs` for the live operation. If it does, make it a separate small commit after `git merge origin/main`, noted in build.md. `tabsModel.ts`, `useProjectTab.ts`, `TabParts.tsx` and `project-tabs.mjs` are shared with F-75/F-74. Do not rename or reshape anything they use.

## Acceptance criteria
1. With `/money` returning stages in a given order, the Money tab rows appear in exactly that order, each contract stage with a non-null `stage_position` showing that number before its label and a null one showing none (never the array index) — verify: `tests/money.test.tsx` renders a fixture whose keys are out of any alphabetical order and asserts the row order.
2. A null `amount` shows Unknown (the existing `Unknown` tag) with its `missing_reason`, and never "0", "0.00" or blank — verify: test asserts the cell text and that no `0.00` appears in the table.
3. A null `paid` or `owed` on an invoice shows Unknown for that figure. The page makes no "Paid" or "Part paid" word of its own. An invoice with `status: "Awaiting Finance decision"` shows that text exactly — verify: component test, plus a model test that `paid === amount` does not change any text.
4. No total, subtotal or sum appears anywhere. A fixture with two known stage amounts and one null shows only the individual figures — verify: test asserts no element contains the arithmetic sum.
5. A stage with two invoices lists both, each with its own status, paid and owed — verify: component test.
6. Currency comes from the item: an `USD` item shows `USD 1,000.00`, never `₦` — verify: model test.
7. `limited: true` shows the "Some figures may be incomplete." warning, and `limited: false` shows none; "As of" shows `as_of` — verify: component test and the `/money` page in the mock.
8. Pressing an amount sets `?figure=<key>`, issues `GET …/money?figure=<key>`, and the panel (phone: the sheet) lists the item's sources in order with label, kind and time. An item with no sources reads "No source recorded". An unknown key shows "That figure isn't available." and leaves the table — verify: component test with the mock server, 1440 and 390 widths.
9. `/money` returning 404 or 403 shows only "You can't see this project's money.", with no stage, amount or server message. A 500 shows the error card with Try again, and pressing it re-reads. A body missing `items` shows the error card and draws nothing partial — verify: tests for each, and no `ApiError` message text in the DOM.
10. The Milestones tab shows `contract_stage: true` items only, with due and completion text, and the CHANGES column only when a change exists. A change with `additional_amount: null` reads "change amount Unknown", and the contract amount is not combined with it — verify: component tests for `default` and for the `psl_mock_milestones=changed` cookie page.
11. "Recorded completions" is its own list under the table and is never merged into table rows. A second page (`has_more`) appends through "Show more" with `?page=2` — verify: test asserts the request query and the appended rows.
12. When `/money` is 404, the Milestones tab shows the completions and the "aren't available to your role" note, and no amount, invoice or column header — verify: test and `/projects/<id>/milestones` with the scripted persona. When `/milestones` is refused and `/money` is ok, the table shows without a completions heading. When both are refused, only the note shows.
13. Wrong user and wrong tenant: a project the persona cannot see (P-0099 and its UUID) answers 404 from both mock routes, and the pages show no data for it — verify: `tests/mock-live-money.test.ts`.
14. `tests/mock-live-money.test.ts` (new, modelled on `mock-live-projects.test.ts`) validates every money fixture and every body the mock serves for `/money`, `/money?figure=`, and `/milestones` (every persona and scenario that returns 200) against the live contract with Ajv 2020 and `addFormats`, with UUID `case_id` values, and checks that P-nnnn requests still resolve — verify: `npx vitest run tests/mock-live-money.test.ts`.
15. The old tests for the removed shapes (`money.test.tsx`, `money-model.test.ts`, `mock-money.test.ts`, and the milestone cases in `project-tabs*.test*` and `mock-project-tabs.test.ts`) are rewritten for the live shape with every behaviour above still asserted. None is deleted without a replacement, and no assertion is weakened — verify: `npx vitest run` passes from `frontend/`.
16. No `api.GET('/api/v1/reports/…')`, `E-PROJECT-TAB` or `E-REPORT` reference remains in `MoneyTab.tsx`, `MilestonesTab.tsx`, `useMoney.ts` or their models — verify: `grep -rn "E-REPORT\|E-PROJECT-TAB" src/features/projects/{Money,Milestones,money,milestones,useMoney,useMilestones}*` has no hits. `npx tsc --noEmit` and `npm run lint` are clean.
17. Live smoke (integration owner): with Django on 8010, a signed-in account that holds `finance.read` opens `/projects/<case_id>/money` and `/milestones` on port 4970, and both render without console errors, with a real `as_of`. A local account without `finance.read` (for example live-none, if it can see a project) opens `/milestones` and sees no figures. If no local project carries money data, record that and rely on criteria 1 to 16 — verify: the build.md records the account, the case and what each page showed.
18. Money display has no write control: no button or form submits anything from either tab, and no request other than GET leaves them — verify: component test spies on `fetch`, and asserts only GET calls.

19. On both tabs, a stage with `stage_position: 2` shows "2" before its name, and a `contract_stage: false` row shows no number — verify: component test at 1440 and 390 widths.
20. A source with `reference` shows it after the label in the drill-down, and a source with `reference: null` shows the label only — verify: component test.
21. A completed stage with a non-null `milestone_id` shows "Proof". Pressing it issues exactly one `GET …/milestones/<milestone_id>` and shows the name, completed date and "Proof version N". A 404 shows "Proof isn't available to your role.". A stage with `milestone_id: null` shows no "Proof" and no completion text, even when a completion has the same name — verify: component tests with the mock server, spying on the request path.
22. When the loaded completions page has a `record_id` equal to a row's `milestone_id`, that row adds "Recorded by <detail>"; a same-name completion with another id is not joined — verify: model test.
23. The Milestones tab finds the completions section as the tab's only section and does not match on the title; a changed title still renders the rows — verify: model test.
24. Delivered is not shown as paid: an invoice with `status: "Delivered"` and `paid: null` shows "Delivered" and Paid Unknown, and no paid word appears — verify: component test.

## Out of scope
- SCR-19 mark-complete (blocked on PSL), change-milestone-link, commercial-response, policy-configuration review, and Ask Chidi with a figure (B-20). The v7 "Ask me" card is hidden. B-20 is answered: a conversation starts from an agent and `case_id`, and a figure key is not a parameter, so a per-figure Ask me card stays out.
- The invoice, cash-lot, payment-receipt and correction detail pages and the per-invoice payments read. The invoice reference and sources are text, not links.
- A proof file link or download (no route in the contract) and the mark-complete write and its upload (F-78).
- Showing `sections[].total`, `counts`, or tab-bar counts (not drawn on SCR-12 or SCR-38).
- Registers and Actions (SCR-11, SCR-29), Documents, and the Delivery route (F-75, F-74). Do not touch their code paths.
- Any change to `src/api`, `src/shell`, `src/features/workspace`, the contract file or the Django code.
- Totals, subtotals, currency conversion, a computed "paid / part paid / not paid" word, and inferring a milestone-to-completion link by name or date.
- Opening the `finance_url` or `django_url` links (retired Django pages).

## Conflicts with the boards
D-182 applies to each hide in this list ("Hide, accept all recs"), and the build default is option 1. Product acceptance for the changed columns and states is recorded under D-184.

D-185: the position number, source references and "Done on <date> · proof" were hides under D-182. 1.24.0 supplies their data, so they are built as drawn and removed from the hide list below.

**Plain hides** (board part with no live source; option 1 = hide, build default; option 2 = keep the board part by asking the backend, not in this release)
1. SCR-12: the explicit paid status word ("Paid", "Part paid", "Not paid", "Not due") and the "owed" amount worked per stage. `/money` gives per-invoice `paid` and `owed` amounts and a `status` of Draft, Issued or Delivered (B-16). The paid word lives on a different per-invoice payments read, so it stays hidden (New product question 1). Recommendation: option 1.
2. SCR-12: the "figures differ" check between the table and the report figure (one read now). Recommendation: option 1.
3. SCR-12: the report title heading (`E-REPORT` `title`) and the agent card with "Ask me about any figure here" (B-20: a figure key is not a conversation parameter). Recommendation: option 1. The lead sentence "Every figure links to the record it came from. Unknown amounts are shown as Unknown, never as 0." stays.
4. SCR-38: "INV-0412 · awaiting Finance decision" as one composed status. It is shown as the invoice `reference` plus the invoice's own `status` text. Recommendation: option 1.
5. SCR-38: the `amount_note` ("to be amended") under the contract amount. Only `missing_reason` appears, and only when the amount is null. Recommendation: option 1.
6. SCR-38: a milestone-level "Mark milestone N complete" button with a reason when disabled. It stays out (SCR-19). Recommendation: option 1.
7. SCR-38: change text as "<reference> · <title>" linking to its work item (live has `reference` and `note`, no work item link). It shows as text. Recommendation: option 1.

**Built as drawn now (D-185, no longer conflicts):** the position number before the stage or milestone name (`stage_position`), source references (`sources[].reference`), and "Done on <date> · proof". There is no proof file link in the contract, so the board's link becomes a button showing the recorded proof version (New product question 2).

**Not a plain hide** (adds something the boards do not draw, or changes a board's meaning)
8. Live data the boards do not draw, worth showing:
    - Option 1 (recommended, built): show the `limited` warning, a "Due <date>" line in COMPLETION, several invoices per stage as a stacked list, and the `contract_stage: false` invoice rows in the Money tab. The `limited` flag marks figures that may be partial, so hiding it would mislead.
    - Option 2: show none of them. `limited` is then never shown, a stage's extra invoices are dropped, and the table matches the boards.
    - Option 3: show `limited` only, and nothing else new.
9. SCR-38 for a person without `finance.read`: the board draws only the full table.
    - Option 1 (recommended, built): show the completions only, plus one plain line, "Contract amounts, invoices and payments aren't available to your role."
    - Option 2: show a single empty state and no completions list.
    - Option 3: stop showing the Milestones tab to such people (a change to F-70's tab bar, not built here).
10. SCR-38 "Recorded completions" is a new section the boards do not draw. It stays a separate list, because people without `finance.read` see it alone, even though rows now join through `milestone_id`.
    - Option 1 (recommended, built): a separate list under the table.
    - Option 2: hide the section and draw only the table, which loses the completion proof for people without `finance.read`.
11. Paid column wording. The board draws one word and an owed amount, and `/money` supplies amounts and a Draft/Issued/Delivered status only.
    - Option 1 (recommended, built): "Paid <amount> · Owed <amount>" with Unknown for each null.
    - Option 2: a dash when both are null and the amounts otherwise. This hides the unknown rather than showing it, so it is not recommended.

## New product questions (1.24.0)
Built as recommended; the design engineer may redirect.
1. **Paid word per invoice.** The board draws "Paid / Part paid / Not paid / Not due". 1.24.0 says that word lives on the per-invoice payments read, not on `/money`, and that Delivered is not paid.
   - Option 1 (recommended, built): the Money tab keeps `status` as given plus Paid and Owed amounts, with no payment word.
   - Option 2: read each invoice's payments status and show its word (one extra read per invoice, and it pulls in the payments feature).
   - Option 3: show a word only when `paid` equals `amount` (rejected: infers paid from numbers).
2. **Proof on a completed milestone.** The board draws a proof link. The contract gives a proof version and evidence id but no file route.
   - Option 1 (recommended, built): a "Proof" button showing the recorded name, date and proof version.
   - Option 2: omit proof until the backend adds a file route.
   - Option 3: "Proof recorded" text only, with no read.

## Assumptions
- `milestone_id` exists only "where a native link exists" (B-49). Where null the row has no Proof button and no join, and is never matched by name.
- The Proof read is on press, not on open, so the tab does not make one request per completed stage.
- `state_code` is `recorded` for every completion today; it drives no display.
- The completions section's `key` value is not stated in the contract. The model takes the single section, and the builder records the live key in build.md.
- Items with `contract_stage: false` are drawn on the Money tab in place and omitted on the Milestones tab. They are invoices outside any stage, so they are money but not milestones.
- The drill-down uses a second read `?figure=<key>` for the chosen figure, per the connection map. It does not use the figure from the first read, so the panel always reflects the backend's own answer for that key.
- A 403 on `/money` is treated the same as the 404 B-48 describes. Both are refusals, and neither is shown as an error.
- The currency code is shown as text from the item's `currency`, not a symbol. The contract carries no other basis field, so "basis" here is `missing_reason` when the amount is unknown and the source `kind`.
- "Not completed" is drawn only from `completed_at: null`. It is not a derived overdue or late state. Due dates are shown but never compared with today.
- The milestone-only code is split into `milestonesModel.ts` and `useMilestones.ts` rather than edited in `tabsModel.ts`, to keep clear of F-75/F-74 edits to the shared tab files.
- The lane runbook asks the spec writer to append board conflicts to `delivery/connect/questions-batch.md`. This spec writes only `spec.md`, so the coordinator copies items 11 to 14 above into the lane B batch.
