VERDICT: CHANGES
REVIEWER: reviewer-ui
COMMIT: 9f594712fb1c9a7ac4283d41d121707c4f96d45f
AUTHORITY: delivery UI review

## Summary
- I read the builder's single fidelity run (round-1/fidelity, port 4871) for all 8 boards and checked it against my own screenshots of the head build on http://localhost:4873 at 1440 and 390. The layout matched. I made no writes on the mock. The mock session was signed in as the Finance Lead persona, so I used it for layout only.
- Coverage is 100% with exceptions on all 8 boards. Visual scores run from 76.7 to 86.7, and every board has a proposed D-83 waiver. Most of the gap is the approved F-17/F-30 frame or D-113 content: the top bar, crumbs, PM subtitle, line tab bar, no sub-nav on SCR-44, Lagoon Health sample data, desktop wording on phones and the checklist section for Tola's checks. Some of the gap is fixable, though, so the waivers can't be signed as written. Their stated basis is "frame plus listed Conflicts" only.
- Blocking items:
  - On SCR-43, the Overview sub-nav item is not drawn as selected.
  - On SCR-43, the agent card is nested inside a second agent panel, which makes the body text blue and draws a double frame.
  - On SCR-43, the number boxes and row styling differ from the board.
  - On SCR-43, one fixture tone is wrong.
  - On W-2501, a blank band appears above the release gates.
  - On W-2501, the Planning decision gate shows two conflicting statuses.
  - Several frame restyles are in neither the spec nor the exceptions file.
- Tokens: the new CSS in project-tabs.css uses existing tokens only, with no hex, rgb or one-off colours. Shared components (Panel, Tag, AgentCard, psl-tabs, psl-btn) are reused, but two are used wrongly (UI-1-1, UI-1-2).
- Phone (D-92c): nothing scrolls sideways at 390. The delivery row links, Ask Tola and the decision controls are at least 44px tall. The 24px-tall History link at 390 belongs to the existing frame (UI-1-10).

