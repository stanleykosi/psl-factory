VERDICT: CHANGES
COMMIT: 352893425c8d197b3de15ab04eac6c68d1d05782
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer (design-fidelity gate)

## Summary
- All 18 boards reach 100% coverage after exceptions. Only 4 reach visual >= 90: desktop team-input 93.4, rfp-outcome 90.3, -lost 94.6 and -pending 92.9. I re-ran all 18 and got the builder's numbers: identical on the frozen form pages, within 0.8 on the live recorded pages.
- One real styling defect. The team input form's look depends on the order the CSS files load, and the component imports them in the wrong order. When they load in that order, the board's single panel becomes a double frame (UI-1-1).
- Five fixable differences from the boards on the recorded states: the desktop won "Next" is restyled; the phone recorded states put their action in a "Next" panel instead of pinning it at the bottom; the phone archive line and follow-up heading are restyled; and two status tag tones contradict the boards without an approved exception (UI-1-2 to UI-1-6).
- Most of the remaining shortfall comes from decisions already made. These are the 40px/26px titles (Conflicts 2), the fields the request needs (note, attestation, record_as, "Amount not known", "To", 44px segments), native date text and the omitted copy (D-60 c). No layout fix can lift those boards to 90, so the design engineer needs to rule on them (UI-1-7).
- Undrawn states (sending, sent, effect_uncertain, Check again) use the design-system callout and buttons consistently. There is no sideways scroll at 390 on any page I checked. rfp.css uses tokens only.

