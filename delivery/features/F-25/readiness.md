DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change, product-decision
PRODUCT-ACCEPTANCE: not-required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-25 builds the content of three of the project's tabs on the existing tab bar: Milestones (SCR-38), Registers (SCR-11) and Actions (SCR-29). That is 8 boards (SCR-38 default and changed, SCR-11 default, SCR-29 default, each desktop and phone), which meets the D-64 cap of about 8. No split is needed.
- The other tabs go elsewhere. Money (SCR-12) is F-26 (FE-M3-REPORT). "Mark milestone complete" (SCR-19) is FE-MILESTONE-COMPLETE, and the document review page (SCR-08) is FE-DOCUMENT-REVIEW. Both wait on this task. The Documents tab has no approved list board, so F-25 does not build it.
- Gates are met. FE-M3-PROJECT-TABS is in architecture v7 with "Unresolved gates: none" (architecture/packages/v7/delivery.md:1471-1500). The boards are in the client approval of 13 Nov 2026 (design/review.json:110, SCR-11, SCR-29 and SCR-38 listed at lines 24, 42 and 46). The dependency FE-M3-PROJECTS (F-07) is merged: the tab bar and the `/projects/[caseId]/[tab]` route exist, and each non-journey tab shows a "coming next" panel (ProjectJourney.tsx:170-199).
- The one soft gate is D-PROJECT-TAB-ROWS, still `proposed` (architecture/build_model.py:501). It counts only under the recorded exception (architecture/sources/decisions-2026-11-15.md items (g) and (i)): contract mock only, the backend developer may change or refuse any field, nothing released. No business rule is open.
- I did not run `design.py check` because my role has no shell. The spec writer or builder runs it first and stops if it fails.

## Scope
**Outcome (one):** a person on a project opens Milestones, Registers or Actions from the tab bar and reads that tab's rows from `E-PROJECT-TAB`, with the project's counts, search and paging, and can follow a row to its work item. All three tabs are read-only and mounted on the existing `ProjectJourneyPage` tab panel, replacing `ComingNext` for those three tabs only.

**Boards in F-25 (8):**
- SCR-38-desktop and SCR-38-mobile (`default`): milestone rows with MILESTONE, CONTRACT AMOUNT, COMPLETION, INVOICE, PAID. Completion, invoice and payment are separate facts, as the board says.
- SCR-38-desktop-changed and SCR-38-mobile-changed (`changed`): a CHANGES column ("CR-0031 · SMS reminders") with its own amount, shown when any row has `changes`. The original amount and the change are never added together, and an unknown change amount shows "Unknown", never 0.
- SCR-11-desktop and SCR-11-mobile (`default`): the register selector with counts (issues, changes, emergencies, RFPs) from `summary.registers`, search, the Issues columns ISSUE, WHAT, SEVERITY, OWNER, STATE and AGE, and the footer sentence. The `empty` state has no board. The frontend builds the shared empty pattern from the STATES board.
- SCR-29-desktop and SCR-29-mobile (`default`): the header counts "ACTIONS · OVERDUE · WITHOUT OWNER" from `summary.actions`, and the columns ACTION, FROM, OWNER, DUE, STATE.

**Reuse, not rebuild** (shared library, D-91..D-102): `Table`, `Tabs`, `ListToolbar`, `SearchField`, `Segmented` (register selector), `Tag`, `CountBadge`, `SampleLabel`, `Values` (money and Unknown), `ShowMore` (paging), `Callout`, `Loading` and `PageTitle`. `useProject.ts` and `ProjectTabs.tsx` are kept. Money formatting reuses `features/decide/format`. Do not add a new table or tab component. Where a board needs a small general change to a shared component, make it general and keep the existing tests green. The register selector and search state go in the URL (`?register=`, `?q=`), as the projects list does. Cursors are never written to the URL.

**Task and endpoints:** FE-M3-PROJECT-TABS (R-PROJECT); acceptance A-PROJECT-TABS (frontend half). `E-PROJECT` (read: `tab_counts`, `title`, `pm`) and `E-PROJECT-TAB` (read: `milestones`, `registers` and `actions` arrays, `summary`, `next_cursor`, `as_of`; query `register`, `q`, `cursor`, `limit`). No writes. Routes stay `/projects/[caseId]/milestones|registers|actions`. The `documents` and `money` routes keep their current panel.

**Tests and fidelity (D-64):**
- v7-typed fixtures and mock handlers for the three tab reads, validated against the schema. Cover the default and changed milestone rows, an unknown contract amount and an unknown change amount, a closed issue with no `age_seconds`, an owner who is a team or an outside party, an owner who is absent ("No owner"), a due date that is unknown, a sample row, an empty register, paging, and a 401, 403 and 404.
- Unit tests, plus Playwright with axe at 390 and 1440. Tab keyboard behaviour stays as built.
- Fidelity: the UI review passes only on the design-fidelity check of all 8 boards, every element present (after approved exceptions) and a score of at least 90 (decisions item (h)). One fidelity run per round (D-64). Tokens only, no hard-coded colour. Sonnet builder, because the work is read-only on the mock.

