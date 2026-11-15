VERDICT: PASS
COMMIT: ab641e93900ddddcaeaa19d323f33fa9045ef9d0
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux

## Summary
- Walked /projects (Active, Closed, All I can see, search, no match, Filter dialog), P-0101 (Journey, Milestones and Money "comes next" tabs, a work item and back) and the P-0104 no-access page as pm, at 1440 and 390, on the shared build (3711).
- The list and journey follow SCR-22 and SCR-07 at both widths. The phone drops the list tabs, eyebrow, facts strip, references and Tola's summary, and shows a "← Projects" link, a summary line and a stacked journey, as the mobile boards do. D-08 to D-10 are accepted as approved.
- No horizontal scroll at either width. The phone Filter button is 44px. Escape closes the Filter dialog and focus returns to Filter. Opening a work item and going back returns to the project page.
- No-access shows "You can't open this project" and "Back to projects", with no name or code. Not-built tabs say "<Tab> comes next" and offer "Open the journey".
- Two low, non-blocking points are below.

## Findings
- UX-2-1 | non-blocking | low | frontend | With a search active on desktop, the total still reads "4 PROJECTS" while the table shows one row ("All 1 showing"). The tab counts are for the whole tab, but the label next to the search box reads as the result count. Consider "1 of 4 PROJECTS" while a search is active.
- UX-2-2 | non-blocking | low | product | On phones the Active / Closed / All tabs are hidden, as on SCR-22-mobile, so a phone user cannot reach closed projects such as Sabi Market. If that is intended, record it. If not, the board needs a phone way to see closed projects.

## Verified
- UX-1-1 | verified | Journey link names are now the unique line titles ("Invoice · Milestone 1", "Invoice · Milestone 2", "Invoice · Milestone 3"), so the link list no longer repeats. The builder's test for repeated titles adds a hidden suffix. I did not drive that case live.

## Notes
- Did not re-run axe. I trusted the builder's e2e.
- I did not drive 401, 500 or loading states live. I checked them only through the builder's tests.
- The phone journey shows the coloured square without a visible tag (D-10). The detail line says what is happening in words, so colour is not the only signal.
