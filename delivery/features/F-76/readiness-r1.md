DECISION: NOT-READY
RISK: high
SURFACES: ui, api, auth, security, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: D-ADMIN-AUTHORITY
REVIEWER: readiness

## Summary
- F-76 is FE-SETUP-ROLES with SCR-21 Staff accounts. D-ADMIN-AUTHORITY is still revision 1, status open (architecture/model.json:1722-1747). Nothing in delivery/OVERNIGHT-DECISIONS.md:26, COORDINATOR-HANDOFF.md:165 or the connect docs settles it.
- Live 1.22.0 now has the endpoints (GET /staff, GET /staff/{person_id}, deactivation, restoration, invitations, primary-role). Having the endpoints does not settle who may use them. A-53 (who may open the screen, and what a non-admin gets) is unanswered in delivery/connect/backend-questions.md:117.
- Invite, deactivate, restore and change role are writes on identity and access. They stay held until PSL names who holds Admin. I have not assumed an Admin.
- A read-only slice is buildable (see Scope). It needs a separate feature, so F-76 as written (the whole screen plus writes) stays NOT-READY.

## Scope
Not for a spec as written. Proposed split:
- **F-76a, read-only Staff accounts (re-run readiness on it).** One outcome: an allowed person sees the staff list and one person's access by workspace. Endpoints: `GET /staff` (`people[]`, `invitations[]`, `next_page`, `next_invitations_page`, `q`, `status`) and `GET /staff/{person_id}` (`workspaces[]`). The page renders from the returned `can_edit_profile` and `can_assign_primary_role` and shows no write controls (Invite, Deactivate, Restore, Edit roles). Left out and listed as design exceptions: "8 people" count, "Last signed in", "Invite sent N days ago", "Deactivated <date>", and role-per-workspace wording (A-50, A-52; the live row has one `access` string). Not built until the design engineer records these exceptions. Before it passes, the design engineer or backend must say who may open it, and what a non-admin gets, empty list or 403 (A-53). The page must show the real 403 and must not guess the Admin role.
- **F-76b, the writes (Invite, Deactivate, Restore, Edit roles).** Waits on PSL answering D-ADMIN-AUTHORITY. Invite also needs the A-54 answers (invitation life, `join_url` host). Deactivate needs A-51 (who may take each open action). Each write is a review, then a confirm with a fingerprint.
- Out of both: delegations (`/staff/delegations/{authority_id}`), SCR-13 roles tab, Setup case-id picker beyond what the read needs (B-21/B-51).

## Risk
High for the whole task (identity, access and deactivation are hard to undo, and the authority is undecided, so any write invents an approver). The read-only slice alone would be medium: personal data (email, username, access), a role-gated read, and no write. Sources: model.json D-ADMIN-AUTHORITY, connect/screens-a-frame-core.md SCR-21, backend-handoff/gaps-a-project-setup.md:209-296.

## Questions
(Not NEEDS-INFO, since the blocker is a PSL decision. Listed for the coordinator.)
1. PSL: who holds Admin, and who may assign roles, invite and deactivate? (D-ADMIN-AUTHORITY)
2. Backend (A-53): which role may read `GET /staff`, and what does a non-admin receive?
