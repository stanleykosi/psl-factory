VERDICT: PASS
REVIEWER: reviewer-ux
COMMIT: 5020a86be7320090efa1b2888295f52e205e761a
AUTHORITY: delivery UX review

## Summary
- Re-walked W-4001..W-4008 and W-4013 as finance_lead at 1440 and 390 against the live demo. UX-1-1 is fixed. No regressions.
- The verified strip shows six labelled cells, nothing computed. Unknown still shows as Unknown, and nothing reads approved before the backend says so.

## Findings
- None blocking. UX-1-2..UX-1-5 are non-blocking and carried forward unchanged (phone callout wording, duplicate Next sentence, agent "DONE" beside a stopped station, shared-frame touch targets).

## Verified
- UX-1-1: W-4003 button is enabled at both widths. Pressing with no choice shows "Choose what happened to continue." After "It arrived" the button is disabled and `aria-describedby` points to "Upload the proof to continue." Same at 1440 and 390.
- W-4004 strip: 6 dt/dd cells at both widths (CALCULATED, REVIEWED, DRAFTED, PUBLISHED, RECEIPTS 2 of 2, VERIFIED) with the limit caption. No horizontal overflow (scrollWidth equals viewport).
- Facts tags: ACCEPTED on W-4001; NOT SET on holds W-4006/7; no Record actuals control.
- W-4001, W-4002/5/8/13, W-4003, W-4006/7 render with the same content as round 1. The W-4002 table still shows Unknown cells (11 on the page), not 0.
- Not re-exercised: decide/return/approve submit paths (the changed code does not touch them).
