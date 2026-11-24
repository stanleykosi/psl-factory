VERDICT: CHANGES
COMMIT: 0517372f2319ecf958c8db0123b884264ab748f6
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer

## Summary
- Fidelity tool: SCR-43 desktop 1440 FAIL (coverage 52.1%, visual 81, missing 23, moved 8, extra 8); SCR-43 mobile 390 FAIL (coverage 50%, visual 79, missing 3, moved 1, extra 9). F-113 has no fidelity-exceptions.json, so the tool cannot pass until the design engineer approves the hidden parts. Most missing items are parts the spec and D-187 hide on purpose; they are not raised as defects.
- Real visual defect: the row layout is broken at both widths. The state tag collides with the "Updated ..." date, and the reference and "Open" sit flush against the panel's right edge.
- Phone: no horizontal overflow, but rows are about three times taller than the board's single-line rows.
- Looked at via `next start` on 4998 using the existing `.next` (built at head). The mock ran on 4010 because that build bakes in API_ORIGIN 4010. 4990/4991 untouched. Both of my processes are stopped.
- The fidelity report.json and side-by-side.png were NOT copied into the feature folder (the sandbox allows writing only this file). They are at `/private/tmp/claude-501/-Users-Hunchoo-psl-factory/f3d2f47a-b311-4962-a74a-1c6348f1d696/scratchpad/fidelity/SCR-43-desktop-1440/` and `.../SCR-43-mobile-390/`; the coordinator should copy them.

## Findings
- UI-1-1 | blocking | high | frontend | Tag and date overlap in every row at 1440 and 390 (for example "VERIFIEDpdated 25 Mar", "ACTION NEEDED" printed over "Updated 20 Nov"). The Tag is not laid out in its own grid cell, so the text is unreadable. Expected (board): the tag right-aligned, title and reference on the left, nothing overlapping. `frontend/src/features/projects/delivery.css:3` (6-column grid) against `DeliveryTab.tsx:56-69`. Visible in both side-by-side.png files.
- UI-1-2 | blocking | medium | frontend | At 1440 the reference ("REL-0091") and "Open" are flush against the panel's right border with no inset (the `projects__journeybody` body class appears to override the row padding set at `delivery.css:3`). The board rows have a 16px inset on both sides. Make the row padding show on both edges.
- UI-1-3 | blocking | medium | frontend | Mobile (390) row structure differs from SCR-43-mobile. The board draws one compact line per row (title left, tag right, about 40px high). The build stacks title, reference, tag, date and Open vertically at about 195px per row, so six rows take about two screens. Put title and tag on one line, with reference and date beneath in small text and Open compact. `delivery.css:13-19`.
- UI-1-4 | blocking | low | frontend | Copy and element differences that the spec does not list among the hidden parts: the board's row title is an underlined link to the line (the build has plain text plus a separate "Open"), and the panel head reads "DELIVERY LINES" where the board says "THE SIX DELIVERY LINES, IN ORDER". Restore, or ask the design engineer to list them as exceptions.
- UI-1-5 | blocking | low | design engineer | No `fidelity-exceptions.json` for F-113, so the tool reports 23 (desktop) and 3 (mobile) board items missing. The spec-hidden ones are: DLV-0052 header and "3 OF 6 DONE" tag, the "PM TUNDE BELLO" tag, the sub-nav strip (Overview, Release, Go-live, ...), the Tola card ("Checked where delivery stands", DONE, Ask Tola), the NEXT card, "Open the handover", and the per-row gate sentences. The design engineer must list them in `fidelity-exceptions.json` before the tool can pass. Also extra: "Setup" nav link, alerts, account menu (shell, not this feature), the "DELIVERY LINES" head and "Checked ..." line.

## Verified
None (round 1).

## Notes
- Rows 04 Handover and 05 Archive follow the spec (Q2 a), so they show as a swap against the board; accepted.
- Tab order Journey, Delivery, Milestones ... is fine. The board's Planning and Registers/Actions counts come from live `tabs[]` and are not this feature's.
- The static Q5 sentence at desktop only matches the board text.
- Tone tags use the existing Tag colours; the spec's table is accepted.
