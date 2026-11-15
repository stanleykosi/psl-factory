VERDICT: PASS
COMMIT: 41b4925c441959c3a4fc2b7eaf8437fa35791109
REVIEWER: reviewer-ui
AUTHORITY: delegated UI review

## Verified
- UI-1-1 | verified | Save is blue and enabled on both detail side-by-sides (round-2/fidelity/SCR-35-desktop-detail-1440 and SCR-35-mobile-detail-390); the blank-press path (message beside the field, no request, focus) is in the diff and in the updated component test. Spec line 48 / acceptance 10 are replaced by D-75a.
- UI-1-2 | verified | Both empty inputs draw the orange (--signal) border on desktop and phone, matching the boards.
- UI-1-3 | verified | Phone detail shows a white bottom bar with an ink top rule and a full-width blue Save, like the board.
- UI-1-4 | verified | Phone detail has no panel frame or head; labels and inputs sit on the page at the 16px gutter like the board.
- UI-1-5 | verified | "Patient app" is the blue link on desktop and phone.
- UI-1-6 | verified | Desktop detail side-by-side shows Projects white with the orange underline; new destinationForPath test covers /clients, /clients/CL-3501 and not /clientsx.
- UI-1-7 | not verified | Left by the builder. Desktop list is unchanged at 85.9; the drift remains. Non-blocking (see UI-2-2).
- UI-1-8 | not verified | Left by the builder. Panel heads are still about 43px against the board's 37px (visible on SCR-35-desktop-detail). Non-blocking (see UI-2-2).

## Findings
- UI-2-1 | non-blocking | low | design engineer | Scores under 90 (desktop 85.9, desktop-detail 80.3, mobile-detail 86.0; mobile 92.5 passes) are, in substance, forced by the approved omissions (D-71): Legal name, Billing address and Tax ID fields and the Save row below them, the Contacts panel, the Search/Filter row, the OWED column, the extra Money panel, the shorter data-driven banner sentence, the "Save billing contact" copy, the phone Billing address field, and the frame's bell/Start and 40px/26px titles. I find no blocking build-fixable gap left on the detail boards: the controls, colours, borders, link and bar states now match. A waiver for the residual scores is for the design engineer to decide; I do not block on them.
- UI-2-2 | non-blocking | low | frontend | Small gaps still fixable in the build, worth only a few points: desktop panel heads at about 43px against 37px (UI-1-8); content about 4-6px lower than the board on desktop detail and about 2px per row on the desktop list (UI-1-7). On the phone the helper "Needed before any invoice can start" shows under the name field where the phone board draws none; the spec keeps it as static copy (Conflicts 7), so leave it unless the design engineer wants it dropped on phone.
- UI-2-3 | non-blocking | low | design engineer | New exception "Billing contact name" (Conflicts 7, pending design engineer): the label is drawn on the built phone page (visible in the side-by-side), so nothing is omitted. The tool lists it as missing only because its role-matching now sees the input label as a field, not text, once the panel heading is gone. It is a tool matching artefact and harmless; I recommend approving it, with the reason reworded as "label present, matched as a field" (it fits Conflicts 7 only loosely). It hides no real board difference, so it is not a way around a missing element. The design engineer signs it.
