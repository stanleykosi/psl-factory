VERDICT: CHANGES
COMMIT: d9cd1d2e011106564b113229ce15100497d81ca7
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer (D-59 region check, D-62/D-63 layout), lean round per D-64

## Summary
- I used the builder's round-3 reports (not re-run) and read 3 side-by-sides myself: checklist 390, table 1440, unknown-money 1440. Coverage is 100% in 21 of 21 runs; visual >= 85 in 9 of 21.
- UI-2-1..2-8 are fixed. The 390 phone boxes, row ends on the right, sans status pills, nowrap table references, cite line and uppercase tags, and the desktop checklist without marks all show in the pictures; text-cites 390 went 52.8 to 100. The bar (UI-2-3) I did not look at myself; I rely on the builder's 375x667 measurement (192px, no sideways scroll).
- One new fixable gap (UI-3-1) remains. Everything else under 85 is forced.
- The gate is not met (12 runs under 85), so VERDICT stays CHANGES for UI-3-1 only; the forced gaps go to the design engineer.

## Findings
- UI-3-1 | blocking | medium | frontend | Table money doesn't match SCR-56. The board draws month and amounts left-aligned in the body sans, the table inset 16px inside the panel; the frame right-aligns amounts in mono (`.num`) and runs the table full width. The money size is now right (UI-2-7b fixed), but the alignment and face are a frame style, not a line's task (D-63 only decided full vs compact figures). Fix: in `.ws-table`, give money cells `text-align: left; font-family: var(--font-sans)` (header cells left too), and inset the table 16px inside its section panel. Also draw the unknown-money note's warning icon as the board does (the callout has no icon), and show the "As of ... reconciled" line below the table, or ask for an exception since the board has no such line. Expected: unknown-money 1440 from 72.3 to near 85. Do not use `.psl-unknown` chip inside the cell next to "UNKNOWN" text (checklist last row shows "UNKNOWN · Unknown" twice, non-blocking).

## Verified
- UI-2-1..2-7 | fixed | by the side-by-sides and scores above.
- UI-2-8 | fixed | no marks on the desktop checklist (D-63).

## Dropped 390 regions
- recipients, timeline | fair | the phone board draws one green summary line.
- suggestions, step-form | fair | the phone boards are a full-screen swipe card and an edit page.
- facts | acceptable | no phone board draws a label/value list; the SCR-44 pill rows scored 64.2. The design engineer should confirm there is no better anchor, since phone facts are now unmeasured.

## Runs under 85
| region | width | score | class | cause |
|---|---|---|---|---|
| steps | 1440 | 40.4 | forced | board has inline Note field and "DECIDE · PMO LEAD"; neither is in the contract |
| steps | 390 | 31.6 | forced | D-63 keeps the consequence sentence pinned; board bar holds buttons only |
| table | 1440 | 77.5 | forced | 44px checkbox targets (accessibility) make rows 63px against 55px; board has a select-all header box the contract lacks |
| table | 390 | 72 | forced | the phone board is a swipe card, not a table |
| suggestions | 1440 | 70.1 | forced | Status radio, "Write my own", requirement title not in the item |
| checklist | 390 | 76.8 | forced | the board omits owner, held-by and due lines and has no head; the frame shows contract data |
| checklist-gates | 390 | 72.2 | forced | same as checklist 390 |
| findings | 1440 | 71.6 | forced | no board draws a findings list; anchored on a checklist |
| findings | 390 | 74.7 | forced | one SCR-25 Risks row compared; the board's risk row differs in content |
| unknown-money | 1440 | 72.3 | fixable | UI-3-1: left sans money, table inset, callout icon |
| step-form | 1440 | 45.2 | forced | no prefill, submit label or item context in the contract |
| notice-done | 390 | 67.9 | forced | board shows a short summary line; the frame shows the returned sentence |

## Notes
- Fidelity evidence is in `/Users/Hunchoo/psl-factory/delivery/features/F-17/round-3/fidelity/<region>-<width>/`.
- Phone checklist rows add "· 14 May 2027" and "· Unknown" in mono beside the pill; the board shows only the pill. Part of the forced gap; consider an exception to drop due and money on phones.
