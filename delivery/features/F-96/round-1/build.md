STATUS: READY
COMMIT: bd15ed6913b1715b844dee087912c7f49afaf6bb
BUILDER: builder
LANE: full

## Summary
- The live work item now draws the RFP response panel (panel key `bid-answers`, `GET /work/{id}/bid-answers`) through a new line adapter: summary counts, the Engineering Lead's review, and one row per requirement with its disposition, status, saved answer, Tola's suggestion and its source.
- Review decisions work: Accept, Edit and Write your own (`action:"review"`, one decision per press), Ask Tola (`action:"suggest"`, with an earlier winning answer when picked) and Undo (`action:"undo"`). Each carries `expected_revision`, `case_revision` and, for suggest, a fresh `operation_key` per requirement. The page re-reads after each write and says what the item now is.
- Controls follow the server's flags only (`can_write`, per-row `can_review`, `can_undo`). Shared write locks and error handling come from `useWorkCommand`; no shared API changed.
- Held: Send for review (see Blocked/Held below), a Reject verdict, and the design parts the live API does not serve.

## Changes
- `frontend/src/features/workspace/bidAnswersAdapter.ts` (new): reads the panel, builds the summary sections, describes the commands (review, undo, one suggest per requirement).
- `frontend/src/features/workspace/BidAnswersActions.tsx` (new): the requirement rows and their controls, in the adapter's `Actions` slot.
- `frontend/src/features/workspace/lines/index.ts`: one line registers the adapter.
- `frontend/src/api/types.ts`: `LiveBidAnswers`, `LiveBidAnswerRow`.
- `frontend/src/features/workspace/workspace.css`: `.bid-*` rules (list, row, quote, form), only for this panel.
- `frontend/mock/bid-answers-live.mjs` (new): live-shaped fixtures 4401 to 4404 and the read and write rules (token check, predecessor, operation-key idempotency, undo re-opens the suggestion). `frontend/mock/work-live.mjs`: path allows `/bid-answers`, four work item fixtures, routing, reset. `node --check` passes on both. No allow-list change needed (the `django_url` field lives in work-live.mjs, already allowed).
- Tests: `frontend/tests/bid-answers.test.tsx` (19), `frontend/e2e/work-item-bid-answers.spec.ts` (6 per viewport).
- No shared file changed except the one registry line, the type aliases and CSS above.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Requirement rows show key, response, disposition and status (addressed, needs clarification, out of scope; current, queued, running, held, suggested, reviewed, stale): panel tests and Playwright rows test.
2. [x] Tola's suggestion with its source and prior reusable answers; `can_write`, `can_review`, `can_undo` drive the controls: tests "who sees which control", "offers the earlier winning answers".
3. [x] Review (accept, edit, replace), suggest and undo send the exact bodies; re-read told after the write; 409, 422, 403 and a dropped answer handled (locked until the page moves): tests "review decisions", "ask Tola", "when a write goes wrong".
4. [x] Design parts the API does not serve are not drawn (filters, progress figures, "before review" checklist, add requirement): tests assert none appear.
5. [ ] Send for review: held, see below.

## Validation
- `tsc --noEmit`: clean. `eslint . --max-warnings 0`: clean.
- `vitest run` (all): 186 files, 4326 tests passed. Named files `next-config`, `demo-mock`, `mock-contract`, `line-adapter`, `live-work-item`, `bid-answers`: 6 files, 435 tests passed.
- Playwright on the mock, ports 4980 (app) and 4981 (mock), desktop 1440 and phone 390: 11 passed (includes 44 by 44 tap targets on phone, no sideways scroll). The runner started and stopped both servers; nothing is left listening.
- Live backend read-only check (`psl_demo5`, GET only, as the PM user): work 1 and 9 return the panel with the fields above (`position`, `source`, `citation`, `counts`, `response_review`, `next_page`). Their `can_write` is false and they have one addressed row, so writes were checked against the Django source (`apps/core/factory_api/bid_responses.py`, `apps/pmo/rfp_answers.py`), not run.
- Fidelity tool: not run. SCR-26 has no board for this live panel; the live API cannot fill the board's table (see below), so no coverage claim is made. For the design engineer.

## Blocked
Nothing blocks the PR. These are held, each by contract:
- **Send for review.** `POST /reviews` kind `bid` records a reviewer's verdict (`approve`, `return`, `reject`) on a response, commercial or document subject; it is not the PM's send. The PM's send is the separate `POST /work/{id}/bid-pack/review-request` ({pack_id, version_id}), which the bid-answers read does not carry, and the bid pack is not a panel this item lists (it lists bid-pricing, bid-submission, bid-outcomes, security-estimate). The button is drawn disabled with its reason. Needs a decision from the coordinator: build the pack panel (a pack read gives `pack_id` and `document_version_id`), or have the backend add the ids to this panel. This differs from the connection map, which pointed at `reviews`.
- **Reject.** The review verdicts in the contract are `accept`, `edit` and `replace` only. "Write your own" is `replace`. There is no refusal, so none is drawn.
- **Not served, not drawn:** filters, progress bar, "before review" checklist, add a requirement (C-22: fixed by the reviewed source analysis), tab bar. Counts are drawn from `counts` (requirements, with an answer, needing clarification, reviewed, not shown to you).
- **Beyond the task's list, now served and drawn:** the live read carries `citation` (wording, page) and `source`; shown when present. Paging: the panel reads without `page` (up to 100 rows) and shows "Listed below" when fewer rows than the total come back.
- **Clarification rows** show their disposition only; the send and answer record for client clarifications (C-25) is a separate read and write, not built here.
- Engineering return reason is shown from `response_review`; the return-to-PM flow beyond that is not built.

For the coordinator: nothing shared was changed. `useWorkCommand` locks per command id, so one suggest descriptor per requirement is used; a shared per-key idempotency helper would remove that if more lines need it.
