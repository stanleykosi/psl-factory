# A Lead or Admin opens Setup, reads every rule with its value or "Not set", and saves a role-list rule as its next version

> Tasks: FE-M3-SETUP (R-SETUP rules part only; FE-M3-SETUP stays open for F-11B to F-11F). Architecture: package v7 (proposal), manifest digest `f6231d20b4fdeabbdca9bde5986a0a7883536f1a5cafc883848ef62dd6d4b624` (`architecture/packages/v7/manifest.sha256`); fields from D-SETUP-RULES-VIEW r1 (proposed, mock only). The app and mock stay on v4 (`9d4cbc10137ee452d29d240876cf07fbf13d02ac63e9b0fbdddb1256ae568ff0`); F-13 repoints to v7 separately. Acceptance: A-SETUP (frontend half), A-SETUP-RULES-VIEW (frontend half), A-ACCESSIBILITY. Design: approved canvas version 1794581312-b166 (`design/review.json`); screens: SCR-13 states rules, finance-rules, delivery-rules. Artboards: `design/canvas/project/SCR-13-{desktop,mobile}-rules.dc.html`, `SCR-13-{desktop,mobile}-finance-rules.dc.html`, `SCR-13-{desktop,mobile}-delivery-rules.dc.html`. The shared empty, loading and error patterns come from `STATES-desktop.dc.html` and `STATES-mobile.dc.html`.

## Summary
- `/setup` redirects to `/setup/rules`. That page shows the Setup frame (SETUP eyebrow, "Roles, rules and delegation", the seven-tab bar with Roles and Rules count badges). Below it are the "N rules aren't set yet" banner, the RULE / AREA / CURRENT VALUE / VERSION table and the "Set a rule" panel, as drawn on SCR-13-desktop-rules. `/setup/rules/finance` and `/setup/rules/delivery` show the grouped Finance view and the Delivery table. Below 720px all three show the phone boards.
- Every value comes from E-SETUP-RULES. "Not set" means only `set: false`. Counts come only from `not_set_count` / `roles_missing_count`. Edit controls appear only on rows with `can_change: true` and `editor.kind: "role_set"`. Nothing is defaulted, inferred from `/me` roles or computed from rows.
- The panel saves through E-SETUP-RULE-SAVE: `expected_revision` exactly as read (0 for Not set), `value: {roles}`, `starts`, optional `reason` and `evidence_id`, with the CSRF header. A 200 reloads the list. A 409 shows the message, reloads and clears the edits. A 422 marks the named fields. A network or server error reloads and never resends on its own.
- The six other tabs open reserved routes that show the frame plus the shared empty pattern ("… comes next").
- The mock gets `frontend/mock/setup.mjs` and `frontend/mock/evidence.mjs`, one fixture per board, an `admin` persona, and a JSON Schema overlay for the proposal fields. Tests prove that each fixture and request body is valid against the overlay, and still valid against v4 once the proposal fields are removed.

## Context
- **Route today:** `frontend/src/app/setup/page.tsx` renders `DestinationPage destination="setup"` (`frontend/src/shell/DestinationPage.tsx`), the placeholder "This page is not built yet." Nothing exists under `frontend/src/features/setup/`.
- **Frame:** `frontend/src/app/layout.tsx` wraps every page in `AppShell` (`frontend/src/shell/AppShell.tsx`). `destinationForPath` (`frontend/src/shell/destinations.ts`) already marks Setup as current for any `/setup/*` path. `useMe()` gives `destinations`, and `NotOpenState`, `SignedOutState` and `LoadingState` are in `frontend/src/shell/FrameStates.tsx`. The top bar shows `me.name · me.roles` (`TopNav.tsx:35-36`).
- **API client:** `call(api.GET|PUT|POST(...))` in `frontend/src/api/client.ts` adds `X-CSRFToken` on writes (from `/me`, kept in memory). `ApiError.kind` (`frontend/src/api/errors.ts`) is `unauthenticated | forbidden | not_found | stale | invalid | server | network`. `frontend/src/api/schema.d.ts` is generated from v4 and has `operations['E-SETUP-RULES']` (line 2402) and `operations['E-SETUP-RULE-SAVE']` (line 2473) with only the core fields: `component, name, value?, set, revision`; `next_cursor?`, `as_of`; body `expected_revision (min 1 in v4), value`.
- **Contract (v7 proposal, `architecture/packages/v7/openapi.json`):**
  - `GET /api/v1/setup/rules?area=` (E-SETUP-RULES). Rows gain optional `area, area_label, group, group_label, used_by[], display_value, link, holds_work, effective_from, can_change, restricted, editor{kind: role_set|read_only, options[{role,label}], selected[]}`. The response gains `not_set_count` and `roles_missing_count`.
  - `PUT /api/v1/setup/rules/{component}` (E-SETUP-RULE-SAVE). `expected_revision` min 0, plus optional `starts` (date), `reason` and `evidence_id`. The response is `{component, revision}`, with 401/403/404/409/422 errors.
  - Evidence: `POST /api/v1/cases/{case_id}/evidence` (E-EVIDENCE-UPLOAD). The body `{kind, filename, content_base64, case_revision}` is required. It answers `{evidence_id, sha256, case_revision?}` (`case_revision` is v7 only).
