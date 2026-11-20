VERDICT: PASS
REVIEWER: reviewer-security
COMMIT: cfd8a916060e08c73e7217af956fe4d3b98f41a1
AUTHORITY: delivery security review

## Summary
- Checked the round-1 routing note and the new code for security impact.
- Mock routing now needs both the kind and a case the line starts on (`caseBase`), so start-work takes fewer uploads, not more. The CSRF check and the scenario-then-CSRF order in the `server.mjs` branch are unchanged.
- Try again can no longer send proof to a case the drawer has dropped, because the re-read refuses with not_found and the hook stops before sending.
- The new alert text is `${f.name}: Not uploaded. ${f.problem}` rendered as React text. There is no new HTML sink or `href`. 403/404 (CANT_ADD) is left out, so access refusals still read the same and name nothing.
- Tests run on this head: vitest: 6 start-work/response files gave 252 passed, and 7 mock-contract/setup/work-item/workspace/weekly files gave 499 passed. e2e/start-work-proof.spec.ts (4946/4947, 5-min load 19.5) gave 14 passed at 1440 and 390; test-results removed.

## Findings
None.

## Verified
- Round-1 note (ownsUpload routes on kind only) | verified | start-work.mjs ownsUpload now also requires caseBase(...) !== undefined. The routing test shows a kind on a case the line doesn't start on, or for another persona, returns false.

## Update for head cfd8a916 (diff 8d7da0c4..cfd8a916)

- None of F-47's files (start-work intake, ProofField, useEvidenceUpload, server.mjs, me.finance_lead.json) changed in 8d7da0c4..cfd8a916; the only F-47 file touched is tests/mock-contract.test.ts, which gained F-31, F-32 and F-33 proposal checks.
- Re-run on the worktree: start-work, response and mock-contract tests, 9 files, 571 passed. checks.sh passed (2552) and e2e passed (99) per build.md.
- F-31 response Drawer and F-33 lines are untouched by F-47 and their tests pass.

Verdict unchanged.
