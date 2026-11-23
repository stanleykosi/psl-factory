# Setup connected to the live API: company Setup, rules, delegation and templates, with draft-then-review saves

> Re-specified against 1.24.0 (D-185). Tasks: FE-CONNECT-1. Architecture: v9 (D-SIGNIN r2 revision on main 12181de9) with live OpenAPI 1.24.0 (`contracts/psl-factory.openapi.json`, main b8542c79). Design: approved canvas as built under F-11, F-20 and F-27 (data-source change; the company selector, the no-access state and the draft steps are not drawn, see Conflicts with the boards); screens: SCR-13 (rules, delegation), SCR-34 (templates).

## Summary
- Setup opens on the company, not on a project. `GET /setup/scopes` (answer to B-21/B-27) lists the companies the signed-in Admin manages and the company policies with their authority workspace. Rules and Delegation read through that workspace; the person never has to know a project.
- A workspace choice stays only where a value really is per project: the Templates tab (the template catalogue takes a `case_id`, B-38). It is also the fallback on Rules and Delegation for someone who manages no company.
- 1.24.0 now supplies data the first spec hid: rule `component`, delegation names, reason and status, template document type, creator, recorded time, sample flag and download link. Those parts are built as the boards draw them.
- Saves are built as draft then review (new product behaviour, question N1): upload a signed decision PDF (`POST /setup/{case_id}/decision-proofs`), save a delegation draft or a template replacement, and review a version (validate, activate, revoke) only with the actions the server returns. A draft is never shown as in force.
- Rule edits stay unavailable: no current rule row maps to a typed-draft component (see Contract, Rules).

## Context
Today Setup is organisation-wide and reads v7 operations through the generated `api` client.
- `frontend/src/features/setup/api.ts`: `readRules` (`GET /api/v1/setup/rules`), `readTemplates`, `readDelegations`, plus `saveRule`, `uploadEvidence`, `uploadTemplateVersion`, `addDelegation`.
- Hooks `useSetupRules.ts`, `useDelegations.ts`, `useTemplates.ts` (first page plus "Show more"); write hooks `useRuleSave.ts`, `useDelegationAdd.ts`, `useTemplateUpload.ts`.
- Views `RulesView.tsx`, `FinanceRulesView.tsx`, `DeliveryRulesView.tsx`, `SetRulePanel.tsx`, `DelegationView.tsx` (already draws reason and status columns), `DelegationForm.tsx` (already has From, To, Starts, Ends, Reason), `TemplatesView.tsx`, `TemplateUploadPanel.tsx`; frame `SetupFrame.tsx` (`SetupLayoutFrame`, `SetupGate`, `RulesReadState`, `useSetupRead`). Routes `frontend/src/app/setup/(tabs)/{rules,delegation,templates}/page.tsx`, `frontend/src/app/setup/rules/{finance,delivery}/page.tsx`.
- Live client `liveApi` and `live-schema.d.ts` in `frontend/src/api/client.ts` (F-56/F-57); `liveApi.GET('/api/v1/me')` is used by `src/shell/AppShell.tsx`. Shared components: `FileUpload`, `Table`, `Tag`, `Callout`, `Select`, `DateField`, `TextField`, `ShowMore`, `SampleLabel`.
- Mock: `frontend/mock/setup.mjs`, `delegations.mjs`, `templates.mjs`, `projects.mjs`, routed from `mock/server.mjs`.
- Backend (read only, `apps/core/factory_api/setup.py`, `apps/core/setup_rules.py`): `scope_options` lists `organisations` only for people with `manage_access` authority and `workspaces` the person has `policy.read` on (25 a page); `rules` resolves each row's effective value for that workspace, so a workspace read includes company policy.

## Contract
All calls are same-origin through `liveApi`, signed-in session, writes carry `X-CSRFToken`. Errors use `{code, message, fields[]}`.