- **Records and invariants:** REC-CONFIG (`case, component, revision, envelope`; "A missing value is Not set, never a default"); INV-REVISION (a mismatch returns 409 and changes nothing); INV-ACCESS; INV-AUDIT. A-SETUP-RULES-VIEW: "Save with expected_revision 0 creates version 1; not_set_count drops; the read-only Lead sees no edit control; a stale save returns 409 and re-applies nothing."
- **Mock today:** `frontend/mock/server.mjs`. It loads v4 routes, `M1_OPERATIONS` (line 25), `PERSONAS = ['finance_lead','pm','none']` (line 26), the CSRF check per persona token, scenarios by `X-Mock-Scenario` / `psl_mock_scenario` (applied before dispatch, declared statuses only, and to E-ME too), and `/__mock/reset` (clears `overrides`). Every other operation answers 501. `frontend/tests/mock-contract.test.ts` runs every `M1_OPERATIONS` entry for every persona and expects 200 with a v4-valid body. It also lists every persona's `/me` in "E-ME carries each persona fixture" (line 100).
- **Reusable UI:** design-system classes in `frontend/src/styles/psl-bundle.css`: `psl-tabs`/`psl-tab`/`psl-badge` (191-204), `psl-callout--warning|info|problem|success` (221-228), `psl-tag--person` (signal tint, used for NOT SET and HOLDS WORK), `psl-crumb` (265), `psl-panel`/`psl-panel__head` (279), `psl-field`/`psl-label`/`psl-input` (86-106), `psl-check` (152), `psl-drop`/`psl-file` (427-436), `psl-empty`, `psl-showmore`, `psl-btn`. `WorkErrorCard` comes from `frontend/src/features/work-item/WorkItemStates.tsx:7`. The Africa/Lagos formatter pattern comes from `frontend/src/features/work-item/labels.ts:136` (`formatWat`).
- **Decide flow precedent:** `frontend/src/features/decide/useDecision.ts` (a single-write ref guard, reload after a stale or uncertain write, never auto-resend).
- **F-06 precedent** (not necessarily at the base): `PERSONA_STATUS` and `CONTRACT_BODY` maps in `mock-contract.test.ts`. If they exist at the base, add entries to them. Otherwise add them in that shape.

## Contract

### Types: `frontend/src/features/setup/contract-proposal.ts`
- `RulesPageV4 = operations['E-SETUP-RULES']['responses'][200]['content']['application/json']` and `RuleRowV4 = RulesPageV4['items'][number]`.
- `RuleProposal` holds every v7 row field above, all optional, plus the F-11 addition `proof_case?: { case_id: string; case_revision: number; evidence_kind: string }` (see Assumptions A-3). Then `RuleRow = RuleRowV4 & RuleProposal` and `RulesPage = Omit<RulesPageV4,'items'> & { items: RuleRow[]; not_set_count?: number; roles_missing_count?: number }`.
- `SaveBody = { expected_revision: number; value: { roles: string[] }; starts?: string; reason?: string; evidence_id?: string }`, plus `SaveResult` from v4 and `EvidenceResult = v4 200 & { case_revision?: number }`.
- Every field outside v4 is optional, and code tolerates its absence (see the Absent fields table). No edit to `src/api/**`. A single narrowing cast in `features/setup/api.ts` passes `SaveBody` to `api.PUT`.

### GET /api/v1/setup/rules (E-SETUP-RULES, read)
- **Calls:**
  - `/setup/rules`: `call(api.GET('/api/v1/setup/rules', { params: { query: cursor ? { cursor } : {} } }))`.
  - Finance: `query.area = 'finance'`. Delivery: `query.area = 'delivery'`.
  - The v4 type has no `cursor` query. Add it through the same cast in `api.ts`, and list it in build.md as a proposal for the backend developer: E-SETUP-RULES returns `next_cursor` but declares no `cursor` parameter.
- **Order:** rows render in the order returned. "Show more" (`psl-showmore`) appears only when `next_cursor` is present. It appends the next page and keeps the counts from the first page.
- **Permission and tenant:**
  - If `me.destinations` lacks `setup`, render `NotOpenState` with the first visible destination and make no API call (same as `DestinationPage`).
  - The API decides which rules a person may read (INV-ACCESS). The page never filters by role.

**Screen states (all three views):**

| State | What shows |
|---|---|
| Loading | `LoadingState` (STATES "Loading…"; old values never shown as current) |
| Success | the view as drawn (below) |
| Empty (`items: []`) | `psl-empty`: h2 "No rules to show." / "Rules your role may read will appear here." Desktop `/setup/rules` keeps the frame and tabs; there is no banner and no panel |
| 401 | `SignedOutState` with `pathname` from `usePathname()` |
| 403 or 404 | `NotOpenState` (`frontend/src/shell/FrameStates.tsx`): nothing about any rule is shown |
| Server or network | `WorkErrorCard`: "We couldn’t load the rules. Your work is safe; nothing was changed." Try again re-reads the first page |
| Show more fails | Loaded rows stay. A warning callout says "We couldn’t load more rules. Choose Show more to try again." A 401 replaces the page with `SignedOutState` |

**Absent fields, in every view:**

| Row or field | Display |
|---|---|
| `set:false` | "Not set" (desktop list: amber `waiting-ink`, weight 600) or NOT SET tag (finance, delivery, phone lists) |
| `set:true` with `display_value` | the `display_value` text |
| `set:true` without `display_value` | "Set". The `value` object is never interpreted |
| `link` (`costing-rule`) | the value text is a `next/link` to `/setup/costing-rule`. A row with `link` is never offered for editing. An unknown `link` slug renders plain text |
| `holds_work:true` | the HOLDS WORK tag in the VERSION cell, shown instead of the version text |
| otherwise, `set:true` | "v{revision} · since {DD Mon}" from `effective_from` in Africa/Lagos, with the year appended when it is not the current Lagos year. Without `effective_from`: "v{revision}" |
| otherwise, `set:false` | an empty VERSION cell |
| `area_label` | the AREA cell. Absent means an empty cell |
| `not_set_count` absent | no Rules badge, no banner, no "· N not set" on the phone. Present and 0: badge "0" (CMP-06 rule) and no banner |
| `roles_missing_count` absent | no Roles badge. Present and 0: "0" |
| `restricted` | typed only. Not displayed in this slice (no board draws it) |

