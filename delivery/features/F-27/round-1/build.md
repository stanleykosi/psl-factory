STATUS: READY
COMMIT: ab5a4f0f8046ab431cd183345b6e98f8012369ca
BUILDER: builder
LANE: full

## Summary
- Setup > Delegation (`/setup/delegation`) no longer shows the reserved "comes next" page. It now lists what E-DELEGATIONS returns: a desktop table (FROM, TO, DATES, REASON, STATE) and phone cards. A missing end date shows "Unknown". The status word comes only from the returned `status`.
- Adding a delegation: the desktop "Add a delegation" panel and, on phones, the shared sheet (D-103) use one form. From, To and Authority come only from `from_options[]`, `delegate_options[]` and `authorities[]`, with nothing chosen in advance and no free text. Values are checked against the lists again on submit. The form sends one PUT with CSRF and `expected_revision` as read, then re-reads the list.
- Every outcome is covered. 422 messages show beside their fields. 409 re-reads and keeps the entries. 401 shows the signed-out state. 403/404 show the backend's message and re-read. An uncertain write is never shown as "added": the list is re-read once. If the revision is unchanged it says "It was not added". If it moved, Add stays blocked until "Start again". If the re-read fails, Add is locked and "Try again" only reads the list.
- The add controls appear only when the list says `can_add: true` and returns a `revision`. Nothing reads `/me` roles or the persona.
- New contract mock `frontend/mock/delegations.mjs` with 7 scenarios and 4 save outcomes. The overlay schemas are in `proposals/setup.json`. This is a contract mock only: nothing is released and no delegation takes effect.

## Changes
Base merge: the coordinator merged dlv-00 into the branch (ab5a4f0f). `git diff --stat ff0e8a55 ab5a4f0f -- frontend` is empty (delivery records only), so the build and test evidence below, taken at ff0e8a55, still applies.

- `frontend/src/features/setup/DelegationView.tsx` (new): the page, desktop table and add panel, phone cards with a fixed bottom "Add delegation" bar and the Drawer sheet. Also: outcome handling (success announcement and focus on the new row, stale, rejected, unconfirmed and unchecked), and Try again / Start again.
- `frontend/src/features/setup/DelegationForm.tsx` (new): the one form. From is "You", or one option as text, or a Select. To is paired by `for_person_id` (exact key match) or the whole list. Authority is absent, one line, or a required Select. Dates is a fieldset of two DateFields; Reason is a TextField. Checks are format only. The board's hint and note are shown as drawn.
- `frontend/src/features/setup/useDelegations.ts`, `useDelegationAdd.ts` (new): first page, Show more and refresh. One write at a time (a ref checked synchronously, shared by the panel and the sheet), with outcome kinds as in F-20.
- `frontend/src/features/setup/api.ts`: `readDelegations`, `addDelegation` (keeps 422 `fields[]`). Additive only.
- `frontend/src/features/setup/contract-proposal.ts`: the delegation overlay types beside the v7 types.
- `frontend/src/features/setup/format.ts`: `boardDate`, `dateRange` ("18–25 Nov 2026", "28 Nov – 03 Dec 2026", "28 Dec 2026 – 03 Jan 2027").
- `frontend/src/features/setup/setup.css`: additive `setup-deleg*` rules plus the board's column widths for `.setup-table--deleg`. Tokens only.
- `frontend/src/app/setup/delegation/page.tsx`: renders `DelegationPageView`. `ReservedTab.tsx` is unchanged and is still used by Roles, Costing rule, Payroll visibility and Staff accounts.
- `frontend/mock/delegations.mjs` (new): scenario cookie `psl_mock_delegations` (or `MOCK_DELEGATIONS_SCENARIO`) and save cookie `psl_mock_delegations_save`. Checks run in the spec's order, and the body is validated with Ajv against the overlay `delegation_body`. Status is worked out from the mock clock (2026-11-16) for new rows only. State is held in memory per persona:scenario and cleared by `/__mock/reset`. It also has `contractDelegations` / `contractDelegation` strippers.
- `frontend/mock/fixtures/delegations/{default,empty,readonly,many,authority,single}.json` (new, sample names only), plus placeholder `fixtures/E-DELEGATIONS.json` / `E-DELEGATION.json`, which `server.mjs` loads for every M1 operation, as for E-TEMPLATES.
- `frontend/mock/server.mjs`: kept minimal (6 lines). One import, the two ids in `M1_OPERATIONS`, `resetDelegations()` in `/__mock/reset`, one route line and one header comment line.
- `frontend/mock/proposals/setup.json`: adds the `delegations_response` and `delegation_body` keys. Existing keys are unchanged.
- Tests: `frontend/tests/setup-delegation.test.tsx` (30), `frontend/tests/setup-delegation-mock.test.ts` (11), `frontend/tests/mock-contract.test.ts` (new entries only: body, persona 403s, contract strippers), `frontend/e2e/setup-delegation.spec.ts` (9).
- `frontend/e2e/setup.spec.ts`: removes Delegation from `RESERVED`, because it is no longer a reserved tab. F-20 did the same for Templates (d97566b6). The other four reserved tabs are still asserted.
- Factory files: `delivery/features/F-27/fidelity-exceptions.json`, `round-1/fidelity/` (`drive-states.mjs`, `serve-frozen.mjs`, `run.sh`, `frozen/`, reports, `scores.txt`).

