VERDICT: PASS
COMMIT: 02d59d8bb2216a7242a02454b957d4a0b0fdde49
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead)

## Summary
- Everything the rebuilt My work reads from the contract is in the frontend's generated types: `project`, `waiting_on`, `line_key`, `agent` and `filters.lines`. The generated types are v4 and the v6/v7 `/api/v1/work` parameters and response keys are identical, so nothing is invented.
- The only field outside the contract is `suggestions`. It is typed locally as `WorkListWithSuggestions` and marked PROPOSAL. It is read through a cast, and the panel renders nothing when the field is absent. The mock sends it only with the `psl_mock_worklist=board` cookie, and a test checks it is absent otherwise.
- Degradation is sound. Without `filters`, line options fall back to the loaded rows (`line_key ?? line`). If E-PROJECTS fails, only "Any project" is offered. A failed "Show N items" preview falls back to "Show results". Absent `agent` shows no avatar. Absent `counts` gives no records line.
- QA-2-1 and QA-2-2 are fixed, and no existing test was weakened. Removed assertions were replaced by their board-driven equivalents.
- I did not re-run the checks. I read `checks.md`, which shows a gate pass on this head.

## Findings
- TECH-3-1 | non-blocking | frontend | The Project chip shows the raw `case_id` (`view.project`), not the project title. Business-language rule: the chip should show the title. Reason it is not blocking: titles are only known once E-PROJECTS loads, and the mock does not serve it yet. `frontend/src/features/my-work/MyWork.tsx` (Project chip).
- TECH-3-2 | non-blocking | frontend | The Project select loads one page (`limit: 50`) of E-PROJECTS with no paging. Projects past 50 cannot be picked, and the load error is swallowed on purpose (commented). `frontend/src/features/my-work/FilterPanel.tsx` (`useProjects`).
- TECH-3-3 | non-blocking | frontend | `Suggestion.href` is rendered straight into `<Link href>`. When the proposal is adopted, restrict it to an internal path. In addition, `suggestions[0].agent` picks the avatar for the whole panel. Both are harmless on the mock. `frontend/src/features/my-work/CaughtUp.tsx` (`WhileYoureFree`).
- TECH-3-4 | non-blocking | frontend | "N records you can see" is a sum of the queue counts (an engineering derivation, as the builder says), but it reads as a business fact. The text is not labelled in the UI. Settle this when the architecture ratifies the field. `frontend/src/features/my-work/model.ts` (`recordsText`).
- TECH-3-5 | non-blocking | integration | The mock and `gen:api` still point at the v4 package, while v6/v7 is the current contract. F-13's repoint to v7 covers this. The `/api/v1/work` shape is identical, so there is no live mismatch.

## Verified
- QA-2-1 | verified | `mock/work-list.mjs` returns 404 `invalid_query` for an empty `q`, `line`, `project`, `waiting_on`, `state` or `cursor`, and for an unknown `waiting_on`. `tests/mock-work-list.test.ts` covers `q=`, `line=` and `waiting_on=everyone`.
- QA-2-2 | verified | `tests/mock-row-item-match.test.ts` checks that every row sharing an id with a work fixture has the same title and reference. The fixture ids and titles are unchanged.
- Mock changes | verified | The `server.mjs` change is the single `dataset: cookies.psl_mock_worklist` pass-through. Board data lives in its own fixture, so the default fixtures and `mock-contract.test.ts` are unaffected. `suggestions` is stripped before the v4 schema validation and is asserted absent outside the board cookie.
- Filters and query | verified | `buildWorkQuery`, `parseView` and `viewSearch` round-trip the four filters. Invalid `state` and `waiting_on` values fall back to none. The one-line-at-a-time rule matches the contract's single `line` value.
- Errors and polling | verified | A response for an older view is ignored (`seq`). A failed refresh keeps the rows. A 401 gives the signed-out state. A 403 gives the queue-not-open screen. The caught-up "Where your work is" group requests fail soft.
