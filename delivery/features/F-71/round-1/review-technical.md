VERDICT: PASS
COMMIT: 3df5462d49c464d12d789486760215fb1df62304
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead), lighter panel (D-180)

## Summary
- Delta re-review of e5f7b00d..3df5462d. All three earlier fixes (TECH-1-1, TECH-1-2, TECH-1-3) are closed, each with a test that fails without the fix.
- Both merge resolutions keep both sides working. The `next-config.test.ts` allow-list holds the F-71 entries (`money-model.test.ts`, `milestones-model.test.ts`) and F-72's and F-86's. `mock/server.mjs` keeps the F-71 milestone route (`isMilestoneRequest`) and F-72's live document-review route, and F-86's start-live route is wired in too.
- The merge of main 8692cf87 (CI gate workflow) touched nothing under the F-71 files.
- I ran three single files, `money-model.test.ts`, `money.test.tsx` and `next-config.test.ts`: 3 files, 67 tests, all passed on head 3df5462d. Gate attempt 5 also passed.
- One non-blocking note stays open (TECH-1-4).

## Findings
- TECH-1-4 | non-blocking | low | integration | Live smoke (AC17) saw only an empty seeded project, so a populated live body is unproven. Re-check on the first populated environment, with `reference`, `milestone_id` and `stage_position` set. Stages whose completion is beyond the first 25 rows lose the "Recorded by" line, but Proof still works through `milestone_id`. That is acceptable and documented.

## Verified
- TECH-1-1 | verified | `isInvoice` now requires an integer `id` and a string `currency` (moneyModel.ts:19). `isChange` requires an integer `link_id` (moneyModel.ts:27). `money-model.test.ts` adds three rejection cases: an invoice without an id, an invoice without a currency, and a change without a link_id. `money.test.tsx` adds the same three as live 200 bodies, and each ends in the error card with Try again and one new read.
- TECH-1-2 | verified | The `money__lead` copy now reads "Each figure shows where it comes from when a source is recorded...". That no longer overclaims for items with no sources. The test assertion was updated to the new text.
- TECH-1-3 | verified | `incomplete` is now computed before the empty-state return and rendered above the `EmptyState`. The new test "limited with no items still shows the warning above the empty state" asserts both the callout and the heading.
