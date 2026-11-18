VERDICT: PASS
REVIEWER: reviewer-ux
COMMIT: 4f53c9f15d69264d048e8ea482fb80475d936481
AUTHORITY: delivery ux review

## Summary
- Verification of 5e14a6ad..4f53c9f15d69264d048e8ea482fb80475d936481: three files (AssignPmDrawer.tsx, rfp-assign.test.tsx, e2e rfp-assign.spec.ts). Shared AssignForm untouched, so F-30 and F-31 422 behaviour is unchanged. Vitest on the 3 assign test files: 71 passed.
- Named-field 422s now show the page's words under the field, a linked summary, focus on the first field, entries kept; duplicate 'Nothing was changed.' removed.

## Findings
None.

## Verified
- UX-1-1 | verified | 422 on person_id/note/acting_role/evidence_id shows the page's own sentences, with summary and focus; tests and e2e (axe clean) assert it.
- QA-2-1 | verified | read the fix; 422 on acting_role or evidence_id shows the page's words under the field, a linked summary, focus on the first field, entries kept, and no "Check these fields" text. Component 422 tests (7 incl. the 5 new) pass; e2e 422 case passes with axe clean at 1440. QA still to re-check in the browser.
