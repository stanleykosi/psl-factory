VERDICT: CHANGES
REVIEWER: reviewer-ux
COMMIT: 356656654596e6bc7295f4cdca4f80a88d4ce2e5
AUTHORITY: delivery UX review

## Summary
- Walked W-3601 to W-3609 as PM (the mock has no separate PMO Lead persona; every persona gets you_can_act on T-3602) at 1440 and 390, then ran the decisions. Mock reset afterwards.
- Works: the escalate-or-not panel reads clearly and states the message is reviewed before it is sent; "Don't escalate" with an empty note shows "Add a note to reject it." with focus on the note (desktop and phone Drawer); with a note it posts one reject and shows NOT ESCALATED; the uncertain decide shows RESULT NOT CONFIRMED, no buttons, never drafted or escalated; W-3605 names Kemi Adebayo, W-3606 shows Unknown; the no-reviewer hold sends nothing and shows the reason; "Back to the issue" opens W-3609.
- Blocking: the NOT ESCALATED page on desktop has a broken layout and departs from the board (UX-1-1).

## Findings
- UX-1-1 | blocking | medium | frontend | Desktop NOT ESCALATED (W-3603, and after deciding on W-3602) is laid out badly and differs from SCR-51-desktop-not-escalated. The board has the quote (info tone) on the left and one NEXT panel on the right holding "Back to the issue". The build draws a right-hand "Decide whether to escalate / Only a PMO Lead can decide" panel on a finished decision, leaves a blank hole in the left column, pushes the quote (warning tone) and a loose "Back to the issue" button below it, and butts the NEXT panel against the decide panel with no gap. After a live decide a green "Escalation ESC-0012 was rejected" bar also sits flush against the panel. Expected the board layout; the exceptions file covers score gaps, not this. Evidence: round-1 screenshots /private/tmp/claude-501/s/pm-1440-3603.png and d-after.png. Phone is acceptable.
- UX-1-2 | non-blocking | medium | frontend | W-3604 and W-3608 (MESSAGE V1) show "Nothing here yet." above the drafted message, which contradicts it. The board has no such line (empty copy from features/workspace/labels.ts:76 shown with content present).
- UX-1-3 | non-blocking | low | frontend | The success notice after "Don't escalate" says "was rejected"; the product word is "not escalated". Suggest "Escalation ESC-0012 was not escalated" style plain wording or drop the notice.
- UX-1-4 | non-blocking | low | frontend | The shared uncertain notice reads "Nothing was sent again." That uses "sent" in a feature that promises nothing reaches the client (build.md already flags it). On the phone the Reload button sits inline mid-sentence.
- UX-1-5 | non-blocking | low | frontend | The no-reviewer hold (W-3608) has one visibly unavailable "Send for review" button (aria-disabled, described by the reason, no POST on click). This matches spec.md, but if "no buttons" was intended it differs.
- UX-1-6 | non-blocking | low | frontend | On the phone decide screen "Don't escalate" is not full width like "Escalate to the client". The "Back to the issue" page (W-3609) shows crumbs ESCALATIONS / ESC-0012 on desktop (mock frame), while the phone bar says ISS-0241.

## Verified
