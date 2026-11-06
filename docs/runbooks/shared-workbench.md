# Shared case discovery and human work

The home page searches only currently granted case title/UUID metadata and, with engagement.read, recorded project references and identifier history. Exact tenant and kind filters narrow access. It does not search private source message bodies, financial payloads, staff records or arbitrary evidence text. No hidden-case total is returned.

Pages use a signed user/filter/page-size-bound keyset cursor, with a technical one-hour lifetime and engineering page bounds of25 default/50 maximum. A page link grants no access: every request rechecks active identity and current record/action grants. Changing the query starts a new search. Invalid/expired links ask the user to restart. Tenant authority, business roles and policy values are unchanged.

`/work/` reads existing source records rather than creating another task engine. It distinguishes current PMO action assignment/recorded deadlines, latest Support ownership, current role/delegation-eligible public document quality review, financial intents the user initiated that are held/unknown, and configured B02 summary reviews. Private accepted Finance metadata and Finance report review do not enter the generic PMO quality-review queue. Missing or revoked role/source authority does not silently assign another owner or close history.

Work discovery is bounded and is not an exhaustive task, SLA, priority, approval or execution claim. Deadlines are recorded values; calendars are not recalculated here. Source links open the owning workflow UI, whose services recheck current permissions, versions, policy, calculations, independent reviews and effect receipts before any action. Discovery performs no retries, issuance, approvals, source-owner changes or grant transfers.

Views are authenticated, use no-store responses and escape untrusted displayed metadata. Actual PostgreSQL tests must verify search/cursor/scope/current identity, ownership changes, review/source revocation, actual native private-version exclusion, domain URL routing and unchanged task/financial facts. Fixture success is not operational owner, real-provider or full-product acceptance. See BUILD-TESTS.md for retained runs.
