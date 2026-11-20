STATUS: READY
COMMIT: 6c71129e2ae29ff81d641b6061542bb2a1db882e
BUILDER: builder
LANE: full

## Summary
- Work now happens in the ONE shared worktree /Users/Hunchoo/psl-factory-worktrees/f-54 on fe-paging-consistency-table-footer (D-145). F-55's branch (HR stand-in sample data) was merged here by the coordinator, along with F-54 round 2 (shared paging from 10, blue-border focus).
- F-55 round 1 is finished here: the 3 failing hr e2e checks are fixed (real next-step text, real refusal wording "This section isn't open to your role." for Projects and Setup and "This list is for Leads" for Exceptions, history counted in the table).
- New stand-in persona hr_lead, "HR Lead" (D-147): Ngozi Adeyemi, destinations my_work and assistant, starts hr_staff_list, Zainab only. It decides: W-4605 (payroll correction) is Needs me, plus W-4612 (approve a staff record change) and W-4613 (confirm 4 business unit moves before payroll matching); 2 Waiting rows (W-4614, W-4615) and 2 Done rows (W-4616, W-4617); each has an item page and a 6-entry history with one Restricted entry.
- 4 alerts (N-0311 to N-0314) and 3 Zainab conversations (CV-2431 to CV-2433, one declines a salary). Exceptions refused (403); Projects and Setup are not in its destinations. No salary or payroll amount anywhere.
- NOT yet run: the hr_lead e2e. The mock on 4951 was started before hr_lead existed, so it needs a restart (see Validation).

