VERDICT: CHANGES
COMMIT: d5046515521bca99b4b7de220c4d524838cfff1f
REVIEWER: reviewer-ux
AUTHORITY: delivery UX review

## Summary
- The core journey works on the contract mock at 1440 and 390: Tola's suggestions are all ticked, unticking one sends only the ticked ids (I sent D-1, D-2, A-1, A-3 after unticking A-2, with audience "client"), audience is a labelled radio group (Client chosen first, aria-checked correct), Send for review moves to the review page, the "Goes to" recipients and the "Open the minutes" panel with the "Test template" tag show, and an approve through a double click sent one decision. After the uncertain send every step is aria-disabled with "Confirm what happened first." and the reconcile choices lead the page. No sideways page scroll at 390.
- One blocking gap: Edit forms open empty, so the PM cannot see or correct the text Tola found.
- The rest is wording and layout polish (non-blocking).

## Findings
- UX-1-1 | blocking | Edit on any decision or action (W-2301, 1440 and 390) | The form opens with "Action" and "Due" (or "Decision") empty and the owner on its placeholder. I measured `Action=`, `Due (optional)=`. To fix one typo the PM must retype the whole action, and a blank owner or due is "left out" of the request, so an edit can silently drop the owner and due Tola found. The spec (item 10) says Edit opens a form with text, owner and due; D-98 approved opening a form on press, not an empty one. build.md line 77 admits "Edit forms do not prefill". | Prefill each form from the row it was opened on (text, owner, due), or if the frame cannot, show the current text above the form and send only what the PM changed. Get design engineer sign-off if left as is.
- UX-1-2 | non-blocking | W-2305 after Approve: decision result and reconcile panel | The result page says "Paid is tracked separately by Finance and is not part of this decision", and the reconcile panel says "so the client is never invoiced twice". Both are invoice wording on a minutes send. | Use minutes wording (for example "so the client never gets the minutes twice"); drop the Finance line for the minutes line.
- UX-1-3 | non-blocking | Decision page `/work/W-2304/decide` | The work page says "Approve and send" and "Approving sends this exact version to the client". The decision page button is "Approve v1" with "Approving earns APPROVED only. Send is the next station." The two pages promise different things for the same click. D-98 accepted the F-16 page, but the sentences contradict each other. | Make one sentence true for both, and say plainly whether Approve sends.
- UX-1-4 | non-blocking | W-2301 phone (390) | The Actions table keeps its 560px width inside a scroll region, so Due, Edit and Remove sit off screen (Remove starts at x=492 of 390). The region is focusable and labelled, so it is reachable, but the PM has to scroll sideways to edit or remove, and the board draws "owner · due" rows. | Stack action rows on a phone with Edit and Remove visible.
- UX-1-5 | non-blocking | W-2301 | Decisions sit in the right column with the tick above the text and a full-width Edit button, so the page reads Actions first, Decisions second. The board has decisions first, a tick beside the text and a link Edit. This is exception 6 (frame layout), which D-98 did not list as signed. | Get the exception signed, or draw the tick inline.
- UX-1-6 | non-blocking | Step result, W-2301 | After "+ Add an action" the page says "Done: + Add an action." with the plus sign in it, and a blank add says "Add action to continue." | Say "Done: action added." and "Write the action to continue."
- UX-1-7 | non-blocking | W-2302 | Tola's panel says "step 1 of 1" and "Reading the meeting notes", while the board and the checklist say "step 3 of 4". | Return the same "step 3 of 4" in the agent block.
- UX-1-8 | non-blocking | W-2304 and W-2305 at 1440 | A large empty area sits under the tab bar beside the "Review client minutes" card, and the same review is offered twice (card with "Open the decision", then the Decide panel). Disabled "Approve and send" on W-2305 has near-invisible text (also UX-1-3 in F-21 round 1). | Raise the disabled contrast in the frame and close the gap.

## Verified
- Fixed-set check: ticked ids sent equal the ticked rows shown, including after unticking. Verified at 1440.
- Return with a blank note refuses with no request; with a note one E-TASK-DECIDE `return` is sent. Verified at 1440; the 390 decision page is the same component and has no sideways scroll.
- Not walked: W-2306 (stale 409) and W-2307/W-2308 in the browser beyond their text (restricted row shown, "0 selected" with confirm aria-disabled and "Nothing here yet."). The mock has no PMO Lead sign-in, so I walked W-2304/2305 as the PM persona (header shows Tunde Bello while the page says "You are PMO Lead").
- Servers on 4766 and 4767 stopped by PID; ports free; no test-results folder.
