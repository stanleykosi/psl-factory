# Decide one exact version: approve, return or reject, with stale and cannot-act views

> Tasks: FE-DECIDE. Architecture: package v4 (proposal), manifest digest `9d4cbc10137ee452d29d240876cf07fbf13d02ac63e9b0fbdddb1256ae568ff0` (`architecture/packages/v4/manifest.sha256`); fields D-TASK-DECISION-VIEW r1 and D-WORKITEM-DETAIL r1 are used under the design engineer's recorded exception of 13 Nov 2026 (`architecture/sources/decisions-2026-11-13-v3.md`, item 1); D-RETURN r2 is the working assumption; D-APPROVAL-ORDER r1 comes from the API only. Design: approved canvas version 1794581312-b166 (`design/review.json`); screens: SCR-03 standard states only. Artboards: SCR-03-desktop, -mobile, -desktop-done, -mobile-done, -desktop-stale, -mobile-stale, -desktop-not-yours, -mobile-not-yours (`design/canvas/project/`), and SCR-03-desktop-own, -mobile-own (`design/canvas/finance/project/`).

## Summary
- `/work/[id]/decide?task=<task id>` shows the exact version the person is asked to decide. It shows only the values in `tasks[].decision`: the version, the amount (Unknown, never 0), the basis, the recipient, the changes, the preparer and the approval chain with "step n of m".
- An eligible person (`you_can_act: true`) claims the task on open. They then approve, return or reject it, with `expected_revision` and the CSRF header. A note is required to return or reject, and is capped at 2000 characters. The done view shows the verdict, who decided and when, and the reloaded facts and next step.
- A 409 from claim or decide never retries and never approves the newer version. It keeps the replaced version on screen, reloads the item and shows the replaced and current versions side by side, with "Review version n".
- A person who cannot act gets a read-only view keyed only on `cannot_act_reason`, plus who was asked instead. There are no Approve, Return, Reject or note controls. Eligibility never comes from `/me` roles.
- The contract moves to v4 in all four places. The mock validates claim and decide bodies with the existing `ajv`, answers 409 on a revision mismatch and supports the stale and done flows with sidecar fixtures and in-memory state. Fixtures W-1201 to W-1208 cover every state.

## Context
- **App frame (F-01, merged a41d472):**
  - `frontend/src/app/layout.tsx` wraps every page in `AppShell` (`frontend/src/shell/AppShell.tsx`). The shell loads `/me`, sets the CSRF token through `setCsrfToken` and provides `useMe()`. Persona `none` gets `NoSectionsState`.
  - `frontend/src/shell/FrameStates.tsx` exports `LoadingState`, `SignedOutState({pathname})`, `ForbiddenState`, `LoadErrorState({error, onRetry})` and the `shell-errorcard` classes.
  - `frontend/src/shell/SampleLabel.tsx` shows the build-level label.
- **API client:**
  - `frontend/src/api/client.ts` exports `api` and `call()`. Its `csrfMiddleware` sets `X-CSRFToken` on every POST and throws `ApiError(0,'unauthenticated','csrf_unavailable',…)` when no token is held.
  - `frontend/src/api/errors.ts` maps 401/403/404/409/422 to `ApiError.kind` unauthenticated, forbidden, not_found, stale and invalid. Anything else is server; a failed fetch is network.
  - `frontend/src/api/types.ts` derives types from `frontend/src/api/schema.d.ts`.
  - Four places name `architecture/packages/v2-reviewed`: `frontend/package.json` `gen:api` (line 12), `frontend/mock/server.mjs` `OPENAPI_PATH` (line 13), `frontend/tests/api-schema-drift.test.ts` (line 16) and the header comment of `frontend/src/api/client.ts` (line 1).
- **Mock (`frontend/mock/server.mjs`):**
  - Routes come from openapi.json. Bodies are drained and not read (`req.resume()`, around line 79). Scenarios (header `X-Mock-Scenario` or cookie `psl_mock_scenario`) are applied first. A write without the persona's `X-CSRFToken` gets 403 `csrf_failed`. Every other request is answered from `fixtures[operationId]`.
  - `frontend/mock/fixtures/E-TASK-CLAIM.json` and `E-TASK-DECIDE.json` are static T-2001 answers.
  - `frontend/mock/fixtures/E-WORK-ITEM.json` is W-1001. Its task T-2001 has revision 2 and `you_can_act: true`, and it has **no `decision`**.
  - `frontend/tests/mock-contract.test.ts` posts `{expected_revision: 2}` to claim T-2001 and `{expected_revision: 2, verdict: "approve"}` to decide it, for every persona, and expects 200. It also expects every declared error through `X-Mock-Scenario`, and 403 `csrf_failed` without the header.
- **F-03 (merges first, the base for this branch):**
  - It adds `frontend/src/app/work/[id]/page.tsx` and `/history`, and components in `frontend/src/features/work-item/**` (facts strip, agent card, SCR-02 no-access view).
  - Its mock handler serves `frontend/mock/fixtures/work/<id>.json`, answers 404 for `W-1099` and falls back to `E-WORK-ITEM.json`.
  - Its task panel links "Open the decision" to `/work/<id>/decide?task=<task id>` (F-03 spec, Contract, item 7).
