DECISION: READY
RISK: high
SURFACES: ui, api, security, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-45 is part 1 of FE-FIN-LEDGER: **a captured ledger source becomes a recorded reference.** Chidi checks the file. A second Finance person looks the entry up in QuickBooks and records what they found, with proof. An independent reviewer then approves or rejects it in place, and the item is verified only when the re-read says so. That is 8 of the 12 boards (investigating, observe, review and verified, each on desktop and phone), within D-64. It is one outcome and one PR, and **no part 1 board shows an amount**.
- The only reason this is NOT-READY is the **F-33 dependency**. The review board draws the Decide panel in the page. F-45 reuses F-33's `features/workspace/InlineDecide.tsx`, `proposals.ts` `stepVerdict`, the `steps[].verdict` overlay with its `mock-contract` strip, and the "reviewer not set" hold fixture (D-113). None of these is on dlv-00 yet: they are on branch `fe-fin-schedules-income-detail-review`, head d20fd9b2, not merged. The spec can be written now against d20fd9b2. The build waits for F-33 to merge, and if F-33 changes in its last round the spec is re-checked. Once F-33 merges this becomes READY with no other change. This is the same situation as F-42; F-34 and F-40 were rated the same way for F-32.
- The other gates are met:
  - FE-FIN-LEDGER has `gate_ids: []` and "Unresolved gates: none" (architecture/packages/v7/delivery.md:2804-2833).
  - Its architecture dependency, FE-WORKSPACE-FRAME (F-17), is merged.
  - SCR-58 is in the 13 Nov client approval (design/review.json:66), and the D-89 "+ Start" exception changes only the frame.
  - D-LINE-WORKSPACE (`proposed`) counts only under the recorded exception (architecture/sources/decisions-2026-11-15.md (g), (i)): contract mock only, nothing released.
  - D-RETURN (open) does not touch part 1, because ledger review is approve or reject only, with no Return.
  - The milestone M-7 gates are not task gates. D-RECEIPT-ALLOCATION and D-DECISION-VARIANTS do not apply to any part 1 board.
- All three ledger policy values are NOT SET (frontend/mock/fixtures/setup/finance.desktop.json:343-379): `finance.ledger_sources.verification`, `.conflict` and `.reviewer`. So every fixture is marked as sample data, an unset reviewer is the backend's `setup_needed` hold with no control, and the page names no reviewer and no rule.
- **Relation to F-47 part 1:** F-47 builds the SCR-04 "Record source" drawer (Key, Proof, Continues), which lands on `/work/<work_id>`. That landing is this page's investigating state. Neither feature blocks the other. Whichever merges second may point the start's mock `work_id` at W-4201 and give both features the same back-office case id. The "refused as a duplicate" landing (G-58-1) and "Continues" on a correction belong to part 2, and they touch F-47's start contract. I did not run `design.py check`, because this role has no shell; the spec writer runs it first.

## Scope
**Outcome (one):** a Finance person opens LED-0052 "QuickBooks journal JE-7741 · October" and sees what Chidi read: the provider, the reference, the treatment and the agent steps with their sources. The observer records what they found in QuickBooks (Found, Not found, Unknown or More than one) with a proof file, and the re-read shows the next station. If the backend holds the item after an Unknown or More than one answer, the page shows that hold. An independent reviewer then approves or rejects the reference in the "Decide · <required_role>" panel. The item reads verified only from the re-read `state`, with its stated negatives. Contract mock only.

**Boards (8, part 1)**, all `design/canvas/finance/project/SCR-58-{desktop,mobile}-`:
- `investigating`: "CHIDI INVESTIGATING", the 5 stations, "Source" facts (QUICKBOOKS, JE-7741, ACCRUAL REVERSAL), the agent card (4 steps, sources "QB_EXPORT_JE7741.PDF", "28 OCT · 2026-10", "QUICKBOOKS · REALM PSL-NG", "Started 15:12") and "Ask Chidi".
- `observe`: "RECORD WHAT YOU FOUND". The step `record_observation` has a required 4-option `choice` with nothing pre-selected, an `evidence` field "Proof" and the step's `consequence`. It also shows "Recording what you saw isn't an approval…" as returned text.
- `review`: "AWAITING FINANCE DECISION". The "Evidence" facts are Captured by, Observed by "CHUKA EZE · FOUND" and Lineage "NEW · NO PREDECESSOR". The Decide panel offers "Approve reference" and "Reject" (verdicts approve and reject only), with the basis sentence and the "approve or reject only" line as returned.
- `verified`: "VERIFIED". The "Recorded" facts are Posting performed NO, Authenticity certified NO, Completeness certified NO and Reference recorded "YES · 14 NOV", plus the re-check sentence (G-58-5), all as returned.

