VERDICT: CHANGES
REVIEWER: reviewer-ui
COMMIT: c706d6a7df4ca8eef92acd420d371e5ab484f7b3
AUTHORITY: delivery UI review

## Summary
- UI-1-1 to UI-1-4 are fixed at 1440 and 390. I checked this on the live demo (W-3601 to W-3604, persona pm, mock reset before each page) and in the builder's round-2 side-by-sides. I did not re-run the fidelity tool.
- UI-1-5 is resolved: "Back to the issue" and "15 DAYS LATE" each have their own proposed exception.
- All 8 boards reach 100% coverage after exceptions. Visual scores are 75.5 to 87.1, all above the floor of 70.
- Two record gaps remain. Desktop investigating (87.1) has no visual waiver. The draft board's blue outlined message box is not drawn and is not covered by any exception.
- No page scrolls sideways at 390 (scrollWidth 390). The diff adds no CSS: the banner uses the existing `Callout` info kind, and the tags use the existing tones.

## Findings
- UI-2-1 | blocking | medium | frontend | Desktop investigating is below 90 and has no waiver. round-2/fidelity/scores.txt gives SCR-51-desktop-investigating-1440 a visual score of 87.1, pass False. It was 90.1 in round 1 and dropped once the extra decide card was removed. fidelity-exceptions.json `visual_waivers` lists the other seven boards but not this one. Expected: a D-83 waiver for this board, with its own reason and "pending design engineer". The reason should cite the shared frame (D-99, D-110), the AgentCard head and footer (Conflicts 7), and the untitled facts section, which the board draws with "RAISED BY YOU" as its heading row (Conflicts 9).
- UI-2-2 | blocking | low | frontend | The draft board's message box is a difference with no exception. SCR-51-desktop-draft draws Message v1 inside a blue outlined, tinted box. The page draws the text as a plain shared list row with a divider (W-3604 at 1440 and at 390). The only related exception covers the message text as a tool artefact, not the box styling, and the draft waiver reason does not mention it. The round-1 instruction was to draw the box or list its styling as an exception. Expected: either draw the box, or add its own proposed exception (category component or styling) and name it in the desktop-draft waiver.

## Verified
- UI-1-1 | verified | W-3601 and W-3603 show no "Decide whether to escalate" card at 1440 or 390 (no matching heading in the DOM; screenshots). On investigating, the facts and Tola's card sit side by side at the board's height. On not-escalated, the callout is at the top of the main column with Next beside it. WorkItemOverview.tsx:727-730 adds the `escalation` rule. W-3602 still decides in place with InlineDecide, and no second card appears.
- UI-1-2 | verified | W-3604 shows no "Nothing here yet." and no amber callout at either width. The message is the section's item text (fixtures W-3604, W-3604.next, W-3602.approve, W-3608). The missing box styling is raised as UI-2-2.
- UI-1-3 | verified | The W-3603 banner is `psl-callout--info` with the info icon at 1440 and 390, and matches the board's blue callout. bannerTone, Workspace.tsx:166-173, keys it to the escalation line's status tone (neutral gives info).
- UI-1-4 | verified | MESSAGE DRAFTED is `psl-tag--agent` (blue, as on the board). NOT ESCALATED is `psl-tag--neutral` (grey, as on the board). Live DOM and side-by-sides at both widths.
- UI-1-5 | verified | The "Back to the issue" position and the "15 DAYS LATE" tag now each have their own proposed exception, both marked "not signed". The desktop not-escalated side-by-side confirms that the link-position exception describes what the page actually draws.

## Notes
- Every exception and waiver is still unsigned ("builder proposal, pending design engineer"). That is expected: the design engineer must sign each one before acceptance, which is not a blocker for this review.
- The mobile-draft waiver says "Send for review placed in the page rather than pinned". On the live page it is pinned at the bottom with the Next line above it. Please correct the wording.
- The AgentCard DONE tag is green on the page and blue on the board (the tool reports #16502F against #16388F). This was a round-1 note and is still not named in the draft waiver texts; please name it.
- The phone extras (the full title, Message v1 and Next on the draft and not-escalated pages, and "Back to the issue") sit under Conflicts 6, with the phone-wording exceptions and the phone waivers.
- Screenshots are in the session scratchpad only. I started and restarted no server and changed nothing in the worktree.
