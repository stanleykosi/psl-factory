DECISION: READY
RISK: medium
SURFACES: ui, api, auth, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-32 is part 1 of FE-DELIVERY-RELEASE. It covers 8 boards, the D-64 cap: SCR-43 delivery overview (2) and SCR-44 release gates in default, decision and ready (6). The outcome is the Delivery tab: a person opens a project's Delivery tab, sees the six lines, opens Release, and follows the release gates from "waiting on PMO Lead" through the PMO Lead's decision to "release ready". That is one PR.
- I changed the suggested split: the decision board replaces readiness. The PMO Lead's approval is the human decision this line exists for, and the authority display (who may decide) is the part that most needs building and testing first. Readiness only shows the agent at work, which the frame already renders, so it goes in part 2 with returned and owner-needed.
- The gates are met. FE-DELIVERY-RELEASE has `gate_ids: []` and "Unresolved gates: none" (architecture/packages/v7/delivery.md:2281-2315). SCR-43 and SCR-44 are in the 13 Nov client approval (design/review.json:51-52), and the D-89 "+ Start" exception is recorded. Both dependencies are merged: FE-WORKSPACE-FRAME (F-17) and FE-M3-PROJECTS (F-07). The M-6 gates (D-LINE-WORKSPACE, D-CHANGE-DECIDERS, D-DECISION-VARIANTS) do not block this task. D-LINE-WORKSPACE and D-PROJECTS-VIEW are still `proposed`, so they count only under the recorded exception (architecture/sources/decisions-2026-11-15.md items (g) and (i)): contract mock only, nothing released.
- The endpoints are all in frontend/src/api/schema.d.ts: E-PROJECT with the `delivery[]` proposal (lines 2911-2933), E-WORK-ITEM, E-TASK-CLAIM, E-TASK-DECIDE, E-WORK-STEP and E-CONVERSATION-NEW. The backend handoff lists no blocking gap for SCR-43 (0 blocking, 6 nice-to-have) or SCR-44 (0 blocking, 4 nice-to-have) (delivery/backend-handoff/gaps-d-delivery.md:32-73, 180-181).
- I did not run `design.py check` (no shell in this role). The spec writer or builder runs it first and stops if it fails.

## Scope
**Outcome (one):** a person on a project opens the Delivery tab (`/projects/{case_id}/delivery`, SCR-43) and sees the six delivery lines in order, each with its state and gate label, plus Tola's summary and the next step. From the "Release" row they open the release-gates work item (`/work/{work_id}`, line key `delivery_release`, SCR-44), which shows the four gates.
- The PM sees it waiting on the PMO Lead.
- The PMO Lead sees "YOUR DECISION" and decides on the existing F-16 decision page.
- Afterwards everyone sees "RELEASE READY" with Tola's readiness note and "Open go-live".
- All of it runs on the contract mock.

**Boards (8):**
- SCR-43-desktop, SCR-43-mobile: the overview rows (title, reference, gate label and tone, link through `work_id`, a dash row when `work_id` is absent), the line-order sentence, Tola's "Checked where delivery stands" card and the Next line.
- SCR-44-desktop, SCR-44-mobile (default): "RELEASE · WAITING ON PMO LEAD", the gate checklist (PMO Lead assigned DONE, Client UAT DONE · 22 MAR, Planning decision WAITING FOR PMO LEAD, Release readiness NOT YET), the "don't authorise the deployment" note, and Tola's finished checks.
- SCR-44-desktop-decision, SCR-44-mobile-decision: the "What you're deciding" facts, the "Decide · PMO Lead" panel with its consequence sentence, and Approve for release / Return with a note.
- SCR-44-desktop-ready, SCR-44-mobile-ready: the verified banner, "Readiness note · by Tola" (contents, rollback plan, incident contacts), and Next with "Open go-live".

