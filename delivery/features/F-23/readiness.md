DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change, external-messaging, product-decision
PRODUCT-ACCEPTANCE: not-required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-23 is the first half of FE-LINE-MINUTES (SCR-28): the PM reviews Tola's suggested decisions and actions, confirms them, and for client minutes the draft goes to the PMO Lead for review. It is 8 of the 12 boards (default, suggesting, drafted, review, each desktop and phone), which meets the D-64 cap. The `internal` and `published` boards (4) go to a follow-on feature (F-23b) that depends on F-23.
- Gates are met. FE-LINE-MINUTES is in architecture v7 with no unresolved gates, depends only on FE-WORKSPACE-FRAME (F-17, merged), and acceptance is A-WORKSPACE (architecture/packages/v7/delivery.md:2046-2076). SCR-28 is in the client approval of 13 Nov 2026 (design/review.json:41, approved_at 2026-11-13T15:33:13Z).
- The one soft gate is D-LINE-WORKSPACE, still `proposed`. It counts only under the recorded exception (architecture/sources/decisions-2026-11-15.md items (g) and (i)), on the same terms as F-17 and F-21: contract mock only, the backend developer may change or refuse any field, nothing released.
- The backend handoff (delivery/backend-handoff/gaps-c-client-lines.md, SCR-28) lists 7 "blocking" gaps. They block the real backend, not this frontend. Each one is a contract proposal the backend must settle, and the frame already has the pieces to draw the boards from mock data (`suggestions` sections, `items` and `item` steps, `checklist`, `facts`, `recipients`, `task_id` decision step). No business rule is invented. The frontend shows what the backend returns and decides nothing.
- I did not run `design.py check` because my role has no shell. The spec writer or builder runs it first and stops if it fails.

## Scope
**Outcome (one):** a PM opens a minutes work item (`/work/{work_id}`, line key `minutes`). They see the meeting and Tola's suggestions, keep, edit or remove each one, confirm, and for client minutes the draft reaches the PMO Lead, who approves or returns it. All of it is on the contract mock, rendered through the F-17 workspace frame (`frontend/src/features/workspace/`). No new route and no minutes-specific page.

**Boards in F-23 (8):** design/canvas/project/
- SCR-28-desktop and SCR-28-mobile (`default`): meeting card (`facts`), suggested decisions with "Keep this decision" ticked, suggested actions with owner, due and Remove, "+ Add an action", the audience, and "Confirm and create actions".
- SCR-28-desktop-suggesting and SCR-28-mobile-suggesting (`suggesting`): Tola is reading the notes (`checklist` with `now` and `done`, "Found 2 decisions", the notes file, "From Notes · 14:12"). The pulse respects prefers-reduced-motion as the board does.
- SCR-28-desktop-drafted and SCR-28-mobile-drafted (`drafted`): the drafted summary rows (IN, ATTACHED, TEST TEMPLATE), attendees ("6 ATTENDEES"), "Open the minutes" (`version.document_id`) and the send for review step.
- SCR-28-desktop-review and SCR-28-mobile-review (`review`): the PMO Lead sees "Minutes v1 · client version", the recipients, and the Decide panel ("Approving sends this exact version to the client", "Approve and send", "Return with a note").

**Reuse, not rebuild:**
- Extend the F-17 frame only with small general changes. Do not fork it, and do not write a minutes-specific page. The frame already has `suggestions`, `checklist`, `facts`, `recipients`, `table` and `timeline` sections, `applies_to: items` and `item` steps, and the `task_id` decision link.
- Approve and Return go through the existing decision path: E-TASK-CLAIM and E-TASK-DECIDE, as in F-16, F-17 and F-21. Keep the F-17 rule that after an `effect_uncertain` send the only action is reconcile on E-WORK-ACTION. There is no resend and no new key (INV-RESEND).
- Write steps use E-WORK-STEP with the F-17 idempotency key, `expected_revision` and 409 reload.
- Build on the shared component library from the start (D-91..D-96). No local copies of buttons, tags, tables or panels, and tokens only, no hard-coded colour.

**Task ID and endpoints:** FE-LINE-MINUTES (R-WORKITEM, R-DECIDE), first part. E-WORK-ITEM (read, `workspace`), E-WORK-STEP (steps `edit_item`, `remove_item`, `add_action`, `confirm_minutes`, `save_for_later`, `send_for_review`), E-LINE-OPTIONS (owner options), E-TASK-CLAIM, E-TASK-DECIDE, E-WORK-ACTION (reuse), and E-DOCUMENT for "Open the minutes". All on the contract mock. Acceptance: A-WORKSPACE (frontend half), with A-WORKITEM, A-DECIDE and the F-17 and F-21 tests staying green.

**Tests and fidelity (D-64, D-83, decisions item (h)):** v7-typed fixtures for the four states, and a mock handler for the minutes steps that validates against the schema (confirm sends the exact `item_ids` shown, a stale `expected_revision` returns 409 and reloads). Unit tests, and Playwright with axe at 390 and 1440. The UI review passes only on the design-fidelity check of all 8 boards, with every element present and a score of at least 90. Run fidelity once per round and re-run only the reviews the change affects. Sonnet builder unless the spec rates the work high risk.

**Out:**
- The `internal` and `published` boards (F-23b): the filed-at-once result, the "Actions created" list, "OWNER NEEDED" and the delivery receipts.
- Every other line. Backend, OpenAPI, `schema.d.ts` regeneration and `architecture/**`. If a board needs something the contract lacks, record a contract proposal in build.md and do not extend the contract locally.
- Real sends, real meeting records, real notes parsing. Nothing leaves the mock.
- Changes to `src/shell/**`, `my-work/**` and the existing work item boards.

