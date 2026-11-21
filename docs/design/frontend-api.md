# Factory API for the frontend cutover

The live Django implementation serves a versioned OpenAPI contract at `/api/v1/openapi.json`. The exported contract is generated from the mounted route registry and the request schemas used by Django. The existing frontend prototype uses the design-time v7 contract and its mock server. Generate a separate client from the live contract for the cutover and reconcile its field names and shapes feature by feature.

## Use the live API

Run these commands from the repository root. The first emits machine-readable OpenAPI. The second expands the cutover map to all 262 accepted states and checks every API operation and Django route it references.

```powershell
.venv\Scripts\python.exe manage.py export_factory_api
.venv\Scripts\python.exe manage.py export_factory_api --screen-map
```

- Serve the future frontend and Django API on the same origin. Keep ordinary Django login, recovery and invitations during the cutover. The Django session and staff lifecycle checks apply to both clients.
- Read `GET /api/v1/me` after sign-in. Send its `csrf_token` in `X-CSRFToken` on writes, with the session cookie. The token belongs to the current session. Private responses are marked `no-store`.
- Use the current server-issued record identifiers and revisions. Treat a conflict as a request to reload, inspect the current record and make a fresh decision. A permission response or an unavailable record stops that operation.
- Submit multipart private files through the existing upload service. Fetch file and detailed source links through their authenticated Django URLs. Agent drafts keep the exact source or attempt pin through review, recovery and handoff.
- Send initiation and Assistant requests with the same idempotency key for the same intent. Treat an accepted command as an acknowledgement. Refresh authorized work or receipt status for the business outcome. Explicit release and receipt reconciliation remain separate.
- Read queue coverage and handle incomplete results and pages. Amounts are decimal strings where projected as money. Unknown values remain null.

## Primary roles

Setup starts with PMO Lead, Finance Lead, CEO, CTO, HR and Admin. In **Setup → People**, open a person’s workspace and choose **Review primary role**. Preview the access added or removed, then confirm with a reason. A person can hold one primary role per workspace. Each role change preserves separately granted access and checks outstanding work before removal.

An account has the Admin role in a workspace when its existing staff administration delegation is current there. The technical bootstrap administrator uses **Workspace delegation** and **Staff account controls** to review that authority. Admins can add a workspace role from the available access functions. Business approvals still follow the configured decision rules, including separate authority for restricted payroll, invoice release and technical release.

| API operation | Use |
| --- | --- |
| `GET /api/v1/setup/primary-roles` | Read the built-in roles |
| `GET /api/v1/setup/{case_id}/primary-roles` | Read the workspace catalogue and whether the signed-in person can add roles |
| `POST /api/v1/setup/{case_id}/primary-roles` | Add a role under current Admin delegation |
| `GET /api/v1/setup/{case_id}/people/{person_id}/primary-role?role=cto` | Preview an exact assignment. An empty role value previews removal |
| `POST /api/v1/setup/{case_id}/people/{person_id}/primary-role` | Confirm the preview using its fingerprint and a stable request ID |
| `GET /api/v1/me/workspaces/{case_id}/primary-role` | Read your role within the selected workspace |
| `GET /api/v1/projects/{case_id}/hr` | Open the permitted HR handoff, correction, staff-cost question and Assistant destinations |

The HR role opens the **HR** project tab with handoff metadata and staff-cost follow-up. Correction reviews, disclosures, private exports and Zainab still use their existing, separate permissions. Native HR-to-Finance and payroll services own the workflow and its commands. Staff accounts and access stay under Admin delegation.

The [role-based operating model](../../guide/11-FULL-PRODUCT.md#role-based-work-and-supervision) also supports role-scoped staff invitations. An authorised Admin can use **Primary roles → Teams and work assignments** to create a team and assign existing or new actions and eligible native reviews. The invitee reviews the base role, team, workspace and member, lead or standalone scope. Sign-in opens the role dashboard. Existing workspace-profile invitations follow their existing access model.

For an existing account, choose **Setup → People → Move to team scope** beside the affected workspace. Preview the broad permissions that will be removed and the open actions that will keep their current owner. Resolve any listed handover or decision claim first. The confirmation uses the reviewed fingerprint, a stable operation UUID and a reason. The same account can keep its separately authorised workspaces.

| API operation | Use |
| --- | --- |
| `GET /api/v1/setup/{case_id}/people/{person_id}/team-scope` | Preview the selected role, mode and team, access removals, retained actions and holds |
| `POST /api/v1/setup/{case_id}/people/{person_id}/team-scope` | Confirm the reviewed move with its current fingerprint and operation UUID |
| `POST /api/v1/setup/{case_id}/team-decisions` | Assign a supported current decision to a scoped member under Admin delegation |
| `GET /api/v1/role-dashboard` | Read current role positions, exact assignments, eligible decisions, native workspace decision links and team review status |
| `GET /api/v1/role-work/{assignment_id}` | Read one authorised action or the exact available review packet |
| `POST /api/v1/role-work/{assignment_id}/actions` | Start or complete the native action as its current assignee |
| `POST /api/v1/role-work/{assignment_id}/decision` | Record a native decision using the reviewed version token |

The Django role desk and JSON endpoints share the same checks. Team leads see members’ assignment and decision status. Only the eligible assignee receives a decision packet or can submit a verdict. The scoped desk handles Finance invoice and Accounting reviews, Finance schedules, HR corrections, Planning exit, closure, client escalation and supported controlled-document reviews. Use `workspace_decisions` for native factory decisions and `approval_desks` for specialist workspace links. Payment exceptions, Emergency authorisation and retrospectives, restricted payroll, bids, forecasts and department-owned approvals retain their native permissions and exact source rules. Issuance, publication and technical or customer sign-off each have their own authority checks. Invitation creation and acceptance use the established Django forms.

## Workflow coverage

The [cutover map](../../contracts/factory-api-screen-map.json) groups the 262 states by screen and lists the available JSON operations, the working Django routes and the remaining contracts. A grouped mapping points to workflow capability. It does not imply that every variation already has a JSON equivalent.

The current API covers intake against exact native sources for all 25 existing factory work definitions. It also covers work and project readback, invoice and Accounting task claims and decisions, reviewed project and Finance document actions, minutes confirmation, bid pack and outcome handling, authorised receipt reconciliation, department chat, eight scoped file agents, client contacts, alerts and verified-channel preferences. Its invoice, Payroll and document commands use the same durable services and authority checks as the Django pages.

Prioritize the next cutover in this order.

1. Shared navigation, work queues, project directory and project tabs, using current scope and pagination. Keep native links for controlled record and proof readback.
2. Exact Finance review and recovery, minutes and bid packs, and current-source Assistant conversations. Use the typed draft and start endpoints to require the saved version during handoff.
3. Closed JSON projections for detailed domain records and their scoped commands. The map tracks remaining release and Go-live attestations, change and incident authority, planning and costing detail, Finance imports, payments and corrections, private HR and Payroll records, reports and publication receipts.
4. Account and staff administration, template intake and policy Setup. Retain the native Django forms until equivalents have permission, concurrency and browser parity. HOD-owned values remain deferred.

Keep the current Railway browser ledger as the Django functional baseline. Test newly migrated screens against live API responses with synthetic data and the ordinary test roles before switching their navigation.
