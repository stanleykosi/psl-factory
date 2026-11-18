VERDICT: PASS
REVIEWER: reviewer-ui
COMMIT: 83747e368e5af5b4680839ede43bd485d8744414
AUTHORITY: delivery UI review

## Summary
- All nine round-1 blocking findings (UI-1-1..1-9) are verified on the build at :4863 at 1440 and 390, against the boards and the round-2 side-by-side images. The non-blocking UI-1-11, 1-12 and 1-13 are verified too. The one scored run (round-2/fidelity/, not re-run) has all 8 boards at 100% coverage after exceptions and visual 72.2 to 85.5. All are at or above the 70 floor, so no floor exception is needed. All 8 are under 90, so the waivers are the route.
- Waivers: each is now one per board, with its own score, and names that board's real gaps, including the UI-1-11 shared-renderer items. I read each against its side-by-side and found no unlisted difference of substance. All 8 are signable by the design engineer. Two things to put to them: the SCR-42 row actions are shared outlined item-step Buttons (D-91), and the status tag tone (UI-1-10) is a fixture choice.
- Ruling on the phone record Drawer with no Cancel: the SCR-42-mobile-record board draws a screen with its own back and one pinned "Record input", and no Cancel. The built sheet closes with Close or Escape, which is the approved Drawer behaviour (Conflicts 4 and 9). It is not a fidelity gap, and the omission matches the board better than a Cancel would. It is a frame item for the waiver, already listed (the "Close" wording).
- W-2901 and W-2411 render unchanged at both widths: no page errors, no horizontal overflow, same layout as before. The shared edits only touch disabled primaries in the Decide panel, `.ws-form--bare` and the Drawer-scoped form CSS.
- I made no writes to the mock. Opening the Drawer sends nothing.

### Per board (round-2 run; reports and side-by-side.png are in `round-2/fidelity/<board>-<width>/`)
| Board | Width | Coverage / with exc. | Visual | Reading |
|---|---|---|---|---|
| SCR-41-desktop | 1440 | 77.3 / 100 | 81.9 | Frame, D-113 and shared-renderer gaps only. All named in the waiver |
| SCR-41-mobile | 390 | 60 / 100 | 79.2 | Confirm PM has no box; Price cell is one value. Remaining gaps are Conflicts 7 stacking and frame, named |
| SCR-41-desktop-register | 1440 | 81.5 / 100 | 80.1 | Uploaded state frozen; one consequence and one primary button. Form in the side column is named |
| SCR-41-mobile-register | 390 | 66.7 / 100 | 77.7 | One title, fields flush, actions at the foot of the sheet. Cancel beside the primary is named (AC 15). Not under the floor |
| SCR-42-desktop | 1440 | 73.2 / 100 | 74.3 | Readable disabled button, estimates on one line, bold departments. Row actions as outlined Buttons are named (D-91) |
| SCR-42-mobile | 390 | 42.9 / 100 | 79.5 | Pinned Readiness bar is grey and readable. Stacked table is Conflicts 7, named |
| SCR-42-desktop-record | 1440 | 70.3 / 100 | 85.5 | One column, no page box. Record input is in the Drawer body with Cancel in the footer; the board has both in the footer. Named in the waiver |
| SCR-42-mobile-record | 390 | 64.7 / 100 | 72.2 | One column, pinned Record bar, no Cancel as the board. The longer F-18 form is named (Conflicts 14) |

## Findings
None.

## Verified
- UI-1-1 | verified | W-2603 at 1440 and 390: "Prepare readiness" is `aria-disabled`, background rgb(201,205,199) (the disabled grey) and ink rgb(74,83,87). It is no longer green on grey.
- UI-1-2 | verified | W-2601 at 390: `.ws-form--bare` computes border 0px and padding 0px. The PM field sits in the panel's own padding.
- UI-1-3 | verified | W-2602 at 390: "Costing v2 · ₦40,951,000.00" is one value cell in the value column, not split under the FROM label.
- UI-1-4 | verified | W-2603 Drawer at 1440 and 390: one column, no page box, the pinned Record input bar is in the Drawer, Cancel is in the Drawer footer on desktop, and there is no Cancel on the phone (see the ruling in Summary). Escape closes the Drawer. The one remaining difference from the board (Record input above the footer rule rather than beside Cancel) is named in the SCR-42-desktop-record waiver.
- UI-1-5 | verified | Drawer at 390: Team segments 48px, "Choose a file" 48px, selects and inputs 44px, Record input 50px.
- UI-1-6 | verified | W-2602 register Drawer at 1440 and 390: the sentence "Registers the engagement with this plan evidence." shows once and one "Register engagement" button is visible (50px). The phone sheet shows one title and flush fields with the actions at the foot. SCR-41-mobile-register rose from 69.8 to 77.7, so no floor exception.
- UI-1-7 | verified | `round-2/fidelity/drive-states.mjs` waits for upload end; the register side-by-sides show the uploaded file chip and not "Uploading…".
- UI-1-8 | verified | Drawer eyebrow reads "Ojo Foods · ordering app" from the response. The exceptions file has 45 entries, entry 43 is a project-name `sample data` item, and entry 24 is category `frame`.
- UI-1-9 | verified | W-2603: department names weight 600. Estimates read "230 person-days" and "20 person-days" on one line in the record side-by-side at 1440. The row actions stay outlined Buttons in an extra column and are named in the SCR-42 waivers as a D-91 component item for the design engineer.
- UI-1-11 | verified | Each waiver now names section-note callouts, the plain-row estimate finding and the status tag tone.
- UI-1-12 | verified | `visual_waivers` has 8 entries, one per board, each with its own round-2 score and its own gaps.
- UI-1-13 | verified (by build note, not measured) | The registered state was not reachable without a write; the build records 48px links on a phone.
- UI-1-10 | carried | Non-blocking, left for the design engineer (status tag tone amber or blue). It is named in every waiver.

## Notes
- The phone register Drawer has Cancel beside its primary while the phone record Drawer has none. This is a small inconsistency, but each follows its own board and AC 15. Taste only.
- W-2602 at 1440 shows a stray top rule above the PM row. It is cosmetic and not on the board's hierarchy. Not blocking.
- Received still shows the browser's native "mm/dd/yyyy" in the headless browser (F-18, unchanged), as noted in round 1.
