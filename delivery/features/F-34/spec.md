# Hypercare, part 1: the PM records the release, follows the window and its observations, sees the hold while PSL has not set the criteria, and sees "qualified" only when the backend verifies it (contract mock only)

> **Build starts only after F-32 is merged into dlv-00.** This spec is written against F-32's branch head (`fe-delivery-release-delivery-tab-and-release-gate`, worktree `/Users/Hunchoo/psl-factory-worktrees/f-32`, head `5bab76ae`). It needs F-32's Delivery tab, delivery sub-nav, `work` link kind, the P-0101 `delivery[]` rows and the decision-step rule. If F-32 changes before merge, the builder re-reads this spec against the merged code first and lists every difference in build.md.
>
> Tasks: FE-DELIVERY-HYPERCARE-ARCHIVE, part 1 (R-WORKITEM, R-EXCEPTION; acceptance A-WORKSPACE, frontend half for SCR-46. A-RECONCILE belongs to part 3 (SCR-47). A-WORKITEM, A-PROJECT-TABS and the F-17, F-30 and F-32 tests stay green). Architecture: package `architecture/packages/v7`, manifest digest `f6231d20b4fdeabbdca9bde5986a0a7883536f1a5cafc883848ef62dd6d4b624`. FE-DELIVERY-HYPERCARE-ARCHIVE is at `architecture/packages/v7/delivery.md:2317-2348`, `gate_ids: []`, "Unresolved gates: none". E-WORK-ITEM `workspace` is typed at `frontend/src/api/schema.d.ts:1693-1912` (F-32 tree). E-WORK-STEP and E-EVIDENCE-UPLOAD are already in `schema.d.ts`. This feature changes no generated type. Decisions consumed: D-LINE-WORKSPACE (`proposed`, under the recorded exception `architecture/sources/decisions-2026-11-15.md` items (g), (i)), D-64, D-69, D-83, D-89, D-91, D-92b/c, D-99, D-111, D-112, D-113. Open and held: D11 (`contracts/decision-registry.json:383`, slot `hypercare_criteria_ref` at `contracts/policy-slots.json:920-933`); D-ADMIN-AUTHORITY; the four backend questions at `delivery/backend-handoff/gaps-d-delivery.md:108-112`. Design: client-approved canvas version 1794581312-b166 (13 Nov 2026; SCR-46 at `design/review.json:54`), republished with "+ Start" as 1794762832-cab1 (D-89). `python3 /Users/Hunchoo/software-factory/packages/design/design.py check --project /Users/Hunchoo/psl-factory` was run for this spec on 18 Nov. Result: `EXCEPTION`, `passes: true` (design_sha256 `2859ab21…3d82`, D-89 frame-only change). Screens: SCR-46, 8 artboards in `design/canvas/project/`: `SCR-46-desktop`, `SCR-46-mobile`, `SCR-46-desktop-record`, `SCR-46-mobile-record`, `SCR-46-desktop-setup-needed`, `SCR-46-mobile-setup-needed`, `SCR-46-desktop-qualified`, `SCR-46-mobile-qualified`. Models: `delivery/features/F-32/spec.md` (shape and frame), `F-30/spec.md`, `F-23/spec.md` (driver).

## What is sent, and what stays held (read first)
- **On the contract mock, nothing is deployed, evaluated or qualified, and no one is given authority.**
  - Every "Day 10 of 30", "30 days · from Setup", MET, "qualified" and "verified" on these boards is fixture text. It is returned the way a backend would return it.
  - PSL has not set `delivery.hypercare_window` or `delivery.hypercare_criteria` (D11 open; `frontend/mock/fixtures/setup/delivery.desktop.json:4-30` shows `set: false`). The default and qualified fixtures are sample data. They show what the page would draw once the rules are set.
  - The PR and build.md must say so. They must not claim a working hypercare line, an evaluation or a qualification.
- **What is sent (mock only):**
  - `record_release` on E-WORK-STEP, with `version`, `released_at`, `environment` and the deployment log uploaded first through E-EVIDENCE-UPLOAD.
  - `log_observation` on E-WORK-STEP, with `what` and optional proof (G-46-1).
  - Each send carries CSRF, `expected_revision` as read and one `idempotency_key` per attempt.
  - Nothing else is sent. There is no deploy, no evaluation trigger, no Setup write, and no write to the decision or claim endpoints.
- **What a real hypercare line would be (backend, not built):**
  - The backend starts the window from the recorded release, using the Setup rule.
  - A scheduled or event-driven run has Tola evaluate the line (G-46-2).
  - A deterministic factory check, not Tola's step, sets `verified` from the criteria and the records (INV-AGENT).
  - While either rule is Not set, the backend returns `state: setup_needed` with no criteria rows.
- **Held, because a product or backend decision is open:**
  1. The window and the criteria (D11). Their value shape, and who sets them (D-ADMIN-AUTHORITY).
  2. The observation record (G-46-1). The real `log_observation` write waits for the backend.
  3. The evaluation trigger (G-46-2).
  4. Where the incidents count comes from.
  5. Whether `environment` is free text or a supplied list.
  6. Whether a PM gets the "Open Setup › Rules" link (Conflicts 1).

  The page shows whatever the re-read data returns and adds no rule.
- **Held on the page itself:**
  - A control exists only where the response carries it. A step must be in `workspace.steps[]` without a `disabled_reason`, or a decision step's task must have `you_can_act: true`.
  - A failed, refused, stale or timed-out write never shows "recorded". The page shows a new status, row or banner only from the re-read item.