**Task and endpoints:** FE-DELIVERY-RELEASE (R-PROJECT, R-WORKITEM). Acceptance: A-PROJECTS-VIEW for SCR-43 and A-WORKSPACE for SCR-44. A-RESPONSE belongs to part 3.
- Reads: E-PROJECT for the tab, rows, tab counts and delivery sub-nav, and E-WORK-ITEM (`workspace`, `tasks[]`, `agent`).
- Decision writes: E-TASK-CLAIM and E-TASK-DECIDE, only through the F-16 decision page. In the frame a step with a `task_id` is a link to `/work/{id}/decide?task=…` (Steps.tsx:56-69; F-17 Conflicts 4; precedent F-23 spec Conflicts 3).
- No new endpoint and no new write.

**Reuse, not rebuild:**
- The F-17 workspace frame and the line layout: `features/workspace/**` and `features/work-item/**`, including `ProjectBar` at WorkItemView.tsx:133.
- `ProjectJourneyPage` and `PROJECT_TABS`: add one `delivery` tab at features/projects/model.ts:26-37, and it appears in the line tab bar too.
- `features/decide/DecidePanel.tsx` and `frontend/src/components/` (D-91).
- New v7-typed fixtures in an unused W- range (W-24xx and W-29xx are taken), plus an E-PROJECT fixture with `delivery[]`.
- A new `frontend/mock/proposals/delivery-release.json` overlay for the proposals below.
- The mock handler returns the ready fixture after an approve. A return gives the generic outcome; the returned board is part 2.

**Contract proposals (mock overlay only; record each in build.md for the backend developer):**
- G-43-1 `delivery_summary {reference, done, total}`: "DLV-0052 · 3 OF 6 DONE". Until it is confirmed, leave it out. The browser never counts `verified` rows (D-PROJECTS-VIEW: backend-composed).
- G-43-2 `delivery[].reference`, `.at`, `.detail`: per-row REL-0091 and the date, and the "needs hypercare, handover, retrospective" reason. A missing date reads Unknown.
- G-43-3 `delivery_agent {agent, status, finished_at, steps[]}`: Tola's checks card. The fallback is `agent_summary.text`.
- G-43-4 `next_action {text, work_id?}`: "Open the handover". Until it is confirmed, `next` shows as plain text with no link.
- G-43-5 `delivery_summary.note`: "Closure needs all of them, a saved retrospective and Finance's confirmation" is a business rule, and Finance confirmation is itself undecided (flow-audit 5.4). Show it only when the backend returns it. Never hard-code it.
- G-44-1 `workspace.notices[]`: the ready banner. G-44-2 `workspace.links[]`: "Open go-live". G-44-3 `context {work_id}` on E-CONVERSATION-NEW: "Ask Tola". G-44-4 `agent.finished_at`: "Finished 23 Mar 10:12". Each renders only when the data supplies it.
- G-F32-1 (new): the delivery sub-nav on every SCR-44 board (Overview, Release, Go-live, Hypercare, Archive, Handover, Closure) uses short labels. Proposal: `delivery[].short_title`, read from E-PROJECT `delivery[]` by `case_id` from `workspace.context.project`. A row links only when it has a `work_id`. The spec settles whether the sub-nav is built or recorded as a frame exception.
- G-43-6 (doc only): the factory opens each next delivery work item when the previous output is verified. SCR-43 has no Start control and none is added.

**Exceptions for the design engineer (frame items, as in F-23 Conflicts 11 and F-30):**
- the "Planning" project tab (SCR-42, a different task);
- the selected-tab state in the line tab bar (WorkItemView.tsx:129-132);
- the inline Approve/Return becoming links to the F-16 page;
- the F-16 verdict words versus "Approve for release / Return with a note".

Line boards follow the D-83 standing waiver: 100% coverage after exceptions, the side-by-side review, visual at least 70, and a signed waiver for each board.

