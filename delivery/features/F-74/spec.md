# Setup connected to the live API for reading: workspace picker, rules, delegation and templates

> Tasks: FE-CONNECT-1. Architecture: v9 (D-SIGNIN r2 revision on main 12181de9) with live OpenAPI 1.22.0 (`contracts/psl-factory.openapi.json`). Design: approved canvas as built under F-11, F-20 and F-27 (data-source change only; the picker is new, see Conflicts with the boards); screens: SCR-13 (rules, delegation), SCR-34 (templates).

## Summary
- Setup opens on one chosen workspace (a project). A picker in the Setup header lists the person's active projects, and the choice stays in the address (`?workspace=<case_id>`) so reload and shared links work.
- Rules, Delegation and Templates read live data for that workspace: `GET /setup/{case_id}/rules`, `.../delegations`, `.../delegations/options`, `GET /setup/primary-roles`, `GET /projects/{case_id}/templates`.
- A workspace where `GET /setup/{case_id}/rules` returns 404 shows a plain "no access to this workspace" state. Nothing about hidden rules is shown.
- Every write is held: Edit a rule, Add a delegation and Upload a template version render disabled with the reason "Changes open once proof upload is connected". No write call is made.
- The v7 mock keeps working for design review: the mock serves the live shapes for these reads.

## Context
Today Setup is organisation-wide and reads v7 operations through the generated `api` client.
- `frontend/src/features/setup/api.ts`: `readRules` (`GET /api/v1/setup/rules`), `readTemplates` (`/setup/templates`), `readDelegations` (`/setup/delegations`), plus the writes `saveRule`, `uploadEvidence`, `uploadTemplateVersion`, `addDelegation`.
- Hooks: `useSetupRules.ts`, `useDelegations.ts`, `useTemplates.ts` (first page plus "Show more"); write hooks `useRuleSave.ts`, `useDelegationAdd.ts`, `useTemplateUpload.ts`.
- Views: `RulesView.tsx`, `FinanceRulesView.tsx`, `DeliveryRulesView.tsx`, `SetRulePanel.tsx`, `DelegationView.tsx`, `DelegationForm.tsx`, `TemplatesView.tsx`, `TemplateUploadPanel.tsx`; frame `SetupFrame.tsx` (`SetupLayoutFrame`, `SetupGate`, `RulesReadState`, `useSetupRead`). Routes in `frontend/src/app/setup/(tabs)/{rules,delegation,templates}/page.tsx` and `frontend/src/app/setup/rules/{finance,delivery}/page.tsx`.
- Types: `contract-proposal.ts` (v7 plus overlay). The live client `liveApi` and `live-schema.d.ts` are in `frontend/src/api/client.ts` (F-56/F-57); `liveApi.GET('/api/v1/me')` is already used by `src/shell/AppShell.tsx`.
- Mock: `frontend/mock/setup.mjs`, `delegations.mjs`, `templates.mjs`, `projects.mjs`, routed from `mock/server.mjs`.
- Backend (read only): `GET /api/v1/projects?status=active`, `GET /api/v1/setup/{case_id}/rules`, `.../delegations`, `.../delegations/options?role=`, `GET /api/v1/setup/primary-roles`, `GET /api/v1/projects/{case_id}/templates?templates=<cursor>`. Mapping notes: `delivery/connect/screens-b-projects-setup-clients.md` (SCR-13, SCR-34).

## Contract

### Workspace picker (Setup header, all Setup tabs that read)
- Source: `GET /api/v1/projects?status=active` → `items[]` {`case_id`, `title`, `revision`, ...}, `next_cursor`. Follow `next_cursor` until it is null (stop at 10 pages and keep what was read). Show `title`; the option value is `case_id`.
- Address: `?workspace=<case_id>` on `/setup/rules`, `/setup/rules/finance`, `/setup/rules/delivery`, `/setup/delegation`, `/setup/templates`. Tab links and the picker keep it. Changing the picker replaces the query and re-reads the open tab.
- No `workspace` in the address: select the first project in the list and write it to the address (replace, not push). An address `workspace` not in the list is still tried; its rules read decides the state (below).
- States: loading (existing `LoadingState`); empty list → `EmptyState` "No workspaces to show." and no further Setup call; error (not 401) → `WorkErrorCard` "We couldn’t load the workspaces." with Retry; 401 → `SignedOutState`.
- The workspace `revision` (from the rules read, `revision`) is held in view state for later writes and is not sent anywhere in this release.
- Per-workspace access: `GET /setup/{case_id}/rules` → 404 (also 403) means no `policy.read`. The tab body shows `NotOpenState`-style text "You don’t have access to this workspace’s setup. Choose another workspace." with the picker still usable. The frame stays open in this case (it does not close as `SetupLayoutFrame` does for other failures). 401 → signed-out state. 5xx or network → `WorkErrorCard` with Retry, "Your work is safe; nothing was changed."

