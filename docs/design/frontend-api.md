# Factory API for the frontend cutover

The live Django implementation serves a versioned OpenAPI contract at `/api/v1/openapi.json`. The exported contract is generated from the mounted route registry and the request schemas used by Django. The existing frontend prototype uses the design-time v7 contract and its mock server. Generate a separate client from the live contract for the cutover and reconcile its field names and shapes feature by feature.

## Use the live API

Run these commands from the repository root. The first emits machine-readable OpenAPI. The second expands the cutover map to all 262 accepted states and checks every API operation and Django route it references.

```powershell
.venv\Scripts\python.exe manage.py export_factory_api
.venv\Scripts\python.exe manage.py export_factory_api --screen-map
```

- Serve the future frontend and Django API on the same origin. Keep ordinary Django login, recovery and invitations during the cutover. The Django session and staff lifecycle checks apply to both clients.
- Read `GET /api/v1/me` after sign-in. Send its `csrf_token` in `X-CSRFToken` on writes, with the session cookie. The token belongs to the current session. Private responses are marked `no-store`.
- Use the current server-issued record identifiers and revisions. Treat a conflict as a request to reload, inspect the current record and make a fresh decision. A permission response or an unavailable record stops that operation.
- Submit multipart private files through the existing upload service. Fetch file and detailed source links through their authenticated Django URLs. Agent drafts keep the exact source or attempt pin through review, recovery and handoff.
- Send initiation and Assistant requests with the same idempotency key for the same intent. Treat an accepted command as an acknowledgement. Refresh authorized work or receipt status for the business outcome. Explicit release and receipt reconciliation remain separate.
- Read queue coverage and handle incomplete results and pages. Amounts are decimal strings where projected as money. Unknown values remain null.

## Workflow coverage

The [cutover map](../../contracts/factory-api-screen-map.json) groups the 262 states by screen and lists the available JSON operations, the working Django routes and the remaining contracts. A grouped mapping points to workflow capability. It does not imply that every variation already has a JSON equivalent.

The current API covers intake against exact native sources for all 25 existing factory work definitions. It also covers work and project readback, invoice and Accounting task claims and decisions, reviewed project and Finance document actions, minutes confirmation, bid pack and outcome handling, authorised receipt reconciliation, department chat, eight scoped file agents, client contacts, alerts and verified-channel preferences. Its invoice, Payroll and document commands use the same durable services and authority checks as the Django pages.

Prioritize the next cutover in this order.

1. Shared navigation, work queues, project directory and project tabs, using current scope and pagination. Keep native links for controlled record and proof readback.
2. Exact Finance review and recovery, minutes and bid packs, and current-source Assistant conversations. Use the typed draft and start endpoints to require the saved version during handoff.
3. Closed JSON projections for detailed domain records and their scoped commands. The map tracks remaining release and Go-live attestations, change and incident authority, planning and costing detail, Finance imports, payments and corrections, private HR and Payroll records, reports and publication receipts.
4. Account and staff administration, template intake and policy Setup. Retain the native Django forms until equivalents have permission, concurrency and browser parity. HOD-owned values remain deferred.

Keep the current Railway browser ledger as the Django functional baseline. Test newly migrated screens against live API responses with synthetic data and the ordinary test roles before switching their navigation.
