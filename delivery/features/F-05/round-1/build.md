STATUS: READY
COMMIT: 9ee65d4d689c0101591a3f94a5146c72db9545bc
BUILDER: builder
LANE: full

## Summary
- Anyone whose `/me startable_lines` is not empty now sees Start work: a "+ Start work" split button with a "More ways to start" chevron in the top bar, and "+ Start" in the phone bar. Nothing is read from roles.
- E-LINES is read each time a button is pressed. The main button opens `default_line` directly (pm and finance_lead: the invoice). With no `default_line` (CEO), and from the chevron or "+ Start", "Choose a line" opens first. The drawer renders `intake[]` by kind and posts one E-WORK-START. A 201 goes to `/work/<work_id>`.
- One start per key. The key is made when the line drawer opens, and a double press sends one POST. A network failure, timeout (20 s) or 5xx locks the form, and only "Check again" resends it, with the same body and key. A 409 or 422 unlocks the form and the next press uses a new key. A 409 keeps every value and re-reads the case revision.
- The contract moved from v4 to v6 in one commit (856daff, exactly the 5 repoint files). The mock answers E-LINES, E-LINE-OPTIONS and E-WORK-START from `frontend/mock/start-work.mjs`, using fixtures for 8 lines and 4 personas (pm, finance_lead, ceo, none).
- Round 1, so there are no earlier findings.

## Changes
Commits on top of base 2443664: 856daff (repoint), 4881389 (mock), a87b2dd (drawer), b4a30d1 (shell mount), 9ee65d4 (browser checks).

Contract repoint (856daff, these 5 files only):
- `frontend/mock/server.mjs`: `OPENAPI_PATH` and the header comment now point at `packages/v6`.
- `frontend/package.json`: the `gen:api` path is now v6. Dependencies are unchanged.
- `frontend/src/api/schema.d.ts`: regenerated from v6 with `npm run gen:api`.
- `frontend/tests/api-schema-drift.test.ts`: the path and the test name now say v6.
- `frontend/src/api/client.ts`: the header comment now says v6.

Mock (4881389):
- `frontend/mock/start-work.mjs` (new):
  - It exports `START_OPERATIONS` and `createStartWorkMock(openapi)` → `{handle, reset, started}`.
  - E-LINES serves `lines.<persona>.json`.
  - E-LINE-OPTIONS checks the line (404), then the options field (404), then a dependent field with no parent (empty list). After that it filters by `_personas`, then `_parent`, then `q`, and pages by an `o:<offset>` cursor. The `_` keys are stripped before serving.
  - E-WORK-START runs these checks in order:
    1. Ajv against the v6 request schema: 422 naming the missing or extra property.
    2. The line is granted to the persona: otherwise 403.
    3. The idempotency key: the same canonical body returns the stored 201; a different body returns 409 `idempotency_key_reused`.
    4. The case is served to the persona: otherwise 404.
    5. The case revision: otherwise 409 `stale_revision`.
    6. The intake: 422 with `fields[]`, including the Harmattan `billing_contact` stand-in.
    7. Otherwise it records the start and answers 201 `W-14xx`.
- `frontend/mock/server.mjs`, all small, with the scenario and CSRF checks kept in their order:
  - the import and construction next to `validators`;
  - the 3 ids appended to `M1_OPERATIONS`;
  - `'ceo'` in `PERSONAS`;
  - the dispatch line;
  - `startWork.reset()` in `/__mock/reset`;
  - the persona comment.

  The fixtures loader line now also skips `START_OPERATIONS`. Without that it would try to read `fixtures/E-LINES.json`. This line is beyond the "one line each" list.
- Fixtures:
  - `frontend/mock/fixtures/start-work/lines.{pm,finance_lead,ceo,none}.json`.
  - `options/{project,milestone,meeting,issue,incident}.json`. These hold 26 projects: P-0126 Ojo Foods has no case, and P-0103 is Kora (ceo only). Milestone 4 carries a `disabled_reason`.
  - `frontend/mock/fixtures/work/W-1401.json` to `W-1408.json`.
  - `me.ceo.json` (new: Folake Bello, roles ["CEO"]).
  - `me.pm.json` and `me.finance_lead.json`: `startable_lines` now holds line keys, and finance_lead has `["invoice"]`.
- `frontend/tests/mock-contract.test.ts`:
  - the per-persona 200 loop skips `START_OPERATIONS`;
  - the persona assertion adds ceo;
  - the 501 example is now `E-EVIDENCE-UPLOAD`.
- `frontend/tests/start-work-mock.test.ts` (new).

