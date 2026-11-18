VERDICT: PASS
COMMIT: 306728777fda087120513e0a18e5bcc8d2344389
REVIEWER: pmo-acceptance
AUTHORITY: delivery PMO acceptance

## Summary
- PMO-3-1 (the missing E-TASK-DECIDE idempotency-key line in the F-33 handoff section) is fixed at this head. Nothing else blocks, so the verdict is PASS.
- Scope, task coverage, money criteria, the policy hold, part-2 boundaries and review verdicts are in order. Technical, security, UX, UI and QA passed on d20fd9b2. The merge of F-31 and F-32 (head 30672877) leaves F-33's code untouched, and a targeted rerun of 9 files and 275 tests passed.
- The design engineer has signed the waivers and exceptions and given product acceptance (D-117, 19 Nov 2026, `round-3/acceptance-product.md`).
- This PASS is delivery acceptance only. Merge and release keep their own authorities. All results are mock results: there is no backend, no real Finance policy and no live integration.

## Findings
- PMO-3-1 | blocking | low | frontend | `delivery/BACKEND-HANDOFF.md` section "Added during F-33" did not say that E-TASK-DECIDE has no `idempotency_key`. Fixed at 30672877: see Verified.

## Verified
- PMO-3-1 | verified | BACKEND-HANDOFF.md line 279 in the F-33 section ("Added during F-33", line 274) now has "No idempotency key on E-TASK-DECIDE" (security review SEC-1, carried from F-16). It names the body sent and the claim plus `expected_revision` guard, says the backend must return 409 on a second decide at the same revision and must not apply a decision twice, and asks whether to add a key. I checked the text at head 30672877.

**Scope and tasks**
- FE-FIN-SCHEDULES, part 1, is the only task in `feature.json`. The package (`delivery.md:2680-2709`) has `gate_ids: []`, no unresolved gates, and depends only on F-17 (merged).
- The package task status is still "planned". F-33 claims only part 1: 8 of 14 boards. Held, export, withdrawn and the inventory kind are named as part 2 in the spec, build.md and the handoff. The parent claim stops at this slice.
- `operation_ids` is empty in `feature.json`. The endpoints are covered through the spec and the tests:
  - E-WORK-ITEM, E-TASK-CLAIM and E-TASK-DECIDE are exercised by QA journeys 3 to 9.
  - E-WORK-STEP `correct_and_resubmit` is exercised by journey 10, with the same idempotency key on retry.
  - The coordinator may want to record the IDs in `feature.json`. This is bookkeeping and not a defect.
- Nothing outside scope landed.
  - The changed paths are the fixtures W-2701 to W-2712, the workspace feature files, tests, e2e and the handoff.
  - Two shared files were touched. Both are declared and accepted: `Sections.tsx` (the figures `tag` defect fix, build round 1) and `WorkItemOverview.tsx` (gated on `income_schedules`, accepted by the coordinator, TECH-1-5 VERIFIED).
  - QA found no diff under `src/api`, `src/features/decide`, `src/shell`, `mock/server.mjs`, `mock/workspace.mjs`, the response and finance fixtures, or `E-MONTH-END.json`.
  - The mock-seam choice is option (b): W-1603 and the month-end row are unchanged, and the month-end e2e passes.
- I could not re-run `git diff` myself because this role has no shell. I rely on QA's `git diff --stat` and grep results and on the technical review.

**Money criteria (review-qa.md, journeys 2 and 4)**
- The W-2702 amount reads "₦12,400,000.00" at 1440 and at 390, with no "₦12.4M". A sent "12400000.10" shows "₦12,400,000.10", and a 17-digit amount is shown exactly, so no float is used.
- A real "0.00" is shown as "₦0.00". An unknown amount on W-2707 reads "Unknown", with no "₦0", "0.00" or dash.
- The grep for `parseFloat`, `Number(`, `.reduce(` and `compactAmount` on the diff returns nothing.
- "Verified" appears only from the re-read state. With the decide at 200 and the re-read still in review, the status stays AWAITING FINANCE DECISION. W-2712 (`effect_uncertain`) never reads as approved, returned, rejected or verified, before or after a reload. The page sends one decision POST and never resends.
- The decide body is exactly `{verdict, note?, expected_revision}`, with CSRF. A return or reject without a note sends nothing. The note is trimmed and capped at 2000.
- "Posted to the ledger NO" and "THESE 38 ROWS ONLY" come from the fixture's facts. W-2704 has no Export or Withdraw button.

