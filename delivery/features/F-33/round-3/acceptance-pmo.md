VERDICT: CHANGES
COMMIT: d20fd9b2ccee7be267936cc2758358989ecdedbb
REVIEWER: pmo-acceptance
AUTHORITY: delivery PMO acceptance

## Summary
- Delivery is complete except for one missing handoff line. The "Added during F-33" section of BACKEND-HANDOFF.md does not say that E-TASK-DECIDE has no idempotency key (PMO-3-1). The approval is a write over money, and the backend developer reads this section, not the review files. This is a one-line doc edit, with no code change.
- Scope, task coverage, money criteria, the policy hold, part-2 boundaries and review verdicts are all in order. Technical, security, UX, UI and QA all pass on d20fd9b2. The gate passed (checks.md, attempt 1).
- This PASS is delivery acceptance only. It is not product acceptance, merge or release. All results are mock results: there is no backend, no real Finance policy and no live integration.
- Human items for the design engineer are listed at the end of Verified. They are not PMO defects. They include the QA-3-1 wording question.

## Findings
- PMO-3-1 | blocking | low | frontend | `delivery/BACKEND-HANDOFF.md` section "Added during F-33: income schedules (18 Nov)" (lines 250-264) never says that E-TASK-DECIDE has no `idempotency_key`. Expected: one bullet, as the F-30 section does for assign ("No idempotency key on this operation: the page sends once per press and re-reads before offering a retry"). The bullet should say that approve, return and reject on a money schedule rely only on the `expected_revision` check (409) plus the frontend never resending, and should ask the backend whether to add a key. Actual: the gap appears only in `round-3/build.md` "Open", in `review-security.md:30`, and in `gaps-e-finance-payroll.md:28`, which is about another screen. The F-33 section's decide bullet (line 254) lists the request body and its guards without this gap. Fix: add the bullet. Nothing else needs re-review beyond the usual head change, because the edit touches only a handoff markdown file.

## Verified
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
- I could not re-run `git diff` myself because this role has no shell. I rely on QA's `git diff --stat` and grep results (journeys 2 and 12) and on the technical review.

**Money criteria (QA review-qa.md, journey 2 and journey 4)**
- The W-2702 amount reads "₦12,400,000.00" at 1440 and at 390, with no "₦12.4M".
- Changing the sent amount shows "₦12,400,000.10" for `"12400000.10"`, and a 17-digit amount is shown exactly, so no float is used.
- A real "0.00" is shown as "₦0.00". An unknown amount on W-2707 reads "Unknown", with no "₦0", "0.00" or dash.
- The grep for `parseFloat`, `Number(`, `.reduce(` and `compactAmount` on the diff returns nothing.
- "Verified" appears only from the re-read state:
  - With the decide at 200 and the re-read still in review, the status stays AWAITING FINANCE DECISION.
  - W-2712 (`effect_uncertain`) never reads as approved, returned, rejected or verified, before or after a reload.
  - The page sends one decision POST and never resends.
- The decide body is exactly `{verdict, note?, expected_revision}`, with CSRF. A return or reject without a note sends nothing. The note is trimmed and capped at 2000. The curl checks show the mock refusing an extra key, `revoke`, a missing CSRF token and another session's token.
- "Posted to the ledger NO" and "THESE 38 ROWS ONLY" come from the fixture's facts. W-2704 has no Export or Withdraw button.

**Unset policy keys: handled as a hold, not guessed**
- `finance.income_schedules.reviewer`, `.income_detail` and `.inventory` are NOT SET, and none is in `contracts/policy-slots.json`. The spec records this, and no code supplies a value.
- Every fixture is `sample: true`. W-2706 is the hold:
  - It shows `setup_needed`, "SETUP NEEDED", "Who reviews schedules · NOT SET" and its `next` sentence.
  - It has no Decide panel, no button and zero task POSTs.
  - The words "Schedules reviewer" and any reviewer name are absent from the main content. The only "Ada Okafor" on the page is the signed-in persona in the shell.
- The page has no role or `prepared_by` rule and does not read `/me`. W-2705 (`prepared_by_you`) and W-2708 (`not_your_role`) show the backend's copy with no claim or decide sent.
- The held items are named in build.md "Open" and in the handoff: the reviewer key, the income detail rules, D-RETURN, G-C-1 (verdicts), G-C-3 (Setup link) and G-54-3.

