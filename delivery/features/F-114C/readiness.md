DECISION: READY
RISK: high
SURFACES: ui, api, auth, external-messaging
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- READY as part 3 of SCR-45 (task FE-DELIVERY-RELEASE): the reviewer records an independent verdict on the exact go-live document version through `POST /work/{id}/reviews` with `kind: document`. Part 3 is one operation, so it fits one PR.
- API 1.25.0 contract (lane-d worktree) defines the request: `{kind:"document", expected_revision, case_revision, version_id, verdict approve|return|reject, note (max 4000)}`. The response is `{work_id, state, revision, review_id}`. No evidence id is needed, so the PSL proof rule has nothing to add.
- Build-start waits (not blockers): F-114 (owns the page `/work/{id}/go-live` and the mock), F-85 (shared frame) and F-87 (`Actions` slot and `useWorkCommand`). The coordinator holds the builder until all three are on main. F-114B touches the same page, so this feature depends on F-114 only and must not edit F-114B's files.
- High risk: an approval releases a client-facing go-live document (the system sends it afterwards), and it is a reviewer decision with independence rules. The merge goes to the design engineer's batch.

## Scope
Outcome: the person the server authorises reviews the go-live document version on the go-live page and the verdict is recorded.

In:
- `POST /work/{id}/reviews` with `kind: "document"` only. Offer approve, return and reject. `note` is required by the contract (string, 0 to 4000), but the spec writer should require plain text for return and reject. Do not invent that rule for approve; the API's 422 text shows if it needs one.
- `version_id`, `expected_revision` and `case_revision` come from the reads the spec writer confirms. The `go-live-signoff` read gives `version_id`, but only the appointed PM can read it, and the reviewer may be someone else. The spec writer must check `GET /work/{id}` `tasks[]` (the document review task) for the version and revisions. If the reviewer cannot get `version_id` from any read they can call, hold the write and list it. Never type the id.
- Show the review control only when the work item's read supplies the review task or action for this caller (DC-5). Never decide access from the person's role in the client.
- Show the document version under review and the result after the write (`review_id`, refreshed state). Nothing is sent to the client from this page.
- Mock fixtures and tests: reviewable, not the reviewer, approve, return, reject, 409, and a 404 that reads "This record is unavailable.".
- Form wiring uses F-87's `Actions` slot and `useWorkCommand`, in its own `GoLiveReviewActions.tsx`. Same error words, no double submit and refetch after 2xx as F-114.

Out:
- The sign-off, replies, decline, successor and milestone (F-114, F-114B).
- Other `reviews` kinds (`bid`, `schedule` and so on) and `POST /work/{id}/corrections`.
- Publishing or sending the document (system-reserved, not a person's action).
- Agent steps and Tola wording (D-182). Hide any board part the reads do not supply and say so in build.md.

## Risk
High. A document approval is a recorded independent decision that lets the go-live document go to the client, and it is hard to undo. The server enforces who may review and independence (`apps/core/factory_api` reviews, `backend-answers.md` C-5 and C-29 for the `reviews` pattern), so auth and external-messaging are surfaces along with ui and api. Product acceptance is required because the reviewer flow and its wording are new and client-visible. The `version_id` source for a non-PM reviewer is the one open detail, and the spec writer settles it from the work read.
