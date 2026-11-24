VERDICT: PASS
COMMIT: dab5f01825066cb85627bf0f427f27ef29e7d3ef
REVIEWER: reviewer-security
AUTHORITY: security reviewer, round 1 (lighter panel, D-180)

## Summary
- alertHref only builds same-origin paths (/work, /projects, /assistant) from an exact api_url pattern, or /work/<id>/ from django_url. Each id is decoded, checked as a single segment with no dots, slashes or backslashes, then re-encoded. It never returns the retired Django page. Absolute, protocol-relative and javascript: values give no link.
- markAlertRead and saveAlertPreferences both send the csrfHeader. The client middleware sets X-CSRFToken on every POST, PUT, PATCH and DELETE, and throws before sending if no token is held.
- The preferences write body is only revision, email_requested and whatsapp_requested. It sends no user id, and the read and write use the session-scoped /me/alert-preferences path, so another person's preferences cannot be addressed. Access is enforced server-side.
- Delivery words come from the server's receipt state. "Delivered" shows only for `delivered`, and `uncertain` shows as "Not confirmed". No client-side claim is made.
- Targeted checks only. I ran no tests and found no secrets or new dependencies in the diff.

## Findings
None.

## Notes
- An unknown receipt state from the server would render an empty word. This is non-blocking and the types forbid it.

## Pre-merge re-confirm (dab5f018)

Scope checked: `git diff --stat 5f61b03c dab5f018` lists 15 files (+650/-23), all in `frontend/` (mock server, work-live and delivery-overview mocks, DeliveryTab, deliveryModel, useDeliveryOverview, dlvov.css, model.ts, ProjectJourney.tsx, and tests). Nothing under the alert-link, CSRF or preference-write paths changed.

- Alert links: no alert or notification link code changed. The only new `href` values are internal `/work/<id>` links built from `encodeURIComponent` on the work id, unchanged from the reviewed round.
- CSRF writes: no write route was added or altered. The mock change adds only a `get` branch for `deliveryRead`. The test `calls.every((c) => c.method === 'GET')` confirms the delivery overview issues only GET requests.
- Preference writes: none touched.
- `ledger-source.test.tsx` change is a test-only `waitFor` on an existing notice. No production code.
- `work-live.mjs` adds sample fixtures (ids 2501 to 2505), mock-only.

Verdict: PASS. The reviewed round-1 PASS stands for the security lens at dab5f018. No new findings.
