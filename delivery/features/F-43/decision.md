RECOMMENDATION: ESCALATE
COMMIT: 5020a86be7320090efa1b2888295f52e205e761a
APPROVER: approver

## Summary
- F-43 draws the cash forecast review (SCR-56 part 1) in four states from the contract mock; approve, return, reject and "record what happened" go through existing shared panels.
- Gate, technical, UX, UI, QA and PMO acceptance all PASS on this head. Security PASS is carried from round 1 with an impact note, not re-run.
- Risk is high (approval write on a money figure, uncertain-delivery record, contract-change surface), above the policy's low-only auto-merge level.
- Open items are the design engineer's: unsigned fidelity waivers and floor exceptions, a wording collision, product acceptance.
- Pre-merge: the shared stale-409 fix must arrive from dlv-00 (F-35/F-39) with a two-reviewer test.

## Why
The work is sound and fully evidenced, but the feature is rated high risk and the merge policy allows AUTO_MERGE for low only. The visual waivers, two boards under the 70 floor and a product wording conflict are decisions a person must make.

## Acceptance criteria
1. Four states from data (AC 1): met, component tests and QA at 1440 and 390.
2. Amounts as returned, nothing computed (AC 2, 3): met, tests on modified fixtures and diff grep.
3. Unknown never 0, sample-marked (AC 4, 5): met.
4. Holds, no invented reviewer, controls only from you_can_act (AC 6 to 8, 15): met; QA saw 0 POSTs on every hold.
5. Agent work, uncertain board, reconcile grant (AC 9 to 11, 18, 19): met.
6. Verified only after the re-read (AC 12): met, but collides with the "received" wording (see below).
7. Approve, return, reject, refusals, uncertain decide (AC 13, 14, 16, 17): met except AC 16 note-kept on a stale 409 (QA-2-1, shared gap, fix comes from dlv-00).
8. Access, phone, accessibility, tokens, mock matches contract (AC 20, 21, 23 to 25): met.
9. Fidelity (AC 22): not met until the waivers and exceptions are signed. Coverage 100 on all 8 boards after exceptions.
10. Contract not extended (AC 26): deviation, shared Sections.tsx changed (PMO-2-3).
11. Existing tests green, evidence (AC 27, 28): met, checks.sh exit 0 (2882 tests); e2e 142 passed, 1 mock-reset flake passed on rerun.

## For the human
Files:
- /Users/Hunchoo/psl-factory/delivery/features/F-43/fidelity-exceptions.json
- /Users/Hunchoo/psl-factory/delivery/features/F-43/round-2/build.md (Fidelity table)
- /Users/Hunchoo/psl-factory/delivery/features/F-43/round-2/review-ui.md
- /Users/Hunchoo/psl-factory/delivery/features/F-43/round-2/acceptance-pmo.md

Please sign:
1. The 8 D-83 visual waivers (six boards 70.9 to 84.4; the two verified boards below).
2. The two floor exceptions under 70: desktop verified 55.6 and mobile verified 51.9. The UI review judged these mostly frame offset (StationTrack about 40px taller on desktop; phone title, tag and History about 75px), with a small real part in UI-2-1 (phone strip font).
3. The 28 exceptions (all "builder proposal, pending design engineer"), including the shared-frame items and the phone callout wording (UX-1-2).
4. The "received" wording: AC 12 bans "received" before the re-read, but the Conflicts 4 option reads "I have proof it was received". Keep the option (and amend AC 12) or reword it.
5. The shared Sections.tsx change (strip, caption, fact tags), which also restyles "NOT SET" facts on F-33 and F-42 (TECH-2-1).
6. Product acceptance (required): who the forecast reviewer is, whether a return gives the preparer a task (D-RETURN), uncertain-delivery outcomes, and cancel-delivery.

Before the PR, the coordinator should:
- Sync the stale-409 fix from dlv-00 and add a two-reviewer test (TECH-1-1).
- Set operation_ids (PMO-2-1).
- Restore the f-43 worktree to HEAD (UI review saw round-1 src staged over it).