**BACKEND-HANDOFF "Added during F-33"**
- The section exists and is specific on these points: the `verdict` overlay (G-C-1, G-C-2), `you_can_act` as the only source of controls, backend-sent wording, money as decimal strings with `money.display_short` not built, counts as text, the W-2706 hold shape (G-C-3), D-RETURN and the correct-and-resubmit field, decided-task sidecars, the state and view names to confirm, Ask Chidi (G-C-4), and the part-2 list.
- Missing: the E-TASK-DECIDE idempotency key, recorded as PMO-3-1.

**Part 2 and PSL gaps for the backlog**
- Held (duplicate settlement): G-54-1 (per-row inputs) and G-54-2 (what "Justified" requires; the income detail rules are NOT SET). Both are blocking questions for the backend and Finance.
- Export as an adjustment: G-54-5, G-C-6 and the unit factor question.
- Withdrawn: G-54-4 and G-C-1. The verdict `revoke` has no stated effect. The backend must say that revoking after an export flags the adjustment and never deletes it.
- Inventory kind: G-54-6, which needs a board from the design engineer.
- Outside the gap ids but needed by part 2: the "Duplicate check" value that means "not assessed" (INV-UNKNOWN). The gaps file asks this question already.
- The gaps file is `delivery/backend-handoff/gaps-f-finance-workspaces.md:73-93`. The handoff and the spec both keep these out of part 1. PSL, as the business owner of the Income detail rules, has to settle the NOT SET values before any of them can build against real policy.

**Findings and reviews**
- Round-3 verdicts are PASS from technical, security, UX, UI and QA. All are pinned to d20fd9b2.
- Blocking findings from rounds 1 and 2 are VERIFIED: TECH-1-1, TECH-2-1, UI-2-1, UI-2-2 and UI-2-3. The non-blocking TECH-1-2 to 1-5, UX-2-2 and UI-2-5 are also VERIFIED.
- No accepted risk lacks an authority. Open and non-blocking:
  - UX-2-1: the "See all exceptions" button on the hold comes from the shared frame, which draws it for every exception state. The builder left it as is and asks the frame owner to confirm. It is not an F-33 defect, and the hold still has no decide control.
  - UI-2-7: the frame's phone History link measures 42x24. It is not introduced here, and it appears on W-2901 and W-2411. It goes to a frame follow-up.
  - QA-3-1: see the design-engineer list below.
  - Record sync: `feature.json` still shows UI-2-4 and UI-2-6 as OPEN, but `review-ui.md` round 3 lists both as verified (the waivers now name each board's own gaps). The coordinator should sync these states.
- Checks: `checks.md` is GATE: PASS for d20fd9b2 with no protected paths changed. Build.md reports 2320 unit tests and 105 e2e tests. QA reran 173 e2e tests and 544 vitest tests, and ran axe at both widths with 0 violations.

**For the design engineer (human items, not PMO defects)**
- Sign or reject the 8 per-board D-83 visual waivers in `fidelity-exceptions.json`. Visual scores run 73.3 to 88.1, all above the 70 floor, and the exceptions are all marked "builder proposal, pending design engineer". The UI reviewer judged all 8 signable.
  - Items to look at: the AgentCard "step 4 of 4" against the board's "step 3 of 4" (Conflicts 15); the green "Correct and resubmit" primary; the white stopped station; the missing D-RETURN note (Conflicts 6); the extra Reject consequence line; the phone "₦12,400,000.00" against the board's "₦12.4M" (Conflicts 3); and the SAMPLE DATA tag being off in team builds.
- Answer the "Need an answer" items 1 to 8 in the spec, which the recommendations in the build currently settle.
- Decide the QA-3-1 wording question. When the decide answers 200 but the re-read still shows review, the panel says "Schedule v1 is approved" next to AWAITING FINANCE DECISION. The spec allows this wording, and nothing says Verified. The choice is whether to word the notice as "recorded" and not as an outcome whenever the re-read has not moved. QA's pointer is `InlineDecide.tsx` (`confirmed`, `onDecided`).
- Give product acceptance, which is required and pending. It is a Finance approval flow with new wording that the client has not seen working. Merge needs the design engineer's "merge".
- Confirm UX-2-1 (the hold's "See all exceptions" button) with the frame owner.
