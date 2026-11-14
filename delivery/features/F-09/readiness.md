DECISION: READY
RISK: high
SURFACES: ui, api, security, contract-change, external-messaging
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
COMMIT: none (round 0, no head yet)
REVIEWER: readiness
AUTHORITY: PMO readiness (delivery step 1)

## Summary
- I checked F-09 = FE-M2B-RESPONSE against architecture v7 (commit 61a7ade). The split I proposed is now in the architecture: FE-M2B-RESPONSE covers record a response and reconcile only (packages/v7/delivery.md:1437-1469). It has no gate_ids and no unresolved gates, and depends only on FE-WORKITEM, which is merged. Team input and the RFP outcome are FE-M2B-RFP (F-09B, delivery.md:1776). FE-M2B-RFP depends on F-09 and on FE-CONTRACT-V7, and is not in this feature.
- My v6 blocker PMO-0-1 is closed by contract fields. In D-RESPONSE-VIEW r2 (model.json:1096-1108), `tasks[].response` gains `intro`, `proof_hint`, `agent_note`, `channels`, `context.project`/`context.document`, `next[]` and `recorded{by, at, received_via, proof_count, summary}` (openapi.json:1421-1586). E-RESPONSE also accepts `received_via` and returns `revision`, `recorded` and `next` (openapi.json:4674-4732, 4964). In D-WORK-ACTIONS-VIEW r2 (model.json:1139-1151), the reconcile block gains `reconcile.unknown_note` and `reconcile.resend_note` (openapi.json:1811-1820). The same r2 also closes PMO-0-5: E-WORK-ACTION gets an optional `case_revision` (openapi.json:5226). Every sentence drawn on the 10 boards now has a field that can hold it.
- Both r2 decisions have status `proposed`. They count only under the design engineer's recorded exception (decisions-2026-11-14-v2.md (f)(g), decisions-2026-11-15.md (h)(i)), and the exception has limits: the contract mock only, the backend developer may change or refuse any field, and nothing is released. That is why BLOCKING-DECISIONS is none. D-RFP-OUTCOME is not used by this feature.
- PMO-0-4 (repoint) is no longer a dependency, as the coordinator instructs. F-13 owns the v7 repoint and is not merged, and the base still reads v4 (`mock/server.mjs:22`). F-09 must therefore type its v7 fields locally, validate its own fixtures and handlers against `packages/v7/openapi.json`, and keep all of it out of the v4 checks the base runs. This is binding in Scope items 7 and 8.
- The rating is high because E-RESPONSE records a sworn record that cannot be edited, has no idempotency key, and reconcile can authorise an invoice resend to a client. Under the overnight rules this feature is built and reviewed but not merged: it waits for the design engineer.

## Findings
None of these blocks readiness. PMO-0-1 and PMO-0-2 are build constraints and are binding through Scope.
- PMO-0-1 | non-blocking | high | frontend | F-09 must not be wired into the base mock's v4 checks, or the base suite fails.
  - `tests/mock-contract.test.ts:69-86` calls every `M1_OPERATIONS` entry with body `{}`, expects a 200 and validates the reply against v4.
  - `tests/mock-contract.test.ts:219-235` validates every `fixtures/work/W-<digits>.json` against v4 E-WORK-ITEM, which is `additionalProperties: false`.
  - Expected:
    - (a) do not add E-RESPONSE, E-WORK-ACTION or E-EVIDENCE-UPLOAD to `M1_OPERATIONS`;
    - (b) put the W-16xx item bodies that carry v7 fields under `fixtures/response/work/`, not `fixtures/work/`. Load them into the served `work` map so that E-WORK-ITEM, E-WORK-HISTORY's fallback and F-04's E-TASK-CLAIM `findTask` (server.mjs:107-116) all see them;
    - (c) `mock/response.mjs` compiles its own ajv validators from `architecture/packages/v7/openapi.json` behind one named constant;
    - (d) `tests/response-mock.test.ts` checks every F-09 fixture and handler reply against v7.
  - Actual: if the v6 scope were followed as written ("one `M1_OPERATIONS` entry", fixtures in `fixtures/work/`), the v4 checks would fail.