Drawer (a87b2dd), all in `frontend/src/features/start-work/`:
- `StartWorkButton.tsx`: the `bar` and `phone` variants. Focus goes back to the opener after the drawer unmounts.
- `StartWorkDrawer.tsx`: reads E-LINES and chooses between the line and the chooser.
- `LineChooser.tsx`: the chooser.
- `LineForm.tsx`: the line drawer, its callouts and "What happens next".
- `IntakeField.tsx`: renders each field by kind.
- `RecordPicker.tsx`: a select-only combobox with a searchable listbox, 250 ms debounce, "Show more", disabled reasons, and loading, empty and error states.
- `DrawerFrame.tsx`: the dialog frame. It is a `psl-drawer` from 720px and a `psl-sheet` below. It portals to the body, traps focus, and closes on Esc and the scrim.
- `useStartWork.ts`: E-LINES, E-LINE-OPTIONS, and the start, key, 409, 422 and uncertain logic.
- `intake.ts`: pure. It builds the value shapes, resolves the case, works out dependents, and decides which kinds are shown.
- `labels.ts`: the start-button labels and the agent names.
- `types.ts`: types derived from `@/api/schema`.
- `start-work.css`: tokens and `psl-*` classes only.
- `frontend/tests/start-work.test.tsx` and `frontend/tests/start-work-intake.test.ts` (new).

Shell (b4a30d1). These are shared files that only F-05 edits:
- `src/shell/TopNav.tsx`: mounts `<StartWorkButton variant="bar">` in `shell-navend` when `me.startable_lines.length > 0`, and updates the comment.
- `src/shell/PhoneBar.tsx`: mounts `<StartWorkButton variant="phone">` under the same condition. It is not inside the `<header>`: it sits in a `span.sw-phoneslot.psl-on-dark` after the menu `<nav>`, drawn at the bar's right end, and the header gets the `sw-phonebar` class (padding for it). This is more than "mounting the button", for two reasons:
  - With "+ Start" inside the header, Tab went Menu → "+ Start" → the menu links. That broke disclosure focus order and the F-01 test `frame.spec.ts` "Menu button keyboard focus ring…".
  - With the slot, Tab goes Menu → its links → "+ Start".
- `tests/shell.test.tsx`: the line-127 test is replaced by:
  - pm, finance_lead and ceo see "Start work", "More ways to start" and the phone "Start", and E-LINES is not fetched on load;
  - `none` sees only "Menu";
  - a CEO with `startable_lines: []` sees no button;
  - finance_lead still has no bell or sign-out.

  No other existing test counted all buttons on an `AppShell` page; all of them still pass unchanged.
- From 720px up to 1080px the main part reads "+ Start". " work" is visually hidden but stays in the accessible name, matching the who-line role pattern, and the main part's padding is 10px there. Without this, `frame.spec.ts` "top bar at 720px fits" failed by 5px.

Browser checks (9ee65d4): `frontend/e2e/start-work.spec.ts` (new).

## Fixes
None (round 1).

## Acceptance criteria
1. [x] The contract is v6:
   - `grep -n "packages/v6" mock/server.mjs package.json tests/api-schema-drift.test.ts src/api/client.ts` shows all four files.
   - `npx vitest run tests/api-schema-drift.test.ts tests/mock-contract.test.ts` passes.
   - `git show --stat 856daff` lists exactly the 5 repoint files.
   - Every existing fixture passes mock-contract against v6, and so does the new ceo persona (E-ME and the work list).
2. [x] The button shows only when `startable_lines` is not empty:
   - `tests/shell.test.tsx` "%s, with startable lines, sees Start work in both bars" covers pm, finance_lead and ceo.
   - "persona none … only button is Menu".
   - "roles never decide it: a CEO with no startable lines sees no Start work".
3. [x] pm's main button opens the invoice drawer directly. `start-work.test.tsx` "pm: the main button opens the invoice drawer directly…" finds the dialog "Invoice preparation and delivery", no "Choose a line", no "change line", and Cancel.
4. [x] The CEO's main button opens the chooser:
   - `start-work.test.tsx` "ceo (no default_line)…" sees "Choose a line" and "LINES YOU CAN START · 8".
   - In the browser, `e2e/start-work.spec.ts` "ceo at /my-work sees the chooser from the main button" passes on http://localhost:3501/my-work with `psl_mock_persona=ceo`. The desktop and phone ceo tests pass too.
5. [x] The chooser groups, searches and offers only returned lines:
   - It shows the groups and subtitles.
   - "minutes" leaves 1 line, and "zzz" shows `No line matches "zzz".`
   - "Describe it to Tola" has `href="/assistant"`.
   - finance_lead sees exactly 1 line, and only lines E-LINES returned are offered.