### PUT /api/v1/setup/rules/{component} (E-SETUP-RULE-SAVE, write)
- **Who sees the editor:**
  - A row is editable only when all of these hold: `can_change === true`, `editor.kind === 'role_set'`, `editor.options` is non-empty, and `link` is absent.
  - `/me` roles are never consulted.
  - The backend still enforces the right (403). The mock does too.
- **Request:**
  - Path: `component` (URL-encoded).
  - Body: `{ expected_revision: row.revision, value: { roles: [...ticked option.role, in option order] }, starts: 'YYYY-MM-DD' }`. Add `reason` only when the Why text, trimmed, is non-empty. Add `evidence_id` only when a proof upload succeeded for this edit.
  - `X-CSRFToken` comes from the client middleware.
  - Nothing else is sent. The client sends whatever roles were ticked, including none, and leaves the decision to the backend (Assumption A-5).
- **Idempotency and versioning:** `expected_revision` is the revision read. The client keeps one write at a time with a synchronous ref guard. Save is disabled and reads "Saving…" while the request is in flight. It never resends without a new click.

**Responses:**

| Result | What the person sees |
|---|---|
| 200 `{component, revision}` | Re-read the list (same view, first page). A `role="status"` `psl-callout--success` in the panel says "Saved as version {revision}." The panel keeps the same rule selected, rebuilt from the reloaded row (its `editor.selected`, the next version number). Why and Proof are cleared |
| 409 | Show the API `message` in the panel's `role="alert"` `psl-callout--problem` and re-read the list. Clear every edit: roles reset to the reloaded `editor.selected`, Why and Proof cleared, Starts back to today. The button then reads "Save as version {new revision+1}". Edits are never re-applied |
| 422 | Keep the edits. Put the message in the `role="alert"` callout. `fieldsFromMessage(message)` marks the named fields with `aria-invalid="true"` and `is-error`: `value`/`roles` → Roles allowed group, `starts` → Starts, `reason` → Why, `evidence_id` → Proof. Names match as whole words. An unmatched message marks nothing |
| 403 | Show the API message in the alert and re-read the list (the row will normally lose its editor) |
| 404 | Same as 403 |
| 401 | The page becomes `SignedOutState` |
| Server or network (uncertain effect) | Re-read the list once and do not resend. If the reloaded row's revision is unchanged, keep the edits and show "We couldn’t confirm the save. Nothing new is shown for this rule, so you can save again." If the revision changed, clear the edits as for 409 and show "This rule changed. Check the version shown before saving again." If the re-read also fails, the panel shows "We couldn’t check whether the save went through. Reload the page before saving again." and Save stays disabled until the person picks a rule or reloads |

Focus moves to the callout (`tabIndex={-1}`) after every save outcome.

### POST /api/v1/cases/{case_id}/evidence (E-EVIDENCE-UPLOAD, Proof field)
- **Enabled only** when the selected row has `proof_case`. Otherwise the drop area renders `psl-drop is-disabled` with `aria-disabled="true"` and the text "Proof can’t be attached here yet."
- **Request:** the person chooses one file (a visually hidden `<input type="file">` inside the drop label). The client sends `{ kind: proof_case.evidence_kind, filename, content_base64, case_revision }`. `case_revision` is the last `case_revision` returned by an upload in this edit, else `proof_case.case_revision`. The CSRF header is sent. There is no client-side type or size limit; the backend's 422 decides.
- **States:**
  - Empty: `psl-drop` with paperclip icon and "Choose a file".
  - Uploading: "Uploading {filename}…" in a `role="status"`.
  - Uploaded: the board's box (2px dashed ink border, paperclip, bold filename, "Uploaded · {size}"). Size is `ceil(bytes/1024)` "KB" below 1024 KB, else one-decimal "MB".
  - Choosing again replaces the file and its `evidence_id`.
- **Errors:**
  - 409: "The record changed. Choose the file again." The rules list is re-read for a fresh `proof_case`.
  - 422: the message under Proof, and Proof is marked invalid.
  - 403/404: the message, and the upload stays empty.
  - 401: `SignedOutState`.
  - Network or server: "We couldn’t attach the file. Choose it again." Uploads are never retried automatically.
  - A failed upload never blocks Save (Proof is optional in v7).

### Views
**Desktop and tablet (720px and wider), `/setup/rules` (SCR-13-desktop-rules, in board order):**
1. `p.psl-crumb`-styled "SETUP" eyebrow, then h1 "Roles, rules and delegation" (Archivo 800, 34px).
2. `nav aria-label="Setup"` with links styled `psl-tabs`/`psl-tab` (Assumption A-7), in this order:

   | Tab | Route | Badge |
   |---|---|---|
   | Roles | `/setup/roles` | `roles_missing_count` |
   | Rules | `/setup/rules` | `not_set_count` |
   | Costing rule | `/setup/costing-rule` | none |
   | Delegation | `/setup/delegation` | none |
   | Payroll visibility | `/setup/payroll-visibility` | none |
   | Staff accounts | `/setup/staff` | none |
   | Templates | `/setup/templates` | none |

   The current tab has `aria-current="page"` and the selected styling (ink background, white text, translucent badge).
3. Banner (when `not_set_count > 0`), `psl-callout--warning` with warning icon: "{n} rules aren’t set yet. Work that needs them waits as "Setup needed"; nothing guesses a rule. These are PSL’s decisions (see the approvals worksheet)." For n = 1: "1 rule isn’t set yet. Work that needs it waits…".
4. Two columns that wrap like the board (`flex 999 1 600px` / aside `1 1 320px`, max 420px).
   - **Table:** `psl-tablewrap` containing a table with columns RULE (bold name), AREA, CURRENT VALUE and VERSION, as in the Absent fields table. A row whose `area` is `finance` or `delivery` renders its AREA text as a link to `/setup/rules/finance` or `/setup/rules/delivery` (Assumption A-8).
   - **Aside:** the "Set a rule" panel, shown only when at least one loaded row is editable.
