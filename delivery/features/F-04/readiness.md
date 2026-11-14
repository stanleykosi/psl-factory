DECISION: READY
RISK: high
SURFACES: ui, api, security, payments, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
COMMIT: none (round 0, no head yet)
REVIEWER: readiness
AUTHORITY: PMO readiness (delivery step 1)

## Summary
- F-04 is now FE-DECIDE in architecture v4: the standard decision only. That covers approve, return and reject, the stale version, not yours and own work, with acceptance A-DECIDE, A-STALE and A-NOT-YOURS. Its only dependency, T-FRONTEND-SHELL, is merged (F-01, a41d472). validation.json lists `"FE-DECIDE": []` and delivery.md says "Unresolved gates: none". The client approved SCR-03 on 13 Nov 2026 (design/review.json, canvas 1794581312-b166, both canvases), and the coordinator reports that `design.py check` passes.
- The three v3 blockers are cleared or moved:
  - PMO-0-1 and PMO-0-2 (decision content, who may decide): v4 adds the optional `tasks[].decision`, `cannot_act_reason` and `asked` fields to E-WORK-ITEM (openapi.json, D-TASK-DECISION-VIEW r1).
  - PMO-0-3 (payment-exception verdicts): moved out to FE-DECIDE-VARIANTS, which is gated on the open D-DECISION-VARIANTS. The v3 split is now the architecture's own split.
- D-TASK-DECISION-VIEW and D-WORKITEM-DETAIL are still `proposed`, and the backend developer owns them. The design engineer's recorded choice of 13 Nov (architecture/sources/decisions-2026-11-13-v3.md, item 1) is an explicit exception: the frontend builds against the proposed fields on the mock. That exception has limits. The field shapes may still change, the decisions gate FE-CONNECT-1 and T-DECIDE, and nothing here is released. D-RETURN r2 (open) is the recorded working assumption; the frontend only sends `return` with a note.
- Risk is high. This is the one-tap screen where people approve invoices, so it shows money (with an unknown form), carries the revision and concurrency check (409), reflects separation of duties, and sends CSRF-bound writes. The work runs on the mock only.
- Product acceptance is required. The decision fields are frontend-drafted proposals. Two cannot-act reasons, `already_decided` and `not_your_turn`, have no board copy. Some board elements have no contract and will be omitted (the comment box and the "1 of 3" decision pager). The design engineer must see all of these.

## Findings
- PMO-0-1 | non-blocking | medium | integration | Per-id E-WORK-ITEM serving belongs to F-03 (delivery/features/F-03/spec.md:48-60). F-03 serves `frontend/mock/fixtures/work/<id>.json` when present, answers 404 for W-1099, and otherwise falls back to `E-WORK-ITEM.json`. Expected: F-04 puts its decision work items, from W-1201 up, in that same folder and does not write a second E-WORK-ITEM selector in server.mjs. If F-03's mock change has not merged when F-04's build reaches the mock, the builder rebases onto it first. F-04 owns only the E-TASK-CLAIM and E-TASK-DECIDE handlers and its own fixtures.
- PMO-0-2 | non-blocking | medium | frontend | Repointing the contract to v4 touches more than server.mjs:13. The generator script (`frontend/package.json:12`), `src/api/schema.d.ts` (regenerated), `tests/api-schema-drift.test.ts:16` and the header comment at `src/api/client.ts:1` all name `v2-reviewed`. F-03's spec forbids F-03 from editing schema.d.ts (spec.md:256), and F-02's spec says not to repoint, so F-04 is the only owner. The v4 changes are additive and optional (impact.json; D-TASK-DECISION-VIEW and D-WORKITEM-DETAIL rationale), so F-02 and F-03 fixtures should stay valid. Expected: repoint all four places in one commit, and confirm that `tests/mock-contract.test.ts` still validates every existing fixture against v4.
- PMO-0-3 | non-blocking | medium | frontend | The mock is stateless (server.mjs:76,98), so it cannot show two of the required states end to end:
  - A-STALE: a 409, then a reload that returns the newer version.
  - The done board: the approved state after a decision.

  QA-3-2 is also still open: write bodies are drained, not validated (server.mjs:79-80). Expected:
  - Claim and decide validate the body against the v4 request schema with the existing devDependency `ajv`, so no new package. They answer 422 for a missing `expected_revision`, an unknown verdict or extra properties.
  - They answer 409 when `expected_revision` does not match the task's fixture revision.
  - For stale and done, the mock uses paired per-id fixtures or a minimal in-memory state that resets on restart. Today's scenario cookies keep working.
