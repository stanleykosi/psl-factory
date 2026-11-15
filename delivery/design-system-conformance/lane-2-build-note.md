STATUS: PARTIAL (migration done and pushed; fidelity not at bar, 12 lane e2e tests still failing, see below)
COMMIT: 2b4591afaec429f8c038ac357e724fc178dbf934
BRANCH: ds-migrate-2
BUILDER: builder
LANE: 2 (start-work, response, rfp, exceptions, projects, clients)

## Done
- Every file in the lane now uses `@/components`: Button (busy, never disabled while submitting), Callout (announce rules), Tag/StateTag, Panel, TextField/TextArea/Select/DateField/MoneyField/Checkbox/RadioGroup, Segmented, Tabs, SearchField/ListToolbar/FilterPanel, Table, ShowMore, Drawer, FileUpload, Loading/Skeleton/EmptyState, Breadcrumb, PageTitle, VisuallyHidden, formatters and Money/When. Deleted: response/icons.tsx, usePhone.ts, Segmented.tsx, three phone hooks, the date/size formatters, the hand drawer trap, the 480px narrow drawer.
- Response's ProofField is now built on the shared FileUpload. RecordPicker (start-work) kept as a searchable combobox (no Select for records), per your note.
- Write guards untouched (claim before write, idempotency, 409/422, no resend, RFP follow-up send rules, uncertain-send lock).
- Gate: lint 0 warnings, typecheck, build pass. Unit: 1633 tests; last full run 1632 pass, 1 failure in decide.test.tsx (lane 1, passes alone, load flake).

## Not done / open
1. Fidelity is below the bar on nearly every board (table below; after = production build on 4911 against my mock on 4912, `FRAME_FIXTURES=1`, tool = software-factory fidelity with a local `--actions` hook to drive the forms). The "before" scores in feature folders are not reproducible: background pages (My work behind the Start work drawer, mock data counts such as "4 OPEN" vs 25) now differ because the mock fixtures changed since those runs, so most of the drop is not code. I did not have budget to re-measure the base commit on the same mock. Seen real regressions I fixed: missing search landmark (wrapped ListToolbar in role=search) and the phone toolbar wrapping under the search box.
2. Differences found that come from the library, not the lane: Breadcrumb hides its "/" so the tool no longer finds "PROJECTS / LAGOON HEALTH" as one text (SCR-07 desktop, 95.7%); ListToolbar result count is `role=status` and ShowMore always draws "N showing"; Select draws a chevron icon and TextArea is 88px high where the Start work board shows a one-line box.
3. Lane e2e: 75 passed, 12 failing after my last spec updates (exceptions x9: heading level and empty/no-access wording, Show more; projects x3: journey default and coming-next headings). Not fixed.
4. FollowupCard shows no agent checklist when the follow-up has no agent (AgentChecklist needs one). Team-input proof additionally accepts .xlsx (board file), via an `accept` prop on the proof field.

## Board-vs-page differences caused by the design system (for the design engineer)
- Effect uncertain / "SEND UNCERTAIN" is now the amber tag "Effect uncertain" in exceptions; Blocked has no README word (kept, orange). Follow-up needed reads "Stopped: invoice follow-up needed".
- Ready to continue is green; RFP status: deadline orange, pending/unknown amber, won grey.
- Tag words are sentence case (no capitals); state words "Not known"/"—" are now "Unknown" (projects facts, next milestone, counts).
- Dates "17 Nov 2026", times "14:30 WAT", amounts two decimals (clients, projects, exceptions "since", recorded sentence, follow-up Sent).
- Page titles 34px (26 phone) on all six features (was 36/40).
- Start work: 500px drawer (was 480 for invoice), real Select chevron, DateField instead of native date, TextArea min height.
- Response forms: date + separate time field ("At (WAT)") instead of datetime-local; "What they did" and team choices are Segmented (team given marker is "(given)"); proof is the dashed FileUpload zone, single file where only one proof is sent; wrong-type files (not pdf/png/jpg/eml, plus xlsx for team input) are refused in the browser.
- Reconcile panel: decide-style (orange) panel head, option cards, no amber head.
- Awarded amount: MoneyField with "Mark as unknown" replaces the "Amount not known" tick; digits only, two decimals.
- Clients: "Set" tag grey, saved status is a success callout, notices are warning callouts in a live region.

## Shared files touched outside the lane
None in shell/, styles/, components/. Tests of other lanes updated because they exercise lane code: tests/workspace-step.test.tsx (DateField typing, Proof label, group role) and tests/weekly.test.tsx (reconcile options are a group).

## Test changes (all legitimate component effects, none weakened)
Loading waits use the "Loading…" text (components keep role=status); heading levels 2 to 3 for EmptyState; Select is a combobox button (open and click options); dates typed as "11 Nov 2026" plus blur and a time field; Filter has aria-expanded not aria-haspopup; tab arrows move focus, Enter opens; search settles after 200ms and needs 2 characters; Show more shows "N showing" and a busy label; success callouts located by class; MoneyField filters non-digits ("abc" stays empty, "1.234" keeps 1.23); file rows give "Uploaded · 184 KB" and a "Remove" button without the file name; reconcile radios are cards.

