# Delivery tab and release gates: a project's six delivery lines, and the release item from waiting on the PMO Lead through their decision to release ready (contract mock only)

> Tasks: FE-DELIVERY-RELEASE, part 1 (R-PROJECT, R-WORKITEM; acceptance A-PROJECTS-VIEW for SCR-43 and the A-WORKSPACE frontend half for SCR-44, with A-WORKITEM, A-DECIDE, A-PROJECT-TABS and the F-16, F-17, F-25, F-30 tests kept green; A-RESPONSE belongs to part 3). Architecture: package `architecture/packages/v7`, manifest digest `f6231d20b4fdeabbdca9bde5986a0a7883536f1a5cafc883848ef62dd6d4b624`; FE-DELIVERY-RELEASE at `architecture/packages/v7/delivery.md:2281-2315`, `gate_ids: []`, "Unresolved gates: none". E-PROJECT `delivery[]` is typed at `frontend/src/api/schema.d.ts:2911-2933`; E-WORK-ITEM `workspace` at `:1693-1912`; this feature changes no generated type. Decisions consumed: D-PROJECTS-VIEW and D-LINE-WORKSPACE (both `proposed`, under the recorded exception `architecture/sources/decisions-2026-11-15.md` items (g), (i)), D-ROLE-PMO (Head of PMO = PMO Lead), D-64, D-83, D-89, D-91, D-92c, D-99, D-104, D-111, D-112. Open and held: D-RETURN and D-ADMIN-AUTHORITY (part 2 only), the release-decision questions at `delivery/backend-handoff/gaps-d-delivery.md:67-73`. Design: client-approved canvas version 1794581312-b166 (13 Nov 2026; SCR-43 and SCR-44 at `design/review.json:51-52`), republished with "+ Start" as 1794762832-cab1 (D-89). `python3 /Users/Hunchoo/software-factory/packages/design/design.py check --project .` was run for this spec on 18 Nov. Result: `EXCEPTION`, `passes: true` (design_sha256 `2859ab21…3d82`, D-89 frame-only change). Screens: SCR-43 and SCR-44, 8 artboards in `design/canvas/project/`: `SCR-43-desktop`, `SCR-43-mobile`, `SCR-44-desktop`, `SCR-44-mobile`, `SCR-44-desktop-decision`, `SCR-44-mobile-decision`, `SCR-44-desktop-ready`, `SCR-44-mobile-ready`. Models: `delivery/features/F-30/spec.md`, `F-28/spec.md` (shape), `F-23/spec.md` (decision links to the F-16 page).

## What is released, and what stays held (read first)
- **On the contract mock, nothing is released or deployed, and no one is given authority.** Every "release ready", "verified", "approved" and "Kemi Adebayo" on these boards is fixture text, returned the way a backend would return it. The PR and `build.md` must say so. They must not claim a working release line, a release decision or a readiness check.
- **What a real release decision would be (backend, not built):** the backend opens a decision task on the release work item for the role its configured authority names. It reports `you_can_act` per person. Once the decision is recorded and a deterministic factory check passes, it sets the item to verified. No step deploys anything; Engineering deploys outside the factory and records it in hypercare (SCR-46).
- **Held, because a product or backend decision is open:**
  1. Which decision this gate is: "Planning decision" or "Approve for release" (Conflicts 1).
  2. Who holds release authority (Conflicts 2).
  3. Whether Reject applies to a release (Conflicts 3).
  4. That "release ready" is set by the factory's check, never by Tola's step "Mark release ready" (INV-AGENT).
  5. How a delivery row the person may not open is shown (`gaps-d-delivery.md:48`).
  6. How the factory opens each next delivery line (G-43-6).

  The page shows whatever the reloaded data returns and adds no rule.
- **Held on the page itself:** the decision controls exist only where the response gives this person the task (`tasks[].you_can_act: true`). A failed, refused, stale or timed-out decision never shows "approved" or "release ready". The work page shows "Release ready" only when the re-read item's `workspace.status` says so.

## Conflicts with the boards (for the design engineer, before the build)
"Recommend" is what this spec builds if no answer comes. Each difference becomes a `delivery/features/F-32/fidelity-exceptions.json` entry with `approved_by: "builder proposal, pending design engineer"` until signed. Items 1 to 5 need an answer: 1 to 3 are product questions for PSL, and 4 and 5 are design calls. Items 6 to 10 are layout. Items 11 to 15 are exceptions to sign. A "proposal" is a field built on the mock only; the backend developer may change or refuse it.

### Need an answer
1. **The gate says "Planning decision", but the PMO Lead's buttons say "Approve for release" (product question for PSL).** Planning and costing must be finished before the SOW is signed. A release decision cannot stand in for them, so the label matters.
   - **Recommend:** the page shows the gate's label and the button labels exactly as the response returns them. The fixtures use the board's words and are marked sample. No label is in `src/`, and nothing on the page treats the decision as planning. We suggest PSL confirms this is a release decision and that the backend calls it "Release decision". The real decision stays held until PSL answers.
   - **Option B:** the fixtures say "Release decision" now. Then the board shows a sample-data difference.
2. **Who may approve a release (product question for PSL).** D-ROLE-PMO lists closure, commercial approvals and escalations for the PMO Lead, not release (`architecture/model.json:753-764`).
   - **Recommend:** the page names only the task's `required_role` as returned. It shows the controls only when `you_can_act` is true. "PMO Lead" and "Kemi Adebayo" appear only in fixtures, as sample data, and no role or approver is set as policy. PSL confirms who holds release authority, and the backend configures it. This recommendation gives no one authority.