5. **"Set a rule" panel** (`psl-panel`, action-blue 2px border, blue uppercase head "Set a rule"):
   - Rule: a `<select class="psl-input">` of editable rows by `name`, in returned order. It starts on the first editable row.
   - Roles allowed: one `psl-check` per `editor.options` item, labelled `label`. They start ticked from `editor.selected` (none when absent).
   - Starts: `<input type="date" class="psl-input">`, prefilled with today in Africa/Lagos.
   - Why: `<input class="psl-input">`, empty.
   - Proof: as described in the evidence section.
   - Save: a `<button>` styled as the board's full-width blue 50px control, reading "Save as version {revision+1}".
   - Footnote (12px, muted): "Rules are versioned. Work already decided keeps the version it was decided under."
   - Changing the Rule clears every edit and rebuilds the fields from the chosen row.

**`/setup/rules/finance` (SCR-13-desktop-finance-rules):**
- Breadcrumb `p.psl-crumb` "SETUP / RULES / FINANCE": SETUP links to `/setup/rules`, RULES links to `/setup/rules`, FINANCE has `aria-current` (Assumption A-8).
- h1 "Finance rules" (32px), then the lead paragraph exactly as drawn.
- Warning callout:
  - "All {n} values are Not set." when there is no `next_cursor` and every loaded row has `set:false`, otherwise "{n} values are Not set.".
  - Followed by " Real reviewers and approvers come from PSL; none are invented here.".
  - With `not_set_count` absent, only the second sentence shows.
- Then one `section.psl-panel` per `group` in first-appearance order. The head is `group_label`, and the body is a `ul` of rows (name, then NOT SET tag or value text). Rows without `group` go in a last section headed "Other Finance rules" (Assumption A-10).
- **"Set {group} rules":**
  - Shown at the section foot only when the group has at least one editable row. It is a secondary button (inset 2px ink, 50px, max 220px wide).
  - The label lowercases the group label's first word unless that word is all capitals ("Set management accounts rules", "Set BU totals rules").
  - It is a disclosure (`aria-expanded`, `aria-controls`). It opens the same `SetRulePanel` inside that section, with the Rule picker limited to that group's editable rows. One panel is open at a time.

