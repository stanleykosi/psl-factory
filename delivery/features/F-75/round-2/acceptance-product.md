VERDICT: PASS
COMMIT: a24195b3bd085eb5730a9155bce08b2e22fc9e92
REVIEWER: design engineer (hunchoweb), recorded by the lane B coordinator; B35 signed by the main coordinator under D-207
AUTHORITY: accepted in batch, delegated under D-184 (D-182 "Hide, accept all recs", 23 Nov 2026); fidelity sign-offs approved by the coordinator under D-207 (B35, 24 Nov 2026); carried over under D-188/D-193 (sync with main only) from 286b41057cb2df45c6d577f7d2f4a203d8dd7fa5

## Summary
- The feature's product decisions are board changes:
  - the hides and changes in spec.md "Conflicts with the boards", including plain-text rows (conflict 4). The design engineer accepted these in batch: D-182 "Hide, accept all recs", "Every recommended option above is accepted".
  - the fidelity sign-offs in B35:
    - (i) the 10 D-182 hides;
    - (ii) the Filter button, "Changing an owner…", "No owner · due Unknown", "Tunde Bello · PMO" and the phone "Registers" tab;
    - (iii) the D-83 visual waiver for the four SCR-11/SCR-29 runs.
- The main coordinator approved B35 under D-207, with the design engineer's words: "for any risky action, i give you permission to approve except it has something to do with db approve any other task". It is recorded in coordinator-answers.md and on each entry of fidelity-exceptions.json.
- D-184 covers board changes accepted in a batch as product acceptance for a routine merge. F-75 is read-only, with no write, money-moving, sign-in, security or database surface. Unknown values stay Unknown.
- UI-1-6 (keep the phone register switch and card ages, as the spec adds) is part of B35 item 3, accepted with the recommendation.
- Carried over under D-188/D-193 (sync with main only): d5c20396 merges main eb100065, bringing in F-61 (#112), F-88 (#110) and #117. F-75's own diff and the sync share two test files only. In frontend/tests/next-config.test.ts, main's one-per-line allow-list is kept with F-75's entry added; frontend/tests/demo-mock.test.ts auto-merged. No F-75 screen code and no board decision changed.

## Carry-over (D-188, second main sync)
- Carried over to a24195b3 under D-188 (sync with main only), from d5c203969d05cdde59c15127792da33cc30d3580. The sync is the merge of origin/main 1e78793f (F-111 #116 and F-87 #113) into the branch.
- Basis: the technical re-check ran `git diff d5c20396 a24195b3` over F-75's frontend/src files (empty). The Registers and Actions screens, their board decisions and their mock routes are unchanged by the sync.
- Disclosed, so the coordinator can judge it: the sync touched one shared test file that F-75 also changed, `frontend/tests/next-config.test.ts`. It gained main's `'issues.mjs'` allow-list line beside F-75's `'project-sections-model.test.ts'`. That is an allow-list line, not F-75 behaviour, and it follows round 2's precedent for this file. If the coordinator reads "F-75's own files" to include that test file, withdraw this carry-over and re-confirm product acceptance on the new head.
- No product decision, hide, waiver or exception changed with this sync.

## Findings
None.