### Rules (SCR-13): `GET /api/v1/setup/{case_id}/rules`
- Response 200: `revision`, `as_of`, `items[]` {`label`, `area` ("Pre-sale", "All lines", "Finance", "Delivery"), `status` (ACTIVE, MISSING, UNAVAILABLE, UNKNOWN, INVALID), `version`, `value`, `details[]`, `roles[]`, `url`}. Fixed set, no paging, no `component`.
- Row shows `label`, `area`, `version` when present, `value` or `roles[]` and `details[]`. Status text is shown for every row: Active, Not set (MISSING), and for UNAVAILABLE, UNKNOWN and INVALID a plain "Can’t be read" / "Not valid" tag. Unknown is never drawn as set or as zero.
- Tab badge "not set" = count of `status === 'MISSING'` rows, derived in the client from the loaded read; the Roles badge is absent (no source). The "Show more" footer and `useSetupPaging` stay only if the list exceeds the page window.
- `/setup/rules/finance` and `/setup/rules/delivery` filter the same read by `area` ("Finance", "Delivery").
- `GET /api/v1/setup/primary-roles` → `roles[]` {`key`, `name`, `description`, `functions[]`, `definition_id`}: used only to turn role keys in `roles[]` into the role names; a key with no match shows as returned.
- Errors: as in the picker section. Access: server-checked per workspace; the client never infers access beyond the 404 above.
- Held (not called, no hook wired to the network): `POST /setup/{case_id}/policy-configurations/typed-drafts`, `POST /setup/{case_id}/policy-configurations/{id}/review`.

### Delegation (SCR-13): `GET /api/v1/setup/{case_id}/delegations` and `.../delegations/options`
- `delegations` 200: `items[]` {`role`, `principal_id`, `delegate_id`, `valid_from`, `valid_until`}, `as_of`. No paging, no revision, no reason or status.
- `options` 200 (called once without `role`): `revision`, `roles[]`, `people[]` {`id`, `label`}, `proofs[]`, `source_configuration`, `limited`. Names come from `people[]` by id. An id not in `people[]` shows "Person not listed", never a guessed name. `limited: true` shows the note "Names shown are limited to what you may see."
- Row shows role, "From" name, "To" name, valid from, valid until. No reason and no status column.
- Empty `items[]` → existing empty state. Error and access states as above; a 404 on `delegations` is treated like the rules 404.
- Held: `POST /setup/{case_id}/delegations/drafts`. The Add delegation control is disabled with "Changes open once proof upload is connected"; `DelegationForm` does not open.

### Templates (SCR-34): `GET /api/v1/projects/{case_id}/templates?templates=<cursor>`
- 200: `revision`, `can_upload`, `cursor`, `items[]` {`id`, `name`, `version`, `download_url`}, `proofs[]`. The next page is requested with the query value `templates` set to the returned `cursor`; `cursor` null/absent means the last page.
- Row shows `name` and "Version N". Absent and not drawn: line, test-template tag and banner, updated-by, versions count, kind.
- "Show more" appends pages in order (existing `useSetupPaging`). A failed later page keeps loaded rows and says so.
- Held: `POST /projects/{case_id}/templates/replacements` and first-template `POST /projects/{case_id}/templates`. The Upload control shows disabled with "Changes open once proof upload is connected" whether or not `can_upload` is true; `TemplateUploadPanel` does not open.
- Access: 404/403 → the no-access state; empty `items[]` → "No templates to show."

