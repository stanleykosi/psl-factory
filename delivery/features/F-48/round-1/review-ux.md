VERDICT: PASS
REVIEWER: reviewer-ux
COMMIT: 8a9755d4f598464231786ff2100fd420a93b31a4
AUTHORITY: delivery UX review

## Summary
- CV-2404 as pm at 1440 and 390 matches the SCR-05 cant boards; normal answers unchanged.

## Findings
None.

## Verified
- Desktop 1440: side panel shows the zainab-cant pose, "Zainab can't do that with your access.", Project, Your access and the agents-cannot note. Thread shows ask, steps, answer and reason as separate lines (reason in red), then a Restricted tag with no label or link. No draft card, start button or access-request control. Composer empty.
- Phone 390: the tinted pose card (alt "Zainab, can't do this") sits above the agent name; no sideways scroll. CV-2403 (answered) shows no pose card and keeps the idle avatar.
- finance_lead opening CV-2404 sees "We could not find that conversation." with no leak.
- Not checked: axe and 44px targets (covered by the builder's e2e).
- Note: the mock answer text itself mentions staff-cost totals and asking the HR Lead. That is sample text shown as returned, not a control.