- PMO-0-4 | non-blocking | low | integration | Some board elements have no contract field or endpoint:
  - The not-yours board's "Comment for the Finance Lead (optional)" and "Add comment" (SCR-03-desktop-not-yours): no comment endpoint exists in v4.
  - The "DECISIONS / 1 OF 3" pager and "Next decision · 2 of 3" (SCR-03-desktop, SCR-03-desktop-done): E-WORK-ITEM carries no decision queue.

  Expected: omit them, invent nothing, and list them in build.md for product acceptance and for the backend developer.
- PMO-0-5 | non-blocking | low | backend | The E-TASK-DECIDE `note` rules ("Up to 2000 characters; required to return, reject or withdraw") appear only in the schema description. There is no `maxLength` and no conditional requirement (handoff.md, E-TASK-DECIDE request). Expected: the frontend enforces both in the UI, and the mock rejects a body that breaks them. The backend developer should put them in the schema before FE-CONNECT-1.

## Scope
**Outcome (one, observable):** an eligible person follows F-03's link `/work/<id>/decide?task=<task id>` (or an alert link) and sees the exact version they are asked to decide. They approve it, return it or reject it, and see the result. A person who cannot act sees why and who was asked instead. This works at 390px and 1440px on the contract mock, and A-DECIDE, A-STALE and A-NOT-YOURS (frontend half) and A-ACCESSIBILITY pass on the mock.

**In:**
1. **Contract to v4** (PMO-0-2). Repoint the mock, regenerate the client and update the drift test to `architecture/packages/v4/openapi.json`. Do not edit openapi.json.
2. **Route** `frontend/src/app/work/[id]/decide/**`, with components in `frontend/src/features/decide/**`. The route reads E-WORK-ITEM and selects the task by the `task` query parameter. A missing or unknown task shows the not-found state.
3. **Decision content (default board):** render only `tasks[].decision`:
   - the version label;
   - the amount (`unknown: true` shows "Unknown", never 0 or blank, INV-UNKNOWN);
   - the basis;
   - the recipient;
   - "Changed since <previous_label>" with its items;
   - the preparer, with any agent;
   - the approval chain with "step n of m" from `your_step` and `step_count`.

   Leave out any field that is absent. The facts strip and the agent card reuse the E-WORK-ITEM data. The sample label appears whenever `sample: true`.
4. **Claim:** when `you_can_act` is true, call E-TASK-CLAIM with `expected_revision` set to the task revision and the CSRF header, as the endpoint's trigger says ("Open a decision you are eligible for"). A 403 shows the not-yours view, a 409 goes to the stale flow, and a 422 shows an inline error.
5. **Decide:** Approve, Return and Reject call E-TASK-DECIDE with `expected_revision` and `verdict` (`approve | return | reject`). A note is required for return and reject, capped at 2000 characters. There is no client-side retry. Done state: show the response's `verdict`, `decided_by`, `decided_at` and `work_state`, then reload the work item for the facts and `next_step`.
6. **Stale (A-STALE):** on a 409 from claim or decide, keep the version already shown, reload the work item, and show the replaced and current versions side by side as the stale board does. "Review version <n>" opens the current one. Never auto-approve and never retry.
7. **Cannot act (A-NOT-YOURS):** when `you_can_act` is false, show a read-only view keyed only on `cannot_act_reason`:
   - `not_your_role` uses the not-yours board.
   - `prepared_by_you` uses the own board.
   - `already_decided` and `not_your_turn` use the same pattern with drafted copy, listed for product acceptance (PMO-0-4).

   Show the people in `asked`, with alert time and channels when present. Show no Approve, Return or Reject controls. Never derive eligibility from `/me` roles.
