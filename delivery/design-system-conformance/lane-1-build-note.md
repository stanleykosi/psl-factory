STATUS: READY
COMMIT: 2bb67dbbaa1450bd02ff5e2d812baa3f448a3f24
BRANCH: ds-migrate-1
BUILDER: builder
LANE: 1 (shell, My work, work item, workspace, decide)

## Summary
- The lane's screens now use the shared components and tokens: Button, Callout, Tag, Panel, Tabs, Segmented, Select (rows per page), TextArea, MoneyField, Disclosure, Table (My work, history), ListToolbar, EmptyState, Loading, Skeleton, Avatar, MiniStationBar, SampleLabel, Icon, useIsPhone and the date formatters. Private copies deleted: usePhone and InfoIcon in work-item, the visually-hidden classes of decide and work-item, MyWork's own phone hook, the work-item tag tables (STATE_TAGS now comes from the shared table), avatarClass/agentImage, the My work row tag table, the Segments bar for tables.
- Every size, spacing, border, z-index and 719.98px breakpoint in my-work, work-item, workspace, decide and shell CSS that has a token now uses it (a script applied the on-scale values; off-scale sizes such as 17, 18, 22, 30px stay, as the audit asked for a ruling first).
- Behaviour is unchanged: the uncertain-send lock (workspace `allLocked`, decide `locked`/unconfirmed) and every F-17/F-21 send guard (one write at a time, idempotency key per attempt, aria-disabled step controls, the reconcile path) are the same code; their tests pass unchanged except the assertions listed below.
- Gate: `bash delivery/checks.sh` exit 0 (1631 tests). Playwright on 4901/4902: frame, my-work, work-item, work-item-board, workspace, decide, decide-board, weekly, alerts-bell: 250 passed.
- Fidelity: coverage after exceptions is 100% on every board re-scored. Scores are within 0.5 of the baseline on 41 of 48 boards; 7 boards fell (listed below with the cause). No D-92-caused drop is large; the drops come from other component-vs-board differences, which I list for the design engineer.

## How "before" was measured
The scores recorded in the feature folders were taken at other times (fonts, machine load) and do not repeat today: the same code scores 0 to 4 points differently. So "before" is the base commit c144c91c (`ds-components`) built and scored by the same tool, drivers, exceptions, ports and machine as "after". The feature's last recorded score is in the feature folder (F-02 round-3 scores.txt, F-14 round-4, F-16 round-2, F-21 round-1). Production builds with FRAME_FIXTURES=1; mock on 4902; frozen done/stale/default/invalid pages driven through the real UI as before (drivers copied from the features, ports changed).

