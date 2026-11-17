VERDICT: CHANGES
REVIEWER: pmo-acceptance
COMMIT: 3a2884d4707522db814305db68b78dc6e4fc682a
AUTHORITY: PMO delivery acceptance (not product, merge or release)

## Summary
- Technical, UX, UI and QA all pass on 3a2884d4. QA-2-1..2-3 are VERIFIED, the round-3 gate is PASS, and no blocking finding is open. The criteria QA covered (four states, three writes, failures, access, tab frame, phone) have passing evidence.
- Delivery cannot be accepted yet. Criterion 19 (fidelity) is not met. All 8 round-2 boards show `pass=False` in `round-2/fidelity/scores.txt`, with visual 68.5 to 89.9 against the 90 bar. The 8 board-level waivers (D-83) are not signed, and mobile-verified at 68.5 is below the 70 floor with no one-board exception.
- Every entry in `fidelity-exceptions.json` is `approved_by: "builder proposal, pending design engineer"`, so none is approved. The criterion requires `approved_by` and a Conflicts number. The UI-1-6 and UI-1-7 entries cite conflicts 5/11 and 3, which do not cover them.
- Scope held: `BACKEND-HANDOFF.md` has the "Added during F-30" section (G-SCR30-1/2/4/5, questions, frontend wording). The ISS-0233 repoint to W-2411 (D-111) is in place in the registers fixture. No operation IDs were in scope. The parent package makes no claim beyond this slice (contract mock only, nothing released).
- Product acceptance is required by readiness and is still pending. It is not a PMO verdict.

## Findings
- PMO-3-1 | blocking | high | product | Criterion 19 has no accepted evidence. No board reaches visual 90, and none has a signed D-83 waiver citing the shared frame. All 8 SCR-30 boards need a design-engineer waiver (frame, form opening on press, phone sections, extra Chasing section). `round-2/fidelity/scores.txt`; UI-1-8 is still OPEN. Expected: signed waivers for all 8 boards, recorded in `fidelity-exceptions.json` or a decision record. Round-3 UI says no layout change, so the round-2 run stands.
- PMO-3-2 | blocking | high | product | Mobile-verified scores 68.5, below the D-83 floor of 70. It needs an explicit one-board floor exception (precedent F-23 SCR-28 at 69.2) from the design engineer. `round-2/fidelity/scores.txt:9`.
- PMO-3-3 | blocking | medium | product | None of the 29 exceptions in `fidelity-exceptions.json` is approved. All read "builder proposal, pending design engineer". UI-1-6 (timeline row layout, reasons cite conflicts 5/11) and UI-1-7 ("OWNER FOLLOW-UP", cites conflict 3) cite conflicts that do not approve them. Expected: the design engineer's own sign-off, with reasons that name the new item (the shared timeline renderer; the Next heading) rather than D-111. Note that the exceptions for sample data and times ("11 Nov 16:40", the lead sentences) cover values the data supplies; criterion 19 says no exception may cover those. The design engineer should rule on that when signing.
- PMO-3-4 | blocking | medium | pmo | Product acceptance is required (`readiness.md`, `feature.json` risk) and is pending. The owner-update, reply, escalate and set-owner flows and their wording are new to the client. This must be recorded by the product authority. It is not a code defect.
- PMO-3-5 | non-blocking | low | pmo | The builder's full `checks.sh` failed twice on unrelated timing tests (`setup-rules`, `rfp`) in round 3 (`round-3/build.md`). The coordinator's gate then passed on attempt 1 (`round-3/checks.md`). I accept the gate result but suggest noting the two flaky tests for a separate fix.
- PMO-3-6 | non-blocking | low | frontend | UX-1-2, UX-1-3, UX-1-4 and TECH-1-1 remain OPEN or FIX_SUBMITTED, all non-blocking. UX-1-3 (W-2413 "Next" wording vs the button) is fixture data. Carry them to the next slice or close them with a stated reason.

## Verified
- QA-2-1 | verified | `round-3/review-qa.md`: empty-submit summary and focus verified at 1440 and 390, by click and Enter; 167 e2e and 158 unit tests pass.
- QA-2-2 | verified | `round-3/review-qa.md`: the kind word no longer repeats the role.
- QA-2-3 | verified | `round-3/review-qa.md`: the 403 and 404 e2e cases use the scenario header and assert the not-open view.
- UX-1-1, UI-1-1, UI-1-2, UI-1-3, UI-1-4 and UI-1-5 | verified | all VERIFIED in `feature.json` at 48ba8f7a, and the round-3 diff does not touch their areas (`round-3/build.md`, `round-3/review-ui.md`).
- UI-1-6, UI-1-7 and UI-1-8 | reopen | still open and awaiting the design engineer, as PMO-3-1 to PMO-3-3 describe.