- **Design system:**
  - `frontend/src/styles/psl-bundle.css` has `psl-panel--decide`, `psl-panel__head--decide`, `psl-panel--readonly`, `psl-actionbar` / `psl-actionbar__pair` / `psl-doesnt` (CMP-11), `psl-btn` / `psl-btn--confirm` / `psl-btn--secondary` / `psl-btn--reject` / `psl-btn--block` / `psl-btn--lg`, `psl-field` / `psl-label` / `psl-hint` / `psl-input--area` / `psl-error`, `psl-amount`, `psl-unknown`, `psl-facts` / `psl-fact--*`, `psl-mini` (CMP-03), `psl-avatar--chidi|tola|zainab`, `psl-callout--info|warning|problem|success`, `psl-crumb`, `psl-mono`, `psl-sample` and `psl-empty`.
  - `tokens.css` and `psl-bundle.css` are drift-tested by `frontend/tests/styles-drift.test.ts`. Do not edit them.
- **No route** exists today under `frontend/src/app/work/[id]/decide/`.

## Contract

### Contract source repoint (one commit, PMO-0-2)
- `frontend/package.json` `gen:api` → `../architecture/packages/v4/openapi.json`. Run `npm run gen:api` and commit the regenerated `src/api/schema.d.ts`.
- `frontend/mock/server.mjs` `OPENAPI_PATH` → `architecture/packages/v4/openapi.json`.
- `frontend/tests/api-schema-drift.test.ts` → the v4 path, with the test name saying "v4".
- `frontend/src/api/client.ts` line 1 comment → v4.
- `architecture/**` is not edited. Every existing fixture (`E-*.json`, `me.*.json`, F-02's and F-03's) must still validate against v4. The existing `mock-contract.test.ts` cases are the check.
- Add derived types to `frontend/src/api/types.ts`:
  - `WorkItem`;
  - `WorkTask` (`WorkItem['tasks'][number]`);
  - `TaskDecision` (`NonNullable<WorkTask['decision']>`);
  - `ClaimResult`;
  - `DecideBody`;
  - `DecideResult`.

  If F-03 already added `WorkItem`, reuse it.

### GET /api/v1/work/{work_id} (E-WORK-ITEM, read)
- **Request:** `call(api.GET('/api/v1/work/{work_id}', { params: { path: { work_id } } }))`.
- **What the page uses:**
  - `title`, `line`, `reference`, `revision`, `stations`, `facts`, `agent`, `next_step` and `sample`.
  - The task whose `id` equals the `task` query parameter, with its fields `title`, `required_role`, `you_can_act`, `revision`, `decision?`, `cannot_act_reason?` and `asked?`.
- **`decision` (D-TASK-DECISION-VIEW, proposal):** `{ version{label, number, document_id?, drafted_at?}, amount?{amount?, currency, unknown}, basis?, recipient?, changes?{previous_label, items[]}, prepared_by?{name, role?, is_you, with_agent?: tola|chidi|zainab}, chain{steps[{position, role, person?, status: approved|returned|rejected|withdrawn|current|not_yet, decided_at?, is_you}], your_step?, step_count} }`.
- **Errors:**
  - 401 → `SignedOutState` with `pathname` = `/work/<id>/decide?task=<task>`.
  - 403 or 404 → F-03's SCR-02 no-access view, imported from `features/work-item` and not edited. If F-03 does not export it, use a local copy with the same copy and no item values.
  - Network or 5xx → an error card (`shell-errorcard` classes) with:
    - eyebrow "ERROR · COULDN'T LOAD";
    - "We couldn't load this decision. Your work is safe; nothing was changed.";
    - "Reference <code> for support.";
    - Try again.
- **Permission:** the backend decides. The page never reads `useMe().roles` or `destinations` to decide what to show. The only switches are `you_can_act` and `cannot_act_reason`.

### POST /api/v1/tasks/{task_id}/claim (E-TASK-CLAIM)
- **When:** once, automatically, when the page shows a task with `you_can_act: true` (endpoint trigger "Open a decision you are eligible for"). It runs again only after a reload shows a new task revision, or when the person presses "Review version n". Keep a ref keyed by `task id + revision` so React StrictMode does not double-claim.
- **Request:** `call(api.POST('/api/v1/tasks/{task_id}/claim', { params: { path: { task_id } }, body: { expected_revision: task.revision } }))`. CSRF comes from the existing middleware.
- **200:** `{ task_id, revision, claimed_by }`. Keep `revision` as the decide revision.
- **Errors:**
  - 401 → `SignedOutState`.
  - 403 → the generic cannot-act view (below) and a reload of the item. If the reload carries a `cannot_act_reason`, that view wins.
  - 404 → the no-access view.
  - 409 → the stale flow.
  - 422 → inline problem callout with the server `message`. Controls stay disabled.
  - Network or 5xx → inline warning "We couldn't get this decision ready. Try again." with a Try again button that claims again. A claim records no decision, so retrying it is safe.
- **Until the claim succeeds:** Approve, Return and Reject are rendered but disabled, with the reason "Getting this decision ready…" (CMP-11 "disabled with reason").

### POST /api/v1/tasks/{task_id}/decision (E-TASK-DECIDE)
- **Request body:**

  ```json
  { "expected_revision": <claim revision>, "verdict": "approve" | "return" | "reject", "note": "<text>"? }
  ```

  - `note` is sent only when it is non-empty after trimming. It is sent as typed.
  - `revoke` and `evidence_id` are never sent.
