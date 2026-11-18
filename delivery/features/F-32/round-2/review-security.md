VERDICT: PASS
REVIEWER: reviewer-security
COMMIT: 5bab76ae6a1d3a5bd8a26c0504b7a7ad72d51b9b
AUTHORITY: delivery security review

## Summary
Reviewed 9f594712..5bab76ae. Removing `claim_required` from W-2501/2502/2504-2507 changes only a hint: it is read in `workspace/Steps.tsx` to add the "Claim it first" text and an aria-describedby on the link to the decision page. It gates no write. The claim and the decide write are enforced in F-16, on `/work/[id]/decide` (`decide/useDecision.ts`), which claims the task on open when `you_can_act` is true and sends the decision only when the claim status is `ready` for that task and revision (line 186). The server still checks the claim and the role.

## Findings
No blocking findings.

- Claim before decide: unchanged. `useDecision.submit` returns unless `claim.status === 'ready'` and the claim key matches. `DecideView` and `DecidePanel` lock the controls when `!task.you_can_act` or there is no claim. Fixture `claim_required` is not consulted there.
- `you_can_act` false: `Steps.tsx` shows a disabled control with a reason and no href. A missing task is also disabled. It is unchanged in this diff.
- Layout changes add no control or write. The only new interactive element in `DeliveryTab.tsx` is a `Link` to `/work/<encoded id>` (navigation, encoded). `work-columns--lone` is a class only. The fixture, CSS and e2e edits (link count 6 to 7) add no capability.
- Checks: `release-gates` and `decide` vitest files pass (61 tests).
- Notes (non-blocking): the hint "Claim it first" is no longer shown on release steps. That is cosmetic and matches the page, which claims on open.