3. **The F-16 decision page also offers Reject; the release boards draw only Approve and Return.** The shared page draws "Approve v1", "Return" and "Reject" (`frontend/src/features/decide/DecidePanel.tsx:104-113`).
   - **Recommend:** leave the F-16 page as it is (it is shared and read only here). On the mock, a reject gets the generic outcome. The backend is asked whether reject applies to a release and what it does. If it does not, a later proposal (`decision.verdicts`) lets the page hide it.
   - **Option B:** hide Reject for this task now. That is a frontend rule about a decision; not recommended.
4. **What the PM sees about who decides (default board).** The default board shows only the gate row "Planning decision · WAITING FOR PMO LEAD". The frame also draws the backend's task panel, "Only a PMO Lead can decide." (`TaskPanels`, `frontend/src/features/work-item/WorkItemOverview.tsx:494`), because `tasks[]` carries the decision without a step linking to it.
   - **Recommend:** keep the panel. It is the backend's own statement of who decides, from `required_role`, and readiness asks for the authority display first. List it as an extra element.
   - **Option B:** the default fixture leaves the task out of `tasks[]` for the PM. Whether the backend lists tasks a person cannot act on then becomes a backend question.
5. **The delivery sub-nav (Overview, Release, Go-live, Hypercare, Archive, Handover, Closure, G-F32-1).** It is drawn on SCR-43 desktop and on all three SCR-44 desktop boards.
   - **Recommend:**
     - On the Delivery tab (SCR-43), build it from the `delivery[]` rows already loaded. Overview is current (`aria-current="page"`). Each row's short label comes from the proposal `delivery[].short_title`, or `title` when absent. A row links only when it has a `work_id` (D-104).
     - On the release work item (SCR-44), don't draw it. List it as a frame exception: drawing it would need a second E-PROJECT read inside the shared work-item frame. The project tab bar's "Delivery" tab gets the person back to the overview.
     - On phones, don't draw it either: the phone boards draw none, and the rows are the navigation.
   - **Option B:** the work item page also reads E-PROJECT by `workspace.context.project.case_id` and draws the sub-nav. That is a second read and a frame change for every line item.

### Layout (phone against desktop, frame)
6. **Phone boards are shorter than desktop; the data is the same at both widths (D-99, as D-111 approved for F-28 and F-30).** The SCR-43 phone board shows only the rows and "Open the handover". The SCR-44 phone boards leave out Tola's checks and the note. The decision phone board shows two of the four facts.
   - **Recommend:** on a phone, show the desktop sections stacked in one column, in the same order. Extras are listed (`phone composition`).
   - **Option B:** hide sections on phones with CSS. That hides data the page was given; not recommended.
7. **Titles and wording that differ by width.** Examples: "Delivery · Tamarind" against the project title; "Approve for release?" against "Your decision"; "Verified 25 Mar. Not a deployment." against the desktop sentence; and the phone bar words DECIDE, READY and "← Delivery". **Recommend:** use the desktop wording at both widths, as D-111 approved for F-28 conflict 5. Phone wording and the phone bar are exceptions (`phone wording`, `frame item`). The phone bar keeps the built F-22 frame.
8. **Project tab bar.** `PROJECT_TABS` gets one `delivery` tab after Journey, so the Delivery tab appears in the project page and in the line tab bar (`ProjectBar`, `WorkItemView.tsx:133`).
   - On the project page, Delivery is the selected tab, as on the boards.
   - In the line tab bar, no tab is marked current, as F-30 does (D-111 F-30 conflict 8). Delivery drawn selected on SCR-44 is a listed difference.
   - The board's "Planning" tab belongs to SCR-42 and F-31 and is not built here (`frame item`).
9. **Tola's checks on SCR-44.** **Recommend:** draw them as a `checklist` section titled "Checked release progress" with `agent: "tola"`, one item per check (status and tag as returned). The board's "Finished 23 Mar 10:12" is read from the section's `as_of`. It reads "As of 23 Mar 10:12 WAT" (wording difference), because `agent.finished_at` (G-44-4) is not built. "Ask Tola" is the existing `assistant` workspace link, drawn in the links row under the main column rather than inside the agent panel (`frame layout`). It sends no context; G-44-3 is recorded, not built.
10. **Decide and Next panels (SCR-44 decision and ready).**
    - Decision: "Approve for release" and "Return with a note" are steps with `task_id`. They are links to the F-16 page (F-17 Conflicts 4, F-23 Conflicts 3). The in-page Note box is not drawn; the F-16 page has it.
    - Ready: the shared NEXT heading is used as it is ("Next", `STEP_TEXT.next`), with the returned `next` line. "Open go-live" is a `workspace.links[]` entry of a new kind `work`, drawn in the links row (`frame layout`).
    - The shared timeline row is not used: no fixture here has a timeline.
    - The ready banner is the existing title-less, note-only section. It is drawn green only because the response's status tone is `verified` (`bannerTone`, `Workspace.tsx`). G-44-1 `workspace.notices[]` is recorded, not built.

### Exceptions to sign
11. **Fields left out until the backend confirms them (readiness).**
    - "DELIVERY · 3 OF 6 DONE" and "DLV-0052" (G-43-1): the browser never counts rows.
    - "Open the handover" (G-43-4): `next` is plain text.
    - The SCR-44 sub-nav (Conflicts 5).

    Category `no field`.
12. **The F-16 page's words.** "Approve v1 / Return / Reject" and "Approving earns APPROVED only." appear on the F-16 page, against the board's "Approve for release / Return with a note". The decision page is not a board in this feature, so this is recorded rather than scored.
13. **Frame items.**
    - The top bar and signed-in name: the mock has no PMO Lead persona, so the decision board is served to `pm`, and "Kemi Adebayo · PMO Lead", "Overview" and "Setup" are not drawn.
    - "+ Start" (D-89).
    - The project page's crumb has no "DELIVERY" segment (the existing `Breadcrumb` on every tab).
    - The "Decide · PMO Lead" panel title reads "Decide" (an F-17 exception).
    - Tab counts come from P-0101.

    Category `frame item`.