- **Client rules, checked before any request:**
  - Return or Reject with a blank (trimmed) note → no request. The field error "Add a note to return or reject." appears, the textarea gets `aria-invalid="true"` and `aria-describedby`, and focus moves to it.
  - The textarea has `maxLength={2000}` and a live counter "n / 2000". A note longer than 2000 characters (for example set programmatically) → no request, and the field error "Keep the note to 2000 characters or fewer."
  - A note is optional for Approve.
- **One write at a time:**
  - While a decide is in flight, all three buttons are disabled, the pressed one reads "Approving…", "Returning…" or "Rejecting…", and the panel has `aria-busy="true"`.
  - Nothing retries automatically.
- **200:** `{ task_id, verdict, decided_by, decided_at, work_state }`. Show the done view, then reload E-WORK-ITEM once for the facts and `next_step`.
- **Errors:**
  - 401 → `SignedOutState`.
  - 403 → the generic cannot-act view and a reload of the item.
  - 404 → the no-access view.
  - 409 → the stale flow.
  - 422 → problem callout with the server `message` above the buttons. The note is kept and nothing is resent.
  - Network or 5xx is an **uncertain effect**. Show a warning callout: "We couldn't confirm your decision. We've reloaded this item so you can see whether it was recorded." Then reload the item once, without resending. If the reloaded task is still actionable at the same revision, the controls come back for a deliberate new tap. If it changed, the matching view (done or cannot-act from `already_decided`, or stale) is shown.
- **Idempotency/versioning:** INV-REVISION. Every write carries `expected_revision`. The UI never edits a revision and never reuses an old one after a 409.

### Screen states (SCR-03, standard)
Common header, at every width:
- `psl-crumb`: "My work" (`/my-work`) / `line` / `reference` (mono).
- Eyebrow: the name of the station whose status is `current_person`, upper-cased, then "· `reference`". Board example: "FINANCE REVIEW · INV-0412".
- h1: `task.title`. Sub-line: `title`.
- A `SAMPLE DATA` label (`psl-sample`) whenever `sample: true`, independent of `NEXT_PUBLIC_API_MODE` (INV-SAMPLE).
- Page `<title>`: "Decision · PSL Factory".

1. **Loading:** `LoadingState`.
2. **Not found:** shown when the `task` parameter is missing, matches no task in `tasks[]`, or the task has no `decision`.
   - `psl-empty` with h2 "This decision isn't open here".
   - Text: "It may have been decided, withdrawn or moved. The work item shows where things stand."
   - Link "Open the work item" to `/work/<id>`.
   - No controls. This is what W-1001 / T-2001 shows, because it has no `decision`.
3. **Default (you can act):**
   - **Decision content** (a `dl`; rows render only when their field is present):
     - **Amount:** `psl-amount`, formatted from the decimal string without converting to a float. Group the integer part with commas and keep 2 decimals. NGN uses the prefix "₦"; any other currency uses "<ISO code> ". For example `{"amount":"4250000.00","currency":"NGN","unknown":false}` → "₦4,250,000.00". When `unknown: true`, show the word "Unknown" in `psl-unknown`, whether or not `amount` is present. It is never "0", "₦0.00" or blank (INV-UNKNOWN).
     - **Basis.**
     - **To:** `recipient`.
     - **Changed since <previous_label>:** the `items` as a list.
     - **Version:** `version.label`, plus "drafted <time WAT>" when `drafted_at` is present.
     - **Prepared by:** `name` (`role`). When `is_you`, show "You". When `with_agent` is present, add "with <Tola|Chidi|Zainab>" and its `psl-avatar--<agent>` 20px avatar.
   - **Approval chain:** an ordered list of the steps, each showing:
     - position, role, `person` (or "Not assigned yet") and the status word: Approved, Returned, Rejected, Withdrawn, Current or Not yet;
     - `decided_at` in WAT when present;
     - "(you)" when `is_you`.

     Above the list, "Step <your_step> of <step_count>" when `your_step` is present. Otherwise "<step_count> steps".
   - **Facts strip:** desktop only (hidden below 720px, as on SCR-03-mobile). Use F-03's facts strip component if it is exported, otherwise local markup with the same mapping. Unknown or missing facts read "Unknown".
   - **Phone line:** at 390px, the CMP-03 mini station line (`psl-mini`) reads "Station n of m · <current station name> · only a <required_role> can decide". n is the 1-based index of the `current_person` station. Omit the line when there is none.
   - **Agent card:** shown when `agent.status` is not `none` and `agent.name` is present. It shows the avatar (`psl-avatar--<lower-cased name>`, otherwise a neutral initial), the name, "Cannot approve, send or pay." and a link "See <name>'s steps" to `/work/<id>`. It has no other control.
   - **"Your decision" panel** (`psl-panel--decide`, head `psl-panel__head--decide`, h2 "Your decision"):
     - "Only a <required_role> can decide. You are <required_role>."
     - A textarea labelled "Note", with the hint "(needed to return or reject)" and the counter.
     - Approve (`psl-btn--confirm`, full width), labelled "Approve v<version.number>".
     - Return (`psl-btn--secondary`) and Reject (`psl-btn--reject`) side by side.
     - One line (`psl-doesnt`): "Approving earns APPROVED only." When a station follows the current one in `stations[]`, add "<next station name> is the next station."
   - **At 390px** the three buttons and the `psl-doesnt` line sit in a `psl-actionbar` pinned to the bottom of the viewport, above the shell phone bar, with every target at least 44px tall. The note field stays in the content.
   - **At 1440px** the panel is a right-hand aside, as on SCR-03-desktop.
