RECOMMENDATION: ESCALATE
COMMIT: 1bf933da30fd5e895b5b35f48e89149984c4a305
APPROVER: approver

## Summary
- The Templates tab on Setup lists templates and uploads a new version, on the contract mock only. The diff against dlv-00 is 24 frontend files. It has no edits to architecture, src/api, lock files, package.json or .github.
- Technical, UX, UI and QA pass (QA ran 27 browser journeys, 54 template tests). PMO acceptance passed and was re-confirmed on this synced head. The gate passed at 777d9a3f. The only commits since then are merges of dlv-00 and main.
- The design engineer's product acceptance ("Accept and merge" into dlv-00 and then main, 15 Nov) is recorded in round-2/acceptance-product.md.
- The surfaces include `contract-change` and `product-decision`, and the change touches 24 files against a limit of 15. These are on the merge policy's always-human lists, so auto-merge is not available, even though the work is sound.
- The phone board scores visual 78.8, under the 90 threshold. This is a signed waiver (D-78). D-TEMPLATES-VIEW is still `proposed`, so FE-CONNECT stays gated.

## Why
The change is within scope and well evidenced. The test-template flag is only read from the backend, never set. The remaining human step is already taken: the design engineer accepted and approved the merge. Policy still routes this surface to a person, so I am escalating to confirm that recorded approval, not to ask a new question.

## Acceptance criteria
1. Desktop fidelity: met. Coverage is 100% with exceptions and visual is 95.9.
2. Phone fidelity: met under waiver. Coverage is 100% with exceptions and visual is 78.8, waived under D-78 and signed in `fidelity-exceptions.json`.
3. Exceptions limited and explained: met. PMO checked them against D-71.
4. List from the API only: met. Component tests cover it, and QA confirmed the order and the 8 rows.
5. Badge and copy follow `test_template`: met. A grep of `frontend/src/features/setup` shows no assignment of `test_template` to false.
6. Upload gating: met. The Upload control shows only on rows with `can_upload`, and the 403 path is tested.
7. Upload request: met. QA saw one POST with exactly the four body keys.
8. Success: met. QA saw one reload, the new version shown and the status announced.
9. Stale (409): met. QA exercised the 409 path on the mock and the component tests cover it.
10. Invalid (422): met. QA ran an empty-file 422 naming `filename` and `content_base64`.
11. Other failures: met. The component tests cover them. QA-2-2 (no message when a 403 or 404 on the write empties the list) is low and non-blocking.
12. No double submit: met. Tests cover it.
13. Paging: met. QA saw `cursor=o:50` append rows.
14. Empty and read-only: met.
15. Titles and phone bar: met.
16. Tabs: met. `e2e/setup.spec.ts` changed by one removed line only; PMO reviewed that edit as a listed shared-file edit.
17. Mock matches contract: met. The 54 template vitest tests pass.
18. Accessibility: met. QA reports 0 axe violations at both widths.
19. Tokens only: met per the UI review, which found no new colour literals.
20. Existing behaviour not weakened: met. The technical review found no weakened tests.
21. No new dependency or hard-coded data: met. The diff has no package.json or lock changes.
22. build.md evidence: met per PMO acceptance.

I spot-checked the scope myself. The diff names no protected path, and no code sets `test_template` to false.

## For the human
Confirm the merge of PR #34 (F-20) into dlv-00 and then main. The design engineer's "Accept and merge" is recorded, so I expect no new decision. If you still want to look, check these:
- `frontend/src/features/setup/TemplatesView.tsx`
- `frontend/src/features/setup/useTemplateUpload.ts`
- `frontend/mock/templates.mjs`

Two things stay open and do not block the merge. D-TEMPLATES-VIEW is still `proposed`, so FE-CONNECT stays gated on the backend developer. The phone visual score of 78.8 is waived.