**`/setup/rules/delivery` (SCR-13-desktop-delivery-rules):**
- Breadcrumb "SETUP / RULES / DELIVERY" (same link rule), then h1 "Delivery rules".
- A `psl-panel` headed "Delivery" (the first row's `area_label`, else "Delivery"), containing a table with columns RULE, VALUE (NOT SET tag or value text) and USED BY (`used_by` joined ", ").
- Below it, a `psl-callout--info` with info icon: "These are PSL’s decisions. Until a rule is set, the line that needs it stops as "Setup needed" instead of guessing."
- An aside panel headed "Next": "Each rule is versioned. Changing one doesn’t change work already finished."
- No edit controls on this view (none are drawn).

**Phone (below 720px):**
- No tab bar, eyebrow, banner, panel or Set buttons. The phone boards draw none; see Assumption A-6.
- Each view starts with a back link "← Setup" to `/setup/roles` (the boards point at SCR-13-mobile, the phone Setup home). It sits just under the phone bar, per D-08.
- Rules (SCR-13-mobile-rules): h1 (22px) "Rules · {not_set_count} not set" ("Rules" when absent). Then one outlined card per row:
  - bold name;
  - a 13px line "{Not set | display_value | Set} · {area_label}", amber when not set and muted otherwise;
  - a finance or delivery `area_label` is a link to that area's view.
- Finance (SCR-13-mobile-finance-rules): "RULES" mono label beside the back link, h1 "Finance rules" (20px), warning callout "{n} values Not set.", then the first three groups as cards (bold group label, list rows with NOT SET tag or value). When there are more groups: mono 12px muted text "+ {k} MORE LINES · OPEN ON DESKTOP" ("LINE" when k = 1).
- Delivery (SCR-13-mobile-delivery-rules): "RULES" label, h1 "Delivery rules", one card listing each row with its NOT SET tag or value.
- Both trees render, and CSS media queries hide the other (`display:none`), so only one h1 is exposed.

**Reserved routes:** `/setup/roles`, `/setup/costing-rule`, `/setup/delegation`, `/setup/payroll-visibility`, `/setup/staff`, `/setup/templates`.
- Each renders the desktop frame (eyebrow, title, tab bar with that tab current, and no badges; Assumption A-9).
- Then `psl-empty`: h2 "{Tab label} comes next." / "This part of Setup arrives in a later release."
- The `setup` destination gate applies. They make no API calls.

**Metadata titles:** "Rules · Setup · PSL Factory", "Finance rules · Setup · PSL Factory", "Delivery rules · Setup · PSL Factory", "{Tab label} · Setup · PSL Factory".

There is no SAMPLE DATA tag anywhere in Setup.

### Fixture example (row shapes; `frontend/mock/fixtures/setup/rules.desktop.json`)
```json
{
  "items": [
    { "component": "presale.rfp_assigner", "name": "Who may assign an RFP to a PM", "set": false, "revision": 0,
      "area": "pre_sale", "area_label": "Pre-sale", "holds_work": true, "can_change": true,
      "editor": { "kind": "role_set", "options": [ { "role": "pmo_lead", "label": "PMO Lead" }, { "role": "ceo", "label": "CEO" }, { "role": "pmo", "label": "PMO" } ] },
      "proof_case": { "case_id": "C-SETUP-1", "case_revision": 1, "evidence_kind": "rule_proof" } },
    { "component": "documents.client_reviewer", "name": "Who reviews client documents", "set": true, "revision": 2,
      "value": { "roles": ["pmo_lead"] }, "display_value": "PMO Lead", "area": "all", "area_label": "All lines",
      "effective_from": "2026-10-01T00:00:00+01:00", "can_change": true,
      "editor": { "kind": "role_set", "options": [ "…same three…" ], "selected": ["pmo_lead"] } },
    { "component": "presale.costing_rule", "name": "Costing rule", "set": true, "revision": 4, "display_value": "PSL standard pricing v4",
      "link": "costing-rule", "area": "pre_sale", "area_label": "Pre-sale", "effective_from": "2026-10-01T00:00:00+01:00", "can_change": false,
      "editor": { "kind": "read_only" } },
    { "component": "finance.short_payments", "name": "Short payments (e.g. tax deducted)", "set": false, "revision": 0,
      "area": "finance", "area_label": "Finance", "holds_work": true, "can_change": false, "editor": { "kind": "read_only" } }
  ],
  "as_of": "2026-11-12T10:40:00+01:00",
  "not_set_count": 8,
  "roles_missing_count": 2
}
```

**Board fixtures (exact rows, wording and order):**

| Fixture | Rows | Counts and editors |
|---|---|---|
| `rules.desktop.json` | the board's 10 rows | `not_set_count` 8 and `roles_missing_count` 2 as drawn (PMO-0-4). Role-list rows (assign RFP, client documents, record RFP outcome, adjust costing) are `role_set` with `can_change:true`. The other rows are `read_only` |
| `rules.mobile.json` | 6 rows | count 6. The costing value is "Rate card v4" |
| `finance.desktop.json` | 25 rows in 7 groups, all `set:false` | count 25. Each group's "who …"/preparer/executor rows are `role_set`, `can_change:true` |
| `finance.mobile.json` | 7 groups (Management accounts shows 3 rows, as drawn) | count 25 |
| `delivery.desktop.json` | 5 rows with `used_by` | "Archive storage rule" is set: "Keep, never purge", v1 |
| `delivery.mobile.json` | 4 rows, the phone names | |

All values are sample. None is presented as PSL's policy.

## Lanes
- **Frontend lane (builder), owns:**
  - `frontend/src/app/setup/**`: `page.tsx` becomes `redirect('/setup/rules')`, plus `rules/page.tsx`, `rules/finance/page.tsx`, `rules/delivery/page.tsx` and the six reserved `*/page.tsx`.
  - `frontend/src/features/setup/**`: `contract-proposal.ts`, `api.ts`, `useSetupRules.ts`, `useRuleSave.ts`, `format.ts` (version text, Lagos today, size, `fieldsFromMessage`, group button label), `SetupFrame.tsx`, `RulesView.tsx`, `FinanceRulesView.tsx`, `DeliveryRulesView.tsx`, `SetRulePanel.tsx`, `ProofField.tsx`, `ReservedTab.tsx`, `setup.css`.
  - `frontend/mock/setup.mjs`, `frontend/mock/evidence.mjs` (held until a proof lane takes it over, PMO-0-5), `frontend/mock/proposals/setup.json`, `frontend/mock/fixtures/setup/**`, `frontend/mock/fixtures/me.admin.json`.
  - `frontend/tests/setup-*.test.ts(x)` and `frontend/e2e/setup.spec.ts`. Do not touch `frontend/tests/setup.ts`, which is the vitest setup file.
- **Backend lane:** none in this feature. The backend developer confirms D-SETUP-RULES-VIEW, `cursor`, `proof_case` and the `value.roles` shape under T-SETUP. build.md lists them.
- **Integration owner, shared files (additive only, each listed in build.md):**
  - `frontend/mock/server.mjs`:
    - imports from `./setup.mjs` and `./evidence.mjs`;
    - `'E-SETUP-RULES', 'E-SETUP-RULE-SAVE', 'E-EVIDENCE-UPLOAD'` appended to `M1_OPERATIONS`;
    - `'admin'` appended to `PERSONAS`;
    - two dispatch lines;
    - one `resetSetup()` call in the `/__mock/reset` branch.
  - `frontend/tests/mock-contract.test.ts`:
    - `PATH_VALUES.component` and `PATH_VALUES.case_id`;
    - `BODY` entries for the two writes;
    - `PERSONA_STATUS` entries (pm/none → 403 on all three);
    - `CONTRACT_BODY` entries (strip the proposal fields);
    - the admin row in "E-ME carries each persona fixture".
- **Not touched:** `frontend/src/shell/**`, `frontend/src/api/**`, `openapi.json`, `architecture/**`, `my-work/**`, `decide/**`, `work-item/**` (imports only), `exceptions/**`, `overview/**`, projects and Start work files, `package.json` and `package-lock.json` (no new dependencies), and `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json`.

### Mock behaviour (`frontend/mock/setup.mjs`, `frontend/mock/evidence.mjs`)
- **`me.admin.json`:** `{"name":"Ada Okafor","roles":["Admin"],"destinations":["my_work","projects","overview","assistant","setup"],"startable_lines":[],"csrf_token":"mock-csrf-admin"}`.
- **Personas:** `pm` and `none` get 403 `{code:'forbidden', message:'Your role does not allow this.'}` on all three operations. `finance_lead` and `admin` get the scenario data. The mock never derives `can_change` from the persona.
- **Scenario cookie `psl_mock_setup`:**

  | Value | Data |
  |---|---|
  | `desktop` (default) | `<area>.desktop.json` |
  | `mobile` | `<area>.mobile.json` |
  | `readonly` | desktop data with every `can_change:false` |
  | `empty` | `{items:[], as_of, not_set_count:0}` |
  | `forbidden` | 403 on GET for any persona |
  | `many` | 55 generated `set:false` rows, paged 50, with `next_cursor` `o:50` |

  `<area>` is `rules` when `area` is absent, else `finance` or `delivery`. Any other area returns empty items. Pages are 50 rows with `o:<offset>` cursors.
- **PUT, checked in this order:**
  1. The body is valid against the overlay save schema, else 422 "Check these fields: …".
  2. The component exists in the scenario, else 404.
  3. The row is editable (`can_change` and `role_set`), else 403.
  4. `expected_revision === revision`, else 409 with `SCENARIO_BODIES[409]`.
  5. Every role is in `editor.options`, else 422 "Check these fields: value.roles.".

  On success the mock stores an override keyed `persona:scenario:component`: `revision+1`, `set:true`, `display_value` (option labels joined ", "), `editor.selected`, `effective_from` (`starts` at 00:00 +01:00), `holds_work:false`. It lowers `not_set_count` by one on every page of that scenario that held the row unset, then answers `{component, revision}`.
- **Save cookie `psl_mock_setup_save`:**
  - `stale`: first stores an override as if another person saved "PMO Lead" at `revision+1`, then answers 409.
  - `invalid`: answers 422 "Check these fields: reason, starts.".
- **`evidence.mjs`:**
  - Validates the v4 body, resolves `case_id` against the scenario's `proof_case` values (404 otherwise) and checks `case_revision` against a per-`persona:case` counter (409 otherwise).
  - Answers `{evidence_id:'EV-<n>', sha256:<real sha256 of the decoded bytes>, case_revision:<counter+1>}`.
  - pm and none get 403.
- `/__mock/reset` clears both.
- **Exports:** `contractRules(body)` and `contractEvidence(body)` strip the proposal fields for the v4 checks.

## Acceptance criteria
Unit tests are vitest with jsdom and a stubbed `fetch` (the same pattern as `frontend/tests/decide.test.tsx`). E2E runs `cd frontend && E2E_PORT=4101 MOCK_PORT=4102 npx playwright test e2e/setup.spec.ts`. The fidelity runs use `node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs --playwright frontend/node_modules/playwright/index.mjs --board <board> --page http://localhost:4101<route> --width <1440|390> --exceptions <round>/fidelity/exceptions.json --cookies <cookies>`, against `next start` on 4101 and the mock on 4102.

1. `/setup` lands on `/setup/rules`. The Setup top-bar item is current. The SETUP eyebrow, the h1 "Roles, rules and delegation" and the seven tabs appear in the drawn order, Rules marked `aria-current="page"`, Roles badge "2" and Rules badge "8". — verify: e2e as admin at 1440 (`page.url()` ends `/setup/rules`, tab names and hrefs, badge texts).
2. The list shows the 10 board rows in returned order. Set rows show `display_value` and "v2 · since 01 Oct". Not-set rows show amber "Not set" and the HOLDS WORK tag. The costing value links to `/setup/costing-rule`. The banner reads "8 rules aren’t set yet…". — verify: unit `setup-rules.test.tsx` with the `rules.desktop.json` fixture, plus e2e.
3. Counts come only from the count fields. With `not_set_count` and `roles_missing_count` removed there is no badge, no banner and the phone h1 reads "Rules". With `not_set_count: 0` the badge shows "0" and there is no banner. Rows never change a count. — verify: unit, with three fixtures.
4. Unknown values are never shown as values. `set:false` always renders "Not set" or NOT SET even when a stray `value` or `display_value` is present. `set:true` without `display_value` renders "Set". Nothing renders `value` contents. — verify: unit.
5. Wrong user (read-only Lead): with `psl_mock_setup=readonly` the page shows the same rows but no "Set a rule" panel, no Finance "Set … rules" buttons and no form controls. A forced PUT on any component returns 403. — verify: unit with `can_change:false`; e2e with the cookie (`getByRole('button', { name: /Save as version/ })` count 0); mock test `setup-mock.test.ts` (PUT → 403).
6. Editor gating is per row. A row with `can_change:true` but `editor.kind:'read_only'`, or with `link`, or with no options, is absent from the Rule picker. The panel is absent when no row qualifies. `/me` roles have no effect: the same fixture under the `finance_lead` and `admin` personas renders identically. — verify: unit.
7. Roles allowed checkboxes come from `editor.options`, in order, labelled `label`. They start ticked only from `editor.selected`: none for a Not-set rule, "PMO Lead" for the client-documents rule. The duplicate "PMO Lead" on the board does not appear. — verify: unit and e2e.
8. First save. On "Who may assign an RFP to a PM" (revision 0), tick PMO Lead, keep Starts as today (Lagos), type a Why and attach a file, then click "Save as version 1". It sends one PUT with exactly `{expected_revision:0, value:{roles:['pmo_lead']}, starts:<today>, reason:<text>, evidence_id:'EV-…'}` and `X-CSRFToken: mock-csrf-admin`. The list reloads: the row shows "PMO Lead", "v1 · since <today DD Mon>" and no HOLDS WORK. The Rules badge and banner read 7. "Saved as version 1." is announced. — verify: unit (captured request body and headers), and e2e against the mock (row text and badge after save).
9. A blank Why sends no `reason` key, and no upload sends no `evidence_id`. A double click sends one PUT. — verify: unit.
10. Stale save. With `psl_mock_setup_save=stale`, Save shows the 409 message in the panel's `role="alert"` callout, which takes focus. The list reloads to the other person's version. The ticks, Why and Proof are cleared, and the button reads "Save as version {new+1}". Exactly one PUT was sent. — verify: unit, and e2e (request count via `page.on('request')`).
11. Invalid input. With `psl_mock_setup_save=invalid` the alert shows "Check these fields: reason, starts.". Why and Starts have `aria-invalid="true"` and the edits are kept. `fieldsFromMessage` maps `value.roles`, `roles`, `starts`, `reason` and `evidence_id`, and ignores unknown words. — verify: unit (mapping table), and e2e.
12. Mock validation. A PUT with roles outside `editor.options` answers 422 naming `value.roles`. `expected_revision` −1 or a string answers 422. A mismatched revision answers 409 and changes nothing (a following GET shows the old revision). Unknown component answers 404. No `X-CSRFToken`, or another persona's token, answers 403 `csrf_failed`. — verify: `setup-mock.test.ts`.
13. Uncertain effect. A PUT that rejects with a network error re-reads the list once. If the row's revision is unchanged, the edits stay with the "couldn’t confirm" text and no second PUT is sent until a click. If the revision changed, the edits are cleared with "This rule changed…". If the re-read fails, Save is disabled with "Reload the page before saving again." — verify: unit with stubbed fetch sequences.
14. 401 on read or on save shows `SignedOutState` with `next=%2Fsetup%2Frules`. 403 on read (`psl_mock_setup=forbidden`) shows "This section isn’t open to your role." and no rule names. The pm persona sees `NotOpenState` on `/setup/rules` and the mock records no E-SETUP-RULES call. A server error shows the load error card, and Try again re-reads. — verify: unit, and e2e (pm persona and the forbidden cookie).
15. Proof upload. Choosing a file sends one POST to `/api/v1/cases/C-SETUP-1/evidence` with the row's `evidence_kind`, filename, base64 content and `case_revision` 1. The box then shows the filename and "Uploaded · N KB". A second file in the same edit sends `case_revision` 2. On a row without `proof_case` the drop area is disabled with "Proof can’t be attached here yet." A 422 upload marks Proof invalid and Save still works. — verify: unit and `setup-mock.test.ts` (sha256 equals the content's real digest).
16. Finance view. `/setup/rules/finance` shows the breadcrumb, h1, lead text, "All 25 values are Not set. Real reviewers…", and 7 group panels in board order with every row and NOT SET tag. Each group has its "Set … rules" button (the label for BU totals reads "Set BU totals rules"). Activating it expands a panel limited to that group's editable rules, and `aria-expanded` toggles. As `readonly`, no buttons appear. — verify: unit and e2e as finance_lead.
17. Delivery view. `/setup/rules/delivery` shows the Delivery panel table (RULE, VALUE, USED BY) with the 5 board rows, "Keep, never purge" for the set row, the info callout, and the Next panel text. There are no edit controls. — verify: unit and e2e.
18. Phone. At 390px with `psl_mock_setup=mobile`:
    - `/setup/rules` shows "← Setup" linking to `/setup/roles`, the h1 "Rules · 6 not set" and 6 cards with "Not set · Pre-sale" style lines. There is no tab bar, banner or panel.
    - Finance shows "25 values Not set.", the first 3 groups and "+ 4 MORE LINES · OPEN ON DESKTOP".
    - Delivery shows the 4 rows.
    - No horizontal scroll at 390px.

    — verify: e2e at 390 (`document.documentElement.scrollWidth <= 390`).