### Company scope and workspace choice (Setup header)
- `GET /api/v1/setup/scopes?page=` → `organisations[]` (strings), `workspaces[]` {`case_id`, `organisation`, `name`, `revision`, `can_configure`, `rules_url`, `policy_scopes_url`}, `next_page`, `organisation_policies[]` {`organisation`, `component`, `case_id`, `configuration_id`, `scope_id`, `policy_scopes_url`}, `organisation_policies_limited`. Read once on entering Setup; follow `next_page` (workspaces) up to 10 pages, keep what was read.
- Company mode (`organisations` not empty): header shows the company name; a company `Select` appears only when there is more than one company. Address `?company=<name>` on `/setup/rules`, `/setup/rules/finance`, `/setup/rules/delivery`, `/setup/delegation`. No `company` in the address: the first company, written to the address (replace, not push). Unknown `company` value: first company.
- Authority workspace of a company = the `case_id` of that company's `organisation_policies` entries (the first when they differ). Rules and Delegation read that `case_id`; `can_configure` for it comes from the matching `workspaces[]` entry (false or not found: write controls disabled, "You don’t have permission to change this setting.").
- A company with no `organisation_policies` shows `EmptyState` "No company settings have been set up yet." and makes no rules or delegation call. `organisation_policies_limited: true` shows "Some company settings are not listed."
- Workspace mode, where a value is per project: the Templates tab always, and Rules/Delegation when `organisations` is empty. A `Select` lists `workspaces[]` by `name`, grouped by `organisation`; address `?workspace=<case_id>`; default the first; an address workspace not listed is still tried and its read decides the state. Tab links keep `company` or `workspace`; switching Templates keeps the company in the address too.
- States: loading (`LoadingState`); `organisations` and `workspaces` both empty → "Nothing to set up here yet."; error (not 401) → `WorkErrorCard` "We couldn’t load Setup." with Retry; 401 → `SignedOutState`.
- Per-read access: a 404 or 403 on a workspace read shows "You don’t have access to this setup. Choose another." with the selector usable and no other content; the frame stays open. 5xx or network → `WorkErrorCard` with Retry and "Your work is safe; nothing was changed."
- Replaces the first spec's picker built from `GET /projects?status=active` (B-21, B-27, B-38 answered).

### Rules (SCR-13): `GET /api/v1/setup/{case_id}/rules`
- 200: `revision`, `as_of`, `items[]` {`label`, `area` ("Pre-sale", "All lines", "Finance", "Delivery"), `component`, `status` (ACTIVE, MISSING, UNAVAILABLE, UNKNOWN, INVALID), `version`, `value`, `details[]`, `roles[]`, `url`}. Ten fixed rows, no paging.
- Row: `label`, `area`, `version` when present, `value` or `roles[]` and `details[]`, and a status text on every row: Active, Not set (MISSING), "Can’t be read" (UNAVAILABLE, UNKNOWN), "Not valid" (INVALID). Unknown is never drawn as set or as zero. "Not set" badge = count of MISSING, derived from the loaded read; no Roles badge.
- `/setup/rules/finance` and `/setup/rules/delivery` filter the same read by `area`.
- `GET /api/v1/setup/primary-roles` turns role keys in `roles[]` into names; an unmatched key shows as returned.
- Row link: when `url` is set the row shows an "Open" link to it (the rule’s owning page). The per-row Edit control is not offered: the ten row components (D05.decision_action_matrix, D05.role_principal_assignments, P14-Q01.commercial_costing_rule_oracle, OPS.invoice_short_payment_review, D11.hypercare_criteria_ref, D11.template_storage_retention_rules, D12.stage_terms, OPS.bid_cost_adjustments) are not in the `typed-drafts` component list, and the API has no per-row `can_change` (B-23). `typed-drafts` is therefore not called. `SetRulePanel` and `useRuleSave` are not wired to the network.
- Versions and review: `GET /api/v1/setup/{case_id}/policy-configurations?component=<row.component>&page=` → `case_revision`, `items[]` {`id`, `component`, `version`, `state_id`, `state` (draft, validated, active, revoked, superseded), `actions[]` (subset of validated, active, revoked)}, `next_page`. A row’s "Versions" disclosure lists them with a plain state word (Draft, Reviewed, In force, Withdrawn, Replaced). One button per returned action, labelled "Mark reviewed", "Put in force", "Withdraw". No returned action means no button. Nothing is inferred from the person’s role.
- Review: `POST /api/v1/setup/{case_id}/policy-configurations/{configuration_id}/review` {`case_revision`, `state_id`, `transition`} → 200 {`id`, `component`, `version`, `state_id`, `state`, `actions[]`}. Each button asks for confirmation naming the version and the change. 409 → "This changed since you opened it." and a re-read; 422 and 403 show the server message (independent-review and domain-authority refusals are shown as returned, not worked around; Admin Setup ownership does not bypass a separate reviewer, B-24). Not retried automatically.

