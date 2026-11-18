VERDICT: PASS
REVIEWER: reviewer-technical
COMMIT: 62ed73aa419d1e6a2bc990125bfd517422a778d3
AUTHORITY: delivery technical review

## Summary
Reviewed 9f594712..5bab76ae with round-2/build.md. No blocking issues.

1. Claim flow: unchanged. `claim_required` is read only in `workspace/Steps.tsx` (lines 94-97) to show the "Claim it first" hint beside the link. The claim itself comes from `decide/useDecision.ts` (lines 170-175). It claims once per `task.id:revision` whenever `task.you_can_act` is true, and never looks at the step field. So removing the field from W-2502..W-2507 (W-2503 and W-2508 never had it) cannot make the page or mock skip the claim. The field is optional in `schema.d.ts`, so the fixtures still validate; the gate and `mock-contract` passed on this head. A real backend could send `claim_required: true` on an unclaimed task, and the fixtures no longer show that hint. That is a fixture-realism loss only. The hint is cosmetic, and the claim happens on open either way.
2. Lone column: `work-columns--lone` is added only when `item.workspace?.line_key === 'delivery_release'` and `shownTasks.length > 0`. Every other line keeps `work-columns`. The CSS rules are scoped to the new class, and the desktop override is inside the existing media query. `release-gates.test.tsx` covers both sides: W-2501 gets the class, and W-2901 (minutes) keeps two columns and has no `--lone`.
3. Project-bar link count: the 6 to 7 change in `e2e/issue-detail.spec.ts` is mechanical for the new Delivery tab. No other change was needed.

## Findings
1. TECH-1-1 | non-blocking | low | carried forward, unchanged | `workspace/Steps.tsx` shows the generic "isn't open to you here" text and drops `cannot_act_reason`. No current fixture is affected.
2. TECH-1-2 | non-blocking | low | carried forward, unchanged | The F-23 guard in `mock-contract.test.ts` is `/^W-2[35]/`, slightly broader than needed.
3. TECH-2-1 | non-blocking | info | frontend/mock/fixtures/work/W-2502.json..W-2507.json | The fixtures no longer carry `claim_required`, so the "Claim it first" hint is not exercised on the release lines. It is a hint only, and the claim still happens on the decide page. Consider one fixture with it set so the hint stays covered. No change is required.

## Update for head 62ed73aa (diff 5bab76ae..62ed73aa)
- Read the diff 5bab76ae..62ed73aa on the shared files (Steps, Workspace, Sections, WorkItemView, AssignForm, workspace.mjs, mock-contract test): F-31 additions sit beside the F-32 release-gate paths without changing them.
- Orphan-step rule checked: a step whose task is in tasks[] with you_can_act true still links to the decision page; only a missing task or you_can_act false is unavailable.
- Ran engagement-planning, release-gates, delivery-*, workspace* and issue-detail tests in the worktree: 8 files, 230 tests passed.
- Verdict unchanged.
