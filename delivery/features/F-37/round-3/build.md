STATUS: READY
COMMIT: 36db1217cc448105529fc82e2e2ec5087be13606
BUILDER: builder
LANE: full

## Summary
- Round 3 fixes the loose checkbox rule at 390 and draws the past-answer result and link from fixture data.
- The three "Harmattan" exceptions (two on the review boards, one on the phone) are removed from `fidelity-exceptions.json`.
- Technical notes: `justify-items: start` is now scoped to the RFP line (TECH-2-1). TECH-2-2 (repeated note conditions) left, behaviour correct.

## Changes
- `frontend/src/features/workspace/workspace.css`: `.ws-table--stack td.psl-check-cell, th.psl-check-cell { border: none }` at 390 (shared stacked-table rule, border removal only; F-30/F-31 stacked tables have no select box column so are not affected). `justify-items: start` moved to `.ws[data-line="rfp_response"]`. The past-answer link in the review panel is a 44px tap target (RFP line, phone).
- `frontend/mock/fixtures/work/W-3402.json`, `W-3403.json`, `W-3403.next.json`: the R-07 item's detail now ends "· that bid was won" and carries a cite "Harmattan Bank RFP 2025 · R-12" (work_id W-1999) that draws as a link.
- `frontend/tests/rfp-requirements.test.tsx`: past-answer test now expects the result text and the link; CSS test covers the check-cell rule and the scoped justify-items.
- `delivery/features/F-37/fidelity-exceptions.json`: three "Harmattan Bank RFP 2025 · R-12" exceptions removed.

## Fixes
- UI-1-5 | stacked-table select box cells no longer draw a loose rule at 390 (same change as UI-2-1) | befd93dcf5415e1791379530158a4fd4dd64c81a
- UI-2-1 | border removed on the select-box cell and header box in `.ws-table--stack` | befd93dcf5415e1791379530158a4fd4dd64c81a
- UI-2-2 | past-answer result and link added to the W-3402/W-3403 fixtures; exceptions removed | befd93dcf5415e1791379530158a4fd4dd64c81a, link tap size 36db1217cc448105529fc82e2e2ec5087be13606
- TECH-2-1 | justify-items scoped to the RFP line | befd93dcf5415e1791379530158a4fd4dd64c81a

## Acceptance criteria
1. [x] Review flows and fixtures: `npx vitest run tests/rfp-requirements.test.tsx` 34 passed.
2. [x] Phone 44px targets: the e2e check caught the new link at under 44px; fixed, now passes.
3. [ ] Fidelity: not re-run this round. The live boards (W-3401) are unchanged. The review boards are driver-frozen and changed by one text suffix and one link; the closing exceptions should be re-scored by the coordinator if wanted. Prior scores (round 2) stand.

## Validation
- `bash delivery/checks.sh` under the shared lock: rc=0 (run on befd93dc; the later commit changes one CSS rule only).
- e2e `rfp-requirements.spec.ts` + `rfp.spec.ts`: 55 passed, 1 failed (44px link), fixed, then the 44px test re-run on phone: pass.
- I did not visually re-check the F-30/F-31 stacked tables at 390; the rule touches only `.psl-check-cell` borders, which those tables do not have. Demo rebuilt: app 4995, mock 4994, both running (200).

## Blocked
None.