19. Paging. With `psl_mock_setup=many` the list shows 50 rows and "Show more". Clicking it appends 5 more, and Show more disappears. A failing second page keeps the 50 rows and shows the warning callout. — verify: unit and e2e.
20. Reserved tabs. Each of the six tab links opens its route with the frame (that tab current) and "{Label} comes next.". It makes no API call besides `/me`. The pm persona gets `NotOpenState`. — verify: e2e (loop over the six), plus a unit test for `ReservedTab`.
21. Empty. With `psl_mock_setup=empty`, `/setup/rules` shows the frame, "No rules to show." and no banner or panel. Finance and delivery show the same empty pattern. — verify: e2e.
22. Contract overlay (PMO-0-2).
    - Every file in `frontend/mock/fixtures/setup/` and every mock response is valid against `frontend/mock/proposals/setup.json`.
    - With the proposal fields stripped (`contractRules`, `contractEvidence`), each is valid against the v4 operation schema.
    - Every request body the UI builds in the unit tests is valid against the overlay save schema, and, minus `starts`/`reason`/`evidence_id` and with `expected_revision ≥ 1`, against v4.
    - The overlay's row, response and save schemas equal the v7 operation schemas apart from `proof_case` (the test reads `architecture/packages/v7/openapi.json`).

    — verify: `frontend/tests/setup-proposal.test.ts`.
