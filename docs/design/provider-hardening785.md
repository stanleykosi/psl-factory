# Provider hardening785: accepted bounded synthetic verification

## Current acceptance status

The original source-only proposal and planned verification below are retained as historical implementation context, not current unrun status. Bounded785 completed35 native tests at3548a10 and was locally integrated with sourceb7567bd4a4fe24ef9fda116388f57094b90c6b0b. Acceptance/proof record: d2efff5cd38ff06fe74cacabfb182926ad041e64; BUILD-TESTS.md, “Current local integration: accepted784/785”. Local-only proof is retained under docs/test-evidence/accepted784-785/; do not publish its logs, snapshots or manifests.

The native proof includes known-secret echo rejection at the exact RPC stage, sanitized persisted outcomes and no-replay contrasts. Independent reviews recorded primary preservation, metadata/FK comparisons with sequence differences disclosed, restart equality and clean shutdown. Integration itself started no database. The37 component tests described below and the35 native tests are different selections, not a combined current-source acceptance count.

No actual Intuit schema, OAuth consent, credential, live provider, browser or deployment acceptance is established. Exact known-bearer rejection is not arbitrary secret-transformation detection. The5-second body-read budget is not a hard DNS/TLS/header/framing or end-to-end deadline. Full108 acceptance and held-work boundaries remain unchanged.

## Historical source-only checkpoint

Base: accepted4d5074cb1755061b7bea9adbcccb32565b70e1d8. No production broker/model/schema, authorization, financial policy, endpoint, tool identity or retry behavior changes. No live credential, provider call, database action or cold-cluster action occurred.

## Known-secret echo rejection

The hosted MCP client rejects a decoded remote response containing its actual bearer credential in any string key or value, including nested lists/objects and JSON-escaped characters. It does not redact and continue with modified evidence. The fixed sanitized exception never contains the credential. The check applies at the generic request boundary and independently before returning discovery or tool projection. Existing schema validation, fingerprint matching, read-only exact tool and output projection remain unchanged.

The actual broker execute/probe function bodies were exercised with synthetic dependencies, showing that an echo becomes unknown/projection-null or a sanitized discovery failure, not retained secret-bearing evidence. This is exact-value/substring defense, not a claim to detect arbitrary encodings, transformed secret fragments or unrelated secrets. The token is never printed or written by the new code/tests. All test credentials are invented local strings.

## REST elapsed body-read budget

Replace a single `read(65537)` with `read1` chunks of at most4096 bytes, retaining the existing65536-byte response limit and at most one overflow byte for protocol rejection. A monotonic5-second body budget is checked before and after every read, including EOF. An exhausted budget raises a fixed TimeoutError; the unchanged adapter read boundary maps it to unavailable, with no automatic retry.

The5-second socket timeout remains explicit and unchanged. This is NOT a hard5-second end-to-end network deadline. DNS, TLS, initial HTTP headers, OS scheduling and HTTP chunk framing inside a blocking read can exceed the measured body budget before control returns. A read started just before budget expiry may also consume a blocking operation's socket timeout. Once control returns, late bytes/EOF are rejected. Hard OS-enforced network wall-time cancellation would require separately designed transport/supervision; no private socket internals or background thread leak is introduced here.

## Historical verification and later native plan

37 component tests pass normal and optimized Python: existing10REST+16MCP and11new hardening regressions. These use only synthetic response objects and mocks; no DB/socket/provider or live credential. Added tests cover nested/escaped value/key echoes, discovery and schema-valid projection rejection, unchanged good projection, early request-boundary rejection, exact broker unknown/discovery-failure handling, chunk sizing, EOF/deadline checks and size overflow. Existing transport fixture now implements read1 and verifies chunk bounds rather than requiring the removed monolithic read size.

Independent source review must precede composition. Focused native persistence follow-up, under separate runtime clearance, should exercise an MCP read returning a synthetic echoed credential and verify persisted outcome is unknown/projection-null; readiness discovery should fail without raw credential-bearing inventory. Existing native MCP/REST regression selections remain relevant but have NOT been rerun here. This patch does not change any migrations or native test fixtures and does not claim database acceptance.

## Historical source-only native persistence definitions

Two native tests now extend the unchanged accepted NativeMCPTests TransactionTestCase fixture. They retain the actual Client discovery/call guard and native broker/readiness persistence, mocking only external RPC results and initialized notification. One rejects a synthetic credential echoed in discovery, proves the probe is unknown with no observation and operator retry is denied. The other uses an explicitly reviewed synthetic schema permitting a note field, rejects a schema-valid credential echo, and verifies a single started/completed audit, unknown/null persisted projection, original-only reconciliation with no further RPC, and denied redispatch. Both scan case Evidence/Audit and readiness probe/observation/assessment/review state for the synthetic credential and assert no Finance check exists.

All original native MCP methods remain AST-identical. Exact regression selection is14existingREST+19existingMCP+2newMCP=35, listed in provider-hardening785-native.json. Guarded Django setup/discovery finds exactly35 with Django/psycopg/socket connections forbidden. None were executed. Separate clearance must pin the completed783 primary/test baselines and preserve the owned777 schema, raw row/FK comparisons, resources and process supervision. No migration or database reset is authorized by this source checkpoint.
