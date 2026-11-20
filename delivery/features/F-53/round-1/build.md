STATUS: READY
COMMIT: 37adc13c1e9e17bf4334f07c566b96c002db56fa
BUILDER: builder
LANE: full

## Summary
- All raw `<button>`, `<input>`, `<select>`, `<textarea>`, `<table>` in src/features and src/app are replaced with shared components. The ESLint rule found 58 (the readiness grep found 34 single-line ones; 24 more start on their own line).
- ESLint `no-restricted-syntax` rule in frontend/eslint.config.mjs bans the five elements in src/features and src/app (src/components allowed). A scratch file with all five failed lint in features and app and passed in components, then was removed.
- Shared components extended additively, with tests (tests/components/conformance-options.test.tsx): Button kinds `link` and `bare`; DateField `time` and `hideLabel`; Select `hideLabel` and `data-value` on options; RadioGroup `hideLegend` and `disabled`; Table `leading`, `fullRow`, `wrapClassName`, column `hideHeader` and `className`, `data-label` on cells; new FilePickButton; Field label `hidden`.
- Demo for review is running on 4925 (mock on 4924).

## Changes
- Components: Button, DateField, Field, FileUpload, Radio, Select, Table, index.ts, components.css, README.md.
- Features: alerts (AlertSwitch, AlertsBell), assistant (Chrome, MentionPicker), finance/payments, my-work (CaughtUp, FilterPanel, MyWork), projects, response (ProofField, ReconcilePanel, ResponseForm, ResponseView, Segmented, SupportHandoverForm, TeamInputForm), rfp (FollowupCard, OutcomeForm, OutcomeView, RecordedView), setup/TemplatesView (+ one css selector), start-work (RecordPicker, StartWorkButton), work-item/WorkItemOverview, workspace (Links, Sections, Workspace).
- Tests: tests/controls.ts and e2e/controls.ts helpers (pick, optionsOf, setDate, setWhen); response, rfp, support-handover, my-work, engagement-planning and e2e specs updated to drive the shared Select, DateField and radio groups. New e2e/conformance.spec.ts.
- Design choices to note: chips, tools, menu items, the combobox trigger and the switch use Button `bare` (feature class keeps the look) instead of new chip components. Response Actions (pills and segmented) are now one RadioGroup. The Reconcile outcome uses RadioGroup cards. Note boxes show the counter under the box (shared TextArea). Tests that read role `radiogroup` for these groups now read `group` (fieldset). The setup templates table now has the shared scroll frame as one Tab stop (spec updated, assertion kept).

## Fixes
None (round 1).

## Acceptance criteria
1. [x] No raw controls or tables remain: `eslint . --max-warnings 0` is clean with the rule on; the raw-element grep (single and multi-line) returns nothing in features and app.
2. [x] Lint rule: scratch violation in src/features and src/app each gave 5 errors, none in src/components; scratch files removed.
3. [x] Existing tests pass; new options tested (11 tests in conformance-options.test.tsx). checks.sh: 137 files, 3363 tests passed, lint, typecheck, build, exit 0.
4. [x] Accessible names, keyboard and disabled states kept (component tests). e2e/conformance.spec.ts at 390: response form (Select, date, time, radio, checkbox, file button), RFP follow-up (Send, Edit; Space and Enter work), My work filters (checkbox, Show-all link, three Selects) all at least 44x44. 3 passed.
5. [x] Screenshots at 1440 and 390, before and after, in delivery/features/F-53/round-1/screens/ (response-form, rfp-outcome, rfp-followup, my-work-filters, setup-templates, work-item-overview; `-before.png` and `-after.png`). Reviewed response form, templates and My work filters; look matches, response radios are now plain radios, date and time are separate fields. No fidelity run (as asked).
6. [x] e2e on ports 4931/4932: response, rfp*, my-work, setup*, projects, payments, work-item*, assistant, support-handover, engagement-planning, workspace, cash-forecast, asset-schedule, minutes-end, start-work*, alerts: 644 run, first pass 21 failed (role radiogroup to group, tab order, scroll-frame stop), fixed in specs, rerun of those 21 passed; conformance spec 3 passed.

## Validation
- `bash delivery/checks.sh` under the shared lock: exit 0.
- Playwright as above. Worktree clean, pushed. 4931/4932 servers stopped; demo left on 4925/4924.
- Recurring risk for the coordinator: any other spec or test that fills `datetime-local`, uses `selectOption`, or reads role `radiogroup` for response or reconcile forms will need the helpers in e2e/controls.ts and tests/controls.ts.

## The swaps (58 sites)
alerts: AlertSwitch, AlertsBell (Button bare). assistant: Chrome chip, MentionPicker tool and item (bare). payments: clear filters, my-work MyWork clear, ProjectsList show all, CaughtUp Not now, FilterPanel Show-all, Links source (Button link). FilterPanel: line checkbox (Checkbox), Project, State, Waiting on (Select). response: ProofField Try again, 2 remove chips, file input and button (FilePickButton), ReconcilePanel reload, radios (RadioGroup), Record and continue, ResponseView Try again, ResponseForm Select (shared Select), datetime (DateField time), Actions radios, Note (TextArea), Attest (Checkbox), Record; TeamInputForm Estimate and What they gave (TextField), attest; SupportHandoverForm Gaps (TextArea); Segmented options (bare). rfp: OutcomeForm Amount (TextField), Amount not known (Checkbox), Note, Lessons (TextArea), expected date (DateField), Record; FollowupCard edit box, Try again, Check again, Send, Edit; OutcomeView Try again; RecordedView reopen. setup TemplatesView table (Table). start-work: StartWorkButton x3 (Button start), RecordPicker trigger (bare). work-item: invoice table (Table). workspace: Sections table (Table with leading, fullRow), filter chip (bare), Workspace two checkboxes (Checkbox).