- PMO-0-2 | non-blocking | medium | frontend | `src/api/schema.d.ts` and `api` (client.ts:29) are typed on v4 paths, and F-09 must not edit `src/api/**`. Expected:
  - The v7 shapes are declared once in `src/features/response/contract.ts`, mirroring openapi.json:1300-1593 and 4645-4980 and E-WORK-ACTION.
  - One adapter in `src/features/response/api.ts` makes the calls through `api`/`call`, with a single commented widening cast at that boundary. No cast appears anywhere else.
  - Every r2 field is optional. When one is missing, its element is left out; the builder never substitutes board copy.
  - build.md lists the cast and the v7 constant, so that whoever rebases second onto F-13 removes them.
- PMO-0-3 | non-blocking | medium | integration | The agent avatars named in the standing rule are not in this checkout: `frontend/public/agents/` does not exist and `design/system/project/assets/Mascots/` holds only a README (pose sheets are in `design/mascots/revised-poses/`). The Tola aside (SCR-16-desktop.dc.html:44) and the reconcile checks name an agent (`agent_note.agent`, `reconcile.checks.agent`). Expected: the coordinator puts `tola.png`, `chidi.png` and `zainab.png` on the base, or names the lane that adds them, before the UI round. F-09 reads `/agents/<agent>.png` and does not own those files.
- PMO-0-4 | non-blocking | low | frontend | On the SOW board the active top-bar item is **Projects** (SCR-16-desktop-sow-signed.dc.html:15), and the crumb links PROJECTS to SCR-22 and the project to its page. The top bar belongs to `src/shell/**`, which F-09 must not touch, and F-07 (projects) is unmerged. Expected: the crumb is built from `context.project`/`context.document`. It links only to routes that exist on the base, and otherwise renders as text. If the shell highlights My work on `/work/...`, record that as a proposed fidelity exception for the design engineer. Do not change the shell.
- PMO-0-5 | non-blocking | low | pmo | I could not run `design.py check`, because my role has no shell. The approval (design/review.json, 13 Nov, `design_sha256` 9fad8d2d…) covers SCR-16 and SCR-02. Expected: the coordinator runs the check before the spec is written and confirms that the 12 boards below still match the approved hash.
- Carried from v6 (readiness-v6-not-ready.md), still applying as written there: PMO-0-6 (the UI reviewer scores the whole SCR-02 page, and differences outside the panel are raised against F-03) and PMO-0-7 (the entry button replaces "Open the decision" only for `task.response`, and "Change the reminder" stays out).

## Scope
**Binding for the spec writer.**

**Outcome (one, observable):** the PM opens a work item with a response task and presses "Record the client's response". On `/work/<id>/respond?task=<task_id>` they choose who responded, how and when, what the client did and which version, upload proof, confirm it is genuine and press Record. The success page then shows what was recorded and what happens next. On a work item awaiting reconciliation, a Lead who holds `reconcile` in `allowed_actions` confirms what happened. All of this works at 390px and 1440px on the contract mock.

**Boards (all elements present, scored by the fidelity gate):**
- SCR-16-desktop and SCR-16-mobile
- SCR-16-desktop-validation and SCR-16-mobile-validation
- SCR-16-desktop-success and SCR-16-mobile-success
- SCR-16-desktop-sow-signed and SCR-16-mobile-sow-signed
- SCR-02-desktop-awaiting-reconciliation and SCR-02-mobile-awaiting-reconciliation (the panel, per PMO-0-6)
- The entry button only: SCR-02-desktop-waiting and SCR-02-mobile-waiting

