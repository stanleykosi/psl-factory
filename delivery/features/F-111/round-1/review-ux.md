VERDICT: CHANGES
COMMIT: e35acf835f4162ea0fb1e350933c0a866f8667a3
REVIEWER: reviewer-ux
AUTHORITY: UX reviewer

## Summary
- Walked fixtures 5101 to 5107 on the mock (next dev 4994, mock 4995) as the PMO Lead at 1440 and 390 width. All four states, the 403 Chasing case and the 404 case render sensibly, and no write control or banned string appears.
- Phone width works: the facts, timeline and banners stack cleanly with no overflow.
- One spec criterion fails with a user-visible dead end: the detail 503 error (5107) has no Try again (AC 11).
- Not walked: live Django (AC 17, builder said not run) and the 401 and csrf states (unit tests only). The live journey needs a work item that Start work creates, and none exists on 55433.

## Findings
- UX-1-1 | blocking | medium | frontend | AC 11 and the Section states say a failed detail read shows the mapped message with Try again, and that Try again re-reads only the failed read. /work/5107 shows "What has happened" with only "Try again shortly." and no button, so the person cannot recover without reloading the page. build.md names this gap and blames the shared frame. Fix it in the adapter, or lane C adds a retry slot and the spec records the deviation as approved. src/features/issue-followup/model.ts.
- UX-1-2 | non-blocking | low | frontend | The Chasing rows show "Time unknown" on the right for every request and reminder. The messages items carry no time, so this is a placeholder with no information. Spec: draw no placeholder for data that is not supplied. Drop the right-hand cell when there is no time.
- UX-1-3 | non-blocking | low | frontend | The Blocks fact is a separate box with a muted, non-bold label that doesn't match the other facts. It links to /projects/{case_id}, not the milestones route as the spec's mapping says. The "Open the issue register" link is also missing. build.md discloses the frame limit. Needs a lane C dependency, or the spec must record the deviation.
- UX-1-4 | non-blocking | low | frontend | In 5103 (no owner), "Choose an owner for this issue." appears three times (banner, Next, page Next step) and no control to choose an owner is drawn. Writes are F-111B, so the page tells the person to do something they can't do yet. Show the text once. The F-111B gap is accepted as it stands.
- UX-1-5 | non-blocking | low | frontend | The timeline reads "Owner acknowledged · Acknowledged", which says the same thing twice. The separate acknowledgement line repeats the timeline row ("Acknowledged 20 Nov 11:00"). Drop the repeated status word when it matches the label.
- UX-1-6 | non-blocking | low | frontend | AC 9 says a control whose allowed flag is true is drawn disabled. No control is drawn at all, which is the plain read-only reading (Question 2 option B) and creates no dead end. Record it as approved in the spec.

## Notes
- Owner, severity, Raised and Age null handling matches the spec. There is no "0 days" and no "Unassigned" placeholder.
- 5104 shows RESOLVED beside the VERIFIED work state and never says Closed.
- Not seen on screen: a contrast or keyboard-order problem. Headings and links are real elements. The History tab and the milestone link are reachable by keyboard.
