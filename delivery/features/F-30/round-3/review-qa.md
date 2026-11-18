VERDICT: PASS
REVIEWER: qa
COMMIT: 159262446042b5ff19fc5de2a8a089bb654b02fb
AUTHORITY: integrated QA (frontend against the contract mock)

## Summary
- I tested head 3a2884d4 (base dlv-00 8524af3c plus this branch) on the coordinator's production build. The app ran on http://localhost:4833 (built 20:51, after the head commit at 20:38) against the contract mock on 4832 with `FRAME_FIXTURES=1`, as persona pm. I did not start, stop or rebuild anything. The browser script is `qa-f30/qa8.cjs` in the scratchpad. I reset the mock afterwards (`POST /__mock/reset` returned 204).
- QA-2-1 is fixed. An empty "Post update" or "Record a reply" now shows a top "N things to fix" summary (role=alert) whose links go to each field, and focus lands on the first invalid field's control. This holds at 1440 and in the phone Drawer at 390, whether submitted by click or by Enter. QA-2-2 and QA-2-3 are also fixed.
- Regression e2e: `MOCK_PORT=4832 npx playwright test -c <scratch>/qa-f30/pw.qa3.config.mjs e2e/issue-detail.spec.ts e2e/workspace.spec.ts e2e/work-item.spec.ts e2e/project-tabs.spec.ts e2e/weekly.spec.ts e2e/minutes.spec.ts` gave **167 passed (3.7 m)**, exit 0. That is 165 in round 2, minus the old unknown-id test, plus the new 403 and 404 tests at two widths. The run used the 4833/4832 stack, so I needed no second build; the round-2 note on routes-manifest explains why.
- Unit: `npx vitest run tests/issue-detail.test.tsx tests/issue-assign-mock.test.ts tests/workspace-step.test.tsx tests/weekly.test.tsx tests/minutes.test.tsx` gave 158/158.
- Carried forward from round 2, with an impact note: the round-3 diff touches only StepForm validation (focus target and an opt-in summary), the AssignForm option hint, Workspace passing `summary` on the issue line, and tests. Nothing else is affected: persona controls, the three writes and their double-press and idempotency handling, the 422/409/500/network step and assign failures, the escalation hand-off, 401/403/404 access, the register row and the phone Drawers. The e2e above covers them again and passed. Not proved, as in round 2: real backend authority and tenant isolation (the mock has no tenant concept); the step `uncertain` reconcile panel and the 60 s 409 rule (unit tests only); real escalation creation.

## Findings
None.

## Verified
- QA-2-1 | verified | qa8.cjs ran on W-2411 "Post update" at 1440 and in the 390 Drawer, by click and by Enter. Each empty submit sent 0 POSTs. The summary read "2 things to fix · Add update type to continue. · Add update to continue." (role=alert). The focusin trace went submit, then summary, then the first Update type radio (Acknowledge), and focus ended on that radio, not the submit. The first link focuses that radio and the second focuses the Update textarea. After choosing "Started", resubmitting showed "1 thing to fix" with focus on the textarea. A valid submit sent 1 POST and showed "Done: update posted." On W-2412 "Record a reply", at both widths and by click and Enter, the summary read "1 thing to fix · Add reply to continue." Focus ended on the Reply textarea, and the link focuses it. The Drawer was 844/844 high with no sideways scroll. Other lines draw no summary (only Workspace passes `summary` on `issue_followup`), and the workspace, weekly and minutes e2e plus their unit tests stay green.
- QA-2-2 | verified | The W-2413 owner options at 1440 and 390 read "Tunde Bello · PM · Raised it", "Engineering · Team · recorded by PM" and "Lagoon Health support · Client · recorded by PM · Outside party". The kind word no longer repeats the role.
- QA-2-3 | verified | `e2e/issue-detail.spec.ts:144` now sends `x-mock-scenario` 403 and 404 on the W-2411 item read only. It asserts the visible text "You can’t open this work item", that neither the title nor ISS-0233 appears, and an axe check. All four cases (403 and 404, at desktop 1440 and phone 390) passed in the run above. Because the test asserts the not-open text is visible, it now fails if that view is missing.

## Notes
- A server 422 on a step with no named fields (the mock's `{"code":"invalid","message":"Check the highlighted fields and try again."}`) shows the form-level callout with no summary, and focus stays on submit. This is correct, since no field is named. A 422 that does name fields goes through the same `summarise` path. It is covered only by code review, because the mock never names step fields.

## Update for head 15926244 (diff 3a2884d4..15926244)
- server.mjs and workspace.mjs: merge added F-29's E-DOCUMENT read (falls through to F-23's rule) and F-28's `.next.<audience>` lookup (falls back to `.next`); F-30's E-WORK-ASSIGN, E-PROJECT-TAB and step/sidecar handling are unchanged, with no duplicate or shadowed branches.
- Sections.tsx and workspace.css: the `ws-table--stack` phone rules apply only to tables with a tag column. F-30's issue fixtures (W-2411 to W-2414) have none, so their tables and timeline are unaffected. The `data-label` attribute and the Unknown receipt fallback only touch F-28 channel items.
- proposals.ts and mock-contract.test.ts: `project_tab` sits beside F-30's overlay keys and the stripping and link schema agree; project-tabs.test.tsx keeps the F-29 Documents cases and F-30's tab-link cases; BACKEND-HANDOFF.md keeps all sections, with no conflict markers. A targeted vitest run of project-tabs and issue-assign-mock passed (38 of 38); the coordinator's checks (2268 tests) and e2e (115 of 115) cover the rest.
- Verdict unchanged.
