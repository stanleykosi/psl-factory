DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change, external-messaging
PRODUCT-ACCEPTANCE: not-required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-21 is the first half of FE-LINE-WEEKLY (SCR-25): the PM writes the four parts, Tola assembles, the PMO Lead reviews. It is 8 of the 12 boards (4 states x desktop and phone), which meets the D-64 cap of about 8. The other 4 (returned, received) go to a follow-on feature, F-21b.
- Gates are met. FE-LINE-WEEKLY is in architecture v7 with no unresolved gates (architecture/packages/v7/delivery.md:2014-2044). SCR-25 is in the client approval of 13 Nov 2026 (design/review.json:38, approved_at 2026-11-13T15:33:13Z). The dependency FE-WORKSPACE-FRAME (F-17) is merged into dlv-00-delivery-setup.
- The one soft gate is D-LINE-WORKSPACE, still `proposed` (architecture/build_model.py:826), with no approval in design/review.json or packages/v7/reviews.json. It counts only under the recorded exception (architecture/sources/decisions-2026-11-15.md items (g) and (i)), on the same terms as F-17. The limits are: contract mock only, the backend developer may change or refuse any field, nothing released.
- No business rule is open. The four-part rule (each part needs words and at least one cited record, "TBD" refused) is on the boards and in screens.md:116. The frontend shows what the backend returns and decides nothing.
- I did not run `design.py check` because my role has no shell. The spec writer or builder runs it first and stops if it fails.

## Scope
**Outcome (one):** a PM starts at a weekly client report work item. The page, built from the `workspace` block, takes them from writing the four parts, through Tola assembling, to the PMO Lead's review where the report is approved or returned. This is on the contract mock. It reuses the F-17 renderer and adds no new renderer or route.

**Boards in F-21 (8):**
- SCR-25-desktop and SCR-25-mobile (`default`): "Write this week's client update". Four parts (Status, Risks, Timeline, Next steps), each with a text area and cited records plus "+ cite a record". Also the "This week's records · 5–11 Nov" side panel (meetings, milestones completed, actions, issues open, changes), the agent note, and the buttons "Send to Tola to assemble" and "Save draft".
- SCR-25-desktop-invalid and SCR-25-mobile-invalid (`invalid`, "can't send yet"). Per-part 422 messages ("Write the risk in words and cite at least one…", "Cite at least one record: no record cited yet"). It also shows a not-before-week-end message ("The report can't start before the week has ended. This week ended 11 Nov.") and a "NEEDS FIXING" status. Each message comes from the backend 422 (`fields[].name` maps to the part) or from workspace data. The frontend writes none of them.
- SCR-25-desktop-assembling and SCR-25-mobile-assembling (`assembling`): the agent-working panel ("Tola · PMO agent · step 3 of 4", WORKING, three progress lines with counts, "TEST TEMPLATE" tag, "Started 12 Nov 09:05", the disabled "Send for PMO Lead review", "Ask Tola"). The `agent-now` pulse must respect prefers-reduced-motion, as the board does.
- SCR-25-desktop-review and SCR-25-mobile-review (`review`): the PMO Lead sees "Report v1 · written by Tunde Bello, assembled by Tola", the four parts with record references, "Open the report as the client will see it", and the Decide panel ("Approving sends this exact version to Lagoon Health", a note that is required to return or refuse, "Approve and send", "Return with a note").

**Reuse, not rebuild:**
- Mount on the F-17 renderer (`features/work-item/**`, section kinds `text` with `cites`, `facts`, `checklist`, `timeline`, `recipients` and the step form). Do not fork it. Where the boards need a region the frame lacks, extend the frame's component with a small, general change. Do not write a weekly-specific page.
- Approve and Return go through the existing decision path: a step with `task_id` goes to E-TASK-CLAIM/E-TASK-DECIDE exactly as F-16 and F-17 do. "Approve and send" must keep the F-17 rule that after an `effect_uncertain` send the only action is reconcile on E-WORK-ACTION. There is no resend and no new key (INV-RESEND, the F-17 round-6 fix).
- The write steps ("Save draft", "Send to Tola to assemble") use E-WORK-STEP with the F-17 idempotency and 409 handling.