4. **Submitting:** see "One write at a time".
5. **Done (after a 200):**
   - Eyebrow "YOU APPROVED · HH:mm", "YOU RETURNED · HH:mm" or "YOU REJECTED · HH:mm", from `decided_at` in Africa/Lagos time.
   - h1: "<version.label> is approved", "<version.label> was returned" or "<version.label> was rejected".
   - "Decided by `decided_by`".
   - The reloaded facts strip, at all widths.
   - `next_step` in a callout: success for approve, info otherwise.
   - "Paid is tracked separately by Finance and is not part of this decision." (shown for approve only).
   - Links: "Open the work item" (`/work/<id>`) and "Back to my work" (`/my-work`). There are no decision controls.
   - If the reload fails, the done header stays, with a warning: "We couldn't refresh this item. Open the work item to see the latest."
6. **Stale (409 from claim or decide, A-STALE):**
   - Keep the `decision` that was on screen. Reload the item and find the same task id.
   - Warning callout, h2 "A newer version arrived while you were reading." Add "Version <new number> was drafted at <d MMM HH:mm>." when `drafted_at` is present, then "Version <old number> can no longer be approved."
   - Two columns, stacked at 390px: "VERSION <old> · REPLACED" and "VERSION <new> · CURRENT". Rows: Amount, Basis, Send to (`recipient`). Each current value is marked "unchanged" or "changed" by comparing it with the replaced one, and Unknown follows the amount rule. A row is omitted when the field is absent in both. Under the current column: its `changes.items`.
   - One button, "Review version <new number>". It shows the default view for the current version and claims again with the new task revision. If the reloaded task has `you_can_act: false`, the button leads to the cannot-act view instead.
   - The footer line: "Decisions always apply to one exact version, so an approval can never land on the wrong one."
   - If the reloaded task is missing or has no `decision`, show the not-found state. If the version number is unchanged, still show the callout and the two columns (only the revision moved). No request is sent until the person presses the button.
7. **Cannot act (`you_can_act: false`, A-NOT-YOURS):**
   - A read-only panel (`psl-panel--readonly`). It shows the same decision content rows (amount, basis), "Waiting for <required_role>" and the chain.
   - **There is no textarea and no Approve, Return or Reject button** in the DOM. Copy is keyed on `cannot_act_reason` only:

     | reason | eyebrow | heading | text |
     |---|---|---|---|
     | `not_your_role` | NOT YOUR DECISION | This decision needs a <required_role>. | You can read it, but you can't approve, return or reject it. |
     | `prepared_by_you` | WAITING FOR REVIEW | You prepared <version.label>, so someone else must review it. | — |
     | `already_decided` (drafted copy) | ALREADY DECIDED | This decision has already been made. | Nothing more is needed from you here. The work item shows what happens next. |
     | `not_your_turn` (drafted copy) | NOT YOUR TURN YET | This needs <role of the chain step with status `current`> first. | You'll be asked when it's your turn. |
     | absent, or a 403 on a write | NOT YOUR DECISION | This decision needs a <required_role>. | You can't approve, return or reject it. |

     For `not_your_turn` with no `current` step, the heading is "This needs earlier approvals first."
   - **Asked list (`asked[]`):**
     - Each person: "<name> (<role>) was alerted at <time> by WhatsApp and email". Channels are joined with "and", in the given order: `whatsapp` → "WhatsApp", `email` → "email".
     - Without channels: "<name> (<role>) was alerted at <time>".
     - Without `alerted_at`: "<name> (<role>) has been asked."
     - An empty or absent `asked`: "Nobody has been asked yet."
   - Link "Open the work item" (`/work/<id>`).
8. **Errors:** as listed per endpoint above. All 401/403/404/409/422 handling goes through `ApiError.kind`; nothing parses status codes in feature code.

Times use the en-GB format in `Africa/Lagos`: "HH:mm" in the done eyebrow only, and "d MMM HH:mm" everywhere else (for example "12 Nov 10:42"), so the text does not depend on today's date. Each time is in a `<time dateTime>` element.

### Mock behaviour (F-04 adds; PMO-0-1, PMO-0-3, PMO-0-5)
- **Body reading:** the server reads the request body for every request (replacing the bare `req.resume()`). Only the two task operations use it.
- **Request validation:** compile each operation's `requestBody` schema from the loaded openapi with `ajv/dist/2020` and `ajv-formats` (both already devDependencies; no new package). This runs once at server creation.
- **Order of checks for E-TASK-CLAIM and E-TASK-DECIDE:**
  1. Scenario (unchanged, still wins).
  2. CSRF (unchanged).
  3. Find the task by `task_id` across the bodies the mock would currently serve: the default `E-WORK-ITEM.json`, every `fixtures/work/<id>.json`, and the in-memory overrides. Not found → 404 `{code:"not_found", message:"We could not find that record."}`.
  4. Body: invalid JSON, or schema failure → 422 `{code:"invalid", message:"Check these fields: <comma-separated names>."}`. A missing property names it. An extra property names it. An invalid JSON body names `body`.
  5. Note rules for decide, as described in the schema text: verdict `return`, `reject` or `revoke` with a missing or blank note → 422 naming `note`. A note over 2000 characters → 422 naming `note`.
  6. `verdict: "revoke"` with a valid note → 501 `not_mocked`. There is no withdraw board in FE-DECIDE.
  7. The task has `you_can_act: false` → 403 `{code:"forbidden", message:"Your role does not allow this."}`.
  8. `expected_revision` ≠ the task's current `revision` → 409 with the existing `stale_revision` body.
  9. **Decide only:** when `work/<id>.next.json` exists and that item has not been replaced yet → 409 `stale_revision`, and from then on GET `/work/<id>` serves `<id>.next.json`. This simulates a redraft that landed after the page loaded.
  10. Success:
      - Claim → 200 `{task_id, revision: <task revision, unchanged>, claimed_by: <persona me.name>}`. Claim is idempotent.
      - Decide → 200 `{task_id, verdict, decided_by: <persona me.name>, decided_at: <now, ISO>, work_state}`. When `work/<id>.<verdict>.json` exists, GET `/work/<id>` serves it from then on, and `work_state` is its `state`. Otherwise the item is unchanged and `work_state` is the current item's `state`. W-1001 / T-2001 therefore stays unchanged, so the existing contract tests keep passing.