## Fidelity (visual score, coverage with exceptions 100 on all)
| board | before | after | change |
|---|---|---|---|
| SCR-01-desktop-1440 | 90.9 | 91.0 | +0.1 |
| SCR-01-desktop-my-work-1440 | 90.3 | 90.3 | +0.0 |
| SCR-01-desktop-empty-1440 | 86.5 | 86.5 | +0.0 |
| SCR-01-desktop-filter-1440 | 78.1 | 78.8 | +0.7 |
| SCR-01-mobile-390 | 83.5 | 83.4 | -0.1 |
| SCR-01-mobile-my-work-390 | 92.3 | 92.3 | +0.0 |
| SCR-01-mobile-empty-390 | 76.8 | 76.8 | +0.0 |
| SCR-01-mobile-filter-390 | 96.8 | 96.9 | +0.1 |
| SCR-01-mobile-lead-390 | 83.5 | 83.4 | -0.1 |
| SCR-02-desktop-1440 | 89.8 | 89.8 | +0.0 |
| SCR-02-mobile-390 | 95.8 | 94.7 | -1.1 |
| SCR-02-desktop-ready-1440 | 95.3 | 95.3 | +0.0 |
| SCR-02-mobile-ready-390 | 94.9 | 94.9 | +0.0 |
| SCR-02-desktop-processing-1440 | 92.5 | 92.3 | -0.2 |
| SCR-02-mobile-processing-390 | 91.3 | 91.3 | +0.0 |
| SCR-02-desktop-waiting-1440 | 92.7 | 92.7 | +0.0 |
| SCR-02-mobile-waiting-390 | 89.9 | 89.9 | +0.0 |
| SCR-02-desktop-verified-1440 | 91.3 | 91.3 | +0.0 |
| SCR-02-mobile-verified-390 | 90.3 | 90.3 | +0.0 |
| SCR-02-desktop-history-1440 | 94.8 | 91.0 | -3.8 |
| SCR-02-mobile-history-390 | 93.8 | 94.3 | +0.5 |
| SCR-02-desktop-issue-1440 | 89.9 | 89.9 | +0.0 |
| SCR-02-mobile-issue-390 | 90.0 | 85.8 | -4.2 |
| SCR-02-desktop-cancelled-1440 | 93.1 | 93.1 | +0.0 |
| SCR-02-mobile-cancelled-390 | 95.9 | 95.9 | +0.0 |
| SCR-02-desktop-owner-needed-1440 | 92.7 | 92.7 | +0.0 |
| SCR-02-mobile-owner-needed-390 | 97.2 | 97.2 | +0.0 |
| SCR-02-desktop-setup-needed-1440 | 95.4 | 95.4 | +0.0 |
| SCR-02-mobile-setup-needed-390 | 95.2 | 95.2 | +0.0 |
| SCR-02-desktop-permission-1440 | 93.4 | 93.4 | +0.0 |
| SCR-02-mobile-permission-390 | 98.5 | 98.5 | +0.0 |
| SCR-02-desktop-effect-uncertain-1440 | 92.6 | 92.6 | +0.0 |
| SCR-02-mobile-effect-uncertain-390 | 94.9 | 94.9 | +0.0 |
| SCR-02-desktop-awaiting-reconciliation-1440 | 91.1 | 91.1 | +0.0 |
| SCR-02-mobile-awaiting-reconciliation-390 | 93.3 | 93.3 | +0.0 |
| SCR-03-desktop-1440 | 88.7 | 87.0 | -1.7 |
| SCR-03-mobile-390 | 86.3 | 86.4 | +0.1 |
| SCR-03-desktop-done-1440 | 92.2 | 92.2 | +0.0 |
| SCR-03-mobile-done-390 | 97.3 | 97.3 | +0.0 |
| SCR-03-desktop-stale-1440 | 85.3 | 85.3 | +0.0 |
| SCR-03-mobile-stale-390 | 80.1 | 80.1 | +0.0 |
| SCR-03-desktop-not-yours-1440 | 89.5 | 88.2 | -1.3 |
| SCR-03-mobile-not-yours-390 | 85.7 | 83.8 | -1.9 |
| SCR-03-desktop-own-1440 | 89.9 | 89.9 | +0.0 |
| SCR-03-mobile-own-390 | 79.6 | 79.5 | -0.1 |
| SCR-25-desktop-1440 | 72.8 | 72.8 | +0.0 |
| SCR-25-desktop-invalid-1440 | 79.9 | 79.9 | +0.0 |
| SCR-25-desktop-assembling-1440 | 73.7 | 73.8 | +0.1 |
| SCR-25-desktop-review-1440 | 76.6 | 76.6 | +0.0 |
| SCR-25-mobile-390 | 74.2 | 70.2 | -4.0 |
| SCR-25-mobile-invalid-390 | 80.6 | 82.5 | +1.9 |
| SCR-25-mobile-assembling-390 | 78.4 | 78.1 | -0.3 |
| SCR-25-mobile-review-390 | 81.5 | 81.5 | +0.0 |

F-17 region check (1440/390), same method:
| region | width | before | after |
|---|---|---|---|
| text-cites | 1440 | 86.2 | 86.2 |
| text-cites | 390 | 100 | 100 |
| steps | 1440 | 40.4 | 40.4 |
| steps | 390 | 31.6 | 31.6 |
| recipients | 1440 | 90.1 | 89.6 |
| timeline | 1440 | 90.2 | 90.1 |
| table | 1440 | 77.5 | 77.5 |
| table | 390 | 72 | 72 |
| suggestions | 1440 | 70.1 | 70.1 |
| checklist | 1440 | 91.9 | 91.9 |
| checklist | 390 | 76.8 | 76.8 |
| checklist-gates | 1440 | 92 | 92 |
| checklist-gates | 390 | 72.2 | 72.2 |
| findings | 1440 | 71.6 | 71.6 |
| findings | 390 | 74.7 | 74.7 |
| facts | 1440 | 94.5 | 94.5 |
| unknown-money | 1440 | 75.6 | 75.6 |
| unknown-money | 390 | 89.4 | 89.4 |
| step-form | 1440 | 45.2 | 45.2 |
| notice-done | 1440 | 93.6 | 93.8 |
| notice-done | 390 | 67.9 | 69.5 |