### Held writes (listed in the PR description)
`POST .../policy-configurations/typed-drafts`, `POST .../policy-configurations/{id}/review`, `POST .../delegations/drafts`, `POST /projects/{case_id}/templates/replacements`. Reasons: evidence id cannot be created yet (B-25/B-40) and the draft-then-review design is not approved (B-22/B-24). `useRuleSave`, `useDelegationAdd`, `useTemplateUpload` are not connected to the network; `saveRule`, `addDelegation`, `uploadTemplateVersion`, `uploadEvidence` are not called.

### Screen states, fixtures
Each of the three tabs and the picker has loading, empty, error, no-access and success.
- Fixture (mock and live-shaped): workspaces "Alpha Rollout" (`case_id` UUID, access) and "Beta Pilot" (rules read 404). Rules: ten fixed rows including one ACTIVE with `roles: ["Finance lead"]`, one MISSING (not-set badge counts it), one UNKNOWN. Delegations: one row `{role:"Finance lead", principal_id:3, delegate_id:9, valid_from, valid_until}` with `people:[{id:3,label:"Ada Okafor"}]` so id 9 shows "Person not listed". Templates: two items across two pages via `cursor`.

## Lanes
- Frontend lane (lane B): `frontend/src/features/setup/**`, `frontend/src/app/setup/**`, `frontend/mock/{setup,delegations,templates,projects}.mjs` and mock routing for the live paths, `frontend/e2e/setup*.spec.ts`, `frontend/tests/**` for setup. Mock handlers for the live shapes live in the same feature and keep the v7 design-review mock working.
- Backend lane: none; no backend change.
- Integration owner: runs the live check below.
- Shared files: `src/api` and `src/shell` are lane A's; the picker does not touch them (any need, such as a shared `liveApi` helper, is a separate small commit named in `build.md`). `src/features/workspace` is lane C's and is not changed.

## Acceptance criteria
1. Opening `/setup/rules` with no `workspace` shows the picker, selects the first active project and rewrites the address to `?workspace=<case_id>`. — verify: open the page with `live-admin` signed in; the address contains `workspace=`, the picker shows the project title, and the rules list shows that workspace's ten rules.
2. Reloading the page or opening the saved link keeps the workspace; changing the picker re-reads the open tab and updates the address. — verify: select a second workspace; the address and the rows change; reload; the same workspace is selected.
3. Tab links (Rules, Delegation, Templates) keep `workspace`. — verify: click each tab; the address still holds the same `workspace`.
4. Rules show `label`, area, version, value or roles and a status text for every row; MISSING rows count in the "not set" badge; UNKNOWN, UNAVAILABLE and INVALID are not counted as set or not set. — verify: mock fixture and the live read in the browser; badge equals the MISSING row count.
5. `/setup/rules/finance` and `/setup/rules/delivery` list only rows with area "Finance" / "Delivery". — verify: open each page.
6. A workspace whose rules read returns 404 shows "You don’t have access to this workspace’s setup. Choose another workspace." with the picker usable, and shows no rule, delegation or template content. — verify: pick a workspace the account has no `policy.read` on (live-none or live-lead; or the mock "Beta Pilot"); the same text shows on all three tabs; network log shows no other Setup read succeeding for it.
7. A signed-out session shows the signed-out state, not the access text. — verify: clear the session cookie and reload.
8. Delegation rows show names from `options.people`; an id that is not listed shows "Person not listed". — verify: mock fixture row with delegate id 9.
9. Templates show name and version, load further pages with Show more using `templates=<cursor>`, and show no line, test-template tag, updated-by or versions. — verify: network log shows a second request with `?templates=` equal to the first response's `cursor`.
10. Edit rule, Add delegation and Upload version are disabled and show "Changes open once proof upload is connected"; clicking them opens no panel and sends no request. — verify: Playwright asserts no `POST`, `PUT` or `PATCH` request to `/api/v1` after clicking each control on the three tabs.
11. Unit test: `saveRule`, `addDelegation`, `uploadTemplateVersion` and `uploadEvidence` are not imported by any component in `src/features/setup` after the change. — verify: `npm test` (new vitest) greps the feature sources, or the equivalent import check.
12. A 500 or network failure on any read shows "We couldn’t load the …" with Retry and does not show the access text; Retry re-reads. — verify: mock failure fixture or blocked request in Playwright.
13. An empty workspace list shows "No workspaces to show." and makes no `/setup/{case_id}/…` request. — verify: mock with no projects.
14. The mock (`npm run dev`) shows the same three tabs and the picker with the fixtures above, with no live backend. — verify: run the mock from the lane worktree `frontend/` on its port and open `/setup/rules`.
15. New and updated tests: unit tests for the status-to-badge count and the id-to-name lookup, and Playwright specs for criteria 1, 2, 6, 9 and 10, updating `e2e/setup.spec.ts`, `setup-delegation.spec.ts`, `setup-templates.spec.ts`. — verify: `npm run typecheck`, `npm run lint`, `npm test`, `npm run test:e2e -- setup` from the worktree `frontend/`.
16. Live check: with Django on 8010 and Next.js on 4970 (LANES.md "Live backend for checks"), signed in as `live-admin`, `/setup/rules`, `/setup/delegation` and `/setup/templates` show the live data for a workspace the account can read, and `live-none` sees the no-access state. — verify: browser, as above.

