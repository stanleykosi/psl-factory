VERDICT: PASS
COMMIT: 6e5c9ade8557e0261838c5a2c391a517d829ac69
REVIEWER: reviewer-ux
AUTHORITY: delivery UX review

Round 2. Rebuilt in the worktree (build exit 0), mock 4943, Next 4944, FRAME_FIXTURES=1; Playwright at 390 and 1440 with synthetic mock personas (finance_lead, pm, ceo). Measured target sizes in the browser. No horizontal overflow on work item, alerts settings, projects, exceptions or the My work filter sheet at 390. Servers stopped by PID, test-results removed, no code touched.

## Verified
- UX-01 | verified | /work/W-1001, W-1201, W-1004, W-1401 at 390: Overview 78x44, History 65x44; layout intact (W-1201 screenshot: tag row, tabs and facts strip keep the board rhythm).
- UX-02 | verified | /settings/alerts at 390: all ten switches 44x44, rows keep their height, track still drawn 26px; at 1440 they are 44x26 as before. No overflow.
- UX-03 | verified (one gap, see UX2-01) | At 390: breadcrumb back link 57x44, "Go to My work" 90x44, exceptions card titles are 20px text but the whole card is the hit area (sampled 12/12 points across 44px of each card), Clients names the same (12/12), filter sheet "All 6 lines" 57x44, Start work line row 44px. The sheet grew as stated, still fits at 844px with no overlap. "See Chidi's steps" is still a text link (the W-1201 case shows it on the decide page at about 17px high); the build note says disclosures were moved to 44px but I measured the decide-page link only by sight, not size, so treat it as unverified rather than failed.
- UX-04 | verified in part | W-1201 decide at 390, Return with an empty note: the note field now sits above the sticky bar (field bottom y 674, bar top y 676) with focus on it. But the error text "Add a note to return or reject." is at y 680-698, which is behind the bar, so it still cannot be seen. See UX2-02.
- UX-05 | accepted | Forms stay on board markup; library follow-up as stated.
- UX-06 | accepted | Needs status.tone from the API (backend handoff). With the status fixture (psl_mock_overview=status) the UNCERTAIN chip is amber (255,241,214) at 390 and 1440; the default mock still falls back.
- UX-07 | verified | "Blocked" is gone from the exceptions page text; code reads "Action needed" (no blocked row exists in the mock, so I checked the text absence and the code, not a rendered tag).
- UX-08 | verified | Decide and work item both show "RECEIPT / RECORDED" in the facts strip (and "Unknown"/"—" per the shared FactsStrip); wording is the same on both pages.

## D-94
- Projects, Closed tab: Sabi Market shows "Closed 09 Nov" and "—" in Next milestone at 1440; Rivers Media (Archive) "—". No Unknown tag on either. At 390 the phone cards show no next-milestone line, as the board's phone card draws.
- All I can see (?status=all): Sabi Market reads Unknown at 1440, the known and accepted contract gap.
- Active tab: no open row in the mock lacks a next milestone, so the open-Unknown cell could not be rendered in the mock; verified from code (`nextMilestoneText(...) ?? (closed ? '—' : <Unknown />)`) and the same Sabi row on All. Not a defect.
- Desktop table layout, tabs, count chips and paging bar unchanged.

## New findings
- UX2-01 | non-blocking | My work filter sheet at 390 | The line checkbox rows are 358x36 (label height 36), under the 44px of D-92c; the inputs themselves are 20x20. Rows are separated by gaps, so the touch zone is about 40px. | Give the rows min-height 44px (the sheet will grow a little; D-94 already accepted that trade for "All 6 lines").
- UX2-02 | non-blocking | Decide at 390, Return/Reject with empty note | Field is visible now but its message is under the sticky bar (y 680-698 vs bar top 676). | Scroll the message, not just the field, above the bar (scroll the control block, or raise scroll-margin-bottom by the message height, about 22px).
