VERDICT: PASS
COMMIT: 195926d6854956a6918ef6199c0a5f57ce3a32ad
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead)

## Summary
- /projects (SCR-22) and /projects/<case_id> (SCR-07) read only E-PROJECTS and E-PROJECT, using the generated operation types. The frontend never filters, sorts or derives counts, and it makes no request when `projects` is missing from `useMe().destinations`.
- Error mapping matches the spec. 401 shows the signed-out state, and 403 on the list shows NotOpenState. 404 and 403 on a journey show the same no-access state, which names nothing about the project, and the page title is static. Any other error shows the error card. A non-list body lands in the error state.
- The `server.mjs` edit is the four-part edit in the spec and nothing else. The mock rules follow the spec: persona rows, then `q`, then `o<offset>` paging, `invalid_query` 404, P-0099 reserved, and a fallback journey for unknown ids.
- I ran 6 vitest files (mock-projects, projects-model, projects, projects-journey, mock-contract, shell): 163 passed. The shared mock on 3712 returns finance_lead 24 rows, pm 4, none 0, P-0102 200 for finance_lead and 404 for pm, P-0099 404, and 11 distinct states on P-0101.
- Lane check: the only file outside the lane is `e2e/decide.spec.ts`, which came in with the coordinator's merge of the base (PR #10), not from the builder. Backend, shell, api and styles are untouched.

## Findings
None.

## Notes
- `isJourney` requires a non-empty `next`. The openapi types it as a required string, and the mock never sends an empty one. If the backend ever sent an empty `next`, the page would show the error card. This matches the minLength in the v4 contract, so I am not raising it.
- The Out of scope items (tabs other than Journey, counts, filters and the station bars) are absent, as the spec says.
