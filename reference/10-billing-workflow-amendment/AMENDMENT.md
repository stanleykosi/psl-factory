# PSL planning milestones and payment tracking

## What this amendment settles

Version 0.5 turns the latest user answers into an explicit workflow specification. Detailed planning and costing happen before the client signs the SOW. The requested controlled-document and evidence tooling is a proposed PSL capability, not an existing system we can assume is available. PMO establishes milestone completion. Finance issues invoices and records receipts. Finance does not approve PMO milestone completion.

Three payment stages are described: signed SOW at the beginning, UAT, and completion. These are billing opportunities, not three required payment transactions. A customer may pay irregularly between stages, in several smaller amounts, or before a particular invoice. The system must preserve what was achieved, what was invoiced, what cash was verified and how it was allocated as separate facts.

The expectation of at least 80% paid before deployment is recorded. Whether this is a hard block or permits an exception is still awaiting an answer. The design therefore reports payment position without inventing an enforcement rule or release permission. No 50/30/20 schedule is assumed. This is documentation only, not an application, live invoice action or authority grant.

## How to read this version

The original register, departmental definitions and v0.3/v0.4 files remain unchanged. This folder is the current amendment for the affected rules. U01-U06 in SOURCE-RULES.md identify the latest evidence and its boundaries. The full current source register and all 122 process bindings are supplied in JSON. Unchanged historical source fields remain verbatim; current_amendment_refs identify the applicable update.

The eight execution primitives X01-X08 remain the foundation. This amendment specializes them with 22 typed operations, eight business record types plus Money and Stage definitions, and 31 new mock scenarios. The schemas describe shape. Deterministic authorization, identity checks, arithmetic, state guards and atomic transactions remain mandatory and are not proven by JSON validation.

## The clarified project sequence

First, PMO develops requirements, detailed planning and resource-driven costing with the owning teams. The prescribed PM to Head of PMO to CEO costing approval chain remains; technical, Product, QA and client approvals remain where previously required. Approved client documents then proceed to signature. A signed SOW establishes the opening billing trigger and signed commercial baseline for Finance.

This supersedes the earlier conflicting interpretation that a client signature must exist before detailed planning can occur. It does not mean every other Planning-phase activity is automatically finished at signature, nor does it waive an existing approval. P26 and P63 must apply the clarified sequencing while keeping the remaining phase evidence. Later cost-changing revisions still follow the existing change and costing controls.

The precise UAT record that constitutes the billing event needs to be bound to the agreed workflow. The testimony says reaching UAT, not necessarily final UAT acceptance. Do not substitute the final Product/client UAT approval for the billing event without confirmation. Existing UAT acceptance remains independently required for its original purpose.

Completion is the third payment stage, but its exact billing event is not supplied. Do not equate it automatically with deployment, go-live, hypercare exit or project closure. Capture the contract's completion criterion and amount before issuing that stage's invoice.

## Controlled documents and evidence

PSL is proposed to provide a document/evidence workspace with owned templates, versioned artifacts, content hashes, source links, project associations, role-based access, review status and controlled external publication. This fills a requested capability gap; it does not claim a repository already exists or that files have been migrated.

X05 governs ingestion, parsing, review, release and uncertain delivery. Store the original separately from extracted text, draft summaries and approved output. Signature evidence must identify the exact signed artifact and version; an AI statement that a document is signed is insufficient. External-document review by the prescribed PMO Lead remains. A model may prepare a draft, classify evidence or flag missing fields, but cannot replace actual review or sign-off.

Provide a versioned evidence packet to Finance containing project and contract identity, signed SOW reference, approved schedule version, milestone identity and PMO completion record. Finance can see the necessary commercial evidence without receiving unrelated internal commentary or broader access. Retention periods, storage locations, templates and migration rules are still configuration, not invented policy.

## Independent records and states

A billing schedule belongs to a specific contract version. It contains exactly the three described stage kinds, but each stage has its own evidence predicate, amount and due terms. Missing terms remain null and configuration incomplete. Evidence gathering and payment recording can continue while an affected invoice is blocked by missing terms. No missing stage percentage is filled with a default.

A milestone belongs to PMO. Its states are planned, evidence pending, complete, disputed or superseded. PMO completion atomically creates one correlated Finance handoff. Notification receipt is not invoice issuance. Later correction preserves the previous milestone and identifies affected invoice work rather than erasing it.

An invoice belongs to Finance. Draft, ready, issuance pending, issued, outcome unknown, superseded and voided are document/issuance states. Delivery has a separate status. Settlement is derived from active verified allocations and approved adjustments, not from the milestone state or whether an email was delivered. Superseding a document must not silently cancel an accounting obligation.

