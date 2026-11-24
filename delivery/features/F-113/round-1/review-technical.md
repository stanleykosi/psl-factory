VERDICT: PASS
COMMIT: 0517372f2319ecf958c8db0123b884264ab748f6
REVIEWER: reviewer-technical
AUTHORITY: technical review lead, round 1

## Summary
- The Delivery tab reads GET /projects/{case_id}/delivery-overview once, draws the six lines in the fixed order, and shows state words, references, dates and Open links to /work/{work_id}. No write calls.
- The response check rejects wrong shapes (missing field, five or seven lines, duplicate or unknown key) and shows the error state. Closure hold reasons are read only when closure has no work, and their failures are silent, as the spec says.
- The late-answer race is guarded by a sequence ref in the hook, and the tests cover it. Shared-file edits (model.ts, ProjectJourney.tsx, mock server) are small and in the spec's lane.
- No blocking findings. Five non-blocking items: a tone mapping that differs from the spec, two small code-shape points, a misleading mock URL, and two acceptance checks (403 in a browser, 390px) still open.

## Findings
- TECH-1-1 | non-blocking | medium | frontend | effect_uncertain maps to the amber "waiting" tone; the spec asks for the "stopped" tone, and caution maps to "person". TagTone has no stopped or caution values, so the builder chose the nearest tone (build.md Notes). The result is that RESULT UNCERTAIN looks like a waiting state. Expected: a distinct tone for an uncertain effect, or a recorded decision that the UI reviewer accepts. Actual: frontend/src/features/projects/deliveryModel.ts STATE_WORDS. Any new tone belongs in the shared Tag component, so confirm with the design engineer first.
- TECH-1-2 | non-blocking | low | frontend | visibleTabs inserts Delivery with the hard index `PROJECT_TABS[1]`. Reordering PROJECT_TABS would silently move the tab. Expected: look it up by key, for example `PROJECT_TABS.find((t) => t.key === 'delivery')`. Actual: frontend/src/features/projects/model.ts visibleTabs.
- TECH-1-3 | non-blocking | low | frontend | stateWords has a redundant ternary: `line.gate_state === 'not_started' ? 'not_started' : line.gate_state` equals `line.gate_state`, so the expression reads as a rule it does not add. Result is correct. Expected: `line.state ?? line.gate_state`. Actual: frontend/src/features/projects/deliveryModel.ts stateWords.
- TECH-1-4 | non-blocking | low | frontend | mock/delivery-overview.mjs started() sets gate_url to the release-register URL for every line. F-113B reads gate_url, so this fixture would send five lines to the wrong gate. Expected: each line's own gate path, or null. Actual: frontend/mock/delivery-overview.mjs:started.
- TECH-1-5 | non-blocking | medium | frontend | acceptance criteria 10 (403/404 in a browser on 4990) and 14 (390px with no horizontal scroll) are not run (build.md marks them open). The mobile rules in delivery.css place reference and date in column 2 explicitly, while title and tag auto-place, so the 390px result is not clear from the code. Expected: a browser check before merge. Owner: frontend, with the UI/QA check at 390px on 4990.
- TECH-1-6 | non-blocking | low | frontend | the closure reason list is keyed by `r.title`. Two checks with the same title would give duplicate React keys. Expected: key by the check key (carry it in HoldReason) or by index. Actual: frontend/src/features/projects/DeliveryTab.tsx, reasons map.

## Verified
None (round 1).

## Notes
- Contract: the worktree's contracts/psl-factory.openapi.json is API 1.26.0. delivery_overview, delivery_release_register and closure_checklist match the model checks: work_id integer or null, state enum, closure check statuses (held, unknown, unavailable), and dossier_id as an integer. The spec was written on 1.24.0; the lane context says builders use the current contract, so this is accepted.
- Questions Q1 to Q5 are accepted under the F-113 block of questions-batch.md (D-183/D-187 accept-all-recommended). The builder built the recommended options.
- Tests: tests/delivery-model.test.ts and tests/delivery-tab.test.tsx cover the criteria, including negative cases (403, 404, 500, network, wrong shape, late answer, not-started project, no checklist read when closure has work). The edits to projects-journey.test.tsx and projects-model.test.ts add Delivery to the tab lists and renumber the keyboard test; no assertion was removed or loosened. I did not rerun the tests; checks.md shows the gate passed at this head.
- Scope: src/features/workspace, src/api/live-schema.d.ts and the protected paths are unchanged. Shared files touched: model.ts (Delivery tab), ProjectJourney.tsx (one prop), mock/server.mjs (import and three lines). None touch mock/finance* or payments fixtures.
- Security and boundaries: the page only reads. The closure reads use the release line's work id, and the server decides access; a failed read shows nothing. No client-side authority is derived.
- Reviewers: this agent has no tool to spawn the other routed reviewers (SEC, UX, UI, QA). The coordinator must route them as the feature's routing requires.
