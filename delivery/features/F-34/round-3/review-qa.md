VERDICT: PASS
REVIEWER: qa
COMMIT: 0ce04acb81f47bccea617df483c1691541d99403
AUTHORITY: delivery integrated QA

## Summary
- I ran a production build of af38b432 in the worktree (`API_ORIGIN=http://127.0.0.1:4978 FRAME_FIXTURES=1 npm run build`, then `npx next start -p 4979`) against the contract mock (`MOCK_PORT=4978 node mock/server.mjs`), as persona `pm`. A Playwright driver ran 15 checks (14 pass, plus 1 measurement artefact explained under journey 5). I also ran the e2e suites with `E2E_PORT=4980 MOCK_PORT=4981 npx playwright test e2e/delivery-hypercare.spec.ts e2e/workspace.spec.ts`. Result: 58 passed (hypercare 21, workspace 37), including the phone-390 record-form test that now asserts the "×" is at least 44px. Afterwards I stopped my own app and mock PIDs and deleted `frontend/test-results`.
- QA-2-1 is fixed. At 390, after a proof upload, the "×" in the step form measures 48×48 in both the record form (W-3102) and the observation form (W-3101). It still removes the file, and the journeys complete with one upload, one step and Done only after the re-read. F-18's own respond page is unchanged: its "×" stays 24×24 at 390 and 1440.
- The regression pass at 390 found no change in the other lines' step forms: weekly W-2209, issue W-2411 and planning W-2603.
- **Not proved**, as in round 2. Everything runs on the contract mock only. There is no real backend checking evidence ids, idempotency or per-record access. QA-2-3 (unknown id W-3199) and QA-2-4 (evidence ids not checked) are still open for the backend handoff. D11 (window and criteria) is still open, and nothing is deployed.

## Journeys
Driver: /private/tmp/claude-501/-Users-Hunchoo--claude-spares-spare-2d2Z3S/0986a60c-391e-48d6-b2da-79de8713a755/scratchpad/qa-f34/r3.mjs. Output is in r3-run1.txt and the e2e log in r3-e2e.txt, in the same folder.

1. **Record release at 390 (W-3102).** I filled Released on and uploaded `release-1.0.0-log.pdf`.
   - The "×" ("Remove release-1.0.0-log.pdf") is 48×48.
   - No form control is under 44px, axe is clean (wcag2a/aa, 21a/aa, 22aa) and there is no sideways scroll.
   - Pressing "×" removes the chip.
   - I re-uploaded and submitted. There was one `POST /api/v1/cases/P-0101/evidence` and one `POST /api/v1/work/W-3102/steps`, and `/__mock/workspace-log` shows 1 send. "Done: Record release." appeared after the re-read.

   Pass.
2. **Log an observation at 390 (W-3101).** The same checks as journey 1 also pass here: the "×" is 48×48, there are no small controls, axe is clean and there is no sideways scroll. Pressing "×" removes the chip. The journey sends one upload and one step, and "Done: Log an observation." appears after the re-read. Pass.
3. **Desktop contrast at 1440.** On W-3102 and W-3101 the "×" is 24×24, because the new rule applies on phones only. Axe is clean. Pass (expected).
4. **F-18 respond page is unchanged.** On `/work/W-1601/respond?task=T-1601` at 390 and 1440, the title is "Record a response · PSL Factory". After uploading `Lagoon_UAT_signoff_11Nov.pdf` (184 KB), the "×" is 24×24 at both widths and is not inside `.ws-form` or `.cmp-panel`. Axe is clean and there is no sideways scroll. Pass.
5. **Other lines' step forms at 390.**
   - W-2209 weekly: "Edit your update" opens. No control is under 44px, axe is clean and there is no sideways scroll. Pass.
   - W-2411 issue: a blank "Post update" shows the "to continue" message. Controls are at least 44px and axe is clean. "Progress update" with text posts, and "Done: update posted." and "Owner update · recorded by PM" appear after the re-read. Pass.
   - W-2603 planning: the "Record input" opener is 44px. The Drawer's chip "×" is 48×48 (the earlier `.cmp-panel` rule), and axe is clean.
     - My generic scan flagged one 20×20 input. It is the attestation checkbox, which sits inside its `label.psl-check.resp-attest` of 358×58 (r3-cb.mjs). So the touch target is fine, and this is the measurement artefact counted as one fail in the driver total.
     - Recording sets the state to "PLANNING · 3 OF 5 IN". Pass.
6. **e2e.** 58 passed. This includes `delivery-hypercare.spec.ts:72` at phone 390, which now measures `.resp-chip__remove` at ≥44 with no exclusion, and the network-failure, 409, uncertain and access tests.

**Carried forward from round 2 (on e3928527), by impact assessment.** Since e3928527, the round changes one phone-only CSS rule under `.ws-form` (workspace.css:254) and an e2e assertion. The dlv-00 merge touched only `tests/setup.ts` and `vitest.config.ts`. No TSX, mock, fixture or API code changed. So these round-2 journeys still hold and were not re-driven one by one:
- Delivery tab → W-3101;
- default window and criteria;
- the setup-needed hold (W-3103);
- qualified only from verified (W-3104/W-3110);
- failure fixtures W-3105/3106/3107/3108/3112;
- invalid and refused input (422/403/404/401, upload 500, CSRF, persona `none`);
- read access 401/403/404 with no leak;
- Unknown never 0 (W-3111);
- controls only from the response (W-3109);
- desktop axe;
- F-32's W-2502.

The hypercare and workspace e2e re-ran green on this head and cover most of them.

## Findings
None.

QA-2-2 (the frame's "History" link is 24px, non-blocking), QA-2-3 and QA-2-4 from round 2 are unchanged and stay open as non-blocking items outside this round.

## Verified
- QA-2-1 | verified | At 390 after a proof upload, `.ws-form .resp-chip__remove` measures 48×48 in W-3102 Record release and in W-3101 Log an observation. It removes the file, and the form is axe-clean with no control under 44px. The e2e `delivery-hypercare.spec.ts:72` (phone 390) asserts ≥44 with the `:not(.resp-chip__remove)` exclusion removed, and passed. F-18's `/work/W-1601/respond` "×" is still 24×24 at 390 and 1440.
