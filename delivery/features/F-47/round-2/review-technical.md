VERDICT: PASS
REVIEWER: reviewer-technical
COMMIT: cfd8a916060e08c73e7217af956fe4d3b98f41a1
AUTHORITY: delivery technical review

## Summary
- Read `git diff 438c350f..8d7da0c4` (8 frontend files) and checked each round-1 TECH finding against the code and tests.
- `rereadCase` now throws a `not_found` ApiError when the fixed line is gone, when no project is chosen, or when the chosen project is no longer served. In `useEvidenceUpload`, the Try again path (lines 116-120) sends that to `onAccessError` and returns before any send. The 409 path (line 97) swallows it, and that file is already failed with "This item changed. Add the file again.". So nothing is uploaded to a dropped case.
- `ownsUpload(url, raw, persona)` now needs both a served line's evidence kind and `caseBase(line, persona, caseId) !== undefined` for a line with that kind. That is the spec's routing rule, and it only narrows what start-work takes. One assertion changed: `C-FIN-SCHEDULES` with `ledger_source` was a start-work 404 and now reaches F-09's owner, which answers 422. This is the expected result of the spec rule, not a loosening. The test now also proves the start-work revision stays at 3, and the 404s for `C-0102`, `C-0103` (pm) and `C-NOPE` are kept.
- F-05, F-09 and F-31 upload behaviour is unchanged: the diff touches no file under `src/features/response` or `src/features/setup`, and neither `mock/response.mjs` nor `mock/evidence.mjs`. The `server.mjs` change is only the call inside the F-47 branch.
- Tests run on this head: vitest: 6 start-work/response files gave 252 passed, and 7 mock-contract/setup/work-item/workspace/weekly files gave 499 passed. e2e/start-work-proof.spec.ts (4946/4947, 5-min load 19.5) gave 14 passed at 1440 and 390; test-results removed.

## Findings
None.

## Verified
- TECH-1-1 | verified | useStartWork.ts rereadCase throws not_found in all three no-case paths, and the hook's Try again path stops on not_found. Tests "TECH-1-1: Try again sends nothing once the fixed case… / the chosen project…" assert exactly one upload.
- TECH-1-2 | verified | start-work.mjs ownsUpload checks kind and caseBase per line. The routing test covers 9 kind/case/persona combinations. The changed C-FIN-SCHEDULES assertion now expects F-09's 422 with the start-work revision kept at 3, and the other 404s are kept.
- TECH-1-3 | verified | StartProof.tsx fieldset gets aria-describedby="${id}-error" and aria-invalid only when error is set, and the error span carries that id. The test checks the attribute equals the .psl-error id.
- TECH-1-4 | verified | round-2/build.md records the round-1 BACKEND-HANDOFF.md edit (c3b03bfb) as an edit outside the lane. This round does not touch it.

## Update for head cfd8a916 (diff 8d7da0c4..cfd8a916)

- None of F-47's files (start-work intake, ProofField, useEvidenceUpload, server.mjs, me.finance_lead.json) changed in 8d7da0c4..cfd8a916; the only F-47 file touched is tests/mock-contract.test.ts, which gained F-31, F-32 and F-33 proposal checks.
- Re-run on the worktree: start-work, response and mock-contract tests, 9 files, 571 passed. checks.sh passed (2552) and e2e passed (99) per build.md.
- F-31 response Drawer and F-33 lines are untouched by F-47 and their tests pass.

Verdict unchanged.
