STATUS: READY
COMMIT: 86aefc6d97a27dcb0f7c0801c9edce099038752d
BUILDER: builder
LANE: full

## Summary
- `/work/[id]/decide?task=<id>` shows the exact version from `tasks[].decision`, claims on open with `expected_revision` and the CSRF header, and offers Approve vN / Return / Reject (note required for return and reject, max 2000).
- Done, stale (409 on claim or decide: no retry, one reload, replaced vs current side by side, "Review version n"), cannot-act (per `cannot_act_reason`) and error views are built; eligibility comes only from `you_can_act`.
- The contract is repointed to architecture v4. Decision types are added and the drift test regenerates from v4.
- The mock validates claim and decide bodies and serves the stale (W-1207 -> .next) and done (W-1201 -> .approve/.return/.reject) flows, with `POST /__mock/reset`. W-1201 to W-1208 fixtures are included.
- Round 1: the first build. The gate and the full e2e suite pass (63/63, 16 in decide.spec.ts).

## Changes
- `frontend/src/api/schema.d.ts`, `types.ts`, `client.ts`, `tests/api-schema-drift.test.ts`, `package.json`: contract regenerated from `architecture/packages/v4/openapi.json`; decision, claim and decide types.
- `frontend/src/app/work/[id]/decide/page.tsx`: the route.
- `frontend/src/features/decide/`: `useDecision.ts` (claim, decide, one write at a time, reload on 409 / uncertain effect), `DecideView.tsx` (state switch), `DecisionContent.tsx` (version, amount/Unknown, basis, recipient, changes, preparer, chain), `DecidePanel.tsx` (note and action bar), `DecideStates.tsx` (done, stale, cannot-act, not-open, errors), `format.ts`, `decide.css`.
- `frontend/mock/server.mjs`: claim/decide validation, revision and eligibility checks, sidecar swaps, `/__mock/reset`.
- `frontend/mock/fixtures/work/W-1201*.json` to `W-1208.json`: fixtures and sidecars, all `sample: true`.
- `frontend/tests/decide.test.tsx`, `frontend/tests/mock-decide.test.ts`, `frontend/e2e/decide.spec.ts`: component, mock and e2e coverage.

## Fixes
None (round 1).

## Departures
- **Mock checks the revision before eligibility (criterion 15 and 16).** In `frontend/mock/server.mjs:137-139` a wrong `expected_revision` returns 409 before the `you_can_act` check returns 403. Criterion 16 needs this: after approving T-1201 the task is `you_can_act: false`, and a repeat decide at revision 2 must answer 409, not 403. A claim or decide on T-1203/T-1204 at the right revision still returns 403 (tested). The backend (T-DECIDE) should confirm the same order.
- **SAMPLE DATA uses the shared `SampleLabel` only.** `DecisionContent.tsx` renders `@/shell/SampleLabel` when `item.sample`. The decide page has no tag of its own. When `fe-hide-sample-label` merges into the base, SAMPLE DATA will be hidden here too, as it is app-wide. The criterion 2 "SAMPLE DATA" text check will then follow that change, which is expected.

## Not built (for product acceptance and the backend developer)
- The payment-exception, CEO final costing and CTO emergency variants (FE-DECIDE-VARIANTS, gated on D-DECISION-VARIANTS).
- `revoke` (withdraw approval). The mock returns 422 for it.
- The comment box and "Add comment" on the not-yours board, and comments of any kind.
- The "DECISIONS / 1 OF 3" pager and "Next decision · 2 of 3" (PMO-0-4).
- What "return" does on each line (D-RETURN), plus SCR-08 document review and notifications.
- Board elements with no contract: "Preview: a newer version arrives", "waiting 2h", the agent "Drafted this from 3 sources" / "Redrafted it…" sentences, "You hold Finance on this project", and the board's not-yours title (`task.title` is used).
- Deliberately not built: a confirm dialog, automatic retry or auto-approving the newer version, optimistic facts, polling, client-side eligibility or chain derivation, showing `claimed_by`, keyboard shortcuts, and highlighting My work.

