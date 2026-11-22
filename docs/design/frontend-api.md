# Factory API for the frontend cutover

Generate the frontend client from the [checked-in live OpenAPI contract](../../contracts/psl-factory.openapi.json). A running Django deployment serves the same contract at `/api/v1/openapi.json`. The mounted routes and request schemas generate both copies. The design prototype and its mock server use the separate v7 contract. Where the method and path match, use the live request and response types for Django integration.

## Use the live API

Run these from the repository root to refresh OpenAPI and export the complete inventory of design states, process entry points, and prototype operations without an exact live route.

```powershell
.venv\Scripts\python.exe manage.py export_factory_api --output contracts/psl-factory.openapi.json
New-Item -ItemType Directory -Path .runtime -Force | Out-Null
.venv\Scripts\python.exe manage.py export_factory_api --coverage --output .runtime/psl-api-coverage.json
Set-Location frontend
npm ci
npm exec --offline openapi-typescript -- ../contracts/psl-factory.openapi.json -o src/api/live-schema.d.ts
```

- Serve the future frontend and Django API on the same origin. Keep ordinary Django login, recovery and invitations during the cutover. The Django session and staff lifecycle checks apply to both clients.
- Read `GET /api/v1/me` after sign-in. Send its `csrf_token` in `X-CSRFToken` on writes, with the session cookie. The token belongs to the current session. Private responses are marked `no-store`.
- Use the site origin as the client base URL. The OpenAPI paths already include `/api/v1`. Handle the declared HTTP statuses and use the JSON error `code` and optional `fields` for application errors.
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

The [cutover map](../../contracts/factory-api-screen-map.json) groups 262 design states into 59 screen groups and lists JSON operations, Django routes and remaining steps. OpenAPI 1.4.0 describes 177 operations across 136 paths. The map records remaining JSON work in 43 groups covering 225 states. Some states share a workflow, and some still use a Django form for one action. Of the 51 design-prototype operations, 22 have an exact method and path match. Compare their field shapes before migrating a call.

The current API covers intake against exact native sources for all 25 existing factory work definitions. It also covers work and project readback, invoice and Accounting task claims and decisions, reviewed project and Finance document actions, minutes confirmation, bid pack and outcome handling, authorised receipt reconciliation, department chat, eight scoped file agents, client contacts, alerts and verified-channel preferences. Its invoice, Payroll and document commands use the same durable services and authority checks as the Django pages.

| Journey | How the frontend uses the API |
| --- | --- |
| Start work and source selection | Follow `source_options_url` from `GET /api/v1/lines/projects`. Pass `field` using the returned path relative to `intake`, for example `data.template_id` for minutes. Continue with `before=next_before`. Pass `parent_id` for adjustments to a selected trial balance. Submission checks the source and current revision. |
| Minutes and project actions | Submit existing evidence to `POST /api/v1/work` or use multipart minutes intake. Use the exact extraction and case revisions from the minutes readback for human confirmation, then follow the document and delivery state. The meeting collection and action commands also support independent retrospectives and commitments. |
| Client contacts and recovery | Keep named personnel and legal billing identities separate. An organisation link proposal needs an independent confirmation. Invoice proof uses the named source owner and exact private file; a draft stop uses the original issue readback. Work access requests return an opaque acknowledgement. |
| Controlled reports | Read available edits and release details from the publication resource. Revise against the current version, obtain review and send the exact recipient fingerprint. Check the job and original receipts there. |
| Planning to release | Use the exact Planning packet and each department-owned receipt. Read phase checks in the release register. Record observations and verify the original readiness and release records. |
| Go-live through closure | Capture a client reply against the exact delivered report, then prepare a corrected version or review the decline. Record milestone completion from its separately approved mapping. Use the observed stability and archive results, named Support reply and exact closure evidence for finalisation. |
| Restricted payroll | List the owner's permitted provider formats, then upload the original file. CSV and Excel require extract facts from the source owner. Page private working rows as an authorised reader. Submit HR receipt and publication follow-up against the pinned source and work versions. |
| Decision appointments | Draft a complete set of named approvals against the latest appointment version and recorded owner evidence. Use policy configuration state IDs for validation, activation and revocation. The appointed person still needs the workflow's action grant. |
| Milestones and changes | Read eligible proof or signed-stage plan choices, submit the exact current revision, then read the resulting milestone or project handoff. |
| Actions and templates | Read current owners, deadlines and evidence with scoped history. Use the exact action revision to update an action. Send template sections as repeated multipart fields. Fetch selected files from the returned authenticated download URL. |
| Received bids | Read the assignment queue, then the exact bid and approved nominees. After assignment the bid moves to the chosen project manager's work. |
| Portal submission and follow-up | Use the exact approved pack to record a portal receipt. Save and review customer wording before reserving a follow-up. Use the recorded receipt to show actual delivery. |
| Payments and reminders | Keep reported payments, verified cash and allocations separate. A reminder reservation and a verified delivery receipt are separate records. Attach a checked private PDF from the current user's uploads. |
| Finance close and client directory | Page through authorised workspaces and contact groups. Use current-day receivables capture and read the resulting snapshot. |
| Delegation and corrections | Save a delegation as a draft for separate review. Correction requests require the exact work and case revisions plus a source selection whose shape depends on the line. |
| Planning exit, Go-live and Support receipt | Use the Planning packet fingerprint for a decision. For Go-live, select the current delivered report and supply both signers' observed facts. Support recipients can acknowledge their own receipt or record gaps. |

