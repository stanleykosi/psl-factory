VERDICT: CHANGES
REVIEWER: reviewer-ui
COMMIT: ea9718cd5eeb3fd267df59ebb13d7373165cd43e
AUTHORITY: delivery UI review

## Summary
- I read the builder's single scored run in `round-1/fidelity/` and did not re-run it, because round 2 changed no layout. Coverage is 100% after exceptions on all 4 boards. The visual scores are under 90 on every board: SCR-20 84.5 / 71.1 and SCR-32 76.9 / 79.2.
- Most of each gap comes from the D-115 recommendations (provisional) and the F-17 line frame (D-83). I can waive SCR-20 desktop, SCR-32 desktop and SCR-32 phone once the fixable items below are done.
- SCR-20 phone (71.1) can be waived, but only just. Almost all of its loss comes from Conflicts 12 (the full strip, the PAID card and the full note) and Conflicts 1 (no pinned "Record" bar). The design engineer should look at this board on its own before signing, because answering Conflicts 12 with Option B would recover most of the loss.
- There are 2 fixable gaps, so this round cannot pass under D-83 ("no fixable gap"):
  - On phones, "Open the reminder draft" is an 18px-tall target.
  - The reminder's attachment is drawn as a blue tile that looks like a link, where the board draws a dashed box with a paperclip.
- Every one of the 35 exceptions maps to a spec Conflicts item. No exception hides an amount the data supplies: each amount exception is a tool-pairing limit, and the value is visibly on the page. The CSS uses tokens and library components. Nothing overflows sideways at 390.