23. `mock-contract.test.ts` passes with the new operations and the `admin` persona: 200 for finance_lead and admin, 403 for pm and none, and every declared error scenario. — verify: `cd frontend && npx vitest run tests/mock-contract.test.ts`.
24. Accessibility (A-ACCESSIBILITY).
    - axe (WCAG 2.2 AA tags, same `TAGS` as `e2e/frame.spec.ts`) reports no violations on `/setup/rules`, finance, delivery, one reserved route, the panel after a 422, and the readonly scenario, at 1440 and 390.
    - Keyboard: Tab reaches each tab, the panel controls in order and Save. The focus ring is the 2px `--focus` outline.
    - Each checkbox, the date, Why and Proof have programmatic labels. The Roles allowed group is a `fieldset` with `legend`.
    - There is one h1 per view.

    — verify: e2e.
25. Design fidelity: all six boards PASS (coverage 100% after approved exceptions, visual ≥ 90). Reports and side-by-sides go in `delivery/features/F-11/round-<N>/fidelity/`.

    | Board | Route | Width | Cookies |
    |---|---|---|---|
    | SCR-13-desktop-rules | `/setup/rules` | 1440 | `psl_mock_persona=admin` |
    | SCR-13-mobile-rules | `/setup/rules` | 390 | `psl_mock_persona=admin,psl_mock_setup=mobile` |
    | SCR-13-desktop-finance-rules | `/setup/rules/finance` | 1440 | `psl_mock_persona=finance_lead` |
    | SCR-13-mobile-finance-rules | `/setup/rules/finance` | 390 | `psl_mock_persona=finance_lead,psl_mock_setup=mobile` |
    | SCR-13-desktop-delivery-rules | `/setup/rules/delivery` | 1440 | `psl_mock_persona=admin` |
    | SCR-13-mobile-delivery-rules | `/setup/rules/delivery` | 390 | `psl_mock_persona=admin,psl_mock_setup=mobile` |

    — verify: the six fidelity commands above.
