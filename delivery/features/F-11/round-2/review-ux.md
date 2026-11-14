VERDICT: PASS
COMMIT: edc476370a1b20444d9807811a9d7b0a6ed2f503
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux

## Summary
- Re-walked the new outcome callout on the shared build (4111, built after the head) with the mock at 4112, as admin and finance_lead at 1440, on Rules and Finance rules. The mock was reset before each run and after the last one.
- With the right withdrawn mid-edit (cookie psl_mock_setup=readonly), saving closes the Set a rule panel and shows one red alert above the list: "Your role does not allow this. You can no longer change these rules, so the Set a rule panel has closed. Nothing you entered was saved." Focus is on that alert, and no edit buttons remain. Admin and finance_lead see identical text.
- The wording is plain, says what happened, why the panel went and what became of their input. It suits both personas, and the page stays readable below it (the screenshot showed the list intact).
- Phone at 390 is unchanged: no horizontal scroll (scrollWidth 390), read-only, and the page headings are the same as round 1.
- Round-1 results carry forward: the change touches only the closed-panel path, so the Setup, Rules, Delivery views and the pm and none paths are unaffected.

## Findings
- UX-2-1 | non-blocking | low | frontend | Carried from UX-1-1: phone fidelity visual scores stay below 90 until the D-08 back-link slot exists. Needs the design engineer's recorded exception. No change this round.
- UX-2-2 | non-blocking | low | frontend | Carried from UX-1-2: phone "← Setup" goes to the reserved Roles page. Fine until the phone Setup home is built.

## Verified
- QA-1-1 | verified | UX view: Rules (admin, finance_lead) and Finance (finance_lead, admin) each show one focused alert with the exact EDITOR_GONE and NOT_SAVED wording, the panel is gone, and there are no buttons.
- UX-1-1 | reopen | Still open, unchanged and non-blocking (see UX-2-1).
- UX-1-2 | reopen | Still open, unchanged and non-blocking (see UX-2-2).
