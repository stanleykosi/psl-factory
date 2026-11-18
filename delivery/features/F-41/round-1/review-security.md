VERDICT: PASS
REVIEWER: reviewer-security
COMMIT: ee7d652f59577f8005fa6587ffc5c0aca6253e48
AUTHORITY: delivery security review

## Summary
- The reminder send only goes out through the existing `useWorkspaceStep` hook, from a step the backend lists in `workspace.steps`. `disabled_reason` is honoured, the shared client adds `X-CSRFToken` to every write, and a double press sends once.
- Each press gets one idempotency key, and a manual retry reuses it. After an `effect_uncertain` result, a 5xx, a network failure or a timeout on a step that sends, every step is locked. The lock comes back after a reload because the item itself is `effect_uncertain` or carries `reconcile`. No resend is offered and the code never retries by itself.
- "Delivered" is shown only from each recipient's own `receipt`. 401 goes to the signed-out page. 403 and 404 show one view with no client, amount, count or invoice id. All returned text, including Chidi's lines, client names, the draft and the attachment label, is rendered as React text. No `dangerouslySetInnerHTML` is used.
- Links go only to `/work/<id>`, and the id must match `RECORD_ID` (`^[A-Za-z0-9][A-Za-z0-9._-]*$`) and is passed through `encodeURIComponent`. The attachment is never a link. The browser computes no amounts: the arithmetic grep over the diff returns nothing.
- The new mock E-INVOICES route refuses `pm` and `none`, validates `limit`, `cursor` and `status`, and validates every reply against the v7 schema. Adding it to `M1_OPERATIONS` sends it through the shared scenario and persona checks and widens nothing the mock trusts.

## Findings
None.

## Notes
- Non-blocking, pre-existing: the mock's E-WORK-STEP (`frontend/mock/workspace.mjs`, `handle`) checks only that the step key exists in `workspace.steps`. It does not refuse `send_reminder` under a new key while the item is `effect_uncertain` (W-3803.next, W-3805 and W-3806 still list `send_reminder` with no `disabled_reason`). It also does not check persona or `disabled_reason`. The browser lock is what holds today. This is acceptable for the contract mock, because `delivery/BACKEND-HANDOFF.md` (F-41 section, "Priority 1 before a real send") requires the backend to refuse any send while the item is uncertain or awaiting reconcile, and to apply key idempotency, before any real provider is used. The backend should also send a `disabled_reason`, or no `send_reminder` step, in that state.
- Non-blocking: the new lookup `<id>.next.<step>` in `workspace.mjs` runs only after the step has been validated against `workspace.steps`. It reads an in-memory map loaded at startup, so it gives no path or prototype access. It does not collide with F-28's `W-2301.next.internal` (W-2301 has no step named `internal`).
- Non-blocking: the 401 page puts `q` into `next=` (`/finance/payments?q=…`). This is the person's own search, already in their address bar, and the path is fixed and internal, so it cannot be used as an open redirect.
- Non-blocking: the tests contain no explicit HTML-injection case (for example, a fixture line containing `<img onerror>`). React escaping covers this. Such a test would be a cheap guard if a markdown renderer is ever added.
- Workspace steps carry no `you_can_act`; the typed contract has it only on tasks (`schema.d.ts:1365`). Authority on this page is therefore the backend's returned steps, their `disabled_reason` and `allowed_actions` for reconcile. The page reads no `/me` for authority.
- Secrets: none were found in the fixtures or the diff. Recipient addresses use `.example` domains, and the CSRF token in tests is the mock's `mock-csrf-finance_lead`. Dependencies: no new packages (`ajv` and `ajv-formats` were already used by the mock).
