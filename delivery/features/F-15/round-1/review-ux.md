VERDICT: PASS
COMMIT: 07d078ef95aed97f36a412c6214ee8bc778ab9d0
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux

## Summary
- Walked the shared build (4811, mock 4812) as finance_lead and pm at 1440 and 390, scenario `needs-you` plus `empty`, `board`, `locked`, 401, 403, 500 and a person with no sections. The journey matches the spec and the concept (concept 3 in concept 1's drawer); no dead ends.
- Bell, badge and "3 need you" chip sit between the links and the name; Start work is last (D-54). Tab order: links, bell, Start work, then its "More ways to start" menu. Phone: Menu, bell (44x44), + Start.
- Drawer: focus lands on Close, Escape and scrim close it and focus returns to the bell that opened it (desktop and phone). Open on an unread alert lands on the work item, closes the drawer and lowers the badge and chip (4 and 3 need you became 3 and 2 need you).
- Phone sheet: tabs "Needs you 3" and "For your information" switch by click and Left/Right arrows (wraps); no horizontal scroll; Open buttons are filled in Needs you and outlined in For your information.
- States say something useful: empty "No alerts yet.", error card with Try again (a loaded list stays under it), "You're signed out." with Sign in, 403 message. No bell for signed-out or no-section people. Scratch files deleted; mock reset.

## Findings
None.

## Notes
- pm has no `needs_you` in the mock, so the drawer shows one "For your information" group and no chip or tabs; this is the intended unknown-is-not-zero path.
- Opening alert 1 as pm lands on a mock work item that does not match the alert text; mock data only.
- Keyboard-only: on phone, Tab from Close goes to the selected tab, then the Open links, then the footer links.
