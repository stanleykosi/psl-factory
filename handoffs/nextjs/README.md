# PSL Operations Factory · Next.js handoff

Start from the existing [Next.js app](https://github.com/stanleykosi/psl-factory/tree/ad243b1eada4036d546b4a8f8bb0f22169f2c7bd/frontend) at GitHub main revision `ad243b1e`. The Railway preview serves OpenAPI 1.22.0 with 379 operations across 268 paths. Django owns sessions, work, approvals, uploads and the background workers. Keep Django available throughout the cutover and switch users to the Next.js pages as each journey is verified. [Railway preview](https://psl-design-web-design-acceptance.up.railway.app) · [Live OpenAPI](https://psl-design-web-design-acceptance.up.railway.app/api/v1/openapi.json)

## Files to use

| File | Use it for |
| --- | --- |
| [OpenAPI 1.22.0 snapshot](psl-factory.openapi.json) | Inspect request fields, status codes and response shapes. The snapshot matches the [canonical contract](../../contracts/psl-factory.openapi.json) at the handoff revision. |
| [Generated TypeScript types](live-schema.d.ts) | Type the first connected pages. Regenerate from the canonical contract when it changes. |
| [Screen-to-API map](factory-api-screen-map.json) | Find the mounted operations and Django reference routes for each of the 59 screen groups. |
| [262-state crosswalk](screen-state-crosswalk.csv) | Filter by state ID or journey to find the design board, shared OpenAPI operations and exact responses tested for that state. |
| [Per-state Railway results](../../docs/design/api-state-replay-results.csv) | Find the exact test, required and observed API responses, source revision and Railway deployment for every state. |
| [Detailed API integration notes](../../docs/design/frontend-api.md) | Look up the workflows, scoped inputs, decision pins and receipts behind individual screens. |

Many states use the same page and differ by status, available actions, role or source data. The 262 passes apply to API journeys with synthetic data on Railway PostgreSQL. Run a Next.js walkthrough of each mapped state as you connect the designs.

## Start the app

Run these commands from the repository root with Node 24 or newer.

```sh
cd frontend
npm ci
npm exec -- openapi-typescript ../contracts/psl-factory.openapi.json -o src/api/live-schema.d.ts
npm run dev
```

`npm run dev` starts the design prototype and its mock. Existing `npm run gen:api` regenerates the v7 mock types. Use the separate live types in the adapter for connected screens and leave the mock available for design fixtures. Point `API_ORIGIN` at the Django backend when running against an authorised environment. `frontend/next.config.ts` already proxies `/api/v1`, accounts, static files and Django form fallbacks. Use an approved HTTPS frontend origin for Railway session testing. A separate frontend origin needs an exact Django `PSL_FRONTEND_ORIGINS` entry for CSRF. Keep browser API requests same-origin through the proxy and preserve Django cookies and CSRF checks.

### Session and work flow

1. Keep the existing **My work** route, full menu and **Start work** available to signed-in staff. For the first connected route, use the native sign-in or `GET /api/v1/session` followed by `POST /api/v1/session`. Send cookies and the current `X-CSRFToken` on writes. Refresh the token after sign-in, sign-out or password change. Read `GET /api/v1/me` for navigation, assistant availability and the session context.
2. Build My work from `GET /api/v1/work` and fold `GET /api/v1/role-dashboard` into the same page for the role heading, team invitations and eligible decisions. Build the project list and tabs from `/api/v1/projects` and returned links. Keep the role data in My work with the existing navigation.
3. Use `GET /api/v1/lines`, its project picker and the returned intake URL for the 25 Start work types. Keep received bids as their own intake. `GET /api/v1/processes` supplies the 108 PMO and Finance entries, including the action and tracking links for the 63 department-triggered processes. If a line has no eligible project, present that in the picker.
4. After starting work, read the work detail, its panels and the latest history. The coordinator and eight specialists run on the backend. Show their scoped progress and drafts inside the work item. Use the department Assistant for conversations and verified source reuse. Poll during a current worker step, then refresh on decisions, exceptions and receipts.
5. Render approvals from the current review packet and permitted verdicts. Submit its exact IDs, revisions and token. After a return, show the reason and exact correction path. After an uncertain delivery, use the original receipt lookup before offering any permitted retry. A queued request earns a progress state, and a confirmed business output earns the verified state.

Handle expired sessions, forbidden or unavailable records, stale revisions and field errors. On a conflict, refresh the source or review and let the person confirm again. Render unknown amounts and missing owner or rule values explicitly. Preserve pagination, scope and `no-store` for private reads. Follow authenticated download URLs with the same session.

## Six-role permissions

Use these roles to label My work and structure its relevant work. Use the server's current workspace list, record access and allowed actions to decide what the user can see or do.

| Role key | Scope and My work | Invitations and decisions |
| --- | --- | --- |
| **PMO Lead** · `pmo-lead` | Team lead or member. The lead can open project workspaces in the same organisation and data classification and oversee PMO assignments. Members see their assigned work and permitted PMO records in their workspaces. | The current lead can invite PMO members into their own team. Planning, delivery and publication decisions follow the current native route. |
| **Finance Lead** · `finance-lead` | Team lead or member. The lead has the same workspace reach for Finance oversight. Members see their assigned work and permitted Finance records. Use the separate access checks for private sources and Payroll. | The current lead can invite Finance members into their own team. Independent review, payment exceptions, release and receipts use their exact workflow permissions. |
| **HR** · `hr` | Team lead or member in assigned workspaces. Show scoped HR-to-Finance handoffs, staff matching corrections and staff-cost questions. | The current lead can invite HR members into their own team. Follow the exact owner, review and named-recipient controls for disclosures and acknowledgements. |
| **Admin** · `admin` | Lead or member of an Admin team, with staff administration actions governed by current delegation. Delegated Admins see the relevant staff, role and access controls for their workspaces. | Admin team leads can invite their own members. A currently delegated Admin can create teams, appoint leads or standalone roles, and create workspace role definitions within the available functions. Business decisions require current workflow authority. |
| **CTO** · `cto` | Standalone. Can open project workspaces in the same organisation and data classification. Show permitted readiness, release, Change and Emergency records. | Show CTO decisions only when the current native workflow makes the user eligible. Standalone roles have no team invitation flow. |
| **CEO** · `ceo` | Standalone. Can open project workspaces in the same organisation and data classification. Show permitted leadership reports, verified outcomes and assigned decisions. | Show CEO decisions only when the current native workflow makes the user eligible. Standalone roles have no team invitation flow. |

Supervisors can see scoped assignment status. The exact packet and verdict go to the currently eligible decision maker. Project visibility and a role label alone never confer access to protected evidence or business decisions. Keep team invitations in My work. A team's lead can invite only into that exact team and role. Use the workspace invitation endpoint with `team_id` for its current authority, then submit the returned revision and membership IDs. Show the invitation’s workspace, role and scope during preview and acceptance. The backend rechecks the lead’s authority when the invitation is accepted.

| API | Purpose |
| --- | --- |
| `GET /api/v1/me/workspaces/{case_id}/primary-role` | Current role, mode and team in an exact workspace, if assigned. |
| `GET /api/v1/role-dashboard` | My work role positions, scoped actions, available decisions, team decision status and current invitation links. Use the returned Django team link during the initial cutover. |
| `GET/POST /api/v1/setup/{case_id}/invitations` | Read invitation authority and create the exact role-scoped invitation. Team leads supply the selected team ID. |
| `POST /api/v1/accounts/invitations/preview` and `POST /api/v1/accounts/invitations/accept` | Preview the current scope and set up the account using the verified invitation token. |
| `GET/POST /api/v1/setup/{case_id}/primary-roles` | List role definitions, permitted functions and `can_create`. A delegated Admin can add a definition here. The team and invitation APIs use the six built-in role keys. |
| `GET/POST /api/v1/setup/{case_id}/people/{person_id}/team-scope` | Preview and confirm an existing staff member’s move, including carried work and any blocking handover. |
| `GET /api/v1/role-work/{assignment_id}` | Obtain the native action or decision packet. Follow its declared `actions` or `decision` endpoint with the exact revisions and token. |

## First integration checks

- Sign in on the intended origin. Open My work and Start work with a lead, a member and a standalone account. Confirm each sees the shared menu and appropriate workspace and action scope.
- Run one PMO intake through background work and a human decision. Run one Finance review through return, exact correction, fresh approval and original receipt readback. Use the current state ledger to choose the precise scenarios.
- Check cross-team invitations, private-file access, an out-of-scope direct URL, a stale verdict and an uncertain delivery before moving the corresponding Next.js pages into navigation.
- Use the server's current holds when an owner, authority, rule or connector needs configuration. Department-head policy decisions remain deferred. Keep native Django links available while their corresponding Next.js flow is being connected.
