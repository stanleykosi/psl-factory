DECISION: NOT-READY
RISK: medium
SURFACES: ui, api, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-34 is part 1 of FE-DELIVERY-HYPERCARE-ARCHIVE: 8 SCR-46 hypercare boards (default, record, setup-needed and qualified, each on desktop and phone). That meets the D-64 cap. The outcome is one hypercare line: the PM records the release, follows the window and its observations, sees the hold while PSL has not set the criteria, and sees "qualified" only when the backend verifies it. One PR.
- The only gate that fails is a dependency. These boards are drawn inside F-32's Delivery tab, its delivery sub-nav and its `work` link kind, and they need a `work_id` on the Hypercare row of F-32's P-0101 `delivery[]` fixture. F-32 (branch fe-delivery-release-delivery-tab-and-release-gate) is still unmerged: the approver said ESCALATE, and it waits on the design engineer's waivers and "merge". Once F-32 is in dlv-00 this becomes READY with no other change. The spec can be written now against F-32's branch head. Nothing should be built until the merge.
- The other gates pass. FE-DELIVERY-HYPERCARE-ARCHIVE has `gate_ids: []` and "Unresolved gates: none" (architecture/packages/v7/delivery.md:2317-2348). Its declared dependency FE-WORKSPACE-FRAME (F-17) is merged. SCR-46 and SCR-47 are in the 13 Nov client approval (design/review.json:54-55, approved 2026-11-13T15:33:13Z). The M-6 gates do not list this task. D-LINE-WORKSPACE and D-WORK-ACTIONS-VIEW are `proposed`, so they count only under the recorded contract-mock exception, as in F-30 and F-32.
- Policy hold, not invented: `delivery.hypercare_window` and `delivery.hypercare_criteria` are Not set. The policy slot is D11 `hypercare_criteria_ref` (contracts/policy-slots.json:920-933). Decision D11 is `open` (contracts/decision-registry.json:395-400), and the Setup fixtures show `set: false` (frontend/mock/fixtures/setup/delivery.desktop.json:4-30). The real "qualified" / "not met" transition is held. The setup-needed board is that hold. Qualified and the MET rows are fixture sample data only.
- I did not run `design.py check` (no shell in this role). The spec writer or builder runs it first and stops if it fails.

## Scope
**Outcome (one):** on a project's Delivery tab, a person opens the Hypercare row and reaches the hypercare work item (`/work/{work_id}`, line key `delivery_hypercare`, HYP-0062). There:
- The PM records the release: version, released on, environment and the deployment log as proof.
- The person follows the window: day N of M, observations and issues, incidents, criteria.
- The person can log an observation.
- When the criteria are not set, the person sees "Hypercare can't be evaluated" with "Open Setup › Rules".
- "Qualified, verified" appears only when the backend returns it.
- All of it runs on the contract mock.

**Boards (8):**
- SCR-46-desktop-record, SCR-46-mobile-record: "Record the release" (step `record_release`: `version` text, `released_at` datetime, `environment`, `evidence` proof), the consequence sentence as returned, and the "Engineering deploys outside the factory" note.
- SCR-46-desktop, SCR-46-mobile (default): "HYPERCARE · DAY 10 OF 30", the "Observations so far" table (ISS-0301 OPEN · OWNER SET, OBS-0012 NOTED), "Incidents NONE", the criteria facts and checklist with "from Setup › Rules (PSL to confirm)", Next, and "Log an observation".
- SCR-46-desktop-setup-needed, SCR-46-mobile-setup-needed: `state: setup_needed`, the banner, no criteria rows, "Observations keep being collected meanwhile", and "Open Setup › Rules".
- SCR-46-desktop-qualified, SCR-46-mobile-qualified: the verified banner, the criteria all MET, the Next sentence as returned, and "See what closure needs".

**Later parts (10 boards):**
- Part 2, 4 boards: SCR-46 evaluating and not-met, desktop and phone. Evaluating shows Tola's run (G-46-2, the evaluation trigger). Not-met is the rework path: "Open ISS-0315", "Tola evaluates again", "Closure stays blocked". Both rest on the same unset D11 criteria.
- Part 3, 6 boards: SCR-47 archive default, working and uncertain, desktop and phone. Expect NEEDS-INFO or backend holds:
  - G-47-1 (per-file found or not found reconcile) and G-47-2 (no archive-store integration) are both blocking.
  - The storage rule's status conflicts. The Setup fixture says `delivery.archive_storage` is set, revision 1 (delivery.desktop.json:68-78). rules.desktop.json:118-120 says `delivery.archive_retention` is `set: false`. D11 storage and retention is `open`. This must be settled before part 3. "Keep, never purge" must not be hard-coded (G-47-3).

