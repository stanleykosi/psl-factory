VERDICT: PASS
COMMIT: 2892f009b88a0dfb1a2ec1df5f33b966f7ba0a7c
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead)

## Summary
- TECH-2-1 is fixed. The PROPOSAL names and shapes now match architecture v7 D-PROJECTS-VIEW in `openapi.json`. That covers `next_milestone {name, due{date, unknown}}`, `pm {name, role, is_you}`, `facts[] {label, value, money, unknown}`, `agent_summary {agent, text}`, `work_count`, `line_count`, `total`, and the line fields `station {index, count, name}`, `status_label` and `tone`. Every one is read through a guard in `model.ts` (`nextMilestoneText`, `pmNameOf`, `factsOf`, `factText`, `lineDetail`, `agentSummaryOf`, `countOf`, `textOf`). A value in another shape gives "—" or "Not known" and never reaches React as an object.
- TECH-2-2 is fixed. `buildProjectsQuery` sends no `status` for Active, `closed` for Closed and `all` for All I can see. This matches the v7 enum `active|closed|all`. A v6 backend therefore receives the same request as before on the default tab.
- The round-3 change is small and confined to the F-07 files: the projects feature, its mock fixtures and `mock/projects.mjs`, four test files, one CSS line and the merge of the delivery branch. The UX-2-1 count change (`total` from the response, with the tab count used only when no search is active) is correct and does not invent a count.
- I ran the four F-07 vitest files: 88 passed. `checks.md` shows the gate passing on this head.

## Findings
None.

## Notes
- Non-blocking, no action: the `unknown` flag on `line.tone` is not read by the client, which still maps from `state` through `STATE_TAGS`. v7 says the frontend maps the tone to the tag colour. This is outside the TECH-2 findings and can be taken when a backend serves v7.

## Verified
- TECH-2-1 | verified | The v7 `openapi.json` schemas for `/projects` and `/projects/{case_id}` match the names and shapes in `model.ts`. Guard tests in `projects-model.test.ts` and `projects.test.tsx` pass.
- TECH-2-2 | verified | `buildProjectsQuery` omits `status` for Active, and the v7 `status` parameter enum is `active|closed|all`. Tests pass.
