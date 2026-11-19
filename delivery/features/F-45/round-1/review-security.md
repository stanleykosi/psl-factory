VERDICT: PASS
COMMIT: af1d1c8d3629b577c4baeebb4eae025c6a511397
REVIEWER: reviewer-security
AUTHORITY: delivery security review

## Summary
- The page only shows controls when `tasks[].you_can_act`, `disabled_reason` and the steps sent by the backend allow it. The diff adds no `/me`, role-name, `prepared_by` or observer rule.
- The observer and the reviewer are kept apart on the page. After recording, the observer's re-read sends `you_can_act: false` with the reason `prepared_by_you`, and nothing on the page suggests they can review. Enforcing this for real is a backend job (BACKEND-HANDOFF, G-58-4).
- The proof upload goes to the item's own `case_id` (C-LED-0052) with the kind the step names (`ledger_observation`). The browser cannot point it at another case or kind.
- The writes carry the CSRF token. The step write has an idempotency key. The decide write relies on the claim plus `expected_revision` (handed to the backend).
- 403 and 404 look the same. The holds (W-4205, W-4209) show no control and no reviewer. There are no amounts, no secrets and no outside calls.

## Findings
None.

## Verified
- Authority: `InlineDecide.tsx:132` `canAct = task?.you_can_act === true && claim !== null`. The claim is sent only when the task can be acted on: W-4206 and W-4207 send no claim (tests/ledger-source.test.tsx:348). The diff under `frontend/src` (InlineDecide, Workspace, WorkItemOverview, labels, css) adds no rule based on role, person or text. `LEDGER_LINE` is used only to place notices and the exceptions link, never to grant anything.
- Segregation: fixture matrix checked. In W-4202.next and W-4213.next, T-* has `you_can_act: false` with `prepared_by_you`. W-4206 is `prepared_by_you` and W-4207 is `not_your_role`; neither gets a button. W-4210 is the capturer with `disabled_reason`, so its step is inert. Only W-4203 and W-4212 can act. The "independent reviewer" sentence and the decision basis are text the backend sends; the page does not apply them.
- Proof upload: `Workspace.tsx:362` passes `caseId={item.case_id}` and the kind comes from `field.evidence_kind` (`StepForm.tsx:124-131`). All 13 fixtures use `case_id` C-LED-0052. `response.mjs` is unchanged and still checks CSRF, persona `none` (403), the case (404), the kind (422), the revision (409) and the grant.
- CSRF and idempotency: the step goes through the existing `useWorkspaceStep`/`stepRequest` (X-CSRFToken, UUID `idempotency_key`; a double press sends one request, per the tests). The decide goes through `useDecision` (CSRF, `expected_revision`). W-4213 replays with the same key in the mock test.
- 403 and 404 read the same, and persona `none` makes no further call (tests/ledger-source.test.tsx:828-847). On a 403, the decide and step writes show read-only copy and say nothing was approved.
- Holds: W-4205 (`setup_needed`) and W-4209 (`waiting`) have no steps and no tasks. The tests check that neither "Ada Okafor" nor "Ledger reviewer" appears and that zero POSTs are sent.
- Exposure: a grep of the W-42* fixtures finds no `@`, URLs, token, secret, password, ₦/NGN or digit-group amounts. The only link is `/assistant`. The new stale notice shows the user's own note as React text (no `dangerouslySetInnerHTML` in workspace or work-item). No new dependencies.
- Retest: `npx vitest run tests/ledger-source.test.tsx tests/ledger-source-mock.test.ts` at 4dba97ab passed (2 files, 65 tests).

## Notes
- Non-blocking, existing before this change (F-31): the mock's upload grant (`response.mjs:127-135`, `stepEvidence(item).length > 0`) is broader than real authorisation. It ignores `disabled_reason`, so the capturer (W-4210) or a held item on the same case could upload proof on the mock. Because every F-45 fixture shares C-LED-0052, any one item's step grants upload for the whole case. BACKEND-HANDOFF already asks the backend to allow the upload only for people who may take the step, and to check that every `evidence_ids` entry belongs to this item's case. Keep that in the backend acceptance.
- Backend, already handed off: the three separate people must be enforced in E-WORK-STEP and in E-TASK-CLAIM/E-TASK-DECIDE. A decide at the same revision must be refused with 409 and never applied twice, because E-TASK-DECIDE has no idempotency key. The claim-on-load lock and its release are open questions.
