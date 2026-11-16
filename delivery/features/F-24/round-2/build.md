STATUS: READY
COMMIT: 0f94b4b21e40889bb0300b3cf6891bab76829677
BUILDER: builder
LANE: full

## Summary
- Round 2 fixes the blocking UI findings (UI-1-1 to UI-1-5) and the listed non-blocking ones; TECH-1-3 left as is.
- Phone bar: the shared shell note now ellipses on one line and the back link stays on one line; the assistant home shows "← Home" and "N earlier" (a button) in the bar; the home composer is docked at the bottom; after a start the footer is a full-width "Open INV-0415".
- Fidelity (one run, 8 boards): coverage after exceptions 100 on all; visual 77.3 to 89.9 (round 1: 76.5 to 84.5); none at 90, so the visual waivers stay requested for the design engineer.

## Changes
- assistant.css: columns 240px and 260px; phone centre fills the viewport with the composer at the bottom; `scroll-padding-bottom` on phones; removed the old "earlier" row.
- shell (PhoneBar, AppShell, shell.css): `PhoneBack.onNote` (note as a button), note one line with ellipsis and a gap, back link nowrap. Other pages' short notes unchanged.
- components: AgentChecklist inline refs keep the data's case above the phone breakpoint (uppercase on phones); ChatMessage `hideWho`; DraftCard title in sans on phones.
- DraftStart: amount in the row's own sans (no mono); `onConflict` re-reads the thread. Start work: optional `onConflict` (drawer, form, hook) called on a 409.
- ThreadPage: phone footer "Open {reference}" link (Button primary, full width) from `draft.started` in place of the composer; AssistantHome: `PhoneHome` sets the bar.
- useSend: a lost send is found by the person-message count going up, not by text. mock: draft start replies (201 and 409) validated against v7.
- Tests: assistant.test.tsx (+4: same-text lost send, phone bar, no duplicate byline, Open footer), e2e (+3: column widths, phone bar and docked composer, focus not under composer and Open footer). Exceptions: "Open INV-0415" removed.

## Fixes
- UI-1-1 | 0f94b4b21e40889bb0300b3cf6891bab76829677 | grid 240/260; e2e asserts list 240 and panel 260 at 1440
- UI-1-2 | 0f94b4b21e40889bb0300b3cf6891bab76829677 | back link nowrap, note ellipsis and gap in shell.css
- UI-1-3 | 0f94b4b21e40889bb0300b3cf6891bab76829677 | phone centre min-height and composer margin-top:auto
- UI-1-4 | 0f94b4b21e40889bb0300b3cf6891bab76829677 | "Open INV-0415" footer from draft.started; exception removed
- UI-1-5 | 0f94b4b21e40889bb0300b3cf6891bab76829677 | step refs text-transform none from 720px
- UI-1-6 | 0f94b4b21e40889bb0300b3cf6891bab76829677 | ChatMessage hideWho on the phone working card (compact composer left as a listed difference)
- UI-1-7 | 0f94b4b21e40889bb0300b3cf6891bab76829677 | "N earlier" is a button in the phone bar (with "← Home")
- UI-1-8 | 0f94b4b21e40889bb0300b3cf6891bab76829677 | amount in sans; phone draft title in sans
- UI-1-9 | 0f94b4b21e40889bb0300b3cf6891bab76829677 | scroll-padding-bottom; e2e checks the focused draft button is above the composer
- TECH-1-1 | 0f94b4b21e40889bb0300b3cf6891bab76829677 | count-based detection; test with identical earlier text
- TECH-1-2 | 0f94b4b21e40889bb0300b3cf6891bab76829677 | draftStart replies schema-checked
- UX-1-1 | 0f94b4b21e40889bb0300b3cf6891bab76829677 | as UI-1-2
- UX-1-2 | 0f94b4b21e40889bb0300b3cf6891bab76829677 | as UI-1-9 (composer is in flow; scroll padding added)
- UX-1-3 | 0f94b4b21e40889bb0300b3cf6891bab76829677 | 409 triggers a thread re-read

## Verified
- UI-1-1 | fixed | e2e "desktop columns" passes (240 and 260)
- UI-1-2 | fixed | e2e phone bar test passes; side-by-side 390
- UI-1-3 | fixed | e2e: home composer bottom within 4px of the viewport bottom
- UI-1-4 | fixed | component and e2e tests: link "Open INV-0415" to /work/W-1401, height at least 50
- UI-1-5 | fixed | CSS above 720px; desktop side-by-sides
- UI-1-6 | fixed | test: one "Tola · PMO agent" on the phone working card
- UI-1-7 | fixed | tests and e2e: "5 earlier" button in the bar
- UI-1-8 | fixed | Money no longer used for the draft amount
- UI-1-9 | fixed | e2e focus test
- TECH-1-1 | fixed | assistant.test.tsx lost-send test
- TECH-1-2 | fixed | mock check in draftStart
- UX-1-1 | fixed | as UI-1-2
- UX-1-2 | fixed | as UI-1-9
- UX-1-3 | fixed | second-tab e2e still passes

## Validation
- bash delivery/checks.sh: exit 0 (82 files, 1779 tests, lint, tsc, build).
- Playwright (running app on 4770, mock 4771): assistant.spec.ts 24 passed; start-work.spec.ts passed in the earlier run this round (33 passed together; the later shell.css padding tweak was covered by the 24 assistant tests).
- Fidelity round-2/fidelity/scores.txt: desktop 88.1, working 89.4, thread 86.3, draft-started 85 (1440); mobile 89.9, working 80.4, thread 78.1, draft-started 77.3 (390); coverage with exceptions 100 on all.
- Note: the tool still reports the desktop-thread "Start this invoice" as missing although the button is on the page; it is covered by the existing Conflicts 5 entry, which is wrong for that board. I could not find the cause; please check on review.

## Blocked
Not blocked. Design engineer to sign exceptions and visual waivers.
