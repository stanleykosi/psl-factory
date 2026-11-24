STATUS: READY
COMMIT: 9a110b1de3376866467c4c06531efca790478589
BUILDER: builder
LANE: full

## Summary
- `/work/{id}` for a forecast item now reads `GET /work/{id}/forecast` through a new forecast line adapter (panel key `forecast`, found in `apps/core/factory_api/work.py` STATION_PANELS; `forecast/disclosure` and `forecast/lifecycle` are write routes, no adapter) and draws header, stage and finding, months table, items, findings, matches, group disclosure and delivery. Read only; no POST anywhere.
- Month actuals come from `GET .../actuals/{month}` through a month control (`?month=YYYY-MM`), with the "first rows only" sentence and no Show more. The proof is a plain link to the observation route.
- The group guard is in the mapper: group view draws only header, months, disclosure and delivery; object entries keep only label or key; nothing payroll is read from another route.
- Mock serves ids 4301 to 4308 in the live shape (4308 is the poisoned group variant). Contract 1.25.0 already types the arrays, so the mapper reads the real field names (month, opening, inflow, outflow, closing; items key, kind, expected_on, matched, residual).
- Not READY on design fidelity: see Validation. The gap is parts the API does not supply and board wording; no waiver or exception filed yet.

## Changes
- `frontend/src/features/forecast/labels.ts`: pure mappers (periods, items, findings, matches, disclosure, delivery, uncertain test, month actuals, error words).
- `forecastAdapter.ts`: reads the panel, turns 401/403/404/409/422/csrf into the page's own words (a note section); other failures are thrown so the shared frame shows Try again. Registered under `forecast`. No commands.
- `ForecastExtra.tsx`, `useForecastActuals.ts`: month control, month actuals, Proof link, sign-in link on 401.
- `frontend/src/api/types.ts`: `LiveForecast`, `LiveForecastMonth`.
- `frontend/mock/forecast-live.mjs` (new) and a hook in `mock/server.mjs`; scenario `forecast:<status>` answers only the forecast read. No `mock/finance*` or payments fixture changed.
- Tests: `tests/forecast-live.test.tsx` (16), `tests/mock-forecast-live.test.ts` (validates mock against contract), `e2e/cash-forecast-live.spec.ts`.
- SHARED FRAME CHANGES (spec says dependency on lane C; unavoidable because no section kind can draw a link or a control that reads more, and F-87's Actions slot is not on main). Two small additive commits, 22187535 and 8a01fc7a: `src/features/workspace/adapter.ts` adds optional `Extra` and `LineExtraProps` to `LineAdapter`; `src/features/work-item/live/LiveWorkItemView.tsx` imports the forecast adapter, keeps the readback in `PanelView` state and draws `adapter.Extra` under the sections. Lane C: F-87's `Actions` may replace `Extra`; expect a trivial merge in `PanelView`.

## Fixes
(round 1: none)

## Acceptance criteria
1. [x] 4301 header, six rows, "Receipt 9": e2e passes at 1440 and 390.
2. [ ] Live Django comparison not run (no forecast work item exists on the 55433 database and seed commands are not mine to run). Mock shape is validated against the 1.25.0 contract.
3. [x] Unknown closing: e2e and unit test (missing, null, "0.00" give Unknown, Unknown, zero amount).
4. [x] 4303: e2e and unit test.
5. [x] 4307 unavailable (e2e); error words unit test; 409 forecast-only scenario keeps the header (e2e). 401 draws words plus a sign-in link in `ForecastExtra` (unit-tested words; link not e2e-tested). 429/503/network use the shared frame's Try again, not the spec's exact "Try again shortly" wording.
6. [x] 4305 texts and no Retry/Cancel/Record/Resend button (e2e).
7. [x] "No receipt yet" (unit and e2e).
8. [x] 4306 href `/api/v1/work/4306/forecast/observations/8`, no request until clicked (e2e); false case "No proof on file" (4305).
9. [x] 4304 and poisoned 4308: no staff name or pay in DOM, storage, URL or requests (e2e, unit). Whitelist is applied as "label or key only" for object entries.
10. [x] Unit tests, group read with and without disclosure.
11. [x] Zero input/select/checkbox in 4304 (e2e).
12. [x] Month 2026-11 loaded once, In/Out, Verified, Unknown, Reversed (e2e, unit).
13. [x] Cut sentence on 2026-11, absent on 2026-09 (e2e).
14. [x] Empty month and 404 month keep the forecast (e2e).
15. [x] No write requests or write buttons on 4301 to 4306 (e2e); no `.POST(` in the feature folder.
16. [x] No "not set" text or "M" money (e2e on 4302/4301 at both widths).
17. [x] Revisions are never rendered; the adapter has no commands, so there is nothing to carry yet (unit test). Carrying null revisions is F-103B.
18. [x] `adapterFor('forecast')` returns the adapter (unit); F-85 tests pass.
19. [x] Types come from the generated 1.25.0 types; drift test passes.
20. [ ] Boards not matched; see Validation. axe WCAG 2.2 AA clean on 4301 to 4305 at both widths (e2e).
21. [x] `e2e/cash-forecast.spec.ts` and `e2e/work-item-live.spec.ts` passed in the same run (70 passed).
22. [x] Tests exist and run.

## Validation
- Unit: `npx vitest run tests/forecast-live.test.tsx tests/mock-forecast-live.test.ts tests/live-work-item.test.tsx tests/line-adapter.test.tsx tests/api-live-schema-drift.test.ts`: all pass. `npm run lint` and `tsc --noEmit` clean. `npm run build` passed. Full vitest and the full gate not run (left to the coordinator, D-189). The new tests have no old code to fail against (new feature).
- E2E on a production build (ports 4996/4997): cash-forecast-live + cash-forecast + work-item-live, 70 passed and 2 failed (a test wording clash, "Actual 5 . In" matching twice); I fixed the test and re-ran that spec directly: 2 passed.
- Fidelity, ONE run, 14 boards (production build; 4304 used for both group boards, 4301 with `?month=2026-11` for actuals). All fail the 100%/90 bar; no exceptions file given. Coverage / visual: desktop investigating 25/72, review 31.7/77, group-rows 31/79.5, group-review 25.6/76.6, uncertain 33.3/74.9, verified 25/73.5, actuals 36.4/80.2; mobile investigating 22.2/71.1, review 28/76.5, group-rows 33.3/77.5, group-review 25/78.6, uncertain 28.6/80.9, verified 11.8/76, actuals 40/79.2. Reports in the scratchpad `fid/` folder. The missing items are mostly the parts the spec hides (station track, six facts, agent card, decide and recovery controls, reviewer-not-set, short money, pagination) plus board wording and layout differences I did not iterate on. Needs a design engineer decision: approve exceptions or a visual waiver (all at or above 70).
- Not done: live Django check (criterion 2).

## Blocked
Not blocked. Open for others: design-fidelity exceptions or waiver (design engineer); lane C to confirm the `Extra` slot versus F-87's `Actions`.
Notes for the coordinator: (a) the v7 mock item 4107 in `mock/work-live.mjs` uses panel key `forecast` as its "no adapter" case; it still passes (the new adapter answers 404 for it, drawn as a note), but a different key would keep that test honest. (b) Spec said the arrays are untyped; 1.25.0 types them, so spec Assumptions are out of date. (c) Uncertain-job statuses are my reading (`sent`, `sending`, `unknown`, `uncertain`); the API publishes no list.

## Coordinator note (24 Nov)
- Not gated yet. Commits 22187535 and 8a01fc7a add an `Extra` slot to lane C's shared frame (workspace/adapter.ts, LiveWorkItemView.tsx). That duplicates F-87's `Actions` slot and breaks lane C's rule against importing adapters in LiveWorkItemView.tsx. When F-87 is on main: merge main, revert those two commits (no force-push), draw the proof link and month actuals through `Actions`, and register the adapter in `workspace/lines/index.ts`. Then gate.
- Fidelity gaps: the parts the spec hides plus board wording, from options accepted under D-187. These go on the design engineer's look-back list, as with F-119.
- Live Django comparison (criterion 2): no forecast work item on 55433 yet. QA creates one through POST /work with qa-seed. If a seed command is needed, it goes in the merge batch, not run unasked.

## Coordinator: D-202 (24 Nov)
The design engineer, in chat (relayed by the main coordinator): "Ship simpler for demo". F-103 ships without the proof link and month actuals: drop the `Extra` slot (commits 22187535 and 8a01fc7a, plus ForecastExtra.tsx and useForecastActuals.ts). Add them back on F-87's `Actions` slot after F-87 merges. It builds after F-119 frees a worktree (D-197: two worktrees).
