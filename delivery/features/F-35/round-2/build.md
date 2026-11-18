STATUS: READY
COMMIT: 15db6f7ce238dc53c4d352ae8bd327bca6f13c8e
BUILDER: builder
LANE: full

## Summary
- W-3210 is the fixture where the viewer can see 3 of the 5 projects. It now carries only those 3 projects' records, in the figures and in Tola's step text and sources. The 2 projects left out appear only as the backend's count.
- New tests check that no hidden project's name, case id, count or escalation id appears anywhere on the W-3210 page, Tola's text included, or in the fixture. Both tests fail on the round-1 fixture.
- BACKEND-HANDOFF now states the `sends` contract rule (TECH-1-1, SEC-1-2) and the visibility rule for agent text (SEC-1-1).
- No page code changed. No frontend path joins or draws anything across projects: the page draws only the sections and agent steps the response returns.
- The layout did not change (W-3210 has no board), so there was no fidelity run this round. Round 1's scores and waivers still apply.

## Changes
- `frontend/mock/fixtures/work/W-3210.json`:
  - Figures: Projects covered "3 OF 5" and the coverage line, both unchanged. Milestones completed "2" and invoices verified "1" now count the visible projects only. Open escalations is still Unknown.
  - Tola's steps: "Gathered October's records you can see" with source "3 PROJECTS · 24 MEETINGS · 7 ISSUES"; "Summarised milestones and money" with source "2 MILESTONES COMPLETE · 1 INVOICE VERIFIED"; "Drafted the escalations section" with no source, so no escalation id is cited.
- `frontend/tests/leadership-report.test.tsx`: new test "SEC-1-1: W-3210 shows only the visible projects' records…". It checks `document.body.textContent`, which includes the agent card's steps and sources:
  - the visible-only sources are present;
  - none of these appear: "5 PROJECTS", "41 MEETINGS", "12 ISSUES", "3 MILESTONES", "2 INVOICES", any `ESC-n`, any project title or case id from `projects/list.json`, or any `P-nnnn`;
  - there is no `/projects/` link;
  - "left out" appears exactly once (the backend's count).
- `frontend/tests/leadership-report-mock.test.ts`: new test "SEC-1-1: W-3210 … carries only visible records". In the fixture JSON, the agent text cites "3 PROJECTS", and none of the five-project totals appear, nor any `ESC-n`, `P-nnnn`, `case_id` or `work_id`.
- `delivery/BACKEND-HANDOFF.md` (F-35 section):
  - New contract rule: whenever a step sets `sends: true`, the backend also sends that step's `consequence` naming who receives it. Without it the shared fallback says "This sends to the client.".
  - The fixtures keep `sends` off until the rule is confirmed.
  - The coverage bullet now says the viewer's visibility applies everywhere in the item, the agent's step text and sources included, and that a left-out project is only ever a count.
- The approve steps still have no `sends: true` (TECH-1-1, as agreed).

## Fixes
- SEC-1-1 | 15db6f7c | W-3210's figures and Tola's step text and sources now cover only the 3 visible projects, with no escalation id. A page test checks the whole document body, agent text included, and a fixture test checks the JSON. Both fail on the round-1 fixture.
- TECH-1-1 | 15db6f7c | `sends` stays off the approve step. BACKEND-HANDOFF asks that any step with `sends: true` also sends a `consequence` naming its audience.

## Acceptance criteria
Unchanged from round 1 and still met. Criterion 3 is strengthened: on W-3210, hidden projects are never named, counted or cited, and that includes the agent's text.

## Validation
- `npx vitest run tests/leadership-report.test.tsx tests/leadership-report-mock.test.ts`: 45 passed.
- The two SEC-1-1 tests run against the round-1 W-3210 fixture (`git show HEAD~0:…` before the fix): both fail, which is the intent.
- `bash /Users/Hunchoo/psl-factory/delivery/checks.sh`, under the shared lock (load 13.7 when acquired): exit 0.
  - Django check found no issues.
  - Lint, typecheck and build succeeded.
  - 109 test files and 2491 tests passed.
- `cd frontend && E2E_PORT=4988 MOCK_PORT=4989 npx playwright test e2e/leadership-report.spec.ts e2e/income-schedule.spec.ts`: 66 passed (2.7 min). `test-results` was deleted, and nothing is listening on 4986 to 4989.
- No fidelity run: no layout or board-state change this round (only the W-3210 fixture, which has no board).

## Blocked
None.
