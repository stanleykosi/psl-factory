VERDICT: PASS
COMMIT: ff48d19d80a904de760cf524166ad820107267dd
REVIEWER: pmo-acceptance
AUTHORITY: PMO acceptance

## Summary
- F-17 (FE-WORKSPACE-FRAME) is accepted for delivery on the contract mock at ff48d19. Round 5 was extended by D-66/D-67, a recorded continuation approved by the design engineer, to fix QA-5-1 and QA-5-5. Both are VERIFIED by integrated QA on this head.
- Every blocking finding is VERIFIED, or ACCEPTED_RISK with a named authority. FID-1-1 (region scores below 85) is accepted by the design engineer under D-65, 15 Nov. Technical and security reviews are lean PASS at ff48d19. UI and UX are lean PASS at earlier round-5 heads, and QA covered the later lock and padding diff at ff48d19.
- Scope held: one task (FE-WORKSPACE-FRAME), no line screen, no operation IDs. No backend, OpenAPI or architecture change landed. The base merge brought in F-18 and kept both sides.
- This is delivery acceptance only. D-LINE-WORKSPACE is still a proposal, so nothing real is sent and there is no real backend. Product acceptance is not required (readiness). Merge and release keep their own authorities.
- The backend hand-off items are listed below. Duplicate-send protection is proven on the frontend lock and the mock only.

## Findings
- PMO-5-1 | non-blocking | low | pmo | The backend items are spread across round-1/build.md (Contract proposals), round-2/build.md and round-2/review-ui.md. The round-5 build.md has no consolidated list. Copy the list under "Hand-off to backend" below into the PR description and the hand-off note, so the items travel with the merge.
- PMO-5-2 | non-blocking | low | pmo | feature.json state lag. TECH-5-1 reads OPEN although review-technical.md verifies it at ff48d19. UX-2-1, UX-2-2 and UI-2-8 read FIX_SUBMITTED. TECH-1-4, TECH-2-2, QA-5-3, QA-5-4 and TECH-5-2 are non-blocking and OPEN. None blocks. Sync the record before the merge. TECH-1-4 and TECH-2-2 are backend dependent and must stay open.
- PMO-5-3 | non-blocking | low | frontend | QA-5-3 (the uncertain callout sits below the fold on a phone after the press) and QA-5-4 (the over-long note message shows twice) are carried forward untouched. Fix in a later pass or in the first line task.

## Verified
- Acceptance criteria | verified | The 29 criteria in feature.json are covered. Checks gate: round 5 exit 0 (checks.md). After the base merge: `delivery/checks.sh` exit 0 and the full Playwright suite 405 passed at ff48d19 (build.md). QA ran 126 of 126 on the workspace, work-item, decide, response and rfp specs, plus hit-tested touch taps at 390, 320 and 1440 (review-qa.md).
- QA-5-1, QA-5-5 | verified | review-qa.md. "Record and continue" is reachable in every case. After a reload the steps stay locked, and the mock log shows one `approve_send`. TECH-5-1 is fixed in the same way (review-technical.md). Security confirms `submit()` is the only send path and the lock comes from `item.reconcile`, not from the viewer's permissions.
- Task and scope | verified | One task, FE-WORKSPACE-FRAME, matches readiness. The build touches records and frontend only, with no `src/api`, `apps` or `architecture` change (criterion 27, build.md rounds 1 to 5).
- Blocking findings | verified | FID-1-1 ACCEPTED_RISK (design engineer, D-65). UX-1-1, UI-2-1 to UI-2-7, UI-3-1 and QA-5-1, QA-5-5 are VERIFIED in feature.json. No blocking finding is open.
- Design | verified | The design gate is APPROVED. The frame has no board of its own. It was signed off at measured region scores (D-59, D-62, D-63, D-65), and `fidelity-exceptions.json` now carries "design engineer, 15 Nov (D-65)".
- Overclaim check | verified | build.md (rounds 1 and 2) states the D-LINE-WORKSPACE limits (contract mock only, the backend may change or refuse any field, idempotency not verified). QA states what is not proved. Nothing here claims a real backend.
- Parent package status | verified | Nothing claims more than this slice. Line screens, section paging, real sends and the backend all belong to later tasks.

## Hand-off to backend (PROPOSAL D-LINE-WORKSPACE; the PR must say the contract is a proposal)
1. Backend idempotency and server-side refusal of a resend while delivery is uncertain (SEC-5-C1, PMO-0-2). The frontend lock does not stop a second tab, a stale tab, a direct API call or a retry from another client. It must be built and tested before any real send is enabled. The mock accepts a second `approve_send`, so the "one send per key" result is mock evidence only.
2. E-WORK-STEP and the `workspace` block in E-WORK-ITEM are `unimplemented`. The backend developer may change or refuse any field.
3. A section-page read for `next_cursor`, `total` and `filters`. Today these render as disabled controls with "More rows aren't available yet."
4. Form prefill. The step form cannot open with the item's current answer and status (field `value` is for display fields only). It also lacks a submit label and item context (round-2 and round-3 review-ui.md, fidelity step-form).
5. The deciding role or panel title for the step row (boards draw "Decide - PMO Lead"). The frame shows "Decide".
6. "Try again" revision versus idempotency (TECH-1-4, TECH-2-2). A manual retry reuses the key but sends the reloaded `expected_revision`. If the first attempt landed, the real backend would answer 409 unless it replays by key first. The backend must define which check wins.
7. Smaller gaps: the currency on a money field descriptor (the frame sends NGN), a client-preview link, a "source" cite link on suggestions, and "select all" for items steps.
8. Reconcile permission: a viewer without the `reconcile` grant sees every step off on an item awaiting reconcile and no reconcile button (TECH-5-2). The backend and the line tasks should confirm that this is intended.
