DECISION: READY
RISK: high
SURFACES: ui, api, security, auth, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
COMMIT: none (round 0, no head yet)
REVIEWER: readiness
AUTHORITY: PMO readiness (delivery step 1)

## Summary
- All of FE-M3-SETUP is too big for one PR. It spans 38 boards and 7 screens, and most of them have no endpoint (role assignment, invite and deactivate, payroll visibility, the costing rule, clients). I propose six features (see Split below). This decision rates only the first one, **F-11 = Setup frame and Rules**.
- The gates for F-11 pass:
  - FE-M3-SETUP has no unresolved gates (architecture/packages/v6/delivery.md:1134-1163), and its only dependency, T-FRONTEND-SHELL, is merged.
  - D-API-STYLE and D-AUTH are approved at r2 (v6/reviews.json).
  - The client approved SCR-13 on 13 Nov (design/review.json:26).
  - The scope gate is the recorded early-start exception (v6/manifest.json:16-20). Its limits apply: mock only, nothing released, PSL approval still needed.
- E-SETUP-RULES and E-SETUP-RULE-SAVE carry the core: name, `set`, revision, and a versioned save with 409 and 422. The boards draw more than that (area, group, used by, current value text, "holds work", version date, who may change, the role options, starts, why, proof). Under the 14 Nov standing rule and decision (g) (architecture/sources/decisions-2026-11-14-v2.md), the frontend drafts those fields as a contract proposal and builds against them on the mock only. I list every field below. The backend developer confirms them.
- Risk is high. The save form edits who holds authority ("who may assign an RFP", "who reviews client documents", Finance reviewers and publishers) with a CSRF write. The UI must never present a default as a set rule, offer an edit to someone who may not change the rule, or imply that an Admin can approve. Under the overnight rules, high-risk features are built and reviewed but not merged; this one waits for the design engineer.
- One contract defect gets a binding workaround (PMO-0-1). A rule that is Not set has revision 0, but E-SETUP-RULE-SAVE requires `expected_revision >= 1`. That blocks A-SETUP's own scenario, saving a rule that is Not set.

## Findings
- PMO-0-1 | non-blocking | high | backend | The contract contradicts itself on the first save. E-SETUP-RULES gives `revision` a `minimum: 0` (v6/handoff.md:7402-7405), but E-SETUP-RULE-SAVE requires `expected_revision` with a `minimum: 1` (handoff.md:7550-7553). A-SETUP ("A Finance rule not set... save creates a new revision", model.json:10940-10942) and the board's "Save as version 1" both need to save a rule at revision 0. Binding engineering proposal: send the revision exactly as read (0 for Not set). The proposal relaxes the minimum to 0 and the mock accepts it. List this in build.md for the backend developer.
- PMO-0-2 | non-blocking | medium | integration | The mock validates against the strict contract (`additionalProperties: false`), so proposal fields would fail it. Expected:
  - Keep the proposal as its own JSON Schema overlay in `frontend/mock/proposals/setup.json`, and its TypeScript types in `frontend/src/features/setup/contract-proposal.ts`.
  - Do not edit `openapi.json`, `src/api/schema.d.ts` or `architecture/**`.
  - Tests check each fixture and each request body against the overlay. They also check that the same body, with the proposal fields removed, is valid against the v4/v6 operation schema, so the agreed core never drifts. (E-SETUP-* are the same in v4, which the mock loads, and in v6. None of the v6 changes in decisions-2026-11-14-v2.md touch setup.)