### Delegation (SCR-13): reads
- `GET /api/v1/setup/{case_id}/delegations` → `items[]` {`role`, `principal_id`, `delegate_id`, `principal`, `delegate`, `valid_from`, `valid_until`, `reason`, `status` (scheduled, current_window, expired)}, `as_of`, `configuration_id`, `django_url`. No paging.
- Row: role, "From" `principal`, "To" `delegate`, valid from, valid until, `reason` (blank when null, never invented; earlier versions may have none, B-26), status tag: scheduled "Upcoming", current_window "Active", expired "Ended". A null name shows "Person not listed". `django_url` is not used.
- `GET /api/v1/setup/{case_id}/delegations/options` (no `role`) → `revision`, `source_configuration`, `roles[]`, `people[]` {`id`, `label`}, `proofs[]` {`id`, `version`}, `limited`. Used by the add form only. `limited: true` shows "Names shown are limited to what you may see."
- Empty `items[]` → existing empty state. Access and error states as above.

### Delegation (SCR-13): add as a draft
- Control "Add delegation" opens the existing `DelegationForm` when `can_configure` is true; otherwise disabled with the reason above. Fields: Role (`options.roles`), From (`people`), To (`people`), Starts, Ends, Reason (optional text), Proof.
- Proof (shared by delegation and template replacement): the person chooses a signed decision PDF and enters its decision reference (up to 160 characters). Steps, shown as one "Attaching proof…" state: `POST /api/v1/cases/{case_id}/files` (multipart `file`) → `upload_id`; then `POST /api/v1/setup/{case_id}/decision-proofs` {`revision`, `upload_id`, `checked: true`, `decision_reference`} → 201 {`id`, `revision`}. `checked` is sent true only from an explicit checkbox "I checked this is the signed decision." The returned `id` is the evidence id; `revision` replaces the held revision. An existing proof from `options.proofs` may be chosen instead of uploading.
- Save: `POST /api/v1/setup/{case_id}/delegations/drafts` {`revision`, `source_configuration`, `submission_key` (uuid made once per form open and reused on retry), `role`, `principal`, `delegate`, `starts`, `ends`, `effective` (= `starts`), `evidence`, `reason`} → 201 {`configuration_id`, `version`, `revision`}.
- After 201 the screen says "Saved as a draft. It does not take effect until it has been reviewed and put in force." and shows the draft under "Waiting for review" with the Review buttons from `GET policy-configurations` (find the item whose `id` equals `configuration_id`, reading up to 3 pages). The delegation list is unchanged until the read shows it.
- Errors: 400/422 with `fields[]` → mark the named fields and keep entries; 409 → the message and re-read `options`, keep entries; 413/415 on the file → "That file can’t be used. Choose a PDF within the size limit."; network or 5xx → "We couldn’t confirm the save." and re-read; the retry reuses `submission_key`, so it cannot create a second draft.

### Templates (SCR-34): `GET /api/v1/projects/{case_id}/templates?templates=<cursor>`
- 200: `revision`, `can_upload`, `cursor`, `items[]` {`id`, `name`, `version`, `download_url`, `document_type`, `registered_by`, `registered_at`, `sample`}, `proofs[]` {`id`, `kind`, `version`}. Next page uses `templates` = returned `cursor`; null means the last page.
- Row: `name`, "Version N", kind from `document_type` (minutes, project_artifact, rfp_response, sow, status_report shown as plain words), "Updated by" `registered_by` with `registered_at`, a TEST TEMPLATE tag and the board’s test-template banner when `sample` is true, and a Download link from `download_url` (hidden when null). Still absent and not drawn: the Line column and the versions count (no source, B-39).
- Per-project value: the workspace selector above applies. "Show more" appends pages in order (`useSetupPaging`); a failed later page keeps loaded rows and says so. Empty `items[]` → "No templates to show." 404/403 → the no-access state.

