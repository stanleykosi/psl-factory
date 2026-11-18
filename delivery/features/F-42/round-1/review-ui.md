VERDICT: CHANGES
REVIEWER: reviewer-ui
COMMIT: 5fd62b4c65d9c80c66ebf0f6e3dd37bb0ddb8dc0
AUTHORITY: delivery UI review

## Summary
- Costs on register review (W-3902): drawn correctly, digit for digit, in the board's place and style at 1440 and 390. The fidelity tool misses them because it does not read inside table cells. Those three exceptions cover a tool limitation; the design engineer accepts them.
- Proof line on date review (W-3903): the file name is drawn in capitals, as "ASSET-DATES-EXPLANATION.PDF", in small grey monospace on the far right of the row, and it wraps onto two lines on the phone. The board draws "asset-dates-explanation.pdf" above "Uploaded · 64 KB". The two proof exceptions do not cover a tool limitation. One finding blocks: UI-1-1.
- Side-by-side, all 8 boards: apart from UI-1-1, every remaining gap is in the shared frame, StationTrack, AgentCard or Sections, or in an approved D-118 Conflicts item. They can be waived under D-83 once the design engineer signs. Two of them need the design engineer to look closely (UI-1-2, UI-1-3).
- Tokens, components, overflow, targets: the only CSS added uses existing tokens, with no hard-coded colours. Nothing overflows at 390. The phone buttons meet 44px. F-33's W-2702 looks unchanged at 1440 and 390: the code change is a rename that also covers the new line.

## Findings
- UI-1-1 | blocking | medium | frontend | The proof file name is drawn wrong, and the exceptions call it a tool false-miss. Fixture `cites[0].label` is "asset-dates-explanation.pdf". The page draws it as `span.ws-ref` with computed `text-transform: uppercase`, in IBM Plex Mono 12px, colour ink-muted (rgb 74,83,87), on the right of the row (x 779 at 1440). It reads "ASSET-DATES-EXPLANATION.PDF", and at 390 it wraps to "ASSET-DATES- / EXPLANATION.PDF". "Uploaded · 64 KB" sits alone on the left. The board (SCR-55-desktop-date-review, SCR-55-mobile via the same section) draws the file name in its own case, on its own line, with the detail under it, at x 146. Conflicts 12 (D-118) approves only dropping the paperclip and the bold. It does not cover the capitals, the monospace grey or the move. A file name's case is part of the value. Expected: on the fixed_assets line, the cite label in its returned case, in body text (no capitals or mono), placed above "Uploaded · 64 KB", the way the board draws it. Scope it like the existing `.ws[data-line="fixed_assets"]` rules in `frontend/src/features/workspace/workspace.css:272-279` so F-33 and other lines are untouched. Then rewrite the "asset-dates-explanation.pdf" and "Uploaded · 64 KB" exceptions in `fidelity-exceptions.json` (keep them only if the tool still misses them once the text matches), and re-score the two date-review boards.
- UI-1-2 | non-blocking | low | design engineer | Investigating (W-3901, 1440 and 390): the register's values note "Chidi never reads asset values; he checks structure, dates and provenance." is drawn as the shared amber warning box with a warning icon. The board draws a plain muted line. This comes from Sections' facts `note`, which the approved spec chose (spec Decisions, "Values note"). The waiver covers it, but a warning tone on a reassurance is a change in meaning the design engineer should look at when signing the waiver.
- UI-1-3 | non-blocking | low | design engineer / backend | Calculating (W-3904, 1440 and 390): the Calculate station is amber with "Waiting" (shared StationTrack). The board draws it blue for "in progress". The builder's reason holds: `current_agent` would draw "Agent working" for a factory step. It needs a station status for a running factory step from the backend (backend handoff). Waivable under D-83 until then. No Conflicts item covers it, so the design engineer signs it explicitly.

## Fidelity per board (builder's single run, round-1/fidelity/, not re-run)
| Board | Width | Coverage | With exceptions | Visual | My reading |
|---|---|---|---|---|---|
| SCR-55-desktop-investigating | 1440 | 84.8 | 100 | 84.1 | Waivable (frame, StationTrack, AgentCard head per Conflicts 15; UI-1-2) |
| SCR-55-desktop-register-review | 1440 | 86.3 | 94.1 (100 with the cost exceptions) | 75.0 | Waivable. Costs correct; tool limitation |
| SCR-55-desktop-date-review | 1440 | 90.4 | 96.2 | 74.5 | Fixable: UI-1-1. The rest is waivable (frame, taller shared table rows, Proof as its own titled section per the spec data shape) |
| SCR-55-desktop-calculating | 1440 | 89.7 | 100 | 74.6 | Waivable (frame; UI-1-3) |
| SCR-55-mobile-investigating | 390 | 77.8 | 100 | 82.4 | Waivable (Conflicts 9, 10, 11, 15; UI-1-2) |
| SCR-55-mobile-register-review | 390 | 75.0 | 100 | 84.4 | Waivable (Conflicts 9, 10, 11). Table stacks one cell per line, costs in full, no overflow |
| SCR-55-mobile-date-review | 390 | 75.0 | 100 | 87.1 | Fixable: UI-1-1 (the file name wraps in capitals). The rest is waivable |
| SCR-55-mobile-calculating | 390 | 80.0 | 100 | 89.1 | Waivable (Conflicts 9, 10, 11; UI-1-3) |

Missing and extra elements match the reports: the frame crumbs list, History, the alerts bell, the /me name and "← Queue" (Conflicts 11, 13); the AgentCard name, limits and step on their own lines (Conflicts 15); the note label "(needed to return or reject)" (Conflicts 7); the phone step labels and the full tables in place of the summaries (Conflicts 10). Table styling: the shared `ws-table` rows are about 37px tall against the board's 35px, with the same rules, header type and column order. Costs are left-aligned on both, as on the board.

## Ruling on the post-run exceptions
- "₦8,400,000.00", "₦14,000,000.00", "₦3,150,000.00": fixture amounts are "8400000.00", "14000000.00" and "3150000.00" NGN. The page text at 1440 and 390 is exactly "₦8,400,000.00", "₦14,000,000.00" and "₦3,150,000.00". Each is one visible `span` in the COST `td`, IBM Plex Sans 14px, in ink colour, in the board's column. This is a tool limitation, not a value the page fails to draw. The exceptions can stand, labelled as tool limitations, for the design engineer to accept.
- "asset-dates-explanation.pdf", "Uploaded · 64 KB": the detail is correct, but the file name is drawn in capitals and moved (UI-1-1). Not a tool limitation as things stand.

## Targets and tokens
- Phone (390): Approve, "Return with a note", Reject, Start, the alerts bell, "← Queue" and Ask Chidi all measure 44px or more in height. The frame's History link is 42x24 on every work page, W-2702 included. It is a shared frame item and not new here.
- Desktop: History 42x17 and Ask Chidi 57x20 are the shared frame and AgentCard links, as on F-33.
- `workspace.css:272-279` uses `--space-*`, `--rule-*`, `--ink-muted` and `--text-small-size` only. The TSX changes only switch the existing income-line checks to `scheduleLine()`.

## Notes
- Loading W-3902, W-3903 and W-2702 makes the app itself POST `/tasks/<id>/claim` when the page opens. My read-only page loads therefore sent claim POSTs to the mock (T-3902, T-3903, T-2702). I did not call reset. The builder's run.sh resets the mock before each board.
- Screenshots: /private/tmp/claude-501/-Users-Hunchoo--claude-spares-spare-2d2Z3S/0986a60c-391e-48d6-b2da-79de8713a755/scratchpad/ui/
