VERDICT: PASS
COMMIT: a24195b3bd085eb5730a9155bce08b2e22fc9e92
REVIEWER: pmo-acceptance
AUTHORITY: PMO delivery acceptance (delivery only; client/product acceptance, merge and release keep their own authorities)

## Summary
- D-193 pre-merge re-check of the second main sync. The head moved d5c20396 to a24195b3, a merge of origin/main 1e78793f (F-111 #116 and F-87 #113). The branch reflog confirms the merge commit.
- The sync changes nothing PMO accepts for F-75. F-75's frontend/src files are unchanged across the sync (technical re-check ran `git diff d5c20396 a24195b3` over them, empty). The one shared file I read, `frontend/tests/next-config.test.ts`, keeps both allow-list entries with no conflict markers.
- Scope holds: FE-CONNECT-1 only, SCR-11 and SCR-29, read-only. F-111 and F-87 content arrived through main and is not F-75 scope. The Registers and Actions tabs import none of it.
- Evidence carried from round 2 stands on a24195b3: screen code is unchanged, GitHub frontend-checks passed on a24195b3 (run 45486815610, coordinator-reported and not re-read by me), and product acceptance is carried over under D-188 in acceptance-product.md.
- No blocking finding is open. Still open and non-blocking: PMO-2-1 (stale criteria in feature.json), PMO-2-2 (five "pending" extras entries) and PMO-2-3 (criterion 20 live-data proof and a production-build e2e run).

## D-193 re-check (a24195b3)
What I checked, on this run (no shell was available, so I did not run `git` myself):
- Head: `.git/logs/refs/heads/fe-connect-1-registers-actions-tabs` shows `d5c20396 -> a24195b3` as "Merge remote-tracking branch 'origin/main' into fe-connect-1-registers-actions-tabs". The head is a24195b3.
- Shared test file: `frontend/tests/next-config.test.ts` lines 136-137 hold `'project-sections-model.test.ts'` (F-75) and `'issues.mjs'` (main). No conflict markers. This is a one-line allow-list change, not F-75 behaviour.
- F-75's own code: the technical re-check ran `git diff d5c20396 a24195b3` over every F-75 frontend/src file and got an empty diff. I did not re-run it.
- What main brought in: F-111 (issue follow-up, work-item controls) and F-87 (workspace command and write-lock hooks, `LineAdapter.Actions`). Neither is in F-75's task or screens. The technical grep found no import of them from the Registers or Actions tabs. `mock/server.mjs` routes `issues.mjs` first, but that route does not match the register or action list reads, which fall through unchanged.
- Acceptance: the 21 spec criteria and the task scope are unchanged. Round 2's evidence is unaffected because no screen, model or mock route for these tabs changed.
- Lens effect: none. Nothing from the sync changes the PMO judgement, so this re-check passes.
- Disclosed: the criterion 20 gap (live rows, live `live-lead` run) was accepted in round 2 as PMO-2-3 and is not changed by this sync.

## Findings
- PMO-2-1 | non-blocking | medium | pmo | `feature.json` `acceptance_criteria` still holds the 1.22.0 list, not the re-specified 1.24.0 criteria in `spec.md` (D-185). Examples: criterion 2 says "no count badges ... no Actions header counts", criterion 3 says "no AGE column", criterion 10 says no "From" line. The build shows all of these, as `spec.md` (criteria 3, 4, 11, 12) and product acceptance say. I judged against `spec.md`. Expected: the record carries the 21 spec criteria. Actual: 17 stale criteria. Refresh the record from `spec.md`. Still open on a24195b3.
- PMO-2-2 | non-blocking | low | pmo | `fidelity-exceptions.json` lines 130-150: the five `extras_not_gating` entries still read "pending sign-off (questions-batch B35)" or "pending design engineer". The 18 gating exceptions and the four visual waivers carry the D-207 approval. Expected: each entry shows the D-207 approval. Actual: five entries show "pending". Update them. Still open on a24195b3.
- PMO-2-3 | non-blocking | medium | frontend | Criterion 20 (live backend as `live-lead`, real rows, badges and Actions header against live `total` and `counts`) is not met beyond the empty state. QA's e2e run shows 4 of 35 "exactly one request" checks failing under `next dev` (registers line 126 and the Try again test line 217, at 1440 and 390). QA attributes it to the StrictMode double effect, and F-71 tabs double the same way. It is not proved under `next start`, and the gate does not run e2e. Expected: a production-build e2e run, or tests that tolerate the dev double read, plus one live run on a seeded project. Actual: neither. Carry both into the next live-data pass. Still open on a24195b3.

## Verified
- UX-1-1 | verified | Technical, UX and QA reviews confirm focus lands on the first new row (1440) or card (390) after Show more, on d5c20396. Re-checked on a24195b3: the sync did not change `RegistersTab.tsx`, `ActionsTab.tsx` or `useFocusAfterMore.ts`.
- UI-1-1 | verified | UI review: column order ISSUE, WHAT, SEVERITY, OWNER, STATE, AGE, with AGE right-aligned and last. Screen code unchanged by the sync.
- UX-1-2 | verified | UX review and QA: the Severity note shows on Issues only. Unchanged on a24195b3.
- TECH-1-1 | verified | Technical review: the merge with F-71 is clean beyond the three named spots. QA confirms Money, Milestones, Registers and Actions load with no errors. `?page=0` and `?page=x` answer 422. Unchanged on a24195b3.

## Earlier evidence (round 2, d5c20396, retained)

### Summary (as judged on d5c20396)
- Round 2 passed head 286b4105. Main eb100065 was merged once, giving d5c20396. F-75's own diff and the sync shared exactly two test files, `frontend/tests/next-config.test.ts` and `frontend/tests/demo-mock.test.ts`. `RegistersTab.tsx` and `ActionsTab.tsx` did not change in that sync. The ci-mode checks passed on d5c20396 (GitHub Actions run, success). Both shared test files pass (37 tests).
- The `next-config.test.ts` one-entry-per-line format is what main's #117 requires. F-75's one allow-list entry `'project-sections-model.test.ts'` sits on its own line (line 136).
- Scope: task FE-CONNECT-1 (D-180 connect exception) only, screens SCR-11 and SCR-29, read-only. The changed paths are the spec's lane files plus the shared files it names (`tabsModel.ts`, `TabParts.tsx`, `DocumentsTab.tsx`, `useProjectTab.ts`, `useFocusAfterMore.ts`, mock and fixtures, tests). F-75's own diff touches no protected path (D-200, base moved to eb100065). No operation IDs are recorded for this feature.
- Evidence: gate PASS on 286b4105 (round 2 attempt 1, GitHub Actions run 45431227073). Technical, UX, UI and integrated QA PASS on 286b4105. Product acceptance PASS under D-184/D-207, carried over to d5c20396 under D-188/D-193.
- Held or unproved, accepted as held in round 2: the live qa-seed project is empty, so only the empty state is proved live (200 bodies validate against the 1.24.0 schema with Ajv; a stubbed browser render shows the empty states). Live rows, live counts, live Show more, the `live-lead` account and a live browser render are not proved. They are proved only on the mock.
- Two edits to other lanes' tests are in scope and justified: `tests/issue-assign-mock.test.ts` (ISS-0233 is a plain row with no `work_id`, spec conflict 4, accepted under D-182; the edit keeps `not.toContain('W-1002')`) and `tests/mock-live-money.test.ts` (an unreadable page answers 422 `invalid_filter`, the live contract; the technical review checked it against `work.py:158`).
- Delivery PASS only. The parent package status stops at this slice: Money and Milestones are F-71's, and Documents and Journey are untouched. `feature.json` still shows completion blocked and release not authorised, which is correct.

### Coverage by criterion (spec.md, 21 criteria, as judged on d5c20396)
- 1 to 19: covered by `project-sections`, `project-sections-model`, `mock-live-project-sections`, `mock-project-tabs` and `project-tabs` tests (263 tests in 15 files passed per `build.md`, and the unit-test CI step passed). QA's manual mock walk confirmed 1, 3, 5, 7, 9 and 11 to 16 at 1440 and 390.
- 8, 10 and 11 (Show more and failed-more): the P-0102 Issues Show more was walked (QA, UX). The failed-more Retry path and Actions Show more were covered by render tests only. The mock has no Actions paging.
- Not walked in the browser: the amber `Unknown` due and null-owner cases (unit tests cover them).
- 20: partial (see PMO-2-3). 21: axe, no sideways scroll and keyboard keys passed in e2e at both widths. Focus after Show more was verified by hand.
- Criterion 13 (due "13 Nov" in Africa/Lagos): unit test passed. QA saw "13 Nov" in the browser.

### Design and sign-off trail
- D-182 hides and conflicts 1 to 8 are accepted in batch (D-182, "accept all recs"). Product acceptance is recorded under D-184 and carried over under D-188/D-193 to d5c20396 and now to a24195b3 (see acceptance-product.md).
- B35 (i) to (iii) signed by the main coordinator under D-207 (24 Nov 2026), including the four D-83 visual waivers (81.1, 76.6, 86.2, 78.0; coverage is 100% after exceptions). These were not signed by the design engineer personally: the coordinator used the engineer's delegation, which excludes anything touching the database. This feature has no database surface.

### Handoff of open non-blocking items
Still OPEN in `feature.json`, none blocking, carry forward:
- TECH-1-2 (test timeout flake in `project-sections.test.tsx:241` under parallel load); owner frontend; raise the `until` budget.
- TECH-1-3 (a null owner on an action reads "Owner needed"; the contract says it should not be null); owner frontend, low.
- UX-1-3 (a closed issue with a null owner shows "Owner needed" in signal ink); product call, owner design engineer.
- UI-1-2 to UI-1-5 and UI-2-1 to UI-2-3: covered by the D-207 exception entries and waivers. Close them in the record (see PMO-2-2).
- UI-1-6 (phone register switch and phone card age, not on the mobile board): accepted under B35 (ii), design engineer to confirm taste.
- Escalations: a live section with no board. Left out of the switch (spec conflict 6, option 1). It needs a board if it is ever wanted.
- Follow-ups not in this feature: the per-action proof upload and every write (B-37), a detail route for issue, change, emergency, bid and action rows, a per-row overdue flag, and an owner role label. Each needs a backend or design decision.
- Mock/live difference noted by QA: a page past the last returns 200 page 1 on live registers, and the mock's Milestones answers 404 (F-71's choice). Neither is changed here.
- The PASS does not cover merge, release or client acceptance.
