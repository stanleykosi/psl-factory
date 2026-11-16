VERDICT: PASS
COMMIT: 0d6dabf7e5d6f6d97e9283ca5da8e22e23016772
REVIEWER: reviewer-technical
AUTHORITY: delivery technical review

## Summary
- The round-2 diff (d5046515..0d6dabf7) is small and general. Fixtures-only proposal `items[].values` is read in one typed reader and stripped in the contract test after its shape is checked.
- The task-card rule is narrow: it hides only a task whose id a workspace step's `task_id` already links to. Other tasks still draw.
- SEC-1-1 is fixed in the right place (`ticked` and `cross` ignore restricted sections).
- One non-blocking test gap (TECH-2-1). No blocking findings.

## Findings
- TECH-2-1 | non-blocking | frontend/tests/mock-contract.test.ts:~76-110 | `minutesProposalsStripped` strips `values` from every E-WORK-ITEM fixture, but the "proposal keys exist on their own" guard still covers only `links` and `items_default`. A stray `items[].values` in a pre-F-23 fixture would be stripped silently. | Add `values` to that guard so it appears only in W-23xx fixtures.
- TECH-2-2 | non-blocking | frontend/src/features/work-item/WorkItemOverview.tsx:719 | The task card is hidden for every line whose workspace step links the task, not only minutes. The builder reports that no F-17/F-21/F-22 board has such a pair, and the suites pass. It would hide the card's status text for any future line that has both. | Leave as is. Note it in the frame backlog.

## Verified
- TECH-1-1 | verified | Carried in round-2 build.md "Left": item-scope steps send `item_ids: [id]` on every line, and the backend must accept or ignore it. This is documented. It stays a backend handoff item and is non-blocking.
- TECH-1-2 | verified | `itemValues` (proposals.ts) feeds `StepForm` `initial`. `initial` wins over the descriptor `value`. Only text, long text, date and record fields are prefilled, and only with correctly typed values. Restricted fields are skipped. A missing `values` gives an empty object, so no derivation in the frame. A cleared field is left out, which the spec allows.
- TECH-1-3 | verified | The guard test remains and still limits `links` and `items_default` to W-23xx. See TECH-2-1 for `values`.
- TECH-1-4 | verified | Phone re-score done in round 2 (phone 74.2, 82, 82.5, 78.7). Desktop default is 69.2, under the D-83 floor, and is for the design engineer, not technical.
- Task-card rule | verified | `linked` is built from `item.workspace.steps[].task_id`. `shownTasks` filters by id and both the `TaskPanels` and `task_note` use it. The decision link remains on the work page and still follows the page lock.
- SEC-1-1 / cross-section | verified | `cross` and `ticked` both exclude `section.restricted`, so a restricted section adds nothing to the ticks, the count or the confirm set.
- "Done:" wording | verified | The `/^done\b/i` check only avoids a doubled prefix. The fallback `STEP_TEXT.done(label)` is unchanged.
- Scope | verified | No change to `src/api`, `architecture`, `design` or `apps`. No new `/me` read.
