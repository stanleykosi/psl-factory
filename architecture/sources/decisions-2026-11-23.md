# Decisions, 23 November 2026: API style and sign-in approved as built

Relayed by the coordinator from the design engineer (hunchoweb) in the session that started the frontend connection (wave 0, feature F-56, task FE-CONNECT-1).

## Context

The backend developer shipped the data API on main on 22 November 2026: OpenAPI 1.22.0 (`contracts/psl-factory.openapi.json`, main `9bac3109`). Django on Railway is now API-only. The design-engineer handoff is `handoffs/nextjs/README.md`. Readiness for F-56 found FE-CONNECT-1 gated by D-API-STYLE and D-AUTH, both still `proposed` at revision 2, although the backend built exactly what they describe.

## Question and answer

Asked: "Wave 0 is blocked on two architecture decisions, the API style and how sign-in works. Both are still marked 'proposed' even though the backend has already built them exactly that way. How should we clear this?"

Answer (design engineer, 23 Nov 2026): **"Approve both decisions"**, as the backend built them.

## What is approved

- **D-API-STYLE r3 (approved).** Plain Django JSON views under `/api/v1` call the existing domain services, with no new API framework. The views live in `apps/core/factory_api/`, not in the `apps/api` package that r1 proposed. The contract is generated from the mounted routes and checked in at `contracts/psl-factory.openapi.json`, and the server serves it at `/api/v1/openapi.json`. Lists page by `page` and `next_page`. Errors are `{code, message, fields?}`.
- **D-AUTH r3 (approved).** The Django session cookie authenticates. Writes send the `X-CSRFToken` header. Sign-in, sign-out and token refresh use `GET` and `POST /api/v1/session` and `POST /api/v1/session/logout`. The token rotates on sign-in, sign-out and password change. The Next.js app serves `/api/v1` same-origin through its proxy. A separate frontend origin must be listed exactly in the backend's `PSL_FRONTEND_ORIGINS` for CSRF.

## Also decided in the same exchange (delivery, not architecture)

- F-56 is split into two pull requests: (a) remove the Django embed and fix the proxy; (b) live types, client, session and error handling, and the frame on the live `/me`.
- Until backend question A-1 is answered, the top bar reads role words from `GET /api/v1/role-dashboard` `positions[]` and shows only the name if that read fails. The sign-in gap (no sign-in page until wave 1, SCR-17) is accepted.
