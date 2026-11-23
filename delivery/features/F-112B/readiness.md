DECISION: READY
RISK: high
SURFACES: ui, api, auth, external-messaging, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Part 2 of SCR-31 (FE-CHANGE): the 8 boards notice, execution, go-live-note and closed, desktop and mobile. This matches the board split in the F-112 spec ("Boards: part 1 and F-112B"), which is binding.
- It covers the notice and go-live note document reviews, the four execution evidence steps, close with PM and client signatures, retry and cancel, and restart.
- The data is settled. D-6 gives the stage codes and D-7 says how a PM records a client signature without a client login. D-5 is carried from part 1. D-187 accepted the recommended options in the part 1 specs. The contract has `document_review`, `execution`, `close` (modes `signed` and `owner_applicability`), `operate_delivery` and `restart` on `POST /work/{id}/change`. I read them in the lane-d worktree contract (API 1.25.0 or later).
- Build-start waits, which do not block readiness: F-112 (the adapter, stage track and read), F-85 (PR #101) and F-87 (the `Actions` slot). The spec is written against the F-112 spec and F-85's spec.
- Not checked: I did not open the design boards or run `design.py check`. I relied on the 13 Nov approval and the D-173/D-181 exceptions from the lane context. The spec writer must check each board against the contract and hide whatever the API does not supply (D-182).

## Scope
Task FE-CHANGE, part 2. It extends the F-112 `pmo-change/v1` adapter in its own `XxxActions.tsx` form (F-87 shape). The shared frame in `frontend/src/features/workspace` stays unchanged. A frame change is a dependency on lane C.

In scope, with the 8 boards `SCR-31-<desktop|mobile>-{notice,execution,go-live-note,closed}`:
- Stages `notice` (step 2), `execution` (3), `go_live` (4) and `signatures`/`complete` (5), using the F-112 stage mapper. These steps were only drawn in part 1, and they become actionable here.
- Notice and go-live note review: `document_review` `{version_id, verdict approve/return/reject, note}`, with the version taken from `documents[]`. Also show `jobs[]` status and receipts as the read serves them.
- Execution evidence: `execution` `{kind plan_updated/implemented/testing_validated/documentation_updated, evidence, note, scope_items, dossier_id, candidate_id}`. The four typed steps are shown, and `evidence` is chosen from `evidence[]`.
- Close: `close` `{receipt_id, pm_signature_id, client_signature_id|null, note, operation_key, mode signed|owner_applicability, pm_signature{...}, client_signature{...}|null}`. Per D-7 the source fields come from the retained proof: source system, reference, decision id and version, signer and signed time. Use the proof-upload and evidence rules in lane context (checked signed PDF for the exact receipt and signer role; otherwise choose from the evidence list, with nothing preselected). The `can_close` and `closure_id` values come from the read.
- `operate_delivery` `{job_id, operation cancel/retry, reason}` on a job from `jobs[]`, and `restart` `{reason}` when `can_restart`.
- The linked read `GET /projects/{case_id}/change-versions/{version_id}` and the `change-milestone-link` call, only where a board draws what they return. If a board draws it and the API does not supply it, hide it and say so.
- Every write sends `expected_revision`, `case_revision` and `change_version_id`, handles 201 and 409, and uses `operation_key` (uuid) for `close`. Controls come from the line read, not the client role. A control that needs an evidence id is off when the list is empty.

Out of scope, and carried from F-112:
- Part 1 screens: the log, assess, decide and authorise forms.
- Showing "Authorised by", agent cards and their cited records (DC-3), names beside signers that the read does not carry, and any "milestone scope now includes" line. Hide them.
- Any deployment. `deployment_authorized` stays false, and the page never says a deployment is authorised.
- Any invented signer, source id, attempt count or date. Unknown money and effort stay unknown, never 0.

## Risk
High. `close` records PM and client signatures, including `owner_applicability`, which waives the client signature. `restart`, `retry` and `cancel` change a change request's life and are hard to undo. They are revision-gated and role-gated by the read (`can_close`, `can_restart`, `jobs[]`). The notice and go-live note documents go to the client (external-messaging) and need reviewing before they are sent, so the screen must not imply anything was sent unless `jobs[]` or a receipt says so. The change also touches auth (role-gated actions) and product-decision (D-7 signature rules). It is a new flow, so product acceptance is required. The merge goes to the design engineer's batch.
