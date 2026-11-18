# Handover to Support: Tola's draft is published, the PM records Support's reply with proof, gaps go back for v2, and "acknowledged" shows only when the backend verifies it (contract mock only)

> Tasks: FE-DELIVERY-CLOSURE, part 1 of 3 (R-WORKITEM, R-RESPONSE; acceptance A-WORKSPACE and the A-RESPONSE frontend half for SCR-48, with A-WORKITEM, A-PROJECT-TABS and the F-17, F-18, F-30, F-31 and F-32 tests kept green; R-DECIDE belongs to part 3). Architecture: package `architecture/packages/v7`, manifest digest `f6231d20b4fdeabbdca9bde5986a0a7883536f1a5cafc883848ef62dd6d4b624`; FE-DELIVERY-CLOSURE at `architecture/packages/v7/delivery.md:2350-2382`, `gate_ids: []`, "Unresolved gates: none"; depends on FE-WORKSPACE-FRAME (F-17, merged). Endpoints, all already typed in `frontend/src/api/schema.d.ts`: E-WORK-ITEM (`:54`), E-WORK-STEP (`:715`), E-TASK-CLAIM (`:96`), E-RESPONSE (`:180`, `action` enum `:2455`, variant `support_handover` `:1434`), E-EVIDENCE-UPLOAD (`:159`), E-WORK-ACTION (`:201`), E-PROJECT (`:264`). This feature changes no generated type. Gaps: `delivery/backend-handoff/gaps-d-delivery.md:135-150` (G-48-1, G-48-2 mock only; G-48-3 needs no field, see Contract). Decisions consumed: D-LINE-WORKSPACE and D-RESPONSE-VIEW (both `proposed`, under the recorded exception `architecture/sources/decisions-2026-11-15.md` items (g), (i)), flow-audit conflict C closed on 13 Nov (Support has no login; the PM records the reply with proof), D-64, D-83, D-89, D-91, D-92c, D-99, D-104, D-111, D-112, D-113. Setup rule `delivery.handover_review` is Not set (`frontend/mock/fixtures/setup/delivery.desktop.json:52-63`). Design: client-approved canvas version 1794581312-b166 (13 Nov 2026; SCR-48 at `design/review.json:56`), republished with "+ Start" as 1794762832-cab1 (D-89). `python3 /Users/Hunchoo/software-factory/packages/design/design.py check --project /Users/Hunchoo/psl-factory` was run for this spec on 18 Nov: `EXCEPTION`, `passes: true` (design_sha256 `2859ab21…3d82`, D-89 frame-only change). Screens: SCR-48, 8 artboards in `design/canvas/project/`: `SCR-48-desktop`, `SCR-48-mobile`, `SCR-48-desktop-record`, `SCR-48-mobile-record`, `SCR-48-desktop-gaps`, `SCR-48-mobile-gaps`, `SCR-48-desktop-received`, `SCR-48-mobile-received`. Written against F-32's branch head `5bab76ae` (worktree `/Users/Hunchoo/psl-factory-worktrees/f-32`) and F-31's head `9b73aacf`. Models: `delivery/features/F-32/spec.md` (shape), `F-31/spec.md` (response form in the workspace), `F-28/spec.md` (sent and held).

## Build starts only after F-32 is in dlv-00 (read first)
- **F-32 must be merged into dlv-00 before any F-40 code is written.** Every SCR-48 board is drawn inside F-32's Delivery tab. F-40 uses F-32's `PROJECT_TABS` `delivery` tab, its `work` link kind (`proposals.ts`, `Links.tsx`), its "decision steps follow their task" rule (`Steps.tsx`) and its P-0101 `delivery[]` rows. The F-40 branch is cut from dlv-00 after that merge, never from F-32's branch.
- **F-31 must be in dlv-00 too.** The record form reuses F-31's `frontend/src/features/workspace/ResponseDrawer.tsx` flow and its 44px chip-remove rule (F-31 round 3, `workspace.css:252`). F-31 round 3 passed every review at `9b73aacf`. If F-31 is not merged when F-32 is, the coordinator waits for it. The builder does not copy F-31 code into F-40.
- **F-34 edits the same P-0101 `delivery[]` fixture** (it adds a `work_id` to the Hypercare row). F-40 adds exactly one key, `"work_id": "W-3704"`, to the Handover to Support row and changes nothing else in `P-0101.json`. Whichever of F-34 and F-40 merges second merges the current dlv-00, keeps both `work_id` keys and both test edits, and reruns `delivery/checks.sh` and both e2e specs.

## What is sent, and what stays held
- **On the contract mock, nothing is sent to Support and nobody at Support receives anything.** "Publish to Support" is a mock step (G-48-2: no Support recipient or channel exists in `architecture/packages/v7/integrations.csv`). Every "published", "received", "acknowledged", "Femi Ojo" and "verified" on these boards is fixture text, returned the way a backend would return it. The PR and `build.md` must say so. They must not claim a working handover, a send to Support or a Support receipt.
- **The page never says sent, published, received or acknowledged on its own.** Those words appear only where the re-read response's `workspace.status`, section text or `receipt` says so. A failed, refused, stale or timed-out Publish never shows "published". After an uncertain result the only action is reconcile: there is no resend and no new key (INV-RESEND).
- **Support's reply is recorded by the PM, under the PM's name, with proof** (flow-audit conflict C, closed). Support never logs in, and no text says Support logged in, signed or sent anything through the factory.
- **Held, because a product or backend decision is open:**
  1. **Whether a handover needs a review.** The Setup rule `delivery.handover_review` is Not set. The page shows whatever the response returns. The hold fixture (W-3702) shows "Review needed?" as Unknown, with no Publish control (Conflicts 1). No review decision is built.
  2. **The real send to Support** (G-48-2): the recipient, the channel and the receipt word.
  3. **Received and Gaps found as response actions, and the list of gaps** (G-48-1). These are a mock overlay: `approved` = Received and `changes_requested` = Gaps found, with labels from `actions[].label`, plus a `gaps: string[]` field.
  4. **What closes a gap**: only a later "received, no gaps" reply on v2, or each gap on its own (`gaps-d-delivery.md:148`). The page shows each gap's status as returned.
  5. **Closure.** "See what closure needs" goes to a plain work item. Closure is parts 2 and 3.
- **No money, no decision authority, no approver.** Nothing on these pages changes an invoice, a receipt or an allocation.

