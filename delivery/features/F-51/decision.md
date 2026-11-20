RECOMMENDATION: ESCALATE
COMMIT: b50b0b7ca04b9583c63fbe723de49d90aebbd987
APPROVER: approver

## Summary
- F-51 adds the Start work drawers for a fixed asset schedule (with a proof file) and a cash forecast, from the contract mock only; no money, payroll or client sending.
- Round 2 also changes every Start work line (F-05, F-47, F-49, F-51): an empty press names each required field and sends nothing. This closes F-49's QA-2-1.
- Gate, technical, UX, UI, QA and PMO acceptance all PASS on this head, with no blocking finding.
- Risk is medium, with a contract-change surface, and product acceptance is required.
- Open items belong to the design engineer: unsigned floor exceptions and exceptions, the shared behaviour change, and product acceptance.

## Why
The work is sound and evidenced. A person has to decide: visual scores of 42 to 50 rest on a capture limit that needs a signed exception, and a behaviour change touches five shipped lines. Product acceptance is also required and pending.

## Acceptance criteria
1. Fixed-asset drawer from data (AC 1): met, component tests; QA at 1440 and 390; no board string in src.
2. Forecast drawer, no file (AC 2): met; no file input, Sources follows the fixture.
3. Nothing computed or defaulted (AC 3): met in behaviour. Audience Management comes from the line's data; Months and As of start empty.
4. Only Finance gets the lines (AC 4): met; QA checked pmo_lead, pm, none.
5. Upload, revision chain, held proof, wrong record (AC 5 to 8): met; QA saw revisions 4, 5, 5 and 6, and the upload refusal. Wrong-case upload gives 422, not 404 (backend follow-up).
6. Landing, typed values, held run, uncertain and stale, access (AC 9 to 13): met; QA exercised each except upload_uncertain and the start_hold landing (build.md e2e covers them).
7. Plain text, phone, accessibility, tokens, mock matches contract (AC 14, 15, 17 to 19): met; axe by e2e, not re-run by QA.
8. Fidelity (AC 16): not met until signed. Coverage 100 after exceptions; visual 42.3, 49.9, 43.3, 48.1.
9. Existing tests green, evidence (AC 20): met; checks.sh passed (3273 tests).

## For the human
Please sign:
1. The floor exceptions for visual 42 to 50 on the four SCR-04 boards (the tall-page capture limit, judged by UI round 1), in fidelity-exceptions.json.
2. The 13 exceptions (all "builder proposal, pending design engineer"), including the signed F-05/F-47 phone sheet frame ("← My work", "START"), the remove "×" on the proof card and the calendar icon in As of.
3. The shared empty-submit behaviour across every Start work line (F-05, F-47, F-49, F-51): Start stays enabled and a press names the empty fields. Accept for all lines, or restrict it.
4. Product acceptance (required): both drawers, the Accounting-note and Audience choices, and who may start them (Finance only).

Before the PR, the coordinator should set `operation_ids` to E-LINES, E-LINE-OPTIONS, E-EVIDENCE-UPLOAD, E-WORK-START, E-ME (PMO-2-1), and refresh the F-51 handoff (PMO-2-4).

Files:
- /Users/Hunchoo/psl-factory/delivery/features/F-51/fidelity-exceptions.json
- /Users/Hunchoo/psl-factory/delivery/features/F-51/round-2/build.md (Validation, Fidelity)
- /Users/Hunchoo/psl-factory/delivery/features/F-51/round-2/review-ui.md
- /Users/Hunchoo/psl-factory/delivery/features/F-51/round-2/acceptance-pmo.md
