# D03 verified billing statement and invoice-release evidence

FIN P0023 describes prices on the report; machine transcript VID U0079 says “after I sign it.” This is an unresolved source conflict, not proof of an invoice signature or release gate. F29/F30 preserve Finance ownership and incumbent Power Automate work; generation, approval, posting, sending, receipts and deployment remain distinct. This implementation is a versioned evidence/adapter design, not a new business approval matrix.

## Source clarification and configuration

Capture d03_source evidence and a typed source version at `/cases/<id>/finance/billing-evidence/`. A source is either a billing statement or an exact flow/environment contract. Quotes must occur in the supplied evidence; no missing recording is reconstructed. Capture is available before D03 policy. Tenant/system/external reference/source version is claimed once; exact duplicate capture returns its historical receipt, while conflicting/cross-case claims hold. Explicit same-kind predecessors preserve corrected versions.

A principal with current Finance D05 authority, d03.review and d03.source.read confirms, disputes or withdraws the source. Stated ownership, an admin flag, an ASR string or agent output grants no authority. Statement meanings include prices, signature, other and unresolved; source interpretation alone never creates a signature gate. The original D03.verified_billing_statement component references the exact current confirmed source/hash/review; unresolved meaning cannot activate it.

The original D03.invoice_release_control_refs array references exact current confirmed flow contracts, billing coverage and effect (issue or deliver), explicit implementation, flow/environment versions, freshness and source-confirmed control requirements. Unknown requirements are distinct from an explicit empty list. Configuration cannot silently add a control not present in the confirmed source contract. Values are independently activated through the existing typed policy lifecycle. Neither component supplies rates, taxes, currencies, approvers or a universal signature rule.

## Connected invoice path

1. Continue existing usage/pricing/preparation and Finance invoice drafting/review services. They retain their current rules and unknown-value behavior.
2. Finance explicitly enrolls exact BaaS coverage using d03_enrollment evidence. D03 applies to usage invoices for that business coverage; other usage contracts and project stages remain independent. Once enrolled, a new coverage version or alias of the same customer/service/contract cannot silently bypass enrollment.
3. Record typed `d03_control_*` evidence for the exact invoice hash, preparation key, effect, control key, source/flow/environment and source version. Passed, failed, unknown and unavailable observations preserve history. The observer must have current Finance authority and source access; supplied references are not native Power Automate verification.
4. Assess exact current inputs and bind the assessed evidence. Binding is not a second invoice approval. The existing Finance invoice approval is still required. Missing/unknown/unavailable/expired control evidence, changed sources/reviews/policies/authority or newer assessments require fresh evidence, assessment and binding.
5. Reserve issuance or delivery through the existing invoice service. The reserved intent pins the D03 context. The actual worker rechecks current source/policy/authority at dispatch. The implemented effect is the existing internal invoice register/inbox. Incumbent-reference/unsupported native modes leave evidence work available but hold dependent dispatch until a reviewed native adapter exists.

## Recovery and financial boundaries

Run `.venv/Scripts/python manage.py work_invoices --limit 20`. Existing leases, fences, stable effect identity and receipt-first lookup are reused. A committed receipt is reconciled before current authority checks or resend, including after a lost response and later source revocation. Unknown outcomes cannot be blindly cancelled/retried. Held work with changed evidence requires explicit operator intent replacement and a new generation. Never overwrite a proven invoice issue/delivery.

A later source-access failure does not erase an issued invoice, waive debt, reverse cash, change allocation or substitute a payment exception for independent release controls. Correction/void/cash successor workflows retain their existing separate authority and evidence. No D03 source interpretation posts a journal or deploys a release.

## UI, access and agents

The workbench shows source versions/confirmation, enrolled coverage, recorded versus current assessment status, bindings and permitted typed actions. Source and control-history JSON endpoints require d03.source.read on the exact case. Generic evidence display/timeline, document/extraction paths and AF13 source repackaging exclude raw D03 source/control evidence. The shared restricted-evidence helper also preserves prior P02 and migration protections.

The deterministic investigation reads at most 30 source versions and 20 assessments. It traces stale/unknown evidence and asks exact Finance/source questions without reading source bodies, inventing rates, approving invoices or running financial commands. Mock/internal adapter tests are separate from real-provider or native Power Automate evidence.

Remaining engineering includes authenticated incumbent flow discovery/read/dispatch and lookup receipts, actual Finance source confirmation and source-specific contracts/UAT. Actual owners/access, current source wording, effects/control lists, flow/environment and freshness remain policy/evidence inputs. Explicit synthetic fixtures prove infrastructure; they are not PSL policy or appointments.