## Conflicts with the boards (for the design engineer, before the build)
"Recommend" is what this spec builds if no answer comes. Each difference becomes an entry in `delivery/features/F-40/fidelity-exceptions.json` with `approved_by: "builder proposal, pending design engineer"` until it is signed. Items 1 to 5 need an answer: 1 is a product question for PSL, 2 is for the backend, and 3 to 5 are design calls. Items 6 to 10 are layout. Items 11 to 14 are exceptions to sign. A "proposal" is a field built on the mock only; the backend developer may change or refuse it.

### Need an answer
1. **"Review needed? NO · BELOW THE RULE'S THRESHOLD" while the rule is Not set (product question for PSL).** The default board shows a value that no setting supports yet. PSL has not said when a handover needs review.
   - **Recommend:** two fixtures. W-3701 is the board, marked sample, with the board's words returned as a tag; the fidelity run scores this one. W-3702 is the hold: "Review needed?" reads Unknown, there is no Publish control, and the returned Next sentence says publishing waits for the rule. Neither phrase is written in `src/`. PSL sets `delivery.handover_review` in Setup › Rules; the backend then serves one or the other.
   - **Option B:** score the default board on the hold. The board's Publish button and its value then become listed differences.
2. **What "Publish to Support" sends (backend, G-48-2).** No Support recipient or channel is defined.
   - **Recommend:** on the mock, Publish is a step with `sends: true`. The status reads "Published 08 Apr" only after the re-read says so. An unknown result shows the existing uncertain banner and reconcile panel. The real send waits for the backend to add the Support recipient and channel.
   - **Option B:** hide Publish until G-48-2 is built. This blocks the flow on the mock; not recommended.
3. **Where the reply form opens.** Both record boards draw the form in place on the work item, with no button to open it. F-31's form opens in a Drawer.
   - **Recommend:** draw the form in place, as the boards do. The trigger is a workspace step `record_reply` whose `task_id` names a `support_handover` task in the same response that this person can act on (`you_can_act: true`). The panel title is the step's label. The flow is F-31's (`useResponse`, claim only when asked, one record per press, re-read on 409 or error), hosted in a `Panel` instead of the `Drawer`.
   - **Option B:** a "Record Support's reply" button that opens F-31's Drawer. The desktop record board would then not match.
4. **How the gaps are typed.** The board draws one "Gaps" box with numbered lines.
   - **Recommend:** one labelled text box, shown only when "Gaps found" is chosen. Each non-blank line is one gap, trimmed and sent in order as `gaps[]` (G-48-1). Gaps found needs at least one gap before Record turns on. Received sends no `gaps`.
   - **Option B:** an "Add a gap" control with one field per gap. That means more controls than the board draws.
5. **The "genuine" tick.** E-RESPONSE needs `attested: true`, and the boards draw no tick.
   - **Recommend:** draw F-18's short tick, "I confirm this response is genuine.", above Record at both widths. The person vouches for the proof. Listed as `extra element`.
   - **Option B:** send `attested: true` with no tick. Not recommended, because the person would vouch without being asked.

### Layout (phone against desktop, frame)
6. **Phone boards are shorter than desktop; the data is the same at both widths (D-99, as D-111 and D-113 approved).** The phone default leaves out the handover facts and the Next sentence. The phone gaps board uses short gap names ("Bureau outage contact"). The phone received board has a short sentence ("Support received v2, no gaps. Verified 14 Apr."). **Recommend:** on a phone, show the desktop sections stacked in one column, in the same order and with the same returned text. Extras are listed (`phone composition`, `phone wording`).
7. **Phone bar and titles.** The phone boards use "← Delivery" with HND-0048 / GAPS / DONE, and the titles "Support handover" and "Support's reply". **Recommend:** keep the built phone bar (F-22 frame, as D-113 approved for F-32), and use the desktop titles from the response at both widths (`frame item`, `phone wording`).
8. **Delivery sub-nav and project tabs on the work item.** The desktop boards draw the sub-nav (Overview … Closure) and the Planning tab. **Recommend:** as D-113 approved for F-32 (conflict 5), the work item draws no sub-nav. The line tab bar is the one F-32 and F-31 built, with no tab current (`frame item`).
9. **Tola's panel.** **Recommend:** a `checklist` section titled "Support handover v1" with `agent: "tola"`. It has the three done steps with their returned tags (REL-0091 · GLV-0104 · ARC-0130, TEST TEMPLATE, 2 ATTACHMENTS). "Drafted 08 Apr 14:30" is drawn from the section's `as_of` as "As of 08 Apr 14:30 WAT" (`wording`). "Ask Tola" is the existing `assistant` link in the links row (`frame layout`).
10. **The record form's rows.** The board draws "Support replied" as one row: "Femi Ojo · Support lead · 10 Apr 2027, 11:00". **Recommend:**
    - "Support replied" is fixed text when `responders[]` has one entry, as F-18's `Fixed` does.
    - "When they replied" is the shared date-time field beside it.
    - "What Support said" is the segmented control, from `actions[].label`.
    - The proof chip has F-18's remove "×", which the board does not draw (`extra element`). It is 44px on phones.
    - "What happens next:" is drawn from `response.next`, and the footnote from `response.intro`.
    - The single version is sent and not drawn.

### Exceptions to sign
11. **Not drawn: the board's "Open question for PSL: Support doesn't log in…" note.** Conflict C is closed, and D-113 approved the same exception for F-31. Category `wording`.
12. **Frame items.**
    - The top bar's "Tunde Bello · PMO" is the mock persona's name and role.
    - "+ Start" (D-89).
    - The crumb's project segment comes from the response.
    - Tab counts come from P-0101.
    - Category `frame item`.
13. **Sample data.**
    - The boards' Tamarind Loans becomes Lagoon Health (P-0101), so the crumb, title, tabs and Delivery row agree.
    - The board's "10 Apr 2027" becomes 10 Apr 2026, matching the row's date.
    - Names, references and file names are fixture values.
    - Category `sample data`.
14. **Tones and visual waivers.** OPEN is the `uncertain` tone (the amber tag). DRAFT, ATTACHED and the review tag are `neutral`. Banners take their tone only from the returned status tone. A board colour the design system lacks is an exception, not a hard-coded value. Each board below 90 visual (and at least 70) carries a D-83 waiver citing the shared frame. The waiver counts only after the design engineer signs it.

