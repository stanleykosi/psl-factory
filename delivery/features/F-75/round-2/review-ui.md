VERDICT: PASS
COMMIT: a24195b3bd085eb5730a9155bce08b2e22fc9e92
REVIEWER: ui-reviewer
AUTHORITY: UI design reviewer

## Summary
- D-193 pre-merge re-check on a24195b3 (origin/main 1e78793f merged once into the branch; previous head d5c20396). Diff-only: no servers, no test suite, no npm ci.
- No F-75 file changed in the sync. Every F-75 frontend/src file (RegistersTab.tsx, ActionsTab.tsx, TabParts.tsx, tabsModel.ts, project-tabs.css and the rest of the list in the D-193 section) is byte-identical between d5c20396 and a24195b3.
- Main's 26 files change no UI on the Registers or Actions tabs. The only shared-looking items (work-item.css, workspace/adapter.ts, mock/server.mjs) are class-scoped to the work item or are routing for other paths; projects/ and shell/ import none of them.
- Fidelity scores and the B35 signed exceptions carry over unchanged: 15 exceptions and 4 visual waivers (D-207), coverage 100% after exceptions, visual 81.1 / 76.6 / 86.2 / 78.0 on SCR-11 and SCR-29 at 1440 and 390.
- UI-1-1 remains verified; the earlier UI-2-1 to UI-2-3 and UI-1-6 stay non-blocking, as in round 2.

## D-193 re-check (a24195b3)
What I checked, diff-only:
1. F-75's own frontend/src files (list from `git diff --name-only 4a88c26b d5c20396 -- frontend/src`): `git diff d5c20396 a24195b3 -- <those files>` is empty. No F-75 screen, model, CSS or adapter file changed.
2. `git diff --stat d5c20396 a24195b3`: 26 files, all main's (F-111 issue follow-up, F-87 work-item controls, workspace line adapters, mock issues/work-live/server, and their tests). None is in frontend/src/features/projects, frontend/src/shell or frontend/src/api.
3. Shared files that could reach the Registers or Actions tabs:
   - `frontend/mock/server.mjs`: adds an F-111 GET intercept (`issuesRoute`) before the other handlers. Its path pattern (`ISSUES_PATH` in `frontend/mock/issues.mjs:4`) matches only `/api/v1/work/51nn[/issue-followup]` and `/api/v1/projects/{id}/issues/{n}[/messages]`. The project tab reads that serve Registers and Actions do not match, so they fall through to `projectTab` unchanged. The work-live drop handling change is for work writes only.
   - `frontend/src/features/workspace/adapter.ts` (61+/15-) and `useWorkspaceStep.ts`: workspace line adapters, imported by the work item page only. The projects feature and shell do not import them.
   - `frontend/src/features/work-item/work-item.css`: adds `.work-controls`, `.work-control`, `.work-header--end` and a 719.98px media rule. Grep shows these classes are used only in work-item/ files; project-tabs.css does not use them.
   - `frontend/src/shell/AppShell.tsx`: not in the sync diff, so the bell counts are as at d5c20396.
   - `frontend/tests/next-config.test.ts`: one line changed in the sync (main's `issues.mjs` entry next to F-75's `project-sections-model.test.ts`). It changes no UI.
4. Conclusion: nothing from main changes the layout, tokens, classes, column order, focus behaviour, Show more, the Severity note or the as-of line that the UI lens covers on the Registers or Actions tabs. The fidelity evidence from round 2 stands on a24195b3. No re-run was needed, and none was done.

## Findings
- UI-2-1 | non-blocking | low | design engineer (sign-off, B35) | Unexcepted until signed, (a) D-182 hides, entries read "hide accepted by the design engineer, 23 Nov 2026, D-182; exception entry pending sign-off (B35)": "PM · Tunde Bello", "Engineering (recorded by PM)", "Waiting on Engineering · Engineering (recorded by PM)", "Closed by QA and PM · PM · Tunde Bello", "Engineering (recorded by PM) · due 15 Nov", the four severity glyph texts "■■■", "■■□MEDIUM", "■■□", "■□□", the "OVERDUE" tags (SCR-29 mobile, two), and the five extras (Escalations, dashes on other registers, Critical tag, and so on). Two of these were approved in the spec; the exception entries are what is unsigned.
- UI-2-2 | non-blocking | low | design engineer (sign-off, B35) | Unexcepted until signed, (a)/(b)/(c) entries marked "pending design engineer (B35)": button "Filter" (all four runs), text "Actions come from confirmed minutes. Changing an owner or due date is recorded with your name." (SCR-29 desktop), "No owner · due Unknown" (SCR-29 mobile), "Tunde Bello · PMO" (SCR-11 desktop), tab "Registers" (mobile, clipped in the strip), and the extras "As of line, phone register switch, AGE on phone cards" and "board sample rows and counts". Group (a) for Filter and the sentence; (b) for the sample rows and counts; (c) for the account menu and tab strip.
- UI-2-3 | non-blocking | low | design engineer | Still seen by the tool and not excepted by a name entry, but not missing items: moved items "Table" (board inside a frame, page inside a section; same box within 4 to 79 px in height), SCR-29 desktop breadcrumb "PROJECTS / LAGOON HEALTH", "PROJECTS" and "PM Tunde Bello · Route A from RFP-0031" (c, frame); mobile tabs Milestones, Documents, Money (c, F-70 strip); SCR-29 mobile "OPEN" tags and "Tunde Bello · due 04 Nov" (b, sample words DONE/OVERDUE against live states). Extras: Delivery tab, Overview and Setup nav, bell, Demo controls, "As of" line (c, shell). The visual score 76.6 to 86.2 comes from these; the 4 D-207 visual waivers cover them.
- UI-1-6 carried: phone register switch and age on phone cards are not on the mobile board (taste, for the design engineer; also in the extras above).

## Verified
- UI-1-1 | verified | d5c20396 and a24195b3 (no change to RegistersTab.tsx in the sync): Registers table is ISSUE, WHAT, SEVERITY, OWNER, STATE, AGE with AGE right-aligned last, matching the board at 1440; 390 shows cards with no overflow; the tool lists no misplaced STATE or AGE.

## Evidence
- Round-2 evidence (286b4105 and d5c20396, unchanged): fidelity tool run with fidelity-exceptions.json, P-0101, one run per board and width. Reports and side-by-sides in `/Users/Hunchoo/psl-factory-main/delivery/features/F-75/round-2/fidelity/<board>-<width>/`.
- Sign-off: B35 approved by the coordinator under D-207 (15 exceptions, 4 visual waivers), recorded in `/Users/Hunchoo/psl-factory-main/delivery/features/F-75/fidelity-exceptions.json`.
- Round-2 screenshots and logs: `/private/tmp/claude-501/-Users-Hunchoo-psl-factory/4e9455a7-949a-43f4-9a55-a544c0864821/scratchpad/f75r2/`.
