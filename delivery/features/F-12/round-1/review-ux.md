VERDICT: PASS
COMMIT: 831b17164ca8b1200e9ff84d2d486ea0d7dc7dc5
REVIEWER: reviewer-ux
AUTHORITY: UX reviewer (F-12 round 1)

## Summary
- Walked /notifications and /settings/alerts at 1440 and 390 as the finance_lead test persona on the shared mock (reset first). Both screens match the approved SCR-15 boards.
- Open-an-alert goes to /work/W-1001 and NEW is gone on return ("0 unread"). Search and Filter work, and the phone Filter is a bottom sheet. Escape closes it and focus returns to Filter.
- Settings: the switch matrix toggles, Save shows "Your alert settings are saved." The phone shows event cards, the quiet-hours line and a pinned Save. No horizontal scroll at either width.
- The tab order is logical and every control is a real link, button, switch or select. The phone back link at the right is deviation E-4 (D-19 precedent, awaiting the design engineer's approval). I treat it as non-blocking and note it below.
- Not re-walked here: the stale, invalid, bare and 401 states. The builder's e2e and axe cover them.

## Findings
None.

## Notes
- E-4 (phone back links "← Home" and "← Notifications" level with the heading, not on their own line) is a recorded, fidelity-gated deviation. It needs the design engineer's sign-off. It is not a UX defect.
- On the phone Filter sheet the hint reads "Unread only 0 unread". This is accurate after the alert was opened, and the same copy is in the design.