**Binding rules for the spec:**
- Unknown is not zero (INV-UNKNOWN). An unknown contract amount, change amount, due date or age shows "Unknown" (or the backend `amount_note`, such as "amount set at go-live"). The frontend never shows 0 or blank for these and never computes a total across milestones or a sum of an amount and its change.
- Completion, invoice and paid are separate facts (INV-FACTS). `paid` is shown exactly as the backend returns it (`paid.status`, `owed`). The frontend does not infer paid from the invoice, and does not decide what `finance_tracks` means beyond the board's wording.
- Access is per record. The page shows only the rows and fields the backend returns. A 403 or 404 shows the standard no-access state with no stage names, milestone names or titles. A row opens its work item only when it has a `work_id`, and that page enforces its own access. Restricted evidence is not opened from here.
- Nothing is derived from `/me` beyond what is already allowed: whether the person sees the Projects destination, as F-07 does. No role-based column, control or tab is inferred. The frontend adds no capability the response does not carry.
- Text the backend composes is shown as given: `state`, `amount_note`, owner `role`, and the "recorded by PM" and "outside party" marks. The frontend does not recolour or reinterpret states from the text. If the boards need a colour per state, use a `state_key` proposal (below).
- The frontend invents no columns the boards do not show. The Changes, Emergencies and RFPs sub-tabs use the same row shape and the Issues columns, as G-SCR11-2 states. The builder records a design question if a sub-tab's columns look wrong, and does not guess.
- The "Mark milestone N complete" button, the "Filter" control (SCR-11 and SCR-29), the invoice cell's human status text and the "Changing an owner or due date is recorded with your name" sentence depend on contract items that do not exist (below). Render a control only when the data carries what it needs. Otherwise omit it and record a fidelity exception for the design-engineer sign-off, as D-99 and D-100 did. Never invent a permission, status text or edit.
- The footer rule on SCR-11 ("Severity is set by the PM. Closing an issue needs QA and the PM; there is no separate approval.") is static copy that restates a source rule. Keep it as drawn and list it in build.md for the backend developer to confirm.
- Nothing is sent, started or recorded from these tabs. Starting the invoice or marking a milestone complete is FE-MILESTONE-COMPLETE. Opening a row links to the line workspace pages (SCR-30 issue, SCR-31 change). If those routes do not exist yet, the link goes to the generic `/work/[id]` page.

**Out:**
- Money tab and `E-REPORT` drill-down (F-26).
- The Documents tab content (no approved list board; its row shape is an engineering proposal in D-PROJECT-TAB-ROWS). Keep the current panel.
- SCR-19 milestone completion, SCR-08 document review, SCR-30 and SCR-31 detail pages.
- Backend, OpenAPI, `schema.d.ts` regeneration and `architecture/**`. Record gaps as contract proposals in build.md. Do not extend the contract locally.
- Changes to `src/shell/**` and the Journey tab.

## Contract proposals
To record in build.md for the backend developer, all additive and optional (from delivery/backend-handoff/gaps-a-project-setup.md, SCR-11, SCR-29 and SCR-38 sections). None blocks F-25.
- G-SCR38-1: `milestones[].invoice.status_label`, so the cell can say "awaiting Finance decision" and not only an enum. Until then the cell shows `invoice.reference` with `invoice.title` or `state` as given.
- G-SCR38-2 and G-SCR19-2: `milestones[].milestone_id`, `reference`, `can_complete` and `cannot_complete_reason`, so the "Mark milestone 3 complete" button is backend-decided. Until then the button is omitted and listed as a fidelity exception. FE-MILESTONE-COMPLETE builds it.
- G-SCR38-3: `contract_amount_note` or `changes[].amount_note` ("Unknown until a SOW amendment with it is signed"), so the frontend does not decide when an amendment exists.
- G-SCR11-1 and G-SCR29-1: `severity`, `state` and `owner` filters, with options returned as `filters:[{key, options}]`. Search alone satisfies the screens if the "Filter" control is dropped.
- G-SCR11-2: confirm the same row shape for Changes, Emergencies and RFPs, and ask design for their columns.
- A `state_key` enum on register and action rows if the boards colour states (register `state` is display text only).
- G-SCR29-2: the board sentence implies an owner or due-date edit that is not drawn and has no operation. Ask design to keep or drop it.
- Questions for the backend developer: whether `age_seconds` is computed at response time, what `paid.status` the board's "—" maps to, and that the money and tab reads hide figures and names on a 403 or 404.

## Risk
Medium. The work is three read-only tab panels on a proposed v7 contract (D-PROJECT-TAB-ROWS) that the backend may change, reusing shared components and `features/projects`. It shows money (contract and change amounts, paid and owed), so Unknown handling and the separation of completion, invoice and payment must be exact (INV-UNKNOWN, INV-FACTS). It stays at medium and not high because there are no writes, no sends, no migrations and nothing is released. SURFACES: ui (8 boards), api (`E-PROJECT-TAB` typed arrays and `E-PROJECT` counts), contract-change (D-PROJECT-TAB-ROWS is a proposal and the gaps above), product-decision (the drawn controls that need a contract answer: complete, filter, owner edit). PRODUCT-ACCEPTANCE is not-required, because the work conforms to the client-approved boards and adds no new flow, rule or copy. Any omitted control is a fidelity exception for the design engineer to sign, as in D-99 and D-100.

## Questions
None.