- **In-memory overrides:**
  - Held in a `Map<work_id, body>` that F-03's E-WORK-ITEM handler consults before `work/<id>.json`. This is a one-line hook in F-03's handler and the only edit to it.
  - Reset on restart, and by the mock-only `POST /__mock/reset`, which answers 204 and needs no CSRF.
- **Static fixtures:** `E-TASK-CLAIM.json` and `E-TASK-DECIDE.json` are left in place, unchanged and unused.
- **Required fixtures** (`frontend/mock/fixtures/work/`; all `sample: true`; all valid against v4 E-WORK-ITEM; line "Prepare an invoice" unless stated). In every fixture the decision task's `kind` is `decide`.

| id | task (rev) | purpose |
|---|---|---|
| W-1201 | T-1201 (2) | **Default, A-DECIDE given.** Lagoon Health invoice v2, INV-0412. `you_can_act: true`. `decision`: version `{label:"Invoice v2", number:2, drafted_at}`, amount NGN `4250000.00`, basis "Contract stage 2 of 4 · terms v1", recipient `accounts@lagoonhealth.example`, changes since "Invoice v1": ["PO number, as you asked"], prepared_by Bisi Ade (Finance) with chidi and `is_you: false`. Chain: 1 step, Finance Lead / Ada Okafor / current / is_you, `your_step: 1`, `step_count: 1`. Stations as in W-1001, with Finance review `current_person`. Agent Chidi `done`. Sidecars: `W-1201.approve.json` (rev 3, state `ready`, reviewed and approved `earned` with `at`, task `you_can_act: false` / `already_decided` with the chain step `approved`, next_step "Chidi issues invoice v2 and emails it to Lagoon Health."), `W-1201.return.json` (rev 3, state `action_needed`, `tasks: []`, next_step "Bisi Ade corrects invoice v2 and resubmits it.") and `W-1201.reject.json` (rev 3, state `action_needed`, `tasks: []`, next_step "Bisi Ade decides what to do with the rejected invoice.") |
| W-1202 | T-1202 (2) | Unknown amount: `amount: {currency:"NGN", unknown:true}` and no `amount` string. `you_can_act: true`. Otherwise like W-1201 |
| W-1203 | T-1203 (2) | `not_your_role`. `you_can_act: false`. `asked: [{name:"Ada Okafor", role:"Finance Lead", alerted_at:"2026-11-12T09:42:00Z", channels:["whatsapp","email"]}]`. Basis "SOW v2 stage 2" |
| W-1204 | T-1204 (2) | `prepared_by_you`. prepared_by Bisi Ade, `is_you: true`, with chidi. `asked: [{name:"Ada Okafor", role:"Finance Lead", alerted_at:"2026-11-12T09:20:00Z"}]` |
| W-1205 | T-1205 (3) | `already_decided`. The chain step is `approved`, by Ada Okafor, `is_you: true`, with `decided_at`. `asked: []` |
| W-1206 | T-1206 (2) | `not_your_turn`. Line "Prepare a costing". `required_role: "CEO"`. Chain of 3 (D-APPROVAL-ORDER): PM approved, PMO Lead current, CEO not_yet with `is_you: true`. `your_step: 3`, `step_count: 3`. `asked: [{name:"<PMO Lead sample name>", role:"PMO Lead"}]` |
| W-1207 | T-1207 (4) | **Stale, A-STALE given.** Invoice v2, NGN `4250000.00`, recipient `accounts@lagoonhealth.example`. `you_can_act: true`. Sidecar `W-1207.next.json`: rev 5, task T-1207 rev 5, version `{label:"Invoice v3", number:3, drafted_at:"2026-11-12T09:46:00Z"}`, amount unchanged, recipient `billing@lagoonhealth.example`, changes since "Invoice v2": ["Billing contact changed"] |
| W-1208 | T-1208 (2) | Chain with earlier approvals. 3 steps: 1 approved and 2 approved (both with `decided_at`), 3 current with `is_you: true`. `your_step: 3`, `step_count: 3`. `you_can_act: true`. **No `recipient`** and no `changes` (checks omission) |

