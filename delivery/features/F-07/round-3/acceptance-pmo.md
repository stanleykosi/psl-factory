VERDICT: PASS
COMMIT: 4e8a8c7d75957adbc9de381887453e0e5e11ecf4
REVIEWER: pmo-acceptance
AUTHORITY: PMO acceptance (delivery acceptance only; client/product acceptance, merge and release keep their own authorities)

## Summary
- Extra round (D-47) on head 4e8a8c7. Technical, UI, UX and integrated QA all PASS on this head. QA drove 12 of 12 browser journeys (10 at 1440, 2 at 390) and 22 API calls against the shared build of this head, and found no blocking item. UI re-ran the fidelity gate and got the builder's numbers.
- Scope is unchanged: FE-M3-PROJECTS (SCR-22 list and SCR-07 journey) on E-PROJECTS and E-PROJECT through the contract mock. Technical confirms the diff against the base touches only F-07 lane files plus the registration lines in `mock/server.mjs` and `tests/mock-contract.test.ts`. Tabs, money, E-PROJECT-TAB and E-DOCUMENT stay out.
- Every blocking finding in feature.json is VERIFIED: FID-1, UI-2-1, UI-3-1. No risk is accepted without an authority. D-50 (design engineer) waives the SCR-07-mobile visual score of 78.8; the fidelity tool still fails that board on visual, so the waiver is what makes it acceptable (D-33 covers the frame back-link exception).
- This head is proved only against the contract mock. Real grants, tenant isolation, real paging and real `status`/`total` behaviour are unproved. They belong to backend T-PROJECTS and FE-CONNECT-1.
- Product acceptance by the design engineer is still pending. This PASS does not replace it.

## Findings
- PMO-3-1 | non-blocking | medium | pmo | The recorded gate `round-3/checks.md` is for 2892f00, not this head. Technical states it did not re-run the full gate (it ran 271 tests in 7 files). The full gate on 4e8a8c7 (875 vitest tests, lint, typecheck, build) and the 111-test e2e run are builder-reported in `build.md`, not tool-recorded. Independent evidence on this head (QA's journeys, UI's fidelity re-run, technical's targeted tests) covers the behaviour, so I do not block. Expected: the coordinator re-runs `delivery/checks.sh` on 4e8a8c7 and records it before merge, as was done for F-05 (commit 54bc36a). If that run fails, this PASS lapses.
- PMO-3-2 | non-blocking | low | frontend | QA-3-1 / UX-3-1: "1 PROJECTS" is not pluralised (`frontend/src/features/projects/ProjectsList.tsx:472`). Cosmetic. Carry to a follow-up.
- PMO-3-3 | non-blocking | low | frontend | TECH-3-1: `tests/mock-contract.test.ts` still strips the v7 PROPOSAL fields from the E-PROJECTS and E-PROJECT bodies (`contractBody`, `PROPOSED_FIELDS` in `mock/projects.mjs`), though `build.md` says it is gone. The full v7 body is validated in `mock-projects.test.ts`, so coverage holds. Remove it and correct the build note in a follow-up.
- PMO-3-4 | non-blocking | low | pmo | Carry-overs still open in feature.json: PMO-1-1 (`operation_ids` is `[]`; set it to E-PROJECTS and E-PROJECT), PMO-1-2 (A-PROJECT's money half stays open until FE-M3-REPORT; milestones, documents, money, registers and actions are not proved by this feature), PMO-1-3, QA-1-1 (double-encoded case_id; recheck at FE-CONNECT-1), UX-2-2 (phone access to closed projects, product), UI-2-2 (title size, frame-owned).

## Checks against the PMO list
- Acceptance criteria 1 to 17: `build.md` maps each to tests or e2e, and QA's live journeys on this head cover list, Active/Closed/All with `status` omitted for Active, search, paging, journey order and links, empty, 404/403 naming nothing, 401 with `next=`, 500 with retry, persona none sending no request, unknown values shown as "Not known" and never as 0, and the Tola mascot. Not re-run by QA on this head (rest on e2e and unit tests, which the builder reports green): axe, focus rings and stale-response ordering. UX also did not re-run axe, 401, 500 and loading states.
- Tasks and operations: FE-M3-PROJECTS (list and journey slice) and E-PROJECTS and E-PROJECT are covered. Nothing outside scope landed. The v7 types are now aliased from the generated schema, with no contract edit or repoint in this lane.
- Docs and handoff: the spec's required product-acceptance list is in `build.md` and `round-2/build.md`. The extra-round fidelity reports and screenshots are in `round-3/` and are regenerable by the e2e command in `build.md`. QA's evidence is in `round-3/qa-evidence/`.
- Parent status: nothing in the round files claims more than the list and journey.

## Verified
- UI-3-1 | verified | Mascot image on SCR-07 confirmed by UI and QA on this head.
- FID-1 | verified | Phone back link comes from the frame (`usePhoneBack`) and the in-page link is gone, confirmed by UI and QA (Q11).
- TECH-2-1, TECH-2-2, UX-2-1, UI-2-1 | verified | Reconfirmed on this head by technical, QA and UI.

## Open for others
- Coordinator: re-run `checks.sh` on 4e8a8c7 (PMO-3-1) and fill `operation_ids` (PMO-1-1).
- Product acceptance (design engineer): pending. It should see the reduced boards, the Journey-only tab bar, the SCR-07-mobile waiver (D-50) and the phone back-link exception.
- Backend (T-PROJECTS) and FE-CONNECT-1: real grants, tenant isolation and real paging are unproved.
- Merge and release: not authorized by this file.
