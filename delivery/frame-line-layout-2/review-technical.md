VERDICT: PASS
COMMIT: bef1968cf9633e4ca497304b984c5465b2c65320
REVIEWER: reviewer-technical
AUTHORITY: delegated technical review

## Checked
- Diff base...bef1968c: 5 frontend files, no backend, no contract, no permission or money code. `npx vitest run tests/workspace.test.tsx` in the worktree: 37 passed.
- Tab bar: `ProjectBar` renders only when `!phone && ws?.context?.project`, keyed on `case_id`; no line key. Tabs from PROJECT_TABS; Journey is the only `Link` (encoded href); the others are plain spans with no tabindex or role, so not focusable. No project, no bar. Nav is labelled "Project", distinct from the History nav.
- Title: `--title-line` is declared on `.work-header--line` and used only in `.work-header--line .shell-title` at 720px and up. Other pages keep 40px; phones are unchanged.
- Placement: `inSide` is true for suggestions, or for kind `checklist` with `item.agent.status === 'working'`. The agent note moves to the top of the main column only under the same condition (`noteBeside`) and only when it has lines; the header drops it in that case, so it appears once. DOM order is main then side, so the reading and tab order match the visual order (left to right) on desktop and the one-column flow on phones. The disabled Decide step stays in the side column. Both the writable and read-only branches use the same predicates.
- Phone bar word: `work-barref--line` is applied only inside `LineHeader`, so non-line pages are untouched. The CSS is scoped to `body:has(.sw-phoneslot)`. This agrees with the builder's identical SCR-02 scores on 26 boards. The side-checklist row rule sits in the phone block and targets `.ws-side .ws-rows--checklist`, which exists only for the working-agent case.
- New tests: the bar test checks the six tab names, the Journey-only link with its href, and that no tabindex element is present. The no-project test checks the nav is absent. The placement test checks both columns (side while working, main otherwise). These are meaningful. No existing assertion was changed.

## Findings
- TECH-F2-1 | non-blocking | low | builder | The side `aside` keeps `aria-label="Review and decide"` while it can now hold the agent's checklist. This is accurate enough because Decide sits in it, but a screen-reader user hears "Review and decide" before an assembling checklist. Consider a neutral label when a checklist is in it, or leave as is.
- TECH-F2-2 | non-blocking | low | builder | The doc comments are displaced. The `LineHeader` comment now sits above `ProjectBar`'s comment, and the `WorkspaceHeader` comment sits above `AgentNote`. Move each back above its own function.
- TECH-F2-3 | non-blocking | low | design engineer | The 90 visual bar on the SCR-25 boards is not reached. Two assembling boards fell by about 2 and the phone boards by 0.2, and the builder reports this openly. Waiver or subtitle placement is a design call (D-83). The `--title-line` token is local to work-item.css, and tokens.json is the long-term home.
- TECH-F2-4 | non-blocking | low | builder | The tab bar draws on every desktop line page with a project, including default and invalid boards that do not draw it. This follows D-81 and is flagged in the build note as contract question (b). No action now.