A receipt records actual money evidence, not a scheduled obligation or a promise to pay. Reported, verification pending, verified, rejected and reversed are verification states. Allocation status is separate. Payments may be received at any stage. A receipt without verified evidence cannot increase paid percentage. Duplicate source-system transaction identities return the original receipt; changed amounts under the same identity require investigation.

A receipt is assigned to at most one contract in this bounded design. Finance can record an unmatched customer receipt and assign it later with evidence. Assignment is distinct from allocation to an invoice. Multi-contract remittances must remain unmatched until authorized split-record rules and evidence exist; never duplicate the same cash across contracts. Reassignment must first reverse existing invoice allocations atomically and retain all links.

An invoice allocation consumes a verified receipt's unallocated capacity and an invoice's open capacity. Several allocations can distribute one receipt across several invoices in the same contract; several receipts can settle one invoice. All capacity and version checks commit atomically. There is no assumed first-in-first-out priority. Finance's approved allocation policy decides the intended matching.

A balance snapshot is deterministic and immutable. It records its currency, basis, source versions and time. A deployment payment assessment references a fresh snapshot and the agreed qualification rule. Neither record is an approval to deploy.

## Deterministic balances without double counting

For each issued invoice, open amount equals its issued face amount plus applied debit adjustments, less applied credits and active verified-cash allocations. A negative result is an adjustment conflict, not a number to hide by clamping. Draft, pending or uncertain invoices are not silently treated as issued. Receivable is the sum of valid open issued-invoice amounts on the same currency and basis.

Verified contract cash is the total of unique verified receipts explicitly assigned to that contract, less reversals. Count each receipt once, however many invoices it settles. Allocating a receipt does not create another receipt or additional cash. Unassigned customer funds remain visible but do not count toward a particular contract's paid percentage.

Unallocated contract cash equals verified contract cash less active invoice allocations. The remaining contract cash target is max(contract value minus verified contract cash, zero). Excess contract cash is max(verified contract cash minus contract value, zero). These are proposed reporting calculations on an agreed comparable basis, not a declaration of revenue recognition, overdue debt or refund entitlement.

Invoice receivable and remaining contract cash target answer different questions and must not be added together. A customer can have no unpaid issued invoice and still owe future contract-stage cash. Conversely, a customer can have cash on account while an invoice remains unallocated. Display issued, open, overdue when due terms are known, unbilled stages, verified receipts, unapplied cash and disputed adjustments separately.

Use decimal arithmetic, explicit currency, agreed tax and amount basis, precision and rounding. Missing values are not zero. Mixed currencies require an approved conversion policy and recorded rates before aggregation; none is assumed. Credit notes reduce receivables but are not cash payments. Treatment of fees, withholding, discounts, chargebacks and credits in the 80% numerator must be agreed, not guessed.

## The eighty percent assessment

The known expectation is at least 80% paid before deployment. A meaningful percentage needs an agreed denominator, qualifying receipt rule and current contract version. If these are missing, the assessment is unknown and explains what is missing. If configured, compare using exact decimals; rounding must not turn 79.999% into a passing 80% for decision purposes.

Until the pending enforcement clarification is answered, report below expectation, meets expectation or unknown and mark deployment policy unresolved. Do not fabricate an exception approver, add a new hard payment block, or claim deployment is permitted. Existing Engineering Go/No-Go, GLPI, Security, CTO, CEO and other applicable controls remain in force. Payment assessment is an additional evidence view, not a replacement for those decisions.

If the eventual owner decision establishes a hard gate or exceptions, bind that policy as a new version with permitted authority, exception evidence, validity period and re-evaluation rules. A stale payment snapshot cannot stand in for current evidence. Later reversals or contract amendments refresh the assessment without rewriting past release decisions.

## Recovery and corrections

Before external invoice issuance, validate the exact invoice, milestone and schedule versions. Use one semantic issuance key and a durable operation record. A timeout after sending is outcome unknown. Query the trusted destination or obtain independent Finance evidence before deciding whether to retry. A retry may resend an existing invoice document but must not create another invoice merely because delivery failed.

If PMO changes a milestone while Finance is preparing an invoice, a stale-version check prevents committing against obsolete evidence. If an invoice was already accepted externally, retain it and open a Finance correction. Never automatically void, delete or reissue it on the strength of a milestone revision alone.

Receipt and allocation reversals are append-only compensating entries with reason, actor, evidence and authority. Reverse allocations atomically with a receipt reversal so invoice balances reopen and cash is removed only once. Credits, debit notes and any voiding require Finance's actual policy and document requirements. No command here authorizes refunds, transfers, write-offs or ledger posting.