8. **Phone action bar** at 390px, and the desktop panel at 1440px, as on the boards. 401, 403, 404 and 422 go through the existing F-01 `ApiError` mapping.
9. **Mock and fixtures** (PMO-0-1, PMO-0-3). The E-TASK-CLAIM and E-TASK-DECIDE handlers validate bodies, return 409 on a revision mismatch, and support the stale and done flows. Add per-id decision work items from W-1201 up, all `sample: true` and valid against v4: default, unknown amount, not_your_role, prepared_by_you, already_decided, not_your_turn, stale (a version 2 → version 3 pair), and a chain with earlier approvals.
10. **Tests:**
    - Unit and component tests:
      - unknown is never shown as 0;
      - controls are absent whenever `you_can_act` is false;
      - each `cannot_act_reason` renders its view;
      - the note is required for return and reject;
      - `expected_revision` and the CSRF header are sent;
      - a 409 reloads the item and makes no second write.
    - Mock contract tests for the new fixtures and the 422 and 409 bodies.
    - Playwright and axe at 390px and 1440px for default, done, stale, not-yours and own.

**Out:**
- The payment-exception, CEO final costing and CTO emergency variants (FE-DECIDE-VARIANTS, gated on D-DECISION-VARIANTS).
- `revoke` (withdraw approval), which has no standard board.
- Comments and the decision pager (PMO-0-4).
- The work item page and history (F-03), and My work (F-02).
- Notifications (FE-M4) and the document review screen (SCR-08).
- Backend and `apps/api` work (T-DECIDE), the real API (FE-CONNECT-1) and any openapi.json edit.
- What "return" does on each line (D-RETURN).
- New npm dependencies.

**Ownership:**
- `frontend/src/app/work/[id]/decide/**` and `frontend/src/features/decide/**`.
- The E-TASK-CLAIM and E-TASK-DECIDE fixtures and handlers.
- The per-id fixtures from W-1201 up, in F-03's `fixtures/work/` folder.
- The v4 repoint: `server.mjs:13`, `package.json` gen:api, `schema.d.ts`, the drift test and the client.ts comment.

Any change to `src/shell/**` or `src/api/**` beyond these must be minimal and listed in build.md.

**Task IDs:** FE-DECIDE (R-DECIDE; D-TASK-DECISION-VIEW r1 under the recorded exception; D-APPROVAL-ORDER r1, approved, comes from the API only).
**Endpoints:** E-WORK-ITEM (read), E-TASK-CLAIM and E-TASK-DECIDE, all through the contract mock.
**Acceptance:** A-DECIDE, A-STALE and A-NOT-YOURS on the frontend side, plus A-ACCESSIBILITY. The audit event, the alert being queued, and blocking the preparer's claim are enforced by the backend.

## Risk
I rated it high:
- People approve invoices on this screen with one tap. It renders amounts that must never show unknown as zero (INV-UNKNOWN, REC-MONEY), so the surfaces include `payments`.
- It enforces "act only on the current version" through `expected_revision` and the 409 reload (INV-REVISION, O-STALE), and a stale approval is hard to undo.
- It reflects separation of duties ("Preparer cannot decide own work", REC-TASK), so `security` also covers CSRF on the two writes and never offering actions the API did not grant.

Surfaces:
- `ui`: the SCR-03 standard boards.
- `api`: the first contract writes.
- `contract-change`: F-04 moves the mock and the generated client from v2-reviewed to v4 and is the first consumer of the proposed D-TASK-DECISION-VIEW fields (PMO-0-2).

Excluded surfaces:
- `auth`: the page only reacts to 401 and uses the existing session.
- `dependency`: `ajv` is already a devDependency.
- `product-decision`: the parked variants carry the open business rule.

## Notes
- The v3 report is kept at delivery/features/F-04/readiness-v3-not-ready.md. Its PMO-0-4 is resolved by F-03's mock convention, and its PMO-0-5 (QA-3-2) is now in scope (PMO-0-3 above).
- If the backend developer changes the shape or placement of D-TASK-DECISION-VIEW before this merges, the spec must be re-checked against the new revision.
- I did not run `design.py check` because my role is read-only. The coordinator reports that it passes for version 1794581312-b166.

## Questions
None.