## Changes
- mock/fixtures: me.hr_lead.json, start-work/lines.hr_lead.json, alerts/notifications.hr_lead.json, assistant/CV-2431..2433 and index.json, work/W-4612..W-4617 (+ .history), E-WORK-LIST.rows.json (hr_lead rows incl. W-4605 as Needs me).
- W-4605: the base item is now actionable for the HR Lead; W-4605.hr.json is hr's read-only copy.
- mock/server.mjs: hr_lead in PERSONAS; E-WORK-ITEM serves <id>.<persona>.json when present (used only for W-4605.hr). mock/start-work.mjs, exceptions.mjs, assistant.mjs, alerts.mjs: hr_lead handled like hr (alerts read its own file, preferences stay the empty persona's).
- Tests: hr-mock.test.ts (5 new hr_lead tests), mock-contract.test.ts (hr_lead notification id, Exceptions 403, /me row), mock-work-list.test.ts (payroll-named lines only for hr personas), assistant-mock.test.ts (fixture ids); e2e/hr.spec.ts fixed, plus an "HR Lead (stand-in)" block of 2 tests.
- Shared code touched: only the persona list and the per-persona item lookup in mock/server.mjs; no components or CSS.

## Fixes
- F-55 e2e next-step text, refusal wording and history count | see commits "F-55: hr e2e uses the real next-step text..." and "hr e2e: History rows counted in the table..."

## Acceptance criteria
1. [x] hr queues: e2e passed (8 tests) against 4951/4952.
2. [x] hr item pages and history: e2e passed for W-4601 and W-4605; hr-mock.test.ts covers all 10 rows.
3. [x] hr alerts, bell: e2e passed.
4. [x] hr Assistant: e2e passed (open threads, salary declined, new message reply).
5. [x] hr start: e2e passed, lands on W-4611.
6. [x] hr refused Projects, Exceptions, Setup: e2e passed.
7. [~] hr_lead: mock tests passed (queues, history, alerts, conversations, line, Exceptions 403, other personas unaffected); browser e2e written, not run.

## Validation
- npm run lint: passed. npm run typecheck: passed.
- Full vitest: 141 files, 3486 tests passed (includes the three edited tests and hr-mock.test.ts).
- e2e/hr.spec.ts against 4951/4952 (excluding the HR Lead block): 8 passed.
- NOT run: the 2 HR Lead e2e tests, because the live mock on 4951 does not know hr_lead yet. Coordinator: restart the mock on 4951 from this worktree, then run MOCK_PORT=4951 npx playwright test -c /private/tmp/claude-501/-Users-Hunchoo-psl-factory/a6d3a226-b687-417b-9a09-758687eb3f8d/scratchpad/pw.config.cjs hr.spec.ts (config points at 4952).
- Not run: checks.sh (npm ci and build; gate does it).

## Blocked
Nothing blocks the code. The hr_lead e2e needs the mock reloaded (I may not kill the process on 4951, and I had no way to message you from here).

## D-150 CEO data
Commit b946c1ee4ad748137aa595eab210111cb9f8c93f (branch fe-paging-consistency-table-footer). Sample data only; no new authority rules.
- My work: ceo has 5 Needs me (W-5001 Kora Logistics SOW v3, W-5002 Harbour Bank costing, W-5003 Harmattan emergency change, W-5004 Lagoon escalation, W-5005 November leadership report), 5 Waiting on others (W-5006 to W-5010) and 4 Done (W-5011 to W-5014). Each has an item page and a History of 5 to 7 entries. The first three decisions show the CEO at the last step of the chain with you_can_act true; the emergency change cost is unknown (never zero); W-5006 waits on the PMO Lead (CEO is the next step, cannot act yet). No payment-exception row.
- New ids W-50xx instead of a persona variant of W-1122/W-1302: a variant of those ids would have needed new History files and so changed what finance_lead and pm see. Kora SOW v3 keeps its title and reference PLN-0050.
- Projects: ceo added to all 24 rows of projects/list.json, so the list, journeys, tabs, documents and money follow finance_lead (22 active, 2 closed). pmo_lead sees no projects in the mock today, so there was nothing to mirror; left unchanged.
- Overview: E-OVERVIEW already serves its populated sample to every persona; no change, now covered by a test.
- Alerts: notifications.ceo.json, 6 alerts (4 unread) that open W-5001, W-5003, W-5004, W-5005, W-5002, W-5011. alerts.mjs reads the ceo file.
- Assistant: CV-2441 to CV-2445 (Tola x3, Chidi, Zainab declining pay). A new message from ceo gets a CEO answer (assistant.mjs).
- Tests: tests/ceo-mock.test.ts (16), e2e/ceo.spec.ts (7). Changed because ceo now sees every project and has conversations: mock-contract (ceo notification id N-0401), support-handover-mock and mock-document-review (hidden persona hr instead of ceo), assistant-mock and assistant.test.tsx (ceo list five; empty list uses admin).
- Validation: npm run lint and typecheck passed. Full vitest: first run 3 failures in assistant tests and a mock-contract history check (missing as_of), all fixed; the changed files rerun green (mock-contract + ceo-mock 408 tests, assistant tests 107). A second complete run was not repeated after the final fixes. e2e/ceo.spec.ts: 7 passed against the 4952 app with a second mock on 4961 carrying the new code (browser requests re-routed to it; temp copy deleted). Not yet run against 4951: the live mock must be restarted from this worktree first.
- Shared bug to fix once: none found.

## D-151 toasts
Commits 1fb42338 (ceo e2e), 8a58ec70 (host, replacements, tests), aebb3517 (test fixes), branch fe-paging-consistency-table-footer. The mock was NOT changed by me.

### Step 0: e2e/ceo.spec.ts:33
Cause: the test, not the data. It clicked the Kora row right after `goto`, before the dev page was hydrated, so the click was sometimes lost (URL stayed /my-work; 1 in 3 runs failed). Fix: `waitForLoadState('networkidle')` before the click. 6 repeats pass; the whole file passes (7).

### The host
- `ToastProvider` (in `AppShell`, wraps the whole shell so it survives route changes), `useToast().show(message, {action, kind, dismissible})` and `useToastWhen(text, label?)` (for pages that keep an action result in state), all exported from `@/components` (frontend/src/components/Toast.tsx). `Toast` no longer draws its own fixed wrapper; the host does.
- Bottom centre on desktop (measured: x 595 to 845 at 1440). On phones full width inside 16px gutters (x 16, width 358 at 390) and lifted above any fixed or sticky bar at the bottom: measured toast bottom 742 against the alert settings Save bar top 758, a 16px gap. The lift is measured on appearance, on resize and every 400 ms while a toast shows on a phone.
- Newest at the bottom, 3 max (oldest drops), never takes focus, each toast is its own status/alert region written a moment after it is drawn, 6 s hold on hover or focus. The host element only exists while a toast shows.
- Docs: design/system/project/components/Toast/README.md ("The host") and frontend/src/components/README.md ("Toasts").
- Test setup (frontend/tests/setup.ts) now wraps every RTL `render`/`renderHook` in `ToastProvider`, like the app shell, so a test reads a toast as a person does.

### Replaced by a toast (wording kept)
1. clients/BillingContactForm: "Billing contact saved." (the "Saved. We couldn't refresh" warning stays).
2. alerts/AlertSettingsPage: "Your alert settings are saved."
3. my-work/MyWork: "TL-RFP-2026-014 is now with <name>." (assign from My work; the "sent but couldn't refresh" warning stays).
4. workspace/Workspace, four success callouts: team input recorded, assign done, decision settled, step done or queued (with its bold step label).
5. documents/DocumentReview: "You approved v2 · name · time. Not sent to the client."
6. decide/DecideStates DoneView: the screen-reader-only "Your decision was recorded." status is now the toast.
7. response/ReconcilePanel: "Recorded. Reloading the work item…"
8. setup/SetRulePanel: "Saved as version N." When the save closes the panel, the "You can no longer change these rules" part stays as a warning Callout on its own (wording split, not changed).
9. setup/TemplatesView: "Version N uploaded for X" (was sr-only) and "The upload went through."
10. setup/DelegationView: "Delegation added: …" (was sr-only).
Undo: none offered, the app has no undo path for any of these.

### Deliberate keeps
- response/ResponseView SuccessView ("Response recorded. <who, when, proof>") and rfp/OutcomeView "Outcome recorded": whole completed-page views where the form is gone; the callout is the lasting record and the page would be empty after 6 s. The design engineer may overrule (the board draws it as a callout).
- decide/DecideStates "Next step" card (psl-callout--success on the decided page): lasting guidance for the record.
- assistant DraftStart/DraftCard "Started REF. Open the work item": lasting state of the draft, shown on every load.
- rfp/FollowupCard "Sending… / Sent <time>": status of the follow-up record, holds focus.
- rfp/AssignPmDrawer "Assigned to X": lasting state seen when the assignment is already written.
- FileUpload "Uploaded · size", start-work StartProof "moved", workspace Links loading/gone, all `*__notice` and Callout warnings/problems, the stale/uncertain notices, "Saved. We couldn't refresh…", progress lines ("Getting this decision ready…", "Recording the return…"), assistant send notice (CHANGED).
- Start work, claim and plain uploads have no existing success notice, so none was added.

### Tests
- Unit: tests/components/toast-host.test.tsx (stacking and newest at the bottom, 3 max, 6 s with hover and focus hold, never takes focus, survives a route change, live region empty then written, Undo, useToastWhen, axe). tests/no-success-callouts.test.ts fails on a success Callout outside an allowlist of 3 files with reasons (ResponseView, OutcomeView, DecideStates).
- Old assertions updated to read the toast (same text, same checks): alerts-settings, hypercare, income-schedule, ledger-source, support-handover, setup-delegation, setup-rules, setup-templates, weekly, workspace-step, payment-reminder, asset-schedule; e2e alerts, clients, decide, document-review, rfp-assign, setup, setup-delegation, setup-templates, support-handover, weekly, workspace. Where a test said a notice "goes away" after the next action (income-schedule x2, alerts-settings), it now checks the page holds none; a toast times out on its own. setup e2e no longer expects focus on the success callout (a toast never takes focus).
- e2e added to existing tests: assign on My work as pmo_lead (rfp-assign: toast, no `.psl-callout--success`), saved alert setting (alerts), decision (decide: "Your decision was recorded."), send (workspace W-2001: toast, no success callout), plus clients and setup.
- Two e2e were stale from D-150 (the CEO now sees every project): document-review "401 signs in…" and support-handover "ceo persona is not on P-0101's list" now use admin.

### Validation
- eslint, tsc: clean. Full vitest: 3 runs; the last full run had 3 failures, 2 mine (fixed, rerun green) and 1 mock-contract from the coordinator's concurrent D-153 edit (green on rerun, 436 tests across mock-contract, ceo-mock, hr-mock, toast-host, no-success-callouts). One last full vitest after the final two edits was not repeated.
- e2e against 4951/4952: 107 (rfp-assign, alerts, clients, decide, document-review) all pass after the persona fix; 460 across the other touched features: 451 pass, 9 fail, none from the toast: (a) 3 setup-delegation/templates counts expect 2 GETs but dev StrictMode makes the initial load 2 (proved by a load-only run showing 2 GETs); (b) 5 phone tests (ledger-source x3, income-schedule, asset-schedule) time out because the Next dev overlay intercepts clicks (asset-schedule passed on rerun); (c) support-handover ceo (fixed). Not rerun on a production build.
- NOT run: `delivery/checks.sh` (it runs npm ci and a production build, which you told me not to do), and the fidelity tool. Visual check: toast at 1440 seen in a screenshot; the phone screenshot hung in dev, so the phone position is by measured boxes only.
- Shared fix note: the hydration-lost click in ceo.spec may exist in other first-click e2e specs.

## D-152 conveyor floor
Commits c58879fa (scene), 74703496 (e2e).
- `frontend/src/features/floor/scene.ts` rewritten as concept 1 (CONVEYOR): fixed orthographic camera (yaw .42, pitch .72, drag clamps as in the concept), a belt per line, a machine per station, a stack of white blocks for the waiting count capped at 8 (exact number in the chip label), orange machine plus pulsing lamp when `needs_person`, up to two boxes per busy station riding the belt to the next station, belt slats creeping left to right. Colours are tokens only: `--ink`, `--ink-strong` (belt), `--signal`, `--signal-tint`, `--surface`, `--surface-subtle`, `--neutral-tint`, `--nav-muted`, `--focus`; the concept's `--g-*` materials are not in the app, so they map to these.
- Count or needs_person changes repaint just that machine in place (chip kept, so keyboard focus survives a poll); a changed set of lines/stations rebuilds. The view is fitted to the tallest stack, so a count change never moves the view.
- Frame loop runs while the tab is visible; it stops on `visibilitychange` hidden and restarts on visible. Reduced motion: loop stops, boxes hidden (the app already shows Flat in that case).
- `Floor3D.tsx`: new token set, new hint, stage is a tab stop (`role=group`, tabindex set in an effect to satisfy jsx-a11y) with keydown: arrows turn/tilt, R resets; Reset view button kept. `floor.css` comment only. Unchanged: data passed as returned (counts never coerced), HTML chips and line labels, Flat/3D switch and all fallbacks, lazy import of three.js, hover/focus readout.
- Gaps against the brief, stated plainly: the previous Floor3D had no arrow/R keyboard handler and no click-through to a line or station (chips are not links, nothing in the overview routes there), so the keyboard is newly added and no click-through was added or removed. The 280 ms count-change animation of concept 3 is gone (conveyor motion is the animation).
- Tests: new `tests/floor3d-keys.test.tsx` (scene recorded: lines passed as returned, arrows and R/Reset view call turn/reset); `overview-floor*.test.tsx` stub Floor3D and needed no change (they pass). `e2e/overview.spec.ts`: the two 3D tests now expect frames to keep running (belts), the new hint, and keys on the stage.
- Screenshot at 1440 as ceo: `delivery/features/F-54/round-3/screenshots/overview-3d-conveyor-ceo-1440.png` (project checkout, headless Chromium with software WebGL).
- Not run: the design-fidelity tool (no board for this floor; concept page is the reference). A stack is capped at 8 blocks, so a station with more than 8 shows 8 and its exact count in the chip.

## D-154 response and outcome toasts
Commit 6c71129e.
- `ResponseView.tsx` SuccessView: `useToastWhen` fires "Response recorded." plus the recorded sentence (same wording) only when this page just recorded it (new `fresh: true` on the `done` view in `useResponse.ts`, set on the record and settle paths); a task opened already recorded shows no toast. The success callout is replaced by a read-only "What was recorded" block (sentence: what, how received, who, when, proof count; fallback line when the 200 carried no `recorded`), then the existing "What happens next", footnote and back link. Never blank.
- `OutcomeView.tsx`: toast "Outcome recorded. <Result>" when this page records the outcome (new `justRecorded` in `useOutcome.ts`, covers both the reloaded RecordedView and the reload-failed page). The reload-failed page drops the success callout for a read-only "What was recorded" block (the result, and that only the result is known). The normal recorded state still shows RecordedView as before.
- `tests/no-success-callouts.test.ts`: ResponseView and OutcomeView removed from the allowlist. DecideStates stays: its remaining callout (`decide-next`, line 452) is the next-step statement about the record, not the result of the press; the press result is already the "Your decision was recorded." toast.
- Tests updated: `response.test.tsx`, `rfp.test.tsx` (toast text, read-only block, no `.psl-callout--success`, no toast on an already-recorded task), `e2e/response.spec.ts`, `e2e/rfp.spec.ts` (read `.psl-toast`).

### Validation for D-152 and D-154
- `npm run lint` clean; `npx tsc --noEmit` clean.
- Full vitest: 145 files, 3532 tests passed (the run at 23:03 included the D-154 edits); targeted re-run of response, rfp, no-success-callouts, floor, overview: 497 passed.
- Playwright (temp config, mock 4951 via MOCK_PORT=4951, app 4952): overview.spec all 12 passed; response and rfp success/record tests passed (18 selected, 18 passed). An earlier broad run of overview, response and rfp reported 12 passed with 4 failing before the e2e updates and MOCK_PORT was set; the final targeted run is green but I did not re-run the whole response and rfp files after that.
- Worktree clean, branch pushed. Dev servers left running.
