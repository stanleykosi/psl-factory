DECISION: READY
RISK: low
SURFACES: ui, api
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Part 1 only (reads): SCR-30 issue detail shows a live project issue, read-only. Writes are F-111B.
- Scope and data are settled by backend answers D-2, D-3 and D-4 (API 1.24.0). No client question blocks it.
- Wait: the builder starts only after F-85 (PR #101, shared line adapter) is on main. This delays the build start and is not a readiness blocker. Write the spec against `/Users/Hunchoo/psl-factory-main/delivery/features/F-85/spec.md`.
- Architecture and design approval are covered by the v9 package and the 13 Nov client approval (with the D-173/D-181 exceptions in `design/review.json`).
- Fits one PR: four reads and one adapter mapping.

## Scope
Outcome: the issue workspace shows a live project issue in its overdue, no-owner and verified states. Task FE-CONNECT-1, screen SCR-30.

In (reads only):
- `GET /work/{id}/issue-followup`
- `GET /projects/{case}/issues/{id}`
- `GET /projects/{case}/issues/{id}/messages`
- `GET /work/{id}/history`
- Header: reference, title, severity, status (mapped to Open, In Progress, Resolved, Closed) and owner.
- Raised date and age (D-2).
- The "what has happened" timeline, taken from the issue detail's bounded timeline (D-3).
- Chasing and timing.
- No-owner and overdue banners.
- Blocked-milestone link (D-2).
- Allowed actions come from the line read (DC-5). Write controls render only as disabled or hidden, according to F-85, and do nothing until F-111B.

Out:
- All writes, which belong to F-111B: owner update, owner reply, set owner, message owner, refresh/restart. The reply rule in D-4 is F-111B's.
- The escalation raise flow (SCR-50) and the SCR-31 change request.
- Any change to `frontend/src/features/workspace`. A needed frame change is a dependency on lane C.

Rules:
- Hide what the API does not supply and say so (D-182, D-185). That covers Tola's note and story (DC-3) and the "FIX IN TESTING" wording.
- Unknown values are never shown as zero.
- Do not invent evidence ids, owners or dates.
- Lane D owns only the issue adapter mapping, in its own feature folder.

## Risk
Low. This is read-only, internal and routine, and it moves no money, touches no identity or payroll data and sends no messages. It is mapped onto an existing shared adapter, so the contract is reused and not changed. It can merge under D-180/D-184. The spec stage should confirm that the SCR-30 boards match the approved design and that `design.py check` passes. I did not re-verify this.
