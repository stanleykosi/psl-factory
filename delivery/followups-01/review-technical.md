VERDICT: APPROVE (no blocking findings; 3 non-blocking notes)
REVIEWER: technical (lead)
BRANCH: fu-01-small-followups @ 1a7e4c9de8d61230a4b5b667982212ba18008918

## What I checked
- Read the build note and the full diff against origin/dlv-00-delivery-setup (28 files, frontend lane only). Nothing outside `frontend/`; no backend, contract (openapi) or money/permission code touched.
- Each of the seven fixes against its finding:
  1. Decide done phone view: the card text drops the "Paid is tracked separately..." sentence only when `phone && approved && reloaded`; desktop untouched. New test asserts the sentence appears once.
  2. Projects count: `total === 1 ? 'PROJECT' : 'PROJECTS'`. Three assertions changed (projects.test.tsx x2, projects.spec.ts x1), all "1 PROJECTS" to "1 PROJECT", justified in the note and correct.
  3. Projects mock: `contractBody`, `PROPOSED_FIELDS` and the v6 comments removed. Bodies are now validated in full (list, journey files, fallback, live responses) against the loaded contract. The v7 validators were already run on the same bodies in `mock-projects.test.ts`, so strictness is not lower than before. The removed `PROPOSED_FIELDS.row` equality is a tautology on a list that no longer exists; the real row-field values are still asserted one line above. Nothing weakened.
  4. Alerts drawer: `leaveAlerts(href)` sets the focus flag only when the target path differs from the current path. Query/hash are stripped before comparing. New test covers the same-page case and checks the later navigation does not take focus.
  5. Work item: "See all exceptions" button now follows the panel links. Pure order change. W-1711 gets `case_id`/`case_revision`; three sidecars are the W-1603 shape plus `amount`, and the walk test covers delivered, not delivered and unknown. Mock data only.
  6. Alert settings: CSS variable for the 86px bar, `scroll-margin-bottom` on callouts, and the problem callout is scrolled into view. The e2e tests check callout bottom against bar top at 390.
  7. Setup rules: closed-panel notice cleared when an editable rule is back; focus moves to a visually hidden "All N rules are shown." line after the last page. The test asserts the focus target.
  8. My work empty state: new `tola-done.png` (static asset) and CSS sizes. Alt text and test changed together.
- Confirmed the skipped items (F-09 wording, wordmark under 380px, phone "← Setup") are design or product calls and are correctly left alone.
- The mock-contract change for E-PROJECTS and E-PROJECT: the `CONTRACT_BODY` entries are removed from `mock-contract.test.ts`, so those operations go through the default full-schema path. The builder reports `checks.sh` green (1169 vitest tests). I did not re-run vitest.

## E2E run by me (worktree frontend, `E2E_PORT=4801 MOCK_PORT=4802`, playwright.config.ts sets `FRAME_FIXTURES=1`)
Specs: decide, exceptions, finance-month-end, overview, response, start-work, work-item, frame.
- Run 1 (all eight specs together, 17.2 min): `119 passed`, `28 failed`. Tests 1 to 107 (decide, exceptions, finance-month-end, overview) passed. Then every test in response, start-work and work-item failed, while frame (after them) passed again. All failures were one of two kinds: `getByRole('status').filter({hasText:'Loading…'})` still present after 5s, or `h1` / `main#main h1` not visible. That points to the pages never finishing their load in that stretch of the run (environment or load), not an assertion about this branch's changes.
- Isolated re-check: `work-item.spec.ts -g "W-1099 shows the no-access"` passed.
- Run 2 (response + start-work + work-item together, 3.8 min): `49 passed`, exit 0. This covers all 28 tests that failed in run 1, plus the rest of those specs.
- Net: every spec I was asked to run passes. The 28 first-run failures did not reproduce on a clean re-run, so I treat them as a transient in the long run, not a regression. The cause was not diagnosed.

## Findings
- TECH-1-1 (low, non-blocking): `RulesView.tsx` calls `setClosedNotice(null)` during render when `closedNotice && editable.length > 0`. This is the supported derive-state-in-render pattern and cannot loop (it guards on the value it clears), but it has no dedicated test; the note says the path is unreachable in the mock. Acceptable. A later cleanup could move it to an effect or derive it.
- TECH-1-2 (low, non-blocking): the phone-only `next_step.replace(/\s*Paid is tracked separately[^.]*\.?/, '')` in `DecideStates.tsx` depends on the wording of server text, and mirrors the existing `includes('Paid is tracked separately')` check beside it. If the sentence is ever reworded, the phone shows it twice again (a cosmetic regression only). Fine for now.
- TECH-1-3 (info, non-blocking): the first full e2e run showed a long run of "Loading…" timeouts after about 100 passing tests (see above). If it recurs on other builds, it is worth a look at mock or server health under long runs. Not caused by this diff as far as I can tell.

## Not done by me
- No design-fidelity check on the My work empty boards or the decide done phone board (the builder also did not run it). That gate belongs to the UI review.
- I did not re-run vitest or `checks.sh`; the build note reports exit 0.