## Findings
- UI-1-1 | blocking | high | frontend | The team input form's look depends on which CSS file loads last. `features/response/ResponseView.tsx:25-26` imports `rfp/rfp.css` before `./response.css`. `.resp-form--team { background:none; border:none; padding:0 }` (rfp.css:22) and `.resp-form { background:var(--surface); border:2px solid var(--ink); padding:20px }` (response.css:35) have equal specificity, so whichever file loads last wins. The board draws one panel ("RECORD TEAM INPUT"). On `next dev` the live page `/work/W-2101/respond?task=T-2101` at 1440 computes the form as border 2px, padding 20px, white. The panel then sits inside a second framed box and the layout widens. A frozen page from that build scores visual 69.4 against 93.4 for the production frozen page; see the dev side-by-side I compared. The production build passes only because the chunks happen to load in the other order. Expected: the override holds whatever the load order, e.g. `.resp-form.resp-form--team` (likewise `.rfp-form` and the phone rule at rfp.css:86), or import `response.css` first in ResponseView, as OutcomeView already does (OutcomeView.tsx:26-27).
- UI-1-2 | blocking | medium | frontend | Desktop won (SCR-16-desktop-rfp-won, 73.2). The board draws no "NEXT" panel on the won state. Under the right column it has the plain sentence "When Tola is done, you'll confirm the PM and register the engagement." and a secondary outlined "Open engagement EN-0042" button (white, ink outline, ink text). The page renders a bordered "NEXT" panel with a primary blue button. The tool reports: background #FFFFFF on the board, #2459D6 on the page; outlined on the board, not on the page; extra heading "NEXT". The pending, unknown and lost boards do draw the NEXT panel, so only won differs. Expected: on won, no panel head; the sentence, then `psl-btn` secondary, in the right column (`RecordedView.tsx` / rfp.css `.rfp-recorded__aside`).
- UI-1-3 | blocking | medium | frontend | Phone recorded states (mobile rfp-won 74.8, -pending 77.4, -lost 77.7, -unknown 85.3).
  - **Won and pending.** The boards pin the single action at the bottom (white bar, 2px ink top rule, 50px button at y=776, like F-09's pinned Record and the Send/Edit bar this feature already pins). They draw no "Next" panel. The page puts a bordered "Next" panel with a heading and the button in the flow (won y=343, pending y=362). The tool reports these as "inside a side panel on the page" and extra complementary "Next".
  - **Unknown.** Send/Edit are pinned correctly. Below them the page adds a "Next" panel with a second primary "Record the outcome" button, and the page grows to 1040px. Spec Contract 5 requires that link, so keep it, but as an in-flow secondary button or link with no panel. Two primary actions on one phone screen read as two equal choices.
  - **Lost.** The board draws neither a panel nor "Back to projects". Keep the link the spec requires, but quietly, without the panel chrome.
  - Expected at < 720px: pin the primary action (won, pending) in the same bar as `.rfp-followup__actions`. Drop the Next panel border and heading; show the `next[]` line as plain text where you keep it.
- UI-1-4 | blocking | low | frontend | Phone lost (SCR-16-mobile-rfp-lost). The board draws "Archived as ARC-0117…" as plain muted 13px text under the lessons panel. The page renders a blue info callout (`psl-callout`). The desktop board does draw the callout, so this is phone only. Expected: plain muted line at < 720px.
- UI-1-5 | blocking | low | frontend | Phone unknown (SCR-16-mobile-rfp-unknown). The board's follow-up heading is "Follow-up drafted by Tola" in IBM Plex Sans 15/600, sentence case, with no rule. The page keeps the desktop panel head: Archivo, capitals, 2px ink bar. The tool reports font Plex vs Archivo, capitals on the page, bar under it on the page. The phone head style at rfp.css:84 is applied to `.rfp-panel > .psl-panel__head` but not to `.rfp-followup > .psl-panel__head`. Expected: the same phone head treatment for the follow-up panel. The agent card, checks and "To" line stay (spec Contract 6, AC15); those are forced.
- UI-1-6 | blocking | low | frontend | Status tag tones contradict the boards, and no exception covers them. Desktop rfp-lost: the board's "LOST · 04 DEC" is neutral grey (#3F474B); the page uses red (#9A2F10). Desktop rfp-unknown: the board's "OUTCOME UNKNOWN" is amber (#6E4700); the page uses neutral. The tones come from spec Contract 1 ("lost: red, unknown: neutral"), but the spec's Conflicts list does not record them as a board deviation, and D-60 did not decide them. Expected: match the boards (lost neutral, unknown amber/waiting) in the status-kind tone map (`features/rfp/RfpFrame.tsx`). Alternatively the coordinator records an approved exception and updates the spec line; the design engineer must sign it.
- UI-1-7 | blocking | medium | product | The gate still fails on 14 boards, and the causes are decisions that layout cannot fix. Once UI-1-1 to UI-1-6 are fixed, the remaining gap on each board under 90 comes from:
  - **(T)** The approved 40px/26px titles (Conflicts 2). On the phone every row moves down 4–6px.
  - **(R)** Request-required fields: note, attestation, the record_as select on the phone with 2 roles, "Amount not known", the "To" line, and 44px phone segments (AC20).
  - **(D)** Native datetime-local text, e.g. "12/04/2026, 11:00 am" where the board draws "04 Dec 2026, 11:00". This is the F-09 WhenField precedent.
  - **(C)** Approved omitted copy that leaves the page shorter: the D-60 c planning-packet card (about 300px on won), "What happens next", the recorded intros, "No proof needed" with the proof card kept (D-60 b).

  The design engineer must decide:
  - whether these boards pass with the measured scores, or the boards or contract change;
  - the 23 exceptions still marked "coordinator, provisional (D-60)" or "builder proposal, pending design engineer". These are the 11 typed-value entries, "Lessons", "HANDOFF", the result headings, the recorded intros, the tablist role and the phone "← RFP". Only the design engineer approves exceptions.
- UI-1-8 | non-blocking | low | backend | Tones the contract cannot carry: row tag "NOTHING YET" (amber on the board) and lesson category tags (PRICE and TIMELINE amber, STRENGTH green) render neutral on the page. Build.md contract question 5 asks for a tone. Until a field exists, they need a signed exception. The frontend should not derive a tone from text.
- UI-1-9 | non-blocking | low | backend | Won rows: the board shows "Engagement EN-0042 created (route A, from this RFP) · 04 DEC" and "Tola building the planning packet · AGENT WORKING". v7 `engagement` carries only `reference` and `work_id`, so the page shows "Engagement EN-0042 created" with no date. Add to the D-RFP-OUTCOME r3 question list next to question 3.

## Fidelity (reviewer re-run, cookie pm, --exceptions, --wait-ms 500)
Frozen form pages: the builder's frozen HTML (production CSS from `.next/static`) served on 4653. I re-ran `drive-states.mjs` against head on 4651/4652, and the `<main>` DOM of all 10 frozen pages is identical to the builder's. Live recorded pages: `next dev` on 4651 with mock 4652 and FRAME_FIXTURES=1. The production build's rewrite points the API at 4010, outside my ports, so I used dev; the dev indicator is in those shots. Copied to `round-1/fidelity/<board>-<width>/{report.json,side-by-side.png}`.

| Board | Width | Coverage / after exceptions | Visual | Pass | Remaining difference after exceptions | Cause |
|---|---|---|---|---|---|---|
| desktop team-input | 1440 | 76.9 / 100 | 93.4 | yes | Attestation beside the proof, note beside Received, native date text | R, D (fine). UI-1-1 is a load-order risk |
| desktop rfp-outcome | 1440 | 72.5 / 100 | 90.3 | yes | "Amount not known", note, native date | R, D |
| desktop rfp-outcome-lost | 1440 | 75 / 100 | 94.6 | yes | Note, select | R |
| desktop rfp-outcome-pending | 1440 | 73.8 / 100 | 92.9 | yes | Note, native dates | R, D |
| desktop rfp-outcome-unknown | 1440 | 71.1 / 100 | 88.6 | no | Proof card in place of "No proof needed", note, no "What happens next"; Save as unknown 72px lower | R, C (D-60 b/c) |
| desktop rfp-won | 1440 | 56.7 / 100 | 73.2 | no | Packet card and intro absent; NEXT panel and primary button restyled | C, plus UI-1-2 |
| desktop rfp-lost | 1440 | 74.1 / 100 | 87.8 | no | Archive callout one line; status tag red, lesson tags neutral | C, UI-1-6, UI-1-8 |
| desktop rfp-pending | 1440 | 76.9 / 100 | 74.4 | no | Intro callout absent; rows panel 53px higher | C (Conflicts 12) |
| desktop rfp-unknown | 1440 | 82.4 / 100 | 86.5 | no | "To … · draft v1" line (+28px); status tag neutral; NOTHING YET neutral; no Ask Tola | R, UI-1-6, UI-1-8, C |
| mobile team-input | 390 | 73.7 / 100 | 85.1 | no | 26px title, 44px segments, "Engineering" not "Eng.", note and attestation, native date | T, R, D |
| mobile rfp-outcome | 390 | 60 / 100 | 88.5 | no | Title, roles select, note, "Amount not known", native date | T, R, D |
| mobile rfp-outcome-lost | 390 | 66.7 / 100 | 82.4 | no | Title, roles select, note, no "What happens next" | T, R, C |
| mobile rfp-outcome-pending | 390 | 64.7 / 100 | 87.1 | no | Title, roles select, note, native dates | T, R, D |
| mobile rfp-outcome-unknown | 390 | 53.8 / 100 | 89 | no | Title, proof card kept, select, note | T, R, C |
| mobile rfp-won | 390 | 37.5 / 100 | 74.8 | no | Intro and packet card absent; Next panel and button in flow, not pinned | T, C, UI-1-3 |
| mobile rfp-lost | 390 | 40 / 100 | 77.7 | no | Debrief link, archive as callout, Next panel with Back to projects; tag tones | T, UI-1-3, UI-1-4, UI-1-8 |
| mobile rfp-pending | 390 | 60 / 100 | 77.4 | no | Intro absent; Next panel and button in flow, not pinned | T, C, UI-1-3 |
| mobile rfp-unknown | 390 | 85.7 / 100 | 85.3 | no | Agent card and "To" line (required); heading restyled; extra Next panel under pinned bar | T, R, UI-1-3, UI-1-5 |

Frame items on every board are the shell's, as in F-14 and F-16 (Conflicts 19): alerts bell, "Tunde Bello · PM", "Start work" on the right, and on the phone the bell and Start move the bar note to the middle. Every board reports the tablist and tabs as missing with their exception, and the nav "RFP" as extra.

## Verified
None. This is round 1.

## Notes
- The outcome role select uses the F-09 native `resp-select` chevron where the boards draw a small "▾". This is existing precedent; a shared styled select would be a later batch.
- On the phone the bar note (OUTCOME, WON, …) sits mid-bar because the shell's bell and Start sit at the right. This is the shell's choice, not this feature's.
- The undrawn follow-up states (Conflicts 14) use `psl-callout` warning and secondary buttons consistently with F-09's notices at both widths (checked on W-2114).
