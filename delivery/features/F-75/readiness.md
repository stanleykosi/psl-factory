DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-75 is the F-71b slice: the Registers (SCR-11) and Actions (SCR-29) tabs moved from the v7 mock to the live `GET /projects/{case_id}/{tab}` read. It is read-only, one outcome, and sized for one PR (about 4 files rebuilt: `tabsModel.ts`, `useProjectTab.ts`, `RegistersTab.tsx`, `ActionsTab.tsx`, plus tests).
- The gate that made F-71 NOT-READY is cleared: F-70 is merged (PR #102, main be9d34d9, per coordinator-answers.md). The split is accepted and Money/Milestones moved to F-71.
- FE-CONNECT-1 is the explicit D-180 exception named in LANES.md, and D-182 (hide what live cannot supply, accept all recommendations) settles the board conflicts. Product acceptance is recorded under D-184.
- No business rule is needed. Unknown stays Unknown: a null due date shows as Unknown, a missing owner as "Owner needed", and nothing is shown as 0.
- Caveat: I could not run git here, and the main checkout I could read still holds the pre-F-70 tab files. The spec writer must read the merged F-70 code on origin/main (`git -C /Users/Hunchoo/psl-factory-worktrees/lane-b show origin/main:frontend/src/features/projects/<file>`) and take the tab keys and `ProjectTab` model from it, not from the stale checkout.

## Scope
Binding for the spec writer. Task FE-CONNECT-1. Screens SCR-11 and SCR-29. Reads only.

**In**
- `GET /api/v1/projects/{case_id}/registers` and `.../actions`. The live envelope is `{case_id, tab, sections[], as_of}`. Each section is `{title, items[], page, has_more, django_url, api_url}`. Each item has `title, state, detail, at, due, severity, owner, record_id, api_url`. The spec writer must check the generated types and the live schema through `oa.py live GET /api/v1/projects/{case_id}/{tab} 3`. Use the F-56/F-57 live client pattern and the F-70 tab model.
- Registers
  - Render the sections that come back, which depend on the person's permissions. Live sections are Issues, Escalations, Changes, Emergency changes and Bid requests.
  - Identify sections by `title` through one small mapping table that is easy to swap (B-12 is open).
  - Keep the board's register switch for the four drawn registers (Issues, Changes, Emergencies, RFPs). The switch picks which returned section is shown.
  - Row: the title is the reference for issues, changes and escalations, and an issue's own title is in `detail`. Show state text as given, owner as given, and severity as given (including "Critical").
  - Keep `q`. Do not add `state`, `owner` or `severity` filters, because the board does not draw them (G-SCR11-1) and B-14 does not say which values are valid.
  - Row link goes to `api_url`/`record_id` through the existing matching detail route if one exists. Otherwise the row is not a link. Do not invent a route (B-15).
  - Paging: live has one shared `page` for all sections, 25 rows per section. "Show more" must use `has_more` of the selected section only. The spec must say how a page fetched for the selected register stays consistent when the other sections also page. No `limit` and no page-size choice.
- Actions
  - Map section "Project actions": title is the action text, state text as given, owner name from `detail` or "Owner needed", `due` null shown as Unknown.
  - Keep `q`.
- State mapping: live `state` is display text, so `STATE_TAGS` cannot be fed from it. Rebuild the tag mapping on display text with a neutral default tag for unknown words, and keep it in one small table (B-2, B-35 are open).
- Keep the empty, loading, error, forbidden and not-found states, plus the as-of time.

**Out**
- Every write: record, update or close an issue, change, emergency or escalation, assign a bid, assign, complete or create an action. They need an `evidence_id` (B-37) and are not drawn.
- Money and Milestones (F-71). Documents tab. Journey.
- Issue detail, action detail, and meetings.

**Hides under D-182 (board conflicts that are only hides; build option 1; the spec lists them for the design engineer)**
- Per-register count badges and the header counts ("12 ACTIONS · 3 OVERDUE · 2 WITHOUT OWNER"). Live has none, and they must never be counted from one page or shown as 0.
- Age column and owner role. Owner "recorded by PM" and outside-party marks. The "From <meeting> · <date>" line. Overdue as a state. Live list state is the status word only.
- Page-size choice (10/20/50).
- Open spec decision, not blocking: Escalations is a live section with no board. The spec writer lists it and builds the lowest-risk option, which is to leave it out of the switch and list it for D-184. It must not invent a drawn design.

## Risk
Medium. It is read-only and touches no money, identity or data migration. It is a cross-layer contract change: the typed v7 arrays become display-text sections with a different paging model, and the tab model and tag mapping are rewritten (`tabsModel.ts`, `useProjectTab.ts`, `STATE_TAGS`). The main hazards are matching sections by `title` text (B-12), showing unknown values as 0 or as an invented status, and the shared-page behaviour across sections. Product acceptance is required because the client sees dropped counts, age and meeting origin, and a changed register switch (D-182, D-184). Surfaces are ui, api and contract-change. Security and auth are not in scope: the live API filters sections and tabs by permission, and the UI only renders what it receives.
