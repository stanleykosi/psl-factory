DECISION: NOT-READY
RISK: medium
SURFACES: ui, api, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- SCR-30 issue detail is a sound outcome, but it depends on the shared line adapter F-85 (PR #101). F-85 is IMPLEMENTING and not merged, so the dependency gate fails.
- Backend answers D-2, D-3 and D-4 and the proof answers (section 1) settle the open questions, so no client question blocks it. Once F-85 merges it can be re-rated READY.
- As mapped, the feature is too big for one PR (effort L: four separate commands plus a timeline assembled from several reads). Split it.
- Lane D owns only the issue adapter mapping and must not change the shared frame in `frontend/src/features/workspace`.

## Scope
Outcome: the issue workspace reads and updates a live project issue (overdue, no-owner and verified states). Task FE-CONNECT-1.

Dependency: F-85 merged to main (shared frame). Any frame change is a dependency on lane C.

Split, to be binding once unblocked:
- F-111a (reads): `GET /work/{id}/issue-followup`, `GET /projects/{case}/issues/{id}`, `GET .../issues/{id}/messages` and `GET /work/{id}/history`. This covers the header (reference, title, severity, status, owner), raised date and age (D-2), the "what has happened" timeline from the issue detail's bounded timeline (D-3), chasing and timing, and the no-owner and overdue banners. It also covers the blocked-milestone link (D-2).
- F-111b (writes): owner update (`POST /work/{id}/issue-followup`), owner reply, set owner (`POST .../issues/{id}/assignment`), message owner, and refresh/restart. For a reply, use `issue-followup` with `team_reply` only when answering the exact work task. Use `.../team-replies` for an independently captured reply, and never submit both for one reply (D-4).

Rules:
- Send both `expected_revision` and `case_revision` on writes (DC-1).
- Per the D-185 and D-182 rules, hide what the API does not supply and say so: Tola's note and story (DC-3) and the "FIX IN TESTING" wording. Map status to Open, In Progress, Resolved and Closed.
- Proof: an eligible PMO Lead's signed-in approval counts as the record. Other staff attach a checked file, as in section 1 of the 23 Nov answers. Do not invent evidence ids.
- Allowed actions come from the line read (DC-5), not from a guess.
- Out of scope: the escalation raise flow (SCR-50), the SCR-31 change request, and any frame change.

## Risk
Medium. The shared-adapter contract and several new required fields (proof, channel, source reference, `case_revision`) cross layers, and owner messages are external-facing. Nothing here moves money or touches identity, and the reads are routine. The message-release action is an external-messaging surface, so it needs a note at the merge route if F-111b includes it. I could not confirm design approval or architecture approval status in this pass. The spec stage should check that the SCR-30 boards are client-approved and that `design.py check` passes.
