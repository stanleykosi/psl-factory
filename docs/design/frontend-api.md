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

The role dashboard exposes a delegated Admin position with mode `administrator` and a `manage_url` for its workspace. A staff-only Admin lands there after sign-in. Team leads land on their own team dashboard and retain their department’s invitation link. Business approval access continues to come from the exact workflow decision and current authority.

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

The [role-based operating model](../../guide/11-FULL-PRODUCT.md#role-based-work-and-supervision) requires a reviewed role for new staff. In **Primary roles → Teams and work assignments**, an authorised Admin creates teams and appoints their leads or the standalone CEO and CTO. A current PMO, Finance, HR or Admin team lead uses **Invite a teammate** in **My work** to invite members of their own team. The invitee sees the exact workspace, role and scope before account setup. A change to the lead’s authority stops acceptance until a current invitation is issued. Existing admitted accounts keep their reviewed access until it changes.

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

The role dashboard supplies an `invite_url` for a team lead’s own position. It opens the authorised Django invitation form. A new invitation covers one workspace and one role. Pending links based solely on access profiles or individual functions require a new role invitation.

## Workflow coverage

The [cutover map](../../contracts/factory-api-screen-map.json) groups the 262 states by screen and lists the available JSON operations, the working Django routes and the remaining contracts. A grouped mapping points to workflow capability. It does not imply that every variation already has a JSON equivalent.

The current API covers intake against exact native sources for all 25 existing factory work definitions. It also covers work and project readback, invoice and Accounting task claims and decisions, reviewed project and Finance document actions, minutes confirmation, bid pack and outcome handling, authorised receipt reconciliation, department chat, eight scoped file agents, client contacts, alerts and verified-channel preferences. Its invoice, Payroll and document commands use the same durable services and authority checks as the Django pages.

Prioritize the next cutover in this order.

1. Shared navigation, work queues, project directory and project tabs, using current scope and pagination. Keep native links for controlled record and proof readback.
2. Exact Finance review and recovery, minutes and bid packs, and current-source Assistant conversations. Use the typed draft and start endpoints to require the saved version during handoff.
3. Closed JSON projections for detailed domain records and their scoped commands. The map tracks remaining release and Go-live attestations, change and incident authority, planning and costing detail, Finance imports, payments and corrections, private HR and Payroll records, reports and publication receipts.
4. Account and staff administration, template intake and policy Setup. Retain the native Django forms until equivalents have permission, concurrency and browser parity. HOD-owned values remain deferred.

Keep the current Railway browser ledger as the Django functional baseline. Test newly migrated screens against live API responses with synthetic data and the ordinary test roles before switching their navigation.
### Connecting a separate frontend host

Set `API_ORIGIN` on the Next server to the Django server. When the browser uses a different origin from Django, set `PSL_FRONTEND_ORIGINS` on Django to that exact public frontend origin, including the port if present. Multiple approved origins can be separated with commas. Django still checks the session and the CSRF token on writes. Same-origin Railway use needs no additional origin.

The separate frontend serves the signed-in work queue and Finance invoice review. The other work forms open through the same frontend proxy. A deployment with a separately reachable public Django site may set `NEXT_PUBLIC_FACTORY_ORIGIN` to use that site for the forms.

## PMO and Finance process access

`GET /api/v1/processes` returns the same 108 process entries as **Find a process** in Start work. Each entry identifies whether it continues from a department record and whether the signed-in person has a project where they can submit its intake. Project evidence and decisions are fetched separately under the current reader’s access. The JSON contract is served at `/api/v1/openapi.json`.

| Operation | Use |
| --- | --- |
| `GET /api/v1/lines` | Find intakes available to this person. |
| `POST /api/v1/work` | Start an available workflow on an authorised project. Engagement accepts an existing capture or the source evidence and route from the Django form. |
| `GET /api/v1/received-bids/organisations` and `POST /api/v1/received-bids` | Select a current organisation delegation and submit a received bid with its original private file. Repeating the same intake uses its original receipt. |
| `GET /api/v1/projects/{case_id}/department-handoffs` | Page through this person’s visible department work in a project. |
| `GET /api/v1/work/{work_id}/department-handoff` | Read current source evidence, receipt and available decisions. |
| `POST /api/v1/work/{work_id}/department-handoff/source-review` | Resolve a completed specialist packet as the named information reviewer. |
| `POST /api/v1/work/{work_id}/department-handoff/finance-acknowledgement` | Acknowledge the exact HR-authorised snapshot as its named Finance recipient. |

For a source-triggered process, the ordinary work detail returns `department_handoff_url`. Follow that link for the permitted evidence and decisions. A missing source, a withdrawn appointment or an unavailable original receipt can change what the same account sees on its next request.
