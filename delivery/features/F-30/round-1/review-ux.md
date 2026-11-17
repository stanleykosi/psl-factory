VERDICT: CHANGES
REVIEWER: reviewer-ux
COMMIT: 0b69974d2b1d1b2eb6caa228c98466cf054f1698
AUTHORITY: reviewer-ux

## Summary
- Walked W-2411..W-2414 at 1440 and 390 as PM (and persona `none`, unknown id) on http://localhost:4833; each state shows its own status, facts, chasing, agent note and only the controls its data allows; no sideways scroll at 390.
- Forms: Post update, Record a reply and Set an owner open on press (inline on desktop, full-height Drawer on phone); Escape returns focus to the opener; empty Owner submit shows a message under the field plus a summary and focuses the Owner control; the owner list is exactly the three candidates with team and outside-party wording; success reads "Owner set: ...". Raise an escalation opens the Start work drawer and sends nothing.
- Not-open view for a persona with no access (and for an unknown id) shows no title or fact.
- One blocking deviation: the back link reads "← Queue" (phone bar and desktop bar), not the approved "← Project" (D-111 item 9).
- Test note: my Set an owner submit on W-2413 changed shared mock state (owner now Tunde Bello); restart or reset the mock before another reviewer expects the no-owner state.

## Findings
- UX-1-1 | blocking | medium | frontend | Back link does not match the approved design or D-111 item 9 ("one back link '← Project'", F-22 frame). Actual: all four pages show "← Queue" to /my-work on the phone bar and the desktop bar (`frontend/src/features/work-item/WorkItemView.tsx:238` `usePhoneBack({label:'Queue',href:'/my-work'})`). A person who came from Registers is sent to the queue, not the project; the boards draw "← Project". Expected: label "Project" linking to the work item's project (P-0101) on every state, issue line only if F-22 work items must stay as built.
- UX-1-2 | non-blocking | low | frontend | The Set an owner form shows its title twice on phone (Drawer title "Set an owner" and the card heading "SET AN OWNER"), same for the other forms; harmless but repeats. Not a design break.
- UX-1-3 | non-blocking | low | frontend | W-2413 "Next" text says "Set an owner in the issue register; follow-up starts straight away" while the button on the same page sets the owner. Wording comes from the fixture; align it with the page (data, not code).
- UX-1-4 | non-blocking | low | frontend | Empty workspace state ("Nothing here yet.") has no axe e2e run (build.md item 20); I did not see it either since no fixture reaches it.

## Verified
None (round 1).
