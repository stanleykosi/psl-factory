VERDICT: PASS
COMMIT: 4e8a8c7d75957adbc9de381887453e0e5e11ecf4
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux

## Summary
- Extra-round impact check (D-47): walked /projects and P-0101 as pm at 1440 and 390 on the shared build (4711, mock 4712).
- Back link works at both widths: a "Projects" breadcrumb at 1440, a "← Projects" link in the frame bar at 390; both go to /projects.
- No horizontal scroll at either width, on the list or the journey. The title fits at 390 and the tabs stay inside their frame.
- Tola appears on the project page (desktop right-hand panel, with the "Ask me about this project" link). The phone journey has no panel. Nothing else changed for the user.
- Not re-run: axe, 401, 500 and loading states, and the other personas.

## Findings
- UX-3-1 | non-blocking | low | frontend | The count label is not pluralised: it reads "1 PROJECTS" when the total is 1. Not re-checked in this pass; still open.

## Verified
- UX-2-1 | verified | Count follows the search (round-3 walk, unchanged by the extra round).

## Notes
- UX-2-2 (phone hides the list tabs, so closed projects are unreachable on a phone) stays logged for the design engineer. Not re-raised.