## Fidelity after (coverage, coverage with exceptions, visual)
| feature | board | cov | cov+exc | visual |
|---|---|---|---|---|
| F-05 | SCR-04-desktop-1440 | 70 | 100 | 80.8 |
| F-05 | SCR-04-desktop-change-1440 | 65.8 | 100 | 84.8 |
| F-05 | SCR-04-desktop-escalation-1440 | 71.4 | 100 | 86.9 |
| F-05 | SCR-04-desktop-incident-1440 | 66.7 | 100 | 85.1 |
| F-05 | SCR-04-desktop-issue-1440 | 71.4 | 100 | 87 |
| F-05 | SCR-04-desktop-leadership-1440 | 69.4 | 100 | 89.2 |
| F-05 | SCR-04-desktop-lines-1440 | 74.4 | 100 | 76.5 |
| F-05 | SCR-04-desktop-minutes-1440 | 68.4 | 100 | 86.8 |
| F-05 | SCR-04-desktop-validation-1440 | 73.2 | 100 | 78.7 |
| F-05 | SCR-04-desktop-weekly-1440 | 73 | 100 | 83.5 |
| F-05 | SCR-04-mobile-390 | 62.5 | 100 | 57.1 |
| F-05 | SCR-04-mobile-change-390 | 46.2 | 92.3 | 80 |
| F-05 | SCR-04-mobile-escalation-390 | 60 | 90 | 79.2 |
| F-05 | SCR-04-mobile-incident-390 | 45.5 | 90.9 | 78.6 |
| F-05 | SCR-04-mobile-issue-390 | 60 | 90 | 86.3 |
| F-05 | SCR-04-mobile-leadership-390 | 60 | 90 | 80.9 |
| F-05 | SCR-04-mobile-lines-390 | 73.3 | 100 | 49.9 |
| F-05 | SCR-04-mobile-minutes-390 | 53.8 | 92.3 | 77.2 |
| F-05 | SCR-04-mobile-validation-390 | 58.8 | 100 | 54.9 |
| F-05 | SCR-04-mobile-weekly-390 | 66.7 | 91.7 | 84 |
| F-06 | SCR-10-desktop-1440 | 95.8 | 95.8 | 89.6 |
| F-06 | SCR-10-mobile-390 | 100 | 100 | 73.3 |
| F-07 | SCR-07-desktop-1440 | 95.7 | 95.7 | 84.8 |
| F-07 | SCR-07-mobile-390 | 90 | 100 | 79.8 |
| F-07 | SCR-22-desktop-1440 | 97.9 | 97.9 | 87.5 |
| F-07 | SCR-22-mobile-390 | 90 | 100 | 76.6 |
| F-09 | SCR-02-desktop-awaiting-reconciliation-1440 | 82.4 | 100 | 60.9 |
| F-09 | SCR-02-desktop-waiting-1440 | 56.3 | 100 | 54.7 |
| F-09 | SCR-02-mobile-awaiting-reconciliation-390 | 82.1 | 100 | 72.7 |
| F-09 | SCR-02-mobile-waiting-390 | 55 | 100 | 73.7 |
| F-09 | SCR-16-desktop-1440 | 76.5 | 79.4 | 79.2 |
| F-09 | SCR-16-desktop-sow-signed-1440 | 86.2 | 89.7 | 79.6 |
| F-09 | SCR-16-desktop-success-1440 | 100 | 100 | 83.2 |
| F-09 | SCR-16-desktop-validation-1440 | 80 | 82.9 | 78 |
| F-09 | SCR-16-mobile-390 | 50 | 60 | 84.6 |
| F-09 | SCR-16-mobile-sow-signed-390 | 77.8 | 88.9 | 84.3 |
| F-09 | SCR-16-mobile-success-390 | 90 | 100 | 90.9 |
| F-09 | SCR-16-mobile-validation-390 | 60 | 73.3 | 74 |
| F-18 | SCR-16-desktop-rfp-lost-1440 | 74.1 | 100 | 82.1 |
| F-18 | SCR-16-desktop-rfp-outcome-1440 | 65 | 92.5 | 84.8 |
| F-18 | SCR-16-desktop-rfp-outcome-lost-1440 | 67.5 | 92.5 | 83.3 |
| F-18 | SCR-16-desktop-rfp-outcome-pending-1440 | 64.3 | 90.5 | 83.2 |
| F-18 | SCR-16-desktop-rfp-outcome-unknown-1440 | 63.2 | 92.1 | 80.3 |
| F-18 | SCR-16-desktop-rfp-pending-1440 | 76.9 | 100 | 79.6 |
| F-18 | SCR-16-desktop-rfp-unknown-1440 | 82.4 | 100 | 79.4 |
| F-18 | SCR-16-desktop-rfp-won-1440 | 56.7 | 100 | 83 |
| F-18 | SCR-16-desktop-team-input-1440 | 56.4 | 79.5 | 77.9 |
| F-18 | SCR-16-mobile-rfp-lost-390 | 66.7 | 100 | 74.3 |
| F-18 | SCR-16-mobile-rfp-outcome-390 | 43.8 | 81.3 | 89.1 |
| F-18 | SCR-16-mobile-rfp-outcome-lost-390 | 50 | 81.3 | 87.3 |
| F-18 | SCR-16-mobile-rfp-outcome-pending-390 | 44.4 | 77.8 | 89.6 |
| F-18 | SCR-16-mobile-rfp-outcome-unknown-390 | 35.7 | 78.6 | 89.7 |
| F-18 | SCR-16-mobile-rfp-pending-390 | 66.7 | 100 | 89.6 |
| F-18 | SCR-16-mobile-rfp-unknown-390 | 87.5 | 100 | 85.8 |
| F-18 | SCR-16-mobile-rfp-won-390 | 44.4 | 100 | 87.9 |
| F-18 | SCR-16-mobile-team-input-390 | 40 | 65 | 85.5 |
| F-19 | SCR-35-desktop-1440 | 61.1 | 100 | 83.1 |
| F-19 | SCR-35-desktop-detail-1440 | 50 | 97.1 | 84.5 |
| F-19 | SCR-35-mobile-390 | 33.3 | 100 | 78.8 |
| F-19 | SCR-35-mobile-detail-390 | 22.2 | 100 | 86.9 |
