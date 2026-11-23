DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- One outcome: log a received RFP (SCR-23) and assign the accountable PM (SCR-24) through live API 1.22.0. Both screens are already built (F-36, F-49), so this is wiring, not new design.
- Sized as one PR: two forms, three reads and two writes, all in the received-bids family. If the builder finds the evidence picker or the work-id lookup spreads beyond that, split SCR-24 into its own PR.
- Merge order in lane C: F-85 first (shared evidence picker, needed because live assignment requires an integer `evidence` id), then F-86 (also edits src/features/start-work), then F-88 on top. Builds run one at a time in the lane worktree.
- The live contract forces three visible changes from the approved design: proof and reason become required, the Note field has no home, and the success words lack the PM's name or next steps. The client must see these, hence PRODUCT-ACCEPTANCE required.
- I did not re-verify the architecture approval status or run `design.py check` in this pass. The lane coordinator's runbook (LANES.md) and the built-screen status are my basis. The spec writer should confirm both before specifying.

## Scope
Task FE-CONNECT-1. Binding, per delivery/connect/screens-c-rfp-planning-reports.md sections SCR-23 and SCR-24 and rules DC-1 to DC-5.

SCR-23, Log a received RFP (Start work drawer, line `rfp_intake`):
- Client picker reads `GET /received-bids/organisations` (`items[{id,organisation}]`). The chosen id is sent as `authority`.
- Submit with multipart `POST /received-bids`: `authority`, `start_key` (uuid, reuse as the idempotency key), `reference`, `received_at`, `deadline_status` (unknown/stated/not_stated), `deadline_at`, `prospect_name`, `submission_method` (email/portal/by_hand/not_stated), `submission_target`, `context_attested`, `document` (the file travels in this call), `definition`.
- Confirm by reading `GET /received-bids/{case_id}/receipts/{receipt_id}`.
- Do not use `GET /lines` or the base64 evidence upload for this line.
- Best reading for open questions, flagged and not invented:
  - C-7: find the new item in `GET /work?queue=unassigned` by `case_id`.
  - C-9: `prospect_name` is free text.
  - C-10: hide or remove the Note field if it has no stored field.
  - C-11: show whatever status and `code` the API returns on a repeat `reference`.
  - C-8: do not invent labels for `definition` or `context_attested`. Use the contract's own wording and flag it.

SCR-24, Assign the accountable PM (drawer over the Unassigned list):
- List: `GET /received-bids/assignments`, or `GET /work?queue=unassigned`, keyed by `case_id`.
- Drawer: `GET /received-bids/{case_id}/assignment` gives `nominees`, `roles`, `proofs`, any existing `assignment` and `setup_required`.
- Submit with `POST /received-bids/{case_id}/assignment` {intake (int), revision, candidate (int), role, evidence (int), reason}. Show "assigned" only after a re-read, because no work state comes back.
- Show a plain `setup_required` state when no one is configured to assign.
- Proof is selected from `proofs[]` through the F-85 shared evidence picker. Reason takes the place of the optional Note and is required (C-12).
- Do not show the "what happens next" lines or the nominee's role, since the API does not serve them (C-13). Do not invent them.

Out of scope: any other screen, backend changes, new roles or approvers, and answering the C-2 file-to-evidence-id question. Sign-in, SCR-25 onward and SCR-16 are not part of this feature.

## Risk
Medium: two cross-layer contract changes (multipart upload, integer ids keyed by `case_id`) and a shared form component (`AssignForm.tsx`) used by other workspace lines. Naming the accountable PM is an identity and responsibility decision, but the backend enforces access and the frontend chooses no one. Product-decision surface: making proof and reason mandatory and dropping the Note change a client-approved flow, so the client must accept the wording. No data migration, payments or security-boundary change on the frontend side.
