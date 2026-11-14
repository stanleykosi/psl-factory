VERDICT: PASS
COMMIT: 195926d6854956a6918ef6199c0a5f57ce3a32ad
REVIEWER: pmo-acceptance
AUTHORITY: PMO acceptance (delivery acceptance only; client/product acceptance, merge and release keep their own authorities)

## Summary
- All 17 acceptance criteria have passing evidence on this head: checks.sh PASS (406 vitest tests, lint, typecheck, build), plus QA's independent rerun of `e2e/projects.spec.ts` (24/24) and its own drive of the list, journey, empty, no-access and persona-none pages at 390 and 1440 (review-qa.md).
- Scope matches FE-M3-PROJECTS (SCR-22 list, SCR-07 journey) and the E-PROJECTS and E-PROJECT reads. The changed paths are the F-07 lane files, the four-part `server.mjs` edit and the base merge (build.md integration note). Nothing under `src/shell`, `src/api`, `src/features/work-item` or `fixtures/work` changed. Tabs, the money report, E-PROJECT-TAB and E-DOCUMENT stay out and answer 501.
- Technical, UX, UI and QA all PASS on this head. No blocking finding exists. Two non-blocking findings are open (UX-1-1, QA-1-1) and carried forward. Spec line 229 was corrected by the coordinator (UI-1-1 closed), and the tests assert the corrected behaviour.
- Product acceptance by the design engineer is required and still pending. It must look at the reduced boards listed in build.md "Product acceptance (PMO-0-2)" and at the screenshots. This PASS does not stand in for it.
- QA was UI-only against the contract mock. Real grants, tenant isolation and real paging are unproved and belong to T-PROJECTS and FE-CONNECT-1.

## Findings
- PMO-1-1 | non-blocking | low | pmo | feature.json `operation_ids` is `[]`, but the scope is E-PROJECTS and E-PROJECT (readiness Scope, spec Contract). Expected: the feature record lists both IDs. Actual: empty, so tooling cannot trace the operations to this feature. Evidence in this folder (readiness.md, spec.md, build.md) names them and covers both, so acceptance rests on that. The coordinator should fill the field.
- PMO-1-2 | non-blocking | medium | pmo | The parent package status claim needs to stop at this slice. Architecture v6 `tasks.csv:27` makes FE-M3-PROJECTS the list and journey only, and lists A-PROJECT on it. The money half of A-PROJECT moves to FE-M3-REPORT (`tasks.csv:35`, which also lists A-PROJECT), and the tab acceptance A-PROJECT-TABS to FE-M3-PROJECT-TABS (`tasks.csv:34`). This feature proves only the JR-08 half of A-PROJECT (open a project, see every line and what is next, no grant gives 404). spec.md and readiness.md still say "first part", which is v5 wording. Expected: when FE-M3-PROJECTS is marked done, A-PROJECT stays open until FE-M3-REPORT passes, and no status says that milestones, documents, money, registers or actions work. Actual: nothing in the round files over-claims. build.md and review-qa.md limit themselves to the list and journey. This finding is a reminder for the coordinator's record update.
- PMO-1-3 | non-blocking | low | frontend | UX-1-1 and QA-1-1 are open and non-blocking, as the reviewers rated them. UX-1-1: lines with the same name give identical link text, so add a hidden "line, state" label. QA-1-1: a case_id with reserved characters is encoded twice (no effect with uuids and the mock). Neither blocks delivery. QA-1-1 must be rechecked at FE-CONNECT-1, and both go to the next round or a follow-up. They are named here so they are not lost.

## Checks against the PMO list
- Acceptance criteria 1 to 17: build.md maps each to a test or e2e. checks.md (PASS, commit matches the head) and review-qa.md (24/24 independent e2e, own drive of the main flows) confirm them. QA did not itself drive the 401, 5xx and network paths. These rest on the e2e `page.route` tests and the component tests, which QA records as passing in the e2e run (tests 2, 7, 17, 21, 22) and in checks.sh.
- Criterion 9 (persona none) is met under the corrected spec: the frame's "No sections are open to your role yet." with zero projects requests. build.md still calls this a "Deviation from the spec text", but that note predates the correction and the behaviour now matches the spec.
- Criterion 17: build.md lists the omitted elements, the Journey-only tab bar, the `server.mjs` lines and the screenshots. The screenshots sit in a scratchpad path outside the repo and may be gone, so the design engineer can regenerate them with the e2e command in build.md.
- Task and operation coverage: FE-M3-PROJECTS (list and journey slice) and E-PROJECTS / E-PROJECT are covered. No other task or operation landed. The builder's reported full e2e run had one failure (decide.spec phone-button colour), which belonged to F-04. The coordinator fixed it in PR #10, and it is already merged into this head. No F-07 file changed in that merge.
- Blocking findings: none exist, so none are unverified. No risk is accepted without an authority.
- Docs and handoff: the spec required build.md's product acceptance list, and it exists. No other doc or handoff note is required.
- Architecture mapping: the E-PROJECTS and E-PROJECT schemas are unchanged from v4 to v6, so the mock loading v4 matches. Readiness noted the same for v5. No contract edit or repoint landed.

## Verified
None (round 1, no fixes to retest).

## Open for others
- Product acceptance (design engineer): pending. It is required before the feature is done.
- Merge and release: not authorized by this file.