- PMO-0-3 | non-blocking | medium | product | The boards draw only one value editor: "Roles allowed" checkboxes. Rule values are opaque objects (`value: object`). Binding: the "Set a rule" panel edits only rules the backend marks `editor.kind = "role_set"`, and the options come from `editor.options`. Every other rule (statement contract, hypercare window, inclusion rule and so on) is shown read-only with its `display_value` or Not set. A group's "Set <group> rules" button (SCR-13-*-finance-rules) opens the panel with the Rule picker limited to that group's editable rules. Show the button only when the group has at least one. Record this for product acceptance. Editors for other value kinds wait until the design engineer draws them.
- PMO-0-4 | non-blocking | low | product | Two board errors must not be copied:
  - The "Roles allowed" list on SCR-13-desktop-rules shows "PMO Lead" twice, left over from the 13 Nov merge of Head of PMO into PMO Lead. The options come from the API, so the duplicate disappears.
  - The sample data disagrees between boards. The "Archive storage" rule is "Not set" on -rules but "Keep, never purge" on -delivery-rules. The banner says 8 rules are not set while 7 rows are Not set.

  Use one mock scenario per board for the fidelity check. Take counts from the proposal's `not_set_count`, never from the rows on screen. The design engineer should record both as approved fidelity exceptions.
- PMO-0-5 | non-blocking | medium | integration | The Proof field needs E-EVIDENCE-UPLOAD. No lane owns it yet: F-05 and F-06 exclude it, and the proof and response lanes are not started. F-11 adds a minimal setup-local attach control and a mock handler in its own `frontend/mock/evidence.mjs`, with one entry appended to `M1_OPERATIONS`. Whoever later builds the shared uploader (FE-M2A-PROOF or FE-M2B-RESPONSE) takes over that file and replaces the control. List this in build.md.
- PMO-0-6 | non-blocking | low | integration | The boards' persona is "Admin · sample", and the mock has only `finance_lead`, `pm` and `none` (frontend/mock/server.mjs:25). Add `fixtures/me.admin.json` and append `'admin'` to `PERSONAS`. These are additive one-line edits that the integration owner reconciles with any other lane adding personas. Show or hide the edit controls from the proposal's per-rule `can_change`, never from `/me` roles.

## Scope
**Binding for the spec writer.**

**Outcome (one, observable):** A Lead or Admin opens Setup. They see the Setup tab bar, and on Rules they see every rule they may read, with its area, current value or "Not set", and version or "Holds work". They can open the Finance rules and Delivery rules views grouped by line. A person whose `can_change` is true can pick a role-list rule and choose the roles allowed, a start date, a reason and proof. They save it as the next version and see the new version in the list. A stale save reloads and shows the newer version, and a 422 names the fields. A person who may only read sees no edit controls. This works at 390px and 1440px on the contract mock, and A-SETUP (frontend half) and A-ACCESSIBILITY pass.

**Boards in scope (every element, design-fidelity gate):**
- design/canvas/project/SCR-13-desktop-rules.dc.html
- design/canvas/project/SCR-13-mobile-rules.dc.html
- design/canvas/project/SCR-13-desktop-finance-rules.dc.html
- design/canvas/project/SCR-13-mobile-finance-rules.dc.html
- design/canvas/project/SCR-13-desktop-delivery-rules.dc.html
- design/canvas/project/SCR-13-mobile-delivery-rules.dc.html

The Finance and Payroll canvas has no Setup boards, so none are in scope from it.

**In:**
1. **Setup frame.** The SETUP eyebrow, the "Roles, rules and delegation" title and the seven-tab bar exactly as on -rules: Roles, Rules with its count badge, Costing rule, Delegation, Payroll visibility, Staff accounts, Templates.
   - Routes: `/setup/rules`, `/setup/rules/finance` and `/setup/rules/delivery`.
   - `/setup` redirects to `/setup/rules` until the Roles feature lands.
   - Tabs whose feature is not built link to reserved routes (`/setup/roles`, `/setup/costing-rule`, `/setup/delegation`, `/setup/payroll-visibility`, `/setup/staff`, `/setup/templates`). Each reserved route renders the frame plus the shared empty pattern (STATES-*). Record this for product acceptance.
   - The Roles badge comes from proposal `roles_missing_count` and the Rules badge from `not_set_count`. Show no badge when a count is absent, never 0.
2. **Rules list** (SCR-13-*-rules). Columns are RULE, AREA, CURRENT VALUE and VERSION.
   - Show `display_value` or the amber "Not set". The costing rule shows as a link to `/setup/costing-rule`.
   - The version cell shows either "vN · since <effective_from, Africa/Lagos>" or the HOLDS WORK tag when `holds_work` is true.
   - The banner sentence uses `not_set_count`.
   - Rows appear in the order returned. Page with `cursor` and "Show more" only when `next_cursor` is present.