**Fixture example** (W-1201 `tasks[0].decision.amount` and `chain`):
```json
{"amount":{"amount":"4250000.00","currency":"NGN","unknown":false},
 "chain":{"steps":[{"position":1,"role":"Finance Lead","person":"Ada Okafor","status":"current","is_you":true}],"your_step":1,"step_count":1}}
```

## Lanes
- **Frontend lane (F-04 builder) owns:**
  - `frontend/src/app/work/[id]/decide/page.tsx` (and an optional `layout.tsx` only for the metadata title);
  - `frontend/src/features/decide/**` (components, hooks, formatters, and an optional `decide.css` using only existing tokens);
  - the F-04 fixtures in `frontend/mock/fixtures/work/W-12xx*.json`;
  - `frontend/tests/decide*.test.ts(x)` and the new `frontend/tests/mock-decide.test.ts`;
  - `frontend/e2e/decide.spec.ts`.
- **Contract repoint (F-04 only, one commit):** `frontend/package.json` (`gen:api` line only), `frontend/src/api/schema.d.ts` (regenerated, never hand-edited), `frontend/tests/api-schema-drift.test.ts`, the `frontend/src/api/client.ts` line 1 comment, and additive types in `frontend/src/api/types.ts`.
- **Shared files** (minimal, additive edits; the integration owner, who is the coordinator, merges them):
  - `frontend/mock/server.mjs`:
    - `OPENAPI_PATH`;
    - body reading;
    - the E-TASK-CLAIM and E-TASK-DECIDE handler;
    - the override `Map` with its one-line hook in F-03's E-WORK-ITEM handler;
    - `POST /__mock/reset`.
  - Leave F-02's and F-03's handlers otherwise untouched.
  - `frontend/tests/mock-contract.test.ts` is not edited. Its existing cases must keep passing.
- **Read-only imports:** `frontend/src/shell/**`, `frontend/src/features/work-item/**` (F-03), `frontend/src/api/client.ts` and `errors.ts`. If a needed piece is not exported, copy the markup locally rather than editing F-03 or the shell. Any unavoidable edit to `src/shell/**` or `src/api/**` beyond the above is listed in build.md.
- **Backend lane:** none. **Integration owner:** the coordinator. It cuts the branch after F-03 merges and merges `server.mjs` with F-02.
- **Not touched:** `architecture/**`, `apps/**`, `frontend/src/styles/tokens.css`, `frontend/src/styles/psl-bundle.css`, the content of `E-WORK-ITEM.json` and `E-WORK-HISTORY.json`, F-02 and F-03 files, and `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json` (protected).
- **Ports:** app 3401, mock 3402.
  - e2e: `cd frontend && E2E_PORT=3401 MOCK_PORT=3402 npx playwright test e2e/decide.spec.ts`
  - Dev: `cd frontend && MOCK_PORT=3402 npm run dev -- -p 3401`

## Acceptance criteria
1. **The contract is v4 everywhere.** `grep -rn "v2-reviewed" frontend --exclude-dir=node_modules --exclude-dir=.next` prints nothing. The drift test regenerates from `architecture/packages/v4/openapi.json` and matches. Every existing `mock-contract.test.ts` case passes unchanged. `git diff <base> -- architecture` is empty. — verify: the grep, `npx vitest run tests/api-schema-drift.test.ts tests/mock-contract.test.ts`, and the diff.
2. **Default view (A-DECIDE, A-NOT-YOURS eligible half).** /work/W-1201/decide?task=T-1201 shows:
   - "Invoice v2";
   - "₦4,250,000.00";
   - "Contract stage 2 of 4 · terms v1";
   - "accounts@lagoonhealth.example";
   - "Changed since Invoice v1" with "PO number, as you asked";
   - "Bisi Ade" with Chidi;
   - "Step 1 of 1";
   - "Only a Finance Lead can decide. You are Finance Lead.";
   - the buttons "Approve v2", "Return" and "Reject";
   - SAMPLE DATA.

   — verify: a component test on the W-1201 fixture. Also open http://localhost:3401/work/W-1201/decide?task=T-1201 with the mock on 3402.
3. **Unknown is never zero.** W-1202 shows "Unknown" in the amount row. Neither the amount row nor the page text contains "0.00", "₦0" or an empty amount cell. A crafted decision with `unknown: true` **and** an `amount` string also shows "Unknown". — verify: component tests.
4. **Absent fields are omitted.** W-1208 renders no "To" row and no "Changed since" row. It shows "Step 3 of 3" and the two earlier steps as "Approved" with their times in WAT. — verify: component test.
5. **Claim on open with the right revision.** Opening W-1201 sends exactly one `POST /api/v1/tasks/T-1201/claim` with body `{"expected_revision":2}` and header `X-CSRFToken: mock-csrf-finance_lead`, also under StrictMode. The buttons stay disabled, with "Getting this decision ready…", until it resolves. — verify: component test inspecting the stubbed `fetch` calls (method, URL, body and header).
6. **Approve.** After the claim, pressing "Approve v2" sends one `POST /api/v1/tasks/T-1201/decision` with `{"expected_revision":2,"verdict":"approve"}` and the CSRF header. The view then shows "YOU APPROVED · <HH:mm>", "Invoice v2 is approved", "Decided by Ada Okafor", the reloaded facts with APPROVED earned, the success callout with next_step, the Paid line and "Open the work item". No Approve, Return or Reject button remains. — verify: component test. In the browser after `POST http://127.0.0.1:3402/__mock/reset`, approving W-1201 shows the done view.
7. **Note rules (PMO-0-5).**
   - Return or Reject with an empty or whitespace-only note sends no request, shows "Add a note to return or reject.", sets `aria-invalid="true"` and focuses the textarea.
   - With the note "Wrong PO", Return sends `{"expected_revision":2,"verdict":"return","note":"Wrong PO"}` and shows "Invoice v2 was returned".
   - The textarea has `maxLength` 2000 and shows "n / 2000".

   — verify: component tests.