**Seam and split:** F-23 ends at the review decision. After Approve or Return, the page shows only the generic F-17 outcomes (done reload, queued, uncertain) and renders whatever the reloaded mock returns. Do not tune the fixtures to the internal or published boards.

## Binding rules for the spec
- The frontend shows only what the backend returns. Counts, cite lists, the template label ("TEST TEMPLATE"), step names, the `consequence` text and the recipients all come from the data. Nothing is derived from `/me` roles.
- Agents draft and suggest; people decide. Nothing suggested becomes a decision or action until the PM presses the confirm step. The UI must not auto-confirm, pre-submit, or offer "accept all" outside the board's pre-ticked decisions. Text from the notes cannot set an owner, a due date, an audience or an approval (INV-AGENT). Each suggestion shows its notes cite so the PM can check it.
- The confirm step sends exactly the set the PM saw (`item_ids`) with the workspace `revision`. A 409 reloads and the PM sees the new set before confirming again.
- The PMO Lead's approval is a human decision through E-TASK-DECIDE. Model output never grants authority. The review panel shows the exact recipients from the data (client contact records) and the exact version. The frontend never edits them.
- Unknown values show "Unknown", never 0 or blank (INV-UNKNOWN). A blank due date is sent as nothing, not today. An action without an owner shows "Choose an owner".
- Return needs a note. Show the note field on the phone `review` board as well as on desktop: the phone board omits it, but the write requires it (design engineer to confirm; the spec records it as a fidelity exception request, not a silent deviation).
- No wrapping button labels, tags on one line, per the design rules in screens.md.

## Contract proposals the spec must carry
The builder records each in build.md, renders against the mock, and does not extend the contract locally. All are additive. Source: gaps-c-client-lines.md.
1. **G-SCR28-1 default confirm set** (blocking for the backend): `steps[].items_default: "checked"`, with `item_ids` covering the kept decisions and all remaining actions. The frame today starts `items` steps unchecked, so the builder adds a small general change that honours `items_default` and falls back to unchecked.
2. **G-SCR28-2 owner and due editing** (nice-to-have): edit by per-item step form (form-on-press, as F-21 chose), not inline in the table. Owner options carry `hint` ("recorded by PM", "client"), and the backend stores `recorded_by_pm` and `outside_party` from the chosen option. The frontend sends only the option value. Prefilling needs the same list-of-values `value` F-21 proposed.
3. **G-SCR28-3 links** (X-LINKS): `workspace.links[]` {key, label, target kind}, and `link.action_id` in cells and cites. In F-23, "Open the minutes" works through `version.document_id`. "Ask Tola" and any link the data does not provide render only when the data supplies them. "Open actions" belongs to F-23b.
4. **G-SCR28-4 option scope** (X-STEP-OPTIONS): E-LINE-OPTIONS takes a `work_id` query parameter, so the owner picker and "+ Add an action" are scoped to the work item's case and the person's grants. The mock keys options by work item.
5. **G-SCR28-5 audience**: render the audience as a `choice` only if the data says it may change, otherwise as display. The frontend does not decide whether client minutes need review; the step returns the new `steps` and `consequence`. Record the question for the backend.
6. **G-SCR28-6 records**: there is no REC-ACTION, REC-DECISION or REC-MEETING in model.json. This does not block the mock, because the meeting card is `facts` and suggestions are section items. Record it as a backend item, not a frontend change. Where meetings come from is an open backend question.
7. **G-SCR28-7 order of creation**: whether actions are created at confirm or at approval is the backend's rule. The frontend shows the `consequence` text of `confirm_minutes` and `send_for_review` as returned, and adds no wording of its own.
8. **G-SCR28-8 recipients**: the review task shows exact recipients from the data (`decision.recipient` or a `recipients` section with `receipt: not_yet`). They never come from the notes text.
9. **G-SCR28-9 notes are untrusted** (nice-to-have): no schema change. `suggestions[].cites` carries `evidence_id` for the notes passage.
10. **D-RETURN** (Return with a note): the note is required. Whether a return keeps the confirmed decisions and actions or reopens them is a backend question. The frontend reloads the work item and renders what comes back.
11. **Backend items, not blocking:** E-WORK-STEP and the `workspace` block are unimplemented. Idempotency is a backend promise not yet built. "No duplicate send" is verified only on the mock. The client template is a test template (product decisions, Nov 2026) until PSL supplies the real one. D-ALERT-PROVIDERS gates the real client send and does not gate the mock.

## Risk
Medium. The work sits on the shared F-17 renderer (`features/workspace/**`, `features/work-item/**`) and a proposed v7 contract (D-LINE-WORKSPACE) that the backend may change, and the review state carries "Approve and send" to a client (INV-RESEND, effect_uncertain). It stays at medium because everything is on the mock, the send is unimplemented in the backend and nothing is released. SURFACES: ui (8 boards), api (E-WORK-STEP, E-WORK-ITEM workspace, E-LINE-OPTIONS), contract-change (items_default, links, work_id on options), external-messaging (client minutes send and uncertain-effect handling), product-decision (the backend must settle audience change, order of creation and return behaviour, none of which the frontend decides). PRODUCT-ACCEPTANCE is not-required because the work conforms to the client-approved boards.

## Questions
None. Open design item for the design engineer, not blocking: the phone `review` board has no note field, but the return needs one.
