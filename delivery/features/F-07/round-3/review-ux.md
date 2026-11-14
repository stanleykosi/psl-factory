VERDICT: PASS
COMMIT: 2892f009b88a0dfb1a2ec1df5f33b966f7ba0a7c
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux

## Summary
- Re-walked /projects (search, no match), P-0101 and the P-0104 no-access page as pm, at 1440 and 390, on the shared build (3711) with the mock on 3712.
- UX-2-1 is fixed: searching "lagoon" now reads "1 PROJECTS" with "All 1 showing"; no match reads "0 PROJECTS" and "No projects match" with "Clear search". The tab badges keep whole-tab counts (Active 4, Closed 1, All 5).
- No regression: the list, journey and no-access page match the round-2 walk. No horizontal scroll at either width. The phone list and journey are unchanged, and no-access still names nothing.
- Not re-run: axe, 401, 500 and loading states (builder tests only).

## Findings
- UX-3-1 | non-blocking | low | frontend | The count label is not pluralised: it reads "1 PROJECTS". Consider "1 PROJECT" when the total is 1 (the board label is upper case, so "1 PROJECT").

## Verified
- UX-2-1 | verified | Count follows the search at 1440.

## Notes
- UX-2-2 (phone hides the list tabs, so closed projects are unreachable on a phone) stays logged for the design engineer, as the coordinator said. Not re-raised.
