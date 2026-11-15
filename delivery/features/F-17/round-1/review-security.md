VERDICT: PASS
COMMIT: 1432023f985798659f2cc4342c3a745936d30324
REVIEWER: reviewer-security
AUTHORITY: reviewer-security

## Summary
- The E-WORK-STEP write goes through the shared client, so the CSRF token is attached there. The mock also rejects a missing or wrong token with 403.
- One idempotency key per attempt. A synchronous guard allows one write at a time. There are no timers or effects that send. After effect_uncertain every step is locked. A sending step that fails over the network or with a 5xx is locked and its key is dropped, so it offers no Try again.
- Links are built only from app ids. refPath accepts a plain record id and builds /work or /projects from it, and isAppPath is checked as well. The decision link is built from the page id and the step's task_id, both encoded. No URL from the response is followed.
- Restricted fields, items, cells and sections draw only the word "Restricted" or their label. No value is read. All text goes through React, with no innerHTML. No eligibility comes from /me: steps show only as the backend returns them, and only when a numeric revision is present.
- No new dependency and no secrets. The change is mock-only and D-LINE-WORKSPACE is `proposed`. The mock's idempotency map proves one send per key on the mock, not the backend's promise.

## Findings
None.

## Notes
- Non-blocking: the resend lock lives in page state. After a full browser reload, a sending step that failed with an unknown outcome can be pressed again with a new key. Safe only if the backend holds its idempotency and reconcile promise (PMO-0-2, unbuilt). The backend feature must enforce that server-side, and the page must not be counted as the guard.
- Non-blocking: the `sends` flag comes from the step descriptor. A backend step that sends but omits `sends` would get Try again after a network failure. The backend must set it. The reused key is the only protection in that case.
- Non-blocking: the money currency is fixed to NGN in the frame (already listed as a contract proposal).
