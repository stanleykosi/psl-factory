VERDICT: PASS
COMMIT: abf2482a0bbc656b975f1f1afda722df6cdf7941
REVIEWER: reviewer-technical
AUTHORITY: reviewer-technical

## Summary
- The embed is removed cleanly: `FactoryDesk.tsx` is deleted, and `AppShell` always goes through `visibleDestinations(me.destinations)`. Nothing else in the shell changed.
- `next.config.ts` matches the spec: one `beforeFiles` API rewrite, six download rewrites in `afterFiles`, `fallback: []`, and no `env`. The mock reset is still gated on the flag and non-production.
- The destination is built by stripping the `(...)` constraints and adding Django's trailing slash. It produces the correct Django paths for all six routes, which I compared with `config/urls.py` lines 27-37. The builder confirmed the slash by a live request.
- The new tests cover criteria 1 to 6: the exact set, a flag matrix, accept and reject cases, the no-shadowing list, and the shell with Django fields on `/me`. No existing shell test was edited.
- The `assistant-dictation` test repair is a path fix plus a holder object in place of the `this` alias. No assertion was relaxed. The scope is slightly wider than the spec, but the coordinator asked for it.

## Findings
- TECH-1-1 | non-blocking | low | backend | Criterion 11 expected Django's own 401/403/404 for an unauthenticated download. Django answers 302 to `/accounts/login/` because of `@login_required` (`apps/agents/upload_views.py:57,118`). The browser then lands on a Next 404 until SCR-17. This is existing backend behaviour, outside this feature's lane, and the builder recorded it. It needs a backend or F-57 follow-up so downloads answer an API-form 401. Do not change it here.
- TECH-1-2 | non-blocking | low | frontend | `next-config.test.ts` accepts `afterFiles` entries whose destination includes the `:param` names, but it never asserts the exact destination of each download, for example `${API}/work/:work/invoice-proof/:proof/`. The trailing-slash and no-parenthesis checks are enough to catch regressions, so this is only a hardening idea.

## Notes
- The mock-dev run (criterion 8) used `next start` because of the dev-server lock. Reset demo was therefore not exercised live. The flag matrix is unit-tested and the rewrite code for it is unchanged, so the risk is low.
- The `SIGN_IN_URL` 404 is accepted per D-172.