## Findings
- UI-2-1 | blocking | medium | frontend | The phone tap target on the list's main route to the reminder is too small. Chidi's "Open the reminder draft" measures 152x18 at 390 on the live build (localhost:4955, finance_lead). It is a standalone link, not a word inside a sentence. Spec AC22 and the project's 44px phone rule (tokens.json size note, shell.css:18) require at least 44x44. Build.md AC22 claims "every target is at least 44x44", but this link fails that. Expected: the link fills a target at least 44px tall on phones (for example `display:inline-flex; min-height: var(--control-lg); align-items:center` under the phone media query), with its look unchanged. Actual: 18px. `frontend/src/features/finance/payments/PaymentsView.tsx:219`, `payments.css` (phone block).
- UI-2-2 | blocking | low | frontend | The reminder's attachment is restyled away from the board, on a style this feature owns. SCR-32 desktop and phone draw "INV-0391.pdf / Uploaded · 84 KB" in a neutral box with a dashed `--rule` border and a paperclip icon, under the message. The page draws it as an `--action-tint` tile with bold `--action-ink` text. That is the same colour pair as the links and agent notes, so a non-link reads as clickable, and spec item 8 says it is "never a link". The exceptions for "INV-0391.pdf" and "Uploaded · 84 KB" (category `tool limit`) cover where the tool pairs the element, not this restyle. `.ws-attachment` is new in this feature, so this is a fixable gap and not frame work. Expected: a neutral surface with a dashed border and the paperclip glyph from the icon set, and ink-colour text. Its position inside the message section can stay, as listed. `frontend/src/features/workspace/workspace.css:75-76`, `Sections.tsx:113-116`.
- UI-2-3 | non-blocking | low | frontend | The "Updated 12 Nov 10:00" line sits at the right of the title row (it takes the held button's place). Spec item 15 places the "as of" line "beside the count", following the F-25 precedent. On phones the count ("4 INVOICES") and "Updated" also end up on different rows. Moving it beside "4 INVOICES" would follow the spec and drop one extra element from the title row. `payments.css:9-10`.
- UI-2-4 | non-blocking | low | frontend | On desktop the table starts about 10px lower than on the board: the gap between the chip row and the table is larger, apparently the `.payments__main` gap of `--space-3` plus the toolbar's own margin. It is a small rhythm difference. Worth closing while UI-2-1 is fixed.
- UI-2-5 | non-blocking | low | product | Exception mapping. The four "INV-xxxx" link exceptions cite Conflicts 16, but item 16 is about "every board string is data". No spec item says the reference is a link only when the row sends `work_id`. The behaviour is right (no invented link, and no field exists), but the design engineer should sign it as its own item, next to the G-SCR20 gap, rather than under 16.

### Exceptions check (35 exceptions, 4 waivers)
- Each exception maps to a spec Conflicts item:
  - Conflicts 1, Record button: 1 exception.
  - Conflicts 6, the 7-day sentence: 1.
  - Conflicts 8, attachment: 2.
  - Conflicts 12, phone list cards and note: 14.
  - Conflicts 13, phone reminder: 4.
  - Conflicts 14, frame and persona: 6.
  - Conflicts 16, components and data strings: 7 (see UI-2-5).
- Amount exceptions: "₦0.00", "₦500,000.00", "Still owed ₦500,000.00", "Still owed ₦6,800,000.00", "₦6,800,000.00" (SCR-32) and "INV-0391 · ₦6,800,000.00". In both side-by-sides each value is drawn on the page from the fixture. Both known zeros (INV-0391 RECEIVED, INV-0388 STILL OWED) are present. "Still owed Unknown" is drawn as the library's Unknown. No exception stands in for a value the data supplies.
- "INV-0391 · ₦6,800,000.00" and "21 days overdue · no reminders yet" (phone) are composed summary lines with no source. Their values appear as the separate facts Amount and Overdue by, so they are correctly listed under Conflicts 13.

### Per-board waiver judgement
- **SCR-20 desktop 1440 (84.5, list: needs the design engineer's board-level waiver).** The strip, coverage sentence, toolbar, chip, table columns, tags and Chidi's note match in place, colour and type. What remains:
  - the held Record button (Conflicts 1);
  - plain mono references (UI-2-5);
  - the library's amber `Unknown` tag where the board has bold amber words (Conflicts 16, library component, same as F-26);
  - INV-0388 STILL OWED ₦0.00 is bold, because the page does not style a cell by its amount (listed);
  - the note's lines split into paragraphs (AC9);
  - the "Updated" line (UI-2-3);
  - the shell's nav, bell and persona (Conflicts 14);
  - the board's broken avatar image.
  **Waivable** after UI-2-1. UI-2-3 and UI-2-4 are recommended.
- **SCR-20 phone 390 (71.1, list, 1.1 above the floor).** The board shows only "Owed to PSL" as one line, three cards, a one-line note and a pinned Record bar. The page shows:
  - the 4-cell strip stacked;
  - the coverage sentence;
  - 4 cards (PAID included);
  - the full note;
  - "4 INVOICES" beside Filter;
  - no pinned bar.
  Each of these is an item D-115 took as recommended (Conflicts 12, 1 and 15), so this is not build error. The cards themselves (border, title, tag, "Still owed", ref line) match the board closely. **Waivable** after UI-2-1, on condition that the design engineer confirms Conflicts 12. If Option B is chosen (phone shows "Owed to PSL" only, as drawn), the score should recover well above the floor and this waiver may not be needed.
- **SCR-32 desktop 1440 (76.9, line workspace, D-83).** The differences all come from the F-17 frame, which is approved under D-83 and D-69:
  - the Decide panel on the right, with green "Send reminder", Edit and Not now;
  - To/Copy/Subject and the message paragraphs drawn as rows;
  - "This invoice" in the main column, with mono values;
  - the agent note at the top;
  - "Draft v1", "ACTION NEEDED" and History.
  The 7-day sentence is held (Conflicts 6). The one fixable gap is UI-2-2. **Waivable** after UI-2-2.
- **SCR-32 phone 390 (79.2, line workspace, D-83).** It shows the same sections as desktop in one column. The frame's pinned bar carries Send reminder, Edit and Not now and wraps at 390, as the spec allows. The back link reads "← Queue" (Conflicts 13 and 14). There is no sideways scroll and the bar's buttons are 44px or taller. "History" is 42x24, but it belongs to the F-17 frame and is carried, not raised here. **Waivable** after UI-2-2.

## Verified
- None: this is reviewer-ui's first review of F-41. The round-2 fixes (TECH-1-1, -2, -3) are outside the UI lens and changed no layout.

## Notes
- Live check on localhost:4955 (finance_lead, read only, no writes on the mock), at 390 and 1440 on both pages:
  - `scrollWidth` equals the viewport width.
  - At 390, the only targets under 44px are "Skip to main content" (the shell's, shown on focus), "Open the reminder draft" (UI-2-1) and "History" (frame).
- Tokens: `payments.css` uses token variables throughout, and the bundle classes are composed. Taste only:
  - `.payments .psl-tag { border-radius: 0 }` locally squares the library tag to match the board. If square tags are the canvas's rule, the library tag should change, not this one screen.
  - `min-width: 900px` and `max-width: 380px` are bare layout numbers.
- The fidelity artefacts are in `round-1/fidelity/<board>-<width>/` (report.json, side-by-side.png). They were not copied to `round-2/` because the coordinator directed that the round-1 run stands.