SCR-01 filter boards: the desktop filter board is 78.1 before and 78.8 after; the phone filter board 96.8 and 96.9. F-01 (frame) has no boards of its own; the top bar and phone bar appear in every board above. The line-layout frame boards are the SCR-25 and SCR-02 sets above.

### Drops and their cause (none from the D-92 decisions)
- SCR-02-desktop-history -3.8: the shared Select for Rows per page, the shared Table's cell padding and Tabs; the board's "Download history", Documents tab are unchanged exceptions.
- SCR-02-mobile-issue -4.2: "Preview the invoice" is the shared Disclosure (a boxed summary with a triangle) where the board draws a text link; TEST TEMPLATE is the shared amber dashed label.
- SCR-02-mobile -1.1: "See his steps" is the Disclosure too.
- SCR-03 default -1.7, not-yours -1.3/-1.9: the shared Panel's head and body padding, the TextArea's count line, Callout icons.
- SCR-25-mobile (default) -4.0: the form is taller with the shared TextArea, Select and Button sizes; the page was far from the board already (70 to 74).
To make these differences go away the design engineer can decide: restyle the Disclosure summary as a link on phones, or accept the boxed summary.

## Where a page now differs from its board because of the design system
Colour (D-92b): "Ready to continue" is green on My work, work item and decide tags (boards draw orange); "Effect uncertain" tag and mini-bar segment are amber (My work card/table, boards orange); agent DONE tag is the shared blue; the mini station bar current segment on an Effect-uncertain row is amber.
Wording and format: tab counts show "History7" style with no space between label and count (the component writes none; the accessible name reads "All 7" in the browser); the unknown tab count shows no badge (Tabs takes a number; "Count unavailable" beside the tabs says it); times written by the shared formatter read "10:42 WAT" (My work "updated", error card, refresh notices, history as-of) and "12 Nov 2026 16:45 WAT". I kept the boards' own formats where a board draws a date or time: work item history rows, the facts' dates, the started line, step times and the decision done eyebrow ("YOU APPROVED · 10:47"), version drafted times, alerted-at lines. Those still use `formatWat`/`formatClock`; moving them to "12 Nov 2026 16:40 WAT" costs 4 to 13 points on the history and done boards and a coverage miss on the done eyebrow, so it needs a board change first.
Size: My work phone filter and the history Rows per page use the shared Select (chevron, 44px); the Filter button is not dark while its panel is open (ListToolbar has no such state); toolbar chips come from ListToolbar (Clear all is a link).
Callouts gain the icon the spec asks for (next step, section notes, About history, errors); the done next-step card and the stale notice are written out by hand because the board draws an image or running text where the icon goes.
Page titles: My work keeps the frame's 40px title (`shell-title`, token display-xl); the shared PageTitle is 34px and every board draws 40. Not changed; needs a ruling (change the token or the boards).