6. [x] Chooser states: `start-work.test.tsx` "chooser states" covers loading `role=status` "Loading…", the empty message, a 500 with Try again (two E-LINES GETs), a 401 signed-out with `next=%2Fmy-work`, and a 403 message.
7. [x] Fields render by kind, in order:
   - "renders each kind in the order returned…" finds all 11 kinds in order: date, month and datetime-local inputs; help as the description; placeholder; "(optional)"; display as plain text.
   - `start-work-intake.test.ts` asserts the submitted shapes: `"2026-11-17"`, `{from,to}`, `"2026-11"`, ISO ending in `Z`, the number `3`, choice, record and records. The display field and blank fields are absent.
8. [x] Record options are narrowed by parent:
   - "Choose Project first" shows while the project is empty.
   - The GET is exactly `/api/v1/lines/invoice/fields/milestone/options?parent=P-0101&limit=20`.
   - Milestone 4 has `aria-disabled="true"`, shows its reason and can't be chosen.
   - Switching to Harmattan clears the milestone.
9. [x] Search and paging (ceo): the picker lists 20, "Show more" sends `cursor=o:20` and shows 26, and "harm" sends `q=harm` and leaves only Harmattan. Every request uses `limit=20`.
10. [x] The case comes from the chosen project or the fixed line:
    - The invoice sends `C-0101`/6.
    - The leadership report sends `C-PMO-REPORTING`/4 with no project field.
    - Ojo Foods shows "This project can’t be started on from here." and start stays disabled, with no POST.
    - `intake.ts` resolves a case only from the line or the chosen option (`start-work-intake.test.ts` "resolveCase").
11. [x] A valid start goes to the work item:
    - The component test sees `router.push('/work/W-1401')` and the dialog closed.
    - The browser test "pm starts an invoice on Lagoon and lands on W-1401…" checks the URL `/work/W-1401`, the title "Lagoon Health · Invoice preparation and delivery", `x-csrftoken: mock-csrf-pm`, and exactly the keys `line, case_id, case_revision, intake, idempotency_key`.
12. [x] A missing field shows the 422 inline:
    - "Completed milestone is required." appears under the milestone combobox, which has `aria-invalid="true"` and `aria-describedby`.
    - The callout reads "1 things to fix before Chidi can start." and has focus.
    - The eyebrow reads "1 things to fix".
    - The next press uses a new key.
    - On Harmattan, the callout lists the billing-contact message.
    - The same is checked in the browser at both widths.
13. [x] A double press or an uncertain result never starts twice:
    - Two clicks while the POST is pending send 1 POST.
    - After a network failure the fields are read-only, nothing is sent automatically, and "Check again" sends a 2nd POST with the identical body and key. The mock ends with `started.size === 1`.
    - After a 500 the fields are read-only. Check again on a start that did reach the mock goes to it and creates nothing new.
    - Mock tests: the same key and body give identical 201s with `started.size === 1`, and a different body returns 409 `idempotency_key_reused`.
14. [x] A 409 keeps what was typed and reloads the revision:
    - The note and choices are kept and the stale callout shows. The re-read is E-LINE-OPTIONS `project` with `q=<label>`. No second POST is sent until the person presses start, and that POST carries `case_revision: 7` and a new key.
    - When the project is no longer returned, it and the milestone are cleared, with "That choice is no longer available. Choose again."
    - A fixed case re-reads E-LINES, and if the line is gone it shows "You can no longer start this line." with no start button.
    - Mock: revision 5 returns 409 `stale_revision`.
15. [x] Wrong user, wrong record, no permission, in `start-work-mock.test.ts`:
    - finance_lead `weekly_report` → 403;
    - pm with Kora's `C-0103` → 404;
    - `none` `invoice/project` options → 404;
    - another persona's CSRF → 403 `csrf_failed`;
    - an extra `priority` → 422 naming it.

    In the component test, a 403 shows "You can’t start this here. Your role does not allow this." and keeps the values.
16. [x] Out-of-scope kinds are not invented:
    - Optional `money` and `evidence` fields are not rendered or sent.
    - A required `evidence` field, `start_via: "finance_import"` or no `case_scope` each show "You can’t start this line from here yet." with the Tola link, and the only buttons are Close and Cancel.
17. [x] All 8 drawers, minus proof:
    - The browser test "each of the 8 drawers shows its fields and start label, with no Proof field" passes at 1440 and 390, checking the fixture-table labels in order, the `labels.ts` primary label, and no "Proof".
    - I compared screenshots of the invoice drawer, the chooser and the validation state at both widths against SCR-04-desktop/-lines/-validation and SCR-04-mobile/-validation.
    - I did not compare the other 7 boards pixel by pixel. Differences from the boards are listed under Notes for product acceptance.