## Fixes
None (round 1).

## Acceptance criteria
1. [ ] Both boards pass: **phone passes, desktop does not.** `SCR-13-mobile-delegation` @390: coverage 80, 100 with exceptions, visual 98.6, PASS. `SCR-13-desktop-delegation` @1440: coverage 83.3, 100 with exceptions, **visual 84.0, FAIL (under 90)**. Waiver proposed below, pending the design engineer.
2. [x] Exceptions limited: 10 entries, each with role, name, category, reason and approved_by, and each mapped to a Conflicts number (listed below). No entry covers a list value: the table and card names, roles, dates, reasons and statuses are all matched on the page. Three entries name values the driver put into the form controls (From and To Select values, and the Reason value). Their reasons explain that the value is on the page inside the shared control. One official run this round. Before it, one calibration run with an empty exceptions file went to scratch, outside the round folder, to see what the tool lists.
3. [x] List from data: component tests "desktop: FROM, TO…" and "a missing end is Unknown…" (a past-dated `scheduled` row shows Upcoming; no role or reason means nothing is drawn). e2e desktop rows and phone cards at 1440 and 390.
4. [x] Add control only on `can_add: true`: component test covers readonly, `can_add: false` and a missing revision (no panel, no button, no note). Personas admin, finance_lead and ceo give the same controls. The `grep -n "roles"` over `Delegation*.tsx` and `useDelegation*.ts` finds only three comment lines and no read of `/me` roles.
5. [x] No list of its own: a test shows the options are in backend order with none selected. An option planted in the DOM listbox can't be chosen and sends no PUT. A delegate dropped by the next read is not sent. The `grep -nE "PMO Lead|Finance Lead|Admin|Kemi|Femi|Ada|Chika"` over the Delegation files finds nothing.
6. [x] From follows `from_options`: tests for `single` ("You", no `from_person_id`), `authority` (one option as text) and `default` (Select; `from_person_id: P-KEMI` sent).
7. [x] To pairing: test shows To disabled with "Choose who is delegating first." Ada gives only Chika and Kemi gives only Femi, and changing From clears To. `single` lists every option.
8. [x] Authority: `default` has no field and no key. `single` shows the line "Authority: Approve milestones" and sends the value. `authority` has a required Select with no default. Rows show the label, or the raw value (`close_month`) when it is not in the list.
9. [x] Write request: exact body equality in component tests and the e2e (`{expected_revision: 2, from_person_id, delegate, starts, ends, reason}`), with `X-CSRFToken: mock-csrf-admin`. A double click sends 1 PUT. A blank reason is left out and a reason is trimmed. The mock test shows the body validates against the overlay `delegation_body`; `idempotency_key` and unknown keys give 422.
10. [x] Format checks only: missing To, an unparseable date and Ends before Starts each show under the field and send nothing. A 2020 Starts is sent as is.
11. [x] Success re-reads: GET count 2, the new row comes from the re-read, the announcement reads "Delegation added: Kemi Adebayo to Femi Ade, 01–03 Dec 2026.", focus lands on the new row (`<tr>` / phone card), and the form clears. Without `delegation_id`, focus goes to the list heading. A 200 naming an unlisted id draws nothing (component + e2e).
12. [x] 422: the top message, "under To" and "under Ends" messages (checked via the accessible description in e2e), focus on To, entries kept, no re-read. Covered by component tests and e2e at 1440 and in the phone sheet.
13. [x] 409: re-read, the stale sentence, entries kept, the next press sends `expected_revision: 4`. With fake timers at 60 s there is still only one PUT.
14. [x] Uncertain: `uncertain` gives "It was not added. You can add it again.", Add enabled, and the mock still at revision 2 with 2 rows. `uncertain_written` gives the new row listed, the warning, Add disabled with its reason, the mock holding 3 rows, and "Start again" empties and frees the form. With the re-read failing, Add is locked and Try again reads only (no PUT), then settles. A network throw is treated as uncertain too.
15. [x] Access: 401 on read and on write lead to "Sign in" with `next=%2Fsetup%2Fdelegation`. 403/404 on read show the not-open view with no names and one call. 403/404 on the PUT show the message and a re-read. `/me` without setup makes zero delegation calls (component + e2e for pm).
16. [x] No claimed effect: the effect-words grep finds nothing. A component test checks `document.body.textContent` after a success, minus the board's hint and note, has no "can now / granted / approve / in force / agent". The page has no agent.
17. [x] Phone add form: e2e at 390 shows the sheet "Add a delegation" with the same fields and note, 44px buttons, axe clean. Escape and Cancel return focus to the button. A 422 shows inside the sheet; after success the sheet closes and focus moves to the new card. **Note:** I used the shared `Drawer`, which is a full-height sheet below 720px, as the spec recommends. D-103 says "shared bottom sheet"; if `BottomSheet` was meant, it is a one-line swap.
18. [x] Paging: component test shows 20 rows, then a failed page keeps the 20 rows with the problem callout, then 40, then 45 and "All 45 delegations are shown." The mock test shows pages of 20, 20 and 5.
19. [x] Accessibility: e2e runs axe (the five tag sets) at 1440 and 390 on default, filled form, 422, uncertain warning, empty, readonly, forbidden and the open sheet, with no violations. Also checked: no sideways scroll at 390, a visible focus outline, 44px phone targets, the fieldset legend "Dates", and with reduced motion every transition is 0s.
20. [x] Tokens and components only: no `#hex`, `rgb(` or `hsl(` in the CSS diff. Uses Select, DateField, TextField, Panel, Button, Callout, Tag, Unknown, EmptyState, Drawer, Table, VisuallyHidden and PageTitle from `@/components`, with no local copies.
21. [x] Mock matches the contract: `npx vitest run tests/setup-delegation*.test.* tests/mock-contract.test.ts` gives 3 files and 316 tests passed. One check-order step is not exercised: `no can_add → 403`. The `readonly` fixture has no options, as the spec asks, so its add is refused earlier at the From check.
22. [x] Contract not extended: the `git diff --stat 7ec99296` shows nothing under `src/api/**`, `apps/**`, `architecture/**`, `design/**` or protected paths, and no existing fixture changed (only new fixtures). The proposals are listed below.
23. [x] Existing behaviour kept: `delivery/checks.sh` passes (85 files, 1865 tests). e2e `setup-delegation`, `setup` and `setup-templates` give 37 passed. The only change to an existing assertion is that Delegation is no longer in `RESERVED`.
24. [x] build.md evidence: this file.