### Templates (SCR-34): replace a version
- Control "Upload new version" on a row opens `TemplateUploadPanel` only when `can_upload` is true; otherwise disabled "You don’t have permission to change templates." Proof is attached as above, on this project’s `case_id`; a proof from `proofs[]` may be chosen instead.
- `POST /api/v1/projects/{case_id}/templates/replacements` multipart {`previous` (the row’s `id`), `proof` (evidence id), `revision` (from the template read or the proof step), `request_key` (uuid once per panel open, reused on retry), `file`} → 200 {`template_id`, `version`, `django_url`}. On 200 re-read; the new version row shows. 409 → message and re-read; 422/400 field errors keep entries; the original version is kept (the server keeps it).
- First-template registration (`POST /projects/{case_id}/templates`) is not built.

### Held and not built
`POST .../policy-configurations/typed-drafts` (no matching rule component), `POST .../policy-configurations` and `.../references`, `/setup/roles`, staff accounts, costing rule (SCR-39), HR field visibility, policy scopes and impact, decision appointments. `saveRule` and `uploadTemplateVersion` (v7) are not imported by any `src/features/setup` component after this change; `uploadEvidence` and `addDelegation` (v7) likewise.

### Screen states, fixtures
Each tab and the selectors have loading, empty, error, no-access and success.
- Fixture `/setup/scopes`: `organisations: ["PSL Nigeria"]`; `workspaces`: "Alpha Rollout" (`can_configure: true`) and "Beta Pilot" (`can_configure: false`, rules read 404); `organisation_policies`: one entry on Alpha’s `case_id`.
- Rules: ten rows with `component`, including one ACTIVE with `roles`, one MISSING, one UNKNOWN. `policy-configurations`: one `draft` with `actions: ["validated"]`, one `active` with `actions: ["revoked"]`.
- Delegations: one row `{role:"Finance lead", principal:"Ada Okafor", delegate:null, reason:"Leave cover", status:"scheduled"}` (delegate shows "Person not listed").
- Templates: two items over two pages, one with `sample: true`, `registered_by: "Tunde Bello"`, `document_type: "status_report"`.
- Proof fixtures: `cases/{id}/files` → `{upload_id: 7}`; `decision-proofs` → `{id: 41, revision: 12}`; `delegations/drafts` → 201; a 409 variant.

## Lanes
- Frontend lane (lane B): `frontend/src/features/setup/**`, `frontend/src/app/setup/**`, `frontend/mock/{setup,delegations,templates,projects}.mjs` plus handlers for the live paths, `frontend/e2e/setup*.spec.ts`, `frontend/tests/**` for setup.
- Backend lane: none; no backend change.
- Integration owner: runs the live check below.
- Shared files: `src/api` and `src/shell` are lane A’s; this feature does not change them (a shared proof-upload helper, if wanted by other features, is a separate small commit named in `build.md`). `src/features/workspace` is lane C’s.

