VERDICT: PASS
COMMIT: 195926d6854956a6918ef6199c0a5f57ce3a32ad
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux

## Summary
- Walked /projects and the P-0101, P-0105, P-0099 and P-0102 journeys as finance_lead, pm and none, at 1440 and 390, on the shared build (app 3711, mock 3712).
- List and journey match the spec screen states. Omitted board elements (tabs, Filter, extra columns, facts strip, stations, aside) are the contract gaps listed in build.md, so they are not deviations.
- No-access hides everything: P-0099 for all personas and P-0102 as pm show "You can't open this project" with "Back to projects". The tab title stays "Project · PSL Factory", and no case id or name appears.
- Persona none sees the frame's "No sections are open to your role yet." with no project request. The builder recorded this wording difference in build.md criterion 9.
- No horizontal scroll at either width. Phone shows cards on the list and a "← Projects" link plus stacked lines on the journey, with tags under line names. All 11 state tags render in one line.

## Findings
- UX-1-1 | non-blocking | low | frontend | Journey lines can share a name (two "Prepare an invoice", two "Record a receipt" on P-0101). The link text is identical and only the state tag tells them apart, so a screen-reader link list is ambiguous. Consider an aria-label or visually hidden suffix of "line text, state". Not caused by the contract, since the tag is in the same link.

## Notes
- Did not re-run axe, focus and touch-target checks. The builder reports them passing in e2e/projects.spec.ts.
- Did not drive error, loading, 401 or Show more failure states live. These were left to the builder's tests and screenshots.
