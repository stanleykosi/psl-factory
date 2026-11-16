DECISION: READY
RISK: high
SURFACES: ui, api, contract-change, product-decision
PRODUCT-ACCEPTANCE: not-required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-26 is FE-M3-REPORT: the Money tab of a project (SCR-12) with drill-down. A person sees billing by contract stage (stage, amount, invoice, paid) and, on pressing an amount, exactly which signed document, rule and record it comes from. It is 2 boards (SCR-12-desktop, SCR-12-mobile), well under the D-64 cap of 8. One observable outcome, one PR.
- Gates are met. FE-M3-REPORT is in architecture v7 with "Unresolved gates: none" (architecture/packages/v7/delivery.md:1502-1533); its only dependency FE-M3-PROJECTS (F-07) is merged. SCR-12 is in the client approval in design/review.json:25. The only soft gate is D-PROJECT-TAB-ROWS, still `proposed` (architecture/build_model.py:501), which counts under the recorded exception (architecture/sources/decisions-2026-11-15.md items (g) and (i)), the same terms as F-07, F-17 and F-21. Limits: contract mock only, the backend developer may change or refuse any field, nothing released.
- F-26 does not depend on F-25 (project tabs). Both extend the F-07 project page and can be built in parallel, but they touch four shared files; the touch list and merge rule are under "Seam with F-25".
- Risk is high only because this screen shows money. Nothing here calculates, totals or derives a figure. Every amount, invoice state and paid status is composed by the backend (INV-FACTS, INV-UNKNOWN). The rule that matters most is the one the board states: an Unknown amount shows "Unknown", never 0, and there is no computed total.
- No business rule is open. Four small questions go to the backend developer as non-blocking contract proposals (below).
- I did not run `design.py check` because my role has no shell. The spec writer or builder runs it first and stops if it fails.

## Scope
**Outcome (one):** a person who may see a project opens its Money tab, reads each contract stage's amount, invoice state and paid state as the backend returns them, and presses an amount to see the sources of that figure. Reads only. No writes, no decisions.

**Boards (2):**
- SCR-12-desktop (`default`) and SCR-12-mobile. Eyebrow "REPORT · LAGOON HEALTH · PROJECT MONEY", the page title "Lagoon Health · billing by contract stage", the project tab bar with Money selected, the sentence "Every figure links to the record it came from. Unknown amounts are shown as Unknown, never as 0.", the table STAGE / AMOUNT / INVOICE / PAID (the amount is a link), and the right-hand panel "Where ₦4,250,000 comes from" listing sources (label plus reference, e.g. "Signed SOW v2, stage table, row 2 · SOW-0198 v2"; "RULE · stage terms"; "Milestone 2 completion … HB-M2") and the Chidi card ("I can explain any figure here. Ask me"). The phone board shows "Tap an amount to see where it comes from".
- The `loading` state named in screens.md:35 has no board of its own. It is the shared loading state (frontend), not a third board. The spec writer lists it as a frontend state with no fidelity target.
- Titles, eyebrow wording and the tab bar come from E-PROJECT and the existing F-07 header. The frontend does not write "billing by contract stage" from a role or a guess. If E-PROJECT sends no such title, the screen shows the backend title and records the difference (see Contract proposals 5).

**Task ID and endpoints:** FE-M3-REPORT (R-PROJECT, R-REPORTS). Acceptance A-PROJECT and A-REPORT (frontend half).
- E-PROJECT GET `/api/v1/projects/{case_id}`: title, `tab_counts`. Already read by F-07 (`useProject`). No new call.
- E-PROJECT-TAB GET `/api/v1/projects/{case_id}/money` (tab `money`): `money[]` (position, stage, amount, amount_note, invoice, invoice_status, paid, figure_id), `summary.report_id`, `as_of`.
- E-REPORT GET `/api/v1/reports/{report_id}`: title, agent, `figures[]` (id, label, value, sources, `source_details[]`).
- Route: `/projects/[caseId]/money`, already routed to a "comes next" placeholder by `app/projects/[caseId]/[tab]/page.tsx`. A selected figure is `?figure=<id>` so it can be linked and reloaded (gaps-a-project-setup.md:88).

**Reads join, nothing is derived:** a row's `figure_id` is looked up in `figures[].id`. A row with no `figure_id`, or an id with no matching figure, has no drill-down and shows "No source recorded" in the panel, never an empty panel (G-SCR12-3). The amount is then plain text, not a link.

**Out:**
- The other four tabs (milestones, documents, registers, actions) and the tab counts: F-25.
- Any total, sum, balance, percentage, "outstanding" figure or colour-by-threshold. G-SCR12-4: no computed total while any stage is Unknown. The frontend adds no total even when none is Unknown.
- Any write, any Finance action (invoice, receipt, allocation, exception). The page offers none.
- FE-LEADERSHIP-REPORT (SCR-52) and every report-based work item. It depends on this feature later but is not part of it.
- Backend, OpenAPI, `schema.d.ts`, `architecture/**`. Contract gaps are proposals in build.md only.

