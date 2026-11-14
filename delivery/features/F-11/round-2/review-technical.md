VERDICT: PASS
COMMIT: edc476370a1b20444d9807811a9d7b0a6ed2f503
REVIEWER: reviewer-technical
AUTHORITY: technical review (lead)

## Summary
- The round-2 diff (`06b4c0e..edc4763`, 2 commits, 8 files) touches only Setup frontend files, the two mock modules and tests. No contract, request shape or authority check changed.
- QA-1-1 fix: `SetRulePanel.announce` checks the panel's own rows against the re-read page with the same `isEditable` the views use. When none of them is still editable, the notice goes to the view through `onEditorGone`, and the view shows it in a shared `OutcomeNotice` (same role, tone and focus behaviour) above the list. `NOT_SAVED` is added only to rejections (403/404/409), never to an uncertain result. A failed re-read (ApiError) keeps the notice in the panel. That is correct, because `refresh` keeps the rows on screen, or switches to the error state when access is lost.
- QA-1-2 fix: the evidence counter now lives next to `caseRevisions` in `setup.mjs` and is cleared by `resetSetup()`. `server.mjs` is unchanged, and the existing import cycle is still lazy-only.
- Tests: 2 unit tests, 2 e2e tests (Rules as admin, Finance as finance_lead, readonly after load) and 1 mock test. No existing test was weakened. Gate PASS on this head.
- Impact on the rest: the in-panel notice moved into `OutcomeNotice` with the same markup. Focus now runs on every new notice object, as before. The phone layouts have no panel and are unaffected.

## Findings
- TECH-2-1 | non-blocking | low | frontend | The page-level callout can say "the Set a rule panel has closed" while a panel is showing. `announce` checks only the panel's own components (`SetRulePanel.tsx:77-79`). The view decides whether the panel renders from every editable row in the re-read (`RulesView.tsx:57,110`) or in the group (`FinanceRulesView.tsx:104,130`). If the re-read drops the panel's rules but makes a different rule editable, the callout reports the panel closed and the panel stays open on the other rule. Separately, Rules never clears `closedNotice` (`RulesView.tsx:53`). If a later Show more brings editable rows back, the panel reappears under a stale "panel has closed" message. Finance clears it when a disclosure is toggled. Both cases are unlikely, and no write is unsafe. Expected: decide from the same set the view uses (for example, pass `editable` membership through, or let the view compare before and after), and clear `closedNotice` in RulesView when the panel renders again.

## Verified
- QA-1-1 | verified | Code path read in full. Unit tests "403 that leaves no editable row…" and "finance: a group whose only editable row loses its right…" (`tests/setup-rules.test.tsx`) check the exact text (`FORBIDDEN.message` + `EDITOR_GONE` + `NOT_SAVED`), that the region is gone, that focus is on the alert, 1 PUT and 2 reads, a single alert, and that Finance clears the callout on the next disclosure. The e2e tests in `e2e/setup.spec.ts` cover the readonly-after-load path on Rules and Finance, with focus, a panel count of 0, 10 rows kept and axe clean. Gate PASS on edc4763 (408 unit tests).
- QA-1-2 | verified | `resetSetup()` sets `uploads = 0` (`mock/setup.mjs`). `evidence.mjs` uses `nextEvidenceId()`. The mock test checks EV-1, then EV-2, then a reset, then EV-1.

## Notes
- TECH-1-1 to TECH-1-4 (round 1, non-blocking) are deliberately out of this round's scope (build.md). They still stand as follow-ups. TECH-1-1 is related to TECH-2-1: the closed-panel check uses the same first-page re-read as the view.