26. Shared edits stay additive. `git diff <base> -- frontend/src/shell frontend/src/api architecture frontend/package.json frontend/package-lock.json delivery/checks.sh delivery/config.json delivery/merge-policy.json` is empty. The `server.mjs` and `mock-contract.test.ts` diffs add lines only and change only the lists named under Lanes. — verify: `git diff --stat` and the diff itself.

## Out of scope
- Roles, staff accounts, invite and deactivate (F-11C); Delegation (F-11B); Templates (F-11D); Payroll visibility (F-11E); the Costing rule screen (F-11F, `/setup/costing-rule` stays reserved); Clients (SCR-35); assigning the accountable PM (SCR-24). Their tabs only open reserved routes.
- Editors for any value kind other than role lists. Statement contracts, windows, inclusion rules, limits and so on stay read-only (PMO-0-3). There is no free-form JSON editor.
- Editing on phones (none is drawn), and editing on the Delivery view.
- Filtering or searching rules, history or version lists, rollback, scheduling, and "who changed it" display.
- Deriving permissions from `/me` roles. Treating Admin as an approver. Prefilling any rule value or role. Showing a default for "Not set". Computing any count from rows.
- A SAMPLE DATA tag. Any change to the top bar or phone bar (`src/shell/**`), `src/api/**`, `openapi.json`, `schema.d.ts` regeneration, `architecture/**`, and new npm dependencies.
- A shared evidence uploader for other lanes. `evidence.mjs` and `ProofField` are setup-local until FE-M2A-PROOF or FE-M2B-RESPONSE takes them over.
- Backend implementation of T-SETUP or of the proposal fields.

## Assumptions
- A-1. The board data disagrees with itself (8 vs 7 Not set; archive Not set vs "Keep, never purge"; duplicate PMO Lead). One fixture per board is used, counts come from the fields, and options come from the API (readiness PMO-0-4). Exception request: the design engineer records these.
- A-2. `expected_revision` is sent as read, including 0 (v7 D-SETUP-RULES-VIEW and readiness PMO-0-1). The v4 minimum of 1 is the contract defect, listed for the backend developer.
- A-3. E-EVIDENCE-UPLOAD needs a `case_id` and `case_revision`, but no setup payload gives one, even though REC-CONFIG has a `case`. F-11 adds an optional row field `proof_case {case_id, case_revision, evidence_kind}` to its local overlay. Without it, Proof is disabled. **This field is beyond v7 and is for the backend developer to confirm or replace.**
- A-4. Proof and Why are optional in the UI, because v7 marks `evidence_id` and `reason` optional. Whether PSL requires proof for a rule change is the backend's 422 to state. The approver may escalate this as a product rule.
- A-5. The role value is sent as `value: {roles: [role keys]}`, because v7's editor does not name the value shape. An empty selection is sent as-is and the backend decides whether it is valid. The client invents no minimum.
- A-6. Phones are read-only, as drawn. Editing needs 720px or wider. Exception request: confirm with the design engineer.
- A-7. The tab bar is a `nav` of links with `aria-current`, not ARIA `role="tab"`, because the tabs change routes and ARIA tabs require arrow-key panels. Same look as the board.
- A-8. The boards draw no way from Rules to the Finance and Delivery views, and no way back. AREA texts for finance and delivery are links (desktop and phone cards), and breadcrumb SETUP and RULES link to `/setup/rules`. Exception request.
- A-9. Reserved routes show the tab bar without badges, to avoid one extra read per placeholder page. Badges return when each feature lands.
- A-10. Finance rows without `group` go in a final "Other Finance rules" section, because no board covers ungrouped rows.
- A-11. "Starts" is a native date input prefilled with today in Africa/Lagos. The board's "Today, 12 Nov 2026" text format is not reproduced. Exception request.
- A-12. Board actions drawn as `<a href="#">` (Save, Set … rules) are built as `<button>`, and "Set bu totals rules" reads "Set BU totals rules". Exception requests.
- A-13. Undrawn states use existing patterns, each an exception request: success, 409, 422 and uncertain callouts in the panel; the empty and uploading Proof states; Show more; the empty list; the reserved-tab empty pattern; the Finance disclosure panel.
- A-14. Fidelity exceptions are expected for:
  - the top bar's persona text. The board's "Admin · sample" renders as "Ada Okafor · Admin" because the shell prints `/me`.
  - Start work and More ways to start, if F-05 has not merged at the base (D-04).
  - the phone back link and "RULES" label sitting under the phone bar (D-08).
  - panel inputs captured in their empty starting state (no tick, no Why, no file), because the fidelity tool cannot fill the form.
- A-15. The mock's page size is 50 and its cursor is `o:<offset>`. A `cursor` query parameter is proposed for E-SETUP-RULES, which returns `next_cursor` but declares no parameter.
- A-16. 403 and 404 on the read both show `NotOpenState`, so nothing about hidden rules is revealed (INV-ACCESS). On a write, both show the API message and reload.