## Binding rules for the spec
1. **Unknown is not zero (INV-UNKNOWN).** `amount.unknown` or a missing `amount` shows "Unknown" with the board's amber text and the `amount_note` ("Not yet due · amount set at go-live") if sent. Never "0", "₦0", blank or a dash for an unknown amount. The same holds for `paid.owed` and for a figure `value`. The "—" the boards draw in the PAID and INVOICE cells is shown only where the backend sent no invoice or no paid object for a stage that cannot have one. When the backend sent nothing for a cell that should have a value, the cell says "Unknown" (D-94 split: a deliberate "none" keeps the board's "—", a missing value reads "Unknown").
2. **Money formatting is display only.** The amount string is decimal text from the backend with its `currency`. Format it with the shared money formatting in `components/format.ts` without converting through a floating-point number. If the currency is not NGN, show it as sent. No rounding, no re-ordering of rows (the order is `position`).
3. **Invoice and paid are separate columns and separate facts (INV-FACTS).** INVOICE shows `invoice_status` exactly as the backend composes it ("Verified 03 Nov", "Held · owner needed"), with `invoice.reference` as a link to its work item when `work_id` exists. PAID shows `paid.status` through a fixed status-to-words table kept in one place, with `owed` when sent. `finance_tracks` reads "Finance tracks", as the board does; the frontend does not turn it into "unpaid", "unknown" or "paid". The fixed words are presentation, not a business rule; the status itself is never inferred from the invoice.
4. **Drill-down shows only the backend's sources.** Each source is `label` plus `reference`, with a link where `document_id` (to the document) or `work_id` (to the work item) is present. A `kind` of rule or record without a link id is shown as text, not as a guessed link. The panel title ("Where ₦4,250,000 comes from") is built from the figure's own `label` and `value`, not from the table row.
5. **Coverage and time.** The page shows the E-PROJECT-TAB `as_of` ("As of 12 Nov 16:40", board date format) near the table. E-REPORT figures carry no `as_of` today. If the drilled-down figure's `value` differs from the row's `amount`, the page shows both values and a plain "These figures differ" line using the backend's two values. It does not pick one and does not hide the difference. This costs a comparison only. It is the safeguard for the backend question "can the report drift from the money row?" (gaps-a-project-setup.md:99). Sample data: show the shared SampleLabel only where the data says `sample`.
6. **Access.** The backend decides who may read. A 403 or 404 on E-PROJECT-TAB or E-REPORT shows the existing `ProjectNoAccess` state, which names no stage and no amount. The Money tab is not hidden by role in the frontend (it is in the tab bar the boards draw); the frontend has no role rules. If E-PROJECT-TAB succeeds but E-REPORT fails, the table still shows and the drill-down panel shows a retry message with "Your work is safe; nothing was changed" style wording from the existing error card. The table does not disappear because the explanation failed.
7. **Chidi card.** Shown as the boards draw it. "Ask me" links to `/assistant` only if `/me` lists the Assistant (as `AgentSummary` does in ProjectJourney.tsx). The figure context (G-SCR12-2) is a contract proposal and is not built: the link has no figure context, and the card does not claim Chidi will explain this figure. If the spec writer cannot keep the board's "I can explain any figure here" wording honestly with a plain link, it records that as a fidelity exception for the design engineer, not as a decision made here.
8. **Mobile.** Tap targets 44px (D-92c); the amount link in the table is a standalone link, so it also gets 44px on phones. The drill-down panel opens as the shared BottomSheet or inline per the SCR-12-mobile board; the spec writer reads the board and follows it. Focus returns to the pressed amount on close. A deep link with `?figure=` opens it directly.
9. **Shared library (D-91..D-93).** Use `frontend/src/components/` (Table, Panel, Tabs, Tag, Breadcrumb, PageTitle, EmptyState, BottomSheet, SourceTag, Values, SampleLabel, format). Tokens only, no hard-coded colour (the boards' hex values map to tokens). Where the boards and the design-system specs disagree, the boards win (D-93). No new shared component unless two screens already need it.
10. **Tests and fidelity.** v7-typed fixtures for: all four stages (known, awaiting decision, held, Unknown), a row with no `figure_id`, a figure with no `source_details`, report failure (500), 403 and 404, a report value that differs from its row. A mock handler for E-PROJECT-TAB `money` and E-REPORT that validates against the schema (the mock answers 501 today; `tests/mock-projects.test.ts:209` and `tests/mock-contract.test.ts:192` assert that, so the builder updates those two assertions for E-REPORT and the money tab only). Unit tests, and Playwright with axe at 390 and 1440. UI review passes on the fidelity check of both boards at visual 90 or above, one run per round. A board that cannot reach 90 for a reason on the standing list (D-83 applies to line screens only, so it does not apply here) needs a signed per-board waiver.

## Seam with F-25
**Dependency:** F-26 does not need F-25 merged. It needs only F-07, which is merged: the project page, the tab bar and the Money route already exist, and Money currently falls into `ComingNext`. F-26 can build independently on its own branch from dlv-00-delivery-setup.

**Files both features will touch:**
- `frontend/src/features/projects/ProjectJourney.tsx`: both replace the `ComingNext` branch (line 198) with a real tab. This is the main conflict point. F-26 adds one Money branch and a small tab-switch; F-25 adds the other four. To keep the merge trivial, the F-26 builder puts all its work in new files and changes this file by one import and one branch only.
- `frontend/src/features/projects/model.ts`: tab keys, `PROJECT_TABS`, type guards. F-26 adds only money and report types and guards in a new `moneyModel.ts`, not in `model.ts`, unless a type is genuinely shared.
- `frontend/src/features/projects/projects.css`: F-26 adds a separate `money.css` imported by its own component.
- The mock: `frontend/mock/server.mjs` and `frontend/mock/response.mjs` (the E-PROJECT-TAB dispatch) and `frontend/mock/fixtures/**`. E-PROJECT-TAB is one operation for all five tabs, so both features add a handler to the same dispatch. F-26 handles only `tab === 'money'` and E-REPORT, in its own module; anything else keeps the current 501 until F-25 lands. The two tests that assert 501 for E-PROJECT-TAB (`tests/mock-projects.test.ts:209`) and E-REPORT (`tests/mock-contract.test.ts:192`) are touched by both. Whichever merges second rebases and keeps both feature's cases.
- A read hook for E-PROJECT-TAB (F-07 has only `useProject`). Whichever feature merges first owns a generic `useProjectTab(caseId, tab)`. F-26 writes its own small `useMoney` over the same endpoint so it does not wait. A later cleanup may merge them. This is not a blocker.

**Not touched by either:** `src/shell/**`, `features/work-item/**` (it imports `PROJECT_TABS` from `projects/model`, so the tab list and keys in `model.ts` must not change shape), `my-work/**`, `src/api/schema.d.ts`.

**Merge rule:** whichever is ready first merges; the second syncs from dlv-00-delivery-setup and resolves `ProjectJourney.tsx` and the mock dispatch by keeping both. No order is required. Recommend F-25 first if both finish together, since it replaces more of `ComingNext`.

## Risk
High, because this screen shows money and a mistake (a missing unknown shown as 0, a total, a paid state inferred from an invoice) is what the product rules forbid most (AGENTS.md invariants: unknown is not zero, invoices and receipts are separate). The work itself is a read-only display on the contract mock with no calculation, which keeps it contained and easy to verify against fixtures. SURFACES: ui (2 boards), api (E-PROJECT-TAB money rows, E-REPORT), contract-change (D-PROJECT-TAB-ROWS proposal and four optional field additions below), product-decision (what Finance is allowed to see on a money figure is a backend access rule, not decided here). PRODUCT-ACCEPTANCE is not-required: the work conforms to client-approved boards, adds no flow, no copy beyond the boards and no business rule.

## Contract proposals (non-blocking; the builder records them in build.md, does not extend the contract locally)
All are in gaps-a-project-setup.md:94-101 and stay proposals for the backend developer.
1. G-SCR12-1: `source_details[]` gains `version` (document), `component` and `rule_version` (rule) and `case_id` (record), so "Signed SOW v2" and "Stage terms v1, active since 30 Jun" can be shown from data. Until then the panel shows the label and reference only, and the board's "v2" and "active since" text is a listed difference.
2. G-SCR12-2: E-CONVERSATION-NEW gains optional `context:{kind:'report_figure', report_id, figure_id}`; the backend checks the person's access to the report; the explanation comes from the figure's own sources. Until then "Ask me" is a plain link.
3. G-SCR12-3: state in the contract that a money row without `figure_id` has no drill-down and shows "No source recorded".
4. Add `as_of` to E-REPORT figures if the report is cached and can differ from the money row. Also ask whether `paid.status: finance_tracks` means "tracked by Finance and not shown to this person" and not "unknown", and who may read the money tab (403 versus 404 for PMO; a 404 must reveal no stage names). These are questions for the backend developer, already listed; the frontend follows whatever the backend returns.
5. If E-PROJECT sends no "billing by contract stage" title or the eyebrow's client name, ask for them as optional display fields. The frontend does not compose a title.

**Backend items to record (not blocking):** E-PROJECT-TAB `money` and E-REPORT are unimplemented (501 on the mock today). Paid status and owed come from receipts and allocations composed by the backend (D-PROJECT-TAB-ROWS). Nothing leaves the mock.

## Questions
None.