**What F-34 needs from F-32 (merge first):**
- the Delivery project tab (`PROJECT_TABS` `delivery`) and the delivery sub-nav, with D-113 conflict 5 applied: the sub-nav sits on the Delivery tab only and is a frame exception on line items;
- the `work` link kind and the "links only from data" rule (G-44-2);
- the P-0101 `delivery[]` rows. F-34 adds a `work_id` to the Hypercare row (HYP-0062), which is an additive edit of F-32's fixture;
- the `delivery-release.json` overlay pattern and the W-25xx/T-25xx id range. F-34 takes an unused range: W-26xx if it is free, checked against F-31 and F-33.

**Task and endpoints:** FE-DELIVERY-HYPERCARE-ARCHIVE (R-WORKITEM), acceptance A-WORKSPACE. A-RECONCILE belongs to part 3.
- E-WORK-ITEM (GET /api/v1/work/{work_id}) and E-PROJECT for the tab and the row.
- E-WORK-STEP (POST /api/v1/work/{work_id}/steps) for `record_release` and `log_observation`.
- Evidence upload (`/api/v1/cases/{case_id}/evidence`) before the proof is attached. The F-17 StepForm already handles the `evidence` field.
- All of these are in frontend/src/api/schema.d.ts (lines 54, 159, 715). No new endpoint.

**Contract proposals (mock overlay only; record each in build.md for the backend developer):**
- G-46-1 (blocking for the real write): the workspace step `log_observation` (`long_text` what, optional `evidence`), and observations returned as table rows with `OBS-` references. Until the backend confirms it, "Log an observation" exists only through the overlay.
- G-46-2 (doc only here): the Next sentence "Tola evaluates hypercare when the window ends…" is shown as returned. The page schedules nothing.
- G-46-3: drop step 03 "Record go-live acceptance" from the hypercare line. SCR-45 owns that record. This page records only the release.
- The links "Open Setup › Rules" and "See what closure needs" render only from `workspace.links[]` (G-44-2). Closure (SCR-49) is not built, so its link points at a plain work item or is left out.

**Out:** SCR-46 evaluating and not-met; all of SCR-47; setting or editing any Setup rule; any deploy; any evaluation run or qualification logic in the browser; backend, OpenAPI, `schema.d.ts` regeneration, `architecture/**` and `src/shell/**`.

## Binding rules for the spec
1. **No rule in the browser.** Window length, day counts, the end date, the criteria text and each MET / NOT MET come only from `workspace` facts and items as returned. The frontend computes no day, no criterion and no qualification. With the rule Not set, the fixture returns `state: setup_needed` and no criteria, never "met". No criterion, window or "PSL to confirm" wording goes in `src/`.
2. **Verified only from the backend (INV-AGENT).** The qualified banner shows only from `state`/`workspace.status` `verified`. An agent step "Mark hypercare qualified" marked done is never the verified output. Tola's text shows as returned.
3. **Unknown is not zero.** If incidents or any fact cannot be read, it shows "Unknown", never "None", blank or 0 (gaps-d-delivery.md:110).
4. **Writes:** CSRF, `expected_revision` as read, and an `idempotency_key` on each step. The proof is uploaded before the step. A failed or timed-out write never shows "recorded". Re-read before offering a retry. Controls show only when the response sends them. 403 and 404 look the same (INV-ACCESS).
5. **Design-system rules.** Tokens and components only (D-91); labels on every field; 44px phone targets (D-92c); reduced motion respected; axe at 390 and 1440. One fidelity run per round over the 8 boards (D-64). Line boards follow the D-83 waiver route. Sonnet builder. Boards drawn on Tamarind Loans move to P-0101 Lagoon Health as in F-32 (sample data).

## Risk
Medium:
- The page has four states, two step writes and a proof upload, on the shared F-17 frame.
- It works against the proposed D-LINE-WORKSPACE contract and adds an additive step proposal (G-46-1, contract-change).
- No money, migration, identity or deploy effect is involved, and no control comes from a role.

`product-decision` is ticked because the hypercare window and criteria are a PSL rule, D11, still `open`. The pages only show the hold and the returned values. PRODUCT-ACCEPTANCE is required because the hypercare flow and its wording are new to the client.

## Questions
None for the client in this part. The block is F-32's merge. Backend confirmations hold the real write, not the mock build: the criteria value shape and who sets it (D-ADMIN-AUTHORITY), the source of the incidents count, a deterministic qualification check, and `environment` as free text or a supplied list (delivery/backend-handoff/gaps-d-delivery.md:108-112).
