VERDICT: PASS
COMMIT: d5046515521bca99b4b7de220c4d524838cfff1f
REVIEWER: reviewer-technical
AUTHORITY: delivery technical review

## Summary
- The frame changes are small, general and contained. F-17 single-section `items` steps keep unticked defaults, and the F-21/F-22 steps are unaffected. A non-`task_id` step is unchanged.
- The `task_id` lock closes the INV-RESEND gap (no `href`, `aria-disabled`, no handler), and a forced click sends nothing.
- Proposal keys (`items_default`, `links`) live only in fixtures and `proposals.ts`. They are validated on their own and stripped in `mock-contract.test.ts`. Their presence outside W-23xx is asserted absent. Existing fixtures are untouched (only F-24's `me.*.json` changed, from the merge).
- The mock server merge keeps every operation: `E-DOCUMENT`, `...ASSISTANT_OPERATIONS`, `...START_OPERATIONS`, `...CLIENT_OPERATIONS`. The D-2304 v1 guard returns 501 for any other document.
- The builder's open questions are judged below. None blocks.

## Judgements on the builder's open questions
- Changed F-17 assertion (`workspace-step.test.tsx:168`): accepted. Spec AC 10 requires `item_ids: [<that item>]` for `edit_item` and `remove_item`. Without an id the backend cannot tell which row was pressed. The new assertion is stricter on the id and still checks the step. This is a spec-driven contract change to an item step, not a loosening. It is flagged in build.md, as it should be.
- Confirm set read at submit (`Workspace.tsx` `liveIds`): accepted. A 409 keeps the form open and re-applies defaults to the reloaded set, so a press-time set would send rows the PM no longer sees. Reading at submit matches "exactly the set the PM saw". Unticking everything while the form is open sends nothing, which is correct.
- No `version` byline on the drafted fixture: accepted. It is a fixture choice, since the panel head already carries "Minutes v1 · client version". It is a data field, not frame logic.
- Extra `edit_decision` step: accepted. A decision's Edit form has `text` only and an action's has `text/owner/due`. Per-step descriptors force a second step, and it is fixture-only.

## Findings
- TECH-1-1 | non-blocking | frontend/src/features/workspace/Workspace.tsx:200 | Item-scope steps now send `item_ids` for every line, not only minutes (F-17 `accept_answer`, F-21/F-22 item steps). The contract allows it and the checks pass, but the backend handler for each line must accept or ignore it. | Add one line to build.md or the backend handoff: "item-scope steps send `item_ids: [id]`".
- TECH-1-2 | non-blocking | frontend/mock/fixtures/work/W-2301.json (edit_item / edit_decision) | Edit forms do not prefill the row's current text, because item-scope descriptors are per step. A PM editing a decision must retype it, and `text` is required. This is the builder's own note. | Record it as a backend ask: a per-item `value` on the descriptor, or a per-item step. Do not change the frame in this PR.
- TECH-1-3 | non-blocking | frontend/tests/mock-contract.test.ts:99 | `minutesProposalsStripped` strips `links` and `items_default` from every E-WORK-ITEM fixture, not only W-23xx. The "exist on their own" test limits where the keys occur and checks that they live only in W-23xx, which is acceptable. A malformed `items_default` in an older fixture would still be caught by `toBe('checked')`. | None needed. Keep the guard test.
- TECH-1-4 | non-blocking | delivery/features/F-23/round-1/build.md | The phone boards were not re-scored after the F-24 phone-bar change (the builder says so). Desktop default visual 69.7 is under the D-83 floor and needs the design engineer. This is the UI and fidelity lane, not technical. | Leave it to the UI review and the coordinator. Re-score the phone boards once after merge if the UI reviewer asks.

## Verified
- Frame changes do not weaken F-17/F-21/F-22. `items_default` is absent in those fixtures, so boxes start unticked as before. The cross-section control only applies when an `items` step targets more than one section. The `choice` default applies only when `value` is one of the options, so other lines are unchanged. Links render only when `links[]` is supplied.
- Locked decision links: `Steps.tsx` `off` branch renders `aria-disabled`, no `href`, no `onClick`. `off` comes from the existing flow lock (in flight, `awaitingReconcile`, failed refresh).
- Links / E-DOCUMENT: one GET on press, 403/404 give a neutral sentence with no title, other failures retry the read only, 401 goes to `onAccessLost`, and `body_url` is a link only through `isAppPath`. No template wording is added by the frame (the "Test template" tag comes from `test_template`).
- Scope: no change to `src/api`, `architecture`, `design` or `apps`. No "accept all" or "auto-confirm" under `features/workspace`. No `/me` read added.