**Task ID and endpoints:** FE-LINE-WEEKLY (R-WORKITEM, R-DECIDE), first part. E-WORK-ITEM (read, `workspace`), E-WORK-STEP (write), E-TASK-CLAIM/E-TASK-DECIDE and E-WORK-ACTION (reuse). All on the contract mock. Acceptance: A-WORKSPACE (frontend half), with A-WORKITEM, A-DECIDE and the F-17 tests staying green.

**Tests and fidelity:** v7-typed fixtures for the four states (default, invalid with a 422, assembling, review), plus a mock handler for the weekly line's steps that validates against the schema. Unit tests, and Playwright with axe at 390 and 1440. Per D-64 and decisions item (h), the UI review passes only on the design-fidelity check of all 8 boards, with every element present and a score of at least 90, one fidelity run per round. Tokens only, no hard-coded colour.

**Binding rules for the spec:**
- The frontend shows only what the backend returns. The record panel, the counts ("3 overdue · 1 without an owner"), the cite lists, the template label and the step name come from the data. Nothing is derived from `/me` roles.
- Unknown values show "Unknown". Nothing shows 0 or blank (INV-UNKNOWN).
- Tola assembles but does not write the client text. The words come from the PM, and the UI must not offer to generate them.
- The sample or test-template label shows when the data says so ("TEST TEMPLATE"). Do not claim a real client template.

**Seam and the split:** the split is by state, as the coordinator proposed. Default through review is the intake to the review decision, with one observable outcome ("the PM's text reaches the PMO Lead for review"). `returned` and `received` are the results of that decision. They are a distinct outcome: the return and edit loop (v2) and the client receipt with its delivery confirmations. They belong to F-21b, with 4 boards (SCR-25-desktop/mobile-returned and -received), which depends on F-21. F-21 must not build the returned or received pages. After Approve or Return, the page shows only the generic F-17 outcomes (done reload, queued, uncertain), and the reloaded work item renders whatever the mock returns. The F-21 mock may carry a returned or received fixture only if the F-17 renderer shows it by default. Do not tune it to those boards.

**Out:**
- The `returned` and `received` boards (F-21b).
- FE-LINE-MINUTES (SCR-28) and every other line.
- Backend, OpenAPI, `schema.d.ts` regeneration and `architecture/**`. If the boards need something the contract lacks, record it as a contract proposal in build.md and do not extend the contract locally.
- Real sends. Nothing leaves the mock.
- Changes to `src/shell/**`, `my-work/**` and the existing work item boards.

**Contract gap to check early (non-blocking):** the default board has a "+ cite a record" control that picks from this week's records, with free-text parts. F-17 reuses the Start work field-descriptor kinds. If those have no record-picker or cites field kind, the builder records a contract proposal (a "records" field kind or a cites field on text steps) in build.md and renders the cites using the existing `text.cites` display. The PM's pick lists come from the records panel data. If it truly cannot be built with the frame, the spec writer stops and reports it. It does not invent a local shape.

**Backend items to record (not blocking):** E-WORK-STEP and the `workspace` block are unimplemented. Idempotency is a backend promise not yet built (COORDINATOR-HANDOFF.md:37, 40). The frame sends the key and trusts none of it. "No duplicate send" is verified only on the mock. The client template is a test template (product decisions, Nov 2026) until PSL supplies the real one.

**Size:** one PR on the existing frame, 8 boards, about 4 states on one route. If the spec shows more than that, split first by dropping the phone boards to a follow-on. Do not pull in returned or received.

## Risk
Medium. The work is on a shared renderer (`features/work-item/**`, touched by F-09, F-14, F-16, F-17) and a proposed v7 contract (D-LINE-WORKSPACE) that the backend may change. The review state includes "Approve and send", which sends to a client (INV-RESEND, effect_uncertain). It stays at medium because all of it is on the mock, the send is unimplemented in the backend, and nothing is released. SURFACES: ui (8 boards), api (E-WORK-STEP, E-WORK-ITEM workspace), contract-change (proposed block), external-messaging (client report send and uncertain-effect handling). PRODUCT-ACCEPTANCE is not-required because the work conforms to the client-approved boards. The business rules (four cited parts, PMO Lead review, exact version sent) are already on the boards and in screens.md.

## Questions
None.