**Later parts (16 boards):**
- Part 2, 6 boards: SCR-44 readiness, returned and owner-needed, desktop and phone.
  - Returned and "Send for decision again" (`resubmit` step) rest on D-RETURN, an open working assumption.
  - Owner-needed ("no one holds the PMO Lead role", "Open Setup › Roles") touches D-ADMIN-AUTHORITY (open). The page only shows the hold; it never assigns a role.
  - Readiness needs G-44-4 (`pending` step status).
- Part 3, 10 boards, over the cap, so split it:
  - 3a: SCR-45 default, signatures and accepted (6).
  - 3b: SCR-45 changes and declined (4).
  - SCR-45 has two blocking gaps that need a business or backend answer: G-45-1 (the PM countersignature) and G-45-2 (what a declined go-live does to the other lines). It also depends on D-RESPONSE-VIEW and D-ALERT-PROVIDERS. Expect NEEDS-INFO on 3b, and on 3a for G-45-1.

**Out:** the part 2 and 3 boards; any deploy (no step deploys anything); any role assignment; backend, OpenAPI, `schema.d.ts` regeneration, `architecture/**` and `src/shell/**`.

## Binding rules for the spec
1. **Authority comes only from the backend.** The Decide control appears only when `tasks[]` carries the decision and `you_can_act` is true. Otherwise show `cannot_act_reason` as returned, including `prepared_by_you`. Never derive it from `/me` roles, the board's names or the crumb (INV-ACCESS). Who may release is the task's `required_role` from configured authority. Fixtures may name Kemi Adebayo as sample data only, and no approver is invented as policy. 403 and 404 look the same.
2. **Verified comes only from the backend.** "RELEASE READY" and "verified" appear only from the work `state`/`workspace.status` the backend returns. The agent step "Mark release ready" is never the verified output (INV-AGENT). Tola's text shows as returned.
3. **Decisions use the F-16 page.** It claims, requires a note to return, sends `expected_revision` and CSRF, and handles 409 by re-reading. A failed or timed-out decision never shows "approved".
4. **Unknown is not zero.** Unknown values show "Unknown", never blank or zero (INV-UNKNOWN), and that includes "Open issues". Gate status, tone and labels come from the data. The frontend computes no done count, no gate state and no closure rule.
5. **Delivery rows follow the response.** The row order is as returned. A row the person may not open has no link. The backend question on restricted rows (gaps-d-delivery.md:48) is recorded, not decided.
6. **Design-system rules.** Tokens and components only; labels on every control; 44px phone targets (D-92c); reduced motion respected. Axe at 390 and 1440. One fidelity run per round over the 8 boards (D-64). Sonnet builder.

## Risk
RISK is medium:
- The work has several behaviours on two routes: a new project tab and a line workspace with three states.
- It sits on the shared F-17 frame and the F-16 decide page, against two proposed contracts (D-LINE-WORKSPACE, D-PROJECTS-VIEW), and adds G-F32-1 to the additive proposals.
- It is not high: no money, migration or deploy effect, no new write endpoint, and the decision reuses the tested F-16 claim and decide path on the mock.

SURFACES:
- `auth` is ticked because the page displays a release decision. The security lens must confirm the decide control follows `tasks[].you_can_act` and `required_role` only.
- `product-decision` is ticked for open business questions: the gate is labelled "Planning decision" while the buttons say "Approve for release", and planning and costing must precede the signed SOW. D-ROLE-PMO's scope (architecture/model.json:753-764) names closure, commercial approvals and escalations, not release. Both are backend or PSL confirmations (gaps-d-delivery.md:68-73). They hold the real transition, not this mock build.

PRODUCT-ACCEPTANCE is required because the Delivery tab and the release-gate flow are new to the client.

## Questions
None for this part. Backend confirmations hold the real write, not the mock build:
- which decision the gate is, and that it is a PMO Lead task scoped to the project;
- that "release ready" is set by a deterministic factory check;
- that nothing deploys;
- how restricted rows appear in the overview.

They are listed at delivery/backend-handoff/gaps-d-delivery.md:47-50 and 67-73.