Prioritize the next cutover in this order.

1. Shared navigation, work queues, project directory and project tabs, using current scope and pagination. Keep native links for controlled record and proof readback.
2. Exact Finance review and recovery, minutes and bid packs, and current-source Assistant conversations. Use the typed draft and start endpoints to require the saved version during handoff.
3. Finish JSON projections for detailed domain records and their scoped commands. The map tracks remaining release evidence, Go-live client replies, change and incident authority, planning and costing detail, Finance imports and payment corrections, private HR and Payroll records, reports and publication receipts.
4. Finish account and staff administration and policy Setup. Retain the native Django forms for these steps until equivalents have permission, concurrency and browser parity. HOD-owned values remain deferred.

Keep the current Railway browser ledger as the Django functional baseline. Test newly migrated screens against live API responses with synthetic data and the ordinary test roles before switching their navigation.
### Connecting a separate frontend host

Set `API_ORIGIN` on the Next server to the Django server. When the browser uses a different origin from Django, set `PSL_FRONTEND_ORIGINS` on Django to that exact public frontend origin, including the port if present. Multiple approved origins can be separated with commas. Django still checks the session and the CSRF token on writes. Same-origin Railway use needs no additional origin.

The separate frontend serves the signed-in work queue and Finance invoice review. The other work forms open through the same frontend proxy. A deployment with a separately reachable public Django site may set `NEXT_PUBLIC_FACTORY_ORIGIN` to use that site for the forms.

## PMO and Finance process access

`GET /api/v1/processes` returns the same 108 process entries as **Find a process** in Start work. Each entry identifies whether it continues from a department record and whether the signed-in person has a project where they can submit its intake. Project evidence and decisions are fetched separately under the current reader’s access. The JSON contract is served at `/api/v1/openapi.json`.

The 63 department-triggered entries expose `guide.action`, `guide.screen`, `guide.source_url` and `guide.tracking_url`. The two URLs open the native action or the process-filtered Department handoffs view after the reader chooses an accessible project. A client can pass `?project=<project UUID>` when it already knows the project. An unavailable project is rejected. Other entries return a null guide. Start work retains its 25 workflow types and the separate received bid intake.

PMO Lead, Finance Lead, CEO and CTO see every project in their organisation and data classification through `GET /api/v1/projects` and can open project handoffs. A source link opens the exact screen when the reader has its native permission. For a workspace they can open without that permission, the link explains who owns the action and offers the workspace and tracking views. Handoff rows still require permission to read the original work. Use `intake_available` for permission to start a line.

| Operation | Use |
| --- | --- |
| `GET /api/v1/lines` | Find intakes available to this person, their submission URL and their project picker URL when applicable. |
| `GET /api/v1/lines/projects?line=planning/v1` | Find projects where the current person can submit that Start work type. Use the returned `case_id` and `case_revision`. Keep the returned Django URL for source selection and forms that still run there. |
| `POST /api/v1/work` | Start an available workflow on an authorised project. Engagement accepts an existing capture or the source evidence and route from the Django form. |
| `GET /api/v1/received-bids/organisations` and `POST /api/v1/received-bids` | Select a current organisation delegation and submit a received bid with its original private file. Repeating the same intake uses its original receipt. |
| `GET /api/v1/projects/{case_id}/department-handoffs` | Page through this person’s visible department work in a project. Retain the optional `process` filter alongside `before` when loading earlier results. |
| `GET /api/v1/work/{work_id}/department-handoff` | Read current source evidence, receipt and available decisions. |
| `POST /api/v1/work/{work_id}/department-handoff/source-review` | Resolve a completed specialist packet as the named information reviewer. |
| `POST /api/v1/work/{work_id}/department-handoff/finance-acknowledgement` | Acknowledge the exact HR-authorised snapshot as its named Finance recipient. |

For a source-triggered process, the ordinary work detail returns `department_handoff_url`. Follow that link for the permitted evidence and decisions. A missing source, a withdrawn appointment or an unavailable original receipt can change what the same account sees on its next request.