## Conflicts with the boards (for the design engineer, before the build)
"Recommend" is what this spec builds if no answer comes. Each difference becomes a `delivery/features/F-34/fidelity-exceptions.json` entry with `approved_by: "builder proposal, pending design engineer"` until it is signed.
- Items 1 to 5 need an answer: 1 and 3 are product questions for PSL, and 2, 4 and 5 are design calls.
- Items 6 to 12 are layout.
- Items 13 to 16 are exceptions to sign.

### Need an answer
1. **"Open Setup › Rules" is drawn for the PM, but a PM cannot open Setup (product question for PSL).** On the mock, `pm` gets 403 on every Setup call (`frontend/mock/setup.mjs:25`). The link would land on Setup's "can't open" view.
   - **Recommend:** draw the link only when `workspace.links[]` returns it, as the board does. Point it at `/setup/rules/delivery`. Whatever the person sees there is up to the Setup page. Ask the backend to send the link only to people who may open Setup. The sentence "An admin sets the criteria in Setup › Rules…" still tells the PM who acts.
   - **Option B:** the PM fixture leaves the link out. The two setup-needed boards then list it as a `no field` exception.
2. **"See what closure needs" has no closure page yet.** SCR-49 is FE-DELIVERY-CLOSURE, not built.
   - **Recommend:** a `work` link (F-32 kind) to a plain closure item, W-3120. The generic work item page draws W-3120, the same way F-32 used W-2510 for go-live. It is not SCR-49.
   - **Option B:** leave the link out (a `no field` exception on the two qualified boards).
3. **The default and qualified boards show criteria as MET, but PSL has not set the criteria (D11 open).**
   - **Recommend:** build both as sample fixtures, which is how the boards draw them. P-0101's Hypercare row links to the running item W-3101, which matches F-32's row text "Running · Day 10 of the window". The honest state today is the setup-needed item, and the mock's re-read after "Record release" lands there. No criterion text or MET is in `src/`.
   - **Option B:** the Hypercare row links to the setup-needed item W-3103. F-32's row text then disagrees with the page.
4. **"Setup needed" is drawn red, but the design system makes it amber.** Amber means waiting on someone (`STATE_TAGS.setup_needed` tone `person`, `frontend/src/components/Tag.tsx:65`; D-92b).
   - **Recommend:** the fixture returns status tone `person`, so the tag and the banner are amber. List the board's red as a colour difference.
   - **Option B:** the fixture returns `stopped`, so the tag is red. The banner stays amber, because the frame turns a banner red only on the issue line (`bannerTone`, `Workspace.tsx:104`). Changing that rule for every line is a frame change. Not recommended.
5. **"Log an observation" has no record behind it yet (G-46-1, blocking for the real write).**
   - **Recommend:** build it on the mock as a normal workspace step: `log_observation` with a required `long_text` "What did you notice?" and an optional `evidence` proof. List it as a contract proposal. The re-read shows the new `OBS-` row.
   - **Option B:** draw it unavailable with a returned `disabled_reason` such as "Not available yet" until the backend confirms, as D-111 did for F-29.

### Layout (phone against desktop, frame)
6. **The record form opens on press (D-69).** The board draws "Record the release" already open in the main column. The frame draws the "Record release" button in the side panel, and the form opens there when pressed.
   - The side panel uses the shared NEXT heading with the returned `next` line: "Engineering deploys outside the factory. You record what was released, with the deployment log as proof." The board draws this line as a blue note in the same column.
   - The form heading reads "Record release" (the step label), and the frame adds a Cancel button.
   - For fidelity, the driver presses the button, fills the form and uploads the proof, then freezes the page (as F-23 did).
   - Category: `frame layout`.
7. **Phone boards are shorter than desktop; the data is the same at both widths (D-99, D-111).**
   - On a phone the page shows the desktop sections stacked in one column, in the same order, with the desktop wording.
   - These phone texts are exceptions (`phone wording`): "Hypercare criteria aren't set yet. An admin sets them in Setup › Rules.", "Verified 01 May. 3 of 3 criteria met." and "Hypercare · day 10 of 30" as a heading.
   - These phone bar words are frame items: SETUP, QUALIFIED and "← Delivery". The phone bar keeps the built F-22 frame.
8. **Frame around the line.**
   - The delivery sub-nav is not drawn on a line item (D-113, F-32 Conflicts 5).
   - In the project tab bar, no tab is marked current (F-32 Conflicts 8).
   - The Planning tab is drawn only if F-31 has merged by build time.
   - Tab counts come from P-0101.
   - Category: `frame item`.
9. **Links row.** "Open Setup › Rules" and "See what closure needs" are drawn in the links row under the main column, not inside the Next panel, as F-32 did for "Open go-live" (`frame layout`).
10. **Observations table.**
    - The reference column gets the header "Reference". The board leaves it blank, and a blank header fails accessibility.
    - "Incidents" is a row with "—" as its reference text.
    - "Window · 30 days · from Setup" is a checklist item with a neutral tag, where the board draws plain grey text.
    - Category: `frame layout`.
