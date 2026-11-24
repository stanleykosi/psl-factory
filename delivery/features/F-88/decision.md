RECOMMENDATION: AUTO_MERGE
COMMIT: 98eb07bbb7c5fe76f5f13423947995eb4942e520
APPROVER: approver

## Summary
- Wires Log RFP (SCR-23) and Assign PM (SCR-24) to live API 1.22.0 in the frontend only: 24 files, with no backend, auth, payment, migration or security change and no contracts file in the diff.
- On 98eb07bb the CI gate, technical, UX, UI, QA, PMO acceptance and product acceptance all PASS and all name this head. There are no open blocking findings.
- The product decisions (proof and reason required, no Note, success wording, tick-boxes) were answered by the design engineer in batches D-182, D-187 and D-198. Product acceptance is delegated under D-184.
- Live proof is partial by the design engineer's own answer ("Mock-only, like F-60"). Only the 403 refusal ran live. The success, replay, duplicate, upload-limit and assign paths are mock-proven, and the PR says so.
- Readiness lists the surfaces contract-change and product-decision, which are on the merge policy's always-human list. The merge-decision script may therefore lower this. I read both as already settled: the frontend adapts to the existing contract, and the human answered the product questions.

## Why
The change stays inside readiness's Scope and the spec's lanes. No Assumption is an open business decision, because each one was answered in a batch. I re-ran assign-pm.test.tsx on this head (22 of 22 pass). QA ran 245 tests across the nine F-88 files and they pass, apart from load timeouts that passed on rerun. The merge delta from 811465d8 conflicted only in a test allow-list.

## Acceptance criteria
1. Spec criteria 1 to 21 (log RFP multipart and start_key replay, file limits, duplicate and 403 handling, Unassigned list, assign drawer with integer ids and re-read, setup_required, signed-out state, v7 paths removed, accessibility, registry use): met on the mock. Evidence is round-2/review-qa.md browser walks at 1440 and 390, the request-log readback, and the F-88 test files. I spot-checked criteria 10 to 15 through assign-pm.test.tsx.
2. Criterion 7 (optional Note): superseded by D-182, which hid the Note and made Reason required. Product acceptance records this.
3. Live success paths: not proven live. The design engineer accepted mock-only.

## For the human
Nothing is needed before merge. After merge, check the two drawers on port 3000. Files: /Users/Hunchoo/psl-factory-main/delivery/features/F-88/round-2/acceptance-product.md and round-2/review-qa.md.
