DECISION: NOT-READY
RISK: medium
SURFACES: ui, api, security, auth, infra, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: D-API-STYLE, D-AUTH
REVIEWER: readiness

## Summary
- The work is well understood and mostly sized right, but two gates are open. FE-CONNECT-1 is the one frontend task the architecture says IS gated by the proposals (architecture/build_model.py:1064), and D-API-STYLE and D-AUTH are still `proposed` at revision 2 in architecture/packages/v7/model.json (owner: backend developer). The v7 scope gate is an EXCEPTION (early start by the design engineer, "PSL approval still required"; authorized action `local_artifact_generation` only). F-56 has no recorded explicit exception of its own (`feature.json` baseline.explicit_exception is null).
- The backend facts these decisions describe are already shipped (live OpenAPI 1.22.0, same-origin Django session cookie plus CSRF header, plain JSON views). So the fix is paperwork, not redesign. Either the backend developer or the design engineer approves D-API-STYLE r2 and D-AUTH r2 (they match what shipped), or the design engineer records an explicit exception for F-56 that names its limits (wave 0 only, frontend only, no PSL-visible new flow).
- Approved design (design/review.json, 13 Nov, version 1794581312-b166, plus the 15 Nov frame exception D-89) covers the frame. It never drew a signed-out state without a sign-in page. After this feature lands, a signed-out person on the live API has no way to sign in from the app until wave 1 (SCR-17). The design engineer should accept that gap knowingly, or pair wave 0 and wave 1 in one release.
- Size: all four proposed items together touch next.config.ts, AppShell, the client and error layer, generated types with a drift test, the mock's /me and every consumer of `roles`, `destinations` and `startable_lines`. That is large for one reviewable PR. Proposed split below.
- Not checked: `design.py check` and the tests (no shell was available to this check). The builder gate must run them.

## Scope
Binding for the spec writer once the gates above are cleared. Task FE-CONNECT-1, wave 0 only. No new operation IDs: it uses existing live `GET /api/v1/me`, `GET /api/v1/session`, `GET /api/v1/role-dashboard` (read only, for role words).

Proposed split into two PRs (recommended):

**F-56a, remove the embed and fix the proxy (low-medium risk, ui, infra, security)**
- Delete `frontend/src/shell/FactoryDesk.tsx`. In `AppShell.tsx` remove the import, the `native` constant, the `!native` guard on destinations and the early return.
- In `frontend/next.config.ts` drop `NEXT_PUBLIC_FACTORY_ORIGIN`, the `/factory-assets/work-client.js`, `/accounts/:path*`, `/factory-forms/:path*` and `/static/:path*` rewrites and the catch-all `fallback`. Keep `/api/v1/:path*`, `allowedDevOrigins` and the mock-only `/__mock/reset`.
- Add rewrites for exactly the six authenticated download routes in `config/urls.py` (cases files, project template file, RFP intake attachment, work invoice-proof, finance payment-proof, finance reminder-draft). Builder confirms each against `config/urls.py`; no others.
- Do not point any link at `django_url` or `work_desk_url`.

**F-56b, live types, client, session and errors, live /me (medium risk, api, auth, contract-change)**
- `src/api/live-schema.d.ts` generated from `contracts/psl-factory.openapi.json` by a package script, plus a drift test that fails when the generated file differs from the contract. Live-typed client beside the v7 one, sharing the CSRF middleware and error reader. Unconnected screens keep the v7 client and mock.
- Session: `GET /session` for a token before sign-in and after rotation. Errors: 403 `csrf_failed` handled apart from `forbidden` (refresh token via `GET /session`, tell the person to press the action again; do not auto-retry writes); own kinds for 429, 503 `read_limited` and 400/413/415; `fields` always kept on 422; `idempotency_conflict` replaces `idempotency_key_reused` (useStartWork.ts).
- The frame loads from live `GET /me`: `destinations[]` objects `{key,title,django_url}` (look up by `key`; `clients` known; same six for everyone, so menu hiding by role is lost, backend question A-2), `startable_lines` live keys, `roles` gone. The mock `/me` moves to the live shape and is validated against the live contract (rule: an operation's mock fixtures move to the live shape when its screen is connected).
- Role words in the top bar and phone menu: engineering proposal, read `GET /role-dashboard` `positions[]` until backend answer A-1; if that call fails or returns nothing, show the name only, never an invented role. The design engineer should confirm this fallback.

Out of scope, binding: SCR-17 sign-in, recovery and invitation pages (wave 1); any screen's own data (wave 2+); the per-line workspace adapter and evidence picker; work-id format changes; DemoBar behaviour (stays mock-only).

## Risk
Medium. No money or data migration, but it changes the session, CSRF and 403 handling that every later screen relies on (frontend/src/api/errors.ts, client.ts), the proxy rewrites that decide which paths reach Django (next.config.ts), and a cross-layer contract (live OpenAPI 1.22.0 versus the v7 mock). Surfaces: ui, api, security, auth, infra, contract-change, and product-decision (role words source A-1, menu no longer filtered per role A-2). Product acceptance is required because what people see on first load changes and a signed-out person lands in a state with no sign-in page.

## Questions
Not NEEDS-INFO: nothing here is a client business rule. To move to READY the design engineer or backend developer needs to do one of:
1. Approve D-API-STYLE r2 and D-AUTH r2 in the architecture record (the live API already implements them), or record an explicit exception for F-56 stating its limits.
2. Say whether the split into F-56a and F-56b is accepted, or the single PR is kept.
3. Confirm the role-words fallback (role-dashboard positions, else name only) and that the sign-in gap until wave 1 is accepted.