3. **Finance and Delivery views.** These are E-SETUP-RULES with `area=finance` or `area=delivery`.
   - Finance is grouped by proposal `group` / `group_label` in the order returned, with NOT SET tags and the copy as drawn.
   - Delivery is a table of RULE, VALUE and USED BY (`used_by`), with the info callout and the "Next" panel.
4. **Set a rule panel.** It appears only when at least one rule has `can_change` and a `role_set` editor (PMO-0-3).
   - Fields: Rule (picker), Roles allowed (checkboxes from `editor.options`), Starts (date, prefilled with today in Africa/Lagos as drawn), Why (text) and Proof (PMO-0-5).
   - The button reads "Save as version {revision+1}". It sends E-SETUP-RULE-SAVE with `expected_revision` (PMO-0-1), `value: { roles: [...] }` as `editor` declares, and the proposal fields `starts`, `reason` and `evidence_id`, with the CSRF header.
   - On 200, reload the list.
   - On 409, show the API message, reload, and clear the person's edits (never re-apply them to a newer version).
   - On 422, mark the named fields and put the message in the panel's `role="alert"` callout.
   - 401 goes to SignedOutState. A 403 on read shows the no-access view.
   - Show the footnote "Rules are versioned...".
5. **Contract proposal** (PMO-0-2), listed in build.md for the backend developer:
   - E-SETUP-RULES item fields: `area`, `area_label`, `group`, `group_label`, `used_by`, `display_value`, `link`, `holds_work`, `effective_from`, `can_change` and `editor{kind, options[{role, label}]}`.
   - E-SETUP-RULES response fields: `not_set_count` and `roles_missing_count`.
   - E-SETUP-RULE-SAVE request fields: `starts`, `reason`, `evidence_id`. The minimum `expected_revision` becomes 0.
   - Each of these is a proposal and gates FE-CONNECT.
6. **Mock.**
   - The handler goes in `frontend/mock/setup.mjs` and the fixtures in `frontend/mock/fixtures/setup/`, with one scenario per board (PMO-0-4) plus a read-only persona scenario and an empty scenario.
   - The save is checked against the overlay and the revision, and updates an in-memory override that `/__mock/reset` clears.
   - Sample values carry the existing sample rule. No fixture value is presented as PSL's policy.
7. **Tests.**
   - Component tests: Not set vs set, holds work, the `can_change` gating, the editor options, the save body, revision 0, the 409 reload-and-clear, the 422 field mapping, 401 and 403.
   - Overlay tests (PMO-0-2).
   - Playwright, axe and the fidelity check for the six boards at 390px and 1440px.

**Out (proposed follow-on features):**
- **F-11B Delegation.** Boards: SCR-13-desktop-delegation, SCR-13-mobile-delegation. E-DELEGATION is a PUT only, with no list and no `from` or `reason` fields. It needs a list proposal. Risk is high (authority).
- **F-11C Roles and staff accounts.** Boards: SCR-13-desktop, SCR-13-mobile, SCR-13-desktop-permission, SCR-13-mobile-permission, SCR-13-desktop-validation, SCR-13-mobile-validation, SCR-21-desktop, SCR-21-mobile, SCR-21-desktop-invite, SCR-21-mobile-invite, SCR-21-desktop-deactivate, SCR-21-mobile-deactivate.
  - E-PEOPLE is read-only and lacks scope, invited state and last sign-in.
  - Role assignment ("Assign and resume held work"), invite and deactivate with reassignment have no endpoint.
  - Who holds Admin is for PSL to confirm (design/screens.md:154).
  - SCR-13-desktop still draws the old tab bar ("Roles · 2 missing / Rules · 13 open / Delegation / Alerts"). The design engineer must pick between it and the seven-tab bar.
  - It touches identity: high risk, NOT-READY until the backend contract exists.
