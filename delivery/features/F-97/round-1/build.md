STATUS: READY
COMMIT: 0e682a26ababcc0b3bfef46ef96c2648942c2d2b
BUILDER: builder
LANE: full

## Summary
- Engagement (SCR-41) and Planning (SCR-42) now draw on the live work item through two line adapters, registered in `workspace/lines/index.ts` (panel keys `engagement` and `planning-owner-requests`). Lean mode (D-210): no fidelity run, no review agents.
- Engagement reads: route A/B/C in plain words with its capture, the finding, the three steps (PM, details, register) from `actions[]` and the recorded ids, details saved, what was agreed (`packet_sources`), named links to the project and the planning item, the planning receipt, and the sources from `engagement-intake`.
- Engagement writes: assign, details, register, reassess, each with the exact contract body, through useWorkCommand and the shared locks. Each result is told from the re-read ("Recorded" toast; the steps list shows Done only after the re-read).
- Planning reads (read only): departments table (status, estimate, received), what each department said, changed effort and its review, what holds it (finding, unresolved questions, conflicting or excluded sources, clarification findings), who receives each request (`owner_status`), waiting department requests, reviewed costing, readiness and delivery dossiers.
- Planning writes are not built (not in this task's order).

## Changes
- `frontend/src/features/engagement/model.ts`: engagement Sections and the four command descriptors.
- `frontend/src/features/engagement/EngagementActions.tsx`: the four forms, drawn only for steps listed in `actions[]`; choices come from `managers`, `assignment_roles`, `registration_roles`, `source_proofs`.
- `frontend/src/features/engagement/engagementAdapter.ts`: reads the engagement and (tolerantly) the intake; self-registers.
- `frontend/src/features/engagement/planningModel.ts`, `planningAdapter.ts`: planning Sections; reads owner requests, project planning and source clarifications; a failed packet or clarification read shows "isn’t available to you here" and keeps the rest.
- `frontend/src/features/workspace/lines/index.ts`: two import lines (shared file; only these lines added).
- `frontend/mock/engagement-live.mjs` (new), `frontend/mock/server.mjs`: fixtures 4650 to 4657 in the live shape, with strict body checks for the four writes; routed before the forecast block; reset with the mock. `node --check` passed on both.
- Tests: `frontend/tests/engagement-live.test.tsx` (13), `frontend/e2e/engagement-live.spec.ts` (4 specs x desktop 1440 and phone 390), `frontend/tests/next-config.test.ts` (one allow-list line, `engagement-live.mjs`).
- No change to shared APIs (adapter.ts, useWorkCommand, useScopedWriteLock) or protected paths.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Engagement reads route, capture, managers, roles, proofs, actions, finding, details, registration and planning links: `engagement-live.test.tsx` "registered" and "held" cases; the mock's reads are validated against the live OpenAPI 200 schemas (ajv).
2. [x] Four writes with the exact bodies: test sends assign, details, register and reassess and checks the key sets; the mock refuses extra keys, `checked:false`, an unlisted role and an empty reason with 400, and the same bodies are validated against the contract's `oneOf` in the test.
3. [x] Re-read after each write, shared locks: the chain assign, details, register moves the steps to Done only from the re-read; a 409 shows the lasting notice and the latest version; a 422 shows the server's words and records nothing.
4. [x] Planning reads: departments, unknown effort apart from not applicable and zero (QA reads Unknown, Security Not applicable), changed effort, held reasons, owner status, requests, readiness. Playwright at 1440 and 390 (production build, ports 4990/4991) passes, no horizontal overflow, 44px button on the phone.
5. [x] Checked against the demo database (read-only, GET only): work 2, 6 (engagement), 3 (planning owner requests), the engagement-intake, and planning and source-clarifications for the Kora case read as Tunde Bello. Kemi gets 404 on the project planning read, which the planning panel handles.

## Validation
- `tsc --noEmit`: clean. `eslint . --max-warnings 0`: clean.
- Full vitest: 189 files, 4385 tests passed (includes next-config, demo-mock, mock-contract, line-adapter, live-work-item).
- `engagement-live.test.tsx`: 13 passed.
- Playwright `e2e/engagement-live.spec.ts`: 8 passed (desktop 1440 and phone 390), ports 4990/4991, servers stopped.
- Not looked at in a browser by eye; coverage is by Playwright assertions. No fidelity run (lean mode, no board for this live panel).
- Branch `git status` clean and pushed. `checks.sh` runs in CI mode and waits on GitHub, so it was not run locally; the coordinator's PR carries it.

## Held, and why
- Client contact (`contact_id` on details): the contract gives no contact list or lookup, so details are sent with `contact_id: null` and the form says the contact can’t be chosen yet. (Question C-42 area: ask the backend for a contact choice list.)
- Pulling the plan and source choices: `plan_id` and `evidence_id` both come from `source_proofs`; the contract does not say which kind is the plan. Two selects, same list; the server validates. Worth a backend answer.
- Design parts the API cannot fill, hidden: packet table with IN/OUT tags and costing vs awarded price (only the `packet_sources` rows with on-file state are drawn), the "asked" wording, risks and "4 stages" lines, the link to Setup. "What registering creates" uses the project label and the planning work id; the project link uses the case id from `project.url`.
- Planning writes (department inputs, effort review, readiness, handoff, owner assignment, owner confirmation, capture, align, background): not built; `commands()` is empty. `can_record_input` and `can_assign` are read but not drawn.
- Intake paging (`next_before`) is not followed; the first page is shown.

## Notes for the coordinator
- `mock/projects.mjs` `normaliseProjectPath` turns a project UUID into a P-nnnn form before any later mock route sees it; a new project-path mock must match both forms (done here). Other future lanes will hit the same.
- Planning panel key is `planning-owner-requests` (what the work item serves), not `planning`.