**Boards left for part 2 (4):** `SCR-58-{desktop,mobile}-duplicate` and `-rejected`. Part 2 waits on these:
- G-58-1 (blocking question): which `state` a refused capture takes, and whether E-WORK-START returns its `work_id` so the person lands on it. The refusal rule is `finance.ledger_sources.conflict`, which is NOT SET.
- G-58-2 (blocking): the `continues` record field on "Correct", which extends the same lineage.
- G-C-3: the "Open LED-0049" link.
- G-C-6: whether a correction returns a `created_work_id`.

The duplicate board's compare table carries two amounts (₦2,400,000.00 and ₦2,040,000.00). The rules for it are:
- The backend decides that a capture is a duplicate, and the backend supplies both amounts as `money` cells.
- The browser never compares, subtracts or matches them.

After a Reject in part 1, the re-read sidecar is shown read-only, with no "Correct" step.

**Task and endpoints:** FE-FIN-LEDGER (R-FINANCE), acceptance A-WORKSPACE (frontend half). All of these are typed in frontend/src/api/schema.d.ts:
- E-WORK-ITEM `GET /api/v1/work/{work_id}` (:54), proposed `line_key` `ledger_sources`, `screen` "SCR-58".
- E-WORK-STEP `POST /api/v1/work/{work_id}/steps` (:715), with `evidence_ids` (:2466).
- E-EVIDENCE-UPLOAD `POST /api/v1/cases/{case_id}/evidence` (:159).
- E-TASK-CLAIM (:96) and E-TASK-DECIDE (:117), verdict approve or reject (:2136), with a note required for reject.

**Reuse, not rebuild:**
- The F-17 frame with its `Sections`, `AgentCard` and `assistant` link.
- F-17's `StepForm`, which already draws `evidence` through `EvidenceField`/`ProofField` and `useEvidenceUpload` (StepForm.tsx:123-148), plus `useWorkspaceStep`.
- F-33's `InlineDecide` over F-16 `useDecision`.
- `components/format.ts`.

**Mock seam:**
- `mock/response.mjs` `upload` refuses a workspace step's proof today. F-34's spec proposes the same additive fix: accept a `kind` named by an `evidence` field of a served item's step. Whichever feature builds first owns that change, and the other reuses it. Integration owner: the coordinator.
- Fixtures use W-4201 upward and T-42xx. There is no month-end row to repoint (G-58-6).
- The observer and the capturer are shown only as the backend's names. No persona is added, and the signed-in name follows the F-33 precedent.

**Fixtures the spec must add beyond the 4 boards:**
- "Who reviews ledger sources" not set: `setup_needed`, no task, no reviewer named.
- An observation answered Unknown, which the backend returns as held at station 3.
- A reviewer who captured or observed the source: `you_can_act: false` with the returned reason (G-58-4 asks for a reason code; until then `disabled_reason` or the existing code, and no rule in the page).
- The approve and reject sidecars, drawn only from the re-read.

**Binding for the spec:**
1. **Money.** Any amount is the backend's `money.amount` decimal string, formatted by the shared formatter. Unknown is shown as "Unknown", never 0. The page computes no total, count or difference, and the diff contains no `parseFloat`, `Number(`, `reduce(` or `compactAmount`.
2. **Duplicates.** Only the backend flags a duplicate. The page never compares references, files or amounts to suggest one.
3. **Unset policy is a hold.** The page shows the backend's hold and offers no control and no invented reviewer or rule.
4. **Authority.** Controls come only from `you_can_act` and the steps that are sent. The page has no role, `/me` or `prepared_by` rule, so separation of the capturer, observer and reviewer is the backend's job. 403 and 404 look the same. Writes send CSRF and `expected_revision`, and the step carries an `idempotency_key`. After an uncertain failure the page re-reads first and never resends automatically.
5. **Agent work is not a decision.** "Verified", "Posting performed NO" and "Authenticity certified NO" appear only from data. No QuickBooks call is made or implied (gaps-f-finance-workspaces.md:169).
6. **Phone and fidelity.** The phone shows the desktop data, in one column:
   - The phone observe board drops the proof field and says "Many" for "More than one"; the phone review board drops facts.
   - These differences are listed for the design engineer, following the F-33 precedent (D-111).
   - The Note and the step form open in the Drawer, and tap targets are 44px (D-92c).
   - One fidelity run per round covers the 8 boards: 100% coverage after exceptions, and a visual score of at least 90 or a signed D-83 waiver.
   - Axe runs at 390 and 1440. Tokens and components only. The builder is Opus (high risk).