11. **"See all exceptions" on the setup-needed state.** The frame draws this button for every exception state (`WorkItemOverview.tsx:713`).
    - **Recommend:** keep it (R-EXCEPTION is in this task's refs) and list it as an extra element.
    - **Option B:** hide it for `delivery_hypercare`. That is a line rule in `src/features/work-item/**`, which this feature reads only. Not recommended.
12. **Shared parts used as they are.**
    - The shared NEXT heading ("Next", `STEP_TEXT.next`) is used on all four states.
    - The shared timeline row is not used: no SCR-46 board draws a timeline, and no fixture has one.

### Exceptions to sign
13. **No field.**
    - The consequence's bold lead-in "What happens next:" is drawn as plain text. The whole sentence is the returned `consequence`.
    - The proof line reads as `ProofField` draws it, not "Uploaded · 96 KB".
    - The blue colour of the deploy note is not drawn (Conflicts 6).
14. **Frame items.**
    - The top bar and signed-in name.
    - "+ Start" (D-89).
    - The "Decide" panel class, and Cancel on the form.
    - The crumbs as returned: Projects / Lagoon Health / Delivery / HYP-0062.
15. **Sample data.**
    - The boards' Tamarind Loans becomes Lagoon Health (P-0101), so "Production · Lagoon Health" replaces "Production · Tamarind Loans".
    - Dates are 2026, to agree with F-32's release ready on 25 Mar and go-live signed on 02 Apr. Released 01 Apr 2026 22:00, window ends 01 May. The board says 2027.
    - ISS-0301 and OBS-0012 are fixture references. ISS-0301 has no link, because no issue fixture exists for it.
16. **Tones and visual waivers.**
    - Tags and banners take their tone only from the returned `tone`. A board colour the design system lacks is an exception, not a hard-coded value.
    - A board below 90 visual (and at 70 or more) carries a D-83 waiver citing the shared frame (D-99, D-110), once the design engineer signs it.

## Boards
| Board | File (`design/canvas/project/`) | Page | Width | How reached |
|---|---|---|---|---|
| SCR-46 default | `SCR-46-desktop.dc.html`, `SCR-46-mobile.dc.html` | `/work/W-3101` | 1440 / 390 | live URL, persona `pm` |
| SCR-46 record | `SCR-46-desktop-record.dc.html`, `SCR-46-mobile-record.dc.html` | `/work/W-3102` | 1440 / 390 | driver: reset the mock, press "Record release", fill released on (2026-04-01 22:00), upload `release-1.0.0-log.pdf`, then freeze without submitting |
| SCR-46 setup-needed | `SCR-46-desktop-setup-needed.dc.html`, `SCR-46-mobile-setup-needed.dc.html` | `/work/W-3103` | 1440 / 390 | live URL, persona `pm` |
| SCR-46 qualified | `SCR-46-desktop-qualified.dc.html`, `SCR-46-mobile-qualified.dc.html` | `/work/W-3104` | 1440 / 390 | live URL, persona `pm` |

## Summary
- P-0101's Hypercare delivery row (HYP-0062) gets `work_id: "W-3101"`. That is the only change to F-32's data. On the Delivery tab and in its sub-nav, Hypercare becomes a link.
- The hypercare work item (`/work/{id}`, line key `delivery_hypercare`, SCR-46) is drawn by the F-17 frame with no line-specific code, in four states:
  - record: the PM records version, released on, environment and the deployment log;
  - running: observations, incidents, criteria, Next and "Log an observation";
  - setup-needed: the backend's hold, with no step controls;
  - qualified: the verified banner, the criteria met, and "See what closure needs".
- Every day count, window, criterion, MET and "qualified" is returned text. The browser computes none of them. The qualified banner is green only because the returned tone is `verified`. Unknown reads "Unknown", never "None", blank or 0.
- Writes go through the existing `useWorkspaceStep` and `StepForm`, with the proof uploaded first. Nothing new shows as recorded before the re-read. A fixture covers each failure path.
- New in this feature: fixtures W-3101 to W-3112 and W-3120, an additive `work_id` on P-0101, and one proposed link kind (`setup_rules`). Three small shared fixes, each proved by a test:
  - an empty tag cell reads Unknown;
  - the done notice waits for the re-read;
  - the mock accepts a workspace step's proof upload.

  Contract mock only.

## Context
- **Delivery tab (F-32, merged first):**
  - `frontend/src/features/projects/DeliveryTab.tsx` draws `delivery[]`. A row links only when it has a `work_id` that passes `RECORD_ID`.
  - The sub-nav takes its labels from `short_title`.
  - Fixture: `frontend/mock/fixtures/projects/P-0101.json`. The Hypercare row is at `:143-154` in the F-32 tree and has no `work_id`.
- **Work item page:**
  - `frontend/src/features/work-item/WorkItemView.tsx`: `LineHeader` draws the status tag from `workspace.status`, and `ProjectBar` draws the project tabs.
  - `WorkItemOverview.tsx:699-739` mounts `Workspace` and adds "See all exceptions" for the exception states (`:511-519`, which includes `setup_needed`).
- **Workspace frame:** `frontend/src/features/workspace/`.
  - `Workspace.tsx`: `bannerTone` (`:104`), the Next/Decide panel (`:485-536`, heading `STEP_TEXT.next` when `next` is returned), and the links row (`:478`).
  - `Steps.tsx`: `StepControl` and F-32's `you_can_act` rule.
  - `StepForm.tsx`: the `text`, `datetime` and `long_text` fields via `IntakeField`, `evidence` via `EvidenceField` and `ProofField`, and field `value` pre-fill (`:175-193`).
  - `useWorkspaceStep.ts`: CSRF from the shared client; one idempotency key per attempt; 409 re-reads and shows the stale view; 5xx or network shows `STEP_TEXT.failed` and re-reads; `effect_uncertain` locks every step. Today it sets the done notice before `await page.reload()` (`:116-120`).
  - `Sections.tsx`: `CellValue` (`:169-191`) draws an empty tag cell as blank, which breaks INV-UNKNOWN for "Incidents".
  - `proposals.ts`: `workspaceLinks`, with kinds `assistant`, `project_tab`, `work` and `document`. `Links.tsx` draws them.
- **Setup:** `/setup/rules/delivery` exists (`frontend/src/app/setup/rules/delivery/page.tsx`; `AREA_ROUTES` at `src/features/setup/format.ts:52`).
- **Mock:**
  - E-WORK-ITEM serves `fixtures/work/<id>.json`.
  - E-WORK-STEP is `mock/workspace.mjs`. It applies `<id>.next.json` on 200 and runs `<id>.steps.json` scripts: a status, `next: true` for "written, then failed", or a 200 body `outcome`. It keeps an idempotency map and serves `GET /__mock/workspace-log`.
  - Work-item proof uploads go to `mock/response.mjs` `upload` (`:107-138`). Today it accepts only kinds named by response tasks, reconcile or RFP outcome, so a workspace step's proof is refused.
  - No `W-31xx` fixture and no `T-31xx` task exist in the project or in the F-31, F-32 or F-33 worktrees.
- **Gap notes:** `delivery/backend-handoff/gaps-d-delivery.md:96-112` (G-46-1 to G-46-3 and the four questions).
- **Tests that assert Hypercare has no link** (the only allowed assertion edits): `tests/delivery-overview.test.tsx:98` and `:207-216`, and `tests/delivery-release-mock.test.ts:146-155`. In each, the Hypercare entry gains `/work/W-3101`.

## Contract

### E-PROJECT `GET /api/v1/projects/P-0101` (unchanged operation)
- Only change: the `delivery[]` row with `line_key: "delivery_hypercare"` gains `"work_id": "W-3101"`. Every other key in `P-0101.json` stays byte-for-byte the same.

### E-WORK-ITEM `GET /api/v1/work/{work_id}` (unchanged)
F-17 Contract 1 to 11 and F-32's read rules apply:
- 401 shows the signed-out state with `next`.
- 403 and 404 look the same (`NoAccessState`, with no title, project or reference).
- 5xx shows `WorkErrorCard` with Retry.
- Loading shows `LoadingState`.

The page branches on nothing for `line_key: "delivery_hypercare"`.

Every fixture is:
- `sample: true`, `line_key: "delivery_hypercare"` (except W-3120), `screen: "SCR-46"`, `reference: "HYP-0062"`, `case_id: "P-0101"`;
- `workspace.context.project {case_id: "P-0101", title: "Lagoon Health · patient app"}`, crumbs Projects / Lagoon Health / Delivery / HYP-0062, `subtitle` "PM Tunde Bello";
- numeric `revision` and `workspace.revision` ≥ 1.

`case_revision` equals the value the mock's `upload` compares for P-0101, so an upload followed by a step succeeds. Each fixture validates against the generated 200 schema once `workspace.links` is removed.

| Id | `state`; `workspace.status` | Sections | Steps / next / links |
|---|---|---|---|
| W-3101 running | `processing`; "Hypercare · day 10 of 30", `person` | `table` "Observations so far", columns `ref` (reference, "Reference"), `what` ("What"), `state` (tag, "State"). Rows: ISS-0301 · "Login slow on older phones · medium" · "Open · owner set" (`person`); OBS-0012 · "Peak load on day 3 handled" · "Noted" (`neutral`); "—" · "Incidents" · "None" (`verified`). `checklist` "Criteria · from Setup › Rules (PSL to confirm)": Window (tag "30 days · from Setup", `neutral`); No open high-severity issues, No unresolved incidents, Medium issues have an owner (each `done`, tag "Met", `verified`) | `next: ["Tola evaluates hypercare when the window ends on 01 May. You can log an issue or observation any time."]`. Step `log_observation` "Log an observation" (secondary; fields `what` long_text required "What did you notice?", `proof` evidence optional, `evidence_kind: "hypercare_observation"`) |
| W-3101.next.json | as W-3101, revision + 1, with a new row OBS-0013 · the sample text · "Noted" | | |
| W-3102 record | `action_needed`; "Hypercare · release not recorded", `person` | none | `next: ["Engineering deploys outside the factory. You record what was released, with the deployment log as proof."]`. Step `record_release` "Record release" (primary; `consequence` "What happens next: the hypercare window starts from the release date. Go-live acceptance (02 Apr) is already recorded."; fields `version` text required, `value` "Build 1.0.0"; `released_at` datetime required; `environment` text required, `value` "Production · Lagoon Health"; `proof` evidence required, `evidence_kind: "deployment_log"`, label "Proof") |
| W-3102.next.json | the W-3103 hold under id W-3102, revision + 1 | | the honest result while D11 is open |
| W-3103 setup-needed | `setup_needed`; "Setup needed", `person` | Title-less note-only section: "Hypercare can't be evaluated: PSL hasn't set the hypercare criteria yet (how long the window is and what must be true at the end)." The observations table as W-3101. No criteria section | `next: ["An admin sets the criteria in Setup › Rules. Observations keep being collected meanwhile."]`. `links: [{key: "open_setup_rules", label: "Open Setup › Rules", target {kind: "setup_rules", area: "delivery"}}]`. **No steps** |
| W-3104 qualified | `verified`; "Hypercare qualified", `verified` | Title-less note-only section: "Hypercare qualified on 01 May, verified. All three criteria were met over the 30-day window." `checklist` "Criteria": the four rows as W-3101 | `next: ["Closure needs this. Remaining before closure: handover and retrospective."]`. `links: [{key: "closure_needs", label: "See what closure needs", target {kind: "work", work_id: "W-3120"}}]`. No steps |
| W-3105 | as W-3102; `W-3105.steps.json` `record_release` → 500, nothing written | | uncertain: not written |
| W-3106 | as W-3102; `record_release` → 500 with `next: true` (W-3106.next.json = the hold) | | uncertain: written, then failed |
| W-3107 | as W-3102; `record_release` → 200 `{outcome: "effect_uncertain", message: …}` | | uncertain effect: every step locks |
| W-3108 | as W-3102; `record_release` → 409 with `next: true` (W-3108.next.json = W-3102 at revision 2) | | stale |
| W-3109 | as W-3101, but `log_observation` has `disabled_reason` "Only the project's PM logs observations." (sample backend text) | | unavailable control |
| W-3110 | `processing`; "Hypercare · day 30 of 30", `agent`; `checklist` with `agent: tola` whose last item "Mark hypercare qualified" is `done` | | INV-AGENT: no banner, no "qualified" |
| W-3111 | as W-3101, but the Incidents row's state cell has no tag, the Window item has no tag, and one criterion is `status: unknown` with no tag | | Unknown case |
| W-3112 | as W-3101; `log_observation` → 500 with `next: true` (W-3112.next.json = W-3101.next under id W-3112) | | uncertain on the observation |
| W-3120 | a plain closure work item (no `workspace`) | | link target only; not SCR-49 |

No `T-31xx` task is used: there is no decision in part 1. The range T-3101..T-3199 stays reserved.

### E-WORK-STEP `POST /api/v1/work/{work_id}/steps` (unchanged operation)
- **Body:** `{expected_revision: workspace.revision, step, idempotency_key, inputs, evidence_ids?}`, with CSRF from the shared client.
  - `record_release` inputs: `{version, released_at (ISO 8601), environment}`, plus the deployment log in `evidence_ids`.
  - `log_observation` inputs: `{what}`, with `evidence_ids` only when a proof was uploaded.
- **Before any request:**
  - A blank required field shows its message under the field, and nothing is sent.
  - A record without a proof shows the proof message, and nothing is sent.
  - A failed upload shows `ProofField`'s problem, and the step stays unsent.
- **Replies:**
  - 200 `done`: the page re-reads, then shows the done notice with the re-read item.
  - 200 `effect_uncertain`: every step locks, the page shows "We are checking what happened. Nothing was sent again.", and it re-reads.
  - 409: the page re-reads and shows "This changed while you were working. Showing version N."
  - 422: field messages.
  - 403: "You can't take that step.", then a re-read.
  - 404 or 401: access lost.
  - 5xx or network: "We couldn't confirm this step. Check the page before trying again.", then a re-read. "Try again" keeps the same key, and the mock answers it from its map with no second send.
- **Permission and tenant:** the backend decides per record and step. A step shows only when the response carries it. A wrong-user or wrong-tenant write is a 403 or 404, and the page shows it the same way.

### E-EVIDENCE-UPLOAD `POST /api/v1/cases/P-0101/evidence` (unchanged operation)
The mock fix in `mock/response.mjs` `upload` is additive:
- It also accepts a `kind` named by an `evidence` field of a step in `workspace.steps[]` (with no `disabled_reason`) on a served item of that case.
- It grants that upload only on that condition.
- Everything else stays as it is (CSRF, case revision 409, the `none` persona 403).

### Proposals (mock overlay `frontend/mock/proposals/delivery-hypercare.json`; recorded in build.md)
| Proposal | Shape | Page |
|---|---|---|
| G-F34-1 link kind `setup_rules` | `{key, label, target: {kind: "setup_rules", area}}` | A `Link` to `AREA_ROUTES[area]` (`/setup/rules/delivery`), drawn only for a known area. An unknown area or kind draws nothing. Added to `proposals.ts` and `Links.tsx` |
| G-46-1 `log_observation` and `OBS-` rows | already expressible in v7 `steps[]` and `table` | Built on the mock; the real write is held |
| `environment` as `text` | v7 field kind | Free text until the backend says (gaps question) |
| `evidence_kind` `deployment_log`, `hypercare_observation` | v7 field key | Names are proposals |
| Not built | G-46-2 evaluation trigger; G-46-3 drop "Record go-live acceptance" from this line | Recorded only |

### Shared fixes (small; each proved by a failing test first)
1. **`Sections.tsx` `CellValue`:** in a `tag` column, a cell with no `tag` and no `text`, or a missing cell, reads "Unknown". The builder lists any existing fixture this changes. None is expected.
2. **`useWorkspaceStep.ts`:** on a 200 the done or queued notice is set after `page.reload()` resolves, not before. While the re-read is pending, no "Done:" text is on screen. The uncertain lock stays immediate.
3. **`mock/response.mjs` `upload`:** as above.

### Screen states
- **Loading, error, signed out, no access:** as above.
- **Record:** W-3102 (and W-3105 to W-3108 on failure).
- **Running:** W-3101, W-3109, W-3111, W-3112.
- **Setup-needed:** W-3103, which has no step controls and a links row only.
- **Qualified:** W-3104.
- **INV-AGENT:** W-3110.
- **Empty:** a copy with `sections: []` and no steps shows the frame's empty text.
- **Unknown:** a missing fact or tag reads "Unknown". It is never blank, "None" or 0.
- **Restricted:** a row or section with `restricted: true` shows only its label.
- No animation under `prefers-reduced-motion`.

## Lanes
- **Frontend lane (Sonnet builder; D-64) owns:**
  - Fixtures `frontend/mock/fixtures/work/W-3101.json` to `W-3112.json`, their `.next.json` and `.steps.json` sidecars, and `W-3120.json`.
  - The one `work_id` key in `mock/fixtures/projects/P-0101.json`.
  - `frontend/mock/proposals/delivery-hypercare.json`.
  - `src/features/workspace/proposals.ts` and `Links.tsx` (the `setup_rules` kind).
  - The two shared fixes in `Sections.tsx` and `useWorkspaceStep.ts`, and the `upload` fix in `mock/response.mjs`.
  - Tests:
    - new `frontend/tests/hypercare.test.tsx` and `tests/delivery-hypercare-mock.test.ts`;
    - `mock-contract.test.ts` (new fixtures, the overlay checked and stripped);
    - the three Hypercare link assertions;
    - new `frontend/e2e/delivery-hypercare.spec.ts`.
  - Factory files: `delivery/features/F-34/fidelity-exceptions.json`, `round-<N>/fidelity/**` (including `drive-states.mjs`), `round-<N>/build.md`.
- **Shared, read only:**
  - `src/features/work-item/**`, `src/features/decide/**`, `src/features/setup/**` (import `AREA_ROUTES` only), `src/features/projects/**`, `src/components/**`, `src/shell/**`, `src/api/**` including `schema.d.ts`, `src/styles/**`.
  - `Workspace.tsx`, `Steps.tsx`, `StepForm.tsx`.
  - `mock/server.mjs`, `mock/workspace.mjs`, `mock/setup.mjs`, `mock/evidence.mjs`.
  - Existing fixtures, except the P-0101 key.
  - `package.json`, the lock file, `playwright.config.ts`, `vitest.config.ts`, `architecture/**`, `design/**`, `apps/**`.
  - The protected `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json`.
- **Backend lane:** none. Record in build.md: G-46-1 to G-46-3, G-F34-1, and the four questions at `gaps-d-delivery.md:108-112`.
- **Integration owner:** the coordinator.
  - Rebase on dlv-00 after F-32 merges.
  - If F-31 or F-33 has merged first, keep their changes to `proposals.ts`, `Links.tsx` and `PROJECT_TABS`, then rerun `delivery/checks.sh` and the e2e.
- **Ports:** app **4880**, mock **4881** (not used in any spec or config).
  - Run `df -h /System/Volumes/Data` first and stop under 3 GB.
  - Run `cd frontend && E2E_PORT=4880 MOCK_PORT=4881 npx playwright test e2e/delivery-hypercare.spec.ts e2e/delivery-release.spec.ts e2e/workspace.spec.ts`, with `timezoneId: 'Africa/Lagos'`.
  - Delete `frontend/test-results` afterwards.
  - The e2e is not in `checks.sh`, so paste its output in build.md.
- **Review routing (medium risk):** technical (Sonnet), security (Sonnet: the writes and the upload grant), UI (fidelity gate on 8 boards), UX (Sonnet), QA (Opus). Product acceptance is required.
- **Size:** about 700 to 1,000 lines, mostly fixtures and tests. One PR.

## Acceptance criteria
Fidelity command per board. Swap `--board`, `--page`, `--width` and `--out`. Use the cookie `psl_mock_persona=pm` and a production build (`next build`, `next start -p 4880`, mock on 4881). The record boards are scored on the frozen page from `drive-states.mjs`:
```
node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs \
  --playwright <worktree>/frontend/node_modules/playwright/index.mjs \
  --board /Users/Hunchoo/psl-factory/design/canvas/project/SCR-46-desktop-setup-needed.dc.html \
  --page "http://localhost:4880/work/W-3103" --width 1440 \
  --cookies psl_mock_persona=pm \
  --exceptions /Users/Hunchoo/psl-factory/delivery/features/F-34/fidelity-exceptions.json \
  --wait-ms 500 --out /Users/Hunchoo/psl-factory/delivery/features/F-34/round-<N>/fidelity/SCR-46-desktop-setup-needed-1440
```

### Fidelity (8 boards, D-64, D-83)
1. **Scores.** One fidelity run per round covers all 8 boards in the Boards table.
   - Every board has `coverageWithExceptions` = 100 and `visual` ≥ 90.
   - A board at 70 or more but below 90 passes only with a D-83 waiver signed for that board in `fidelity-exceptions.json`, and only when the UI reviewer's side-by-side reading finds no fixable gap.
   - No board passes under 70.

   — verify: each command exits 0; `round-<N>/fidelity/scores.txt` lists board, width, coverage, visual, pass and waiver.
2. **Driven state is the real UI.** `drive-states.mjs` resets the mock (`POST /__mock/reset`) and uses the real controls: press, type and upload. Its only DOM edits are the freeze. It does not submit the record. — verify: the script and `frozen/*.html`; `GET /__mock/workspace-log` is empty after the drive.
3. **Exceptions limited.** Each entry has `role`, `name`, `category`, `reason` and `approved_by`, and maps to a Conflicts number. None covers a value the data can supply (a name, date, reference, tag, count or sentence). — verify: file content; build.md mapping.

### Page behaviour
4. **The row links to the line.** On `/projects/P-0101/delivery`, the Hypercare row and its sub-nav entry link to `/work/W-3101`. Every other row is as F-32 left it. — verify: the updated `delivery-overview.test.tsx` assertions; e2e.
5. **Four states from data.** `/work/W-3101`, `W-3102`, `W-3103` and `W-3104` each show their fixture's status label and tone, sections, steps, Next and links, and nothing else.
   - The criteria, window and day text appear only from the fixture. A copy of W-3101 with the criteria rows removed shows no criteria. A copy with "day 11 of 30" shows that text.
   - `grep -rniE "day [0-9]+ of|30 days|PSL to confirm|hypercare criteria|high-severity|closure needs|Met\b" frontend/src` finds no new match.

   — verify: `tests/hypercare.test.tsx` at 1440 and 390; grep.
6. **Setup-needed is the backend's hold, with no controls.**
   - W-3103 shows the amber banner, the observations, the Next line and "Open Setup › Rules" (a link to `/setup/rules/delivery`).
   - It shows no criteria rows, no MET, no "Log an observation", no "Record release" and no other button.
   - It also shows "See all exceptions" (Conflicts 11).
   - A copy with the link removed shows no Setup link. A copy whose `setup_rules` area is `nowhere` draws nothing.

   — verify: component tests; `getAllByRole('button')` on the workspace is empty.
7. **Qualified only when the response says verified (INV-AGENT).**
   - W-3104 shows "Hypercare qualified", the green banner and "See what closure needs", which links to `/work/W-3120`.
   - W-3110, whose agent step "Mark hypercare qualified" is done, shows no green banner, no "qualified" status and no closure link.
   - A copy of W-3104 with status tone `person` draws the amber banner.

   — verify: component tests.
8. **Unknown, not zero.** On W-3111, the Incidents state, the Window tag and the unknown criterion each read "Unknown". None of them shows blank, "None", "0" or "—". — verify: component test, which fails before the `CellValue` fix.
9. **Controls only from the response.**
   - A step shows only when `workspace.steps[]` carries it.
   - W-3109's "Log an observation" is an unavailable control (`aria-disabled`, no send) described by its returned reason.
   - A decision step on any of these fixtures follows F-32's `you_can_act` rule (unchanged).
   - Personas `pm`, `finance_lead` and `ceo` see the same controls for the same fixture.
   - The diff adds no `/me` read under `src/features/workspace`.

   — verify: component tests across fixtures and personas; diff.

### Writes
10. **Record the release.** In the e2e on `/work/W-3102`:
    1. Press "Record release". The form opens with Version "Build 1.0.0" and Environment "Production · Lagoon Health" pre-filled, and with the returned consequence.
    2. Submitting with Released on blank, or with no proof, shows the field message and sends nothing.
    3. Upload the proof. One E-EVIDENCE-UPLOAD is sent with `kind: "deployment_log"`, the case revision and CSRF.
    4. Submit. One E-WORK-STEP is sent with `step: "record_release"`, `expected_revision` 1, the three inputs, the returned `evidence_id`, an `idempotency_key` and the CSRF header.
    5. The page then shows the hold from the re-read.

    — verify: e2e with recorded requests and `GET /__mock/workspace-log`.
11. **No success before the re-read.** With the re-read held pending after a 200, no "Done:" text, no new status and no new row is on screen. Once the re-read resolves, they appear together. — verify: component test with a deferred second `GET /work/W-3102`, which fails before the `useWorkspaceStep` fix; the existing `workspace-step.test.tsx` done assertions stay green.
12. **Each uncertain path has a fixture and never shows "recorded".**
    - **W-3105 (500, nothing written):** shows "We couldn't confirm this step. Check the page before trying again." The re-read still shows "Release not recorded". "Try again" resends the same key, and the log shows one send.
    - **W-3106 (written, then 500):** shows the same message and no "Done:". The re-read shows the hold, and the log shows one send.
    - **W-3107 (effect uncertain):** every step locks, and "We are checking what happened. Nothing was sent again." shows. Nothing reads recorded.
    - **W-3108 (409):** shows "This changed while you were working. Showing version 2." and the form is kept.
    - **W-3112 (observation written, then 500):** shows the failed message. The re-read shows OBS-0013, and there is no "Done:".
    - **Network failure** on W-3102, with the request aborted in Playwright: the failed message and a re-read.

    — verify: e2e and component tests per fixture; the workspace log's `sends` per key.
13. **Log an observation.**
    - On W-3101, a blank "What did you notice?" sends nothing and shows the field message.
    - With text, one step is sent (`log_observation`, `inputs.what`, no `evidence_ids`). The re-read shows OBS-0013 · "Noted".
    - With an optional proof, `evidence_ids` carries the uploaded id.

    — verify: e2e; component test.
14. **Invalid and refused input.**
    - A 422 naming `released_at` shows that field's message, and the form is kept.
    - A 403 on the step shows "You can't take that step." and re-reads.
    - A 5xx on the upload shows `ProofField`'s problem, and no step is sent.
    - An upload from persona `none` answers 403.

    — verify: component tests with `X-Mock-Scenario`; `delivery-hypercare-mock.test.ts`.

### Access, phone and quality
15. **Access.**
    - A 401 on `/work/W-3101` shows the signed-out state with `next=/work/W-3101`.
    - A 403 and a 404 (`X-Mock-Scenario`), and an unknown id `/work/W-3199`, look the same: no title, project, reference or row text in `document.body.textContent`, and no further call.
    - A 404 or 401 on a step write shows the same no-access or signed-out view.

    — verify: component tests with a recording `fetch`.
16. **Phone.**
    - At 390 all four states are one column, with the desktop sections in desktop order (Conflicts 7), and there is no sideways scroll.
    - Every button, link, tab and form control is at least 44px tall (D-92c), including the open record form and the proof control.

    — verify: e2e at 390 measuring `getBoundingClientRect`.
17. **Accessibility.**
    - There are no axe violations (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`) at 1440 or 390 on W-3101, W-3102 with the form open, W-3103, W-3104, W-3109, W-3111 and the no-access view.
    - Every field has a label. The table has a header for every column.
    - Unavailable controls expose their reason through `aria-describedby`. Tags and status are text, not colour only.
    - Focus moves to the form heading on open and back to the button on Cancel.
    - Nothing animates under `reducedMotion: 'reduce'`.

    — verify: `e2e/delivery-hypercare.spec.ts`.
18. **Tokens and components only (D-91).** New UI uses `@/components` (`Link`, `Tag`, `Callout`, `Unknown`, `Button`) and adds no local button, tag, panel or link. `grep -nE "#[0-9a-fA-F]{3,8}\b|rgba?\(|hsl\("` on this feature's CSS and TSX diff returns nothing. — verify: diff and grep.
19. **Mock matches the contract.**
    - W-3101 to W-3112, their sidecars and W-3120 validate against the generated E-WORK-ITEM schema once `links` is removed. The `setup_rules` and `work` links validate against the overlays.
    - P-0101 still validates against E-PROJECT, with F-32's overlay.
    - Each step reply validates against E-WORK-STEP v7.
    - A repeated `idempotency_key` gets the stored reply with no second send.

    — verify: `cd frontend && npx vitest run tests/hypercare.test.tsx tests/delivery-hypercare-mock.test.ts tests/mock-contract.test.ts tests/delivery-release-mock.test.ts`.
20. **Contract not extended.**
    - `git diff --stat` shows no change in `frontend/src/api/**`, `apps/**`, `architecture/**`, `design/**`, `src/shell/**`, `src/features/work-item/**`, `src/features/decide/**`, `src/features/projects/**` or the protected paths.
    - No existing fixture is edited, except the one `work_id` key in `P-0101.json`.
    - Every overlay field and step proposal is listed in build.md as a contract proposal.

    — verify: `git diff --stat`; `git diff frontend/mock/fixtures/projects/P-0101.json` shows one added line; build.md.
21. **Existing behaviour not weakened.**
    - `delivery/checks.sh` passes.
    - `tests/workspace*.test.*`, `work-item*.test.tsx`, `delivery-overview.test.tsx`, `release-gates.test.tsx`, `delivery-release-mock.test.ts`, `issue-detail.test.tsx`, `minutes*.test.*`, `setup-rules.test.tsx` and their e2e specs pass.
    - No assertion is removed or loosened. The only assertion edits are the three Hypercare link entries.

    — verify: `delivery/checks.sh`; e2e output in build.md; `git diff` of `tests/`.
22. **No overclaim.** build.md and the PR carry the "What is sent, and what stays held" section: contract mock only; nothing deployed, evaluated or qualified; D11 open; the sample MET rows; the six held items. — verify: file content.

## Out of scope
- Part 2 boards: SCR-46 evaluating and not-met, Tola's evaluation run, "Open ISS-0315" and "Tola evaluates again".
- Part 3: all of SCR-47 archive and its reconcile.
- Any evaluation, day count, window end, criterion check or qualification in the browser. Any criterion or window wording in `src/`.
- Setting or editing any Setup rule from this page. Any deploy or "mark released" control. A "Record go-live acceptance" step (SCR-45 owns that record, G-46-3).
- The real closure page (SCR-49). W-3120 is only a plain link target.
- The sub-nav on the work item, an in-page always-open record form (`steps[].inline`), a red banner rule for other lines, and hiding "See all exceptions".
- A link from ISS-0301 to an issue page.
- Backend, OpenAPI, `schema.d.ts` regeneration, `architecture/**`, `design/**`, `src/shell/**`, new npm dependencies.

## Assumptions
- **Fixtures sit on P-0101 Lagoon Health, with 2026 dates.** Reason: they then agree with F-32's release (25 Mar) and go-live (02 Apr) rows; the boards' 2027 is sample text.
- **Fixture ids are W-3101 to W-3112 and W-3120; no T-31xx task is used.** Reason: the coordinator assigned the range, and part 1 has no decision.
- **After "Record release", the mock re-read is the setup-needed hold.** Reason: D11 is open, and a backend must not start a window it has no rule for.
- **The record step's status tone is `person`, and the running one's is also `person`.** Reason: amber means waiting on someone (D-92b), and both boards draw amber.
- **`environment` is a pre-filled text field.** Reason: the source leaves it open (gaps question), and text is the smallest choice.
- **"Engineering deploys outside the factory…" is a returned `next` line.** Reason: it then sits under the shared NEXT heading in the side column, where the board draws it, with no new field.
- **Observations are a `table` section, and Incidents is one of its rows.** Reason: the board draws one table, and v7 `table` covers it.
- **The done notice waits for the re-read on every line.** Reason: the coordinator's rule "no success before the re-read", and the change is two lines in the shared hook.
- **The `setup_rules` link goes to `/setup/rules/delivery` through `AREA_ROUTES`.** Reason: the page exists, and no path is hard-coded.
- **Personas: every board is served to `pm`.** Reason: controls come from the data, never from the persona.
- **Ports are 4880 and 4881.** Reason: no spec, config or demo server uses them.
