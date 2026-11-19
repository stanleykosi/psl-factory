VERDICT: PASS
REVIEWER: reviewer-technical
COMMIT: af1d1c8d3629b577c4baeebb4eae025c6a511397
AUTHORITY: delivery technical review

## Summary
- LED-0052 works as the spec asks, and the shared-code changes are confined to the ledger line. Fixtures, mock tests, component tests and e2e cover AC 1 to 25. No amount appears, no `/me` or `prepared_by` rule exists, and no board string is in `src`.
- The stale-409 change is the same as in F-35 971bf73a and F-39 45ae7b66. InlineDecide merges cleanly with both branches. Workspace.tsx conflicts with both, and the conflicts are mechanical (TECH-1-1).
- "Approved" appears only after the re-read confirms it. This applies on the ledger line only (`LEDGER_LINE` gate, a wrapper around the ledger line's `onDecided`), so the income line keeps F-33's behaviour.
- The station and fact-label styling is scoped to `.ws[data-line="ledger_sources"]` and uses tokens only. The F-47 landing change is one line, and the landing assertions moved with it.
- There are no blocking findings. The non-blocking findings cover merge guidance, one fallback string written in page code, the station status word being hidden on screen, and the mock's upload grant.

## Findings
- TECH-1-1 | non-blocking | medium | integration | Merge-conflict risk with F-35 and F-39. `git merge-tree` of 4dba97ab against `fe-leadership-report-drafting-review-tuesday` (eefaf6c5) conflicts in four places in `frontend/src/features/workspace/Workspace.tsx`: the labels import, the `LEDGER_LINE`/`REPORT_LINE` constants, the `decidedNow`/`staleShown` block (:233-241) and the `<InlineDecide …>` line (:690). It also conflicts in the allowlists in `tests/income-schedule-mock.test.ts` and `tests/mock-contract.test.ts`. Against `fe-emergency-escalation-escalate-or-not` (45ae7b66) it also conflicts in `WorkItemOverview.tsx` (the exceptions-button condition, :719) and `delivery/BACKEND-HANDOFF.md`. InlineDecide.tsx auto-merges with both, because the hunks are byte-identical. The guidance under Pending in build.md ("keep the general hunk and drop the LEDGER_LINE gate") is incomplete. When resolving, drop the gate on `staleShown` only. Keep `notMovedOn`/`decidedLabel`/`decidedShown` and the ledger `onDecided={… setDecided({ ...notice, taskId })}` wrapper, or AC 9 regresses (coordinator decision 1). Then keep each side's lines in the allowlists and line constants.
- TECH-1-2 | non-blocking | low | frontend | `Workspace.tsx:240` composes the fallback `'This decision'` inline, as `DECIDE_TEXT.notConfirmed(decidedLabel ?? 'This decision')`. Every other frontend sentence lives in `DECIDE_TEXT`/`WS_TEXT`. Expected: put the fallback in `DECIDE_TEXT`, or reuse the label the InlineDecide notice already carries. Fixtures always send `decision.version.label`, so the fallback cannot be reached today.
- TECH-1-3 | non-blocking | low | frontend | `workspace.css:295` hides each desktop station's status word visually and keeps it for screen readers. A sighted user then tells done, current and to-do stations apart only by fill and border (stopped is dashed). The header status tag still gives the state in text, and the design engineer is to review this styling (build.md Pending). Raised for the UX and UI reviewers against AC 20 ("status words in text, not colour only"). This finding is not technical.
- TECH-1-4 | non-blocking | low | integration | The mock's step-evidence upload grant (F-31, `mock/response.mjs:116-133`) does not exclude a step that has a `disabled_reason`. On the mock, the W-4210 capturer can still upload to C-LED-0052. The spec's seam asked for that exclusion. The page sends nothing on W-4210 (tested), and the gap is recorded in BACKEND-HANDOFF, so the real guard is the backend's. The fix belongs to the F-31 seam owner, not this PR (`response.mjs` stays unchanged here, per AC 23).

## Verified
- Contract: the upload goes to `/api/v1/cases/${item.case_id}/evidence` (C-LED-0052) with `kind: ledger_observation` and `case_revision` 4, and it is schema-valid (`tests/ledger-source.test.tsx:419-426`; the mock test refuses a wrong kind, persona none and a stale revision). The step sends exactly five keys. The decide is `{verdict, expected_revision}`, with a trimmed note on reject. Fixtures validate against E-WORK-ITEM once the overlay is stripped (`mock-contract.test.ts` F-45 block, 13 items + 7 sidecars).
- No amounts and no computing: the AC 2 diff grep (`parseFloat|Number(|.reduce(|compactAmount`) and the AC 7 grep (`useMe|/me|is_you|prepared_by`) over the `frontend/src` diff return nothing. The AC 1 board-string grep on `frontend/src` returns nothing.
- Authority: buttons render only through InlineDecide's `task.you_can_act && claim`. No line-specific rule hides or shows controls. Holds (W-4205, W-4209) draw no step or task, and WorkItemOverview drops "See all exceptions" for `ledger_sources` only.
- Stale-409: the InlineDecide hunk is identical to 971bf73a and 45ae7b66. Other lines get only an unused `onStale` callback (their `staleShown` is gated off), so they see no change. InlineDecide is used only in Workspace.tsx.
- "Approved only after the re-read confirms": `notMovedOn` is true only for a settled notice on `ledger_sources` whose task is still offered in the re-read. The verified and rejected sidecars send no steps, so their real outcome words still show. The income line passes the memoized `onDecided` unchanged (income-schedule tests green per checks.md).
- Styling: every new CSS rule is prefixed `.ws[data-line="ledger_sources"]`, and `--space-10px` and `--text-hint-size` exist in `tokens.css`. `SCHEDULE_LINES` gains only `ledger_sources`.
- F-47 landing: `start-work.mjs` `WORK_IDS.ledger_sources` changes to W-4201, and only the W-4402→W-4201 landing expectations change in the three F-47 test files, so no test was weakened. W-4402 stays because `start-work-proof-mock.test.ts:127-130` still reads it.
- Gate: checks.md PASS at 4dba97ab. No protected or shared read-only path changed, apart from the allowed F-47 repoint.

## Notes
- The ledger `onDecided` and the `onStale` callback are inline lambdas, so InlineDecide's effect re-runs on every render. The `handled` ref guards it, which makes this harmless, and it is the same pattern as F-35.

## Impact assessment (re-pin to af1d1c8d, coordinator, 19 Nov, D-123)
- 4dba97ab → 777f2668: Option B (D-125). The re-check sentence is sent as workspace.next. Fixture, test and handoff changes only; verified boards 87 / 84.4.
- 777f2668 → af1d1c8d: merges dlv-00 (F-34, F-35, F-36, F-39, F-43), including the shared stale fix. Following TECH-1-1, only the ledger `staleShown` gate was dropped; `notMovedOn` (AC 9) and the ledger `onDecided` wrapper were kept. Checked against dlv-00: every Workspace/labels change is scoped to `ledger_sources`. The line joins the schedule set, as in round 1.
- Evidence (round-2/merge-checks.log): tsc and eslint clean; coordinator re-run checks.sh exit 0, 3028/3028; e2e 175/175, including the ledger two-reviewer stale test.
- Verdicts carry forward.
