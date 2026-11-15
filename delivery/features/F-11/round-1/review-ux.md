VERDICT: PASS
COMMIT: 06b4c0e93bbc3083cea431c2f022c1e267486f24
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux

## Summary
- Walked Setup, Rules, Finance rules and Delivery rules against the shared build (4111) and mock (4112) as Admin and Finance Lead at 1440. Walked the phone views at 390 with the mobile scenario, and walked the pm and read-only cases. Journeys, copy and states match the spec and the approved SCR-13 boards.
- Saved a role-list rule as Admin. The CEO tick on "Who may assign an RFP to a PM" saved as v1, the row showed "CEO · v1 · since 14 Nov", and the Rules badge and banner dropped from 8 to 7. "Saved as version 1." is announced in a focused status callout, and the button moved on to "Save as version 2". The invalid save showed "Check these fields: reason, starts." in an alert.
- Permission paths are sensible. The pm persona sees "This section isn't open to your role." with a link to My work. The read-only scenario has no buttons or panel. The phone views have no horizontal scroll (scrollWidth 390), no edit controls, and the "+ 4 MORE LINES · OPEN ON DESKTOP" note.
- Two non-blocking points: the phone visual fidelity scores (66 / 78.9 / 83.7) are below 90 because of the D-08 back-link offset, and the phone "← Setup" link lands on a reserved page.

## Findings
- UX-1-1 | non-blocking | low | frontend | Phone fidelity visual scores are below 90 (66 / 78.9 / 83.7), so acceptance criterion 25 is not met. The builder attributes this to the back link sitting under the shell phone bar (D-08). This is acceptable only if the design engineer records the exception, as for earlier features. Source: round-1/build.md, Validation.
- UX-1-2 | non-blocking | low | frontend | On a phone, "← Setup" goes to /setup/roles. That page shows the desktop frame with a horizontally scrolling tab bar and "Roles comes next." The boards do not draw this page. This follows the spec (A-6, reserved routes) and is fine until F-11C builds the phone Setup home. Source: frontend/src/app/setup/roles/page.tsx.

## Verified
None (round 1).