## Out of scope
- All writes (see Held writes). No `evidence_id`, no proof upload, no draft or review UI, no "Saved as draft" copy.
- First-template registration, the template download link (`download_url`), `/setup/roles`, `.../primary-roles` per workspace, SCR-21 staff accounts, SCR-39 costing rule, payroll field visibility, policy scopes and impact, decision appointments.
- Inventing fields the API lacks: `can_change`, `component`, the template line column, test-template tag, updated-by, versions, delegation reason and status, "holds N pieces of work", Roles badge count. No approvers, policy values or proof stand-ins.
- Choosing an organisation workspace for organisation-wide values (open backend question B-21/B-27/B-38).
- Any change to `src/api`, `src/shell` or `src/features/workspace` beyond a separate small named commit.

## Assumptions
- B1 default: Setup always opens on a chosen workspace; reason: recommended option in `questions-batch.md`; product acceptance confirms or changes it.
- B2 default: a simple picker in the Setup header with the choice in the address; reason: recommended option; not yet drawn.
- B3 default: reads only, controls disabled; reason: recommended option. Wording is "Changes open once proof upload is connected" (the batch B3 text, chosen by the coordinator).
- The address key is the query value `workspace`, not a route segment; reason: keeps the five existing routes unchanged.
- With no workspace in the address, the first active project is chosen; reason: avoids probing every workspace for `policy.read`; the cost is that the first project may show "no access".
- The picker lists active projects only (`status=active`) and follows `next_cursor` up to 10 pages; reason: readiness names that endpoint; no other source of workspaces exists.
- "Not set" counts MISSING only; UNAVAILABLE, UNKNOWN and INVALID are shown by their own plain tag and counted in neither; reason: unknown values are not zero.
- Delegation names come from one `options` call without `role`; reason: the delegations read returns ids only. If the backend limits `people` per role, some ids show "Person not listed".
- The 403 case is handled like 404 as no access; reason: the existing `RulesReadState` treats both the same so nothing about hidden rules leaks.
- The mock gains handlers for the live shapes (the live paths) alongside the v7 ones; reason: the instruction to keep the mock working for design review.

## Conflicts with the boards
1. Workspace picker in the Setup header: not drawn on SCR-13 or SCR-34. Recommend approving a simple select in the header (B2) and drawing it afterwards.
2. Disabled Edit, Add delegation and Upload controls with a reason line: boards draw them active. Recommend keeping them visible and disabled (B3 option 1).
3. Templates: the Line column, TEST TEMPLATE tag and banner, "updated by", "N versions" and kind are removed; the API returns none. Recommend leaving them out until the backend answers B-39.
4. Delegation: the reason and status (scheduled/active/ended) columns and the "From/To" pickers filtered by role are removed or absent; the API returns neither. Recommend a read-only list with role, names and dates.
5. Rules: Edit control per row, "holds N pieces of work", effective from, used-by and the Roles badge count are removed. Recommend leaving them out; the "not set" badge stays, derived from status.
6. New "no access to this workspace" state on each tab: not on the boards. Recommend adding it to the canvas.
