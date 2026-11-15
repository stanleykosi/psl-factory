VERDICT: CHANGES
COMMIT: 713e628b94ce0babdd045dbb45f17ac85cafb507
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer (fidelity gate)

## Summary
- I re-ran the gate on all 10 SCR-03 boards against the shared build on 4631 (mock 4632). I re-drove the done and stale pages through the real UI and served them on 4633. Every score matches build.md exactly: desktop default 91.1, done 93.6, not-yours 91.4, own 91.6, stale 88.2; phone default 85.0, done 92.0, not-yours 84.7, own 77.8, stale 79.3. All 10 boards have 100% coverage after exceptions.
- The tool does not read `visual_waivers`, so it still reports `pass: false` on the five boards D-56 waived. On desktop-stale, phone-own and phone-not-yours, the gap is the waived content plus content D-55 or the spec already approved. On phone default, the named rows are only part of the gap (about 1.5 of 5.0 points). The rest is D-55 or frame content, so it is covered, but the waiver text understates it. On phone stale, part of the gap is styling that no waiver or test requires (UI-1-2).
- Both done boards (they pass the score) draw the next-step card with the wrong surface and the wrong Chidi pose (UI-1-1).
- All 26 exceptions are justified, and none hides an omission. The two D-55 choices render well: the disabled comment box and the chain placed below the board content.
- Tokens only (the colour grep is empty, no inline styles). No overflow at 390.

## Findings
- UI-1-1 | blocking | medium | frontend | Done view next-step card does not match SCR-03-desktop-done and SCR-03-mobile-done. Expected: the boards draw the card on the blue agent surface (`--action-tint`, the same surface as the agent card elsewhere on this page) with Chidi's finance "done" pose, thumbs up (`/_blob/27e20cde…` = finance.done in design/mascots/canvas-assets.json; the asset is in design/mascots/transparent/finance-done.png). Actual: the card is a green `psl-callout--success` with the "working" pose. On phones the text is `--action-ink` blue on that green surface, a token pair the boards never use (frontend/src/features/decide/DecideStates.tsx:402 and :421; decide.css:291). The score still passes because the shape matches, but the colour and the mascot are visibly off at both widths and no conflict or waiver records this. Fix: use the info/action-tint surface and a local done pose in features/decide (do not edit work-item/labels.ts; that is the F-14 seam). See fidelity-review/SCR-03-desktop-done-1440/side-by-side.png and SCR-03-mobile-done-390/side-by-side.png.
- UI-1-2 | blocking | low | frontend | SCR-03-mobile-stale: part of the gap is outside the D-56 waiver, which covers only the two stacked version panels and the stale content the tests check. (a) The board draws the agent note inside the current version card, below a 2px ink rule. The page draws a separate card with a 2px `--action` border (decide.css:78). The phone default already does the inside-the-card version (decide.css:212). (b) The board draws the current card's Amount in the mono display figure (the same style as the phone default's Amount row). The page shows plain body text. (c) The board puts the "changed" and "unchanged" marks in small muted type under or after the value. The page uses an inline "· changed" in bold red. No test requires any of these three, and none is in Conflicts 16. Expected: match the board inside the kept two-panel layout, or have the design engineer extend the waiver. See fidelity-review/SCR-03-mobile-stale-390/side-by-side.png.

## Verified
None (round 1).

## Notes
- Waivers, board by board:
  - desktop-stale: the gap is only the Basis row plus the "Changed since Invoice v2" cell (builder measured 95.1 without them). Confirmed.
  - phone-own: the gap is the criterion-17 values, "Open the work item" and the chain. Confirmed against the waiver plus D-55.
  - phone-not-yours: the gap is the disabled comment box, plus the alert line, "Open the work item" (Conflicts 14), the chain (D-55), the sub-line and "+ Start". These are covered by D-55 and the frame.
  - phone default: the waiver names only the Version and Prepared-by rows. The rest of the gap is the chain (D-55), the agent's "Cannot approve, send or pay." with "See his steps" (Conflicts 8), the Note field (Conflicts 11) and "+ Start" (frame). Everything is approved somewhere, but "Everything else matches" in the waiver text is not literally true. It is worth correcting the waiver wording when it is next signed.
- DE-5 (the frame's "+ Start" in the phone bar, about 1.7 points on every phone board) is still open. It is a shell matter (F-05 and F-15), not F-16's. Owner: product, design engineer.
- The 26 exceptions are all justified. Frame: 1-4. Prototype affordance: 5-6. Contract or eligibility words: 8, 9, 12, 16, 17, 19, 20. Tool reading limits on seam markup, with the values visible in place: 13, 14, 15, 21-23. Board disagreements: 7, 10, 11, 18, 24-26. But every entry still reads `approved_by: "builder proposal, pending design engineer"`. D-55 accepted the recommendations and D-56 signed the waivers, so the file should record that sign-off before merge (owner: product).
- D-55, the disabled comment box: the grey textarea, the "Comments aren’t available yet." hint and the muted "Add comment" button (pinned on phones) read clearly as unavailable. The box is not mistaken for a live control. Good.
- D-55, the approval chain: on desktop it sits under the board content in the main column, and on phones after the card. It never displaces board content, and it stays in the same position across default, not-yours and own. Good.
- The done page shows the eyebrow "YOU APPROVED · 21:06" (real `decided_at`) next to the fact "APPROVED 10:47" (fixture `presentation.facts`). It only happens on the board fixture, but the page shows two times for one approval. Consider dropping the fixed time from the W-1901 approve sidecar.
- On desktop done, "Paid is tracked separately by Finance" appears twice: once inside `next_step` and again as the Paid line. Taste or content, not blocking.
- Phone default: "Changed since Invoice v1" wraps to three lines in the 74px label column (exception 15). Acceptable, but it is the largest single rhythm break on that board.
- Not-yours and own titles read "Approve invoice v2" with the sub-line, while the boards draw "Approve the Milestone 2 invoice?" and "Lagoon Health · Milestone 2 invoice". The tool matched both at 80%, and this follows Conflicts 3 (`task.title`). Fine.
- Desktop stale: the new email value is not bold and "changed" is red where the board draws it in ink. These are the kept F-04 marks. Minor.
- Evidence: `round-1/fidelity-review/<board>-<width>/report.json` and `side-by-side.png` for all 10 boards. Frozen pages were regenerated with the driver adapted to 4631, 4632 and 4633 in a scratch folder. The 4633 server is stopped and the mock was reset afterwards.
