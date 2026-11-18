STATUS: READY
COMMIT: 5bab76ae6a1d3a5bd8a26c0504b7a7ad72d51b9b
BUILDER: builder
LANE: full

## What is released, and what stays held
Contract mock only. Nothing is released or deployed, no one is given authority, and all release wording is fixture text. Open product questions for PSL are unchanged (planning vs release decision, who holds release authority, Reject on a release).

## Summary
- Round 2 fixes the seven blocking UI findings and the two cheap UX items; security, technical and UX passed in round 1.
- SCR-43: sub-nav drawn as separate 36px items with Overview filled; Tola's check is one agent card (design-system `psl-agent`) with Next beside it; rows, number boxes and Hypercare tone follow the board.
- W-2501: the release task panel takes the full width (no blank main column), only for `delivery_release` items with an unlinked task, so every other line item renders as before.
- Exceptions recategorised and extended; waiver reasons list the remaining gaps with round-2 scores. All new entries are "builder proposal, pending design engineer".

## Fixes
- UI-1-1 | 5bab76ae6a1d3a5bd8a26c0504b7a7ad72d51b9b | Sub-nav is its own component (`delivery__navitem`): 36px items, 4px gap, Overview (aria-current) filled ink with white text; links in ink.
- UI-1-2 | 5bab76ae6a1d3a5bd8a26c0504b7a7ad72d51b9b | Tola's check is one `psl-agent` card: avatar, title, "Tola · PMO agent · done", DONE tag, ink step text with white ticks, footer "Checked 12 Apr 09:00" with Ask Tola; the nested Panel is gone; Next moves under it in the aside as on the board. The agent_summary fallback is unchanged.
- UI-1-3 | 5bab76ae6a1d3a5bd8a26c0504b7a7ad72d51b9b | 28px bordered number boxes, row padding 12px 0, 34px grid column, ink underlined linked titles, 12px reference, 13px note.
- UI-1-4 | 5bab76ae6a1d3a5bd8a26c0504b7a7ad72d51b9b | P-0101 Hypercare gate tone is `uncertain` (amber); test added.
- UI-1-5 | 5bab76ae6a1d3a5bd8a26c0504b7a7ad72d51b9b | `work-columns--lone` for release items with an unlinked task: one full-width column, no blank band, margin below the panel. Condition is `workspace.line_key === 'delivery_release'` and a shown task; verified existing W-2901 (minutes) keeps two columns (test). Same fix covers UX-1-1.
- UI-1-6 | 5bab76ae6a1d3a5bd8a26c0504b7a7ad72d51b9b | W-2501 Planning decision gate drops `status: now`, so only "Waiting for PMO Lead" (and the held-by line) remain; test added. Tag stays inline with the label (shared checklist row): listed in the waiver.
- UI-1-7 | 5bab76ae6a1d3a5bd8a26c0504b7a7ad72d51b9b | (d) fixed: `claim_required` removed from the W-2502 to W-2507 fixtures, so no "Claim it first" (also UX-1-3; the F-16 page claims on open). (a) amber gates note, (b) plain facts values, (c) grey readiness tags, (e) side-by-side buttons at 390: shared frame components I may not change; each is named in the matching board's waiver reason in `fidelity-exceptions.json` (a maps to G-44-1 notices[] recorded not built, b and c to Conflicts 15 tones, e to D-99/D-110 frame), pending design engineer.
- UI-1-8 | 5bab76ae6a1d3a5bd8a26c0504b7a7ad72d51b9b | Four SCR-43 line links and the Next sentence are "sample data" (no work item exists and P-0101 `next` is shared with the Journey; the fixture cannot send them without breaking the spec's no-link rows and Journey board); "Conflicts 5: Conflicts 5:" fixed; the Tola entry now says it covers SCR-44.
- UI-1-9 | 5bab76ae6a1d3a5bd8a26c0504b7a7ad72d51b9b | Open go-live restyle added as a `frame layout` exception (Conflicts 10).
- UX-1-1 | 5bab76ae6a1d3a5bd8a26c0504b7a7ad72d51b9b | see UI-1-5.
- UX-1-3 | 5bab76ae6a1d3a5bd8a26c0504b7a7ad72d51b9b | see UI-1-7 (d).
Not fixed: UI-1-10 and UX-1-2 (History link 24px at 390 is the shared F-30 frame; for a frame fix). TECH-1-1/1-2 and UX non-blocking items not listed above are unchanged.

## Changes
`DeliveryTab.tsx`, `project-tabs.css`, `model.ts` (export AGENT_ROLES); `work-item/WorkItemOverview.tsx` and `work-item.css` (conditional `work-columns--lone`); fixtures P-0101, W-2501, W-2502 to W-2507; tests `delivery-overview`, `release-gates`; `e2e/issue-detail.spec.ts` (project bar link count 6 to 7, mechanical for the new tab); `fidelity-exceptions.json`, `round-2/fidelity/**`.

## Validation
- `bash delivery/checks.sh` under the shared lock (load < 14): exit 0. Lock released.
- e2e (ports 4870/4871): delivery-release, work-item, workspace, minutes, issue-detail, weekly, project-tabs, projects: 216 passed, 1 failed (issue-detail project bar count 6, expected 7 with the new tab); after the mechanical fix that test passes (1 passed).
- Targeted vitest: delivery-overview, release-gates, delivery-release-mock, mock-projects pass.
- Existing items unchanged: the lone-column class is added only for `delivery_release` with an unlinked task; the minutes W-2901 case is tested.

## Fidelity (one run, production build, ports 4870/4871, `round-2/fidelity/`)
| Board | Width | Coverage | With exceptions | Visual | Round 1 |
|---|---|---|---|---|---|
| SCR-43-desktop | 1440 | 64.6 | 100 | 77.5 | 78 |
| SCR-43-mobile | 390 | 50 | 100 | 78.1 | 77.5 |
| SCR-44-desktop | 1440 | 56.4 | 100 | 84.9 | 86.7 |
| SCR-44-desktop-decision | 1440 | 53.3 | 100 | 77.3 | 77.2 |
| SCR-44-desktop-ready | 1440 | 64.9 | 100 | 76.7 | 76.7 |
| SCR-44-mobile | 390 | 60 | 100 | 80.9 | 78.9 |
| SCR-44-mobile-decision | 390 | 50 | 100 | 77.5 | 76.9 |
| SCR-44-mobile-ready | 390 | 50 | 100 | 82.1 | 82.1 |

Visual stays under 90 on every board; the remaining gaps are the shared frame and approved conflicts. Each board keeps a proposed D-83 waiver whose reason now lists them. The scores barely moved because the fixed items are small against the frame. SCR-44 default fell 1.8 points: the full-width task panel is taller than the right-hand one. Needs design-engineer sign-off.
