VERDICT: CHANGES
REVIEWER: reviewer-ui
COMMIT: 32c97d3df9f2b6f5ae78bf523744c57ee74d83b4
AUTHORITY: delivery UI review

## Summary
- Fidelity tool was not re-run (as instructed). Judged from round-1 report.json, side-by-sides and the 33 pending exceptions.
- Coverage-with-exceptions is unconfirmed but, by name matching, every "missing" item on all 8 boards has an exception, so it would reach 100 once signed. Wrongly excepted items (below) must be built instead.
- Visual 74.2 to 89 on all 8 boards (needs 90); the 8 waivers are unsigned and several gaps are fixable, not waivable.
- Gaps with NO exception (misplaced/extra, not in pass rule): alerts bell, Tunde Bello PMO/PM, Requirements/Pricing/Outcome/Submission tab text, Started 10:15, Tola, Back to RFP/Queue, "Work item"/"Where this sits" navs, Next aside, the note textbox rename, NEXT heading.

## Findings
- UI-1-1 | blocking | high | frontend | "Record the outcome" is drawn as a white outlined link above Next (page y~270) on desktop-submitted, -portal, and phone; the board has a blue (#2459D6, white text) primary button inside the Next card (desktop) / a sticky bottom bar (phone). Exception-free restyle and move. Build it as the board does.
- UI-1-2 | blocking | high | frontend | Success banner is a bordered panel row with a "RECEIPT CONFIRMED" tag, not the board's green band with check icon (desktop and phone). The sentence's missing-element exceptions (Conflicts 23) hide a restyle of a drawable element. Draw the green band with the icon; the tag may stay secondary.
- UI-1-3 | blocking | medium | frontend | Phone submitted/portal: board one-line "Email delivered · ref TL-SUB-0091." / "Portal receipt TL-SUB-0091 confirmed." and top-bar "DONE" tag are excepted as "no field". The ref and status are returned data already shown in the page (banner, timeline). Draw them in the green band and the bar. Same for the phone draft "v1" tag and "DEADLINE 28 NOV · 6 DAYS" (returned rfp.status/title data), and the draft/review headings.
- UI-1-4 | blocking | medium | frontend | Desktop-draft: the tab nav is excepted as "not a tablist", yet the board shows it as plain links; the page renders extra text copies (Requirements, 64, Pricing, Outcome) and a nav named "RFP". The exception covers the role mismatch only; accept via approval or align the roles so the extra-element list is empty. Also "Submission pack v1" is drawn as a dark filled chip (#1F2427 bg, white text) vs board plain bold text.
- UI-1-5 | blocking | medium | frontend | Headings: title is h2 at 22px where the board has h1 at 24px with wider letter spacing (draft/submitted desktop, phone 20 vs 22); review 35px vs 32px. Use the board's heading level and size via existing type tokens.
- UI-1-6 | blocking | medium | frontend | "Submitted" status tag text colour #3F474B vs board amber #6E4700 on the amber chip; draft "DONE" #16502F vs #16388F; nav active-state: "Projects"/"My work" colour #C8CDD0 with no orange underline vs board white with #C8401C bar; "More ways to start" 600 and no underline vs 400 and underline.
- UI-1-7 | blocking | medium | frontend | Review: "Open the full pack" is drawn as an outlined button (600, black) vs the board's plain blue underlined link (#2459D6); "Reject" is red (#9A2F10) vs board neutral #1F2427; the decide caption is #4A5357 vs #1F2427; the section header has an orange bar the board lacks; "Note (needed to return or reject)" is excepted but flagged extra textbox (rename rather than waive, or get the board changed). Phone review: the REVIEW tag is a red-filled chip vs mono plain text; the ref TL-RFP-2026-014 is white vs #4A5357.
- UI-1-8 | blocking | medium | frontend | Phone draft/submitted: the 390 layout adds the "History" link (42x24, below the 44px target; shared) and a big gap and misordered stack; the board has a sticky bottom action bar for Send for review/Record the outcome. Send for review is "misplaced".
- UI-1-9 | blocking | low | frontend | The "Tola · PMO agent · done" and "Drafted 22 Nov 10:15 Ask Tola" exceptions hide a drawable card: the board shows the role line and Drafted time. The time is in agent.started_at (page shows "Started 10:15"); drawing "Drafted <time>" from the same field is possible with mock data. The CEO rule is that a missing API field is not grounds for omission, so build it with mock data. Likewise "Kemi Adebayo · PMO Lead" (person name in the top bar) and the PMO Lead Overview/Setup nav links are drawable with mock data and are not valid exceptions.
- UI-1-10 | non-blocking | low | frontend | The "If delivery hadn't been confirmed..." info note (blue band, board draws it on both submitted desktops) is excepted as "a state the page isn't in". It is drawn on the board, so it is a missing element; draw it with mock data (fixed text).

## Verified
- Coverage with exceptions: by name matching of report.json missing[] against the 33 exceptions, all missing items are excepted, but UI-1-3, UI-1-9, UI-1-10 contest the validity of some. The 8 waivers hide fixable gaps (UI-1-1 to UI-1-8).
- No exception hides a numeric/data value beyond the receipt-ref one-liners and tags in UI-1-3.
- Read 2 side-by-sides (desktop-submitted, mobile-submitted); other boards judged from the report.json looks lists. No overflow at 390 seen; long email addresses break mid-word in tables (taste).
