DECISION: READY
RISK: medium
SURFACES: ui, api
PRODUCT-ACCEPTANCE: not-required
BLOCKING-DECISIONS: none
COMMIT: none (round 0, no head yet)
REVIEWER: readiness
AUTHORITY: PMO readiness (delivery step 1)

## Summary
- F-03 is FE-WORKITEM in architecture package v3. Its only dependency is T-FRONTEND-SHELL, which is done (F-01, PR #3, a41d472). Its only gate is D-UPDATES, approved at r2 (its latest revision). validation.json lists `FE-WORKITEM: []` under gates, and delivery.md says "Unresolved gates: none".
- The client approved the design on 13 Nov 2026 (design/review.json, canvas 1794581312-b166, SCR-02 and CMP-01..24 included). D-API-STYLE and D-AUTH are still `proposed`. As with F-01, the recorded exception covers them: the frontend builds against the contract only (reviews.json r2 "approve"). D-PAGING r2 (approved) applies to the history list.
- The outcome is one read-only page: `/work/[id]` shows the work item (state, stations, the six facts, the agent checklist, the current human task, the next step) plus a History view. It reads E-WORK-ITEM and E-WORK-HISTORY from the contract mock. Every action control belongs to other features.
- Medium risk. It holds no money, identity logic or writes. But the screen is the main place where INV-FACTS, INV-UNKNOWN, INV-AGENT and INV-RESTRICTED become visible to people. Also, the parallel build has to share the mock and the E-WORK-ITEM fixture with F-02 and F-04.
- I found gaps between the contract and the approved boards (see Findings). The builder resolves them by rendering only contract fields; nothing needs a client answer. They go to the coordinator and architecture, and do not block.

## Findings
- PMO-0-1 | non-blocking | medium | integration | The A-WORKITEM acceptance says "unknown amount has unknown=true and no value", but the E-WORK-ITEM 200 schema (openapi v3, `additionalProperties: false`) has no amount field. F-03 can only show the Unknown case through `facts[].status = unknown` (CMP-04 "Unknown", never blank or zero). The amount part of A-WORKITEM cannot be met in this feature. Record it in build.md and route it to architecture/backend as a contract question.
- PMO-0-2 | non-blocking | low | integration | The SCR-02 boards show values the contract does not carry: "Started by … · date" in the header, per-station detail and time ("Done · Mon 14:05", "Waiting 2h · you"), agent step times, "step n of m" start time, history filter counts, the Documents tab and "Download history (CSV)". The expected behaviour is to omit them or derive them only from contract fields; inventing text is not allowed. The builder lists every omission in build.md for the coordinator to take to architecture.
- PMO-0-3 | non-blocking | medium | integration | `frontend/mock/server.mjs:98` returns the single `E-WORK-ITEM.json` fixture for any `work_id` and ignores `kind`, `cursor` and `limit` on history. The current fixtures fall short in three ways:
  - They show only one state (`waiting`, `frontend/mock/fixtures/E-WORK-ITEM.json:6`).
  - They do not match the A-WORKITEM given (approved earned, sent not_yet).
  - The history fixture is out of time order and lacks the return and approval that A-HISTORY needs (`E-WORK-HISTORY.json:3-5`).

  Expected: F-03 adds per-id fixtures, for example the list ids W-1001..W-1003 plus scenario ids. It may make a minimal, backwards-compatible change to server.mjs that selects by `work_id` and `kind`, falling back to today's fixture so F-02 and F-04 keep working. The coordinator must agree any change to server.mjs or to the default `E-WORK-ITEM.json`, because F-04 may read it too.

## Scope
**Outcome (one, observable):** with the mock running, opening `/work/W-1001` (or a row link or alert link) shows that work item as SCR-02 on desktop (1440px) and phone (390px). A History tab or view shows its read-only history with the All / Decisions / Agent work / Evidence filters. A-WORKITEM (within PMO-0-1), A-HISTORY and A-ACCESSIBILITY pass on the mock.

**In:**
1. **Route** `src/app/work/[id]/` (page plus the history view, as a tab or sub-route `history`), excluding any `decide` sub-route, which F-04 owns. Components go in `src/features/work-item/**`. The data comes only through the existing generated client, using `GET /api/v1/work/{work_id}` and `GET /api/v1/work/{work_id}/history`.
2. **Header:** the breadcrumb back to My work, the title, the line and reference, and the revision. The state tag (CMP-05) uses the CMP-05 wording and colour family for each of the 11 contract states. The sample label (CMP-16) appears whenever `sample: true`.
3. **Facts strip (CMP-04):** the six facts in contract order, each shown as earned, current, not yet or unknown ("Unknown", never blank or zero), with `at` shown when present. The note "Paid is a separate Finance fact" is included. The facts are never merged into one status (INV-FACTS).
4. **Station track (CMP-02):** stations from `stations[]`, numbered, with the statuses done, current_person, current_agent, waiting, stopped, not_started and verified. It scrolls sideways on phones.
5. **Agent at work (CMP-09, CMP-18):** the avatar and name, the working/done/waiting/stopped label, and the steps with their `source` (shown in mono). Agent status `none` hides the card or shows the "no agent work" state. The card never shows Approve, Send or Pay, and keeps the line "Cannot approve, send or pay" (INV-AGENT). The current step pulses only when motion is allowed.
6. **Current human task:** for each `tasks[]` entry, show its title, the required role, and whether you can act. When `you_can_act` is true, show a link to F-04's decision route. Otherwise show the read-only "only a <role> can decide" text. The decision panel itself is out of scope. Coordinate the route path with F-04 through the coordinator.
7. **Next step:** `next_step` is shown as the item's callout (CMP-24). States that need an action owned by FE-M2 (effect_uncertain, awaiting_reconciliation, setup_needed, owner_needed, action_needed, followup_needed) show the state and next step read-only, with no action buttons.
8. **History:** rows in time order with when, actor kind tag (PERSON / AGENT / FACTORY), actor, event, version and detail. Restricted entries show "Restricted" with who and when only. The `kind` filter is sent to the API. Paging uses a 10/20/50 rows choice with default 20 and cursor "Show more" (D-PAGING r2), and shows `as_of`. Times are shown in WAT (Africa/Lagos), as the board says. Nothing on the view is editable (INV-AUDIT).
9. **Updates (D-UPDATES r2):** re-fetch the open work item every 5 seconds while `agent.status = working` and the page is visible. Otherwise, do not poll. Re-fetch history when the item's revision changes.
10. **States:** loading, error with retry, and empty history use the shared STATES pattern. A 404 or 403 shows the SCR-02 permission board ("You can't open this work item"; nothing about the item is shown). A 401 follows the shell's existing handling.
11. **Mock and tests:**
    - Fixtures: per PMO-0-3. They must validate against openapi.json, and include at least the A-WORKITEM given, an agent-working item, a restricted history entry, and a history with a return and an approval.
    - Unit and component tests: fact and state rendering, including that unknown is never shown as zero or empty; the restricted entry; the history filter and paging parameters; the 5-second polling rule.
    - Contract test: the new fixtures.
    - Accessibility: automated checks at 390px and 1440px for both views.

**Out:** the decision panel, claim/decide and stale reload (F-04 / FE-DECIDE). The My work list (F-02). Reconcile, resume, record-response, upload-evidence and send actions (FE-M2). The Documents tab and SCR-08. CSV download. The notification bell. Any backend or `apps/api` work, and any change to openapi.json.

**Task IDs:** FE-WORKITEM (R-WORKITEM, D-UPDATES; D-PAGING for history). **Acceptance:** A-WORKITEM, A-HISTORY, A-ACCESSIBILITY. **Endpoints:** E-WORK-ITEM and E-WORK-HISTORY, consumed through the mock.

## Risk
I rated it medium, not low. It renders several cross-layer contract shapes (11 states, 7 station statuses, 4 fact statuses, restricted history). It carries rules that must not be weakened in the UI: INV-FACTS, INV-UNKNOWN, INV-AGENT and INV-RESTRICTED (`architecture/packages/v3/handoff.md`, Invariants). It also has to share `frontend/mock/server.mjs` and the E-WORK-ITEM fixture with two parallel features (PMO-0-3). It is not high: it is read-only, holds no money logic, identity or migrations, writes nothing, and runs locally on the mock.

Surfaces:
- `ui`: SCR-02 and the history view.
- `api`: it consumes two contract operations through the generated client and extends the contract mock.

The surfaces exclude `contract-change` because openapi.json is not edited; the gaps in PMO-0-1 and PMO-0-2 go to architecture. They exclude `auth` because the page only reacts to 401, 403 and 404.

Product acceptance is not required. The work conforms to the client-approved SCR-02 boards and adds no new flow, copy or business rule. Omitting design values that the contract lacks is conformance, not new behaviour.

## Notes
- I could not run `design.py check` because my role is read-only. The coordinator's design gate should confirm it before build.
- The mock still loads `architecture/packages/v2-reviewed/openapi.json` (`server.mjs:13`). v3's impact.json lists E-WORK-ITEM and E-WORK-HISTORY as unchanged, so this is not a blocker.

## Questions
None.