18. [x] Accessibility at 390px and 1440px: `E2E_PORT=3501 MOCK_PORT=3502 npx playwright test e2e/start-work.spec.ts` passes 10/10.
    - axe (WCAG 2.2 AA tags) finds 0 violations on the pm chooser, the invoice drawer, the invoice validation state and the ceo chooser, at both widths.
    - Esc closes and focus returns to the opener.
    - Tab ×12 stays inside the dialog.
    - At 390px the sheet is x=0 and 390 wide, and "+ Start" is in the phone bar, 44px tall, 16px from its right edge.
    - axe in jsdom also passes for an every-kind drawer and an open picker.
19. [x] Mock fixtures match v6. `start-work-mock.test.ts` validates every E-LINES per persona, and every E-LINE-OPTIONS page (every line × field × persona × parent, all pages; more than 50 pages). It also validates the E-WORK-START 201, 403, 404, 409 and 422 bodies, and W-1401 to W-1408 against E-WORK-ITEM. Each persona's `startable_lines` equals its E-LINES keys.
20. [x] Nothing protected or unowned changes. `git diff --name-only 2443664...HEAD` lists only the files above, with nothing under `delivery/`, `architecture/`, `apps/`, `frontend/src/styles/`, `features/work-item/`, `W-1[0-2]*`, or the E-PROJECT, exceptions or overview files. `package.json` dependencies are unchanged.

## Validation
- `cd /Users/Hunchoo/psl-factory-worktrees/f-05 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh` exits 0:
  - django check;
  - `npm ci`, lint (0 warnings) and typecheck;
  - vitest 16 files / 419 tests passed;
  - `next build` compiled.
- `cd frontend && E2E_PORT=3501 MOCK_PORT=3502 npm run test:e2e`: 93 passed.
  - One earlier run had a single failure in `decide.spec.ts` "at 390 Approve is the 54px action-blue phone footer button". It read the colour mid-transition (rgb(78,119,210)). This is a known flake that fails on base too, and another lane has a test-only fix pending. The rerun passed 93/93.
  - Earlier runs caught two real regressions in `frame.spec.ts`, which I fixed above: the 720px top-bar fit and the phone Menu focus order.
- `npx vitest run tests/start-work.test.tsx` passed 3 times in a row (37/37).
- Everything ran on the contract mock: the evidence is mock results only, with no real API.
- `frontend/test-results` is deleted. The ports 3501 and 3502 had only Playwright's own servers, which stopped afterwards.

## Notes
- Question for the backend developer (PMO-0-1): E-WORK-START does not say what a replayed `idempotency_key` returns. The mock returns the stored 201 for the same key and the same canonical body, and 409 `idempotency_key_reused` ("This start was already sent with different details. Close the form and start again.") for a different body. Please confirm or define this for T-START. A `start_label` field could also replace `labels.ts` later.
- Key policy choices within PMO-0-2:
  - A 403 or 404 keeps the key; only a 409 or 422 makes a new one.
  - A 409 `idempotency_key_reused` shows its message in a problem callout and makes a new key.
  - A CSRF token missing before sending shows signed out and sends nothing.
- Copy that has no board, for product acceptance:
  - "You can’t start this line from here yet. Describe it to Tola and she’ll help you start it." (PMO-0-6)
  - "You can’t start this here." followed by the server message (403/404)
  - "This project changed since you opened the form. We’ve loaded the latest version; check your entries and press start again." (and "This record changed…" for a fixed case)
  - "We couldn’t confirm the start. Check again: if it already started you’ll go straight to it, and nothing starts twice." plus "If it started, it will appear in My work."
  - "You can no longer start this line."
  - "That choice is no longer available. Choose again."
  - "This project can’t be started on from here."
  - "We couldn’t load these options." and "Nothing to choose from."
- UI choices against the boards:
  - The UI copy uses the codebase's curly apostrophe (’), as in "You’re signed out." The mock's server messages keep the spec's straight apostrophe.
  - The validation eyebrow replaces "START WORK" with "<n> things to fix" (the spec). The board shows it as the subline.
  - The drawer title is the line `title`, so it is longer than some board titles ("Weekly client report").
  - "What happens next" lists the parts separately.
  - Back in a line drawer opened from the chooser returns to the chooser.
  - Minutes and change have no Proof field.
  - On the phone, the brand now sits next to "+ Start" at the right.
- Sample data: W-14xx titles are fixed per line, for example "Lagoon Health · …" even when started on Harmattan. Project names P-0103 to P-0125 are sample names. "Owerri Medics" replaced a name containing "harm", so `q=harm` stays unique.
- A `round-1/fe-m2a-start-work-pick-a-line-fill-its-intake-i` folder was already in the feature folder before this round. I did not touch it.
- No AI attribution in commits, per the user's rule. I did not force-push, open a PR or deploy.

## Blocked
