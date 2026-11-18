VERDICT: PASS
REVIEWER: reviewer-ux
COMMIT: c5d2515627c96736a1d8884183eb630e29617a0e
AUTHORITY: delivery UX review

## Summary
- Walked W-2601 to W-2604 and P-0106 at 1440 and 390 as the `pm` persona, on the production build with the mock. Confirm PM, Register and Record input all run through to the re-read page. The mock was reset afterwards.
- The journey reads in plain business language. The PM form is open and pre-filled with the returned hint. Register opens on press (side panel at 1440, full-height drawer at 390). Record input opens the 500px drawer at 1440 and a full-height drawer at 390, with the Team preset to the pressed row. Escape closes it and focus returns to the row button. Row buttons are 44px high. No sideways scroll on any page. "Plan a project" on P-0106 links to /work/W-2603.
- "Registered", "PM confirmed" and "Recorded" appeared only with the re-read page in my runs. The 422 and 502 runs never showed "registered" or "recorded". The uncertain case (W-2604) shows "We couldn't confirm the engagement was registered… Nothing was sent again."
- TECH-1-1 (notice before re-read): judged non-blocking. In the normal path the notice and the row change (QA "IN · 11 DEC", "3 OF 5 IN") appear together, so the PM sees one outcome. It would only mislead if the re-read fails. Note too that the notice time ("18 Nov 03:15", the mock's clock) sits above a row that reads "11 DEC"; the real backend should return the received time.
- No blocking finding. Four non-blocking points follow: a drawer after a lost reply, the disabled Prepare readiness button, the phone placement of the main action, and the phone Price cell.

## Findings
1. UX-1-1 | non-blocking | medium | frontend | /work/W-2603 at 390, Record input after a lost reply (`record-then-fail`, where the 200 is applied then answered 502). Expected: after "We've reloaded this item so you can see whether it was", the PM can see the outcome and cannot record the wrong thing. Actual: the full-height drawer covers the table, so nothing shows whether QA was recorded. The re-read had already removed QA, so Team silently switched to Infrastructure while "Who gave it" still said "QA · QA lead, PSL" and the QA file and 45 days stayed in the form. A PM could record QA's input against Infrastructure. Suggested fix: when the re-read removes the chosen team, clear Who gave it, or close the drawer onto the page with the outcome notice. This is F-18's reload behaviour hosted in the new drawer.
2. UX-1-2 | non-blocking | medium | frontend | /work/W-2603 side panel, disabled "Prepare readiness". Expected: a disabled primary button stays legible. Actual: grey text (rgb 74,83,87) on the green fill (rgb 34,118,74) is about 1.5:1, so the label is almost invisible. On phone it is a sticky bar over the table. The reason line below it reads fine. Disabled controls are exempt from WCAG contrast, but "Who receives this?" (grey on grey) shows the intended treatment. Use that disabled style.
3. UX-1-3 | non-blocking | low | frontend | /work/W-2601 and W-2602 at 390. Expected: the next action is easy to find. Actual: "Confirm PM" and "Register engagement" sit at the bottom of a long page, after the packet table and Tola's checklist, with no cue at the top besides the "Next step" line. This matches spec Conflicts 7 (same order as desktop), so it is only a note for the frame pass. A sticky action bar, as on W-2603, would help.
4. UX-1-4 | non-blocking | low | frontend | /work/W-2601 to W-2604 at 390, Price row. Expected: "Costing v2 · ₦40,951,000.00" reads as one value. Actual: the amount wraps onto its own line, outdented, under the stacked "FROM" label ("Costing v2 ·" then "₦40,951,000.00"). It is legible and no data is lost, but it looks broken beside the other rows.
5. UX-1-5 | non-blocking | low | frontend | Record drawer (F-18 form, as spec Conflicts 14 allows). "Received" is a native date-time field in US order with a 12-hour clock (mm/dd/yyyy, 04:05 pm). A Nigerian PM may mistype the date. Note for the shared form, not this feature.

## Verified
None (round 1).