## Boards
| Board | File (`design/canvas/project/`) | Page | Width | Mock |
|---|---|---|---|---|
| SCR-48 default | `SCR-48-desktop.dc.html`, `SCR-48-mobile.dc.html` | `/work/W-3701` | 1440 / 390 | persona `pm`, live URL |
| SCR-48 record | `SCR-48-desktop-record.dc.html`, `SCR-48-mobile-record.dc.html` | `/work/W-3703` | 1440 / 390 | driver: choose Gaps found, type the two gaps, set 10 Apr 2026 11:00, upload `support-reply-10apr.pdf` (40 KB), freeze |
| SCR-48 gaps | `SCR-48-desktop-gaps.dc.html`, `SCR-48-mobile-gaps.dc.html` | `/work/W-3704` | 1440 / 390 | persona `pm`, live URL |
| SCR-48 received | `SCR-48-desktop-received.dc.html`, `SCR-48-mobile-received.dc.html` | `/work/W-3705` | 1440 / 390 | persona `pm`, live URL |

The record driver lives in `delivery/features/F-40/round-<N>/fidelity/drive-states.mjs` (the F-27 and F-31 pattern). It resets the mock, uses only the real controls, copies input values into attributes, removes scripts and saves `frozen/SCR-48-<width>-record.html`. It changes no product or mock code.

## Summary
- The Handover to Support row on `/projects/P-0101/delivery` now links to its work item (`/work/W-3704`; line key `delivery_handover`, HND-0048) through one added `work_id`. The F-32 sub-nav's "Handover" becomes a link by F-32's own rule.
- The F-17 frame draws the handover item in four states, from the response alone:
  - **ready to publish:** the handover facts, Tola's three steps, and Next with "Publish to Support" and its returned consequence;
  - **record Support's reply:** the reply form in place;
  - **gaps:** the returned banner, the OPEN gaps, Next and "Ask Tola to draft v2";
  - **acknowledged:** the verified banner, Next and "See what closure needs".
- A new `support_handover` form in `src/features/response/`, built from F-18's parts, runs on F-31's flow. It records who replied, when, Received or Gaps found, the gaps and the proof, under the PM's name.
- Publish is guarded: one key per attempt, a re-read before any "published", and reconcile only after an uncertain result. "Acknowledged" and the green banner come only from a returned status tone `verified`.
- New in this feature: the variant form, the in-place response panel, two mock rules for the G-48-1 overlay, fixtures W-3701 to W-3711 and W-3720, task ids T-3703 and T-3709, and one key on P-0101. Contract mock only.

## Context
- **Delivery tab (F-32, read only here):** `frontend/src/features/projects/DeliveryTab.tsx`. It draws `delivery[]` rows and the sub-nav, and links a row only when its `work_id` passes `RECORD_ID`. The P-0101 rows are in `frontend/mock/fixtures/projects/P-0101.json` (`delivery[4]` is Handover to Support: HND-0048, "Support listed 2 gaps", tone `person`, 10 Apr, no `work_id`).
- **Work item page:** `frontend/src/features/work-item/WorkItemView.tsx` (`LineHeader`, `ProjectBar`, phone back rule at `:242`) and `WorkItemOverview.tsx` (mounts `Workspace` and `TaskPanels`).
- **Workspace frame:** `frontend/src/features/workspace/`.
  - `Workspace.tsx`: the side panel, `bannerTone` (`:104`), the links row, the reconcile hand-off, and F-31's response-step branch (`responseTaskFor`, F-31 `Workspace.tsx:221`).
  - `Steps.tsx`: `Consequence`, which adds `STEP_TEXT.sends` only when the consequence does not already say it sends (`:17-24`), and `StepControl`.
  - `useWorkspaceStep.ts`: the idempotency key, `effect_uncertain` locks all steps, and a failed `sends` step stays locked (`:100-160`).
  - `Sections.tsx`: `checklist` rows with tag and `StatusWord` (an `unknown` status reads "Unknown"), `FactsList` (an absent value reads Unknown), the note-only banner, and `as_of` and `agent` meta.
  - `proposals.ts` and `Links.tsx`: the F-32 `work` link kind.