8. **One write, no retry.** A double click on Approve sends one decide request. While it is pending all three buttons are disabled and the pressed one reads "Approving…". — verify: component test with a deferred fetch.
9. **Stale (A-STALE).**
   - Opening W-1207 and pressing Approve gets a 409. The page sends no second decide. It reloads the item once and shows "A newer version arrived while you were reading.", "Version 3 was drafted at 12 Nov 10:46.", "Version 2 can no longer be approved." and the columns "VERSION 2 · REPLACED" and "VERSION 3 · CURRENT". The Amount row is marked "unchanged" and Send to `billing@lagoonhealth.example` is marked "changed".
   - Pressing "Review version 3" claims T-1207 with `{"expected_revision":5}` and shows "Approve v3".

   — verify: a component test that counts decide calls (must be exactly 1) and asserts the reload. An e2e on the mock covers the same flow.
10. **409 on claim** goes to the same stale view, and no decide request is sent. — verify: component test with the claim stubbed to 409.
11. **Cannot act: controls absent.** For W-1203, W-1204, W-1205 and W-1206, the DOM contains no textarea and no button named /approve|return|reject/i, and no claim or decide request is sent. — verify: a table-driven component test over the four fixtures, asserting the buttons are absent and the fetch calls are GET only.
12. **Cannot-act copy per reason (A-NOT-YOURS).**
    - W-1203: "NOT YOUR DECISION", "This decision needs a Finance Lead." and "Ada Okafor (Finance Lead) was alerted at 12 Nov 10:42 by WhatsApp and email".
    - W-1204: "You prepared Invoice v2, so someone else must review it." and "Ada Okafor (Finance Lead) was alerted at 12 Nov 10:20".
    - W-1205: "This decision has already been made."
    - W-1206: "This needs PMO Lead first." and "Step 3 of 3".
    - A task with `asked: []`: "Nobody has been asked yet."

    — verify: component tests.
13. **Eligibility is not taken from `/me`.** With `/me` stubbed as the Finance Lead persona and W-1203 (`you_can_act: false`), no decision control renders. With `/me` stubbed as persona `pm` and W-1201 (`you_can_act: true`), the controls render. — verify: component test. `grep -n "roles\|destinations" frontend/src/features/decide -r` finds no use in a branch that controls the decision UI.
14. **Errors (wrong user, invalid input, provider failure):**
    - Decide 403 → the generic cannot-act view and no buttons.
    - Decide 422 `{code:"invalid", message:"Check these fields: note."}` → that message in a problem callout, the note kept, no second request.
    - Decide network error → "We couldn't confirm your decision…", one GET reload and no second POST.
    - Item 404 → no-access view without the id or title.
    - Item 401 → sign-in link whose `next` is `/work/W-1201/decide?task=T-1201`.
    - Item 500 → error card with Try again, which re-fetches.
    - A missing or unknown `task` parameter, and W-1001 / T-2001 (no `decision`) → "This decision isn't open here" with no controls.

    — verify: component tests.
15. **Mock: claim and decide validation (QA-3-2, PMO-0-3, PMO-0-5).** Against the running mock:
    - Claim T-1201 with `{}` → 422 naming `expected_revision`. With `{"expected_revision":2,"x":1}` → 422 naming `x`. With `{"expected_revision":1}` → 409. With `{"expected_revision":2}` → 200 `{task_id:"T-1201", revision:2, claimed_by:"Ada Okafor"}`.
    - Decide with `verdict:"maybe"` → 422. With `return` and no note, or a whitespace note → 422 naming `note`. With a 2001-character note → 422.
    - Claim on T-1203 (`you_can_act: false`) → 403. Claim on `T-9999` → 404. Invalid JSON → 422.
    - Every response validates against the v4 declared schema. The existing scenario cookies still win, and a missing CSRF header still gives 403 `csrf_failed`.

    — verify: new `frontend/tests/mock-decide.test.ts` using a fresh `startMockServer({port:0})`.
16. **Mock: stale and done flows.**
    - Decide on T-1207 with revision 4 → 409. Then GET `/api/v1/work/W-1207` returns version 3 at revision 5. Claim and decide with 5 → 200.
    - Decide approve on T-1201 → 200 with `work_state:"ready"`, and GET W-1201 then returns `W-1201.approve.json`. A second decide with revision 2 → 409.
    - `POST /__mock/reset` → 204, and W-1201 and W-1207 are back to their base fixtures.
    - GET `/api/v1/work/ANY-OTHER` still returns the unchanged `E-WORK-ITEM.json`.

    — verify: `frontend/tests/mock-decide.test.ts`.
