STATUS: READY
COMMIT: e047f82dfb495a681d65f9fe0dc0767add0e1fb7
BUILDER: builder
LANE: full

## Summary
- Phone submission method is now one row of four (UI-1-3).
- Six scroll-capture exceptions removed; fidelity driver now captures the whole phone sheet (UI-1-1, UI-1-2).
- Phone visual is 59, UNDER the 70 floor the coordinator set. Cause below; needs a design-engineer decision.
- Desktop waiver (UI-1-4) stays a pending proposal for the design engineer.

## Changes
- frontend/src/features/start-work/start-work.css: removed the phone 2x2 grid rule for `.sw-seg--four`; added `min-width: 0` on its options.
- frontend/src/features/start-work/useStartWork.ts: the empty "New client" name error now merges with other field errors (TECH-1-2).
- delivery/features/F-49/fidelity-exceptions.json: 30 to 24 exceptions (six scroll-capture removed).
- delivery/features/F-49/round-1/fidelity/_driver/act.mjs: on phone, after filling, sets the viewport tall enough for the whole sheet and scrolls it to top. run.sh: `--visual-height union`.

## Fixes
- UI-1-1 | driver captures the whole sheet (1202px tall page) | e047f82d (driver files are in the delivery record)
- UI-1-2 | six scroll-capture exceptions removed | e047f82d (fidelity-exceptions.json in the delivery record)
- UI-1-3 | phone submission method in one row | e047f82d
- TECH-1-2 | field errors merged | e047f82d
Left: TECH-1-1 (grep pattern; adding `roles` would match an old LineChooser comment), TECH-1-3 (flake), TECH-1-4 (coverage is in rfp-intake-mock.test.ts), UI-1-5 (note), UI-1-4 (design engineer).

## Acceptance criteria
Fidelity (criterion 18), one run, production build, app 4965 / mock 4964, exceptions applied:
- desktop 1440: coverage 51.9, with exceptions 86.5, visual 74.2 (unchanged).
- phone 390: coverage 39.1, with exceptions 78.3, visual 59. The tall capture is 390x1202 against the board's 390x844, and union height counts the extra rows against the score. Coverage went up because the six labels are now seen. Not iterated (one run).
- Not met: neither board is at 100% or visual 90. Pending proposals: desktop D-83 waiver citing conflicts 2, 5, 6, 8 (UI-1-4); phone needs a design-engineer decision, since the built sheet is taller than the board's (help lines, "(optional)").
Other criteria: rfp-intake e2e 10/10 passed (desktop and phone).

## Validation
- checks.sh under the shared lock, twice: 3220 passed, 1 failed, both times tests/start-work.test.tsx "Esc closes and focus returns..." (chooser focus test, not code this change touches). Solo runs of that file: 61/61, 61/61, then 60/61 (same test failed once); later 5 runs gave 4 passes, 1 fail. On the base head it passed 3 of 3 solo. It looks like a timing flake, but the gate is not green.
- rfp-intake e2e: 10 passed.
- Demo left running on 4965/4964 (not stopped or rebuilt by me; the e2e run rebuilt frontend/.next, so the coordinator may want to confirm 4965 still serves; it returned 200).
- Worktree clean, pushed.