- **Response feature (F-18, F-31):** `frontend/src/features/response/`.
  - `contract.ts`: `ResponseVariant` already lists `support_handover`, and `ResponseBody` is the v7 E-RESPONSE body.
  - `ResponseForm.tsx`: `Select`, `WhenField`, `Actions`, `Note`, `RecordRow`, `AgentAside`; the local `Fixed` and `Attest`.
  - `ProofField.tsx`: the chip with remove "×" at `:49` and `:71`.
  - `useResponse.ts`: `Entries`, `missingLine`, `effectiveEntries`, the body build and the guards.
  - `useEvidenceUpload.ts`.
  - `labels.ts`: `RECORDABLE` (F-18's page leaves `support_handover` not-open) and `RESPONSE_LABELS.record`.
  - `ReconcilePanel.tsx`.
  - In F-31: `workspace/ResponseDrawer.tsx` (`RESPONSE_TEXT`, `responseTaskFor`, the Drawer host for `TeamInputForm`).
- **Mock:**
  - `frontend/mock/workspace.mjs` (E-WORK-STEP): `<id>.steps.json` scripts a step, `<id>.next.json` is swapped in on 200 or on a scripted failure with `next: true`, and the idempotency map gives one send per key.
  - `frontend/mock/response.mjs` (E-EVIDENCE-UPLOAD, E-RESPONSE, E-WORK-ACTION). It validates the body against the v7 schema, which has `additionalProperties: false`. A 200 swaps in `fixtures/response/<id>.recorded.json`, and a reconcile swaps in `fixtures/response/<id>.<outcome>.json`. A `record-then-fail` scenario is supported.
  - `frontend/mock/projects.mjs` serves P-0101 to `pm` and `finance_lead`.
- **Tests that assert the Handover row has no link** (the only assertion edits allowed): `frontend/tests/delivery-release-mock.test.ts:146-155` and `frontend/tests/delivery-overview.test.tsx:206-216`.

## Contract

### E-PROJECT `GET /api/v1/projects/{case_id}` (unchanged; one fixture key)
`P-0101.json` `delivery[4]` gains `"work_id": "W-3704"`. Nothing else in the file changes: the journey keys, the other rows, `delivery_agent` and `delivery_summary` stay byte-for-byte the same. `work_id` is already typed in `delivery[]` (`schema.d.ts:2911-2933`), so this is not a proposal. The row and the sub-nav link through F-32's existing rule; F-40 changes no Delivery tab code.

### E-WORK-ITEM `GET /api/v1/work/{work_id}` (handover item; unchanged)
F-17's and F-32's read rules apply:
- 401 shows the signed-out state with `next=/work/<id>`.
- 403 and 404 look the same (`NoAccessState`: no title, project, reference or gap text) and make no further call.
- 5xx shows `WorkErrorCard` with Retry.
- Loading shows `LoadingState`.
- There is no polling.

The page branches on nothing for `line_key: "delivery_handover"`. Its only new branch is on a step's task variant (Conflicts 3).

Every fixture below is `sample: true`, with:
- `line_key: "delivery_handover"`, `reference: "HND-0048"`, `case_id: "P-0101"` and `case_revision: 1`;
- `workspace.context.project {case_id: "P-0101", title: "Lagoon Health · patient app"}`;
- crumbs Projects / Lagoon Health / Delivery / HND-0048, and `subtitle` "PM Tunde Bello".

Each validates against the generated E-WORK-ITEM 200 schema once the `links` `work` proposal (F-32) is removed. `revision` and `workspace.revision` are numbers ≥ 1. Times are stored in UTC and shown in WAT.

| Id | `state`; `workspace.status` | Sections | Steps / tasks / links / next |
|---|---|---|---|
| W-3701 default (board) | `action_needed`; "Handover · ready to publish", `person` | `workspace.version {label: "Support handover v1", document_id: "D-3701"}`. `checklist` "Handover to Support": H-1 "Support handover v1", tag DRAFT `neutral`, cites D-3701; H-2 "Review needed?", tag "No · below the rule's threshold" `neutral`; H-3 "Runbook and escalation contacts", tag ATTACHED `neutral`, cites D-3702, D-3703. `checklist` "Support handover v1", `agent: tola`, `as_of` 2026-04-08T13:30:00Z, three `done` items with tags "REL-0091 · GLV-0104 · ARC-0130", "TEST TEMPLATE", "2 ATTACHMENTS" | step `publish` "Publish to Support" (primary, `sends: true`, `consequence` "Publishing sends it to Support. Then you record whether they received it or found gaps."). `tasks: []`. `links: [assistant "Ask Tola"]`. `W-3701.steps.json` publish → 200 `done`; `W-3701.next.json` = W-3703's record state under id W-3701 (revision 2) |
| W-3702 hold | `waiting`; "Handover · held", `stopped` | as W-3701, but H-2 has `status: "unknown"` and no tag | **no steps.** `next: ["Publishing waits until PSL sets when a handover needs review (Setup › Rules)."]`. No Setup link and no control of any kind |
| W-3703 record (board) | `waiting`; "Handover · published 08 Apr", `person` | none in the main column besides the form panel | step `record_reply` "Record Support's reply" (primary, `task_id: T-3703`). `tasks: [T-3703 {title "Record Support's reply", you_can_act: true, revision: 1, response {variant: "support_handover", responders: [{id: "R-3701", name: "Femi Ojo", role: "Support lead"}], actions: [{value: "approved", label: "Received"}, {value: "changes_requested", label: "Gaps found"}], versions: [{id: "V-3701", label: "Support handover v1", sent_at: "2026-04-08T14:00:00Z"}], evidence_kind: "proof", intro: "Support doesn't log in. You record their reply with proof, and the record keeps your name.", next: ["gaps go back to Tola for v2 of the handover. If they received it with no gaps, the handover is acknowledged."]}}]`. Sidecars `fixtures/response/W-3703.recorded.changes_requested.json` (W-3704's content under id W-3703) and `W-3703.recorded.approved.json` (W-3705's content under id W-3703) |
| W-3704 gaps (board; the row's target) | `waiting`; "Gaps · 2", `person` | Title-less note-only section: "Support listed 2 gaps on 10 Apr. The handover isn't acknowledged until they're closed." `checklist` "Gaps": G-1 "No contact for the credit bureau outage", G-2 "Runbook misses the nightly export restart", each tag OPEN `uncertain` | step `draft_v2` "Ask Tola to draft v2" (primary, no `sends`). `next: ["Tola drafts v2 covering both gaps; it's published to Support again."]`. `W-3704.steps.json` draft_v2 → 200 `queued`, message "Tola is drafting v2."; `W-3704.next.json`: `processing`, status "Drafting v2" `agent`, the same gaps, no steps |
| W-3705 received (board) | `verified`; "Handover acknowledged", `verified` | Title-less note-only section: "Support received handover v2 with no gaps on 14 Apr. Recorded by Tunde Bello with Support's reply as proof, verified." | no steps. `next: ["Closure needs this. Remaining: hypercare and the retrospective."]`. `links: [{key: "closure", label: "See what closure needs", target: {kind: "work", work_id: "W-3720"}}]` |
| W-3706 publish uncertain | as W-3701 | as W-3701 | `W-3706.steps.json` publish → 200 `effect_uncertain`, message "We couldn't confirm Support received the handover." `W-3706.next.json`: `effect_uncertain`, status "Handover · delivery unconfirmed" `uncertain`, H-1 `receipt: "uncertain"`, `reconcile {what: "Support handover v1 to Support", sent_at, outcomes: [delivered, not_delivered, unknown], evidence_kind: "proof", resend_note}`, `allowed_actions: [reconcile]`, the publish step still listed. Reconcile sidecars `fixtures/response/W-3706.delivered.json` (record state under id W-3706), `.not_delivered.json` (default state, status "Handover · not delivered", publish offered again), `.unknown.json` (still uncertain) |
| W-3707 publish lost reply | as W-3701 | as W-3701 | `W-3707.steps.json` publish → `{status: 502, next: true}` (written, then the reply is lost); `W-3707.next.json` = W-3706.next's uncertain state under id W-3707 |
| W-3708 publish stale | as W-3701 | as W-3701 | `W-3708.steps.json` publish → `{status: 409, next: true}`; `W-3708.next.json`: revision 2, status "Handover · published 08 Apr" `person`, no publish step (someone else published) |
| W-3709 cannot record | as W-3703 | as W-3703 | step `record_reply` with `task_id: T-3709`; T-3709 `you_can_act: false`, `cannot_act_reason: "not_your_role"`, `required_role: "PM"` |
| W-3710 Unknown | as W-3704 | G-2 `status: "unknown"` with no tag; Tola's checklist (as W-3701) with no `as_of`; the banner section absent | as W-3704 |
| W-3711 agent claim | `processing`; "Drafting v2", `agent` | Tola's checklist with a `done` item "Support acknowledged the handover" | no steps and no links |
| W-3720 | a plain work item (no `workspace`), title "Closure · Lagoon Health" | | the target of "See what closure needs"; it is not SCR-49 |

### Frame change: a `support_handover` step draws the reply form in place (`Workspace.tsx`, `ResponseDrawer.tsx`)
- `responseTaskFor(item, taskId)` (F-31) also returns a `support_handover` task. It is `open` when `you_can_act === true` and `response.actions` has at least one labelled action.
- When a workspace step's `task_id` names such a task and it is open, the step is not a button. The main column draws a `Panel` titled with the step's `label` ("Record Support's reply"), holding the variant form.
  - When the task is present but not open, the panel is not drawn. F-32's rule then applies: the step is unavailable and described by the `cannotActCopy` sentence.
  - When the task is absent, the step is unavailable with the default sentence.
- F-31's flow body (loading, error, form, the stale, uncertain and unconfirmed notices, `onRecorded`, `onAccessLost`) is split out of `ResponseDrawer` so that it renders either in the `Drawer` (team input, F-31, unchanged) or in the `Panel` (support handover). The F-31 notices that say "input" read "reply" for this variant. For example: "We couldn't confirm the reply was recorded. We've reloaded this item so you can see whether it was."
- F-31's `team_input` behaviour and its tests are unchanged.

### The support-handover form (new `frontend/src/features/response/SupportHandoverForm.tsx`)
Built from F-18's parts; `Fixed` and `Attest` are exported from `ResponseForm.tsx` (additive). In order:
1. "Support replied": the responder's text (`Fixed`) when there is one responder, otherwise a `Select` of `responders[]`. Beside it, "When they replied" (`WhenField`).
2. "What Support said": the segmented `Actions`, from `actions[].label`. Nothing is chosen by default.
3. "Gaps": a labelled textarea, shown only while the chosen action is `changes_requested`, with the hint "One gap per line."
4. Proof: `ProofField`, uploaded through E-EVIDENCE-UPLOAD to case P-0101 as soon as it is chosen.
5. The tick (Conflicts 5).
6. "What happens next:", drawn from `response.next`. Then `RecordRow` with `RESPONSE_LABELS.record.support_handover` = "Record reply" (pinned in the phone action bar). Then `response.intro` as the footnote.

`missingLine` gains a `support_handover` branch: who, when, what Support said, and at least one gap when Gaps found is chosen, then proof and the tick. The note is not drawn for this variant. `RECORDABLE` stays as it is, so F-18's `/respond` page still shows its not-open state for this variant.

### E-RESPONSE `POST /api/v1/tasks/{task_id}/response` (unchanged endpoint; one proposal field)
- **Order:** E-TASK-CLAIM first, only when `response.claim_required`. The proof has already been uploaded. Then one POST.
- **Body:** `{expected_revision (the task revision), who: "R-3701", action: "approved" | "changes_requested", responded_at (as entered, WAT, ISO), evidence_id, attested: true, case_revision, version_id: "V-3701"}`, plus `gaps: string[]` only with `changes_requested`. Header `X-CSRFToken`. There is no idempotency key (not typed). F-18's guards are the protection: one press sends once; a 409 keeps every entry and re-reads; a network error or 5xx re-reads to see whether it was recorded; only a new press sends again.
- **Success:** the panel closes. The page re-reads E-WORK-ITEM. Only after that re-read does the notice "Recorded under your name: …" (F-31's `done`) appear, beside the state the re-read shows (gaps or acknowledged).
- **Errors:** 401 and 404 show the signed-out or not-open view. A 403 shows the not-open view (F-31). A 422 names the fields, and `gaps` reads "Add at least one gap." The form keeps its entries.
- **Permission and tenant:** the backend decides per task and record. A wrong-user or wrong-tenant read or write is a 403 or 404, and the two look the same.

### Proposals (mock overlay only; each recorded in build.md for the backend developer)
| Proposal | Shape | Where |
|---|---|---|
| G-48-1 | E-RESPONSE body `gaps: string[]` (required and non-empty with `changes_requested` on `support_handover`, refused otherwise); the mapping Received = `approved`, Gaps found = `changes_requested`, with labels from `actions[].label` | `contract.ts` `ResponseBody.gaps?` (marked PROPOSAL); `useResponse.ts` body build; `mock/response.mjs` (below) |
| G-48-2 | Support recipient, channel and receipt word | recorded only; Publish is a mock step |
| G-48-3 | `unknown` on plain items | **not needed**: a `checklist` item with `status: "unknown"` already reads Unknown, and so does a `facts` item with no value. Recorded as covered |
| G-F40-1 | `fixtures/response/<id>.recorded.<action>.json`: a recorded state per action | mock only; it is not a contract field |

**Mock rules (`frontend/mock/response.mjs`, additive):**
1. For a `support_handover` task, `gaps` is taken out of the body before the v7 schema check. It is then checked: with `changes_requested` it must be a non-empty array of non-blank strings, or the mock answers 422 naming `gaps`; with any other action, `gaps` present gives 422 `gaps`. The schema check still runs on the rest.
2. A 200 swaps in `<work_id>.recorded.<action>` when present, else `<work_id>.recorded`. Every existing fixture uses the second form and behaves as before.

### E-WORK-STEP `POST /api/v1/work/{work_id}/steps` (`publish`, `draft_v2`; unchanged)
- **Body:** `{expected_revision (workspace.revision), step, idempotency_key}`, with CSRF. A double press sends once.
- **200 `done`:** the page re-reads. The status ("Handover · published 08 Apr") and the form come only from that re-read.
- **200 `queued`:** "Waiting: Tola is drafting v2.", then the re-read.
- **200 `effect_uncertain`, or a 5xx or network error on `publish` (a `sends` step):** every step locks. The page re-reads and shows the uncertain banner and `ReconcilePanel` when the re-read offers `reconcile`. No Publish, no resend and no new key until a reconcile outcome is applied. `not_delivered` serves Publish again, as the response says.
- **409:** the stale notice and a re-read. No "Done".
- **422:** field messages. **403:** "You can't take that step." and a re-read.

### Screen states
- **Loading, error, signed out, no access:** as above.
- **Handover item:** ready to publish (W-3701), hold (W-3702), record (W-3703), gaps (W-3704), drafting (W-3704.next), acknowledged (W-3705), and the negative fixtures W-3706 to W-3711.
- **Empty:** a copy with `sections: []`, no steps and no `next` shows only the header and the frame's "Nothing here yet.".
- **Unknown:** an `unknown` status, a missing fact value or a missing `as_of` reads "Unknown" or draws no time line. Never blank, "0" or "-".
- **Restricted:** a section or item with `restricted: true` shows only its label.
- No animation under `prefers-reduced-motion`.

## Lanes
- **Frontend lane (Sonnet builder, D-64) owns:**
  - `frontend/src/features/response/SupportHandoverForm.tsx` (new).
  - Additive edits to `ResponseForm.tsx` (export `Fixed`, `Attest`), `useResponse.ts` (`gaps` entry, `missingLine` branch, body), `contract.ts` (`gaps?` PROPOSAL), `labels.ts` (`record.support_handover`) and `response.css` (tokens only).
  - `frontend/src/features/workspace/ResponseDrawer.tsx` (split the flow body; variant wording) and `Workspace.tsx` (the in-place panel), plus additive `workspace.css`: the in-place panel, and `.resp-chip__remove` at `var(--control-phone)` inside it on phones.
  - Fixtures `frontend/mock/fixtures/work/W-3701.json` to `W-3711.json` and `W-3720.json`, with the `.steps.json` and `.next.json` files named above. `frontend/mock/fixtures/response/W-3703.recorded.{changes_requested,approved}.json` and `W-3706.{delivered,not_delivered,unknown}.json`. The one key in `P-0101.json`.
  - `frontend/mock/response.mjs`: the two additive rules.
  - Tests: new `frontend/tests/support-handover.test.tsx` and `support-handover-mock.test.ts`; additions to `mock-contract.test.ts`; the two Handover-row assertions; new `frontend/e2e/support-handover.spec.ts`.
  - Factory files: `delivery/features/F-40/fidelity-exceptions.json`, `round-<N>/fidelity/**`, `round-<N>/build.md`.
- **Shared, read only:**
  - `src/features/projects/**` (the Delivery tab), `src/features/decide/**`, `src/features/work-item/**`, `src/components/**`, `src/shell/**`, `src/api/**` including `schema.d.ts`, `src/styles/**`.
  - `Sections.tsx`, `Steps.tsx`, `StepForm.tsx`, `useWorkspaceStep.ts`, `ProofField.tsx`, `ReconcilePanel.tsx`, `TeamInputForm.tsx`, `ResponseView.tsx`: change only if a test proves a defect, and list it.
  - Existing fixtures except the P-0101 key, `mock/server.mjs`, `mock/workspace.mjs`, `mock/projects.mjs`.
  - `package.json`, the lock file, `playwright.config.ts`, `vitest.config.ts`, `architecture/**`, `design/**`, `apps/**`.
  - The protected `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json`.
- **Backend lane:** none. Record in `build.md`: G-48-1, G-48-2, G-48-3 (covered), G-F40-1, and the three questions at `gaps-d-delivery.md:147-150`.
- **Integration owner:** the coordinator.
  - Cut the branch from dlv-00 only after F-32 and F-31 are merged.
  - F-34 shares `P-0101.json` and the two Handover/Hypercare row assertions. It may also touch `Workspace.tsx`. The second to merge keeps both and reruns `delivery/checks.sh`, `e2e/support-handover.spec.ts` and F-34's e2e.
- **Ports:** app **4890**, mock **4891** (not used by any spec). Run `df -h /System/Volumes/Data` first and stop under 3 GB. Run `cd frontend && E2E_PORT=4890 MOCK_PORT=4891 npx playwright test e2e/support-handover.spec.ts e2e/delivery-release.spec.ts e2e/engagement-planning.spec.ts e2e/workspace.spec.ts e2e/response.spec.ts` with `timezoneId: 'Africa/Lagos'`. Delete `frontend/test-results` afterwards. The e2e is not in `checks.sh`, so paste its output in build.md.
- **Review routing (medium risk):** technical (Sonnet), security (Opus: `external-messaging`), UI (fidelity gate on 8 boards), UX (Sonnet), QA (Opus). Product acceptance is required.
- **Size:** about 800 to 1,200 lines, more than half of it fixtures and tests. One PR.

## Acceptance criteria
Fidelity command per board (swap `--board`, `--page`, `--width` and `--out`; cookie `psl_mock_persona=pm`; run on a production build: `next build`, then `next start -p 4890`, with the mock on 4891; the record boards point `--page` at the frozen file):
```
node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs \
  --playwright <worktree>/frontend/node_modules/playwright/index.mjs \
  --board /Users/Hunchoo/psl-factory/design/canvas/project/SCR-48-desktop-gaps.dc.html \
  --page "http://localhost:4890/work/W-3704" --width 1440 \
  --cookies psl_mock_persona=pm \
  --exceptions /Users/Hunchoo/psl-factory/delivery/features/F-40/fidelity-exceptions.json \
  --wait-ms 500 --out /Users/Hunchoo/psl-factory/delivery/features/F-40/round-<N>/fidelity/SCR-48-desktop-gaps-1440
```

### Fidelity (8 boards, D-64, D-83)
1. **Scores.** One fidelity run per round covers all 8 boards in the Boards table: six live URLs and the two driver-frozen record pages. Every board has `coverageWithExceptions` = 100 and `visual` ≥ 90. A board at 70 or more but below 90 passes only with a D-83 waiver signed by the design engineer for that board in `fidelity-exceptions.json`, and only when the UI reviewer's side-by-side reading finds no fixable gap. No board passes under 70. — verify: the commands exit 0; `round-<N>/fidelity/scores.txt` lists board, width, coverage, visual, pass and waiver; a re-run of `drive-states.mjs` reproduces the frozen pages.
2. **Exceptions limited.** Each entry has `role`, `name`, `category`, `reason` and `approved_by`, and maps to a Conflicts number. None covers a value the data can supply (a name, date, reference, tag, gap or sentence). — verify: file content; build.md.

### Handover row and states
3. **The row opens the item.** On `/projects/P-0101/delivery`, "Handover to Support" links to `/work/W-3704`, and the sub-nav's "Handover" links to the same. Every other row, tag and date is unchanged. `P-0101.json` differs from dlv-00 by exactly one added `work_id` line. — verify: the updated `delivery-overview.test.tsx` and `delivery-release-mock.test.ts` assertions; `git diff frontend/mock/fixtures/projects/P-0101.json`.
4. **Four states from data.** `/work/W-3701`, `/work/W-3703`, `/work/W-3704` and `/work/W-3705` each show their fixture's status label and tone, sections, steps, Next and links, and nothing else.
   - W-3701 shows "Publish to Support" with its consequence once. "This sends to the client." does not appear, because the consequence already says it sends.
   - W-3703 shows the reply form in place, titled "Record Support's reply".
   - W-3704 shows the banner, two OPEN gaps and "Ask Tola to draft v2".
   - W-3705 shows the green banner, Next and "See what closure needs", linking to `/work/W-3720`.

   `grep -rnE "Ready to publish|Published|Acknowledged|below the rule|Gaps ·|Femi Ojo|closure needs" frontend/src` finds nothing. — verify: `tests/support-handover.test.tsx` at 1440 and 390; grep.
5. **The hold has no controls.** W-3702 shows "Review needed?" as "Unknown". It shows the returned Next sentence and no button, link, form or step of any kind in the workspace (beyond the frame's tabs and back link). A recording `fetch` sees no POST. — verify: component test.

### Publish (an external send on the mock)
6. **Publish writes once and claims nothing before the re-read.** On W-3701, pressing Publish sends one POST `/api/v1/work/W-3701/steps` with `{step: "publish", expected_revision: 1, idempotency_key}` and CSRF. A double press sends one; the mock log shows one send for the key. The words "published 08 Apr" appear only after the re-read serves `W-3701.next.json`. — verify: e2e with recorded requests and `GET /__mock/workspace-log`; component test with a held re-read showing no "published" until it resolves.
7. **Each uncertain path has a fixture and ends without a resend.**
   - W-3706 (200 `effect_uncertain`) and W-3707 (502, written) show the uncertain banner and `ReconcilePanel`. Publish is off, and no "published", "sent" or "received" appears. A second press sends nothing.
   - On W-3706, reconcile `delivered` with proof serves the record state, `not_delivered` serves Publish again, and `unknown` stays uncertain. Each happens only from the re-read.
   - W-3708 (409) shows "This changed while you were working. Showing version 2." and the re-read's status, and no "Done".
   - A network failure (`X-Mock-Scenario` or the route aborted) on W-3701 locks Publish, re-reads, and shows "We couldn't confirm this step. Check the page before trying again.".

   — verify: e2e per fixture; `workspace-log` shows one send per key and no second key after an uncertain result.
8. **Draft v2 is Tola's work, never a verified result.** On W-3704, "Ask Tola to draft v2" sends one step. It shows "Waiting: Tola is drafting v2.", and then the re-read's "Drafting v2" status with the gaps still OPEN. No green banner, "v2 published" or "acknowledged" appears. — verify: component test; e2e.

### Record Support's reply
9. **The form comes only from the response.** On W-3703 the form shows:
   - "Support replied · Femi Ojo · Support lead" (fixed text);
   - "When they replied";
   - "What Support said", with Received and Gaps found as returned and neither chosen;
   - the proof field and the tick;
   - "What happens next:" with the returned sentence, and the returned intro.

   "Gaps" appears only after Gaps found is chosen. A copy whose actions have no labels offers no choice, and Record stays off. W-3709 draws no form: its step is unavailable, described by F-32's `cannotActCopy` `not_your_role` sentence naming the returned `required_role`. Personas `pm` and `finance_lead` see the same thing for the same fixture. The diff adds no `/me` read under `frontend/src/features/workspace` or `features/response`. — verify: component tests across fixtures and personas; diff.
10. **Recording sends one guarded write after the proof.** With Gaps found, two gap lines, a time and `support-reply-10apr.pdf`, the network shows, in order:
    1. one POST `/api/v1/cases/P-0101/evidence`;
    2. one POST `/api/v1/tasks/T-3703/response` with `{expected_revision: 1, who: "R-3701", action: "changes_requested", responded_at, evidence_id, attested: true, case_revision, version_id: "V-3701", gaps: ["No contact for the credit bureau outage", "Runbook misses the nightly export restart"]}` and CSRF.

    There is no claim, because `claim_required` is absent. Received sends no `gaps`. A double press sends one. Without proof, without the tick, or with Gaps found and no gap, Record stays off and the missing line names what is needed. — verify: component test with a recording `fetch`; e2e.
11. **No success before the re-read, on every path.**
    - On 200, the gaps state (or, for Received, the acknowledged state) and "Recorded under your name: …" appear only after the E-WORK-ITEM re-read resolves.
    - `X-Mock-Scenario: record-then-fail` (written, then 502) re-reads, shows the reply-wording uncertain notice and the gaps state from the re-read, and sends nothing again.
    - A plain 500 or a network failure keeps every entry and shows the uncertain notice. The re-read (still W-3703) shows the form. Nothing is sent until a new press.
    - A 409 keeps the entries and shows the stale notice.
    - A 422 `gaps` shows "Add at least one gap." under Gaps.

    None of these shows "Recorded", "Received" or "acknowledged" without the re-read. — verify: component tests for each; e2e for `record-then-fail` and 409.
12. **Recorded under the PM's name, never as Support.** The notice and the acknowledged banner attribute the record to the signed-in person, as returned. No text says Support logged in, signed or sent through the factory. `grep -rniE "logged in|signed in as|support (sent|signed)" frontend/src/features/response/SupportHandoverForm.tsx frontend/src/features/workspace` returns nothing. — verify: component test; grep.
13. **Verified only from the backend (INV-AGENT).** W-3711, whose Tola item "Support acknowledged the handover" is done, shows no green banner, no "Handover acknowledged" and no closure link. W-3705's banner is green only because `status.tone` is `verified`: a copy with the same text and tone `person` draws the warning banner. — verify: component tests.
14. **Unknown, not zero.** On W-3710 the unknown gap reads "Unknown", and Tola's checklist has no time line. W-3702's "Review needed?" reads "Unknown". Nothing shows blank, "0" or "-". "GAPS · 2" is drawn only from the returned label: a copy with three gap items and the label "Gaps · 2" still shows "Gaps · 2". The browser counts nothing. — verify: component tests.
15. **Links only from data.** "See what closure needs" appears only from a `work` link with a valid `work_id`. A copy with `work_id: "../x"`, or with no link, draws nothing. — verify: component test.

### Access, phone and quality
16. **Access.**
    - A 401 on `/work/W-3703` shows the signed-out state with `next=/work/W-3703`.
    - A 403 and a 404 on the read look the same, with no title, project, reference, gap or responder text in `document.body.textContent`.
    - A 403 on the response write shows the same not-open view (F-31), and nothing reads as recorded.
    - A persona not on P-0101's list (for example `ceo`) gets the no-access view with no further call.

    — verify: component tests with `X-Mock-Scenario` and a recording `fetch`.
17. **Phone.** At 390, each state is one column, with the desktop sections in the desktop order (Conflicts 6), and there is no sideways scroll. Every target is at least 44px tall, measured: buttons, the segmented options, the date-time field, the file button, row links, standalone links, and the proof chip's remove "×", which is also at least 44px wide (D-92c). Record reply sits in the pinned action bar. — verify: e2e at 390 measuring `getBoundingClientRect`, including `.resp-chip__remove` after an upload.
18. **Accessibility.** There are no axe violations (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`) at 1440 or 390 on W-3701 to W-3705, W-3702, W-3706.next, W-3709, the form with a 422, and the no-access view. Every field is labelled. Errors are announced. The remove button is named "Remove support-reply-10apr.pdf". Tags and status are text, not colour only. Focus is visible and returns to the page heading after a record. Nothing animates under `reducedMotion: 'reduce'`. — verify: `e2e/support-handover.spec.ts`.
19. **Tokens and components only.** New UI imports from `@/components` (`Panel`, `Button`, `Tag`, `Callout`, `Link`, `Unknown`) and F-18's response parts. It adds no local button, tag, panel, segmented control or upload. `grep -nE "#[0-9a-fA-F]{3,8}\b|rgba?\(|hsl\("` on this feature's CSS diff returns nothing. — verify: diff and grep.
20. **Mock matches the contract.**
    - `support-handover-mock.test.ts`: W-3701 to W-3711, W-3720 and every `.next` and sidecar file validate against the generated E-WORK-ITEM schema once the `links` proposal is removed.
    - Each recorded body validates against the v7 E-RESPONSE body once `gaps` is removed.
    - `changes_requested` without `gaps` answers 422 `gaps`, and `approved` with `gaps` answers 422 `gaps`.
    - A record on T-3709 answers 403.
    - A repeat publish with the same key is a replay with no second send.
    - The existing `.recorded` sidecars still apply.

    — verify: `cd frontend && npx vitest run tests/support-handover.test.tsx tests/support-handover-mock.test.ts tests/mock-contract.test.ts`.
21. **Contract not extended.** `git diff --stat` shows no change in `frontend/src/api/**` (including `schema.d.ts`), `apps/**`, `architecture/**`, `design/**`, `src/shell/**`, `src/features/decide/**`, `src/features/projects/**` or the protected paths. No existing fixture is edited except the one `work_id` key in `P-0101.json`. `gaps` exists only as a PROPOSAL-marked optional field in `features/response/contract.ts` and in the mock. Every proposal is listed in build.md. — verify: `git diff --stat`; grep for `PROPOSAL` beside `gaps`; build.md.
22. **Existing tests green.** `delivery/checks.sh` passes. The response, team-input, workspace, work-item, delivery-overview, release-gates, engagement-planning, decide and project-tab tests and their e2e specs pass. No assertion is removed or loosened. The only assertion edits are the two Handover-row expectations, which now expect `W-3704`. — verify: `delivery/checks.sh`; the e2e output in build.md; `git diff` of `frontend/tests/` and `frontend/e2e/`.
23. **No overclaim.** build.md and the PR carry the "What is sent, and what stays held" section: contract mock only, nothing sent to Support, no review rule set, and G-48-1 and G-48-2 open for the backend. — verify: file content.

## Out of scope
- SCR-33 (retrospective) and all of SCR-49 (closure, in every state), which are parts 2 and 3. W-3720 is only a plain link target.
- A handover review decision, a review task or any reviewer. Setting, editing or linking to the `delivery.handover_review` rule.
- Any real send to Support, a Support recipient or channel, alerts or WhatsApp messages to Support, and a Support login.
- Closing a gap one by one, editing or deleting recorded gaps, and composing v2 in the browser.
- The sub-nav on the work item, and a second E-PROJECT read in the frame.
- Making `support_handover` recordable on F-18's `/respond` page.
- Backend, OpenAPI, `schema.d.ts` regeneration, `architecture/**`, `design/**`, `src/shell/**`, new npm dependencies.

## Assumptions
- The Handover row links to the gaps state (W-3704). Reason: the row already reads "Support listed 2 gaps · 10 Apr", so the row and the page agree.
- The record board's form is scored after a driver fills it. Reason: the board draws chosen and typed values that the response cannot supply (the F-31 pattern).
- One gap per line, trimmed, sent as typed and in order. Reason: the board draws one box. Splitting lines is presentation, not a rule.
- The note field is not drawn for this variant. Reason: no SCR-48 board draws it, and `note` is optional.
- The single version is sent as `version_id` and not drawn. Reason: the board draws none, and F-18 already picks a single option.
- F-31's flow sentences use "reply" for this variant. Reason: "input" is team-input wording.
- `required_role: "PM"` on T-3709 is sample data only. Reason: it exercises the refusal path. It names no real approver.
- No change to `STEP_TEXT.sends` ("This sends to the client."). Reason: W-3701's consequence already says it sends. A Support step without one would misname the recipient, which is noted for the backend.
- Fixture ids are W-3701 to W-3711, W-3720, T-3703 and T-3709, and evidence documents are D-3701 to D-3703. Reason: these are the night log's F-40 block.
- Dates are 2026 and shown in WAT. Reason: they match P-0101's delivery row (10 Apr 2026) and F-32's fixtures.
- Ports are 4890 and 4891. Reason: no spec, config or demo server uses them.