**In:**
1. **Route.** `frontend/src/app/work/[id]/respond/page.tsx` takes `?task=`. It is a page, not a drawer, and its title never names the item, the same as `decide/page.tsx`.
2. **Header and aside, from `tasks[].response`:**
   - `intro` under the heading;
   - the crumb from the work item and `context` (PMO-0-4);
   - `agent_note` as the agent aside, with the avatar at `/agents/<agent>.png` (PMO-0-3).
3. **Form** (`variant` `client_response` or `sow_signature`):
   - The pickers come only from `responders`, `channels` (sent as `received_via`), `actions` (labels from the API) and `versions` (label and note). Offer nothing the API did not return, and derive nothing from roles.
   - The proof field shows the `proof_hint`.
   - Proof goes up first through E-EVIDENCE-UPLOAD on `case_id` with `case_revision` and `evidence_kind`. "Add another file" adds to `evidence_ids`.
   - When `claim_required` is true, call E-TASK-CLAIM before E-RESPONSE.
   - E-RESPONSE carries CSRF and these fields:
     - `expected_revision` (the task revision);
     - `case_revision` (from the last upload);
     - `who`, `action`, `responded_at`, `evidence_id` and `attested`;
     - `version_id` and `received_via`;
     - an optional `note` of up to 2000 characters.
   - Record stays disabled, with the validation board's alert, until there is proof and the attestation is ticked.
   - A 422 shows inline. A 409 keeps what was entered and reloads the work item. A 403 or 404 goes through `ApiError`, and a 401 through `SignedOutState`.
   - The button is disabled while the request is in flight. After an uncertain result, never retry automatically: reload the work item and show the recorded state if the task is already done.
4. **Success.** Filled from the E-RESPONSE 200 (`recorded`, `next`) and the refetched work item, with "Back to the work item". Leave out any element whose field is missing.
5. **Reconcile panel.**
   - Shown only when `reconcile` is present and `allowed_actions` includes `reconcile`.
   - The options come from `outcomes`, the check sentence from `checks`, and the notes from `resend`, `resend_note` and `unknown_note`.
   - "It arrived" requires an upload of `evidence_kind`.
   - Submit E-WORK-ACTION `{expected_revision, action: "reconcile", outcome, evidence_id?, case_revision?}` with CSRF, then refetch.
   - The frontend never triggers a resend.
6. **Entry from the work item. These are the only F-03 edits, and each is listed in build.md:**
   - one branch in `TaskPanels` (WorkItemOverview.tsx:147-162) for `task.response && task.you_can_act`, with the labels in `src/features/response/labels.ts`;
   - one conditional mount of `ReconcilePanel` next to line 182.
   - Do not touch `NextStep` (F-06).
7. **Mock, per PMO-0-1.**
   - `frontend/mock/response.mjs` handles E-EVIDENCE-UPLOAD, E-RESPONSE and E-WORK-ACTION. It validates against v7 and answers:
     - 422 without proof or attestation;
     - 409 on a stale revision;
     - 403 for a persona without the grant;
     - CSRF and `X-Mock-Scenario` the same way server.mjs does.
   - A success swaps the item through the existing `overrides` map.
   - E-TASK-CLAIM reuses F-04's handler.
   - The shared edits to `server.mjs` are additive only: loading F-09's work bodies into `work`, and routing F-09's three operations to `response.mjs` before the 501 fallback. No `M1_OPERATIONS` entry.
   - Fixtures are W-1601 to W-1649:
     - a UAT response;
     - a SOW signature;
     - awaiting reconciliation with `allowed_actions: ["reconcile"]`;
     - the same item without the grant;
     - a `claim_required` task;
     - one item with every r2 field absent, to prove the tolerance.
   - Post-record variants go in `fixtures/response/**`.
