VERDICT: CHANGES
COMMIT: 59ce7dc1e6896a89a54ccd7e83cf2addf5b51937
REVIEWER: reviewer-ui
AUTHORITY: delivery UI review

## Summary
- Review, investigating and the desktop uncertain board fit the shared frame. Their remaining gaps are covered by Conflicts items and the D-83 waivers (71.3 to 84.6, all above the floor of 70).
- The verified board (both widths) hides a real layout difference behind "tool limit" exceptions. The board draws a dark strip of six figures with a caption under it. The page draws a white list of rows and a boxed panel. No Conflicts item allows this.
- The Sources "ACCEPTED" and Confirmation "UNKNOWN" tags are sent by the fixtures but not drawn: `FactsList` ignores `item.tag`.
- On the phone uncertain page, the record choices sit above the station bar and the banner, with an empty gap of about 80px.
- I did not re-run the fidelity tool. This review reads the builder's round-1 run (`round-1/fidelity/*/report.json` and `side-by-side.png`) and live screenshots of W-4001 to W-4004 at 390 and 1440 on :4895.

## Findings
- UI-1-1 | blocking | medium | frontend | **Verified figures: the tool-limit exceptions hide a restyle and a move.**
  - Board: SCR-56-desktop-verified draws CALCULATED / REVIEWED / DRAFTED / PUBLISHED / RECEIPTS / VERIFIED as one dark (ink) strip of six cells. Each cell has a mono label over a bold display value, and the VERIFIED cell is green. The limit sentence is a muted caption under the strip, with no box. SCR-56-mobile-verified draws the same strip as a 3x2 dark grid.
  - Page: the `figures` section is a white bordered list. Labels are on the left, mono values on the right, in six stacked rows (`Sections.tsx:371-383`, `.ws-row`). The limit sentence is its own boxed `text` panel. At 390 that panel's text touches its top border, with no top padding (live W-4004 at 390).
  - The text check on the "tool limit" exceptions is genuine. `extract.mjs:252` skips any span inside an `li`/`td` whether or not the parent has its own text, and every value is on the page. But these 10 exceptions are also the only thing that would have reported the restyle and the move. The verified waiver cites Conflicts 14, which says only that strings are data, not that the strip may become a list. The spec's Decisions (`spec.md:187`) call it "an untitled `figures` strip". AC 22 forbids an exception over a value the data supplies.
  - Expected: on `cash_forecast`, draw the figures as a strip. Extend the F-30 `.ws-section--strip` pattern (`workspace.css:212-222`, today for `facts` only) to this line's `figures`, using tokens: ink surface, label over value, success tone from data on the verified cell, six columns at 1440 and a 3-column grid at 390. Draw the limit sentence as a plain muted caption under it. Or the design engineer signs a separate exception with its own Conflicts number. Either way, the "tool limit" category must not stand in for it.
- UI-1-2 | blocking | medium | frontend | **Tags sent in `facts` items are not drawn.**
  - W-4001 Sources sends `tag: {label: "ACCEPTED", tone: "verified"}` and W-4003 Delivery sends `tag: {label: "UNKNOWN", tone: "uncertain"}`. The boards draw both as tinted tags (green ACCEPTED, amber UNKNOWN), and the spec's Decisions (`spec.md:186`) fix those tones.
  - `FactsList` (`frontend/src/features/workspace/Sections.tsx:167-184`) renders only `item.value`. Both appear as plain grey mono text at 1440 and 390, so the tone the backend sends is lost.
  - The tool matched the words, so no exception or waiver lists this.
  - Expected: when a `facts` item carries `tag`, draw `<Tag tone={tagTone(item.tag.tone)}>` in the `dd` instead of the bare value, as the `figures` and `recipients` rows already do. This changes shared Sections, so other lines' facts with a `tag` need a check. A line-scoped alternative must be listed.
- UI-1-3 | blocking | medium | frontend | **Phone uncertain page is in the wrong order and has a gap.**
  - Live W-4003 at 390 shows, in order: status tag; the reconcile callout "Confirm what happened before anything is resent." and its three choices; "Your choice is recorded with your name."; an empty gap of about 80px; then the mini station bar and "STATION 7 OF 8 · PUBLISH"; then the problem banner; then Delivery and Next.
  - The board puts the station line straight under the title and the banner under it. Spec Conflicts 10 says the reconcile panel uses its existing phone layout, "pinned button, choices above".
  - The station line and banner are pushed below the choices, and the gap breaks the page's rhythm. No exception covers it.
  - Expected: on `cash_forecast` at phone width, order the page as title, status, station line, banner, Delivery, Next, then the choices above the pinned "Record and continue", with no empty block. `reconcileBeside` is false on phone, so the overview's `ReconcilePanel` (`WorkItemOverview.tsx`) still renders ahead of the workspace.
