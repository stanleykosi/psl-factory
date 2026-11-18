STATUS: READY
COMMIT: c5d2515627c96736a1d8884183eb630e29617a0e
BUILDER: builder
LANE: full

## Summary
- Contract mock only. Nothing is sent to anyone: no department request goes out, no project or planning line is really created, no file leaves the machine. This is not a working engagement registration, department request or project creation; every "registered", "confirmed" and "recorded" word comes from a fixture, shown only after the re-read.
- The engagement work item (W-2601, W-2602, W-2604) shows Tola's packet (unknowns stay Unknown), a pre-filled "Confirm PM" form (E-WORK-ASSIGN, candidates from the response only) and "Register engagement" (plan evidence, start date, client contact; E-WORK-STEP). The uncertain registration (W-2604) turns every step off and sends once.
- The planning item (W-2603, on P-0106) shows what each department owes, Tola's checklist, the estimate-changed finding and Readiness; "Record input" opens F-18's team-input form in the shared Drawer and records one department's input under the PM's name (E-RESPONSE).
- D-113 conflicts built as recommended (Ojo Foods/P-0106; open pre-filled PM form; register on press; Drawer for record; "Who receives this?" and "Prepare readiness" disabled with returned reasons; designer notes to PSL not drawn; project bar as F-30; text-plus-money cell rule).
- Ports: mock 4860, app 4861. Fidelity: all 8 boards 100% coverage after exceptions; visual 69.8 to 84.3, so 8 board-level waivers are proposed (one below the 70 floor).