**Unset policy keys: handled as a hold, not guessed**
- `finance.income_schedules.reviewer`, `.income_detail` and `.inventory` are NOT SET, and none is in `contracts/policy-slots.json`. No code supplies a value.
- Every fixture is `sample: true`. W-2706 is the hold: it shows `setup_needed`, "Who reviews schedules · NOT SET" and its `next` sentence, with no Decide panel, no button, zero task POSTs and no reviewer named.
- The page has no role or `prepared_by` rule and does not read `/me`. W-2705 (`prepared_by_you`) and W-2708 (`not_your_role`) show the backend's copy with no claim or decide sent.
- The held items are named in build.md "Open" and in the handoff: the reviewer key, the income detail rules, D-RETURN, G-C-1, G-C-3 and G-54-3.

**Part 2 and PSL gaps for the backlog** (`delivery/backend-handoff/gaps-f-finance-workspaces.md:73-93`)
- Held (duplicate settlement): G-54-1 (per-row inputs) and G-54-2 (what "Justified" requires; the income detail rules are NOT SET). The "Duplicate check" value that means "not assessed" (INV-UNKNOWN) is asked there too.
- Export as an adjustment: G-54-5, G-C-6 and the unit factor question.
- Withdrawn: G-54-4 and G-C-1. The verdict `revoke` has no stated effect. The backend must say that revoking after an export flags the adjustment and never deletes it.
- Inventory kind: G-54-6, which needs a board from the design engineer.
- PSL has to settle the NOT SET Income detail rules before any of this can build against real policy.

**Findings and reviews**
- Round-3 verdicts are PASS from technical, security, UX, UI and QA, all pinned to d20fd9b2. Blocking findings from rounds 1 and 2 (TECH-1-1, TECH-2-1, UI-2-1, UI-2-2, UI-2-3) are VERIFIED, as are TECH-1-2 to 1-5, UX-2-2 and UI-2-5.
- Open and non-blocking, with their routes:
  - UX-2-1: the "See all exceptions" button on the hold comes from the shared frame. The frame owner is to confirm.
  - UI-2-7: the frame's phone History link measures 42x24. It goes to a frame follow-up.
  - QA-3-1: see the human items below.
  - Record sync: `feature.json` still shows UI-2-4 and UI-2-6 as OPEN, but `review-ui.md` round 3 verifies both. The coordinator should sync these states.
- Checks: `checks.md` is GATE: PASS for d20fd9b2 with no protected paths changed. QA reran 173 e2e tests and 544 vitest tests, with axe at both widths showing 0 violations.

**Human items for the design engineer (not PMO defects)**
- Done under D-117 (19 Nov 2026): the 8 per-board D-83 visual waivers and the exceptions in `fidelity-exceptions.json` are signed. The "Need an answer" items 1 to 8 and product acceptance are also done (`round-3/acceptance-product.md`).
- Check that D-117 records an answer on QA-3-1. This file does not claim one. The question is whether a 200 decide with an unmoved re-read should say "recorded" and not "is approved". It is non-blocking, and the spec allows the current wording.
- Still open, with no defect in F-33: UX-2-1 with the frame owner, and merge on the design engineer's "merge".

## Update for head 30672877 (diff b8265cdb..30672877)
- Merge head 30672877 only adds F-31 (response drawer, engagement and planning) and F-32 (orphan-step rule, work links) code around F-33. F-33's inline decide, uncertain handling, income banner and agent card are untouched in the Workspace, proposals and workspace.css diff.
- Targeted vitest (income-schedule, engagement-planning, release-gates, workspace, issue-detail, finance-month-end): 9 files, 275 tests passed.
- The handoff line is present at this head. The verdict is now PASS.