- UI-1-4 | non-blocking | low | frontend | **The "Unknown" exception should not be listed as a tool limit only.**
  - On the review board (1440 and 390) "Unknown" is plain body text. The page draws the shared `Unknown` as a tinted chip.
  - The text miss is a genuine tool limit (a span inside a `td`). The style difference is real, and it is named only in the review waivers ("Unknown tags").
  - Recategorise this exception as `component` (shared Unknown chip, Conflicts 1/14), so the design engineer signs the look and not just a tool gap.
- UI-1-5 | non-blocking | low | frontend | **Side column named "Review and decide" with nothing to decide.**
  - On W-4001 (investigating), the side column holding only Chidi's agent card is announced as "Review and decide" (`Workspace.tsx:774-775`, F-33 code path).
  - There is nothing to review or decide in this state. Name the landmark after its content (for example, from the agent card heading) when there is no decide task.

## Verified
- Per-board results from the builder's run (`round-1/fidelity/scores.txt`), with coverage after the proposed exceptions as recomputed in build.md:

| board | coverage | after exceptions | visual |
|---|---|---|---|
| desktop investigating 1440 | 86.1 | 100 | 84.6 |
| desktop review 1440 | 74.6 | 100 | 75.6 |
| desktop uncertain 1440 | 84.6 | 100 | 71.6 |
| desktop verified 1440 | 68.8 | 100 | 75.8 |
| mobile investigating 390 | 77.8 | 100 | 83.8 |
| mobile review 390 | 56 | 100 | 78.4 |
| mobile uncertain 390 | 57.1 | 100 | 71.3 |
| mobile verified 390 | 29.4 | 100 | 72.6 |

  - The tool's own `coverageWithExceptions` equals raw coverage because the run used an empty exceptions file.
  - Every missing element in the reports maps to one of the 38 proposed exceptions.
  - All 8 waivers are at or above 70, so no floor exception is needed.
  - Signatures are pending; that alone does not block.
- **Tool-limit exceptions, one by one.**
  - "Unknown": the text miss is genuine. The style difference is real but named in the review waivers (UI-1-4).
  - CALCULATED, REVIEWED, DRAFTED, PUBLISHED, RECEIPTS, "12 Nov", "13 Nov", "14 Nov", "2 of 2", and "The forecast never moves cash or authorises a payment.": all are present on the page, so the text miss is genuine. But they hide the strip-to-list restyle and the caption-to-panel move (UI-1-1).
- **Other differences checked by reading the side-by-sides and live pages; each is covered by its Conflicts item or waiver.**
  - Compact amounts drawn as full amounts (C1), and the six table rows (C2).
  - Cancel delivery and the shorter Next sentence (C3).
  - ReconcilePanel in the desktop side column above Next (C4).
  - No Record actuals (C5).
  - Basis without bold, and the note label (C6).
  - Phone wording, the "Return with a note" label and CALC/2/2 (C9), and the phone showing desktop sections (C10).
  - Frame: crumbs, Queue back link, alerts bell, History, and station tiles drawn by the shared StationTrack with status lines (C11).
  - Banner without a bold lead (C12), the signed-in name (C13), and the AgentCard head with "step 4 of 4" (C15).
- **Tokens and layout.**
  - The CSS diff is three additive, line-scoped rules with tokens only and no hex or px. InlineDecide, ReconcilePanel, Drawer, Tag and AgentCard are reused, with no component copies.
  - No page overflows at 390: `scrollWidth` is 390 on W-4001 to W-4004, and the table scrolls inside its own region.
  - The desktop eight-station row fits at 1440.
- **Contrast.** Tags, the warning callout, the problem banner and the pinned buttons use the existing tone tokens, and no low-contrast text was seen.

## Notes
- The phone reconcile callout still says "Confirm what happened before anything is resent." while the desktop heading says "Record what happened". Conflicts 4 changed only the heading, the accessible name and the desktop sentence. The design engineer may want the phone wording aligned.
- Fact labels are bold on the page (`.ws-fact dt` weight 600) and regular on the boards. This is the shared style across lines, so it is a taste matter for the design engineer, not this feature.