## Things the library does not cover (kept hand-written, each with the reason)
- My work filter panel (popover and sheet): the shared FilterPanel scored 50 on SCR-01-mobile-filter against 96.8 with the board's own layout (blue apply button, grab handle, X, "Clear all" instead of the board's Clear in the head and dark Show button). The popover/sheet and its native Project list are the previous markup; Project also stays native because Select has no search box (coordinator's rule).
- FactsStrip, StationTrack and AgentChecklist: the work-item boards need per-fact detail words and tones, the station detail text, the uncertain-station block and phone cut-off; the shared ones take none of these. Own versions stay in WorkItemOverview.
- Workspace Decide panel and Section panels: Panel has no ref, data attributes or heading level (the pinned phone bar needs a ref; section titles are h2/h3). The Table in workspace sections has a select column, step buttons and form rows the shared Table lacks.
- Breadcrumb: the work item crumb is written out; the shared one hides its slashes from assistive text and the fidelity tool then reads the crumb as pieces (coverage miss on 8 SCR-02 boards).
- ProjectBar tabs (plain text for unbuilt tabs), decide MiniLine is the shared MiniStationBar.
- RFP/FollowupCard still uses `work-sr` (lane 2/3): the rule stays in work-item.css until it moves.

## Changed assertions (reason)
tests/my-work.test.tsx: dates/time "10:42 WAT"; tab arrow keys now move focus only (Tabs: Enter or click opens; single tab stop); unknown counts show no badge instead of "–"; tabpanel is named by aria-label; role=status is not unique any more (ListToolbar result count) so loading is read from `.psl-loading`; Show more is busy (aria-busy) and not disabled; avatar is decorative (alt ""); filter tests: no aria-haspopup, no dark Filter while open.
tests/my-work-model.test.ts: ready tone done, effect_uncertain tone waiting (shared table).
tests/work-item.test.tsx, work-item-board.test.tsx: tag tone ready=done; link tabs are role tab with aria-selected; the task panel is named by its title; avatars alt "" (full poses keep their text); "See his steps"/"Preview the invoice" are details summaries; Rows per page is a Select (click then option); "History7" names; as-of line and refresh warning use the shared formatter.
tests/decide.test.tsx, decide-board.test.tsx: note has no maxLength (the shared TextArea never cuts; the over-limit check still runs on press); the pressed button is busy and the others disabled; comment box description id.
tests/workspace.test.tsx, workspace-step.test.tsx: as-of/date strings via the shared formatter; the uncertain/stale warnings are in the polite status region (Callout warnings have no alert role) so they are found by `.ws-notice`; W-2010 id normalisation (useId).
Other lanes' tests touched because they render my components: tests/response.test.tsx (task panel region name), tests/weekly.test.tsx (`.ws-notice`).
e2e: `loaded()` helpers wait on `.psl-loading` instead of any status; same changes as above for tabs, disclosures, Rows per page, dates; my-work phone tab padding/size kept by a rule on `.my-work__tabs .psl-tab`. alerts-bell.spec.ts `loaded()` too (shared My work base page).

## Shared files touched outside the lane
- `frontend/src/shell/icons.tsx` still exports WarningIcon (now the shared Icon) and `frontend/src/features/my-work/icons.tsx` is unchanged: other lanes still import both. Delete them when the last importer is gone (ProjectsList, ExceptionsList, AlertsFilterPanel, NotificationsPage, ExceptionsFilter import my-work/icons; many import WarningIcon).
- `features/work-item/labels.ts` keeps `formatWat` and `formatWatDay` (used by exceptions, overview, response, clients, workspace labels of other lanes and by the boards' own formats). `STATE_TAGS` there is now the shared table (ready green, effect uncertain amber): projects/ProjectJourney and finance month-end read it, so their Ready tag is green too; their tests passed unchanged.
- `features/decide/format.ts` formatClock is unchanged (alerts, month-end use it).
- styles/shell.css is the shell's own and was edited; nothing in `components/`, `architecture/`, `src/api/`, `package.json` or the lockfile.

## Library issues found (for the coordinator; I did not edit components/)
1. CountBadge/Tabs/Segmented put no space between label and count ("History7"); the accessible name in the browser has a space, the textContent does not.
2. ListToolbar's result count is always a live status; pages that wait for "no status" need another signal.
3. BottomSheet does not return focus to its opener (the Filter button); I do it in My work.
4. ListToolbar's FilterPanel differs from the SCR-01 filter boards (see above).
5. Callout wraps children in a span and always draws the icon: pages with running-text notices (stale notice) and image cards (done next step) cannot use it.
6. Panel has no ref/data/heading-level pass-through.
7. Disclosure's summary looks boxed; the boards draw a link.

## Validation
- `bash delivery/checks.sh` in the worktree: exit 0 (Django check, lint 0 warnings, typecheck, 77 files / 1631 tests, build).
- Playwright (E2E_PORT 4901, MOCK_PORT 4902, the specs above): 250 passed after the last fix; one decide.spec assertion re-run alone (passed).
- Fidelity as above; outputs under /private/tmp/claude-501/lane1/out (after) and /before (base), compare table final-compare.txt. Servers on 4901 to 4903 stopped by port; test-results deleted; no files outside the lane's paths other than those listed.
