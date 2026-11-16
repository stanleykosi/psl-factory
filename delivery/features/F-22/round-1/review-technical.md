VERDICT: PASS
COMMIT: 6d857c318ffb4d772126d9e236e9dba90f0625ba
REVIEWER: reviewer-technical
AUTHORITY: delivery technical review

## Summary
- The three frame changes (item-less note, tag over receipt word plus "Time unknown", "Next" panel) are small, general and token-only. Absent `next` and absent `tag` keep the old output.
- Fixtures W-2209 to W-2214 match the spec table. Recipient and unknown states never claim delivery unless the data's own tag or receipt says so. W-2212 offers no step and only reconcile.
- No change under `src/api`, `apps`, `architecture`, `design`, `mock/workspace.mjs` or `mock/start-work.mjs`, and no existing fixture edited. The weekly-mock guard for W-2201 to W-2208 is kept and positive checks added.
- checks.sh passed on this head. The limits (contract mock only, D-RETURN, D-ALERT-PROVIDERS) are in build.md.

## Findings
- TECH-1-1 | non-blocking | frontend/src/features/workspace/Workspace.tsx:237 | The `said` filter drops a `next` line equal to a step consequence, so that line shows only if the step row draws its own consequence. Expected: the page shows the data line in every state. Actual: it relies on Steps.tsx drawing it, and the form-open state was not checked. | Confirm the consequence stays visible while the form is open, or drop the dedupe and let the step omit it.
- TECH-1-2 | non-blocking | frontend/src/features/workspace/Sections.tsx:379 | Text rows now draw an item `tag` for every text section. The only existing text-kind fixtures are unaffected, but this is wider than the recipients change. | Keep, and note it in the frame-change list (build.md already does).
- TECH-1-3 | non-blocking | delivery/features/F-22/round-1/build.md | Criterion 12 is marked partial: the 401/403 paths are not re-tested for W-2209 to W-2214. They are the unchanged F-21 handling. | Optional: add one 403 component test on W-2209 in a later round.

## Verified
None (round 1).