## Acceptance criteria
1. Opening `/setup/rules` as an Admin with no `company` selects the first company, rewrites the address to `?company=<name>`, and shows the company’s rules read through its authority workspace, without any project being chosen. — verify: sign in as `live-admin`; the address holds `company=`, no project selector appears on Rules, the network log shows `GET /setup/scopes` then `GET /setup/<case_id>/rules` and no `GET /projects?status=active`.
2. With more than one company the company selector shows; with one it does not. Changing it re-reads the open tab and updates the address; reload keeps it. — verify: mock fixture with two companies, then one.
3. Tab links keep `company` (or `workspace`). — verify: click each tab; the address keeps it.
4. A company with no `organisation_policies` shows "No company settings have been set up yet." and makes no rules or delegation request. — verify: mock with empty `organisation_policies`; network log.
5. A person with no companies sees a workspace selector on Rules and Delegation filled from `scopes.workspaces`; the Templates tab always shows the workspace selector. — verify: mock fixture with `organisations: []`; Templates tab for an Admin.
6. Rules show label, area, version, value or roles and a status text on every row; the "not set" badge equals the MISSING count; UNKNOWN, UNAVAILABLE and INVALID are counted in neither. — verify: fixture and live read; unit test on the count.
7. `/setup/rules/finance` and `/setup/rules/delivery` list only their area’s rows. — verify: open each page.
8. A workspace read returning 404 shows "You don’t have access to this setup. Choose another." with the selector usable and no rule, delegation or template content; a signed-out session shows the signed-out state instead; a 500 shows "We couldn’t load …" with Retry and not the access text. — verify: mock "Beta Pilot"; clear the session cookie; blocked request in Playwright.
9. No Edit control is offered on rules and `typed-drafts` is never called; rows with `url` show an Open link. — verify: Playwright asserts no request to `/typed-drafts` on any Setup flow.
10. The "Versions" disclosure lists versions from `policy-configurations?component=` with a plain state word, and shows one button per returned action and no other. — verify: fixture draft shows only "Mark reviewed"; active shows only "Withdraw"; none shows no button.
11. A review action asks for confirmation, then posts `{case_revision, state_id, transition}`; 409 shows "This changed since you opened it." and re-reads; 403 and 422 show the server message and keep the version unchanged. — verify: Playwright with fixture variants; request body asserted.
12. Delegation rows show role, From, To, valid from, valid until, reason and status (Upcoming, Active, Ended); a null name shows "Person not listed"; a null reason shows blank. — verify: fixture row; unit test on the status map.
13. Adding a delegation uploads the PDF (`/cases/{id}/files`), records the proof (`decision-proofs` with `checked: true` only after the checkbox), then posts `delegations/drafts` with `evidence` equal to the returned proof id, a `submission_key` uuid and `effective` equal to `starts`; the success text says it is a draft and not in force; the list does not gain the row. — verify: Playwright asserts the three requests in order and the bodies; the delegation list is unchanged.
14. A failed or retried save reuses the same `submission_key`; a 422 marks the named fields and keeps entries; a 413 file shows the file message. — verify: Playwright with a failing then succeeding draft; the two requests carry the same key.
15. "Add delegation" and "Upload new version" are disabled with their reason when the authority workspace `can_configure` is false or `can_upload` is false, and open no panel and send no write. — verify: Playwright asserts no `POST` after clicking the disabled controls.
16. Templates show name, version, kind, updated by with time, a TEST TEMPLATE tag and banner only when `sample` is true, and a Download link only when `download_url` is set; no Line column and no versions count. — verify: fixture; network log shows page two requested with `?templates=` equal to the first `cursor`.
17. Replacing a template posts multipart `previous`, `proof`, `revision`, `request_key`, `file` to `.../templates/replacements`, then re-reads and shows the new version; the original is not removed from the UI until the read shows it. — verify: Playwright asserts the multipart fields; 409 shows the message and re-reads.
18. No component under `src/features/setup` imports `saveRule`, `addDelegation`, `uploadTemplateVersion` or `uploadEvidence` (v7), and `SetRulePanel` is not rendered. — verify: vitest greps the sources.
19. The mock (`npm run dev`) shows all three tabs and the selectors with the fixtures above and no live backend. — verify: open `/setup/rules`, `/setup/delegation`, `/setup/templates` from the lane worktree `frontend/`.
20. New and updated tests: unit tests for the badge count, the status map, the company-to-authority-workspace resolution and the proof sequence; Playwright specs for criteria 1, 8, 9, 11, 13, 14, 15, 16 and 17 in `e2e/setup.spec.ts`, `setup-delegation.spec.ts`, `setup-templates.spec.ts`. — verify: `npm run typecheck`, `npm run lint`, `npm test`, `npm run test:e2e -- setup` from the worktree `frontend/`.
21. Live check: Django on 8010 and Next.js on 4970 (LANES.md "Live backend for checks"), `live-admin`: Rules, Delegation and Templates show live data; a draft delegation can be saved with a PDF proof and appears under "Waiting for review" with the buttons the server returned; `live-none` sees no companies or workspaces and the "Nothing to set up here yet." state. — verify: browser, as above.

