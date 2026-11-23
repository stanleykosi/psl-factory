DECISION: READY
RISK: medium
SURFACES: ui, infra, security
PRODUCT-ACCEPTANCE: not-required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Both gates from the earlier NOT-READY are cleared. D-API-STYLE r3 and D-AUTH r3 are approved as built (architecture/sources/decisions-2026-11-23.md, D-172 in delivery/OVERNIGHT-DECISIONS.md, package v8). The split into F-56 (this, part a) and F-57 (part b) is recorded, so the size problem is gone.
- The screen-view proposals still pending under FE-CONNECT-1 (D-ASSISTANT-VIEW, D-LINE-WORKSPACE, D-RESPONSE-VIEW and similar) shape screen data. F-56 touches no screen data, so none of them applies to this slice.
- One outcome: the Django embed is gone, so the shell always draws our own frame, and the Next.js proxy forwards only /api/v1 and the six authenticated download routes. No design change: the approved frame is what the shell already draws in mock mode.
- The sign-in gap until wave 1 is accepted (D-172) and only matters against the live API. Role words are F-57's work, not this feature's.
- Not run by this check (no shell): `design.py check` and the tests. The builder gate must run both. No test in frontend/tests or delivery/checks.sh references the removed pieces (FactoryDesk, factory-forms, factory-assets, work_desk_url).

## Scope
Task FE-CONNECT-1, part a only. No operation IDs; no new endpoints. The spec writer follows this as binding.

In:
- Delete `frontend/src/shell/FactoryDesk.tsx`. In `frontend/src/shell/AppShell.tsx` remove the `FactoryDesk` import (line 19), the `native` constant (around line 73), the `!native` guard on destinations, and the early `if (native) return <FactoryDesk .../>` (around line 131). Nothing else in the frame changes.
- In `frontend/next.config.ts` remove `NEXT_PUBLIC_FACTORY_ORIGIN` (the `env` entry), the `/factory-assets/work-client.js`, `/accounts/:path*`, `/factory-forms/:path*` and `/static/:path*` rewrites, and the catch-all `fallback`. Keep `/api/v1/:path*`, `allowedDevOrigins`, and the mock-only `/__mock/reset` (still gated on `NEXT_PUBLIC_MOCK_DEMO === '1'` and not production).
- Add rewrites for exactly the six authenticated download routes in `config/urls.py` (lines 27 to 37): `cases/<uuid>/files/<int>/`, `projects/<uuid>/templates/<int>/file/`, `cases/<uuid>/rfp/intake/<int>/attachment/`, `work/<int>/invoice-proof/<int>/`, `cases/<uuid>/finance/invoices/<int>/payments/<int>/proof/<kind>/`, `cases/<uuid>/finance/reminders/<int>/drafts/<int>/<file_kind>/`. Match each as narrowly as the path syntax allows. Do not proxy `finance/followup-inbox/...` (an inbound webhook, not a download) or `health/`. Check the pattern list against `src/app` pages so a rewrite does not shadow an app route (for example `/cases/...` or `/work/...` pages); if one would, use `afterFiles` or a tighter pattern and say so in the spec.
- Check the tests main changed around these files (`git diff d6413009..9bac3109 -- frontend`) and keep them passing; add a unit or config test that the rewrite list is exactly the expected set and has no catch-all.
- No link may point at `django_url` or `work_desk_url`.

Out, binding:
- F-57's work: live types, live client, session and error handling, frame on live `GET /me`, role words, mock `/me` shape.
- SCR-17 sign-in, recovery and invitation pages (wave 1); any screen's own data (wave 2+); DemoBar behaviour.
- Any change to the v7 mock or to `roles`, `destinations` and `startable_lines` consumers.
- Any backend change.

Known and accepted: against the live API the frame will not be fully right until F-57 (it still reads the v7 `/me` shape), and a signed-out person has no sign-in page until wave 1 (D-172). Mock mode must stay fully working.

## Risk
Medium. Small diff, but `next.config.ts` decides which paths reach Django, and four of the six routes carry client files and payment proofs; a rewrite that is too broad or that shadows an app route would be a security and routing fault that is easy to miss. Surfaces: ui (shell loses the embed), infra (proxy config, env var removal), security (authenticated download paths exposed through the proxy). No data, money logic, auth code or contract change, so not high; no new flow or copy, so product acceptance is not required.
