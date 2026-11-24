VERDICT: CHANGES
COMMIT: 9f9dc026b5e62762de288ca468aa8a4380a649f1
REVIEWER: pmo-acceptance
AUTHORITY: pmo

## Summary
- Delivery matches the agreed scope (F-87a): the five work-item controls, the shared seams for lanes B and D (useWorkCommand JSON and multipart, LineAdapter.Actions, LineContext.state, read(ref, ctx), lines/index.ts) and the F-85 lows. Only the 19 listed files changed, none protected. The F-93 "Confirm what happened" panel is not built, as agreed.
- Round 3 gate, technical, UX, UI and QA all pass on this head. Blocking TECH-1-1 and TECH-2-1 are VERIFIED. TECH-3-1 and TECH-3-2 are open, low and non-blocking. UX-1-2 is still FIX_SUBMITTED and non-blocking.
- One criterion lacks passing evidence on this head. Criterion 21 asks for a live "Check what happened" 202. The QA run found no live item that lists `reconcile`, so only Pause and Continue (202 on work 1) are proved live. Resume, Cancel, Check and the live error paths are mock-only (round-3/review-qa.md).
- Per the contract, missing evidence is a pmo-owned blocking finding (PMO-3-1). It clears with a live proof or a named person's written acceptance of the gap. No code change is needed.
- This is delivery acceptance only. Client acceptance (required, pending), merge and release keep their own authorities.

## Findings
- PMO-3-1 | blocking | medium | pmo | Criterion 21 (live 202 on "Check what happened", plus no row when nothing is listed) has no passing live evidence on 9f9dc026. QA signed in as qa-seed on Django 8020. Items 1, 2 and 4 list only `background` and `cancel`, so reconcile and Resume could not be pressed. Cancel was not pressed live. The 403, 409, 422, timeout and 5xx paths were checked on the mock only. Expected: a live record per criterion 21, or an acceptance by a named authority. For the CEO demo path (D-201), Pause and Continue are live-proved with a re-read, and Cancel's dialog opens live and "Keep it" sends nothing. Check what happened and Resume would be shown to the CEO with no live proof. Recommended route: (a) the lane C coordinator gets one live work item that lists `reconcile` (and one that lists `resume`) from the backend seed owner, QA presses them and records the 202 or 200 JSON, then PMO re-accepts; or (b) the design engineer, who owns acceptance for the demo path, records in readiness.md or BUILD-DECISIONS that criterion 21 is accepted as mock-only for the demo with these controls not shown live. I cannot grant (b) myself. | delivery/features/F-87/round-3/review-qa.md (Summary, last bullet; Notes, Live detail)

## Verified
- TECH-1-1 | verified | VERIFIED in feature.json; technical round-3 retest on 9f9dc026 (tab and failed-panel tests, 43 of 43)
- TECH-2-1 | verified | VERIFIED in feature.json; technical retest plus QA browser check on 4121 with w500 (History and Back stay locked, one POST) at 1440 and 390

## Checked
- Scope and tasks: task FE-CONNECT-1 only. `operation_ids` is empty in feature.json. The work is frontend-only with no backend or contract edit, so no operation mapping applies. Nothing outside the 19 listed files landed. Build note: the head is the coordinator's merge of origin/main 4a88c26b (D-200), with one test-only conflict resolved by keeping both sides.
- Criteria 1 to 20, 22 and 33: covered by the round 3 gate (CI run 45411069067, lint, typecheck, unit tests and build all success), the technical and QA reviews and the e2e and unit tests named in build.md. Criterion 19 (v7 path unchanged) is covered by the unchanged useWorkspaceStep tests.
- Board decisions LC-Q2 and LC-Q5 (D-182) and LC-Q12 and LC-Q13 (D-183) are accepted and reflected in the build. Design gate is the recorded EXCEPTION; no new screens beyond the spec.
- Docs and handoff: the Actions seam is documented in adapter.ts with an example, as the coordinator note required. build.md names the one full-suite failure (cash-forecast, a 90 s timeout under load, passes alone) and CI later ran green. The spec's remaining records (BUILD-STATE and similar) are the coordinator's at merge.
- Parent package status: the F-87 record claims only F-87a. The "Confirm what happened" panel, delivery-observations and proofs stay with parked F-93. `release_invoice`, `adopt_profile`, `/reviews` and weekly-report correct are untouched. The spec's criteria 3 (panel part) and 23 to 32 are not claimed here.
- Open non-blocking items to carry: TECH-3-1 (lock store survives sign-out in the same tab; call resetScopedWriteLocks on sign-out), TECH-3-2 (add the line `Actions` History-and-back tests under the slot suite), UX-1-2 (callout can sit beside a new-state tag after a dropped connection; no fix recorded). None has an owner-accepted risk, and none blocks delivery.

## Notes
- If PMO-3-1 is resolved by route (a), no new build round is needed; the same head can be re-accepted with the live evidence. If TECH-3-1 and TECH-3-2 are fixed in the same follow-up, that is a new head and needs its own gate.
