VERDICT: PASS
REVIEWER: reviewer-ux
COMMIT: 8d7da0c400b19e41356a0230e1328978452bc763
AUTHORITY: delivery UX review

## Summary
- Checked that upload failures are now announced, and announced once.
- StartProof adds one visually hidden `role="alert"` span per failed file, inserted together with its words ("<name>: Not uploaded. <reason>"). This is the same insert-with-words pattern Callout uses.
- It is not read twice: F-09's ProofField card has no live region (its reason is plain text), and 403/404 (CANT_ADD) is left out because the drawer Callout already announces it. The fieldset's aria-describedby points only at the 422 error, not at the alert.
- Once a failed file is removed or replaced by a good upload, no alert is left. A 422 under Proof is now linked to the Proof box. Try again after the case is gone drops the file and shows "You can't add proof to this item." (fixed line) or "That choice is no longer available. Choose again." (project).
- Tests run on this head: vitest: 6 start-work/response files gave 252 passed, and 7 mock-contract/setup/work-item/workspace/weekly files gave 499 passed. e2e/start-work-proof.spec.ts (4946/4947, 5-min load 19.5) gave 14 passed at 1440 and 390; test-results removed. The e2e checks the alert text "qb_export_je7741.pdf: Not uploaded. Couldn't upload. Try again." at both widths, and axe stays clean.

## Findings
None.

## Verified
- UX-1-1 | verified | StartProof.tsx adds a hidden role="alert" per failed (non-403/404) file. The vitest "UX-1-1: each upload failure is announced…" covers a 422 .exe, a 500, a 409 and a 200 without an id, and checks no alert is left after a fix. e2e "ledger states" asserts the alert text at 1440 and 390 with axe clean.
- UX-1-2, UX-1-3, UX-1-4 | carried forward | non-blocking and unchanged this round. The e2e axe runs at both widths stay clean, which still answers UX-1-4.
