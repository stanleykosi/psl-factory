STATUS: READY
COMMIT: 798c17f8b0b30f6aabf94dc0ff621a901b6df7e4
BUILDER: builder
LANE: full

## Summary
- Round 2 fixes the three blocking findings (UX-1-1, UI-1-1, UI-1-2) and one small UX note (UX-1-4) in one commit.
- Fixtures W-2201..W-2204 no longer draw rows their boards do not have; W-2204 shows the board's short references.
- The weekly form tells the person that saved cites stay until they choose new ones, and sends no cites field they did not touch.
- Phone: the pinned Decide bar hides while a Decide step's own form is open, so Send is not shown twice.
- All 8 boards re-scored once: coverage 100 after approved exceptions on all; visual 72.8 to 80.3 (D-83 waiver, >= 70, still holds).

## Changes
- `frontend/mock/fixtures/work/W-2201.json`: dropped `byline`; `help` on the four cite fields: "Records you cited in the saved draft stay on it until you choose new ones."
- `W-2202.json`: dropped `byline`, `subtitle`. `W-2203.json`: dropped `subtitle`. `W-2204.json`: dropped `byline`, `version`, `subtitle`; `cite_label` "ISS-0233" on P-2 and "MIN-0141" on P-3.
- `frontend/src/features/workspace/Workspace.tsx` and `workspace.css`: `data-form-open` on the Decide panel while a `ws:` step form is open; hidden in the phone layout only.
- `frontend/tests/weekly.test.tsx`: three new tests (below).
- Main folder: `fidelity-exceptions.json` waiver reasons updated with the new visual numbers (approved_by unchanged); `round-2/fidelity/` holds frozen pages, reports, side-by-sides, `scores.txt`.

## Fixes
- UX-1-1 | 798c17f8 | Contract limit: a `records` field's `value` is a string, so saved cites cannot prefill the pickers (no list-valued value). The frame already omitted empty cites; a test now pins that (open + Save draft sends no `*_cites` key and no empty list), and the cite fields carry a hint line that saved cites stay. Note: the hint is a claim about server behaviour (omitted = keep); the backend must confirm it. Also: Send on a saved draft without re-picking cites will get the server's 422 until prefill exists. Contract question for the coordinator: allow `value` as a list of option `{value,label}` for `records` fields. That test passes on old code too for the request shape; only the hint assertion fails on old code.
- UI-1-1 | 798c17f8 | byline/version dropped on W-2201, 2202, 2204; subtitle dropped on W-2202, 2203, 2204. Test added. W-2205 left unchanged (not asked).
- UI-1-2 | 798c17f8 | `cite_label` set on P-2 and P-3 as the board draws. Open question for backend/PMO: the board's "MIN-0141" (minutes) vs the fixture's cited MTG-0140 (weekly sync); not decided here, the board's reference is used only as the label.
- UX-1-4 | 798c17f8 | phone Decide bar hidden while its form is open.

## Left, and why
- UX-1-2 "(optional)" labels: the label comes from the frame's IntakeField for `required: false` (spec sets false so the server owns the rule). Frame or design-engineer matter.
- UX-1-3 disabled primary button contrast: shared design-system button; noted, not changed.
- UX-1-5 W-2205 reconcile layout: shared F-09/F-17 layout, frame owner.
- UX-1-6 phone titles/back labels: approved exceptions.
- TECH-1-1..5, SEC-1-1, SEC-1-2: backend/notes (server-side duplicate-send guard, cite scoping to actor/case/week, 422 field naming, mock label "received" in W-2204 is sample text). No change in F-21.
- UI notes: fixtures W-2201 and W-2202 word the meetings records differently; not drawn on the same board state, left.

## Acceptance criteria
1. [x] AC 6 default state from data: W-2201 renders from fixture; test covers rows present/absent per state.
2. [x] AC 7/8 form and write request: Save draft sends no untouched cites; Send test unchanged and passing.
3. [x] Other criteria unchanged from round 1; the full weekly and workspace e2e pass.

## Validation
- `bash delivery/checks.sh`: exit 0 (an earlier run showed one transient unit failure; the rerun of the two files passed, then checks.sh passed in full).
- `E2E_PORT=4741 MOCK_PORT=4742 FRAME_FIXTURES=1 npx playwright test e2e/weekly.spec.ts e2e/workspace.spec.ts`: 62 passed.
- Fidelity (production build, FRAME_FIXTURES=1, frozen pages re-captured, one run), coverage with exceptions / visual: desktop 100/72.8, invalid 100/79.9, assembling 100/73.7, review 100/76.6; mobile 100/72.9, invalid 100/79.0, assembling 100/76.9, review 100/80.3. Visual below 90 on all, covered by D-83 waivers. Changed numbers on 7 of 8 boards (mobile-review 80.4 to 80.3); desktop default fell 75.3 to 72.8, desktop assembling 77.0 to 73.7 (the page got shorter so boards' bottoms no longer line up); waiver reasons updated to the new numbers. Raw coverage unchanged.
- Servers on 4741 to 4743 stopped by PID. `frontend/test-results` still exists (git-ignored): my `rm -rf` was refused by the permission system, so please delete it.
- `git status --porcelain` clean; pushed.

## Blocked
None.
