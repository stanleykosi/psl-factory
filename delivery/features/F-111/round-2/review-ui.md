VERDICT: PASS
COMMIT: 30143e1a4f9376200d9fc6f89797ff57e97a3b54
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer

## Summary
- D-193 sync-only re-check of 30143e1a (from 8a5c09fe): the merged F-71/F-64 range changes decide.css, money.css and project-tabs.css, but the issue route does not import them. A live work id (/work/5101) draws LiveWorkItemView, which imports work-item.css and no changed file; the shared components, shell, workspace, styles and tokens are unchanged, and psl-unknown changes are scoped under .ptabs__ms and .ptabs__card. VERDICT stays PASS; signed D-203 fidelity result stands, fidelity not re-run.
- UI-1-1 and UI-1-2 verified. UI-1-3 (amber banner) and UI-1-4 (frame next-step line) are accepted risk under D-202: counted as exceptions, not findings.
- Fidelity run, 8 SCR-30 boards, with the builder's 57-entry fidelity-exceptions.json. The tool still FAILs every board: visual is 74.8 to 84.4 (needs 90, so D-83 waivers are required), and after the exceptions fix coverage is 100% on all eight.
- Coverage with exceptions: desktop default 97.1, overdue 96.4, no-owner 92.3, verified 96.2; all four phone boards 100.
- Production copy of head built under the lock (API_ORIGIN 4999 confirmed in routes-manifest), Next on 4998 (pid 93070), mock on 4999 (pid 92641); both stopped, copy deleted. Outputs: /private/tmp/claude-501/-Users-Hunchoo-psl-factory/f3d2f47a-b311-4962-a74a-1c6348f1d696/scratchpad/fidelity/<board>-<width>/ (report.json, report.html, side-by-side.png). Pages: 5101 default, 5102 overdue, 5103 no-owner, 5104 verified; cookie psl_mock_persona=pmo_lead.

## Scores
| Board | Width | Coverage | With exceptions | Visual | Missing / moved / extra | Unexcepted |
|---|---|---|---|---|---|---|
| SCR-30-desktop | 1440 | 50% | 100% | 74.8 | 17 / 5 / 18 | none |
| SCR-30-desktop-overdue | 1440 | 39.3% | 100% | 77.6 | 17 / 1 / 18 | none |
| SCR-30-desktop-no-owner | 1440 | 34.6% | 100% | 84.4 | 17 / 0 / 18 | none |
| SCR-30-desktop-verified | 1440 | 38.5% | 100% | 83.6 | 16 / 1 / 17 | none |
| SCR-30-mobile | 390 | 17.6% | 100% | 76.5 | 14 / 1 / 15 | none |
| SCR-30-mobile-overdue | 390 | 50% | 100% | 76.9 | 3 / 1 / 16 | none |
| SCR-30-mobile-no-owner | 390 | 33.3% | 100% | 75.1 | 4 / 0 / 14 | none |
| SCR-30-mobile-verified | 390 | 40% | 100% | 76.8 | 3 / 0 / 13 | none |

The visual gap is the same on all eight: the board is a short two-column (desktop) or single-card (phone) screen with the side panel and Tola; the built page is the shared frame with a taller vertical facts list and bordered section panels. No horizontal overflow at 390 (side-by-side read).

## Findings
- UI-2-1 | resolved (see Verified) |  | low | design engineer | The "(side panel)" board item (role complementary, empty name) is missing on all four desktop boards and not matched by the exception file: the entry is named "(side panel)", but the tool's real name for it is the empty string. Change that entry's name to "" (it is hidden write forms, so keep it in the file). Not a page defect.
- UI-2-2 | resolved (see Verified) |  | low | design engineer | SCR-30-desktop-no-owner draws a "NEXT" heading that is missing from the page and has no exception. The builder shows the no-owner sentence once and skips the Next section (UX-1-4 fix), so the heading and its Set an owner action are not drawn. Add an exception "text / NEXT" (category: UX-1-4, text shown once; Set an owner is already excepted). Alternatively draw a Next heading.
- UI-2-3 | non-blocking | low | frontend | The Acknowledged / Not acknowledged line is a heading-less bordered panel (for example "Not acknowledged yet" on 5102, "Acknowledged ... Owner replied by email" on 5101) between What has happened and Chasing. Reads as a stray box. Give it a heading or fold it into the facts.