## Changes
- `frontend/src/features/workspace/proposals.ts`: `assignDefault`, `itemTeamKey`, `teamDisabled` readers.
- `AssignForm.tsx`, `useWorkspaceAssign.ts`: preset form drawn open in the side panel (labelled `assign.role`, hint, "Confirm PM", no Cancel); "PM confirmed: <name>" when the role is "PM". F-30's closed form unchanged otherwise. Comment reworded so the `/me` grep returns nothing.
- `ResponseDrawer.tsx` (new): F-18's `useResponse` and `TeamInputForm` in the shared `Drawer`; row team preset, teams with `disabled_reason` not offered, notices, Cancel (above the form on phones, where F-18's Record bar is pinned), closes on 200 / access loss.
- `Workspace.tsx`: a `task_id` step whose task is a `team_input` in the same response opens the drawer (no button when `you_can_act` is false; other `task_id` steps still link to `/decide`); notice, re-read, focus to the table heading; phone Drawer also for the `engagement` line; the preset form flows in the panel on phones.
- `Sections.tsx`: cell rules only: text plus money reads "text · amount"; a tag or text cell that exists and carries nothing (or a missing tag cell) reads Unknown.
- `WorkItemView.tsx`: phone back link to the project for the `planning` line too.
- `workspace.css`: two additive rules (tokens only).
- `frontend/src/features/response/useResponse.ts` (shared, read-only lane): ONE additive field, `Notice.problem.forbidden`, set when the refusal was a 403, so the Drawer can close onto the not-open view (AC 13). F-18's page ignores it; F-18 tests (`response.test.tsx`, `response-mock.test.ts`, `rfp.test.tsx`) are green and unchanged.
- Mock: fixtures `W-2601`, `W-2601.next`, `W-2601.steps`, `W-2602`(+`.next`, `.steps`), `W-2603`, `W-2604`(+`.next`, `.steps`), `fixtures/response/W-2603.recorded.json`, P-0106 `lines[]` entry, `mock/proposals/engagement-planning.json`. `workspace.mjs`: a script may carry `serve` (another fixture served under the item's id, so W-2601 walks confirm then register). `response.mjs`: upload accepts a workspace step's evidence kind; a team input on a task that stays open for other teams (sidecar has no `recorded`) answers `recorded {by, at, summary, proof_count}` without marking the task recorded (otherwise Infrastructure's drawer would open "done").
- Deviations from the spec text: (a) the registered item's "Created" section is kind `text`, not `facts`, because the facts renderer draws no cites and the links must come from cites; (b) the recorded sidecar has no `links`, `team_key`, `asked_at` because the existing `response-mock.test.ts` validates every sidecar strictly (so "Ask Tola" and the Infrastructure team preset are absent after the first record on the mock); (c) W-2603's `line` is "Plan a project" to match the P-0106 row (existing `mock-projects` test requires it); (d) the start-date field carries `help: "Agreed with the client on 9 Dec"` as fixture data.
- Tests: `tests/engagement-planning.test.tsx` (44), `tests/engagement-planning-mock.test.ts` (18), `e2e/engagement-planning.spec.ts` (26 at 1440 and 390). `tests/mock-contract.test.ts`: two edits for the new fixtures only (links allowed on `W-26xx`; the F-31 overlay keys stripped and checked before the schema check). No other existing test edited.
- `delivery/BACKEND-HANDOFF.md`: "Added during F-31" section.

## Contract proposals (overlay, mock only; for the backend developer)
`assign.default_person_id` and `assign.default_hint` (G-41-1), `items[].team_key`, `teams[].disabled_reason`, `teams[].asked_at` (not read) (G-42-2), text-plus-money cell (G-41-3). Not read, for the backend only: `quantity` cells (G-42-1), E-WORK-STEP `created[]` and half-done registration recovery (G-41-5), plan evidence before the project exists (G-41-4), client contact record (G-41-6), side-panel title, link target for "Who receives this?" (G-42-4). Held for PSL: G-42-3, G-42-5, G-42-6, G-41-2. Blocking for real writes: G-41-1, G-41-4, G-41-5 (rate high).

## Acceptance criteria
1. [x] Packet from data: `engagement-planning.test.tsx` (rows, tags, "Costing v2 · ₦40,951,000.00", unknowns line, checklist, Ask Tola; no "Open question for PSL"); src grep for board strings returns nothing (test).
2. [x] Money and Unknown: unknown money reads "Costing v2 · Unknown"; removed tag or tag cell reads Unknown; other fixtures' tables (W-2002, W-2004, W-2312; the spec's W-2209/W-2411 have no tables) draw their words with Unknown only where data says so.
3. [x] Confirm PM: PM Select with 3 candidates, Sola chosen, hint, "Confirm PM"; one POST, body `{expected_revision: 3, person_id: "P-0021"}` validates, double press one, "PM confirmed: Sola Martins" and register step from the re-read; stray/absent default gives F-30's closed form; grep for `useMe` and `/me` in AssignForm and the hook returns nothing.
4. [x] Register: form with the 3 fields; one upload to C-2602 with its case_revision; one POST validating against the generated schema (`inputs.start_date "2027-01-15"`, trimmed contact, `evidence_ids`, UUID key, empty optional not sent); message and links from the re-read cites.
5. [x] Never repeats blind: W-2604 uncertain notice, all steps `aria-disabled`, reload keeps it, one register request; 500 and network error say "Not done", Try again reuses the key; 409 keeps entries and sends the new revision; 422 under the field.
6. [x] Departments from data: status, byline, five rows, estimates and Unknown, note, finding with cite, checklist, Readiness; no `reduce(` or "person-days" in `features/workspace` source.
7. [x] Controls only from the response: Record input on QA and Infrastructure; Who receives this? disabled with reason and no href; Prepare readiness disabled, sends nothing; same controls for pm, finance_lead, ceo; stripped steps and `you_can_act: false` draw none.
8. [x] Record: Drawer "Record department input", picker QA and Infrastructure (QA from `team_key`), estimate, what, proof, Received, attestation, intro; POST body validates against the generated schema (`team qa`, `estimate_person_days 45`, `attested`, revisions); claim only when `claim_required`; double press one; on 200 drawer closes, re-read shows QA IN, "PLANNING · 3 OF 5 IN", button gone; focus to the table heading; `disabled_reason` team not offered.
9. [x] PM's name: "Recorded under your name: …"; no "logged in" text or source; Record off without the attestation.
10. [x] Failures: 422 keeps entries; 409 re-reads, no resend; 500 and network error re-read and never say recorded. A stale proof upload (409) re-read is F-18's `useEvidenceUpload` (unchanged) and the mock rule is in `engagement-planning-mock.test.ts`; no new component test drives it.
11. [x] Agent text only displayed; Ask Tola only when `links[]` carries it.
12. [x] Planning from the project: P-0106 "Plan a project" links to `/work/W-2603`; project bar six links none current; phone back "Project"; W-2209 keeps "Queue" (unit); e2e reaches the page from the project.
13. [x] 401 signed out; 403 and 404 same view with no title or fact (unit and e2e via route interception); a 403 on the record write closes onto that view. Persona `none` is not enforced by the work-item mock (existing behaviour), so that part is not tested.
14. [x] No `/me` read in `features/workspace` or `features/work-item` (test over the sources).
15. [x] Phone: Register and Record open the full-height Drawer; Escape and Cancel close it and return focus; no sideways scroll; QA's Record input is at least 44px high (e2e at 390). Other row buttons use the shared Button.
16. [~] Fidelity: coverage after exceptions 100% on all 8 boards; visual below 90 on all 8, so proposed waivers (see below).
17. [x] axe (wcag2a/aa/21/22aa) clean at 1440 and 390 on W-2601 to W-2604, the open register form, the open record Drawer, the not-open view, after the record and after the uncertain state. Not covered by axe: a 422 state in each form and the empty workspace (unit tests only).
18. [x] No `#hex`, `rgb(`, `hsl(` added in CSS; the drawer is the shared `Drawer`.
19. [x] Mock test covers fixtures vs generated schema, `default_person_id` in candidates, register and uncertain scripts, T-2603 rules, swap, reset.
20. [x] No change in `src/api`, `apps`, `architecture`, `design`, `src/shell`, protected paths (`git diff --stat` empty for them). Existing fixtures changed: only the P-0106 line. `src/features/response/**` has the one additive field listed above.
21. [x] checks.sh passes; e2e listed below. No existing assertion edited, skipped or loosened except the two `mock-contract.test.ts` edits for new fixtures.

## Validation
- `bash /Users/Hunchoo/psl-factory/delivery/checks.sh` under the shared lock: first run exit 1, one failure in `tests/setup-rules.test.tsx` (file this branch does not touch; load average 26 to 34); re-run alone: 42 passed; second full run: exit 0 (django check, lint, typecheck, 2331 tests, production build).
- `npx vitest run tests/engagement-planning.test.tsx tests/engagement-planning-mock.test.ts`: 44 and 18 passed. `tests/mock-contract.test.ts` 297 passed.
- e2e: `E2E_PORT=4861 MOCK_PORT=4860 npx playwright test e2e/engagement-planning.spec.ts e2e/workspace.spec.ts e2e/work-item.spec.ts e2e/issue-detail.spec.ts e2e/project-tabs.spec.ts e2e/response.spec.ts e2e/rfp.spec.ts`: 183 passed, 1 failed (`workspace.spec.ts W-2003 at 390`, `.ws` not attached while the proxy logged ECONNRESET under load); re-run alone: 1 passed. Earlier runs of the new spec had failures I fixed (upload not awaited, 403 via cookie hit `/me`, phone Cancel covered by F-18's pinned Record bar).
- Servers stopped by their own PIDs; `frontend/test-results` deleted.

## Fidelity (one run, production build `API_ORIGIN=http://127.0.0.1:4860 FRAME_FIXTURES=1 npm run build`, app 4861, mock 4860; frozen boards via `serve-frozen.mjs` on 4860 with the mock stopped)
Files: `round-1/fidelity/` (scores.txt, per-board reports, `drive-states.mjs`, `run.sh`, `frozen/`). Exceptions: `delivery/features/F-31/fidelity-exceptions.json` (44 entries, each with a Conflicts number, `approved_by: "builder proposal, pending design engineer"`; 8 visual waivers, same approval).
Before the final run I ran the tool once with an empty exceptions file to list the differences (logs not kept); the scored run is the one in `scores.txt`. The last small edit (phone Cancel position in the Drawer) came after the run; it moves one secondary button.

| board | width | coverage | with exceptions | visual |
|---|---|---|---|---|
| SCR-41-desktop | 1440 | 77.3 | 100 | 82.2 |
| SCR-41-mobile | 390 | 60 | 100 | 80.4 |
| SCR-42-desktop | 1440 | 73.2 | 100 | 74.0 |
| SCR-42-mobile | 390 | 42.9 | 100 | 80.0 |
| SCR-41-desktop-register | 1440 | 77.8 | 100 | 77.6 |
| SCR-41-mobile-register | 390 | 66.7 | 100 | 69.8 (below the 70 floor: one-board exception asked) |
| SCR-42-desktop-record | 1440 | 70.3 | 100 | 84.3 |
| SCR-42-mobile-record | 390 | 64.7 | 100 | 71.7 |

Open design-engineer decisions: the 8 visual waivers (D-83, shared frame D-99, D-107, D-110, D-112) and the 69.8 floor exception. The board's "Unknowns stay Unknown…" line sits in its own panel (board: a line inside the table panel) and is excepted as `component`; moving it into the table panel needs a frame change.

## Left open
- Prepare readiness, Who receives this?, Ask-Tola-sends and costing v3 are out of scope and disabled as specified.
- Frozen register/record boards were driven with the real controls; the driver ticks the attestation (an extra control the board does not draw, Conflicts 14).
- Disabled "Prepare readiness" renders dark text on the green panel button (existing Decide-panel disabled style, as F-29's disabled Ask Tola); not changed here.
