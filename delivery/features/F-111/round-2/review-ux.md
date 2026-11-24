VERDICT: PASS
COMMIT: 30143e1a4f9376200d9fc6f89797ff57e97a3b54
REVIEWER: reviewer-ux
AUTHORITY: UX reviewer

## Summary
- D-193 sync-only re-check of 30143e1a (merge of origin/main 4fd055ce: F-71 money and milestones tabs, F-64 decision desk): none of the issue follow-up journey files changed (work item frame, issue line, issues.mjs and the 51xx routes, live-work and work-live mocks, issue-followup adapter). server.mjs live-decide routes only own work ids 17 to 19 and task ids, so the 51xx reads are unaffected. The shared DecisionRows and AmountValue used by WorkItemOverview moved to decide-v7 with identical content (247 lines, diffed against 8a5c09fe), and decide/format.ts re-exports an identical file. VERDICT stays PASS; no new findings. No servers started and no browser walk repeated.
- Walked mock fixtures 5101 to 5108 as the PMO Lead at 1440 and 390 (next dev 4990, mock 4991, both stopped). No horizontal overflow at 390, no write control, no banned string.
- Round 1 findings checked: UX-1-2, UX-1-4 and UX-1-5 are fixed. UX-1-6 is accepted by the builder but the spec text is not yet updated (non-blocking, below). UX-1-1 and UX-1-3 are accepted risk under D-202 and not re-raised.

## Verification
- UX-1-2 fixed: 5102 Chasing shows "Asked · Sent / Receipt recorded 09 Nov 10:02" and "Reminder · Sent / No receipt yet" with no "Time unknown" anywhere.
- UX-1-4 fixed: 5103 shows "This issue has no owner. Choose an owner for this issue." once, in the banner. The Next section is gone from that page.
- UX-1-5 fixed: the timeline row reads "Owner acknowledged | 20 Nov 11:00". The remaining "Acknowledged | 20 Nov 11:00 · Owner replied by email" line carries the channel, so it adds information.
- UX-1-6: no control is drawn, which is the read-only reading and creates no dead end. The spec (lines 51 and 99) still says "drawn disabled". See UX-2-1.
- States: 5105 shows "Chasing is not available to you" with the rest of the page intact. 5106 and 5108 show "No access. This record is unavailable." with a Back to my queue link. 5107 keeps the facts and shows "This is not available right now. Reload the page to try again." in place of the timeline (accepted, D-202). 5104 shows RESOLVED with the Verified state and never says Closed.

## Findings
- UX-2-1 | non-blocking | low | spec | AC 9 and the Allowed actions row still say a control whose flag is true is drawn disabled. The build draws nothing, and the design engineer accepted this reading in round 1. Edit the spec text to say nothing is drawn until F-111B.
- UX-2-2 | non-blocking | low | frontend | 5103 still shows the frame's "Next step. Wait for the owner to update the issue." directly above the banner "Choose an owner for this issue." These conflict. This is the frame next-step line accepted under D-202 (UI-1-4), so it is noted only.

## Notes
- The first load of 5101 at 1440 showed "Loading…" for a few seconds, which was the dev compile. It rendered normally afterwards.
- The live Django journey was not walked, as in round 1.
