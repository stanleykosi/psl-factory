VERDICT: PASS
REVIEWER: pmo-acceptance
COMMIT: ef0362f8cfe0fd7dab7e1ce57eb419db93395954
AUTHORITY: delivery PMO acceptance

## Summary
- Scope holds: FE-M2A-PROOF part 2 (SCR-04 fixed asset schedule with proof, cash forecast start), contract mock only. The diff is 22 files, all in the start-work feature, its mock and fixtures, tests and the handoff. No change in `frontend/src/api/**`, `components/**`, `shell/**`, `apps/**`, `architecture/**` or protected paths.
- Gate PASS on this head (checks.sh round 2, attempt 1, 3273 tests). Technical, UX, UI and QA round 2 all PASS on b50b0b7c; no blocking finding.
- Round-1 blockers UX-1-1, TECH-1-1, UI-1-1 to UI-1-5, UX-1-2 are closed (each marked verified by a round-2 reviewer).
- The shared empty-submit change (every Start work line: F-05, F-47, F-49, F-51) closes F-49's follow-up QA-2-1. Per-family empty-press tests exist; QA saw zero POSTs on the F-51, F-47 and F-49 lines.
- Fidelity: coverage 100 after exceptions on all four boards; visual 42.3, 49.9, 43.3, 48.1, which is the tall-page capture limit (list under the scrim), judged by UI round 1 and 2. Unsigned.

## Task and endpoint mapping
- Task FE-M2A-PROOF matches feature.json `task_ids`. Dependencies F-05, F-47 (proof upload, revision chain) are merged. None open.
- Endpoints consumed (readiness.md:20): E-LINES, E-LINE-OPTIONS, E-EVIDENCE-UPLOAD, E-WORK-START, E-ME. All exist; none is added.

## Findings
- PMO-2-1 | non-blocking | medium | coordinator | feature.json `operation_ids` is empty. Set it to exactly: E-LINES, E-LINE-OPTIONS, E-EVIDENCE-UPLOAD, E-WORK-START, E-ME.
- PMO-2-2 | non-blocking | medium | product | AC 16 (fidelity) is not met until the design engineer signs the floor exceptions for visual 42 to 50, and all 13 exceptions (all "builder proposal, pending design engineer"), including the signed F-05/F-47 phone sheet frame (this board's use), the remove "x" and the calendar icon.
- PMO-2-3 | non-blocking | medium | product | The shared empty-submit behaviour change touches every Start work line. Start stays enabled; a press names each empty required field, focuses the first and sends nothing. The design engineer should accept it for all lines. Project lines still keep Start off until a project is chosen.
- PMO-2-4 | non-blocking | low | backend | Handoff (BACKEND-HANDOFF.md, F-51 section) is stale: it says the Accounting-note placeholders are "Sample note A to D"; the fixture now has two ("Sample: note A/B"). It also omits the shared empty-submit check and that the Audience default is read from the field-level `value`. Correct before the PR.
- PMO-2-5 | non-blocking | low | backend | Contract has no choice-default field (TECH-2-2, UX-2-1); the builder used field-level `value`. The coordinator should define it.
- PMO-2-6 | non-blocking | low | backend | Backend follow-up: an upload of kind ppe_register to C-0101 or C-FIN-LEDGER as finance_lead answers 422 "Check these fields: kind." on the mock, not the 404 in spec criterion 8 (QA-2-1). The page shows a refusal either way; the real backend should settle 404 versus 422.
- PMO-2-7 | non-blocking | low | builder | TECH-2-1: the F-05 422 test lost its "Start greyed after a 422 until a change" assertion; add one at frontend/tests/start-work.test.tsx:501.
- PMO-2-8 | non-blocking | low | product | Product acceptance is required (readiness) and pending: both drawers are new to the client.

## Verified
- Evidence: checks.md round 2 PASS; scores.txt recomputed (coverage 100 after exceptions, visual below 90 on all four). Tool not re-run. QA did not exercise upload_uncertain, start_hold landing, 401 or axe; build.md reports e2e 48 passed covering them.
- Round-1 findings: see Summary; each carries "verified" in a round-2 review.
- Handoff: F-51 section is on the branch (line 479), questions only; no generated type changed.
