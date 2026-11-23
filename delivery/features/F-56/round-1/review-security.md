VERDICT: PASS
COMMIT: abf2482a0bbc656b975f1f1afda722df6cdf7941
REVIEWER: reviewer-security
AUTHORITY: reviewer-security

## Summary
- The proxy now forwards only `/api/v1/*`, six exact download paths, and the mock-only `/__mock/reset`. It has no catch-all, and `fallback` is empty. That shrinks what the browser origin can reach on Django.
- All six Django download views have `@login_required` and `@require_safe`. They also take the case or work id and check per-record access. Session, permission and tenant checks stay in Django, so the proxy grants nothing.
- Ids are constrained to a UUID or `\d+`, and `:kind` and `:file_kind` are single segments. I probed the dev server on :3000. A `%2F` in a kind gave a 404, and `%2e%2e` was normalised by Next into a same-origin 308 and did not reach a new Django route. `/accounts/login/`, `/static/x.js` and `/admin/` give a Next 404, and `/health` gives a 308 and then the Next 404. The Django admin, health, static and finance followup-inbox routes are no longer exposed through the browser origin.
- The six rewrites sit in `afterFiles`, so a real app page wins over a download rewrite. The embed is deleted, and the shell ignores `work_desk_url` and `django_url`. This removes the third-party script and form-prefix path.

## Findings
None.

## Notes
- Non-blocking, accepted under D-172: an unauthenticated download gets Django's 302 to `/accounts/login/`, which is a Next 404 until wave 1. It exposes nothing. It is a backend and UX question for F-57.
- Non-blocking: the `:kind` and `:file_kind` params accept any single segment. Django's views allow-list the values (`report`, `verification`, `reported-amount`, `pdf` and `email`) and return 404 for anything else. No proxy change is needed, but a future download that trusts a free-form kind would inherit this.
- Pre-existing, not introduced here: `retired_page` and Django's own handlers still answer on the API origin. This is only reachable directly, not through the proxy.
- No new dependencies, secrets or logging changes in the diff. The deleted `NEXT_PUBLIC_FACTORY_ORIGIN` env removes a build-time public origin setting.
