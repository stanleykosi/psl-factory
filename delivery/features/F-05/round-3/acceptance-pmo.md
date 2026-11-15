VERDICT: PASS
COMMIT: 0758d3e3f8568c084ed88b1c37a05f0641d62510
REVIEWER: pmo-acceptance
AUTHORITY: PMO acceptance (delivery acceptance only; product acceptance, merge and release keep their own authorities)

## Summary
- Scope is the one task FE-M2A (Start work on the contract mock, v6 repointed and then v7 types from the base merge). Technical, security, UI, UX and integrated QA all passed on this exact head. QA ran 21 browser journeys and 14 API calls on a build newer than the head commit.
- The only blocking findings in the extra round (SEC-3-1 and TECH-3-1, the `//` bypass in `safePath`) are VERIFIED by technical, security and QA. Every other blocking finding from rounds 1 to 3 (UX-1-1, UI-1-1 to UI-1-12, TECH-2-1, TECH-2-2, TECH-2-4) is VERIFIED. No blocking finding is open.
- This is acceptance of the frontend slice on the mock only. The backend, T-START and FE-CONNECT-1 are not delivered. Server-side duplicate handling after a person leaves an uncertain drawer (PMO-0-2) is not proved by anything in this round.
- Product acceptance is still pending and required (new client flow, minutes and change without proof, "can't start here yet" copy with no board). This PASS does not stand in for it.
- One record gap: the delivery gate in feature.json was last recorded at 230edd6, not at this head (PMO-3-1, non-blocking, run it before merge).

## Findings
- PMO-3-1 | non-blocking | medium | pmo | The recorded gate (round-3/checks.md, feature.json `checks`) is at 230edd6, not at head 0758d3e (merge of the base plus the safePath fix). The builder reports `checks.sh` exit 0 with 907 tests at the head (round-3/build.md, Extra round > Validation), and QA served a fresh build of the head. But the tool did not record a gate on the head, and so did not record the protected-path check for the merged diff. Expected: a recorded gate PASS on 0758d3e with no protected paths changed. Actual: not recorded. Run the gate on the head before merge. I did not re-run it (read-only role).
- PMO-3-2 | non-blocking | low | pmo | The spec text is stale in two places that QA found. Criterion 3 says pm's direct open shows no "change line"; the build shows it on purpose (round 2, UI-1-5, to match the boards). Criterion 12 says "1 things to fix"; the build says "1 thing to fix" (UX-1-2, verified). Both are accepted behaviour, not defects. Update spec.md or tell product acceptance so the checklist is not read literally.
- PMO-3-3 | non-blocking | low | pmo | feature.json `operation_ids` is empty although the readiness lists E-LINES, E-LINE-OPTIONS, E-WORK-START and E-ME. Coverage is evidenced instead by QA's API journeys (all three plus `startable_lines`), `start-work-mock.test.ts` (v6/v7 schema checks for every response) and the component tests. Record the IDs on the feature so the dashboard does not show them as uncovered.
- PMO-3-4 | non-blocking | medium | product | Desktop visual scores fell 7 points in the extra round (SCR-04 desktop 92.7 to 85.0, lines 92.9 to 85.1, change 94.6 to 87.0). The builder and D-49 say the cause is the page behind the drawer: the SCR-04 boards draw the old My work, which F-02 replaced. The UI review accepted this at this head, with coverage with exceptions at 100. This is provisional per D-49. The design engineer should either redraw the SCR-04 backdrops or confirm the exception, so a later fidelity gate does not read 85 as a regression.

## Verified
Checks against what was agreed:
- Acceptance criteria. Every part has passing evidence at this head from the routed reviews and QA:
  - Button visibility and `default_line` versus chooser (pm opens the invoice drawer, ceo opens "Choose a line" with 8 lines): QA J-journeys.
  - Success path to `/work/W-1401` with one POST and CSRF header: QA, browser and API.
  - 422 inline with a new key, 409 keeping typed values with no automatic resend, 403 keeping values, 401 signed-out state with `next`: QA.
  - Double press sends one POST. 500 and network loss lock the fields; "Check again" reuses the same key and body and gets the stored 201.
  - Persona with no lines has no Start control.
  - Journey link safety: refused values include `//evil.example`, `/.//evil.example`, `/%2e//evil.example`, `https://`, `javascript:` and `http://localhost:4611//evil.example`. Same-origin path with query and hash is linked.
  - Accessibility (axe, focus, Esc, Tab trap, 390 sheet) is covered by the e2e suite recorded in build.md round 3 (93 tests) and the UX review. QA did not re-run axe; I rely on those, not on QA.
- Tasks and operations. FE-M2A is the only task. The endpoints E-LINES, E-LINE-OPTIONS, E-WORK-START and E-ME (`startable_lines`) are all exercised. Nothing outside scope is reported landed: Finance and payroll drawers, proof and evidence fields, money fields, `finance_import` lines and SCR-23 are absent. The merge of the base in the extra round (conflicts in `package.json`, `client.ts`, `schema.d.ts`, `tests/api-schema-drift.test.ts` took the base) is recorded in build.md with the reason. I did not run `git diff` against protected paths on this head (see PMO-3-1).
- Blocking findings. All VERIFIED (list in Summary). Open non-blocking items, each with a named owner and none an accepted risk needing an authority: TECH-1-1, TECH-1-4 (frontend), TECH-1-2 (backend: look up the idempotency key before the revision and line grant), TECH-1-3 and TECH-1-5 (integration, version names in other lanes' tests and the rebase re-check), UX-1-4 (frontend, cosmetic), TECH-2-3 (backend, `next.summary` separator), SEC-2-1 (the security review verified it at this head, so only the record lags; ask the tool to mark it verified), UI-2-2 (product, wording of D-16).
- Handoff notes the spec requires. build.md round 3 carries the backend notes (TECH-2-3, the v7 proposal), the reasons for the left items, the extra-round merge, and the fidelity table. QA's evidence is in `round-3/qa-evidence/` (API commands and answers, browser journeys, screenshots).
- Parent package status. Nothing in the round files claims more than the frontend slice on the contract mock. QA says plainly that no real backend exists. I accept that framing and ask that no one report FE-CONNECT-1 or T-START as done on the strength of this feature.

## Not proved (carried forward, not blocking this slice)
- Backend behaviour. Everything ran against the contract mock (:4612). The mock checks the idempotency key after the line grant and answers a replay with the same stored 201. Whether the real backend does the same is unknown. If it checks the revision first, a start that already happened would return 409 `stale_revision`, and the drawer would offer a new key and could start the work twice. This is TECH-1-2 and must be settled as part of T-START and FE-CONNECT-1.
- PMO-0-2 after leaving. The key is discarded when the drawer closes. If a person closes an uncertain drawer and starts the same line again, a new key goes out. No test, frontend or backend, shows the second start is refused or merged. A server-side duplicate rule on line, case and revision is needed. Until then, the "never starts the same work twice" promise holds only inside one open drawer.
- Fault injection. The 500 and network-loss cases were injected in the browser with `page.route`, not by the server. The 409 "reloaded revision" is the same value as before because the mock returns the same one.
- TECH-2-4 (proof field plus duplicate problem) is covered by a component test only; the mock cannot produce it in the browser.
- Product acceptance of the "You can't start this line from here yet" copy and of minutes and change without a Proof field.
- The mobile fidelity scores (75 to 86) rest on the bottom-sheet decision (D-02/D-16) and the frame bar (D-08). They are exceptions, not passes.
