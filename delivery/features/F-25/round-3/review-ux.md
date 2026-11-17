VERDICT: PASS
COMMIT: ba04923c108e0180ffdbd49404afc42fceeb191d
REVIEWER: reviewer-ux
AUTHORITY: delivery UX review

## Summary
- Checked live on a fresh production build (mock 4794, app 4795) as PM at 1440, 1024 and 390, plus the code.
- The empty-state sentence is now an h2 directly under the h1 (no skipped level). Long values wrap: at 1024 with the changed milestones, no cell is clipped and the page has no sideways scroll.
- Milestones, Registers and Actions behave as in round 2; Money (F-26) renders its own panel at 1440 and 390; Documents still says "Documents come next" with the way back to the journey. The tab bar is the same on all five.

## Findings
None.

## Verified
- UX-2-1 | verified | P-0106 Actions headings are H1 then H2 "No actions on this project yet"; `TabEmpty` renders an h2.
- Long values wrap | verified | no td has scrollWidth above clientWidth on Milestones at 1024 (changed) and 1440, Registers 1440, Actions 390; the ellipsis rule is gone from `project-tabs.css`.
- Money and tabs together | verified | Money shows the billing-by-stage panel (h2 under the page h1), Documents shows the coming-next panel, at both widths.
