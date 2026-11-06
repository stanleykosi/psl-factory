Implemented bounded checkpoint28 October2026. See docs/runbooks/finance-followup-successors.md and BUILD-TESTS.md. The historical proposal below remains design provenance; supported v1 relationships and actual test limits are stated in the runbook. New invoice-ID mappings and authenticated source request transport remain separate engineering work.

# Proposed next: source-owned Finance financial successor lineage

Engineering proposal, not implemented behavior or a source-backed financial policy.

Native acknowledgement/current-disposition readback proves the exact current source request and owner disposition under the registered internal v1 authority contract. An investigation link is non-executing. The next connected step is explicit lineage from that source-owned request to a separately created current invoice/correction successor, with ordinary business reviews and independent execution controls still enforced by the existing source services.

Inspect the incumbent `InvoiceJob` generations, legal correction document versions, canonical receipt semantics and operator replacement rules. A new lineage record should distinguish an investigation link to an existing intent from a proposed financial successor. It must record original request/publication evidence, original invoice/correction, current owned successor and the reason/evidence for the relationship. Unknown effects must be reconciled before competing replacement; no archived job replay or copied grants.

Expose typed versioned lineage criteria and source-owner UI/agent tools. Configuration controls eligible relation kinds, current owner/role and evidence requirements without inventing an actual approver or financial rule. Hold only dependent relation acceptance/dispatch when values are absent. Creating lineage must never create an invoice, waive debt, apply a correction or substitute for ordinary current Finance review/issuance/release controls.

Extend native metadata readback to distinguish proposed, independently reviewed, current and superseded lineage from actual financial receipt proof. Preserve old request/decision/observation history. Add real PostgreSQL/current-source tests for cross-case/correction/obligation mismatch, source policy/role/grant/intent changes, duplicate ownership, unknown outcomes, current successor receipts and fresh-process recovery. Reuse existing canonical invoice/correction services and shared evidence paths; avoid recursive AF13 chains.

Authenticated source request transport, cross-identifier mappings, other-family/vendor adapters and actual provider/owner/provisioning/security/load/UAT acceptance remain separate engineering/deployment gaps. All122 exact process identities and13 families remain tracked.
