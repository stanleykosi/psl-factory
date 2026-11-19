VERDICT: PASS
REVIEWER: pmo-acceptance
COMMIT: 4dba97ab6ee7dd7c97f33f51a63d28750636cb58
AUTHORITY: delivery PMO acceptance

## Summary
- Scope holds: FE-FIN-LEDGER part 1 (SCR-58 investigating, observe, review, verified; W-4201..W-4204 plus hold and refusal fixtures W-4205..W-4213), contract mock only. Part 2 (duplicate, Correct, rejected board, Open LED-0049) is held and listed in the handoff.
- Gate PASS on this head (checks.sh, round 1 attempt 1). Technical, security, UX, UI and QA all PASS on 4dba97ab; no blocking finding anywhere.
- The only change outside the ledger line is the F-47 landing repoint (`mock/start-work.mjs`, 2 lines), which spec.md:223 assigns to whichever of F-45 and F-47 merges second. InlineDecide gets the stale-409 fix, identical to F-35 and F-39. `frontend/src/api/**` is unchanged.
- Fidelity: coverage 100 after exceptions on all 8 boards (desktop verified recomputed from report.json, tool not re-run). Visual 76.4 to 91; seven boards rest on unsigned D-83 waivers.
- Handoff: the F-45 section is on the branch (BACKEND-HANDOFF.md:373-388), questions only. No new generated type or endpoint.

## Task and endpoint mapping
- Task FE-FIN-LEDGER matches feature.json `task_ids`. Dependencies F-17 (frame), F-31 (upload grant), F-33 (InlineDecide, `steps[].verdict`) and F-47 are merged on dlv-00. No dependency is open.
- Endpoints consumed per readiness.md:43-46 and the handoff: E-WORK-ITEM, E-WORK-STEP, E-EVIDENCE-UPLOAD, E-TASK-CLAIM, E-TASK-DECIDE. All are existing; none is added.

## Findings
- PMO-1-1 | non-blocking | medium | coordinator | feature.json `operation_ids` is empty. Set it to exactly: E-WORK-ITEM, E-WORK-STEP, E-EVIDENCE-UPLOAD, E-TASK-CLAIM, E-TASK-DECIDE.
- PMO-1-2 | non-blocking | medium | product | AC 22 (fidelity) is not fully met until the design engineer signs the 7 visual waivers (76.4 to 91), the 27 exceptions (all "builder proposal, pending design engineer") and the verified side-note choice (Conflicts 13, Option B). The UI review prefers Option B.
- PMO-1-3 | non-blocking | medium | product | Ledger-only behaviour differs from F-33: after a decide 200 whose re-read still offers the task, the ledger page shows "result not confirmed", while the income line still says "<label> is approved". The design engineer should accept the difference or ask for F-33 to be aligned.
- PMO-1-4 | non-blocking | low | coordinator | AC 26 lists `mock/start-work.mjs` as unchanged. It changed by 2 lines, as the spec's own Conflicts line (spec.md:223) requires. Accepted.
- PMO-1-5 | non-blocking | low | coordinator | Product acceptance is required (readiness) and still pending. It covers the three NOT SET ledger policy values, the three-person separation, what Unknown or More than one does, and the verdict set.

## Follow-ups (none block the merge)
1. TECH-1-1 (merge note): F-45 handles the stale 409 for the ledger line only. Against F-35 (eefaf6c5) and F-39 (45ae7b66), Workspace.tsx conflicts in four places and the allowlists in `income-schedule-mock.test.ts` and `mock-contract.test.ts`; F-39 also conflicts in `WorkItemOverview.tsx` and BACKEND-HANDOFF.md. Resolve by dropping only the `staleShown` ledger gate. Keep `notMovedOn`, `decidedLabel`, `decidedShown` and the ledger `onDecided={... setDecided({ ...notice, taskId })}` wrapper, or AC 9 regresses. Keep both sides' lines in the allowlists and line constants. InlineDecide.tsx merges cleanly. The builder's "drop the LEDGER_LINE gate" note in build.md is incomplete.
2. F-33's income line still says "<label> is approved" before the re-read confirms it (build.md Pending; PMO-1-3).
3. UX-1-1: the shared milestone strip (DRAFTED / REVIEWED / APPROVED / SENT / RECEIPT RECORDED / VERIFIED) shows on ledger pages; the boards do not draw it and SENT and RECEIPT are invoice words. Shared work-item code; the coordinator decides whether `ledger_sources` hides it.
4. UI-4: mobile verified shows two extra facts (Authenticity certified, Completeness certified) and a "RECORDED" heading beyond the board's two rows. They come from the data. Add an exception line so every difference is listed.
5. QA non-blocking: QA-1-1 / TECH-1-4, the mock upload grant ignores a step's `disabled_reason` (W-4210 capturer can upload on the mock; page sends nothing; the real backend must refuse, recorded in the handoff); QA-1-2, after the W-4213 500 no Try again is offered (spec allows).
6. TECH-1-2 (fallback string 'This decision' inline in Workspace.tsx:240) and TECH-1-3 (station status word hidden visually, kept for screen readers; the design engineer reviews this styling). UI-3: shared note field height and fact rows could be restyled in ledger-scoped CSS.

## Verified
None. This is round 1; there are no earlier findings to retest.