## Validation
- `bash /Users/Hunchoo/psl-factory/delivery/checks.sh` run in the worktree: exit 0. Django check passed; then npm ci, lint (0 warnings), typecheck, vitest (85 files, 1865 tests passed) and next build all passed.
- `cd frontend && E2E_PORT=4801 MOCK_PORT=4802 npx playwright test e2e/setup-delegation.spec.ts e2e/setup.spec.ts e2e/setup-templates.spec.ts`: **37 passed (2.0m)**. The setup-delegation tests:
  - desktop: frame/rows/panel axe; add (one PUT, CSRF, body, re-read row, announcement, focus); 422; uncertain and uncertain_written with the mock state read back; readonly/empty/forbidden/pm
  - desktop with reduced motion: nothing animates
  - phone: cards/44px/no side scroll/axe; sheet Escape/Cancel/422/success; uncertain warning, empty, readonly and not-open axe
- `npx vitest run tests/setup-delegation*.test.* tests/mock-contract.test.ts`: 316 passed.
- Mutation check: forcing the uncertain branch always to "not added" fails the "revision moved" component test (1 failed out of 30); restored afterwards.
- Fidelity: production build (`API_ORIGIN=http://127.0.0.1:4802 next build`, `next start -p 4801`), mock on 4802 with `MOCK_DELEGATIONS_SCENARIO=default`, desktop frozen by `round-1/fidelity/drive-states.mjs` and served on 4803. Run with `round-1/fidelity/run.sh`. Scores (`round-1/fidelity/scores.txt`):
  - SCR-13-desktop-delegation @1440: coverage 83.3, 100 with exceptions, visual 84.0, pass False (visual only)
  - SCR-13-mobile-delegation @390: coverage 80, 100 with exceptions, visual 98.6, pass True
