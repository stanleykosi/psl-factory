STATUS: READY
COMMIT: 2075d4aa29aa4d09b9adc118b4955ad7e5c29af3
BUILDER: builder
LANE: full

## Summary
- UI-2-1: below 720px `.as__open` is docked like the composer (sticky bottom, surface background, 2px ink top rule, margin-top auto); the e2e now asserts it sits at the viewport bottom.
- UX-2-1: the phone bar's "N earlier" is underlined so it reads as tappable.
- UI-2-2: exceptions file tidied. The "← Home" entry could not simply be removed: without it SCR-05-mobile coverage fell to 93.3 because the frame names the link "Back to Home"; it is kept with an accurate reason. Mobile-thread waiver is 78.1; the "Start this invoice" reason names the tool false-miss.
- Re-scored only the two phone boards touched.

## Changes
- assistant.css (`.as__open` dock at <720px), shell.css (underline on `.shell-phonenote--action`), e2e/assistant.spec.ts (dock check), fidelity-exceptions.json, round-3/fidelity scripts.

## Fixes
- UI-2-1 | 2075d4aa29aa4d09b9adc118b4955ad7e5c29af3 | .as__open docked; e2e asserts bottom within 4px of the viewport
- UI-2-2 | 2075d4aa29aa4d09b9adc118b4955ad7e5c29af3 | exceptions file edited (see Summary)
- UX-2-1 | 2075d4aa29aa4d09b9adc118b4955ad7e5c29af3 | note button underlined

## Verified
- UI-2-1 | fixed | e2e "phone: the draft button..." passes with the dock assertion; SCR-05-mobile-draft-started visual 77.3 to 82.8
- UI-1-4 | fixed | same footer, now docked
- UI-2-2 | fixed | file edited; mobile board coverage 100 with the kept "← Home" entry
- UX-2-1 | fixed | underline in shell.css; SCR-05-mobile visual 90.6, pass

## Validation
- bash delivery/checks.sh: exit 0 (82 files, 1779 tests, lint, tsc, build).
- Playwright against the running app (4770/4771): assistant.spec.ts and start-work.spec.ts, 34 passed.
- Fidelity (round-3/fidelity/scores.txt): SCR-05-mobile-390 coverage 100 with exceptions, visual 90.6, pass (its visual waiver is no longer needed and is removed); SCR-05-mobile-draft-started-390 coverage 100, visual 82.8, waiver kept. The other six boards were not re-scored (round 2 values stand).

## Blocked
Not blocked. Design engineer to sign the remaining exceptions and the 7 visual waivers.
