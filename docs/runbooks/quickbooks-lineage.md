# F01 incumbent QuickBooks reference controls

Source-backed boundary: reference/03-definitions/Finance.json F01-N01 shows TX-001 already posted as QB-101; F01-E01 requires incumbent-state verification for duplicate intake or uncertain posting outcome. Finance retains individual posting/accounting treatment in QuickBooks. This module creates no postings and has no automatic posting/retry tool.

Engineering implementation: /cases/<case>/finance/ledger/ captures immutable source, original entity/realm/date/period, supplied incumbent user and posting/treatment evidence, optional exact case Finance mapping/PPE source references and corrected-reference predecessor. Source capture works before policy configuration. Reference observations are separate immutable records and are not ledger entries. A supplied read adapter validates a strict response allowlist, exact source/scope/date/period/treatment correlation, observation freshness, target reference and incumbent version. Found results are candidates until a separate configured Finance review. Missing, unknown, multiple or mismatched target/version states hold verification; not-found never grants permission to post. Read responses are operator-supplied evidence, not authenticated QuickBooks execution.

F01.verification_rules and F01.review_authority are supplemental typed versioned engineering interfaces, using the existing policy lifecycle. The workbench drafts registered policy references; the ordinary policy workbench validates and activates them. Realm/entity/provider, authorised incumbent user references, approved treatment evidence, maximum observation age, actual Finance principal IDs and independence are explicit inputs. D05 role assignments must also authorize the reviewer. No operational defaults or actual appointments are supplied by the fixture.

The current report rechecks current source head, duplicate identities/target claims, latest observation/decision, policy versions, observation age and current actor/reviewer access. A corrected target requires an explicit same-identity predecessor and fresh observation/review. Historical records remain visible. Different source references claiming a target hold review. Unlinked duplicate records remain an investigation hold; cross-case ambiguity requires scoped operator/Finance investigation and is not silently discarded. The bounded local agent selects only reference/status metadata and drafts evidence questions; it cannot approve or post.

Grant case.read, finance.read and ledger.read for scoped viewing. Additional actions ledger.capture, ledger.verify, ledger.review, agent.ledger and policy.configure are independent grants. Responses use no-store. Source evidence is captured through the existing evidence UI; choose ledger_source or quickbooks_verification and supply the workbench schema. All writes use existing case revision/locks/audit; identity advisory locks serialize cross-case claims. No remote side effect exists, so there is no posting outbox or resend operation.

Remaining engineering: authenticated native QuickBooks read contracts, provider/schema/identity verification, cross-case duplicate resolution with scoped owner decisions and source-specific/native operational acceptance. Supplied Finance-reviewed evidence is not native authenticity. Missing policy values and unsupported native adapters are separate gaps. No invoices, cash, journal amounts or existing Finance histories are changed.


Actual verification: RUN117: 18 / OK / 51.970s; RUN118: 90 / FAILED (failures=1) / 365.382s; RUN119: 28 / FAILED (errors=1) / 126.884s; RUN120: 2 / OK / 5.631s; RUN121: 28 / OK / 132.568s.

RUN118 passed89/90: the shared catalogue assertion still expected79 rather than81 interfaces; updated before RUN119. RUN119 passed27/28: a new access-revocation fixture reused QB-101 for a different source, so the target-collision guard correctly held its review; fixture now uses QB-NEW. RUN120 verifies the final human-readable template. RUN121 verifies final F01 behavior, real two-connection races and the corrected shared catalogue test. Overlapping counts are not added. Supplied/deterministic evidence is not native QuickBooks authentication, real-provider evaluation or operational owner acceptance.

## Optional native QBO read component (781)

`adapters.quickbooks_online` implements an optional **QuickBooks Online**, Invoice-only,
exact-ID GET transport. It is not a choice of the operational accounting product or entity.
The integration registry may contain `quickbooks_reads`; its absence leaves no native
reads configured. Entries have exactly `enabled` (boolean), `environment` (`sandbox` or
`production`), numeric-string `realm`, `entity` (`Invoice`), explicit numeric-string
`minor_version`, and `credential_ref`, `credential_revision`, `principal_ref`. Credential
references reuse the existing `secrets` map, never contain tokens. Keep `enabled: false`
until product, company, entity, consent and secret delivery are explicitly established.
The accounting OAuth scope is not read-only: this component enforces GET-only locally.
There is no arbitrary URL/query, refresh, posting, payment or token-persistence interface.

The pure `ReadIntent` freezes exact case/source revision, complete binding and object ID.
`read` requires a matching current binding and credential revision and a caller-provided
secure reference resolver. `Observation` is frozen and records local observation time,
status, optional SyncToken/TxnDate and a 60-second throttle delay. Repeated reads yield
new observations, not replacement history. No response body/customer/line item is retained.
404 means `not_observed`, not proof of business nonexistence. Timeout is unavailable,
not absence. There are no automatic retries; the application scheduler must enforce the
returned delay and current scope before authorizing a later read.

### F01 application integration contract (not implemented by this component)

Reuse immutable case evidence for a distinct `qbo_native_observation` envelope rather
than a `quickbooks_verification` RESPONSE or LedgerCheck. Reserve an immutable intent
under existing ledger scope/case locks after `ledger.read`/`ledger.verify` permissions,
current source head, target and policy checks. Include exact lineage/evidence ID, case
revision, policy revisions, registry alias and binding digest in that persisted envelope.
Resolve only the credential reference after authorization; execute the read outside a
transaction; then reacquire the same scope, recheck actor grants/current source/policies,
credential revision and configured target before recording an immutable observation.
Changed scope must reject linking, not rewrite the remote result or historical intent.
Persist a new observation per attempt and retain uncertain outcomes. No business effect
or posting outbox is required for these reads. Synthetic transport tests do not establish
this application's authorization, persistence, concurrency or freshness guarantees.

An `observed_object` may support **only** the observed realm/entity/ID/version/date facts.
Intuit does not establish PSL source_reference, accounting_period, treatment_evidence_id,
incumbent user rights or authorization to approve. Those remain separately sourced and
reviewed assertions. Existing F01 Finance decisions, policy currentness and cross-case
collision controls must remain authoritative. Do not convert this object into a supplied
RESPONSE to sidestep those checks. Add native PostgreSQL tests before accepting the link.
No schema migration is required for the pure component; persistence design remains to
be verified against evidence immutability before a later application increment.

### Remaining inputs and verification

Confirm QBO versus Desktop; approved entity and exact authoritative target-ID mapping;
realm/environment and minor version; app ownership/consent and authorized principal;
secure expiring-token delivery/refresh ownership; approved projection/retention. HOD/source
owners supply business identity, period/treatment and review authority. No such selection,
credential or policy has been invented. Component tests use synthetic tokens/responses
only. Native app linkage, live Intuit acceptance and provider setup remain incomplete.
Browser tests are excluded by current user direction.

Official protocol references used by the feasibility audit:
- https://developer.intuit.com/docs/api/accounting/invoice
- https://static.developer.intuit.com/output_html/qbo/docs/develop/authentication-and-authorization/oauth-2.0.html
- https://static.developer.intuit.com/output_html/qbo/docs/develop/troubleshooting/error-codes.html
- https://static.developer.intuit.com/output_html/qbo/docs/learn/limits-and-throttles.html
