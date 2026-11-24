VERDICT: PASS
COMMIT: 5f61b03c833db545052bd88a34ed1a1ac62eb608
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