## Findings
1. UI-1-1 | blocking | medium | frontend | SCR-43-desktop sub-nav: Overview is not shown as the current item, and the strip is the wrong component size. Expected (board): separate 36px items with a 4px gap and Overview filled ink (#1F2427) with white text. Actual: a joined 44px `psl-tabs` strip in which Overview is white. The shared selected style keys on `aria-selected`, but the page sets `aria-current="page"` and adds no matching rule, so on 4873 Overview has background rgb(255,255,255). `setup.css:15-17` already has the token-based rule for `.psl-tab[aria-current="page"]`. Paths: frontend/src/features/projects/DeliveryTab.tsx:30-46 and project-tabs.css:52.
2. UI-1-2 | blocking | medium | frontend | SCR-43-desktop and SCR-43-mobile, Tola's check: the component is used wrongly. `AgentCard` sits inside `Panel kind="agent"`. That draws two blue frames, and `components.css:73` turns every step line blue (`--action-ink`), which leaves the dark tick barely visible on the blue box. The card head becomes an uppercase blue Archivo panel title. Expected (board): one agent card. Its head has the avatar, "Checked where delivery stands" in sentence-case ink, the "Tola · …" line and the DONE tag. Step text is ink 14px with white ticks, and "Checked 12 Apr 09:00" and "Ask Tola" sit on one footer line under a rule. Actual: a nested card with blue body text, and Ask Tola on its own line below. Path: frontend/src/features/projects/DeliveryTab.tsx:98-111.
3. UI-1-3 | blocking | low | frontend | SCR-43-desktop and SCR-43-mobile rows: the row styling differs from the board.
   - Expected: each line number in a 28px box with a 2px ink border and mono 11px text; row padding 12px 0, giving about 54px rows; linked titles in ink and underlined.
   - Actual: the number is plain muted mono text; rows are about 68px (padding `--space-3 --space-4`); linked titles use the action blue.
   - Path: project-tabs.css:57-60.
4. UI-1-4 | blocking | low | frontend | SCR-43, Hypercare "Running" tag: drawn blue (`tone: "agent"`) where the board draws it amber. The tone comes from the fixture, so the data can supply the board's colour, and no exception covers it. Path: frontend/mock/fixtures/projects/P-0101.json, `delivery_hypercare.gate.tone`.
5. UI-1-5 | blocking | medium | frontend | SCR-44-desktop (W-2501) layout: the "Planning decision" task panel fills the frame's aside column on a row of its own. That leaves a blank band about 240px tall, the full width of the main column, to its left. The Release gates and checks panels are then pushed below it at full width. Expected (board): the gates panel starts at the top of the main column with the agent panel beside it. The spec (Conflicts 4) keeps the panel as an extra element but does not approve this gap. Cause: `work-columns` renders an empty `work-column` when the line item's main area is empty (WorkItemOverview.tsx:724-735). Fix: don't render an empty main column (for example, put the task panel in the workspace side column), or take Conflicts 4 Option B with the design engineer.
6. UI-1-6 | blocking | medium | frontend | SCR-44-desktop and SCR-44-mobile, "Planning decision" gate: the row shows two statuses that disagree. An inline "WAITING FOR PMO LEAD" tag and the line "Held by PMO Lead" sit on the left, and a right-aligned "IN PROGRESS" tag (from `status: "now"`) sits on the right. Expected (board): one right-aligned "WAITING FOR PMO LEAD" tag, like the other gates. Path: frontend/mock/fixtures/work/W-2501.json, gates item G-3. Fix the fixture or the frame mapping, or record it as an exception for the design engineer.
7. UI-1-7 | blocking | low | frontend | Restyles that are in neither the spec's Conflicts nor fidelity-exceptions.json. The D-83 waivers say they cover only "listed Conflicts 5, 6, 7, 9 and 10" differences, so each needs a fix or a listed exception:
   - (a) SCR-44-desktop and SCR-44-mobile: the gates note is an amber warning callout inside the panel. The board has a blue info callout below the panel. Amber reads as a problem.
   - (b) SCR-44 decision, desktop and phone: "What you're deciding" values are plain mono text with bold labels. The board has toned tags: green "4 OF 4 STAGES BUILT" and "APPROVED 22 MAR", amber "1 MEDIUM · 0 HIGH". The `facts` kind drops the colour meaning.
   - (c) SCR-44 ready, desktop and phone: the readiness note statuses are grey inline tags with a "Tola" byline. The board has right-aligned mono words.
   - (d) SCR-44 decision: "Claim it first" appears under Approve for release (from the fixture's `claim_required`). It is not on the board.
   - (e) SCR-44-mobile-decision: Approve and Return sit side by side at half width with the consequence above them. The board stacks them full width.
8. UI-1-8 | non-blocking | low | frontend | Problems in fidelity-exceptions.json:
   - The SCR-43 links Hypercare, Archive, "Handover to Support" and Closure, and "Record what Support needs…", are filed as `no field`. But `work_id` and `next` are fields; the fixture simply leaves them out, because no work item exists for those lines and P-0101 `next` is shared with the Journey board. File them as `sample data`.
   - The sub-nav reasons repeat "Conflicts 5: Conflicts 5:".
   - The SCR-43 "Tola · PMO agent · done" entry cites Conflicts 9, which covers SCR-44 only.
9. UI-1-9 | non-blocking | low | frontend | SCR-44-desktop-ready and SCR-44-mobile-ready: "Open go-live" is a secondary outlined button in the links row. The board has a primary blue button in the Next panel (desktop) or the phone bar. Spec Conflicts 10 records this as `frame layout`, but the exceptions file has no entry for the restyle. Add one so the design engineer signs it with the waiver.
10. UI-1-10 | non-blocking | low | frontend | All SCR-44 phone boards: the frame's History link is 42x24px at 390, below the 44px target. It comes from the existing F-30 frame, not from this diff; record it for a frame fix.

## Exceptions check
- I traced every entry in fidelity-exceptions.json to a spec Conflicts item:
  - Items 5 and 11 (`no field`).
  - Items 7, 8, 9, 10 and 13 (frame, phone wording, frame layout).
  - Item 14 (sample data).
- No entry hides a value the data supplies, except the category mislabels in UI-1-8.
- All entries remain `builder proposal, pending design engineer`.

## Waivers
The visual gaps are mostly frame, so the scores are not the problem. The waivers become signable once UI-1-1 to UI-1-6 are fixed and the UI-1-7 items are fixed or listed. The design engineer still has to sign them.
