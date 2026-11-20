VERDICT: PASS
REVIEWER: reviewer-technical
COMMIT: c4bd4510133c0c807bf0ae1d2068f8b7a14b6ff8
AUTHORITY: delivery technical review

## Summary
- Change is additive: one src edit (two button labels), mock routing, fixtures, tests. F-05, F-47 and F-49 behaviour is unchanged; only finance_lead line counts (3 to 5) were updated in existing tests, which is unavoidable.
- Lines are served to finance_lead only; /me equals E-LINES; the page reads no roles. Forecast has no Proof box. Unknown is never 0 (no preselected audience, empty Months and As of).
- "Start not disabled while required fields are empty" matches F-05's existing contract (LineForm canPress depends only on caseRef and proofHeld; the server names missing fields). It does NOT match spec criteria 3 and 6 as written, which are internally inconsistent with the "422 Proof is required" half of criterion 6.
- Fidelity is not met (visual 42 to 50); that is for the design engineer and the UI review, not a technical defect.

## Findings
- TECH-1-1 | non-blocking | product | Spec criterion 3 and 6 say "Start stays off until the four required fields are filled". The build keeps F-05's behaviour (Start enabled, server returns "<Label> is required." under each field; the test asserts that). Changing it would touch shared LineForm and alter F-05, F-47 and F-49. Recommend the spec is amended to F-05's contract. frontend/src/features/start-work/LineForm.tsx:232.
- TECH-1-2 | non-blocking | backend | Spec criterion 8 expects 404 for a ppe_register upload to C-0101 or C-FIN-LEDGER; the mock only guarantees a 4xx because F-47 leaves non-owned cases with F-09/F-11 routing. The case binding still holds: ownsUpload and upload() accept only a line's own case, and starts with another case's evidence id answer 422 "That proof isn't on this record" (mock test line 189 to 196). Record the 404 as a backend item. frontend/mock/start-work.mjs:307-335.
- TECH-1-3 | non-blocking | frontend | Accounting note has four sample options instead of two so the drawer draws a select; sample labels, no business terms. Accepted as mock fixture only.

## Verified
- Authority: lines only in lines.finance_lead.json and me.finance_lead.json; the mock test checks pm, ceo and none get neither.
- Evidence binding: upload is to the fixed case C-FIN-PPE with the revision chain; foreign or unknown ids are refused; no src logic for kinds, size or type.
- Forecast mock: Months, As of and Audience 422 messages are mock samples only; the page adds no validation; start_hold lands on W-4006 as setup_needed.
- src diff is labels.ts only; no api, components or shell changes. checks.md records a passing run on this head.
