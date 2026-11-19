VERDICT: PASS
REVIEWER: reviewer-security
COMMIT: 264b349260dbbd734eaadcb5228781f83cccccb0
AUTHORITY: delivery security review

## Summary
Reviewed base be04d072..264b349 (AssignPmDrawer, proposals.ts, the lifted AssignForm and useWorkspaceAssign, the My work changes, and the mock). Every point in the brief holds. No blocking finding. Static read only; no suite run, no server started.

- Assign control: the form is drawn only when the item read carries `assign`. With none, the page goes to `/work/<id>` (unless the person has already pressed Assign). With `assign` but no candidates there is a message and no control.
- Candidates: only `assign.candidates`. Nothing is chosen ahead of the person. A re-read that drops the chosen person clears the choice and says so. Roles are only `assign.roles` or `assign.role`. Nothing reads `/me` or the persona. `grep pmo_lead src` finds no match.
- `pmo_lead`: appears only under `frontend/mock` (server, work-list, fixtures) and tests.
- Proof: the upload uses the item's own `case_id` and `case_revision`. The write is blocked unless every file is `uploaded`. The mock rejects an `evidence_id` not issued on the item's case with 422, and a stale `case_revision` with 409. The real backend must enforce the same binding (see Notes).
- CSRF and one write per press: the mock checks the CSRF token before the item and the body. The `writing` ref guard and `proof.uploading` stop a second send. No resend after a 5xx or a lost reply: the page re-reads first. Success words come only after the item and the list are re-read.
- 401/403/404: 401 shows the signed-out state with `next` set to this panel. 403 and 404 show the same fixed "You can't open this item." The heading is drawn only when `lost` is unset, so no client or RFP name shows.
- Plain text: all returned text (names, hints, `next.summary`, `next.agent`, client, reference) is rendered as React text. No `dangerouslySetInnerHTML` in `src/features/rfp`.
- Panel URL: `assign` is accepted only on the unassigned queue and only if it matches `^W-\d+$`. The panel never trusts the id. It reads the item through E-WORK-ITEM, so an item the person can't see gets the not-open view. The `assign` key is stripped from the list request, so it can't change the list query.

## Findings
None blocking.

## Notes
SEC-N1 (non-blocking, backend handoff): `acting_role`, `evidence_id` and `case_revision` are proposals (G-24-1, G-24-2), enforced only in the mock. The real backend must check that `acting_role` is a role the caller actually holds, that the `evidence_id` belongs to this work item's case and was uploaded by this caller, and the stale `case_revision`. It must not trust the client's `assign` block. Record this in the backend handoff.
SEC-N2 (non-blocking): the mock upload grant for `assign.evidence_kind` is "any item with that field". It is mock-only and says nothing about real authorization.