## Out of scope
- Editing a rule value (no typed-draft component matches a rule row; no per-row `can_change`); `typed-drafts`, the policy envelope draft and `references` calls.
- First-template registration, `/setup/roles`, staff accounts (SCR-21), costing rule (SCR-39), payroll field visibility, policy scopes and impact, decision appointments, organisation policy version creation through `policy-scopes`.
- Ending a delegation early; changing an active delegation other than through a new draft.
- Inventing fields the API still lacks: the template Line column and versions count, rule "holds N pieces of work", effective from, used-by, the Roles badge count, per-row `can_change`.
- Inventing approvers, policy values or proof stand-ins; treating a draft as in force; bypassing the server’s independent-review checks.
- Any change to `src/api`, `src/shell` or `src/features/workspace` beyond a separate small named commit.

## New product questions (1.24.0)
- **N1. Build the draft-then-review saves now?** 1. (Recommended, built) Yes: proof upload through `decision-proofs`, delegation draft, template replacement and the review buttons, all as drafts that are not in force until reviewed; rule value edits stay unavailable because the API has no draft path for the current rule rows. 2. Keep Setup reads only with the controls disabled (the earlier B3 answer). Reason: B-25 (proof creation) and B-22/B-24 (review) are now answered, and the earlier B3 hold was "until the backend answers".
- **N2. Company selector.** 1. (Recommended, built) A selector in the Setup header, shown only when the Admin has more than one company, with the choice in the address. 2. Always show the company name with no selector and read the first company only.
- **N3. Per-project values.** 1. (Recommended, built) Templates keep a workspace selector (the catalogue is per project; no company-wide list exists), and Rules and Delegation use it only for someone with no company. 2. Remove Templates from company Setup and open it from a project.
- **N4. Wording of states.** 1. (Recommended, built) Draft words: "Saved as a draft. It does not take effect until it has been reviewed and put in force."; state words Draft, Reviewed, In force, Withdrawn, Replaced; buttons "Mark reviewed", "Put in force", "Withdraw". 2. The design engineer supplies the words.

## Assumptions
- The company’s authority workspace is the `case_id` of its `organisation_policies` entries (the first if they differ); reason: `scopes` gives one "exact authority workspace" per company policy and no single company workspace field.
- `can_configure` for the authority workspace is taken from the matching `workspaces[]` entry; reason: it is the only per-workspace write flag returned (B-23, B-27). If the entry is not on the pages read, writes stay disabled.
- A person with no `organisations` falls back to a workspace selector on Rules and Delegation; reason: `organisations` is limited to people with staff-administration authority and `workspaces` still lists what they may read.
- `effective` equals `starts` in a delegation draft; reason: the form has no separate effective date and the board draws none.
- The proof step needs a decision reference text; reason: `decision-proofs` requires `decision_reference`; the form gains one plain field.
- The delegation status `current_window` is labelled "Active" because the read returns the active configuration’s current window; it is not a claim of any further effect.
- The "Open" link on a rule row uses `url` as returned; reason: the API supplies it and the board has a link slot.
- Mock handlers mirror the live shapes alongside the v7 ones; reason: keep design review working.

## Conflicts with the boards
D-182 hides now switched on (built as drawn, no longer conflicts): template TEST TEMPLATE tag and banner, "updated by" and kind; delegation reason and status columns and the From/To names. B10 hides that remain:
1. Company selector in the Setup header: not drawn. Recommend a simple select shown only for more than one company (N2), drawn afterwards.
2. Workspace selector on Templates (and the fallback on Rules/Delegation): not drawn. Recommend a simple select (N3), drawn afterwards.
3. Rules: the per-row Edit control stays absent, and the "Set a rule" panel is not shown, because no draft path exists for the current rows. New: a "Versions" disclosure with review buttons and an Open link. Recommend accepting; the board draws Edit, so this is a removal plus an addition.
4. Rules: "holds N pieces of work", effective from, used-by and the Roles badge count stay removed (no source). The "not set" badge stays.
5. Templates: the Line column and the versions count stay removed (no source, B-39). Recommend leaving them out.
6. Add delegation and template replacement gain a proof step (file, decision reference, "I checked" box) and a "Saved as a draft" result with a "Waiting for review" list; the boards draw a direct save. Recommend accepting (N1, N4) and drawing the steps.
7. Delegation list shows no "From/To filtered by role holders" pickers and no end-early control (no source). Recommend leaving out.
8. New "You don’t have access to this setup" state on each tab and "No company settings have been set up yet." empty state: not drawn. Recommend adding both to the canvas.