## Exception list (57 entries plus 2 proposed), by group
Layout
- keep (lane C frame, 17 entries across breadcrumbs "PROJECTS", "LAGOON HEALTH", the project tab bar on three boards (7 entries), "← Registers"/"← Project", the page-head "BLOCKS" strip): breadcrumb, back link, persona and tab bar are the frame (spec Q4). Recommendation: keep; they move with F-95.
- keep (hidden by spec, side panel "OWNER FOLLOW-UP", Update type, Update, textarea sample, helper text, "Post update", "Post an update", "Set an owner", "Record a reply", "Raise an escalation", "Open the issue register"): writes are F-111B on F-87. Recommendation: keep.
- drop: "BLOCKS" text (lane C frame). Now matched; it shows as moved with RAISED, AGE, Engineering and "3 days" on the default board.
- fixable gap (accepted for demo under D-202 for lane C, otherwise a finding): Owner / Raised / Age / Blocks are a vertical Section list, not the board's four-cell strip with Blocks highlighted. It is the shared Section style, and Blocks is in the one facts block as UI-1-1 asked. Recommendation: accept as a lane C item (F-95).
- fix: add "" for the side panel (UI-2-1) and "NEXT" on no-owner (UI-2-2).

Colour
- keep (D-187): bar glyph "■■■ HIGH" and "■■■" (page draws the live severity tag).
- keep (D-187 and D-202): banner tone. Board draws a red alert for "no response" and the no-owner line; the page draws amber (UI-1-3, accepted). Not an entry; it shows as the visual gap.
- Recommendation: keep; ask lane C for a tone on the section banner (F-95).

Copy
- keep (D-187 Q1 A): status words "FIX IN TESTING", "OWNER NEEDED", "NO RESPONSE · 3 DAYS", "FOLLOW-UP VERIFIED", "DONE" (page shows the live Open / In Progress / Resolved).
- keep (spec hides Tola, D-182/D-185): "Tola" text and card, the Tola sentences on overdue, no-owner and verified, "Tola investigated".
- keep (sample data, 16 entries): "09 Nov", "11 Nov 16:40", "10 Nov 09:15", "09 Nov 18:02", "ISS-0240", "Owner update", "Owner acknowledged", the "(recorded by PM)" line, the Tola investigation line, and next-step sentences with the board's fixture wording. The page shows served values (fixture dates 20 Nov).
- keep (D-202 accepted, extra items, not entries): frame "Next step." line, "Waiting / With ... / Updated ...", Overview / History switch, alerts bell, account menu, and the My work breadcrumb.
- Recommendation: keep all; no copy gap remains that the data can fix.
- Final file (coordinator fix): "BLOCKS" dropped, side panel entry named "", "NEXT" added. All remaining entries are keep; none is a fixable gap. Everything stays pending the design engineer.

## Verified
- UI-2-1 | verified | re-run on the four desktop boards after the exceptions fix: side panel entry (name "") matched; coverage 100% with exceptions on all eight boards.
- UI-2-2 | verified | "NEXT" entry added; SCR-30-desktop-no-owner coverage 100% with exceptions.
- Re-run (head 8a5c09fe, desktop only): visual 74.8, 77.6, 84.4, 83.6; coverage with exceptions 100 on every board. The tool still reports FAIL only because visual is below 90: needs D-83 waivers (eight scores in the table). Nothing fixable remains; layout (strip vs list), banner tone and frame next step are accepted under D-202 / F-95. PIDs this run: mock 99673, next 99674, stopped; copy deleted; disk 5.8 GB free.
- UI-1-1 | verified | /work/5101 and the other states: Blocks ("Go-live") is the last row of the one facts block with Reference to Age. Still a vertical list, not the strip (see layout note).
- UI-1-2 | verified | 5101, 5102, 5107 Chasing rows read "Asked · Sent / Receipt recorded ..." and "Reminder · Sent / No receipt yet"; no "Time unknown".
- UI-1-3 | accepted risk (D-202) | amber banner on 5102 remains; counted as an exception.
- UI-1-4 | accepted risk (D-202) | frame "Next step" line above the banner remains; counted as an exception.

## Notes
- Visual is below 90 on every board, so each needs a D-83 waiver: 74.8, 77.6, 84.4, 83.6 (desktop); 76.5, 76.9, 75.1, 76.8 (phone). No exception is marked approved by me; approved_by stays "builder proposal, pending design engineer".
- The phone runs could not reach Google Fonts (fallback fonts), so text widths may differ slightly.