17. **Fixtures are valid and labelled.** Every `W-12xx*.json` (including the sidecars) validates against v4 E-WORK-ITEM with `strict` Ajv, has `sample: true`, and has `cannot_act_reason` only where `you_can_act` is false. — verify: a test iterating the files.
18. **Layout and accessibility (A-ACCESSIBILITY).** axe reports no WCAG 2.2 AA violations at 390x844 and 1440x900 for:
    - default W-1201;
    - done (after approving W-1201);
    - stale (W-1207 after Approve);
    - not-yours W-1203;
    - own W-1204.

    At 390 the action bar is visible within the viewport without scrolling, each of its buttons is at least 44px tall, and `document.documentElement.scrollWidth <= 390`. Keyboard Tab reaches Note, Approve, Return and Reject in that order, with a visible focus ring. With `reducedMotion: 'reduce'` no element animates. — verify: `cd frontend && E2E_PORT=3401 MOCK_PORT=3402 npx playwright test e2e/decide.spec.ts`, calling `/__mock/reset` in `beforeEach` and reusing the `frontend/e2e/frame.spec.ts` helpers.
19. **Gate:** `delivery/checks.sh` passes. — verify: the gate run.

## Out of scope
- **Readiness excluded:**
  - The payment-exception, CEO final costing and CTO emergency variants (FE-DECIDE-VARIANTS, gated on D-DECISION-VARIANTS).
  - `revoke` (withdraw approval).
  - The comment box and "Add comment" on the not-yours board.
  - The "DECISIONS / 1 OF 3" pager and "Next decision · 2 of 3" (PMO-0-4). List both in build.md for product acceptance and the backend developer.
  - The work item page and history (F-03), My work (F-02), notifications (FE-M4), SCR-08 document review, and what "return" does on each line (D-RETURN).
- **Board elements with no contract, omitted:**
  - "Preview: a newer version arrives" (a canvas prototype link).
  - "waiting 2h" on the phone line.
  - The agent's "Drafted this from 3 sources: …" sentence and "Redrafted it from the updated client record".
  - "You hold Finance on this project".
  - The board's not-yours title "Approve the Milestone 2 invoice?" (`task.title` is used instead).
  - Comments of any kind.
- **Tempting but not built:**
  - A confirm dialog before Approve (the board is one tap).
  - Automatic retry, or auto-approving the newer version.
  - Optimistic facts.
  - Polling on the decide page.
  - Deriving "you can act", approvers or chain order on the client.
  - Showing the claim's `claimed_by` anywhere.
  - Keyboard shortcuts.
  - Highlighting My work in the top bar.
- **Out of bounds:**
  - Any edit to `openapi.json` or `architecture/**`, backend work (`apps/**`, T-DECIDE) and real-API wiring (FE-CONNECT-1).
  - New npm dependencies.
  - Editing the design tokens or bundle CSS.
  - Editing F-02's or F-03's components or tests.

## Assumptions
- **Decide uses the revision the claim returned.** This works whether the backend bumps the revision on claim or not. The mock does not bump it.
- **The mock does not require a claim before a decide.** The real "claimed eligible role" rule is the backend's (T-DECIDE).
- **A network or 5xx error on decide is treated as an uncertain effect.** The page reloads and never resends (AGENTS.md: reconcile uncertain effects before retrying). A claim may be retried because it records no decision.
- **A task without `decision` gets the "not open here" state.** No one should decide a version they cannot see. This includes today's W-1001 / T-2001, which F-03 links to.
- **Copy for `already_decided` and `not_your_turn` is drafted, with no board.** It is listed for product acceptance (readiness, Summary). The own-board copy is generalised from "this invoice" to "<version.label>".
- **The done headings follow the approved board's pattern.** "<label> was returned" and "<label> was rejected" follow "Invoice v2 is approved". The done Paid line shows for approve only.
- **The approve button reads "Approve v<number>"**, as on the board ("Approve v2"). The full label is visible in the content above.
- **"Approving earns APPROVED only. <next station> is the next station."** This is built from `stations[]`, generalising the phone board line.
- **The facts strip is hidden on the phone default and shown on the phone done view.** This matches SCR-03-mobile and SCR-03-mobile-done.
- **403 on claim or decide gets the generic cannot-act copy.** The 403 body carries no reason, so the page reloads and prefers the reloaded `cannot_act_reason`.
- **The mock answers 403 for a task with `you_can_act: false` whatever the persona.** Mock personas do not map to fixture eligibility.
- **Mock stale and done use sidecar fixtures plus an in-memory override.** The sidecars are `<id>.next.json` and `<id>.<verdict>.json`, and `POST /__mock/reset` clears the override. This is the smallest stateful design that keeps today's fixtures, scenarios and F-03's fallback unchanged, and it lets e2e reset between tests.
- **The mock sends `revoke` with a valid note to 501.** No FE-DECIDE screen sends it, and a fake success would mislead.
- **The 422 message format is "Check these fields: …".** It meets the contract's "fields named in message" without a new error shape.
- **The W-1206 not_your_turn fixture uses a costing with the D-APPROVAL-ORDER chain** (PM, PMO Lead, CEO), as in the A-NOT-YOURS given. It shows only the standard read-only view, not the CEO costing variant. The PMO Lead's sample name is the builder's choice and is labelled sample.
- **The sidecar next_step texts are sample wording for the mock,** in particular for return and reject (D-RETURN r2 working assumption). They are not business rules.
- **Times use en-GB format in Africa/Lagos (WAT),** as F-03 does. "10:42" on the board corresponds to `09:42Z`. Dates are always shown outside the done eyebrow because the boards' bare times assume "today", which a fixture cannot guarantee.
