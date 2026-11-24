VERDICT: PASS
COMMIT: e5f7b00d3f67a933ecb2f9029552c9fa0b173ff6
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead), lighter panel (D-180)

## Summary
- Reviewed from refs (`origin/main...e5f7b00d`) against spec.md and contract 1.26.0. I ran no tests, because the lane worktree holds F-72's files.
- Unknown money holds. A null `amount`, `paid`, `owed` or `additional_amount` reads Unknown. Nothing is summed. Invoice `status` is shown as sent and no paid word is derived. `amountText` returns undefined for a non-decimal string, so it reads Unknown rather than 0.
- The stage-to-completion join goes only through `milestone_id` (`completionFor`). There is one GET per Proof press, and `403` or `404` reads as refused. The two reads on the Milestones tab are independent, each with its own refusal and retry.
- Live types come from the generated `live-schema` (`workspaces_money`, `workspaces_project_tab`, `project_operations_milestone`). The model guards match the 1.26.0 required fields, apart from the gaps in TECH-1-1.
- The shared tab files are in good shape for F-75. `ReadTab` is a clean `Exclude`, and `AmountValue` was removed with no other users. The mock touches (`server.mjs`, `project-tabs.mjs`) are small and isolated. The three shared test touches match what build.md lists and weaken nothing.

## Findings
- TECH-1-1 | non-blocking | low | frontend | `isInvoice` does not check `id` or `currency`, and `isChange` does not check `link_id`. All three are required by the contract. They are used as React keys, and `invoice.currency` goes into `amountText`. A body missing them would draw "undefined 1.00" or a duplicate key rather than the bad-body card. Add the integer and string checks at moneyModel.ts:19 and :27.
- TECH-1-2 | non-blocking | low | frontend | The Money intro line says "Every figure links to the record it came from". Items with no sources show "No source recorded", so the claim is wider than the data. Soften the copy (MoneyTab.tsx, the `money__lead` paragraph).
- TECH-1-3 | non-blocking | low | frontend | When `money.items` is empty, MoneyTab returns the empty state before the `limited` callout. A limited and empty body hides the "may be incomplete" warning. Show the callout above the empty state.
- TECH-1-4 | non-blocking | low | integration | Live smoke (AC17) saw only an empty seeded project, so a populated live body is unproven. Re-check on the first populated environment, with `reference`, `milestone_id` and `stage_position` set. Stages whose completion is beyond the first 25 rows lose the "Recorded by" line, but Proof still works through `milestone_id`. That is acceptable and documented.

## Verified
None (round 1).
