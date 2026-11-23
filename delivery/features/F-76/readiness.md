DECISION: READY
RISK: medium
SURFACES: ui, api, auth
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-76 is now the read-only slice of SCR-21 Staff accounts (task FE-SETUP-ROLES): the staff list and one person's access. It is the F-76a slice from readiness-r1.md.
- D-182 (design engineer, B13) approves "read-only list now". Invite, deactivate, restore and role changes wait for PSL's D-ADMIN-AUTHORITY, which is still open. They are out of scope, so that decision does not block this slice.
- D-182's "hide, accept all recs" rule records the design exceptions r1 asked for. A-53 is answered: build on the server's answer.
- I did not re-check the code or the design files this round. I relied on the coordinator's answers and the r1 findings.

## Scope
Binding for the spec writer.
- **Outcome:** a person the server allows sees the staff list, and can open one person to see their access by workspace.
- **Endpoints:** `GET /staff` (`people[]`, `invitations[]`, `next_page`, `next_invitations_page`, `q`, `status`) and `GET /staff/{person_id}` (`workspaces[]`). Source: delivery/connect/screens-a-frame-core.md section SCR-21.
- **Code:** the frontend, under `frontend/src/features/setup`.
- **Controls:** render from the returned `can_edit_profile` and `can_assign_primary_role`. Draw no active Invite, Deactivate, Restore or Edit roles controls.
- **Hidden until the backend supplies the data (D-182):**
  - the "8 people" count
  - "Last signed in"
  - "Invite sent N days ago"
  - "Deactivated <date>"
  - role-per-workspace wording (the live row has one `access` string)
- **Who may open it (A-53):** show the list to whoever the server serves it to. On 403, show the existing forbidden state. Do not guess an Admin role. Flag this in the spec and the PR.
- **Out of scope:**
  - all writes and the A-51 and A-54 questions
  - delegations (`/staff/delegations/{authority_id}`)
  - the SCR-13 roles tab
  - the Setup case-id picker beyond what the read needs
- **Other rules:** standing answers as in delivery/features/F-73/coordinator-answers.md.

## Risk
Medium. The slice reads personal data (email, username, access) and is role-gated by the server, but it has no write and nothing hard to undo. The surfaces are ui, api and auth. The reviewers should confirm that the 403 is shown honestly and that no control is drawn as active.
