VERDICT: CHANGES
COMMIT: 195926d6854956a6918ef6199c0a5f57ce3a32ad
REVIEWER: reviewer-ui
AUTHORITY: UI reviewer (round 1)

## Summary
- /projects (SCR-22) and /projects/<case_id> (SCR-07) match the approved boards' type, tokens, surfaces, tab selection and footer treatment; the components use `var(--…)` tokens and bundle classes, with no hard-coded colours in `features/projects/`.
- Nothing overflows at 390: document width equals viewport width on every captured page (list, search, rows per page, journey, empty, no access, list error).
- Omitted board elements, the Journey-only tab bar and the closing note match the spec's Out of scope list and screen-state table.
- One blocking deviation: for persona `none`, the page shows the shell's "No sections are open to your role yet." instead of the spec's required "This section isn't open to your role." (criterion 9). The spec does not record this as approved.
- Otherwise the states read clearly at both widths; the points under Notes are taste only.

## Findings
- UI-1-1 | blocking | medium | product | Spec criterion 9 (and Screen states / Behaviour line 229) requires persona `none` to see "This section isn't open to your role." on `/projects` and `/projects/P-0101`. Actual: the frame (`src/shell/AppShell`, F-01) intercepts first and shows "No sections are open to your role yet." / "Ask a Lead or Admin to check your roles." (`src/shell/FrameStates.tsx:71`), with no h1 on that route (captured for `/projects` at 1440, and the 390 capture shows the same text; I did not capture `/projects/<id>` for `none`). The page-level `NotOpenState` in `src/features/projects/ProjectsPage.tsx:13` and `ProjectJourney.tsx` is therefore unreachable with the three mock personas. The build records this as a deviation (build.md, criterion 9) but the spec does not approve it. Expected: either the spec records the shell wording as the approved copy for a person with no sections, or the spec's text is kept and the shell is changed under its own lane. Owner decides; no change in this lane is needed unless the spec text stands.

## Verified
- None (round 1).

## Notes
- Captured and compared against the approved boards (`design/canvas/project/SCR-22-desktop`, `SCR-22-mobile`, `SCR-07-desktop`, `SCR-07-mobile`) and the existing My work and work item screens:
  - The list toolbar, table header rule, footer (rows per page, Show more) and phone cards follow My work's pattern.
  - The breadcrumb, selected Journey tab (solid ink) and "The whole journey" heading follow SCR-07.
  - The no-access panel and error card reuse the work item patterns.
- The search placeholder reads "Search projects"; the board reads "Search projects or clients". The spec gives only the label, so this is copy taste.
- On phones the line names are blue underlined links, while the board shows them as dark text. This matches the list links and My work, so it is consistent with the frame.
- At 390 the journey title wraps with "app" alone on the second line. Taste only; no fix needed.
- The line status tags use sentence case from `STATE_TAGS` ("Ready to continue"), where the board uses uppercase. This matches My work's tags, so it is consistent with the frame.
- The journey tab uses `aria-current` with a one-off CSS selector in `projects.css` because the bundle styles `aria-selected`. This is correct for link navigation; no visual issue.
- The fixture names (for example "Harbour Bank") differ from the board ("Harmattan Bank"). This is mock data and does not affect the UI.
- I did not run axe, focus or touch-target checks myself; the builder's e2e run covers them (build.md, criterion 15).

## Method (not part of the verdict)
- Ran Playwright from the worktree's `frontend/node_modules` against the shared app on :3711 and the shared mock on :3712, view only. I did not start or stop a server, and I did not open a named `<feature>-ui` browser session.
- Captured /projects and /projects/P-0101 (finance_lead), limit=10, q=zzz, /projects/P-0105, /projects/P-0099 and /projects/P-0102 (pm), /projects (none), and list and journey 500 states, at 1440x900 and 390x844 (Africa/Lagos).
- Confirmed the requests: `?limit=20`, `?limit=10`, `?limit=20&q=zzz`, and one `/projects/<id>` per journey. Persona `none` made no projects requests.
- Screenshots were in the scratchpad and deleted after this file was written.
