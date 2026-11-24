VERDICT: CHANGES
COMMIT: f39d6dda8b095d99f19a3f9c809a2c97b71eba27
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer

## Summary
- Fidelity tool, production build (origin 127.0.0.1:4999 confirmed in routes-manifest), case 3f6c1a52-...-2001 dossier 5001, with the builder's proposed fidelity-exceptions.json (28 entries, all used, none unused): SCR-33 desktop 1440 FAIL: coverage 36% (18/50), 100% with exceptions, visual 78.8 (round 1: 79.7). SCR-33 mobile 390 FAIL: coverage 27.3% (3/11), 100% with exceptions, visual 76.6 (round 1: 78.1).
- Coverage now passes with the exceptions. Visual does not reach 90 at either width, and the gap is almost all spec-accepted additions (see UI-2-2), so only the design engineer can settle it.
- UI-1-1 to UI-1-4 verified, except phone Save is still not in the board's bottom bar (UI-2-1).
- Filled form checked at both widths (three boxes, one person, notes file chosen): Save turns the board blue (#2459D6, white text), 300x50 desktop and 326x50 phone, no horizontal overflow. The grey Save in the tool run is the disabled empty-form state, not a colour defect.
- Fidelity outputs: scratchpad fidelity/SCR-33-1440 and fidelity/SCR-33-390 (report.json, side-by-side.png), plus filled-1440.png and filled-390.png in the same folder. Servers stopped by PID; copy deleted.

## Findings
- UI-2-1 | blocking | low | frontend | Phone Save is not in the board's bottom bar. The mobile board draws a white bar at the bottom with a full-width blue button; the built Save is full width but sits in the flow after Notes file (y about 1002) with Decisions below it. The tool does not flag this (the button matches by name). Make it a bar at the foot of the form as the board draws it (sticky or last in the panel, with Decisions above it), or add it to the exceptions for the design engineer.
- UI-2-2 | blocking | medium | design engineer | Visual score is below 90 at both widths (78.8, 76.6), so the tool cannot pass. The causes are spec-approved: When it was held and Reference row, checkbox list and notes select instead of the one-line and dashed chip, Decisions block, no Cites chips or Tola panel, API checklist words, and on phone the info note and checklist the board omits (spec D-99). No code change gets to 90 without removing these. Needs the design engineer to accept the score for F-119, or to rule on the additions below.

## Verified
- UI-1-1 | verified | desktop: Save is 300x50 directly after Notes file, board blue when filled (computed rgb(36,89,214)); phone: full width 326x50. Phone bottom-bar placement remains (UI-2-1).
- UI-1-2 | verified | no panel title bar on either width (side-by-side and filled screenshots).
- UI-1-3 | verified | chips now Closed/Recorded green, Not yet red, Unknown amber as the board (words are the D-187 option).
- UI-1-4 | verified | phone boxes are bordered cards with the label inside, title 22px, no resize grip; the tool lists no style difference on the title or boxes.
- TECH/UI-1-5 to UI-1-10 | covered | by the exceptions below, none approved by me.

## Exception list for the design engineer (all 28 still needed; none dropped, none approved)
Tool run with the file: no unexcepted item; every entry matched a missing board item.
Layout
- Entries 3, 4, 5, 8, 11 (Cites:, MIN-0138, Milestone 2, ISS-0233, Test plan v2) | keep (spec hides, D-182: no live source for per-box citations).
- Entries 16, 17 (Tola panel and name) | keep (spec hides, DC-3: no live source); it also moves the checklist up the right column.
- Entry 15 (Save draft) | keep (spec hides, D-8: every save is a version).
- Entries 12, 13, 14 (who took part line, notes file name, "Uploaded · 36 KB") | keep (D-195 plain form: checkbox list of project people and a select of recorded proofs; outside parties and upload not offered).
- Entries 27, 28 (phone back link and subtitle) | keep (frame item: the shell shows the breadcrumb on phone).
- Not an exception, still a difference: the "extra" items (When it was held, Reference, Decisions, Add a decision, write-in hint, and on phone the info note and checklist) are spec-approved additions. Ask the design engineer to rule on them together with UI-2-2.
Colour
- None needed. Chip colours match the board; Save matches when filled. The tool's "looks" notes (account-name colour, "More ways to start" weight) are the shell, not this screen.
Copy
- Entries 1, 6, 9 (What went well, What didn't, Lessons for next projects) | keep (D-195: the tool reads the board's labels as plain text and the page's as textarea labels; wording is identical).
- Entries 2, 7, 10 (box sample sentences) | keep (sample content, not UI).
- Entries 18 to 26 (Go-live accepted DONE, DONE, Hypercare qualified DONE, Archive DONE, Handover received DONE, Retrospective NOW, NOW, Finance confirmation UNKNOWN, UNKNOWN) | keep (D-187: API titles and words Closed/Recorded/Not yet/Unknown; the board's "Hypercare qualified", "Handover received", "Retrospective" and NOW/DONE are not shown). Recommend the design engineer confirm D-187 covers the renamed rows.
- Fixable gaps: none in the list; UI-2-1 is the only one found.

## Notes
- Strip row "Retrospective saved · this screen" with a sub-line is the accepted spec addition (round 1 UI-1-9).
- Persona "Tunde Bello · PM" vs board "PMO", the SAMPLE DATA label and the alerts bell are shell or mock, not findings.
