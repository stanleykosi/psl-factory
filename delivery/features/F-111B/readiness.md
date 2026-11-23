DECISION: READY
RISK: high
SURFACES: ui, api, external-messaging
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Part 2 of SCR-30: the issue writes on top of F-111's read-only adapter. They are owner update, owner reply, set owner, message owner and refresh/restart. Task FE-CONNECT-1.
- Scope and data are settled by the live contract (API 1.25.0 or later) and backend answer D-4. D-187 accepted every recommended option in the F-111 specs, so the hidden Tola note and the four live status words carry over.
- Build-start waits, not blockers: F-111 (part 1 must merge), F-85 (shared adapter, PR #101) and F-87 (the `Actions` slot and `useWorkCommand`). Write the spec against those specs.
- High risk because "message owner" releases an external message and "set owner" assigns responsibility. The merge goes to the design engineer's merge batch.
- Architecture and design approval are covered by the v9 package and the 13 Nov client approval (with the D-173/D-181 exceptions in `design/review.json`). I did not re-run `design.py check` in this pass, so the spec stage should do it.

## Scope
Outcome: from `/work/{id}` for a `pmo-issues/v1` item, a permitted person records an owner update or reply, sets an owner, and prepares, reviews and releases the owner message. The page then shows the recorded result from the server.

In:
- Owner update: `POST /work/{id}/issue-followup`.
- Owner reply: use `issue-followup` with `team_reply` only when answering the exact work task. Use `POST /projects/{case}/issues/{id}/team-replies` for an independently captured reply. Never submit both for one reply (D-4).
- Set owner: `POST /projects/{case}/issues/{id}/assignment`. The owner choices come from `GET /projects/{case}/issues` `owners[]`, which part 1 left out.
- Message owner: the single `POST .../issues/{id}/messages` (`issue_communications_command`). It covers prepare, edit, review, release, check, reconcile and recover. Offer only the steps the messages read allows. Reconcile an uncertain send before any retry.
- Refresh and restart of the follow-up, as the line read allows.
- Form file: `IssueFollowupActions.tsx`, registered as the adapter's `Actions` slot once F-87 is on main. Forms send through `useWorkCommand`. Do not touch `frontend/src/features/workspace`.
- Controls: enabled only when the line read's flags allow them (`can_request_update`, `team.can_record`, `team.can_resolve`, `response_task`). Hidden when the flag is false.

Rules:
- Send `expected_revision` and `case_revision` on every write (DC-1). Never default them to 0. Until TECH-1-1 lands, never put revision tokens or the idempotency key inside `inputs` to `makeCommand`.
- Proof: use the action's own upload field or proof endpoint. Otherwise the person chooses from the evidence list the read supplies, with nothing preselected and the button off when the list is empty. Never invent an evidence id.
- Do not invent owners, attempt counts or channels. Where the API does not supply a part a board draws, hide it and say so (D-182).
- Message release goes out only through the server's review and release steps. Model or agent text cannot release it.

Out:
- The part 1 reads (F-111).
- SCR-50 escalation raise flow and SCR-31 change request.
- Tola's note and story (DC-3).
- Any frame change. A needed frame change is a named dependency on lane C.

Sizing: this is large but it is one outcome on one screen. The message lifecycle is the biggest piece. If the spec finds more than about 8 boards or more than one reviewable PR, split the message-owner lifecycle into a further part. Do not do that now.

## Risk
High. `issue_communications_command` releases an external message (external-messaging) and `assignment` changes who is accountable, with concurrency through `expected_revision` and `case_revision` and uncertain-send recovery (`apps/core/factory_api`, `contracts/psl-factory.openapi.json` around lines 46390 to 47245). It moves no money and touches no payroll or identity data. It needs UI review, a security review for the permission and idempotency handling, and the design engineer's merge batch.
