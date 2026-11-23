DECISION: READY
RISK: medium
SURFACES: ui, api, auth, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Part 2 of SCR-55 (the 8 remaining of 14 boards: register-review, date-review, schedule-review, returned) adds the write side to the read-only panels F-102 builds. It is one outcome and fits one PR.
- Build start waits on F-102 (merged panels), F-85 (adapter) and F-87 (`Actions` slot and `useWorkCommand`). These are build-start waits, not blockers. The spec is written against their specs.
- E-23 (basis review) and E-24 (accounting-note link) are answered. D-187 accepted every recommended option in the F-102 specs. No client decision is open.
- Contract is API 1.25.0 or later (the lane-d worktree). The data and the writes exist, so the screen is built from what the boards draw.
- Risk is medium: finance review decisions with per-record authority and multipart uploads. Nothing moves money or posts to the ledger.

## Scope
Outcome: on line `fixed_assets` (W-3901..W-3912, task FE-CONNECT-1), a finance person records the register, date and schedule reviews, answers a return, and corrects the register and dates. This is done through a `FixedAssetsActions.tsx` registered as the line adapter's `Actions` slot (F-87 shape `LineActionsProps`). It is sent through `useWorkCommand`. It does not touch `frontend/src/features/workspace`. The panels from F-102 are not rebuilt.

In:
- Reviews: `POST /work/{id}/reviews` with `kind`, `target_id`, `purpose` register, basis or schedule, `verdict` approve, return, reject or revoke, `evidence_id`, `note`. Offer only what `review_options` lists, with its `target_id` and verdicts. The basis review (E-23) is offered only when listed. Evidence is chosen from `review_evidence[]` with nothing preselected, and the button stays off when the list is empty. No evidence id is invented.
- Capture a register: `POST /projects/{case_id}/asset-registers` (`case_revision`, `reference`, `evidence_id`).
- Record dates with proof: `POST .../asset-registers/{register_id}/dates`, multipart (`case_revision`, `evidence_id`, `asset_id`, `delivery_date`, `in_service_date`, `fraction_basis`, `file`). The file is a checked PDF, uploaded through this action's own field.
- Returned board: `POST /work/{id}/assets/opening-proof`, multipart (`expected_revision`, `case_revision`, `target_id`, `review_id` from `opening_return`, `reason`, `file`).
- States: success, 409 (re-read and say the case changed), 422 `fields[].message`, 403 `csrf_failed` (refresh the session, press again), 403 other or 404 ("This record is unavailable."), 429, 503 and network ("Try again shortly"). Writes carry an idempotency key per attempt. Do not pass revision tokens or the key inside `inputs` to `makeCommand` until TECH-1-1 lands.
- The independent-reviewer hold is shown as the server returns it. The client never decides authority.

Out:
- Anything in F-102's read scope, and any change to the shared workspace frame (a needed change is a named dependency on lane C).
- Ledger posting, client-side sums or depreciation, and exporting the schedule.
- Parts the API does not supply, hidden per D-182 and listed in the PR: "Chidi never reads asset values", the accounting-note text, the phone short money form, the review dates, and "Feeds MANAGEMENT ACCOUNTS".
- Backend, migrations and contract edits.

Rules: unknown money stays unknown, never 0. No invented approvers or rules. Any change to `frontend/mock/finance*` is named in build.md for lane B. Lane D merges origin/main first (API 1.26.0, after the F-68 hotfix).

Open questions for the spec to carry to the batch (presentation only, recommendation first): (1) the review form shows the basis review as a third choice beside register and schedule, listed only when `review_options` has it; (2) one shared evidence picker for all three reviews; (3) phone shows the same forms in one column, as in F-102.

## Risk
Medium. `POST /work/{id}/reviews` records approval decisions under per-record, independent-reviewer authority (`auth`), and three writes are multipart uploads. The basis review is a new flow (product acceptance required) on a contract that changes the review shape (`contract-change`). It moves no money, does not post to the ledger (`ledger_posted` is read-only) and has no restricted payroll data. The decisions are reversible by return or revoke, so it is not high. Under D-180/D-184 it merges routinely, but reviewers should check the authority handling and the upload checks.