8. **Types, per PMO-0-2:** `src/features/response/contract.ts` and the single adapter. Export the proof field and the upload hook from `src/features/response/index.ts` for FE-M2A-PROOF.
9. **Tests.**
   - Component tests:
     - only the returned options are shown;
     - the claim comes before the response;
     - the disabled and alert state;
     - the 422, 409, 403 and 401 paths;
     - one record on a double press;
     - the upload's `case_revision` is carried into the response;
     - r2 fields absent means the elements are left out, with no fallback copy;
     - reconcile is hidden without the grant.
   - `frontend/tests/response-mock.test.ts` against v7.
   - Playwright and axe at 390px and 1440px for the default, validation, success, SOW and reconcile states.
   - The existing suite (mock-contract, api-schema-drift, mock-decide) still passes unchanged on v4.
   - Acceptance: A-RESPONSE and A-RECONCILE (frontend half), plus A-ACCESSIBILITY.

**Out:**
- F-09B / FE-M2B-RFP: team input, the RFP frame, the RFP outcome and the follow-up send.
- "Change the reminder".
- The resume and cancel buttons.
- The backend (T-RESPONSE, T-EXCEPTIONS) and the real API.
- The v7 repoint (F-13).
- Edits to `architecture/**`, `openapi.json`, `src/api/**` and `src/shell/**`.
- New npm dependencies.
- A visible SAMPLE DATA tag.

**Ownership (unchanged from my v6 proposal):**
- Owns:
  - `frontend/src/app/work/[id]/respond/**`
  - `frontend/src/features/response/**`
  - `frontend/mock/response.mjs`
  - `frontend/mock/fixtures/response/**`
  - `frontend/mock/fixtures/work/W-16[0-4]x*.json` (reserved; use it only for v4-valid bodies until F-13 lands)
  - `frontend/tests/response*.test.ts(x)`
  - `frontend/e2e/response.spec.ts`
- Shared, additive only, listed in build.md:
  - the `server.mjs` lines in item 7;
  - the two `WorkItemOverview.tsx` edits in item 6.
- Does not touch:
  - `NextStep` and the exceptions files (F-06);
  - the start-work files (F-05);
  - the projects files (F-07);
  - the overview files (F-08);
  - the alerts files (F-12);
  - the contract files (F-13);
  - `decide/**` and `my-work/**`;
  - the existing W-10xx, W-12xx, W-14xx and W-15xx fixtures;
  - `public/agents/**`.
- Rebase onto whichever lane touches `WorkItemOverview.tsx` or `server.mjs` first. If F-13 lands first, drop the local cast and the v7 constant and use `OPENAPI_PATH` and the generated types. If F-09 lands first, F-13's rebase does that.

**Task IDs:** FE-M2B-RESPONSE (R-RESPONSE, R-EXCEPTION). **Endpoints:** E-WORK-ITEM (read), E-EVIDENCE-UPLOAD, E-TASK-CLAIM, E-RESPONSE and E-WORK-ACTION, all on the contract mock. **Decisions consumed:** D-RESPONSE-VIEW r2 and D-WORK-ACTIONS-VIEW r2, both proposals under the recorded exception.

## Risk
The rating is high:
- E-RESPONSE stores a record that a staff member swears to: an outside party's UAT approval or SOW signature, backed by proof. It "can't be edited later" (SCR-16-desktop.dc.html:40; INV-AUDIT).
- E-RESPONSE has no idempotency key in v7 (openapi.json:4623-4984), so a double or retried submit is the main failure to guard against.
- A reconcile answer of `not_delivered` authorises a resend of an invoice to a client (D-WORK-ACTIONS-VIEW, INV-RESEND).

The surfaces:
- `security`: the attestation, CSRF on four writes, and offering only what the API grants (`allowed_actions`, `responders`, `actions`, `channels`).
- `external-messaging`: the resend authority.
- `contract-change`: the work runs on two r2 proposals with local typing before the v7 repoint.
- `api` and `ui`.

`payments` is excluded, because no money moves and no amount is recorded. `product-decision` is dropped now that v7 carries the copy as backend fields. Product acceptance is required: this is a new flow and new copy for the client.

## Questions
None. Nothing open needs a client or product-owner rule. The 13 Nov decision stands (Engineering Lead and Support do not log in, and the PM records their part), and the responder list comes only from `responders`.
