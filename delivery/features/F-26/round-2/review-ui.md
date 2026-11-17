VERDICT: PASS
COMMIT: ac401c09e80d4398acb8101994d6f18b4b0f1d76
REVIEWER: reviewer-ui
AUTHORITY: delivery UI review

## Summary
- All of my round-1 findings are fixed or settled. UI-1-1 (bold selected amount) and UI-1-2 (semibold phone Unknown) match the boards. UI-1-4 now uses tokens. UI-1-3 is settled by the D-107 per-board waivers.
- UI-2-1 is settled by D-108. The SCR-12-mobile waiver now names the phone cards about 12px taller per linked stage, for the two 44px tap targets (D-92c). There is no code change, and head ac401c09 is the build that was scored and waived.
- UI-2-2 is settled. The SCR-12-desktop waiver now names the shorter Chidi card and the report title on the same line as the board's sentence.
- Both boards are at 100% coverage after the 11 D-104 exceptions. Visual is 85.7 on desktop and 77.8 on phone, each under a signed per-board waiver whose text matches what it covers. My side-by-side reading finds no difference left that a waiver or exception does not cover.
- Tokens and colour meaning are right. Unknown is waiting-ink amber with no tint, muted lines use ink-muted, links use the action blue and money.css has no hex values. Nothing overflows sideways at 390.

## Findings
- UI-2-3 | non-blocking | none (P-0102, not on a board) | An Unknown amount that has a figure is a link with the amber Unknown as its text. On desktop it is amber, semibold and underlined. Amber keeps its "waiting" meaning (D-92b) and the underline marks it as a link. No board draws this case. | Fix: none needed; noted for the design engineer.

## Verified
- UI-1-1 | verified | In round-2/fidelity/SCR-12-desktop-1440/side-by-side.png, Stage 2's ₦4,250,000.00 has the same weight as Stages 1 and 3. The `aria-current` bold rule is removed in money.css and `aria-current="true"` is kept.
- UI-1-2 | verified | In round-2/fidelity/SCR-12-mobile-390/side-by-side.png, Stage 4's "Unknown" is mono, regular weight, 16px and amber, as the board draws it. The desktop table keeps 600, matching its board.
- UI-1-3 | verified | `visual_waivers` in fidelity-exceptions.json sign SCR-12-desktop at 85.7 (D-107) and SCR-12-mobile at 77.8 (D-107, D-108), matching round-2/fidelity/scores.txt.
- UI-1-4 | verified | The tap areas use `--space-6px`, `--space-3` and `--control-md`, and the amount no longer reaches over the stage name. The resulting card height is waived under UI-2-1.
- UI-2-1 | verified | The SCR-12-mobile waiver reason now reads "Also covers phone cards about 12px taller per linked stage, for the two 44px tap targets (D-92c)", approved by the design engineer on 17 Nov 2026 (D-108 in delivery/OVERNIGHT-DECISIONS.md:177). This matches the measured 12–14px per linked card at head ac401c09, with no code change.
- UI-2-2 | verified | The SCR-12-desktop waiver reason now names "the shorter Chidi card, "Ask me about any figure here.", which makes the side panel about 20px shorter; the report title on the same line as the board's sentence, before it", which matches the round-2 side-by-side.

## Carried forward (impact assessment)
- The head is unchanged since my first round-2 review, and only the main folder's fidelity-exceptions.json and decisions changed. The round-2 code that touches no board-scored layout (TECH-1-1 guards, UX-1-1 phone report error, UX-1-2 money no-access line, Chidi `agentKey`) stays as assessed. The no-access panel uses `psl-panel`, and its wording is approved in D-108.