- `frontend/test-results` deleted; servers on 4801/4802/4803 stopped by PID. Disk: 6.2 GB free at the end.

### Desktop visual 84.0: proposed waiver (pending the design engineer)
What the diff shows is not fixable on this page within the spec:
- The shared Setup frame: no Start work in the top bar for the admin persona, "Ada Okafor · Admin" in place of "Admin · sample", and the tab badges "Roles 2" / "Rules 8" not shown (Conflicts 8), which shifts every tab. The title also renders slightly narrower than the board.
- The panel head is ink, not the board's action blue. That is the shared `Panel`, as F-11's Set a rule panel became in the shared-component move (043c8f30).
- Dates is two fields (Conflicts 5), not one, so everything below it in the panel moves down by about 80px. The page is 967px tall against the board's 900px.

I measured two variants on a copy of the frozen page; neither was adopted:
- action-blue panel head: 86.3
- the two dates side by side: 84.8, and it widens the aside past the board's 320px and clips "18 Nov 2026" in the shared DateField

None reaches 90. I'm asking for a D-83-style waiver at 84.0 for SCR-13-desktop-delegation. If the design engineer wants the blue head back, that is a Setup-wide call covering the Rules panel too.

### Exceptions (`delivery/features/F-27/fidelity-exceptions.json`), all "builder proposal, pending design engineer"
- Conflicts 9, frame: "Start work", "More ways to start", "Admin · sample" (desktop); "← Setup", "Start" (phone).
- Conflicts 2, component: "Kemi Adebayo · PMO Lead ▾", the From Select's value (the tool reads the control by its label "From").
- Conflicts 3, component: "Femi Ade · PMO Lead ▾", the To Select's value.
- Conflicts 5, component: "18 Nov – 25 Nov 2026", shown as two DateFields (Starts/Ends).
- Conflicts 5, component: "Reason" (the TextField `<label>`, which the tool skips) and "Annual leave" (the Reason field's typed value; the table row's "Annual leave" is matched).
- D-103 (Conflicts 1 and 4, approved "design engineer, 16 Nov 2026 — D-103"): the phone sheet and the two board sentences need no entry. The tool does not flag the sheet (it is on no board), and both sentences are matched on the page.

### Contract proposals, mock overlay only (for the backend developer; none confirmed)
- G-SCR13A-1: `from_options[] {person_id, name, role?}` on E-DELEGATIONS, `from_person_id` on E-DELEGATION, and `person_id` on rows' `from` and `delegate`.
- G-SCR13A-2: `delegate_options[].for_person_id`.
- G-SCR13A-4: E-DELEGATION 200 returns `delegation_id`.
- Proposed in readiness: list-level `can_add` (absent means no add control).
- `expected_revision` minimum 0 on a first delegation (v7 says minimum 1).
- 422 `fields[{name, message}]` (v7's 422 is `{code, message}` only).
- Conflicts 4 option B, not built: `delegate_hint` / `note` sent by the backend.
- Backend rules to confirm: G-SCR13A-5 (the authority ceiling; a delegate may not approve an item they prepared). Open questions: project-scoped delegation; what happens to claimed tasks when a delegation ends.
- Not built: G-SCR13A-3 (end or cancel; no per-row control even with `can_change: true`), G-SCR13A-6 (tab counts).
- E-DELEGATIONS and E-DELEGATION are unimplemented in the backend.

### Held items and D-DELEGATION-VIEW limits (for the PR description)
- This is a contract mock only and nothing is released. D05 and D-ADMIN-AUTHORITY are open, and D-DELEGATION-VIEW is a proposal. The screen records and lists; it does not claim a working delegation, enforcement of the authority ceiling, or the self-approval rule.
- The two board sentences are shown as drawn (D-103), the frontend enforces neither, and their wording is a product acceptance check (PA-2).

### Notes for the coordinator
- The session scratchpad is shared with the parallel F-25/F-26 builders, and my early helper files there (`shot.mjs`, `next.pid`) were overwritten. Before I noticed, one `kill $(cat next.pid)` read a pid file that may have been rewritten by another builder. The process it named was a `next-server`; I could not tell afterwards whose it was. From then on I used `scratchpad/f27/` and stopped servers only by the PID listening on my own ports, after checking that its working directory was my worktree.
- `server.mjs`, `proposals/setup.json` and `api.ts` are also touched by F-25/F-26. My changes there are additive.

## Blocked
None.
