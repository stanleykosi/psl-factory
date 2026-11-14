VERDICT: PASS
COMMIT: 604e1b0a0f8fb3ac2cee49124f70370b1343e6de
REVIEWER: pmo-acceptance
AUTHORITY: PMO delivery acceptance (not client/product acceptance, not merge or release)

## Summary
- Head 604e1b0 is accepted as delivered against the spec for F-11 (Setup frame and Rules, FE-M3-SETUP rules part only). The gate, technical, UX, UI (six boards 93.4 to 99.8, 100% coverage after exceptions), security and integrated QA all passed on this exact head.
- Both blocking findings (QA-1-1, FID-2-1) are VERIFIED. Every other open finding is non-blocking and low, and none is a hidden spec gap.
- Scope held except one disclosed shell addition: the optional `note` on the phone bar (`src/shell/**`). This breaks spec AC 26 ("shell diff empty") and D-34 already moves it to its own frame PR. F-11 must drop it on rebase before merge (PMO-3-1).
- Unproved: no real backend. T-SETUP and the proposal fields exist only in the mock. This is delivery acceptance only. Client/product acceptance (required, pending), merge (high risk, held for the design engineer) and release are untouched.

## Findings
- PMO-3-1 | non-blocking | medium | pmo | Spec AC 26 and the Ownership lane forbid any edit to `frontend/src/shell/**`. Round 3 changed `PhoneBar.tsx`, `AppShell.tsx` and `shell.css` (optional `note`, "RULES" label) so the phone boards could pass. The checks gate reported no protected-path change, so the gate does not catch this. The change is disclosed in round-3/build.md and recorded in D-33 and D-34. Expected before merge: F-11 is rebased onto the frame PR (branch fe-frame-phone-note, D-34) so its own diff touches no shell file, and it takes the TECH-3-2 `margin-left: auto` line from that PR. Actual at this head: the shell change is in F-11's diff. Accepted at this head only because D-34 gives the route. If the frame PR does not merge first, AC 26 is not met and the merge needs a fresh decision.
- PMO-3-2 | non-blocking | low | pmo | The "Back to Setup" fidelity exception (D-33) holds the phone boards at 100% coverage and is provisional, approved by the coordinator. Without it coverage is 92.9 / 87.5 / 66.7%. A permanent decision by the design engineer is still needed. It is listed so it is not mistaken for a final approval.
- PMO-3-3 | non-blocking | low | pmo | `feature.json` has `operation_ids: []` although the spec names E-SETUP-RULES, E-SETUP-RULE-SAVE and E-EVIDENCE-UPLOAD, and `baseline.architecture_manifest_sha256` is null although the spec cites v7 digest f6231d20…b624. Record gap only. The operations are covered (below). Fill the record before merge so traceability reads correctly.

## Verified
- QA-1-1 | verified | VERIFIED in feature.json (technical, round 2). Re-proved on this head by QA: e2e on Rules and Finance, plus a live mid-edit withdrawn-right run with one focused alert and no Save button.
- QA-1-2 | verified | VERIFIED in feature.json. QA re-ran reset then upload twice, got EV-1 both times, and the sha256 matches the content.
- FID-2-1 | verified | VERIFIED by reviewer-ui. Phone visual 99.8 / 99.1 / 99.7.
- TECH-2-1 | verified | VERIFIED. Two new unit tests, which fail on round-2 code.
- SEC-2-1 | verified | State VERIFIED in feature.json by technical, with a security reopen as a non-blocking test-gap note. The test it asked for was added in 604e1b0 and passes, so I rely on the VERIFIED state.

## Acceptance evidence
- **Criteria 1 to 25** have passing evidence on this head: gate (lint, typecheck, 419 unit tests, build), 42 e2e tests run by the builder, and QA's 17 e2e tests in `setup.spec.ts` against the shared build. QA also did direct API checks (403/404/409/422, CSRF, upload sha256), browser journeys for uncertain-effect and withdrawn-right paths, and axe at 1440 and 390. The 25 criteria were not re-listed one by one in a QA table. They are covered by the named e2e, unit and mock tests, and by the technical, UX and UI reviews on the same head.
- **Criterion 25 (design fidelity):** all six SCR-13 boards PASS at 100% coverage with approved exceptions, visual 93.4 / 96.2 / 97.9 (desktop), 99.8 / 99.1 / 99.7 (phone). Both the builder and the UI reviewer ran it and agree. Reports are in `round-3/fidelity/` and `round-3/fidelity-review/`.
- **Criterion 26 (additive edits):** met except for the disclosed shell change (PMO-3-1). The api, architecture, package files and delivery config were not changed.

## Task and operation coverage
- **Task FE-M3-SETUP**, R-SETUP rules part only. The v7 task line says the other Setup tabs belong to FE-SETUP-ROLES, -DELEGATION, -TEMPLATES, -PAYROLL-FIELDS and -COSTING. Those open as reserved routes with the shared empty state, and nothing from them landed.
- **E-SETUP-RULES (GET)** is covered by Rules, Finance and Delivery views, paging, counts, empty, 401/403 and server errors.
- **E-SETUP-RULE-SAVE (PUT)** is covered by revision 0 first save, 409 reload-and-clear, 422 field mapping, uncertain-effect recovery, double-click safety and CSRF.
- **E-EVIDENCE-UPLOAD (POST)** is covered by the setup-local Proof field and mock handler, disabled where no `proof_case` exists.
- **Acceptance IDs:** A-SETUP and A-SETUP-RULES-VIEW (frontend half) and A-ACCESSIBILITY are covered by the tests above.
- **Out of scope respected:** no Delegation, Roles, Staff, Templates, Payroll or Costing screens. No editor beyond role lists. No sample-data tag. No new dependencies.

## Docs and handoff
- Round-1 build.md lists the backend proposals (`proof_case`, `cursor`, `expected_revision` minimum 0, the overlay fields) for the backend developer, as the readiness and spec require. Round-3 build.md records the shell change, the exception request and the fidelity table.
- Review follow-ups for the next session, all non-blocking and open: TECH-1-1..4, SEC-1-1 (Save during upload), SEC-1-2 and SEC-1-3 (backend rules for `evidence_id` and `proof_case`, for T-SETUP), UX-1-1/2-1 carried, UX-1-2/2-2/3-1 (phone back link goes to the reserved Roles page), TECH-3-1 (stale notice hidden, not cleared), TECH-3-2 (note placement with the sample tag, to be fixed in the frame PR), QA-3-1 (focus drops to body after the last Show more).

## Not proved and not mine to accept
- **Backend T-SETUP:** none of it is proved. The proposal fields, `cursor`, `proof_case`, `expected_revision >= 0`, the `value.roles` shape and `evidence_id` binding (SEC-1-2, SEC-1-3) are mock-only. Real tenancy, real sessions and CSRF, and a real evidence store are untested. This blocks FE-CONNECT, not this delivery acceptance. The parent package status must not claim a working Setup against a real backend.
- **Product acceptance** (required) is pending. It should rule on: the reserved-tab placeholders, read-only rows for non-role rule kinds (PMO-0-3), A-8 links from Rules to Finance and Delivery, phone as read-only (A-6), and Proof and Why as optional (A-4).
- **Merge:** high risk, held for the design engineer under the overnight rules. It must follow PMO-3-1.
- **Authority wording check:** the UI never treats Admin as an approver, shows no default as a set rule and offers edit only from `can_change`. This was confirmed by the security and technical reviews on this head.
