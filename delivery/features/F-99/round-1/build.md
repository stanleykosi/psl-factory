STATUS: READY
COMMIT: bf88a9afbe56b7e05b09511f310b7ae42832275b
BUILDER: builder
LANE: frontend

## Summary
- The costing sheet (SCR-27) is the `bid-pricing` panel on the live work item (rfp-response line). It reads `GET /work/{id}/bid-pricing` and the project's `GET /projects/{case_id}/costing` (rule used; if that read fails the rest still draws).
- It shows the held reasons (not current, estimate missing, security estimate missing), the backend's `costing_note` as given (this is where the D-214 template/placeholder wording comes from), the inputs with versions, the calculated figures (known value as given with its unit; null reads Unknown; none = "No calculated amounts are available yet."), the rule used, the approvals in order with their state, the adjustment limits, and any pending / last price change.
- Writes: the decision on the approval waiting now (Approve, Return with a note, Refuse) via `POST /work/{id}/reviews` {kind bid, subject commercial, target_id = commercial_revision_id, role = the waiting approval's `role`, verdict, evidence_id null, note} with `expected_revision` and `case_revision`; the PM price proposal and the decision on a pending price change via `POST /work/{id}/bid-pricing`. Uses `useWorkCommand` (shared write locks); the result is told from the re-read.
- Registered with one import line in `workspace/lines/index.ts`. No shared API changed. Mock `mock/costing-live.mjs` (ids 4700 to 4705) registered in `mock/server.mjs`.

## Changes
- `frontend/src/features/costing/model.ts`: readback types, sections, command descriptors.
- `frontend/src/features/costing/costingAdapter.ts`: adapter (key `bid-pricing`).
- `frontend/src/features/costing/CostingActions.tsx`: approval, proposal and price-decision controls.
- `frontend/src/features/workspace/lines/index.ts`: one import line.
- `frontend/mock/costing-live.mjs`, `frontend/mock/server.mjs`: fixtures and routes, both project path forms, `node --check` ok.
- `frontend/tests/costing-live.test.tsx`, `frontend/e2e/costing-live.spec.ts`.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Inputs and versions, figures (unknown stays unknown), rule used, approvals and their state: vitest "costing reads" and e2e 4700/4705.
2. [x] Held reasons and no controls when held: e2e 4703, vitest.
3. [x] Approval decision with exact body and tokens, re-read tells the result: vitest "approves the step waiting now" (CEO role, target_id 5); e2e 4701 shows three Approved.
4. [x] Price proposal and its decision, exact bodies: vitest; the mock validates bodies against the contract schema.
5. [x] Desktop 1440 and phone 390: e2e 6 of 6 passed (ports 4990/4991, stopped by Playwright); no horizontal scroll; Approve is at least 44px high on the phone.

## Held, and why
- Who may decide an approval step: the live read has no per-step flag (`can_decide` / `can_propose` belong to the price-change writes, read from the contract summary and C-29). The step controls therefore show for the waiting step with the line "The server checks that you are the person for this step", and the server's 403/409 words show if not. The coordinator may want a backend flag so the buttons can be hidden for others (question for backend).
- Price change forms are drawn only when `can_propose` (with targets) or `can_decide` (with a pending change) say so; `adjustment_targets` is empty in the demo, so they are hidden there. The second proposal variant (body with `action` of unspecified value) is not built.
- Not drawn, the API does not serve them: rule explanation text, display names for figure keys (keys are shown in plain words, as C-26 says to resolve names from the rule), cost version history, Tola's past-bid note, Ask Security (`security-estimate` is not built; demo user gets 403 on it).
- Demo data: the local demo database returns `amounts: []` for the verified bids (note: "calculated amounts are unavailable here"), so figures could only be checked on the mock.
- Board SCR-27 (mobile approvals) read as text only; no fidelity-tool run (lean mode).

## Validation
- `npx tsc --noEmit`: pass.
- `eslint . --max-warnings 0`: pass.
- vitest: costing-live 11 of 11; next-config, demo-mock, mock-contract, line-adapter, live-work-item together 414 of 414 passed.
- Playwright costing-live: 6 of 6 (desktop 1440, phone 390).
- Full vitest: 191 files, 4415 tests passed. The CI run on GitHub is the authority for the production build.
