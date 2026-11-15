DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change, external-messaging
PRODUCT-ACCEPTANCE: not-required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-17 is FE-WORKSPACE-FRAME only: the generic renderer for the v7 `workspace` block on the work item (typed sections, step forms built from field descriptors, the step write). It is infrastructure. No line screen is built here, and the frame has no board of its own (delivery/screen-coverage.md:186 lists no SCR for it).
- Gates are met. The task is in architecture v7 with "Unresolved gates: none" (architecture/packages/v7/delivery.md:1809-1841). Dependencies FE-WORKITEM (F-14), FE-DECIDE (F-16), FE-M2B-RESPONSE (F-09) and FE-CONTRACT-V7 (F-13) are merged, and `schema.d.ts` already types `workspace` and the step write. No business rule is open.
- The one soft gate: D-LINE-WORKSPACE (build_model.py:826) is `proposed`, and design/review.json and architecture/packages/v7/reviews.json hold no approval for it. It counts only under the recorded exception (architecture/sources/decisions-2026-11-15.md items (g), (i)): contract mock only, the backend developer may change or refuse any field, nothing released. Same basis as F-09 (D-RESPONSE-VIEW). The spec must state these limits, and the PR must not claim a real backend.
- No mock handler for the step write exists yet (the only `workspace` use in `frontend/src` is `schema.d.ts` and a type reference in `features/decide/DecisionContent.tsx`). The builder adds the fixtures and handler.
- Risk is medium: a new cross-layer proposed contract, a write that can send to clients, and shared code (work item page, decide, response). The step write is mock-only, so nothing irreversible runs.
- `design.py check` was not run (my role has no shell). The spec writer or builder runs it first and stops if it fails.

## Scope
**Outcome (one):** when the work item returns a `workspace` block, the work item page renders it from the data alone (sections by kind, steps offered only as returned, step forms from descriptors) and takes a step safely, on the contract mock. A work item with no `workspace` looks and behaves exactly as it does today.

**In (binding):**
1. A workspace renderer mounted on `features/work-item/**` (the page, not a new route), driven only by `workspace` in E-WORK-ITEM. Header from `title`, `subtitle`, `status`, `byline`, `version`, `context.crumbs`, `agent_note`, `revision`. The frontend decides no content. It shows what is returned, and an absent field is hidden, never guessed.
2. One component per section kind: `facts, table, checklist, findings, suggestions, recipients, figures, text, timeline`. Table cells by column kind (`text, money, date, tag, reference, integer`). Item `status`, `severity`, `receipt` (`received, not_yet, uncertain, failed, unknown`), `cites` and `cite_label`, `owner`, `due`, `held_by`, `agent`, and per-item `steps`. Paging by `next_cursor` and `filters` where a section returns them.
3. Rules the renderer must keep (INV): `restricted=true` sections show `restricted_label` and no rows; unknown money and dates show "Unknown", never 0 or blank (INV-UNKNOWN); `as_of` and `coverage` are shown when returned; the sample label shows when `sample: true`.
4. Step forms built from `steps[].fields` using the same field-descriptor kinds as the Start work intake (D-START-INTAKE; reuse the F-05 field components in `features/start-work/**`, do not fork them). Show `consequence`, `confirm`, `emphasis`, `disabled_reason`, `claim_required`, `sends`. `applies_to` decides workspace, item or items scope, with `item_ids`. Client-side checks are only what the descriptor states. A 422 maps `fields[].name` to the right input.
5. Step write: POST E-WORK-STEP (`/api/v1/work/{work_id}/steps`) with the CSRF header, `expected_revision` from `workspace.revision` (not guessed), `step`, `item_ids`, `inputs`, optional `evidence_ids`, `note` (max 2000) and `idempotency_key`.
   - One key per user attempt, generated when the form opens or on first submit, reused on any repeat of that same attempt, and a new key only for a new attempt. The button is disabled while in flight.
   - No automatic retry of any write. Responses by `outcome`: `done` (reload the work item), `queued` (show waiting, reload), `effect_uncertain` (show the uncertain state with the returned `message`; no resend, no new key, and the page offers only reconcile through the existing E-WORK-ACTION path from F-09, INV-RESEND). 409 follows the F-16/F-14 flow (keep what is shown, reload, show the current version, never auto-repeat). 401, 403, 404 and 422 use the existing ApiError mapping.
   - A step that carries `task_id` is a decision: it goes to E-TASK-CLAIM/E-TASK-DECIDE exactly as F-16 does (reuse that code), never to E-WORK-STEP. Responses stay on E-RESPONSE and reconcile on E-WORK-ACTION. The frame links to those paths and does not reimplement them.
   - Controls render only for returned steps. Eligibility is never derived from `/me` roles.