- **F-11D Templates.** Boards: SCR-34-desktop, SCR-34-mobile. The list reads from E-TEMPLATES. The upload action has no endpoint. Risk is low to medium.
- **F-11E Payroll visibility.** Boards: SCR-13-desktop-fields, SCR-13-mobile-fields. It has no endpoint, and the HR Lead decides restricted payroll fields. High risk.
- **F-11F Costing rule.** Boards: SCR-39-desktop, SCR-39-mobile, SCR-39-desktop-review, SCR-39-mobile-review, SCR-39-desktop-example, SCR-39-mobile-example, SCR-39-desktop-review-own, SCR-39-mobile-review-own. These cover money, a review and confirm decision, and the 12 Nov rule that the proposer cannot review their own version ("backend change needed", screens.md:169). It has no endpoint. High risk, NOT-READY.
- **Not Setup:**
  - SCR-35 Clients (SCR-35-desktop, -mobile, -desktop-detail, -mobile-detail) sits on the Projects canvas page (p-projects-SCR-35-desktop) and goes to the projects lane.
  - SCR-24 Assign the accountable PM (SCR-24-desktop, -mobile) is a My work Unassigned drawer (rfp.assign) and goes to the My work lane.
  - Both lack endpoints.
- Also out of this feature: rule editors other than role lists (PMO-0-3), any edit to `src/shell/**`, `src/api/**`, `openapi.json` or `architecture/**`, and new npm dependencies.

**Ownership (disjoint from F-02, F-05, F-06, F-07, F-08):**
- Owns:
  - `frontend/src/app/setup/**`, which replaces the placeholder `page.tsx`;
  - `frontend/src/features/setup/**`;
  - `frontend/mock/setup.mjs`;
  - `frontend/mock/evidence.mjs`, held until a proof lane takes it over;
  - `frontend/mock/proposals/setup.json`;
  - `frontend/mock/fixtures/setup/**`;
  - `frontend/mock/fixtures/me.admin.json`;
  - `frontend/tests/setup*.test.ts(x)`;
  - `frontend/e2e/setup*.spec.ts`.
- Shared, additive only, each listed in build.md:
  - the `M1_OPERATIONS` entries for E-SETUP-RULES, E-SETUP-RULE-SAVE and E-EVIDENCE-UPLOAD;
  - the dispatch lines in `frontend/mock/server.mjs`;
  - `'admin'` in `PERSONAS`.
- Does not touch: `src/shell/**`, `src/api/**`, `my-work/**`, `decide/**`, `work-item/**`, `exceptions/**`, `overview/**`, projects or Start work files.

**Task IDs:** FE-M3-SETUP, the R-SETUP rules part only. FE-M3-SETUP stays open for F-11B to F-11F. **Endpoints:** E-SETUP-RULES (GET), E-SETUP-RULE-SAVE (PUT) and E-EVIDENCE-UPLOAD (proof). **Acceptance:** A-SETUP (frontend half) and A-ACCESSIBILITY.

## Risk
I rated it high:
- The save is a CSRF write to policy configuration (REC-CONFIG, INV-REVISION, INV-AUDIT; handoff.md:7508-7705). It sets who holds authority on pre-sale, documents and every Finance line.
- The UI must not:
  - invent or prefill a policy value ("Not set" is display only, and unknown is never shown as a value);
  - show edit controls without the backend's `can_change`;
  - re-apply stale edits after a 409;
  - imply that Admin confers approval (guide/10-POLICY-CONFIGURATION.md:16).
- It also adds an evidence upload.

Surfaces:
- `security` and `auth`: permission gating, CSRF, and 401 and 403 handling.
- `api`: two setup endpoints plus evidence.
- `contract-change`: the PMO-0-1 and PMO-0-2 proposal.
- `ui`: six boards.
- `product-decision`: PMO-0-3 and PMO-0-4, and the reserved-tab placeholders.

## Notes
- I could not run `design.py check` (I have no shell). The coordinator should confirm it passes for canvas 1794581312-b166 before the spec is written.
- No earlier readiness file exists for F-11.

## Questions
None for this slice. Before F-11C's readiness check, the design engineer should say which Setup tab bar is current (the SCR-13-desktop roles board vs the seven-tab bar), and PSL should name who holds Admin.
