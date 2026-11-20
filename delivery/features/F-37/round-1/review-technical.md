VERDICT: PASS
REVIEWER: reviewer-technical
COMMIT: 089037b2cde16d3877db4e4aed27068017c50a35
AUTHORITY: delivery technical review

## Summary
- Contract mock only; the diff touches no generated type, backend, shell or existing fixture. Steps, items and the Record link all come from the response (`steps`, `you_can_act`), nothing from `/me`.
- Request shapes match spec criteria 7 to 10 (accept, accept_selected, edit_accept, write_own with item_ids, inputs and idempotency key). The mock adds the item_ids 422 for rfp_response only.
- Shared edits are mostly gated on `rfp_response` or opt-in props. Three are not, or are wider than needed (TECH-1-1, TECH-1-2, TECH-1-3); none breaks a current test or board.
- Fidelity (criterion 17) is below 90 with unsigned waivers. That is a human sign-off, not a code defect.

## Findings
- TECH-1-1 | non-blocking | medium | builder | `WorkItemOverview.tsx` (`rfpPage`) drops every task panel on desktop for any `rfp_response` item that has `rfp`, not just the team-input task the tab and Record reach. An actionable task of another kind (a decision task) would have no entry point. Expected: hide only tasks with `response.variant === 'team_input'` that the frame links to, as `RfpFrame` already selects them.
- TECH-1-2 | non-blocking | low | builder | `Sections.tsx` changes "Suggested by <agent>" for every line: it now shows whenever a tag label lacks the agent's name, where before any tag hid it. Only W-2002 is affected today and it still hides it, but this is not scoped to rfp_response. Gate it on the line, or note it for the F-30 and F-31 owners.
- TECH-1-3 | non-blocking | low | builder | `StepForm.tsx` choice prefill from `initial` applies to every line that passes `itemValues` (F-23, F-30, F-31). It is correct, but unscoped, and no other line has a test for it. The same goes for `inSide` moving figures and checklist to the side column: it applies to W-2002 and W-2006, and their tests pass.
- TECH-1-4 | non-blocking | low | builder | `RfpFrame.tsx`: when the person has no actionable team-input task (for example W-3404), Team input falls back to `work(target)`, a link to the page you are already on. Draw it as plain text, or leave it as the page did before.
- TECH-1-5 | non-blocking | low | builder | `Workspace.tsx` `sideNote` and the `ws-side` condition repeat `RFP_LINE && !phone` four times. One local `rfpDesktop` would be simpler.

## Verified
- Criteria 1 to 16 and 19 to 22 | verified | read against the diff and tests. Ran `grep` on the diff: no hex, `rgb(` or `hsl(` in CSS, and no `.skip`, `.only` or `fixme` in the new tests. Builder's checks.sh pass and 813 e2e passes taken from the gate and not re-run.
- Holds | verified | Pricing, Submission and Outcome stay plain text; Send for review is disabled and sends nothing; past-bid result and "Your reason helps…" are not built.
- Discard question | verified | opt-in `askBeforeDiscard` (rfp_response only); `closeRef` is cleared on unmount; Escape does not double-close the Drawer.
- Select all | verified | the control exists only for rfp_response and covers the rows on screen. The phone CSS is scoped by `:has(th.ws-selectall)`.
- Note for the second merger (F-38, `RfpFrame.tsx`) | keep `REQUIREMENTS_LINE`, the `requirements`, `current` and `teamTask` props on `Tab`, the `end` slot in the eyebrow, and the `import './rfp.css'`. Keep the Requirements href rule so W-2101 and W-2103 still show plain text, and the Team input link to `/work/W-2103` there. Add Submission's href as one more branch in the same `href` chain. Merge `rfp.css` additions after `.rfp-history`. Do not drop the `.rfp-frame:has(.rfp-history)` title size rule.