**Out:**
- Part 2 (above).
- Any QuickBooks integration.
- Repointing month-end (G-58-6).
- The re-check or reopen trigger (G-58-5, backend).
- Setup editing (SCR-13).
- The SCR-04 drawer (F-47).
- Backend, OpenAPI, `schema.d.ts` regeneration, `architecture/**`, `src/shell/**`.

## Risk
High. This is a Finance approval that records a ledger source as a reference, which is an authority-bearing write. The proof upload is append-only on a back-office case, so it is hard to undo. Three separate people (the capturer, the observer and the reviewer) must be kept apart by the backend. A wrong control would make a source look approved, or a hold look cleared, without the human decision. The work stays contained: on the F-17 frame with F-33's inline Decide, on the mock, and nothing is posted.

The SURFACES are these:
- ui: 8 boards.
- api: E-WORK-ITEM, E-WORK-STEP, E-EVIDENCE-UPLOAD, E-TASK-CLAIM/DECIDE.
- security: the approval write and the upload grant.
- contract-change: the `ledger_sources` line, `steps[].verdict` and the mock upload grant.
- product-decision: the three ledger policy values, which are NOT SET.

PRODUCT-ACCEPTANCE is required, because this is a new Finance flow the client has not seen working.

## Questions
None for the client in part 1. These go to the backend developer and Finance. They hold part 2 or the real transition, not this build:
1. Does the backend enforce three separate people (capture, observation, review) for every ledger source, and with which `cannot_act_reason` (G-58-4)?
2. What state follows an Unknown or More than one observation, and who is told (G-58-3)? Which station does "Verification rules" hold when it is unset?
3. Part 2: what `state` does a refused duplicate take, and does E-WORK-START return its `work_id` (G-58-1)? Does `continues` go on the correction (G-58-2)?

## Re-check 19 Nov
**Verdict changed: NOT-READY to READY.** The F-33 dependency is cleared. Risk (high) and surfaces unchanged. The Summary bullet above that says "NOT-READY" is the earlier analysis, kept for the record.

What changed:
- F-33 (PR #64) is merged into dlv-00. `frontend/src/features/workspace/InlineDecide.tsx` exists, and `stepVerdict` is in `features/workspace/proposals.ts` and used by `Workspace.tsx` and `InlineDecide.tsx`.
- F-33's last approved head was d20fd9b2 (round 3, ESCALATE). The spec was written against that head.

Spec re-check needed (the builder verifies before coding):
- Compare the merged `InlineDecide.tsx`, `proposals.ts` `stepVerdict`, the `steps[].verdict` overlay, the `mock-contract` strip and the "reviewer not set" fixture (W-2706) with what `spec.md` quotes from d20fd9b2. Fix any drift in the spec.
- Confirm F-33's two `line_key === 'income_schedules'` checks in `WorkItemView.tsx` / `WorkItemOverview.tsx` (around :698-728) are on dlv-00, and add the `ledger_sources` case beside them; do not duplicate.
- F-33's D-83 waivers and PMO acceptance were pending at ESCALATE. Treat merged behaviour as the baseline; if the merge changed copy, re-read the SCR-54 conflicts list.
- Fixture ids: W-4201 upward, T-42xx. Check for collisions with merged F-34/F-42/F-47 fixtures. F-34's mock upload `kind` fix may already be in: reuse it, do not redo it.
- Run `design.py check` first.

Follow-up risk (not blocking): the shared InlineDecide has a stale-409 gap, being fixed in F-39 round 4. F-45 inherits it until that lands. The builder must not patch InlineDecide in this PR. After F-39 merges, F-45 re-verifies the stale-409 path (409 on approve/reject reloads and never resubmits) in its own tests. Note this in build.md.