14. **Sample data.** The boards' Tamarind Loans becomes Lagoon Health (P-0101), so the crumb, title and tab counts agree with the project the rows sit on. Counts are Milestones 4, Documents 6, Registers 6, Actions 9. Names, dates and references are fixture values (`sample data`). The SCR-43 heading "The six delivery lines, in order" is drawn as "The delivery lines, in order", so no count is fixed in code (`wording`).
15. **Tones and visual waivers.** Tags take their tone only from the returned `tone`, never from the words. A board colour the design system lacks is an exception, not a hard-coded value. Each board below 90 visual (and at least 70) carries a D-83 waiver citing the shared frame (D-99, D-110), after the design engineer signs it.

## Boards
| Board | File (`design/canvas/project/`) | Page | Width | Mock |
|---|---|---|---|---|
| SCR-43 desktop / phone | `SCR-43-desktop.dc.html`, `SCR-43-mobile.dc.html` | `/projects/P-0101/delivery` | 1440 / 390 | persona `pm` |
| SCR-44 default | `SCR-44-desktop.dc.html`, `SCR-44-mobile.dc.html` | `/work/W-2501` | 1440 / 390 | persona `pm` |
| SCR-44 decision | `SCR-44-desktop-decision.dc.html`, `SCR-44-mobile-decision.dc.html` | `/work/W-2502` | 1440 / 390 | persona `pm` (the fixture's `you_can_act: true` is the data) |
| SCR-44 ready | `SCR-44-desktop-ready.dc.html`, `SCR-44-mobile-ready.dc.html` | `/work/W-2503` | 1440 / 390 | persona `pm` |

All 8 are live URLs; no driver is needed.

## Summary
- A new "Delivery" project tab (`/projects/{case_id}/delivery`, SCR-43) draws E-PROJECT `delivery[]` as returned. Each row shows its number, title, reference, gate tag and date or reason, and links through `work_id` only. The page also shows the backend's line-order note, Tola's delivery check (falling back to `agent_summary.text`) and the Next line. It makes no second read and no write.
- The release work item (`/work/{id}`, line key `delivery_release`, SCR-44) is drawn by the F-17 frame in three states:
  - waiting on the PMO Lead: the four gates and Tola's checks;
  - the PMO Lead's decision: what is being decided, plus Approve and Return as links to the F-16 page;
  - release ready: the verified banner, Tola's readiness note, Next and "Open go-live".
- Authority comes only from `tasks[].you_can_act`, `cannot_act_reason` and `required_role`. A decision step whose task is not actionable for this person is drawn unavailable, with the reason. Nothing is read from `/me` for it.
- "Release ready" and verified come only from the returned status. Unknown values read "Unknown", never 0 or blank.
- New in this feature: the Delivery tab, one small frame rule (decision steps follow their task's `you_can_act`), a `work` link kind, fixtures W-2501 to W-2510 and the `delivery[]` rows on P-0101. Contract mock only.

## Context
- **Project page:** `frontend/src/features/projects/ProjectJourney.tsx`.
  - `ProjectView` branches on `tab`: journey, `hasTabContent`, otherwise `MoneyTab`.
  - `AgentSummary`, `PmRoute` (in `ProjectTabContent.tsx`), `ProjectNoAccess`, `SignedOutState` and `LoadingState` are reused.
  - `frontend/src/features/projects/model.ts:26-37`: the `ProjectTab` type and `PROJECT_TABS`.
  - `ProjectTabs.tsx` builds `Tabs` with links. The route is `frontend/src/app/projects/[caseId]/[tab]/page.tsx`, which accepts any key in `PROJECT_TABS`.
  - The read is `useProject.ts` (one E-PROJECT read; no polling).
- **Work item page:** `frontend/src/features/work-item/WorkItemView.tsx`.
  - `ProjectBar` (line 133) maps `PROJECT_TABS`, so the new tab appears there with no further change. `LineHeader` draws crumbs and the status.
  - `WorkItemOverview.tsx` mounts `Workspace` and `TaskPanels` (lines 494-511, 720-732). `TaskPanels` skips any task a workspace step links to.
- **Workspace frame:** `frontend/src/features/workspace/`.
  - `Workspace.tsx`: the decide/next side panel, `bannerTone`, the links row.
  - `Steps.tsx` `StepControl`: a step with `task_id` becomes a link to `/work/{id}/decide?task=…` (lines 56-79). Today it does not look at the task's `you_can_act`.
  - `Sections.tsx` (`SectionView`, `FactsList` with `Unknown`, checklist `Items`, section `as_of` and `agent` meta), `proposals.ts` (`workspaceLinks`: kinds `assistant`, `project_tab`, `document`), `Links.tsx`, `labels.ts`.
- **Decision page (F-16), used as it is:** `frontend/src/features/decide/` (`DecideView`, `DecidePanel`, `useDecision`, `DecideStates.tsx` `cannotActCopy` with the reasons `not_your_role`, `prepared_by_you`, `already_decided` and `not_your_turn`).
- **Mock:**
  - `frontend/mock/projects.mjs` serves `fixtures/projects/P-0101.json` to personas `finance_lead` and `pm` (`list.json`); others get 404, and P-0099 is the no-access id.
  - `frontend/mock/server.mjs` `taskResponse` (lines 148-182) handles claim and decide; it applies `<work_id>.approve.json` after an approve.
  - E-WORK-ITEM serves `fixtures/work/<id>.json`.
  - There are no W-25xx fixtures and no T-25xx tasks; F-31 avoids W-21xx, W-29xx and W-30xx.
- **Gap notes:** `delivery/backend-handoff/gaps-d-delivery.md:32-73`.
- **Tests that list the tabs** and gain "Delivery" (the only allowed assertion edits): `tests/projects-journey.test.tsx:164` and `:192`, `tests/workspace.test.tsx:116` and `:118`.

## Contract

### E-PROJECT `GET /api/v1/projects/{case_id}` (Delivery tab; read only, unchanged)
- **Used fields:** `title`, `pm`, `tab_counts`, `delivery[]` (`line_key`, `title`, `state`, `gate {label, tone}`, `work_id`, `held_by`), `agent_summary`, `next`, `revision`.
- **Rows:** drawn in the returned order and numbered 01, 02, … by position. A row's tag is `gate.label` with `tagTone(gate.tone)`; a row with no `gate` shows "Unknown". The title links to `/work/{work_id}` only when `work_id` is present and passes `RECORD_ID`. Otherwise the title is plain text and the reference reads "—".
- **Not computed by the frontend:** no done count, no gate state and no closure rule. Nothing changes because of a row's `state`; the state only becomes the tag's accessible text when there is no `gate`.
- **Empty:** with `delivery` absent or `[]`, the panel reads "No delivery lines yet." and no Tola card is drawn unless the data supplies one.
- **Errors:**
  - 401: signed-out, with `next=/projects/<id>/delivery`.
  - 403 and 404 look the same (`ProjectNoAccess`: no title and no row).
  - 5xx: `WorkErrorCard` with Retry.
  - Loading: `LoadingState`.
- **Access:** the existing `/me` destinations gate for Projects is unchanged. It opens the page and grants no authority.

### Proposals on E-PROJECT (mock overlay `frontend/mock/proposals/delivery-release.json`; recorded in build.md)
| Proposal | Shape | Page |
|---|---|---|
| G-43-2 | `delivery[].reference` string; `delivery[].at` `{date?, unknown}`; `delivery[].detail` string | Reference beside the title. After the tag, "· 25 Mar" from `at.date`, or "Unknown" when `at.unknown`, or `detail` when there is no `at`. An absent `at` and `detail` draw nothing |
| G-F32-1 | `delivery[].short_title` | Sub-nav label (Conflicts 5); falls back to `title` |
| G-43-3 | `delivery_agent {agent, title?, status, finished_at?, steps[{text, status, source?, at?}]}` | Tola's card through the existing `AgentCard` shape (`title` as its heading, "Checked 12 Apr 09:00" from `finished_at`, "Ask Tola" link to `/assistant`). When it is absent or malformed, the existing `AgentSummary` from `agent_summary.text` is drawn |
| G-43-5 | `delivery_summary.note` | The line-order sentence, drawn only when returned; never written in `src/` |
| Not built | G-43-1 `delivery_summary {reference, done, total}`, G-43-4 `next_action` | Recorded only (Conflicts 11) |

### E-WORK-ITEM `GET /api/v1/work/{work_id}` (release item; unchanged)
F-17 Contract 1 to 11 and F-30's read rules apply: 401 shows signed-out with `next`; 403 and 404 look the same (`NoAccessState`, with no title, project or reference); 5xx shows `WorkErrorCard`. The page branches on nothing for `line_key: "delivery_release"`: no line-specific code is added to `Workspace.tsx`.

| Id | `state`; `workspace.status` | Sections | Steps / tasks / links |
|---|---|---|---|
| W-2501 default | `waiting`; "Release · waiting on PMO Lead", `person` | `checklist` "Release gates · build 1.0.0": PMO Lead assigned · Kemi Adebayo (done, "Done"); Client UAT response recorded · approved build 1.0.0 (done, "Done · 22 Mar"); Planning decision (now, `held_by {kind: role, name: "PMO Lead"}`, "Waiting for PMO Lead"); Release readiness (not_yet, "Not yet"); `note` = "Release gates check the project is ready to release. They don't authorise the deployment itself." Plus `checklist` "Checked release progress", `agent: tola`, `as_of` 23 Mar 10:12, three done checks with their tags | no steps. `tasks: [T-2501 {required_role: "PMO Lead", you_can_act: false, cannot_act_reason: "not_your_role", decision{…}}]`. `links: [assistant "Ask Tola"]` |
| W-2502 decision | `action_needed`; "Your decision", `person` | `facts` "What you're deciding": Delivered against plan v1 = "4 of 4 stages built"; Client UAT = "Approved 22 Mar"; Open issues = "1 medium · 0 high"; Changes since the SOW = "CR-0044 · signed". Plus Tola's checklist as W-2501 | steps `approve_release` "Approve for release" (primary, `task_id: T-2502`, `claim_required: true`, `consequence` "Approving lets Tola prepare release readiness. It doesn't deploy anything.") and `return_release` "Return with a note" (secondary, `task_id: T-2502`). `tasks: [T-2502 {required_role: "PMO Lead", you_can_act: true, revision: 1, decision {version {label: "Release gates · build 1.0.0", number: 1}, prepared_by Tunde Bello, chain [PMO Lead · Kemi Adebayo, current, is_you]}}]` |
| W-2502.approve.json | the ready item of W-2503 with id W-2502; T-2502 `you_can_act: false`, `already_decided` | | |
| W-2503 ready | `verified`; "Release ready", `verified` | Title-less note-only section: "Release ready and verified on 25 Mar. This isn't a deployment: deploying is done by Engineering outside the factory, and recorded in hypercare." `checklist` "Readiness note · by Tola": Build 1.0.0 · 58 requirements ("Contents"), Rollback plan ("Attached", `cites` a document id), Incident contacts ("Attached") | `next: ["Tola drafts the go-live document for the client."]`, `links: [{key: "open_go_live", label: "Open go-live", target {kind: "work", work_id: "W-2510"}}]`. No steps |
| W-2504 | as W-2502, but T-2504 `you_can_act: false`, `not_your_role` | | the same two steps, which must render unavailable |
| W-2505 | as W-2502, but T-2505 `you_can_act: false`, `prepared_by_you` | | the same two steps, unavailable |
| W-2506 | as W-2502, but the steps name `task_id: T-2599`, which is not in `tasks[]` | | steps unavailable; no decide link |
| W-2507 | as W-2502 with Open issues `value` absent, one gate item `status: unknown` without a tag, and no `as_of` | | Unknown case |
| W-2508 | `processing`; "Preparing", `agent`; agent checklist whose last item "Mark release ready" is `done` | | INV-AGENT case: no banner, no "Release ready" |
| W-2510 | a plain go-live work item (no `workspace`), drawn by the generic work item page | | the target of "Open go-live" and of the overview's go-live row; it is not SCR-45 |

Every fixture is `sample: true`, `line_key: "delivery_release"` (except W-2510), `reference: "REL-0091"`, `workspace.context.project {case_id: "P-0101", title: "Lagoon Health · patient app"}`, crumbs Projects / Lagoon Health / Delivery / REL-0091, and `subtitle` "PM Tunde Bello". Each validates against the generated E-WORK-ITEM 200 schema once the `links` proposal is removed. `revision` and `workspace.revision` are numbers ≥ 1.

**P-0101 `delivery[]` (additive keys in `P-0101.json`; the journey's existing keys are byte-for-byte unchanged):**
1. Release gates: REL-0091, "Release ready", tone `verified`, at 25 Mar, `work_id` W-2503.
2. Go-live acceptance: GLV-0104, "Accepted", detail "Signed 02 Apr", `work_id` W-2510.
3. Hypercare: HYP-0062, "Running", detail "Day 10 of the window", no `work_id`.
4. Archive: ARC-0130, "Archived and verified", at 05 Apr, no `work_id`.
5. Handover to Support: HND-0048, "Support listed 2 gaps", at 10 Apr, no `work_id`.
6. Closure: no reference, "Not yet", tone `neutral`, detail "Needs hypercare, handover, retrospective", no `work_id`.

Each row also has a `short_title`. P-0101 also gets `delivery_agent` (the board's four checks) and `delivery_summary.note`. `next` keeps its existing value.

### Frame change: decision steps follow their task (general, small; `Steps.tsx` and `Workspace.tsx`)
A step with `task_id` is a link to the F-16 page only when `tasks[]` has a task with that id and `you_can_act: true`, and the page lock is off (the F-23 rule).
- When the task is present with `you_can_act: false`, the step is an unavailable control (`aria-disabled`, no `href`) described by the `cannotActCopy(reason, task).heading` sentence. For example, "This decision needs a PMO Lead." for `not_your_role`, or "You prepared Release gates · build 1.0.0, so someone else must review it." for `prepared_by_you`.
- When the task is absent, the step is unavailable with the default sentence.
- `disabled_reason` keeps priority, as today.

Every existing fixture with a `task_id` step already matches: W-2009, W-2208, W-2303.next, W-2304, W-2305, W-2309 are all `you_can_act: true` or carry `disabled_reason` or `reconcile`. Existing tests stay green.

### Proposal on E-WORK-ITEM: `workspace.links[]` kind `work`
`{key, label, target: {kind: "work", work_id}}` is drawn as a `Link` to `/work/{work_id}` only when `work_id` passes `RECORD_ID`; otherwise nothing is drawn. It is added to `proposals.ts` `workspaceLinks` and `Links.tsx` (part of G-44-2). Recorded, not built: G-44-1 `notices[]`, G-44-3 `context` on E-CONVERSATION-NEW, G-44-4 `agent.finished_at`.

### Decision (E-TASK-CLAIM, E-TASK-DECIDE through the F-16 page; unchanged)
- On W-2502, "Approve for release" and "Return with a note" link to `/work/W-2502/decide?task=T-2502`. The work page sends nothing to `/claim`, `/decision` or `/steps`.
- The F-16 page:
  - claims once;
  - sends `expected_revision` (the task revision) and CSRF;
  - refuses a blank note for Return before any request;
  - on 409, re-reads and shows the stale view;
  - on 403, shows that it cannot act;
  - on 5xx or a network error, shows its problem state, never "approved".
- After an approve, the mock applies `W-2502.approve.json`; back on `/work/W-2502` the page draws the ready state only from that re-read. A return or reject gets the generic F-16 outcome, and the item stays as it is (the returned board is part 2).
- **Permission and tenant:** the backend decides per task and record. A wrong-tenant or wrong-user read is a 403 or 404 and looks the same.

### Screen states
- **Loading, error, signed out, no access:** as above, on both routes.
- **Delivery tab:** rows; an empty state; Tola's card or the fallback summary; the note when returned; Next.
- **Release item:** waiting, decision, ready, and the negative fixtures W-2504 to W-2508.
- **Unknown:** a missing fact value, an `unknown` gate status, an `at.unknown` or a missing gate label reads "Unknown". Never blank, 0 or "-".
- **Restricted:** a section or item with `restricted: true` shows only its label.
- No animation under `prefers-reduced-motion`.

## Lanes
- **Frontend lane (Sonnet builder; D-64) owns:**
  - `frontend/src/features/projects/model.ts`: the `delivery` key in `ProjectTab` and `PROJECT_TABS` (path `/delivery`, no count), plus guards for the overlay fields.
  - `ProjectJourney.tsx`: a `delivery` branch in `ProjectView`.
  - A new `frontend/src/features/projects/DeliveryTab.tsx` with additive rules in `project-tabs.css` (tokens only).
  - `frontend/src/features/workspace/Steps.tsx` and `Workspace.tsx` (the authority rule, passing `item.tasks`), `proposals.ts` and `Links.tsx` (the `work` kind).
  - Fixtures `frontend/mock/fixtures/work/W-2501.json` to `W-2508.json`, `W-2502.approve.json`, `W-2510.json`; additive keys in `mock/fixtures/projects/P-0101.json`; `frontend/mock/proposals/delivery-release.json`.
  - Tests: new `frontend/tests/delivery-overview.test.tsx`, `release-gates.test.tsx`, `delivery-release-mock.test.ts`; `mock-contract.test.ts` (new fixtures, overlay checked and stripped); the four tab-list assertions; new `frontend/e2e/delivery-release.spec.ts`.
  - Factory files: `delivery/features/F-32/fidelity-exceptions.json`, `round-<N>/fidelity/**`, `round-<N>/build.md`.
- **Shared, read only:**
  - `src/features/decide/**`, `src/features/work-item/**` (import `AgentCard`, `TaskPanels` unchanged), `src/features/response/**`, `src/components/**`, `src/shell/**`, `src/api/**` including `schema.d.ts`, `src/styles/**`.
  - `Sections.tsx`, `StepForm.tsx` and `useWorkspaceStep.ts`: change only if a test proves a defect, and list it.
  - Existing fixtures (except the P-0101 addition), `mock/server.mjs`, `mock/projects.mjs`, `mock/workspace.mjs`: no change expected; the existing decide sidecar rule is enough.
  - `package.json`, the lock file, `playwright.config.ts`, `vitest.config.ts`, `architecture/**`, `design/**`, `apps/**`.
  - The protected `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json`.
- **Backend lane:** none. Record in `build.md`: G-43-1 to G-43-6, G-44-1 to G-44-4, G-F32-1, and the six questions at `gaps-d-delivery.md:47-50, 67-73`.
- **Integration owner:** the coordinator.
  - F-31 runs in parallel and reads E-PROJECT for the tab bar and a Planning link (G-42-7). It may touch `PROJECT_TABS`, `ProjectBar` and the same tab-list assertions.
  - F-33 renders through the same `Steps.tsx`, so the authority rule applies to it.
  - Whichever merges second merges the current base, keeps both tab changes, and reruns `delivery/checks.sh` and the e2e.
- **Ports:** app **4860**, mock **4861** (not used in any spec or config). Run `cd frontend && E2E_PORT=4860 MOCK_PORT=4861 npx playwright test e2e/delivery-release.spec.ts e2e/workspace.spec.ts e2e/work-item.spec.ts e2e/project-tabs.spec.ts`, with `timezoneId: 'Africa/Lagos'`. Run `df -h /System/Volumes/Data` first and stop under 3 GB; delete `frontend/test-results` afterwards. The e2e is not in `checks.sh`, so paste its output in build.md.
- **Review routing (medium risk):** technical (Sonnet), security (Opus: the authority rule, `auth` surface), UI (fidelity gate on 8 boards), UX (Sonnet), QA (Opus). Product acceptance is required.
- **Size:** about 900 to 1,300 lines, half of it tests and fixtures. One PR.

## Acceptance criteria
Fidelity command per board (swap `--board`, `--page`, `--width` and `--out`; cookie `psl_mock_persona=pm`; run on a production build: `next build`, `next start -p 4860`, mock on 4861):
```
node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs \
  --playwright <worktree>/frontend/node_modules/playwright/index.mjs \
  --board /Users/Hunchoo/psl-factory/design/canvas/project/SCR-44-desktop-decision.dc.html \
  --page "http://localhost:4860/work/W-2502" --width 1440 \
  --cookies psl_mock_persona=pm \
  --exceptions /Users/Hunchoo/psl-factory/delivery/features/F-32/fidelity-exceptions.json \
  --wait-ms 500 --out /Users/Hunchoo/psl-factory/delivery/features/F-32/round-<N>/fidelity/SCR-44-desktop-decision-1440
```

### Fidelity (8 boards, D-64, D-83)
1. **Scores.** One fidelity run per round covers all 8 boards in the Boards table. Every board has `coverageWithExceptions` = 100 and `visual` ≥ 90. A board at 70 or more but below 90 passes only with a D-83 waiver signed for that board in `fidelity-exceptions.json`, and only when the UI reviewer's side-by-side reading finds no fixable gap. No board passes under 70. — verify: the commands exit 0; `round-<N>/fidelity/scores.txt` lists board, width, coverage, visual, pass and waiver.
2. **Exceptions limited.** Each entry has `role`, `name`, `category`, `reason` and `approved_by`, and maps to a Conflicts number. None covers a value the data can supply (a name, date, reference, tag, count or sentence). — verify: file content; build.md.

### Delivery tab (SCR-43)
3. **The tab exists everywhere tabs are drawn.** `/projects/P-0101` and every other project tab show the tabs Journey, Delivery, Milestones 4, Documents 6, Money, Registers 6, Actions 9. Delivery links to `/projects/P-0101/delivery` and is selected there. The line tab bar on `/work/W-2501` shows the same seven, linked, with none current. An unknown tab (`/projects/P-0101/planning`) is still a 404 page. — verify: `tests/delivery-overview.test.tsx`; the updated `projects-journey.test.tsx` and `workspace.test.tsx` assertions; e2e.
4. **Rows from data.** `/projects/P-0101/delivery` shows six rows in the returned order, numbered 01 to 06. Each shows its title, reference (or "—"), the returned gate label with its returned tone, and the date or reason. Release gates links to `/work/W-2503` and Go-live acceptance to `/work/W-2510`. Hypercare, Archive, Handover and Closure have no link. Reordering the fixture reorders the page. A row with `state: "verified"` but a `gate.tone` of `uncertain` shows the uncertain tone. — verify: component tests on the fixture and modified copies; `grep -rn "Release ready\|Not yet\|Support listed" frontend/src` returns nothing.
5. **Nothing counted or ruled in the browser.** No "3 of 6" or similar count appears, and no closure sentence appears unless `delivery_summary.note` is returned. A copy without `note` shows no line-order sentence. A copy with five rows shows five and the heading "The delivery lines, in order". `grep -rniE "closure needs|retrospective|finance's confirmation" frontend/src` finds nothing. — verify: component tests; grep.
6. **Tola and Next.** With `delivery_agent`, the card shows its title, the four steps with their sources, "Checked 12 Apr 09:00" and "Ask Tola" (a link to `/assistant` that sends nothing). Without it, the existing summary of `agent_summary.text` appears. `next` is plain text with no link. — verify: component tests with and without `delivery_agent`; a recording `fetch` (no POST).
7. **Sub-nav (Conflicts 5).** At 1440 the Delivery tab shows Overview (current) and one entry per row, labelled `short_title` (or `title` when absent). Only Release and Go-live are links. At 390 the sub-nav is not drawn. — verify: component test; e2e at both widths.
8. **Empty and Unknown.** A copy with `delivery: []`, and one with no `delivery`, show "No delivery lines yet." A row with `at: {unknown: true}` shows "Unknown", and a row with no `gate` shows an "Unknown" tag. Neither shows blank or "0". — verify: component tests.

### Release item (SCR-44)
9. **Three states from data.** `/work/W-2501`, `/work/W-2502` and `/work/W-2503` each show their fixture's status label and tone, sections, steps, Next and links, and nothing else. W-2501 has no decision control. Its gate row reads "Waiting for PMO Lead", and its task panel reads "Only a PMO Lead can decide." (Conflicts 4). `grep -rnE "WAITING ON PMO LEAD|Approve for release|Release ready|PMO Lead" frontend/src` finds no new match. — verify: `tests/release-gates.test.tsx` at 1440 and 390.
10. **Decision controls only from `you_can_act`.**
    - W-2502 draws "Approve for release" and "Return with a note" as links to `/work/W-2502/decide?task=T-2502`.
    - W-2504 draws both as unavailable controls with no `href`, described by "This decision needs a PMO Lead.".
    - W-2505 does the same, with the `prepared_by_you` sentence.
    - W-2506 draws both unavailable, with the default sentence.
    - Personas `pm`, `finance_lead` and `ceo` see the same controls for the same fixture.
    - The diff adds no `/me` read under `frontend/src/features/workspace` or `features/projects/DeliveryTab.tsx`.

    — verify: component tests across fixtures and personas; diff.
11. **No decision write from the work page.** Pressing either link on W-2502 navigates only. A recording `fetch` sees no POST to `/claim`, `/decision` or `/steps` from the work page. — verify: component test.
12. **Approve ends on ready only through the response.** In the e2e:
    1. Open `/work/W-2502`, press "Approve for release" and land on the F-16 page.
    2. The F-16 page sends one claim and one decide with `verdict: approve`, `expected_revision` 1 and the CSRF header.
    3. Back on `/work/W-2502`, the page shows "Release ready", the banner, the readiness note, Next and "Open go-live" (linking to `/work/W-2510`).

    With `X-Mock-Scenario` set to 409, 500 or a network failure on the decide, the F-16 page shows its stale or problem state. The work page still shows "Your decision", and neither page shows "approved" or "Release ready". — verify: e2e with recorded requests; component tests of the F-16 flow (existing) kept green.
13. **Return needs a note.** On the F-16 page for T-2502, Return with an empty note sends nothing and shows the note message under the field. With a note it sends one decide (`verdict: return`), and the work page then shows the generic outcome with no "Release ready". — verify: e2e.
14. **Verified only from the backend (INV-AGENT).** W-2508, whose agent step "Mark release ready" is done, shows no green banner, no "Release ready" status and no "Open go-live". The banner is green on W-2503 only because `status.tone` is `verified`: a copy with the same text and tone `person` draws the warning banner. — verify: component tests.
15. **Unknown, not zero.** On W-2507, Open issues reads "Unknown", the unknown gate reads "Unknown", and Tola's checklist has no time line. Nothing shows blank or "0". — verify: component test.
16. **Links only from data.** "Open go-live" appears only with a `work` link whose `work_id` is a valid id. A copy with `work_id: "../x"`, or an unknown kind, draws nothing. W-2501 and W-2502 show no "Open go-live". — verify: component tests.

### Access, phone and quality
17. **Access.**
    - A 401 on either route shows the signed-out state with `next` set to that route.
    - A 403 and a 404 look the same on `/work/W-2502` and on `/projects/P-0101/delivery`, with no title, project, reference or row text in `document.body.textContent`.
    - The `ceo` persona (not on P-0101's persona list) and `/projects/P-0099/delivery` get the no-access view with no further call.

    — verify: component tests with `X-Mock-Scenario` and a recording `fetch`.
18. **Phone.** At 390 both routes are one column, with the desktop sections in the desktop order (Conflicts 6). There is no sideways scroll. Every button, tab, row link and standalone link is at least 44px tall (D-92c). — verify: e2e at 390 measuring `getBoundingClientRect`.
19. **Accessibility.** There are no axe violations (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`) at 1440 or 390 on: the Delivery tab and its empty state; W-2501, W-2502, W-2503, W-2504 and W-2507; the no-access views. Unavailable decision controls expose their reason through `aria-describedby`. Tags and status are text, not colour only. Focus is visible, and nothing animates under `reducedMotion: 'reduce'`. — verify: `e2e/delivery-release.spec.ts`.
20. **Tokens and components only.** New UI imports from `@/components` (`Tabs`, `Tag`, `Panel`, `Link`, `Unknown`, `EmptyState`, `Callout`) and adds no local button, tag, panel or tab. `grep -nE "#[0-9a-fA-F]{3,8}\b|rgba?\(|hsl\("` on this feature's CSS diff returns nothing. — verify: diff and grep.
21. **Mock matches the contract.**
    - `delivery-release-mock.test.ts`: W-2501 to W-2508, W-2510 and `W-2502.approve.json` validate against the generated E-WORK-ITEM schema once the `links` proposal is removed.
    - P-0101 validates against the E-PROJECT schema once the overlay keys are removed, and the overlay keys validate against `mock/proposals/delivery-release.json`.
    - Each `you_can_act: true` task appears only in a fixture whose status is "Your decision".
    - Approve on T-2502 applies the sidecar once, and a repeat decide answers 409.
    - A decide on T-2504 answers 403.

    — verify: `cd frontend && npx vitest run tests/delivery-overview.test.tsx tests/release-gates.test.tsx tests/delivery-release-mock.test.ts tests/mock-contract.test.ts`.
22. **Contract not extended.** `git diff --stat` shows no change in `frontend/src/api/**`, `apps/**`, `architecture/**`, `design/**`, `src/shell/**`, `src/features/decide/**` or the protected paths. No existing fixture is edited, except the additive `delivery`, `delivery_agent` and `delivery_summary` keys in `P-0101.json`. Every overlay field is listed in build.md as a contract proposal. — verify: `git diff --stat`; build.md.
23. **Existing behaviour not weakened.** `delivery/checks.sh` passes. `tests/workspace*.test.*`, `work-item*.test.tsx`, `decide*.test.tsx`, `projects*.test.tsx`, `project-tabs.test.tsx`, `issue-detail.test.tsx`, `minutes*.test.*` and their e2e specs pass. No assertion is removed or loosened; the four tab-list assertions only gain "Delivery". — verify: `delivery/checks.sh`; e2e output in build.md; `git diff` of `tests/`.
24. **No overclaim.** build.md and the PR carry the "What is released" section: contract mock only, nothing released or deployed, no authority configured, and the two product questions open. — verify: file content.

## Out of scope
- Part 2 boards: SCR-44 readiness, returned and owner-needed. That includes "Send for decision again" (`resubmit`), "Open Setup › Roles" and any role assignment.
- Part 3 boards: SCR-45 go-live, in all states. W-2510 is only a plain link target.
- An in-page Approve or Return, an in-page note box, and any change to the F-16 page, including hiding Reject.
- Any deploy or "mark released" control. Setting release ready from the page or from agent text.
- Choosing, naming or configuring an approver or role.
- Counting done lines, composing gate states or closure rules, and starting a delivery line from SCR-43 (G-43-6; no Start control).
- The sub-nav on the work item (Conflicts 5 Option B), and a second E-PROJECT read in the frame. The Planning tab (SCR-42, F-31).
- G-43-1, G-43-4, G-44-1, G-44-3 and G-44-4 as built fields. Context on E-CONVERSATION-NEW.
- Backend, OpenAPI, `schema.d.ts` regeneration, `architecture/**`, `design/**`, `src/shell/**`, new npm dependencies.

## Assumptions
- Fixtures sit on P-0101 Lagoon Health, not the boards' Tamarind Loans. Reason: the crumb, title and tab counts then agree with the project the rows belong to (coordinator instruction). P-0101's older Journey line "Prepare for release · REL-0077" is unrelated sample data and is left as it is.
- Fixture ids are W-2501 to W-2510 and T-2501 to T-2508. Reason: unused, and outside F-31's and F-33's ranges.
- The mock's approve goes straight to the ready item, skipping readiness. Reason: readiness asks for it, and the readiness board is part 2; the real factory sets ready only after its check (backend question).
- All boards are served to the `pm` persona; the decision state comes from the fixture's `you_can_act`. Reason: the mock has no PMO Lead persona, and authority must come from data, never from persona.
- A decision step whose task is missing from `tasks[]` is unavailable. Reason: readiness binding rule 1 ("only when `tasks[]` carries the decision"). No existing fixture relies on the opposite.
- Rows are numbered from their returned position. Reason: the board draws 01 to 06; a number is display, not a business count.
- An absent `delivery[].at` draws nothing, and `at.unknown` reads "Unknown". Reason: an absent date means not applicable (the closure row); unknown is a stated value (INV-UNKNOWN).
- "No delivery lines yet." and "The delivery lines, in order" are frontend wording, not business rules. Reason: the sources say nothing about them, and the approver may escalate.
- G-43-3 gets an optional `title` for the card heading ("Checked where delivery stands"). Reason: otherwise the heading would be hard-coded agent wording.
- The ready banner uses the existing note-only section, not G-44-1 `notices[]`. Reason: it is the smallest reuse, and it already takes its tone from the returned status (F-30).
- Ports are 4860 and 4861. Reason: not used by any spec, config or the D-112 demo servers.
