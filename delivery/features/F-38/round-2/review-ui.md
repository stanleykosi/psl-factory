VERDICT: CHANGES
REVIEWER: reviewer-ui
COMMIT: 273d81b5b7cb2d146cd010383cb6f5a40e9e6b96
AUTHORITY: delivery UI review

## Summary
- Fidelity tool not re-run (as instructed); judged from round-2 scores.txt, fixtures and live pages at 1440 and 390 (app 4985, mock reset, persona pm; W-3501..3505 plus approve then "didn't arrive").
- The drawable round-1 findings are fixed and come from returned data. The round cannot pass the gate: all 8 boards score visual 76.7 to 89 (need 90) and the 8 waivers are unsigned (design engineer only). Several remaining items are shared-code gaps, not this line.

## Findings
- UI-2-1 | blocking | high | process | Visual is under 90 on all 8 boards (desktop 89 / 76.7 / 84.7 / 79.5; phone 78.4 / 79.3 / 83.6 / 81.3) and every visual_waiver and all 26 exceptions say "pending design engineer (not signed)". Coverage 100 holds only after approval. Needs the design engineer to sign or reject the waivers; nothing here can be self-approved.
- UI-1-8 | blocking | medium | frontend | Still open. At 390 the draft page puts Send for review and Edit cover letter at the end of the Next card in normal flow (not a pinned bar), the History link is 42x24 below the Start bar, and the stack is longer than the board. The submitted pages do have a bar ("Record the outcome") but it overlays content in a full-page capture; judge in the viewport. The waiver text calls this "a section, not a fixed bar", so it is a known deviation of a drawn board element, not an honest exception unless signed.
- UI-1-4 | non-blocking | medium | frontend | Tab nav still has the 5 role/name exceptions and the dark "Submission" chip (shared F-18 frame). Honest only if the design engineer signs them; the page matches the board visually apart from the chip fill.
- UI-1-9 | non-blocking | low | frontend | Kemi Adebayo / Overview / Setup exceptions blame "no PMO Lead persona" and "page never reads /me". The top bar is shell, so this is a shell gap, but the first reason is a mock gap (a PMO Lead persona can be added), which the CEO rule says is not grounds for omission. Please add the persona or have it signed as shell.
- UI-1-5 | non-blocking | low | frontend | Title is 24px wide-set (phone 20px) as the board, but stays h2 under the frame's h1. Heading level difference is not visible; accept via sign-off.
- UI-1-6 | non-blocking | low | frontend | Shell nav colours/underline, agent card DONE tag colour, decide caption colour, section-header bar and note label ("needed to return or reject") remain shared-code deviations, honestly listed. Tola line "Tola · PMO agent · done" and "Cannot approve, send or pay." also remain.

## Verified
- UI-1-1 | verified | "Record the outcome" is a blue primary button inside the NEXT card at 1440 (W-3503, W-3504) and a pinned bottom bar at 390.
- UI-1-2 | verified | Success banner is a green band with a check icon at 1440 and 390; "RECEIPT CONFIRMED" is a small secondary tag.
- UI-1-3 | verified | Receipt ref TL-SUB-0091 is drawn from returned data in the band and timeline; phone top bar shows "Done"; draft shows "v1" and "DEADLINE 28 NOV · 6 DAYS". The one-line phone sentence exceptions (Conflicts 20) stay as the contract returns one sentence; honest.
- UI-1-9 | verified (Tola) | "Drafted 22 Nov 10:15" and Ask Tola drawn on W-3501 at 1440 and 390.
- UI-1-10 | verified | The blue info note ("If delivery hadn't been confirmed...", portal variant too) is drawn on both submitted pages at both widths.
- UI-1-5 | verified (size) | Submission title is 24px at 1440, 20px at 390.
- UI-1-6 | verified (Submitted tag) | "SUBMITTED 26 NOV" is an amber chip with amber text.
- UI-1-7 | verified (link, Reject) | "Open the full pack" is a plain link; Reject is neutral.
- Removed exceptions: none removed this round; every remaining missing-type exception was still hit in the builder's run, and the live pages still show those differences.
- No sideways overflow at 390 (scrollWidth 390) on W-3501 to W-3505, nor on the uncertain and not-delivered states. Email addresses break mid-word in tables (taste).
