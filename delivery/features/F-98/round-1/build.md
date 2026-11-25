STATUS: READY
COMMIT: 8ff62ea680c81796cf1d805bc188e745e85dc098
BUILDER: builder
LANE: full

## Summary
- The live work item now draws the RFP submission panel (panel key `bid-submission`, which every rfp-response item already lists). It reads the submission, the bid pack (`GET /bid-pack`) and the item's own review tasks: pack version, cover note, review state, reviewer's note, parts, file size, file checks and the server's words for problems, approval recorded, delivery status and receipt facts, and a link to the exact PDF.
- Writes: the PM's Send for review (`POST /bid-pack/review-request` {pack_id, version_id}), the reviewer's Approve, Return, Refuse on that exact pack (`POST /reviews`), and Send to the client (`POST /bid-submission`, 202). Each carries `expected_revision` and `case_revision`, goes through `useWorkCommand` and the shared locks, and is told from the re-read.
- F-96's Send for review is now enabled: the response panel also reads the bid pack and sends the same request with the pack and document version it gives. It stays disabled, with its reason, when there is no pack, the pack has no document version, it is decided, or it is already with the reviewer.
- No shared API changed. One registry line, types, CSS untouched; the mock got a new file.

## Changes
- `frontend/src/features/workspace/bidPack.ts` (new): reads the pack context (pack, item tasks, read result), finds the open `document_review` task this person may decide, and builds the send-for-review descriptor both panels use.
- `frontend/src/features/workspace/bidSubmissionAdapter.ts` (new): reads, summary sections, command descriptors (send, approve, return, reject, queue).
- `frontend/src/features/workspace/BidSubmissionActions.tsx` (new): PDF link, the review block with a note, Send for review, Send to the client.
- `frontend/src/features/workspace/bidAnswersAdapter.ts`, `BidAnswersActions.tsx`: read the pack beside the answers; the Send for review button uses the shared descriptor (was drawn disabled).
- `frontend/src/features/workspace/lines/index.ts`: registers the adapter (one line).
- `frontend/src/api/types.ts`: `LiveBidPack`, `LiveBidSubmission`.
- `frontend/mock/bid-pack-live.mjs` (new): live-shaped fixtures 4501 to 4509 (and a pack on 4401) with the reads and the three writes, tokens, a dropped answer and scenarios. `mock/work-live.mjs`: path allows `/bid-pack`, `/bid-pack/review-request`, `/bid-submission`; nine items; routing; reset. `mock/bid-answers-live.mjs`: `bidBump`. `node --check` passes on every mock file.
- `frontend/tests/next-config.test.ts`: allow-list entry `bid-pack-live.mjs` (one line; the mock carries the contract's `django_url` field).
- Tests: `frontend/tests/bid-submission.test.tsx` (19 new), `tests/bid-answers.test.tsx` (Send tests replaced, 20), `e2e/work-item-bid-submission.spec.ts`, `e2e/work-item-bid-answers.spec.ts` (held assertion updated).

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Bid-pack panel on the live work item: pack, versions, review state, what the reviewer sees, exact version under review: reads tests, Playwright "shows the pack". Only the current pack is served (no version list); the exact version is `document_version_id`.
2. [x] PM sends the pack for review with `pack_id` and `version_id`: test "sends the exact pack and version", e2e; re-read says "With the reviewer".
3. [x] Reviewer decides on that exact pack: `POST /reviews` {kind:'bid', subject:'document', target_id: document_version_id, role, verdict, evidence_id: null, note}; shown only when the item has an open `document_review` task with the server's `can_decide`; verdicts are the task's own.
4. [x] Response recorded as sent: the contract's step is `POST /bid-submission` (separate from approval, C-36); test and e2e check the body, 202, re-read shows Processing and the delivery as queued. "Sent" facts (time, receipts, on time) appear only from the server's `submission`.
5. [x] F-96's Send for review enabled through the pack: bid-answers tests "sends the pack and version the bid pack read gives" and "held ... no bid pack".
6. [x] Design parts the API cannot fill are not drawn (per-part checklist, history timeline, agent note, "open full pack (size)"): tests and e2e assert absent.

## Validation
- `tsc --noEmit` clean. `eslint . --max-warnings 0` clean.
- Full `vitest run` before the last fix: 190 files, 4411 tests, 1 failed (cash-forecast guard against `Number(` / `toFixed` in changed `src/features/workspace` files). Fixed (parseInt, Math.round), re-ran cash-forecast, bid-submission, bid-answers: 4 files, 94 passed. Named files `next-config`, `demo-mock`, `mock-contract`, `line-adapter`, `live-work-item`, `bid-answers`, `bid-submission`: 7 files, 442 passed.
- Playwright on the mock, ports 4980/4981, production build, desktop 1440 and phone 390: 20 passed, 1 skipped (the phone-only 44 by 44 test on desktop). Includes no sideways scroll and 44 by 44 targets on phone. The runner stopped its servers; nothing listens on 4980/4981. (A first run on the default ports 3101/3102 was started by mistake and killed by pid within seconds; only my own pids.)
- Live backend, read only (`psl_demo5`, PM user): work 1 and 9 (rfp-response, verified) list panels `bid-answers, bid-pricing, bid-submission, bid-outcomes, security-estimate` and no bid-pack panel; `GET /bid-pack` and `/bid-pack/portal-receipt` answer 404 (no pack in the seed); `GET /bid-submission` returns `file: null`, `route: internal_recipient_inbox`, `job_status: confirmed`, `approval_recorded: true`, a `submission` with receipt ids. No live pack exists to read, so the pack body and the writes were checked against the Django source (`apps/core/factory_api/commands.py`, `reviews.py`, `apps/workflows/factory_rfp_submission_pack.py`, `factory_rfp_views.py`), not run.
- Fidelity tool: not run. No board for this live panel (the board's per-part checklist, timeline and agent note are not served). For the design engineer.

## Blocked
Nothing blocks the PR. Held or different from the map, each by contract:
- **Reviews kind.** The prompt and OpenAPI list a `document` variant, but the server's `reviews` handler answers 404 for kind `document` on an rfp-response item (`DOCUMENTS` has no rfp line); only kind `bid`, subject `document` reaches the pack review (as backend answer C-39 says). Built on `bid`/`document`. The `role` field is required; it is sent as the open review task's own `role` (ignored by the server for a document, which keeps only the version, verdict and note). Backend: the contract's `document` variant does not fit this line.
- **Who may act.** `bid-pack` and `bid-submission` carry no `can_*` flags. The reviewer's controls follow the item's `document_review` task `can_decide` and `verdicts`. For the PM's Send for review and Send to the client no flag exists, so they are offered by state only (an undecided pack with a prepared version and no open review; an approval recorded with no submission and a clean file) and the server's 403 is shown if the person may not. Backend: a `can_send` / `can_submit` flag would let us hide them.
- **Edit the pack** (`POST /bid-pack`, needs `response_id`, `base_pack_id`, file rules): not drawn; the response id is not on this panel and the file-rule inputs are undesigned. After a Return the PM has no edit here.
- **Record a portal receipt** (`POST /bid-pack/portal-receipt`, needs a proof picked from a list and an attestation the contract does not word): not drawn, and the portal-receipt read (404 on internal routes) is not read.
- A note is required client side for Return and Refuse (as F-89); the contract does not say it is, the server answers if it differs.
- The pack read serves only the current pack, so no version list; there is no `django_url` use.
- For the coordinator: `useWorkCommand`/line `ctx` carry no work item `tasks`, so adapters needing them read `GET /work/{id}` themselves (one extra read per panel read). A `tasks` field on `LineContext` would remove it.