Cancellation is sticky for undispatched work. It cannot make an accepted invoice or received payment disappear. An uncertain external effect remains under reconciliation. Worker leases, fencing tokens, retry limits, queue recovery and human-wait resumption inherit X03/X08; no new unbounded retry loop is introduced. Human decisions and document releases inherit X04/X05.

## A concrete human and agent walkthrough

PMO completes detailed planning and approved costing, then supplies the signed SOW. An evidence agent checks references and prepares a missing-items list. PMO records the opening milestone. A workflow creates one Finance case with the signed baseline and stage schedule, without asking Finance to approve PMO's milestone.

Finance issues the opening invoice under its configured authority. A receipt arrives for less than the invoice amount. Finance verifies it and assigns it to the contract. An agent can suggest matching it to the invoice, explain why, and identify ambiguity; only configured Finance policy determines whether an allocation can execute without a separate click. No such grant is created by this document.

During delivery, additional receipts arrive. Deterministic snapshots show issued receivables and the remaining contract cash target independently. PMO sees payment position without modifying receipt evidence. At UAT, the configured PMO event raises the next Finance handoff. Before deployment, the payment view reports the 80% expectation and unresolved enforcement policy alongside the existing release evidence.

## What remains genuinely unresolved

D02 is closed by the user answer. D11 no longer asks for a pre-existing document tool or Finance milestone approval. D12 requests contract-specific amounts, due terms and exact UAT/completion trigger evidence. D13 records the already-pending question on the consequence of paying less than 80%, plus the basis needed to measure it. D14 requests actual receipt verification, allocation and adjustment policy. The other previously recorded owner/evidence gaps remain unchanged.

The source-rule register distinguishes user clarification, reported testimony, old SOP facts and proposed technical mechanics. The workbook and JSON preserve all 122 IDs. Independent review and schema checks assess the specification; no live workflow, accounting result, owner acceptance or application effectiveness is claimed.

## Precise concurrency and snapshot rules

The command envelope's expected version names the primary aggregate for that action: schedule, milestone, invoice, receipt, allocation or adjustment. Zero denotes creation. Balance and assessment commands use the current contract snapshot revision. Embedded versions must agree. Commands that consume several records must check all relevant versions and capacities in one transaction.

Invoice issuance reserves dispatch against the current invoice, milestone and schedule versions and cancellation tombstones atomically. Revision or cancellation before that reservation prevents dispatch. Revision or cancellation after reservation may race with external acceptance, so the operation stays potentially effective until reconciled. The system cannot promise atomicity with an external invoice service. A milestone and its durable handoff/outbox record commit together; external delivery is asynchronous with its own receipt.

A calculation service constructs its own complete authorized snapshot, with a high-water mark and all relevant invoices, receipts, assignments, allocations, adjustments and schedule/basis versions. Caller-supplied subsets cannot produce a valid balance. Missing or stale manifests block affected results. The returned snapshot retains its source manifest for audit.

Receipt reversals are full-only in this bounded contract and can apply only once per immutable verified cash lot, even if submitted with different adjustment IDs. The reversal amount must equal the original gross receipt and reverse linked allocations atomically. Partial refunds or chargebacks require an approved additional treatment; they are not silently modelled as full reversals. Count gross ever-verified receipts, including those later reversed, less applied full reversal amounts once. Do not filter out a reversed receipt and then subtract it again. Allocation reversals are also full-only and unique per allocation.

P21's pre-signature alignment uses current draft PRD and planned scope. Preserve both documented alignment purposes, but do not let the old signed-baseline prerequisite reintroduce a cycle before detailed planning. After signature, relevant changes can be revalidated against the signed baseline; this is distinct from requiring a signature before planning begins.

A correction operation has its own pending, applied or outcome-unknown state, distinct from the original invoice's proven issuance. An uncertain correction keeps the original obligation visible and marks the net result for adjustment review. The canonical obligation key and corrects-invoice lineage prevent original and replacement documents being counted as two debts. A known delivered artifact remains delivered even if a later delivery attempt fails; attempts bind the invoice version, artifact hash and destination.


A verified cash lot is bound to the exact receipt version and gross amount. Corrections retain the logical source transaction and correction-of-version lineage; after full reversal, a verified corrected successor receives a new cash-lot identity. Reversal uniqueness and amount checks target that lot, not the reusable logical receipt ID. At most one unreversed active verified lot exists in the transaction lineage. Snapshots sum gross verified lots less their own applied reversals once.