## Acceptance criteria
1. [x] Contract is v4: `grep -rn "v2-reviewed" frontend --exclude-dir=node_modules --exclude-dir=.next` prints nothing. The drift test and the unchanged `mock-contract.test.ts` pass in the gate. `git diff 25cd30e -- architecture` is empty (0 lines).
2. [x] Default view: `decide.test.tsx` "W-1201 shows only the decision values, the chain and the three controls". The e2e opens /work/W-1201/decide?task=T-1201 on 3401 with the mock on 3402 (decide.spec.ts axe default cases pass at 390 and 1440).
3. [x] Unknown never zero: "formats amounts … never shows unknown as zero" and "a decision with unknown: true and an amount string still shows Unknown".
4. [x] W-1208 omits To/Changed since, Step 3 of 3, two approvals in WAT: the test of the same name.
5. [x] Claim once with `{"expected_revision":2}` and `X-CSRFToken: mock-csrf-finance_lead`, also under StrictMode, with buttons disabled and "Getting this decision ready…": "claims once on open … also under StrictMode".
6. [x] Approve and done view: the component test "Approve sends one decide … then shows the done view". In the browser, e2e "done after approving W-1201" runs after `/__mock/reset`.
7. [x] Note rules: "Return or Reject without a note sends nothing and asks for one; a note is sent as typed" and "a note over 2000 characters is refused…".
8. [x] One write: "a double click sends one decide; while pending all three are disabled and Approve reads Approving…".
9. [x] Stale: the component test "a 409 on decide keeps the replaced version, reloads once and compares; Review claims the new revision" checks exactly one decide and `{"expected_revision":5}`. The e2e "stale flow on the mock" covers the same flow.
10. [x] 409 on claim: "a 409 on claim goes to the same stale view and sends no decide".
11. [x] Controls absent and GET only for W-1203 to W-1206: table-driven test in "cannot act (A-NOT-YOURS)".
12. [x] Cannot-act copy per reason, including `asked: []` -> "Nobody has been asked yet.": "copy follows cannot_act_reason, with who was asked" and the fallback test.
13. [x] Eligibility not from /me: "eligibility comes from the task, never from /me". `grep -rn "roles\|destinations" frontend/src/features/decide` finds only a comment in DecideView.tsx:4.
14. [x] Errors: the decide 403, 422, network error (one reload, no resend), item 404 / 401 (next set) / 500 (Try again) tests, plus the missing task, T-9999 and W-1001/T-2001 "This decision isn't open here" cases.
15. [x] Mock validation: `mock-decide.test.ts` "claim and decide validation" (5 tests, fresh `startMockServer({port:0})`, responses validated against v4).
16. [x] Mock stale and done flows: `mock-decide.test.ts` "stale and done flows" (T-1207 rev 4 -> 409 -> v3 at rev 5 -> 200; T-1201 approve -> ready + sidecar, repeat -> 409; reset -> 204; ANY-OTHER unchanged). See the departure on 409 before 403.
17. [x] Fixtures: "F-04 fixtures" iterates all 12 `W-12xx*.json` with strict Ajv2020 against v4 E-WORK-ITEM and checks `sample: true` and that `cannot_act_reason` appears only where `you_can_act` is false.
18. [x] Layout and a11y: `e2e/decide.spec.ts` gives axe-clean results at 390 and 1440 for default, done, stale, W-1203 and W-1204. At 390 the action bar is pinned with 44px targets and no sideways scroll. Tab order is Note, Approve, Return, Reject with a focus ring at both widths, and reduced motion means nothing animates.
19. [x] Gate: `bash delivery/checks.sh` exit 0.

## Validation
- `cd /Users/Hunchoo/psl-factory-worktrees/f-04 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh`: exit 0. The Django check passes, eslint has 0 warnings, typecheck is clean, vitest gives 9 files and 200 tests passed, and `next build` passes, including `/work/[id]/decide`.
- `cd frontend && E2E_PORT=3401 MOCK_PORT=3402 npm run test:e2e`: 63 passed (1.7m), including all 16 decide.spec.ts cases.
- `git push -u origin …fe-decide-decide-one-exact-version-approve-return`: the remote head is 8ebcd41. `git status --porcelain` is empty, `frontend/test-results` was removed, and the disk had 13 GB free afterwards.

## Blocked
None.


## Integration with the base (coordinator, 14 Nov 2026)
After the builder pushed 8ebcd41, the base gained PR #7 (SAMPLE DATA tag hidden) and PR #8 (My work rows match their work item fixtures). The coordinator merged the base in as a3797d0 (kept all three mock imports: ajv, ajv-formats, workList) and committed 86aefc6:
- My work's PM sample rows moved from W-1201..W-1205 to W-1301..W-1305, so the decision fixtures keep W-1201..W-1208 and PR #8's row-to-item guard test passes.
- tests/decide.test.tsx no longer expects the hidden SAMPLE DATA tag.
On 86aefc6: delivery/checks.sh exit 0 (vitest 311 passed; one run before had a transient ECONNRESET in mock-contract.test.ts that passed 3/3 on re-run and in the next full run), Playwright 78/78.