6. Mock and tests: v7-typed fixtures with one workspace per section kind plus the states (restricted, unknown, empty, effect_uncertain, 409, 422, queued), a mock handler for E-WORK-STEP that validates against the schema, unit tests, and Playwright with axe at 390 and 1440 on a frame test page. Existing work item, decide and response tests stay green.

**Boards: what this frame satisfies and what is left to later tasks**
- The frame owns the shape and look of every section kind, the step button row and consequence sentence, the step form, and the saved, queued, uncertain, stale and error states. Each is drawn on the line boards, so the spec writer lists, for each of the 9 kinds and the step form, the specific board region that is the anchor. Starting anchors, to confirm in the spec, are SCR-25 `review` and `received` (text with cites, "Approving sends this exact version", recipients and receipts), SCR-26 (suggestions and table), SCR-28 `suggesting` (checklist/suggestions with owner and due), SCR-44 `readiness` (checklist), SCR-45 `signatures`, SCR-46 `evaluating`, SCR-49 `blocked` (findings), SCR-52 `received` (recipients and receipts) and the Finance SCR-53..58 (figures, Unknown, quarantine findings). Tokens only, no hard-coded colour.
- No whole-board fidelity score is required of F-17 (there is no SCR for it and the pages are composed from per-line titles, copy and section order the backend returns). The design-fidelity gate for those anchored regions applies at the line tasks. Because a UI review needs something to gate on, the spec must either state the region-level check it uses or name an exception for the design engineer to sign. That is non-blocking and the design engineer should confirm it before the build.
- Belong to later tasks, not F-17: every line page and its copy, content and states. These are FE-LINE-WEEKLY (SCR-25), FE-RFP-RESPONSE (SCR-26), FE-COSTING (SCR-27, gated by D-COSTING-RULE), FE-LINE-MINUTES (SCR-28), FE-ISSUE (SCR-30), FE-CHANGE (SCR-31, D-CHANGE-DECIDERS), FE-DELIVERY-CLOSURE (SCR-33, 48, 49), FE-RFP-SUBMIT (SCR-40), FE-ENGAGEMENT-PLANNING (SCR-41, 42), FE-DELIVERY-RELEASE (SCR-43-45), FE-DELIVERY-HYPERCARE-ARCHIVE (SCR-46, 47), FE-EMERGENCY-ESCALATION (SCR-50, 51), FE-LEADERSHIP-REPORT (SCR-52), FE-PAYMENTS (SCR-20, 32), and the Finance FE-FIN-* tasks (SCR-09, 18, 37, 53-59). Also later: the FE-DECIDE-VARIANTS boards, and the payment, costing and change decision flows.

**Out:**
- Any line-specific page, route, copy, or screen state. Any rule about which sections or steps exist (backend-composed).
- Backend, OpenAPI, `schema.d.ts` regeneration, `architecture/**`. If the frame cannot render something the schema lacks, record it as a contract proposal in build.md, as F-14 did. Never extend the contract locally.
- `src/shell/**`, `my-work/**`, the decide page's own layout, and the existing work item boards, unchanged apart from mounting the workspace block.
- Real sends. Nothing leaves the mock.

**Size:** one PR. A generic renderer with 9 section components, one form and one write path on one route. The risk of growth is a builder who starts a line page, which would break the one-PR size. If the spec exceeds the limit, split as (a) read-only sections renderer and (b) step form and write, in that order. Do not split by line.

**Backend items to record (not blocking):** E-WORK-STEP and the `workspace` block are `unimplemented`. The idempotency behaviour (the same key returns the same result, no second send) is a backend promise not yet built (COORDINATOR-HANDOFF.md:37, PMO-0-2). The frame sends the key and trusts none of it. Do not claim "no duplicate send" as verified. It is verified only on the mock.

**Task ID:** FE-WORKSPACE-FRAME (R-WORKITEM). **Endpoints:** E-WORK-ITEM (read, `workspace`), E-WORK-STEP (write), and reuse of E-TASK-CLAIM, E-TASK-DECIDE, E-RESPONSE and E-WORK-ACTION, all on the contract mock. **Acceptance:** A-WORKSPACE (frontend half) plus A-WORKITEM, A-DECIDE and the response tests keep passing. **Decision consumed:** D-LINE-WORKSPACE (proposal, under the recorded exception).

## Risk
Medium. The frame is a shared renderer on `features/work-item/**` (also touched by F-09, F-14, F-16) and defines the one write that every later line uses, including steps that send to clients (`sends`, `effect_uncertain`, INV-RESEND), so a wrong duplicate-submit, retry or restricted-section rule here is copied into about 25 screens. It stays at medium and not high because it is mock-only, the write is unimplemented in the backend, and nothing is released. SURFACES: `ui` (the renderer), `api` (new write and request shape), `contract-change` (it consumes a still-proposed v7 block that the backend developer may change) and `external-messaging` (steps that send and uncertain-effect handling). Money appears only as displayed values (unknown never 0); payment decisions are out of scope, so `payments` is not listed.

## Questions
None.
